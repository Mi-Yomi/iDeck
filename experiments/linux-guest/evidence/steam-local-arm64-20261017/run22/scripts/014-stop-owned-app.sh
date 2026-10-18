set -eu
export PYTHONDONTWRITEBYTECODE=1
python3 - <<'PY'
from pathlib import Path
import os,json,signal,subprocess,time,select
out=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-desktop-native-v17')
assert (out/'summary.json').is_file(),'monitor must finish before controlled application stop'
assert os.geteuid()==0 and os.uname().release=='6.18.35-0-virt'
assert {'ideck.steam_experiment=1','ideck.steam_disk_grow=1'}<=set(Path('/proc/cmdline').read_text().split())
root='/home/ideck/.local/share/Steam/'
original_ns=os.readlink('/proc/self/ns/mnt');namespaces=set();sent=[];records=[]
launch_rows=[json.loads(line.split('=',1)[1]) for line in (out/'launcher.log').read_text().splitlines() if line.startswith('IDECK_NAMESPACE_ROOT_READY=')]
assert len(launch_rows)==1
launch_record=launch_rows[0]
assert launch_record['before']['mount_namespace']==original_ns
private_ns=launch_record['rooted']['mount_namespace']
assert private_ns!=original_ns and private_ns.startswith('mnt:[')
assert launch_record['rooted']['root']==launch_record['before']['root']
namespaces.add(private_ns)
def info(pid):
    p=Path('/proc')/str(pid);f=(p/'stat').read_text().rsplit(') ',1)[1].split();d=dict(x.split(':',1) for x in (p/'status').read_text().splitlines() if ':' in x)
    return {'pid':int(pid),'starttime':f[19],'state':f[0],'uid':d['Uid'].split(),'tracer':int(d['TracerPid']),'ppid':int(d['PPid']),'exe':os.readlink(p/'exe'),'mnt':os.readlink(p/'ns/mnt'),'argv':(p/'cmdline').read_bytes()}
def scan():
    rows=[]
    for p in Path('/proc').iterdir():
        if not p.name.isdecimal():continue
        try:i=info(p.name)
        except (FileNotFoundError,ProcessLookupError):continue
        if i['uid']!=['1000']*4 or i['state']=='Z':continue
        if i['exe'].startswith(root) or b'/usr/local/bin/ideck-steam' in i['argv']:
            assert i['mnt']!=original_ns,'unexpected original mount namespace for launch'
            namespaces.add(i['mnt']);rows.append(i)
    for p in Path('/proc').iterdir():
        if not p.name.isdecimal():continue
        try:i=info(p.name)
        except (FileNotFoundError,ProcessLookupError):continue
        if i['uid']==['1000']*4 and i['state']!='Z' and i['mnt'] in namespaces and i['pid'] not in {r['pid'] for r in rows}:rows.append(i)
    return rows
def same(a,b):return all(a[k]==b[k] for k in ('pid','starttime','uid','exe','mnt'))
def send(row,sig):
    fd=os.pidfd_open(row['pid'])
    try:
        assert same(info(row['pid']),row),'identity changed'
        signal.pidfd_send_signal(fd,sig);sent.append({'pid':row['pid'],'signal':signal.Signals(sig).name})
    finally:os.close(fd)
def validate_tracers(rows):
    verified=[]
    for row in rows:
        for task in (Path('/proc')/str(row['pid'])/'task').iterdir():
            try:
                d=dict(x.split(':',1) for x in (task/'status').read_text().splitlines() if ':' in x)
                tracer=int(d['TracerPid'])
                if not tracer:continue
                t=info(tracer)
                assert t['uid']==['1000']*4 and t['exe'].startswith(root) and t['ppid']==row['pid'],'unknown tracer; no application signals authorized'
                verified.append({'target_tgid':row['pid'],'tid':int(task.name),'tracer_pid':tracer,'tracer_starttime':t['starttime'],'tracer_exe':t['exe']})
            except (FileNotFoundError,ProcessLookupError):continue
    return verified
initial=scan();verified_tracers=validate_tracers(initial)
# Resume only this watcher's group-stopped, untraced launch processes for an
# ordinary client shutdown request. No diagnostic ptrace or target memory write.
for row in initial:
    if row['state']=='T' and row['tracer']==0:
        try:send(row,signal.SIGCONT)
        except (FileNotFoundError,ProcessLookupError):pass
request={'attempted':False}
if initial:
    env={'PATH':'/usr/local/bin:/usr/bin:/bin','HOME':'/home/ideck','USER':'ideck','LOGNAME':'ideck','LANG':'C.UTF-8','DISPLAY':':0','XAUTHORITY':'/run/user/1000/Xauthority','XDG_RUNTIME_DIR':'/run/user/1000'}
    with (out/'shutdown-request.log').open('wb') as log:
        child=subprocess.Popen(['setpriv','--reuid=1000','--regid=1000','--init-groups','/usr/local/bin/ideck-steam','stop'],env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        request={'attempted':True,'pid':child.pid}
        try:request['exit_code']=child.wait(timeout=4)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid,signal.SIGTERM)
            try:child.wait(timeout=1)
            except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait(timeout=3)
            request.update(timeout=True,exit_code=child.returncode)
    time.sleep(.5)
remaining=scan();verified_tracers.extend(validate_tracers(remaining));forced_application=bool(remaining)
# Explicitly terminate only the recorded guest-owned launch tree/namespaces.
# These are application exit signals, not a competing debugger or cleanup fix.
for row in remaining:
    records.append({k:v for k,v in row.items() if k!='argv'})
    try:
        send(row,signal.SIGTERM)
        if row['state']=='T' and row['tracer']==0:send(row,signal.SIGCONT)
    except (FileNotFoundError,ProcessLookupError):pass
time.sleep(2)
for row in scan():
    try:send(row,signal.SIGKILL)
    except (FileNotFoundError,ProcessLookupError):pass
deadline=time.monotonic()+25
while time.monotonic()<deadline:
    remaining=scan()
    if not remaining:break
    time.sleep(.25)
result={'shutdown_request':request,'verified_owned_assertion_tracers':verified_tracers,'application_stop':'unclean owned-process termination' if forced_application else 'ordinary shutdown completed','owned_mount_namespaces':sorted(namespaces),'signals':sent,'terminated_identities':records,'remaining':[{k:v for k,v in r.items() if k!='argv'} for r in remaining],'ready_for_original_vm_stop':not remaining,'original_pid1_shutdown_changed':False,'time_ns':time.time_ns()}
(out/'application-stop.json').write_text(json.dumps(result,indent=2)+'\n');print('IDECK_APPLICATION_STOP='+json.dumps(result),flush=True)
assert not remaining,'do not request VM Stop while launch processes remain'
time.sleep(2)
PY