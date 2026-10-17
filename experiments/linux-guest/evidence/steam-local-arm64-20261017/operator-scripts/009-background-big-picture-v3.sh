set -eu
cat > /run/ideck/local-guarded-v3.py <<'IDECKPY'
import os, time, json, subprocess, signal, hashlib, threading, select
# Only lsof/dependencies differ from the prior baseline; preserve resource profile.
# Keep 384 MiB SHM reserve to observe the first failure without exhaustion.
from pathlib import Path

out = Path('/home/ideck/steam-experiment-logs/resume-local-20261017-big-picture-v3')
out.mkdir(exist_ok=False)
root = Path('/home/ideck/.local/share/Steam')
logs = root/'logs'
positions = {p.name:p.stat().st_size for p in logs.glob('*.txt')}
assert hashlib.sha256(Path('/usr/local/bin/ideck-steam').read_bytes()).hexdigest() == '11cc1c70d2960a745b0f2c31a989eedc3ed23a1f6a95d5be7e6094cd25a7f790'
assert hashlib.sha256(Path('/opt/ideck-steam/namespace-check.py').read_bytes()).hexdigest() == '96c929eafefb2f76aa7751fb1869baa6def54e5e31be2a0e6620a486bca64b0d'
assert os.statvfs('/').f_bavail * os.statvfs('/').f_frsize > 3*1024**3
def read(path):
    try: return Path(path).read_text(errors='replace')
    except OSError as e: return 'UNAVAILABLE:'+str(e.errno)
def link(path):
    try: return os.readlink(path)
    except OSError: return None
def fd_links(path):
    try: return {f.name:link(f) for f in path.iterdir()}
    except OSError: return {}
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
def shm():
    v=os.statvfs('/dev/shm'); rows=[]; deleted={}
    for p in Path('/dev/shm').iterdir():
        try:
            s=p.stat(); rows.append({'name':p.name,'inode':s.st_ino,'uid':s.st_uid,'mode':oct(s.st_mode&0o7777),'size':s.st_size,'allocated':s.st_blocks*512})
        except OSError: pass
    for p in Path('/proc').iterdir():
        if not p.name.isdigit(): continue
        try:
            for fd in (p/'fd').iterdir():
                target=link(fd)
                if target and ('/dev/shm/' in target or target.startswith('/memfd:')):
                    s=fd.stat(); key=f'{s.st_dev}:{s.st_ino}'
                    row=deleted.setdefault(key,{'target':target,'size':s.st_size,'allocated':s.st_blocks*512,'fds':[]})
                    row['fds'].append(f'{p.name}/{fd.name}')
        except OSError: pass
    return {'size':v.f_blocks*v.f_frsize,'used':(v.f_blocks-v.f_bfree)*v.f_frsize,'free':v.f_bavail*v.f_frsize,'inodes_free':v.f_ffree,'objects':rows,'open_objects':deleted}
started=time.monotonic(); frozen=[]; reason='deadline'; last_windows=0; candidate=None
assert subprocess.check_output(['dpkg-query','-W','-f=${Version}','lsof'],text=True)=='4.99.4+dfsg-2'
def emit(kind, **data):
    row={'seconds':round(time.monotonic()-started,3),'wall_ns':time.time_ns(),'kind':kind,**data}
    with (out/'timeline.jsonl').open('a') as f: f.write(json.dumps(row)+'\n')
