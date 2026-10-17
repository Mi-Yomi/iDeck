set -eu
python3 - <<'FINISH'
from pathlib import Path
p=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-connect-5000-v9/finish-games-guardian');assert not p.exists();p.write_text('stop\n')
FINISH
cat > /run/ideck/bp-guardian16.py <<'URI_GUARD'
import os,time,json,subprocess,signal,threading,select
from pathlib import Path
out=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-connect-5000-v9')
root=Path('/home/ideck/.local/share/Steam')
started=time.monotonic();allow_uri=None
finish_guard=threading.Event();guard_tripped=threading.Event()
pin_lock=threading.Lock();pins={};browser_pid=None;guard_result={}
def read(path):
    try: return Path(path).read_text(errors='replace')
    except OSError as e: return 'UNAVAILABLE:'+str(e.errno)

def link(path):
    try: return os.readlink(path)
    except OSError: return None

def processes():
    found={}
    for p in Path('/proc').iterdir():
        if not p.name.isdigit(): continue
        comm=read(p/'comm').strip()
        if comm not in ('steam','steamwebhelper','steamerrorreport','steamsysinfo'): continue
        st=read(p/'status'); fields={}
        for line in st.splitlines():
            if ':' in line:
                k,v=line.split(':',1)
                if k in ('Name','State','PPid','Uid','Gid','VmRSS','VmSwap','Threads','NSpid','NoNewPrivs','TracerPid','Seccomp','Cpus_allowed_list'): fields[k]=v.strip()
        fields.update(exe=link(p/'exe'),cmdline=read(p/'cmdline').replace('\x00',' '),stat=read(p/'stat'),wchan=read(p/'wchan'),syscall=read(p/'syscall'),ns={n:link(p/'ns'/n) for n in ('mnt','pid','user','ipc')})
        found[p.name]=fields
    return found

def identity(pid):
    p=Path('/proc')/str(pid)
    fields=(p/'stat').read_text().rsplit(') ',1)[1].split()
    status=dict(x.split(':',1) for x in (p/'status').read_text().splitlines() if ':' in x)
    return {'pid':int(pid),'starttime':fields[19],'exe':os.readlink(p/'exe'),
            'uid':status['Uid'].split(),'state':fields[0],'tracer':int(status['TracerPid']),'ppid':int(status['PPid'])}

def roles(ps):
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
    return native,browsers,tracers

def pin_seen(ps):
    global browser_pid
    natives,browsers,tracers=roles(ps)
    if len(natives)>1:raise RuntimeError("ambiguous native process")
    for pid,row in ps.items():
        if pid in tracers:continue
        if row.get('exe') not in (str(root/'steamrtarm64/steam'),str(root/'steamrtarm64/steamwebhelper')) or row.get('Uid','').split()!=['1000']*4:continue
        with pin_lock:
            if pid in pins:continue
            fd=None
            try:
                fd=os.pidfd_open(int(pid));now=identity(pid)
                if now['uid']!=['1000']*4 or now['exe']!=row['exe'] or now['starttime']!=row['stat'].rsplit(') ',1)[1].split()[19] or now['tracer']:
                    os.close(fd);fd=None;guard_result.setdefault('refused_processes',[]).append(pid);continue
                pins[pid]={'fd':fd,'identity':now,'stopped':False};fd=None
                if pid in browsers:
                    if browser_pid is not None and browser_pid!=pid:guard_result['requested_cause']='second_browser_before_diagnosis';continue
                    browser_pid=pid
            except (FileNotFoundError,ProcessLookupError):
                if fd is not None:os.close(fd)

def freeze_pinned(cause):
    # Never freeze Steam's assertion dumper while it traces an owned parent.
    _,_,protected=roles(processes())
    with pin_lock:
        ordered=sorted(pins.items(),key=lambda item:0 if item[0]==browser_pid else 1 if item[1]['identity']['exe'].endswith('/steam') else 2)
        for pid,pin in ordered:
            if pid in protected:continue
            try:
                now=identity(pid);before=pin['identity']
                if any(now[k]!=before[k] for k in ('pid','starttime','uid')) or now['tracer']:
                    guard_result.setdefault('refused_pins',[]).append({'before':before,'current':now});continue
                if now['exe']!=before['exe']:guard_result.setdefault('owned_exec_changes',[]).append({'before':before,'current':now})
                signal.pidfd_send_signal(pin['fd'],signal.SIGSTOP);pin['stopped']=True
            except (FileNotFoundError,ProcessLookupError):continue
    # Parents are stopped first, so they cannot add another browser/allocator.
    current=processes();pin_seen(current)
    _,_,protected=roles(current)
    with pin_lock:
        for pid,pin in pins.items():
            if pin['stopped'] or pid in protected:continue
            try:
                now=identity(pid);before=pin['identity']
                if any(now[k]!=before[k] for k in ('pid','starttime','uid')) or now['tracer']:
                    guard_result.setdefault('refused_pins',[]).append({'before':before,'current':now});continue
                if now['exe']!=before['exe']:guard_result.setdefault('owned_exec_changes',[]).append({'before':before,'current':now})
                signal.pidfd_send_signal(pin['fd'],signal.SIGSTOP);pin['stopped']=True
            except (FileNotFoundError,ProcessLookupError):continue
    v=os.statvfs('/dev/shm')
    guard_result.update(cause=cause,seconds=time.monotonic()-started,browser_pid=int(browser_pid) if browser_pid else None,free_bytes_after_freeze=v.f_bavail*v.f_frsize)

