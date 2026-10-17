set -eu
export PYTHONDONTWRITEBYTECODE=1
cat > /run/ideck/snapshot-ipc-parent.py <<'SNAPSHOT_SOURCE'
#!/usr/bin/env python3
"""One bounded address-only AArch64 frame-pointer snapshot. No register writes."""
import argparse, ctypes, errno, json, os, platform, signal, struct, time
from pathlib import Path

ROOT = '/home/ideck/.local/share/Steam/steamrtarm64/'
SEIZE, INTERRUPT, GETREGSET, DETACH = 0x4206, 0x4207, 0x4204, 17
EVENT_STOP, WALL, TRACEEXEC = 128, 0x40000000, 0x10
STOP_SIGNALS = {signal.SIGSTOP, signal.SIGTSTP, signal.SIGTTIN, signal.SIGTTOU}


class Refusal(Exception):
    pass


def proc_info(tid):
    p = Path('/proc') / str(tid)
    fields = (p/'stat').read_text().rsplit(') ', 1)[1].split()
    status = dict(x.split(':', 1) for x in (p/'status').read_text().splitlines() if ':' in x)
    return {'tid':tid, 'tgid':int(status['Tgid']), 'ppid':int(status['PPid']), 'starttime':int(fields[19]),
            'uid':[int(x) for x in status['Uid'].split()], 'tracer':int(status['TracerPid']),
            'state':status['State'].strip()[0], 'exe':os.readlink(p/'exe')}


def validate(info, tgid, exe):
    if info['tid'] <= 1 or info['tgid'] != tgid or info['exe'] != exe or info['uid'] != [1000]*4:
        raise Refusal('unexpected_process')
    if info['tracer']:
        raise Refusal('already_traced')
    if info['state'] in ('Z','X','x','t'):
        raise Refusal('unavailable_process')


def is_browser_argv(info, argv, main_pid):
    # Steam's forked assertion dumper inherits the browser's executable and
    # argv. It is a child of the browser, not the native client's browser.
    return (info.get('ppid') == main_pid and
            ('-steampid='+str(main_pid)).encode() in argv and
            not any(x.startswith(b'--type=') for x in argv))


def parse_maps(text):
    out=[]
    for line in text.splitlines():
        f=line.split(None,5)
        lo,hi=(int(x,16) for x in f[0].split('-'))
        out.append({'lo':lo,'hi':hi,'perm':f[1],'offset':int(f[2],16),
                    'module':f[5] if len(f)>5 else '[anonymous]'})
    return out


def map_for(maps, address, size=1):
    return next((m for m in maps if m['lo'] <= address and address+size <= m['hi']),None)


def address_info(address, maps):
    m=map_for(maps,address)
    result={'address':hex(address)}
    if m:
        # File offset is exact; ELF module VA requires the module PT_LOAD mapping.
        result.update(module=m['module'], mapping_offset=hex(address-m['lo']),
                      file_offset=hex(address-m['lo']+m['offset']))
    return result


def walk_frames(fp, sp, maps, read16, max_frames=32):
    if not 1 <= max_frames <= 32:
        raise Refusal('invalid_frame_limit')
    if sp%16:return [],'unaligned_stack'
    stack=map_for(maps,sp)
    if stack is None or 'r' not in stack['perm'] or 'w' not in stack['perm']:
        return [],'stack_not_readable_writable'
    rows=[];previous=sp-16
    for _ in range(max_frames):
        if fp == 0:return rows,'end_zero'
        if fp%16:return rows,'unaligned_frame'
        if fp <= previous or fp < sp:return rows,'nonincreasing_frame'
        if not(stack['lo'] <= fp and fp+16 <= stack['hi']):return rows,'frame_outside_stack'
        try:raw=read16(fp)
        except OSError:return rows,'frame_read_failed'
        if len(raw)!=16:return rows,'short_frame_read'
        next_fp,lr=struct.unpack('<QQ',raw)
        if lr == 0:
            rows.append({'fp':hex(fp),'return':{'address':'0x0'}})
            return rows,'end_zero_return'
        code=map_for(maps,lr-1)
        if code is None or 'x' not in code['perm']:
            # Never strip guessed PAC/tag bits; raw pointer may be signed.
            return rows,'return_not_executable_or_pac'
        rows.append({'fp':hex(fp),'return':address_info(lr,maps)})
        previous,fp=fp,next_fp
    return rows,'frame_limit'