emit('preflight',memory=read('/proc/meminfo'),mounts=read('/proc/self/mountinfo'),shm=shm(),processes=processes())
assert not processes(), 'unexpected preexisting Steam processes'
with (out/'launcher.log').open('wb') as f:
    launcher=subprocess.Popen(['python3','/opt/ideck-steam/namespace-check.py','launch','big-picture'],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
emit('launch',pid=launcher.pid)
# A separate cheap watcher must run independently of expensive /proc/SHM walks.
# The prior 128 MiB sampled guard overshot; this is diagnostic instrumentation,
# not a change to Steam's memory, CPU or timeout configuration.
finish_guard=threading.Event();guard_tripped=threading.Event()
pin_lock=threading.Lock();pins={};browser_pid=None;guard_result={}
def identity(pid):
    p=Path('/proc')/str(pid)
    fields=(p/'stat').read_text().rsplit(') ',1)[1].split()
    status=dict(x.split(':',1) for x in (p/'status').read_text().splitlines() if ':' in x)
    return {'pid':int(pid),'starttime':fields[19],'exe':os.readlink(p/'exe'),
            'uid':status['Uid'].split(),'state':fields[0],'tracer':int(status['TracerPid']),'ppid':int(status['PPid'])}
def roles(ps):
    native=[];browsers=[];tracers=set()
    for pid,row in ps.items():
        if row.get('TracerPid','0').isdigit() and int(row.get('TracerPid','0'))>0:tracers.add(str(int(row['TracerPid'])))
        if row.get('Uid','').split()!=['1000']*4:continue
        parent=ps.get(str(row.get('PPid','')), {})
        if row.get('exe')==str(root/'steamrtarm64/steam') and parent.get('exe')!=str(root/'steamrtarm64/steam'):
            native.append(str(pid))
    for pid,row in ps.items():
        if row.get('Uid','').split()==['1000']*4 and row.get('exe')==str(root/'steamrtarm64/steamwebhelper') and str(row.get('PPid','')) in native and '--type=' not in row.get('cmdline',''):
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
guard_thread=threading.Thread(target=watch,daemon=True);guard_thread.start()
previous={}; last_full=0; dbus_checked=False
while time.monotonic()-started < 360:
    if guard_tripped.is_set():reason=guard_result.get('cause','guard_failure');break
    ps=processes();pin_seen(ps);memory=read('/proc/meminfo');shared=shm()
    if guard_tripped.is_set():reason=guard_result.get('cause','guard_failure');break
    if time.monotonic()-last_windows > 15:
        subprocess.run(['xdotool','mousemove','400','300'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=5)
        w=subprocess.run(['xwininfo','-root','-tree'],capture_output=True,text=True,timeout=5)
        emit('windows',exit_code=w.returncode,text=w.stdout,stderr=w.stderr)
        last_windows=time.monotonic()
        if any('--type=renderer' in p['cmdline'] for p in ps.values()) and any(('\"Steam\"' in line or 'Sign in to Steam' in line) for line in w.stdout.splitlines()):
            candidate=candidate or time.monotonic()
            if time.monotonic()-candidate>15:
                reason='ui_candidate_requires_screenshot_review'; break
    emit('sample',memory=memory,processes=ps,shm=shared,launcher_exit=launcher.poll())
    if not dbus_checked:
        native=next((pid for pid,row in ps.items() if row.get('exe')==str(root/'steamrtarm64/steam')),None)
        if native:
            selected=[v.split(b'=',1)[1].decode() for v in (Path('/proc')/native/'environ').read_bytes().split(b'\0') if v.startswith(b'DBUS_SESSION_BUS_ADDRESS=')]
            if len(selected)==1:
                bus=subprocess.run(['setpriv','--reuid=1000','--regid=1000','--init-groups','env','DBUS_SESSION_BUS_ADDRESS='+selected[0],'dbus-send','--session','--type=method_call','--print-reply','--dest=org.freedesktop.DBus','/org/freedesktop/DBus','org.freedesktop.DBus.ListNames'],capture_output=True,timeout=8)
                emit('native_dbus',pid=native,exit_code=bus.returncode,reply_bytes=len(bus.stdout),stderr=bus.stderr.decode(errors='replace'))
            else:emit('native_dbus',pid=native,failure='session_address_absent_or_ambiguous')
            dbus_checked=True
    new_log=''
    for p in logs.glob('*.txt'):
        try: size=p.stat().st_size
        except OSError: continue
        start=positions.get(p.name,0)
        if size<start: start=0
        if size>start:
            with p.open('rb') as f: f.seek(start); b=f.read(262144)
            with (out/('delta-'+p.name)).open('ab') as f: f.write(b)
            text=b.decode(errors='replace'); emit('log',file=p.name,text=text)
            if p.name=='steamui_html.txt': new_log+=text
            positions[p.name]=start+len(b)
    for pid,row in ps.items():
        if pid not in previous:
            p=Path('/proc')/pid
            emit('process_birth',pid=pid,row=row,maps=read(p/'maps'),fds=fd_links(p/'fd'))
    for pid,row in previous.items():
        if pid not in ps: emit('process_disappeared',pid=pid,last=row,exit_status='not a direct child; unavailable without tracing')
    previous=ps
    if 'Timed out waiting for webhelper init' in new_log or 'Restart webhelper process' in new_log or shared['free']<384*1024**2:
        reason='first_timeout_or_restart' if shared['free']>=384*1024**2 else 'shared_memory_reserve'
        break
    time.sleep(2)
finish_guard.set();guard_thread.join(10)
if guard_thread.is_alive():raise RuntimeError('guard thread did not finish')
if reason!='ui_candidate_requires_screenshot_review' and not guard_tripped.is_set():freeze_pinned(reason)
frozen=[];freeze_identities=[]
for pid,pin in pins.items():
    if pin['stopped']:
        try:
            now=identity(pid)
            group_states=[read(t/'stat').rsplit(') ',1)[1].split()[0] for t in (Path('/proc')/pid/'task').iterdir()]
            if any(s!='T' for s in group_states):raise RuntimeError('group freeze incomplete')
            frozen.append(int(pid));freeze_identities.append({k:now[k] for k in ('pid','starttime','exe')})
        except (FileNotFoundError,ProcessLookupError):pass
    os.close(pin['fd'])
(out/'freeze-identities.json').write_text(json.dumps(freeze_identities,indent=2)+'\n')
(out/'fast-guard.json').write_text(json.dumps(guard_result,indent=2)+'\n')
emit('diagnostic_freeze',reason=reason,pids=frozen,shm=shm(),memory=read('/proc/meminfo'))
(out/'summary.json').write_text(json.dumps({'reason':reason,'seconds':time.monotonic()-started,'frozen':frozen,'launcher_pid':launcher.pid,'path':str(out)},indent=2)+'\n')
subprocess.run(['xdotool','mousemove','410','300'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=5)
print((out/'summary.json').read_text(),flush=True)
for name in ('delta-steamui_html.txt','delta-cef_log.txt','launcher.log'):
    p=out/name
    if p.exists():
        print('IDECK_FIRST_LOG='+name)
        print('\n'.join(p.read_text(errors='replace').splitlines()[-55:]))

IDECKPY
setsid python3 /run/ideck/local-guarded-v3.py </dev/null >/run/ideck/local-guarded-v3.log 2>&1 &
printf 'IDECK_MONITOR_PID=%s\n' "$!"
