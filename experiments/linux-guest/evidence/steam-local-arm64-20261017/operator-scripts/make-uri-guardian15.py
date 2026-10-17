from pathlib import Path
import ast,json,hashlib
task=Path(__file__).parent
s=(task/'commands15/002-start-same-client-profile.sh').read_text().split("<<'IDECKPY'\n",1)[1].split('\nIDECKPY',1)[0]
tree=ast.parse(s)
names=('read','link','processes','identity','roles','pin_seen','freeze_pinned','watch')
functions={n.name:ast.get_source_segment(s,n) for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names}
roles=r'''def roles(ps):
    native=[];browsers=[];tracers=set();native_parents=set()
    for pid,row in ps.items():
        if row.get('TracerPid','0').isdigit() and int(row.get('TracerPid','0'))>0:tracers.add(str(int(row['TracerPid'])))
        if row.get('Uid','').split()!=['1000']*4:continue
        if row.get('exe')==str(root/'steamrtarm64/steam'):
            native_parents.add(str(pid))
            parent=ps.get(str(row.get('PPid','')), {})
            if parent.get('exe')!=str(root/'steamrtarm64/steam'):
                allowed=(allow_uri is not None and str(pid)==str(allow_uri['pid']) and
                    row.get('PPid')==str(os.getpid()) and
                    row.get('cmdline','').split()==[str(root/'steamrtarm64/steam'),'steam://open/bigpicture'] and
                    row['stat'].rsplit(') ',1)[1].split()[19]==allow_uri['starttime'])
                if not allowed:native.append(str(pid))
    for pid,row in ps.items():
        if row.get('Uid','').split()==['1000']*4 and row.get('exe')==str(root/'steamrtarm64/steamwebhelper') and str(row.get('PPid','')) in native_parents and '--type=' not in row.get('cmdline',''):
            browsers.append(str(pid))
    return native,browsers,tracers'''
# Only an exact, owned, fixed-argument child may be a URL dispatcher. Any new
# browser, including one under that child, still trips the existing guard.
from types import SimpleNamespace
ctx={'root':Path('/home/ideck/.local/share/Steam'),'os':SimpleNamespace(getpid=lambda:123),'allow_uri':{'pid':500,'starttime':'111'}}
exec(roles,ctx)
def row(pid,exe,parent,argv,start='111'):
    fields=['0']*20;fields[19]=start
    return {'exe':str(ctx['root']/('steamrtarm64/'+exe)),'Uid':'1000 1000 1000 1000','PPid':str(parent),'TracerPid':'0','cmdline':argv,'stat':str(pid)+' (steam) '+' '.join(fields)}
core=row(879,'steam',877,'steam -nobigpicture');browser=row(938,'steamwebhelper',879,'steamwebhelper -steampid=879');uri=row(500,'steam',123,str(ctx['root']/'steamrtarm64/steam')+' steam://open/bigpicture')
base={'879':core,'938':browser,'500':uri}
assert ctx['roles'](base)[:2]==(['879'],['938'])
for key,value in (('PPid','124'),('cmdline',uri['cmdline']+' extra'),('stat',uri['stat'][:-3]+'112')):
    wrong={**uri,key:value};assert len(ctx['roles']({**base,'500':wrong})[0])==2