class Iovec(ctypes.Structure):
    _fields_=[('base',ctypes.c_void_p),('length',ctypes.c_size_t)]


class LinuxBackend:
    def __init__(self):
        self.pidfds={}
        self.libc=ctypes.CDLL(None,use_errno=True)
        self.libc.ptrace.restype=ctypes.c_long
        self.libc.ptrace.argtypes=[ctypes.c_uint,ctypes.c_int,ctypes.c_void_p,ctypes.c_void_p]

    def ptrace(self,operation,tid,addr=0,data=0):
        ctypes.set_errno(0)
        if self.libc.ptrace(operation,tid,ctypes.c_void_p(addr),ctypes.c_void_p(data)) == -1:
            code=ctypes.get_errno()
            raise OSError(code,'ptrace_failed')

    def wait(self,tid,seconds):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            try:pid,status=os.waitpid(tid,os.WNOHANG|WALL)
            except ChildProcessError:raise Refusal('tracee_no_longer_child') from None
            if pid:
                if not os.WIFSTOPPED(status):raise Refusal('tracee_exited')
                return status
            time.sleep(.002)
        raise Refusal('ptrace_stop_timeout')

    def registers(self,tid):
        regs=(ctypes.c_uint64*34)()
        iov=Iovec(ctypes.cast(regs,ctypes.c_void_p),ctypes.sizeof(regs))
        self.ptrace(GETREGSET,tid,1,ctypes.addressof(iov))
        if iov.length!=272:raise Refusal('unexpected_prstatus_size')
        # Other register values are intentionally neither returned nor logged.
        return {'pc':int(regs[32]),'sp':int(regs[31]),'fp':int(regs[29]),'lr':int(regs[30])}

    def pin_group(self,tgid):
        self.pidfds[tgid]=os.pidfd_open(tgid,0)
    def stop_group(self,tgid):
        # A pidfd cannot accidentally signal a recycled process ID.
        signal.pidfd_send_signal(self.pidfds[tgid],signal.SIGSTOP)
    def close_group(self,tgid):
        fd=self.pidfds.pop(tgid,None)
        if fd is not None:os.close(fd)
    def info(self,tid):return proc_info(tid)


def same_identity(current,initial):
    return all(current.get(k)==initial.get(k) for k in ('tid','tgid','starttime','uid','exe'))