def watch():
    try:
        while not finish_guard.wait(.02):
            v=os.statvfs('/dev/shm')
            cause=guard_result.get('requested_cause') or ('shared_memory_reserve' if v.f_bavail*v.f_frsize<384*1024**2 else None)
            with pin_lock:bp=pins.get(browser_pid)
            if bp:
                poll=select.poll();poll.register(bp['fd'],select.POLLIN)
                if poll.poll(0):cause='first_browser_exit'
            if cause:
                freeze_pinned(cause);guard_tripped.set();return
    except BaseException as e:
        guard_result.update(failure_class=type(e).__name__,message=str(e))
        try:freeze_pinned('guard_failure')
        finally:guard_tripped.set()
deadline=time.monotonic()+90
while True:
    try:original=json.loads((out/'games-guardian-summary.json').read_text());break
    except (FileNotFoundError,json.JSONDecodeError):
        assert time.monotonic()<deadline,'prior URI guardian must finish first'
        time.sleep(.5)
assert original['guard']['cause']=='uri_guardian_operator_budget'
ps=processes();pin_seen(ps)
assert roles(ps)[:2]==(['876'],['933']) and {'876','933'}<=set(pins)
for pid,pin in pins.items():
    now=identity(pid);before=pin['identity']
    assert all(now[k]==before[k] for k in ('pid','starttime','uid','exe')) and now['state']=='T' and now['tracer']==0
    states=[read(t/'stat').rsplit(') ',1)[1].split()[0] for t in (Path('/proc')/pid/'task').iterdir()]
    assert states and all(x=='T' for x in states),'incomplete group freeze'
started=time.monotonic();guard_thread=threading.Thread(target=watch,daemon=True);guard_thread.start()
child=None;uri_fd=None
try:
    for pid,pin in pins.items():
        now=identity(pid);before=pin['identity']
        assert all(now[k]==before[k] for k in ('pid','starttime','uid','exe')) and now['tracer']==0
        signal.pidfd_send_signal(pin['fd'],signal.SIGCONT)
    env=['PATH=/usr/local/bin:/usr/bin:/bin','HOME=/home/ideck','USER=ideck','LOGNAME=ideck','LANG=C.UTF-8','DISPLAY=:0','XAUTHORITY=/run/user/1000/Xauthority','XDG_RUNTIME_DIR=/run/user/1000','STEAM_RUNTIME=1','LD_LIBRARY_PATH='+str(root/'steamrtarm64')+':'+str(root/'steamrtarm64/panorama')]
    argv=['nsenter','--mount=/proc/876/ns/mnt','--root=/proc/876/root','--wd='+str(root),'/usr/bin/setpriv','--reuid=1000','--regid=1000','--init-groups','/usr/bin/env','-i',*env,str(root/'steamrtarm64/steam'),'steam://open/bigpicture']
    with (out/'bp-dispatch.log').open('xb') as f:
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
            (out/'bp-result.json').write_text(json.dumps({'uri':'steam://open/bigpicture','exit':child.returncode,'dispatcher_pid':child.pid,'existing_client_pid':876,'no_game_request':True,'time_ns':time.time_ns()},indent=2)+'\n');dispatch_done=True
        v=os.statvfs('/dev/shm')
        with (out/'bp-timeline.jsonl').open('a') as f:f.write(json.dumps({'seconds':time.monotonic()-started,'shm_free':v.f_bavail*v.f_frsize,'processes':ps})+'\n')
        if (out/'finish-bp-guardian').exists():break
        time.sleep(1)
finally:
    finish_guard.set();guard_thread.join(10)
    if not guard_tripped.is_set():freeze_pinned('uri_guardian_operator_budget')
    (out/'bp-guardian-summary.json').write_text(json.dumps({'seconds':time.monotonic()-started,'guard':guard_result,'existing_client_resumed':True,'same_steam_runtime_configuration':True},indent=2)+'\n')
    if uri_fd is not None:os.close(uri_fd)
    for pin in pins.values():os.close(pin['fd'])

URI_GUARD
setsid python3 /run/ideck/bp-guardian16.py </dev/null >/run/ideck/bp-guardian16.log 2>&1 &
printf 'URI_GUARDIAN_PID=%s\n' "$!"