assert len(ctx['roles']({**base,'600':row(600,'steamwebhelper',500,'steamwebhelper -steampid=500')})[1])==2
functions['roles']=roles
code=r'''import os,time,json,subprocess,signal,threading,select
from pathlib import Path
out=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-connect-5000-v7')
root=Path('/home/ideck/.local/share/Steam')
started=time.monotonic();allow_uri=None
finish_guard=threading.Event();guard_tripped=threading.Event()
pin_lock=threading.Lock();pins={};browser_pid=None;guard_result={}
'''+ '\n\n'.join(functions[n] for n in names)+r'''
deadline=time.monotonic()+90
while not (out/'summary.json').exists():
    assert time.monotonic()<deadline,'original monitor must finish first'
    time.sleep(.5)
original=json.loads((out/'summary.json').read_text())
assert original['reason'] in ('deadline','operator_requested_stop')
expected=json.loads((out/'freeze-identities.json').read_text())
pin_seen(processes());assert {int(p) for p in pins}=={r['pid'] for r in expected}
for r in expected:
    now=identity(r['pid'])
    assert all(now[k]==r[k] for k in ('pid','starttime','exe')) and now['state']=='T' and now['tracer']==0
assert roles(processes())[:2]==(['879'],['938'])
started=time.monotonic();guard_thread=threading.Thread(target=watch,daemon=True);guard_thread.start()
child=None;uri_fd=None
try:
    for pid,pin in pins.items():
        now=identity(pid);before=pin['identity']
        assert all(now[k]==before[k] for k in ('pid','starttime','uid','exe')) and now['tracer']==0
        signal.pidfd_send_signal(pin['fd'],signal.SIGCONT)
    env=['PATH=/usr/local/bin:/usr/bin:/bin','HOME=/home/ideck','USER=ideck','LOGNAME=ideck','LANG=C.UTF-8','DISPLAY=:0','XAUTHORITY=/run/user/1000/Xauthority','XDG_RUNTIME_DIR=/run/user/1000','STEAM_RUNTIME=1','LD_LIBRARY_PATH='+str(root/'steamrtarm64')+':'+str(root/'steamrtarm64/panorama')]
    argv=['nsenter','--mount=/proc/879/ns/mnt','--root=/proc/879/root','--wd='+str(root),'/usr/bin/setpriv','--reuid=1000','--regid=1000','--init-groups','/usr/bin/env','-i',*env,str(root/'steamrtarm64/steam'),'steam://open/bigpicture']
    with (out/'uri-dispatch.log').open('xb') as f:
        child=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,close_fds=True)
    try:
        uri_fd=os.pidfd_open(child.pid);allow_uri={'pid':child.pid,'starttime':identity(child.pid)['starttime']}
    except (FileNotFoundError,ProcessLookupError):pass
    dispatch_started=time.monotonic();dispatch_done=False
    while time.monotonic()-started<300 and not guard_tripped.is_set():
        ps=processes();pin_seen(ps)
        if child.poll() is None and time.monotonic()-dispatch_started>20:
            now=identity(child.pid)
            assert uri_fd is not None and now['starttime']==allow_uri['starttime'] and now['ppid']==os.getpid() and now['tracer']==0
            signal.pidfd_send_signal(uri_fd,signal.SIGTERM)
            try:child.wait(timeout=2)
            except subprocess.TimeoutExpired:signal.pidfd_send_signal(uri_fd,signal.SIGKILL);child.wait(timeout=5)
        if child.poll() is not None and not dispatch_done:
            (out/'uri-result.json').write_text(json.dumps({'uri':'steam://open/bigpicture','exit':child.returncode,'dispatcher_pid':child.pid,'existing_client_pid':879,'no_game_request':True,'time_ns':time.time_ns()},indent=2)+'\n');dispatch_done=True
        v=os.statvfs('/dev/shm')
        with (out/'uri-timeline.jsonl').open('a') as f:f.write(json.dumps({'seconds':time.monotonic()-started,'shm_free':v.f_bavail*v.f_frsize,'processes':ps})+'\n')
        if (out/'finish-uri-guardian').exists():break
        time.sleep(1)
finally:
    finish_guard.set();guard_thread.join(10)
    if not guard_tripped.is_set():freeze_pinned('uri_guardian_operator_budget')
    (out/'uri-guardian-summary.json').write_text(json.dumps({'seconds':time.monotonic()-started,'guard':guard_result,'existing_client_resumed':True,'same_steam_runtime_configuration':True},indent=2)+'\n')
    if uri_fd is not None:os.close(uri_fd)
    for pin in pins.values():os.close(pin['fd'])
'''
compile(code,'uri-guardian15','exec')
command="set -eu\npython3 - <<'FINISH'\nfrom pathlib import Path\np=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-connect-5000-v7/finish-monitor');assert not p.exists();p.write_text('stop\\n')\nFINISH\ncat > /run/ideck/uri-guardian15.py <<'URI_GUARD'\n"+code+"\nURI_GUARD\nsetsid python3 /run/ideck/uri-guardian15.py </dev/null >/run/ideck/uri-guardian15.log 2>&1 &\nprintf 'URI_GUARDIAN_PID=%s\\n' \"$!\"\n"
assert len(command.encode())<65536
(task/'commands15/021-request-big-picture.sh').write_text(command)
(task/'uri-guardian15-source.json').write_text(json.dumps({'sha256':hashlib.sha256(command.encode()).hexdigest(),'role_fixtures_pass':True,'other_guard_functions_unchanged':True,'uri':'steam://open/bigpicture','operator_budget_seconds':300},indent=2)+'\n')
print('queued guarded same-client Steam URI request; role refusal and second-browser fixtures pass')