def capture_thread(initial, backend, snapshot, stop_timeout=.75):
    tid=initial['tid'];prior_stop=initial['state']=='T'
    report={'tid':tid,'tgid':initial['tgid'],'prior_group_stopped':prior_stop,
            'status':'failed','detached':False,'group_stop_restored':None}
    attached=False;stopped=False;stop_status=None;pinned=False
    try:
        current=backend.info(tid)
        if not same_identity(current,initial):raise Refusal('identity_changed')
        if (current['state']=='T')!=prior_stop:raise Refusal('group_state_changed')
        backend.pin_group(initial['tgid']);pinned=True
        if not same_identity(backend.info(tid),initial):raise Refusal('identity_changed')
        backend.ptrace(SEIZE,tid,0,TRACEEXEC);attached=True
        backend.ptrace(INTERRUPT,tid)
        stop_status=backend.wait(tid,stop_timeout);stopped=True
        event=stop_status>>16;sig=os.WSTOPSIG(stop_status)
        report['stop_event']=event;report['stop_signal']=sig
        if event!=EVENT_STOP or sig not in ({signal.SIGTRAP}|STOP_SIGNALS):
            raise Refusal('unexpected_signal_stop')
        if sig in STOP_SIGNALS:prior_stop=True
        current=backend.info(tid)
        if not same_identity(current,initial):raise Refusal('identity_changed_while_stopped')
        report['snapshot']=snapshot(tid)
        report['status']='captured'
    except Exception as exc:
        report['failure_class']=type(exc).__name__
        report['reason']=exc.args[0] if isinstance(exc,Refusal) else 'capture_failed'
        if isinstance(exc,OSError):report['errno']=exc.errno
    finally:
        if attached:
            try:
                if not stopped:
                    backend.ptrace(INTERRUPT,tid)
                    stop_status=backend.wait(tid,stop_timeout);stopped=True
                current=backend.info(tid)
                if not same_identity(current,initial):raise Refusal('identity_changed_before_detach')
                if prior_stop:
                    # Explicit OS signal: DETACH(sig) alone can silently ignore it.
                    backend.stop_group(initial['tgid'])
                sig=os.WSTOPSIG(stop_status) if (stop_status is not None and stop_status>>16==0) else 0
                backend.ptrace(DETACH,tid,0,sig)
                report['detached']=True
            except Exception as exc:
                report['cleanup_failure_class']=type(exc).__name__
                if isinstance(exc,OSError):report['cleanup_errno']=exc.errno
                report['status']='cleanup_failed'
        if report['detached']:
            try:
                current=backend.info(tid)
                if not same_identity(current,initial):raise Refusal('identity_changed_after_detach')
                report['tracer_after']=current['tracer']
                if prior_stop and current['state']!='T':
                    backend.stop_group(initial['tgid'])
                    deadline=time.monotonic()+stop_timeout
                    while current['state']!='T' and time.monotonic()<deadline:
                        time.sleep(.002);current=backend.info(tid)
                        if not same_identity(current,initial):raise Refusal('identity_changed_restore')
                report['state_after']=current['state']
                report['group_stop_restored']=current['state']=='T' if prior_stop else None
                if current['tracer'] or (prior_stop and current['state']!='T'):
                    report['status']='restore_failed'
            except FileNotFoundError:
                report['state_after']='exited'
                report['group_stop_restored']=None
            except Exception as exc:
                report['status']='restore_failed';report['restore_failure_class']=type(exc).__name__
        if pinned:backend.close_group(initial['tgid'])
    return report


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--main-pid',type=int,required=True)
    ap.add_argument('--browser-pid',type=int,required=True)
    ap.add_argument('--tid',action='append',type=int,required=True)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    if len(args.tid)>4 or len(set(args.tid))!=len(args.tid) or any(x<=1 for x in args.tid):
        ap.error('select1..4uniqueuserspacetids')
    if platform.machine() not in ('aarch64','arm64') or os.name!='posix' or os.geteuid()!=0:
        raise Refusal('requires_root_in_aarch64_linux_guest')
    # Existing outputs are never overwritten; no attachment precedes this gate.
    fd=os.open(args.output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    report={'schema':1,'kind':'address_only_ptrace_snapshot','started_ns':time.time_ns(),
            'target_register_writes':False,'memory_writes':False,'follows_children':False,
            'status':'failed','threads':[]}
    interrupted=[False];old={}
    try:
        main=proc_info(args.main_pid);browser=proc_info(args.browser_pid)
        validate(main,args.main_pid,ROOT+'steam')
        validate(browser,args.browser_pid,ROOT+'steamwebhelper')
        # Read argv to identify the browser; never output it or environment.
        argv=(Path('/proc')/str(args.browser_pid)/'cmdline').read_bytes().split(b'\0')
        if not is_browser_argv(browser, argv, args.main_pid):
            raise Refusal('unexpected_browser')
        selected=[]
        for tid in args.tid:
            info=proc_info(tid)
            if info['tgid'] not in (args.main_pid,args.browser_pid):raise Refusal('unrelated_tid')
            validate(info,info['tgid'],ROOT+('steam' if info['tgid']==args.main_pid else 'steamwebhelper'))
            group_states=[proc_info(int(x.name))['state'] for x in (Path('/proc')/str(info['tgid'])/'task').iterdir()]
            if 'T' in group_states and any(x!='T' for x in group_states):raise Refusal('mixed_group_stop')
            selected.append(info)
        backend=LinuxBackend()
        def snapshot(tid):
            regs=backend.registers(tid)
            maps=parse_maps((Path('/proc')/str(tid)/'maps').read_text())
            memory=os.open('/proc/'+str(tid)+'/mem',os.O_RDONLY|os.O_CLOEXEC)
            try:frames,reason=walk_frames(regs['fp'],regs['sp'],maps,lambda address:os.pread(memory,16,address))
            finally:os.close(memory)
            return {'registers':{name:address_info(value,maps) for name,value in regs.items()},
                    'frames':frames,'unwind_stop':reason}
        for sig in (signal.SIGINT,signal.SIGTERM):old[sig]=signal.signal(sig,lambda *_:interrupted.__setitem__(0,True))
        began=time.monotonic()
        for initial in selected:
            if interrupted[0] or time.monotonic()-began>8:raise Refusal('snapshot_budget_or_interrupt')
            result=capture_thread(initial,backend,snapshot)
            report['threads'].append(result)
            if not result['detached'] or result['status'] in ('cleanup_failed','restore_failed'):break
        report['status']='captured' if len(report['threads'])==len(selected) and all(t['status']=='captured' for t in report['threads']) else 'incomplete'
    except Exception as exc:
        report['failure_class']=type(exc).__name__
        report['reason']=exc.args[0] if isinstance(exc,Refusal) else 'snapshot_failed'
        if isinstance(exc,OSError):report['errno']=exc.errno
    finally:
        for sig,handler in old.items():signal.signal(sig,handler)
        report['finished_ns']=time.time_ns()
        with os.fdopen(fd,'w') as f:json.dump(report,f,indent=2);f.write('\n')
    print(json.dumps({'status':report['status'],'threads':len(report['threads'])}))
    return 0 if report['status']=='captured' else 1

if __name__=='__main__':
    raise SystemExit(main())

SNAPSHOT_SOURCE
cat > /run/ideck/trace-ipc-parent.py <<'TRACE_SOURCE'
#!/usr/bin/env python3
"""Bounded guest-only IPC syscall trace. Never launch/stop a guest or Steam."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import time

SYSCALLS = ('futex', 'openat', 'ftruncate', 'mmap', 'munmap', 'close', 'unlink',
            'unlinkat', 'connect', 'clone', 'clone3', 'exit', 'exit_group')
ROOT = Path('/home/ideck/.local/share/Steam')
DEFAULT_STRACE = '/opt/ideck-diagnostic-strace/usr/bin/strace'


def proc_info(pid, proc=Path('/proc')):
    base = proc / str(pid)
    raw = (base / 'stat').read_text()
    fields = raw[raw.rfind(')') + 2:].split()
    status = dict(line.split(':', 1) for line in (base / 'status').read_text().splitlines() if ':' in line)
    argv = [x.decode('utf-8', 'replace') for x in (base / 'cmdline').read_bytes().split(b'\0') if x]
    return {'pid': pid, 'starttime': fields[19], 'ppid': int(fields[1]),
            'exe': os.readlink(base / 'exe'), 'argv': argv,
            'uid': [int(x) for x in status['Uid'].split()],
            'tracer_pid': int(status.get('TracerPid', '0')),
            'state': status.get('State', '').strip(),
            'seccomp': int(status.get('Seccomp', '-1'))}


def is_browser(info, main_pid):
    return (info['exe'] == str(ROOT / 'steamrtarm64/steamwebhelper') and
            info['uid'] == [1000] * 4 and
            info.get('ppid') == main_pid and
            f'-steampid={main_pid}' in info['argv'] and
            not any(x.startswith('--type=') for x in info['argv']))


def validate_main(info):
    if info['exe'] != str(ROOT / 'steamrtarm64/steam') or info['uid'] != [1000] * 4:
        raise RuntimeError('unexpected_native_process')
    if '-cef-force-sandbox' not in info['argv']:
        raise RuntimeError('force_sandbox_missing_native')
    deny = {'-no-cef-sandbox', '-cef-disable-sandbox', '--no-sandbox'}
    if deny.intersection(info['argv']):
        raise RuntimeError('sandbox_disable_argument')


def find_browser(main_pid, proc=Path('/proc')):
    found = []
    for path in proc.iterdir():
        if not path.name.isdecimal():
            continue
        try:
            info = proc_info(int(path.name), proc)
        except (OSError, KeyError, ValueError):
            continue
        if is_browser(info, main_pid):
            found.append(info)
    if len(found) > 1:
        raise RuntimeError('multiple_browser_processes')
    return found[0] if found else None


def trace_command(strace, tids):
    argv = [strace, '-qq', '-ttt', '-T', '-i', '-s', '128',
            '-e', 'signal=none', '-e', 'trace=' + ','.join(SYSCALLS)]
    # Explicit existing TIDs: no -f, no ptrace of future sandboxed children.
    for tid in sorted(set(tids)):
        argv.extend(['-p', str(tid)])
    return argv


def snapshot(pid, dest, phase):
    info = proc_info(pid)
    safe = {k: v for k, v in info.items() if k != 'argv'}
    safe['force_sandbox_arg'] = any(x in info['argv'] for x in ('-cef-force-sandbox', '-force-sandbox', '--force-sandbox'))
    safe['cwd'] = os.readlink(f'/proc/{pid}/cwd')
    marker = Path(f'/proc/{pid}/cwd/.cef-initialize-sentinel')
    try:
        st = marker.lstat()
        safe['sentinel'] = {'exists': True, 'size': st.st_size, 'uid': st.st_uid, 'mode': st.st_mode, 'mtime_ns': st.st_mtime_ns}
    except FileNotFoundError:
        safe['sentinel'] = {'exists': False}
    (dest / f'{phase}-{pid}.maps').write_bytes(Path(f'/proc/{pid}/maps').read_bytes())
    return safe


def detach(tracer):
    # Drain the bounded pipe while waiting: strace can otherwise block while
    # printing its detach messages after the byte budget has been reached.
    os.set_blocking(tracer.stderr.fileno(), False)
    for sig in (signal.SIGINT, signal.SIGTERM):
        if tracer.poll() is not None:
            return True
        try:
            tracer.send_signal(sig)
        except ProcessLookupError:
            return True
        deadline = time.monotonic() + 5
        while tracer.poll() is None and time.monotonic() < deadline:
            try:
                os.read(tracer.stderr.fileno(), 65536)
            except BlockingIOError:
                pass
            time.sleep(0.01)
    return tracer.poll() is not None


def collect(tracer, sink, seconds, byte_cap, interrupted, reserve=64 * 1024 * 1024):
    started = time.monotonic()
    stored = 0
    reason = 'duration_limit'
    selector = selectors.DefaultSelector()
    selector.register(tracer.stderr, selectors.EVENT_READ)
    try:
        while True:
            if interrupted[0]:
                reason = 'interrupted'
                break
            if time.monotonic() - started >= seconds:
                break
            shm = os.statvfs('/dev/shm')
            if shm.f_bavail * shm.f_frsize < reserve:
                reason = 'shared_memory_reserve'
                break
            if stored >= byte_cap:
                reason = 'byte_limit'
                break
            events = selector.select(timeout=0.1)
            for key, _ in events:
                chunk = os.read(key.fd, min(65536, byte_cap - stored))
                if not chunk:
                    reason = 'tracer_exited'
                    return stored, reason, round(time.monotonic() - started, 3)
                sink.write(chunk)
                stored += len(chunk)
            if tracer.poll() is not None and not events:
                reason = 'tracer_exited'
                break
        return stored, reason, round(time.monotonic() - started, 3)
    finally:
        selector.close()
        sink.flush()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--main-pid', type=int, required=True)
    ap.add_argument('--browser-pid', type=int)
    ap.add_argument('--wait-browser', type=float, default=45)
    ap.add_argument('--seconds', type=float, default=25)
    ap.add_argument('--max-bytes', type=int, default=8 * 1024 * 1024)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--strace', default=DEFAULT_STRACE)
    args = ap.parse_args()
    if not (0 < args.seconds <= 30 and 0 <= args.wait_browser <= 60 and
            1024 <= args.max_bytes <= 16 * 1024 * 1024 and args.main_pid > 1):
        ap.error('bounds: seconds<=30, wait-browser<=60, max-bytes1024..16MiB, main-pid>1')
    args.output.mkdir(parents=False, exist_ok=False)
    result = {'schema': 1, 'kind': 'separate_instrumented_probe', 'status': 'failed',
              'baseline_timing': False, 'capture': 'existing native/browser TIDs only',
              'read_write_buffers_captured': False, 'new_sandbox_children_traced': False,
              'requested_seconds': args.seconds, 'max_bytes': args.max_bytes,
              'started_wall_ns': time.time_ns(), 'before': [], 'after': []}
    tracer = None
    interrupted = [False]
    old_handlers = {}
    try:
        initial = proc_info(args.main_pid)
        validate_main(initial)
        deadline = time.monotonic() + args.wait_browser
        while True:
            current = proc_info(args.main_pid)
            if current['starttime'] != initial['starttime']:
                raise RuntimeError('native_pid_reused')
            browser = proc_info(args.browser_pid) if args.browser_pid else find_browser(args.main_pid)
            if browser is not None:
                break
            if time.monotonic() >= deadline:
                raise RuntimeError('browser_not_found')
            time.sleep(0.1)
        if not is_browser(browser, args.main_pid):
            raise RuntimeError('unexpected_browser_process')
        if not {'-force-sandbox', '--force-sandbox'}.intersection(browser['argv']):
            raise RuntimeError('force_sandbox_missing_browser')
        if '--no-sandbox' in browser['argv']:
            raise RuntimeError('browser_no_sandbox')
        pids = [args.main_pid, browser['pid']]
        tids = []
        for pid in pids:
            result['before'].append(snapshot(pid, args.output, 'before'))
            for task in Path(f'/proc/{pid}/task').iterdir():
                try:
                    info = proc_info(int(task.name))
                except FileNotFoundError:
                    continue
                if info['tracer_pid']:
                    raise RuntimeError('already_traced')
                tids.append(int(task.name))
        if not tids or len(tids) > 256:
            raise RuntimeError('invalid_thread_count')
        result['tids'] = sorted(tids)
        command = trace_command(args.strace, tids)
        result['command'] = command
        for sig in (signal.SIGINT, signal.SIGTERM):
            old_handlers[sig] = signal.signal(sig, lambda *_: interrupted.__setitem__(0, True))
        tracer = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, start_new_session=True)
        result['tracer_pid'] = tracer.pid
        with (args.output / 'trace.log').open('xb') as sink:
            size, reason, elapsed = collect(tracer, sink, args.seconds, args.max_bytes, interrupted)
        result.update(bytes=size, stop_reason=reason, trace_seconds=elapsed)
        result['tracer_detached'] = detach(tracer)
        result['tracer_exit'] = tracer.poll()
        result['remaining_traced_tids'] = []
        for tid in tids:
            try:
                if proc_info(tid)['tracer_pid'] == tracer.pid:
                    result['remaining_traced_tids'].append(tid)
            except FileNotFoundError:
                pass
        for pid in pids:
            try:
                result['after'].append(snapshot(pid, args.output, 'after'))
            except FileNotFoundError:
                result['after'].append({'pid': pid, 'exited': True})
        result['status'] = ('captured' if result['tracer_detached'] and
                            not result['remaining_traced_tids'] and result['tracer_exit'] == 0
                            and size else 'trace_incomplete')
    except Exception as exc:
        # No command-line/environment content or arbitrary exception string.
        result['failure_class'] = type(exc).__name__
        result['reason'] = exc.args[0] if isinstance(exc, RuntimeError) else 'trace_setup_or_capture_failed'
    finally:
        if tracer is not None and tracer.poll() is None:
            result['tracer_detached'] = detach(tracer)
            result['tracer_exit'] = tracer.poll()
        for sig, handler in old_handlers.items():
            signal.signal(sig, handler)
        for path in args.output.glob('*.maps'):
            result.setdefault('files', {})[path.name] = {'size': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        path = args.output / 'trace.log'
        if path.exists():
            result.setdefault('files', {})[path.name] = {'size': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        result['finished_wall_ns'] = time.time_ns()
        (args.output / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'status': result['status'], 'output': str(args.output),
                      'tracer_detached': result.get('tracer_detached'),
                      'reason': result.get('reason', result.get('stop_reason'))}))
    return 0 if result['status'] == 'captured' else 1


if __name__ == '__main__':
    raise SystemExit(main())

TRACE_SOURCE
python3 /run/ideck/snapshot-ipc-parent.py --main-pid 2192 --browser-pid 2295 --tid 2192 --tid 2296 --tid 2295 --tid 2316 --output /home/ideck/steam-experiment-logs/resume-local-20261017-guarded-v2/address-snapshot-parent.json
python3 - <<'PY'
from pathlib import Path
import hashlib,json,subprocess
out=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-guarded-v2')
result={'tools':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path('/run/ideck/snapshot-ipc-parent.py'),Path('/run/ideck/trace-ipc-parent.py'))}}
p=Path('/opt/ideck-diagnostic-strace/usr/bin/strace')
result['strace_exists']=p.is_file()
if p.is_file():
    result['strace_sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
    r=subprocess.run([str(p),'-V'],capture_output=True,text=True,timeout=5);result['strace_version']=r.stdout;result['strace_version_exit']=r.returncode
(out/'parent-checked-tools.json').write_text(json.dumps(result,indent=2)+'\n')
print('IDECK_PARENT_TOOLS='+json.dumps(result),flush=True)
PY