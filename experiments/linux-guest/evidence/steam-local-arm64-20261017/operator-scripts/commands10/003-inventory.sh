set -eu
cat > /run/ideck/snapshot-ipc-stack.py <<'SNAPSHOT_SOURCE'
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
    return {'tid':tid, 'tgid':int(status['Tgid']), 'starttime':int(fields[19]),
            'uid':[int(x) for x in status['Uid'].split()], 'tracer':int(status['TracerPid']),
            'state':status['State'].strip()[0], 'exe':os.readlink(p/'exe')}


def validate(info, tgid, exe):
    if info['tid'] <= 1 or info['tgid'] != tgid or info['exe'] != exe or info['uid'] != [1000]*4:
        raise Refusal('unexpected_process')
    if info['tracer']:
        raise Refusal('already_traced')
    if info['state'] in ('Z','X','x','t'):
        raise Refusal('unavailable_process')


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
        if ('-steampid='+str(args.main_pid)).encode() not in argv or any(x.startswith(b'--type=') for x in argv):
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
set -eu
export PYTHONDONTWRITEBYTECODE=1
python3 - <<'PY'
from pathlib import Path
import hashlib,json,os,stat,struct,subprocess,time
out=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-first-attempt')
summary=json.loads((out/'summary.json').read_text())
rows=[]
for p in Path('/proc').iterdir():
    if not p.name.isdecimal():continue
    try:
        exe=os.readlink(p/'exe')
        if exe not in ('/home/ideck/.local/share/Steam/steamrtarm64/steam','/home/ideck/.local/share/Steam/steamrtarm64/steamwebhelper'):continue
        row={'pid':int(p.name),'exe':exe,'argv':(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace'),'status':(p/'status').read_text(),'maps':(p/'maps').read_text(),'fds':{},'threads':[]}
        for fd in (p/'fd').iterdir():
            try:row['fds'][fd.name]=os.readlink(fd)
            except FileNotFoundError:pass
        for t in (p/'task').iterdir():
            try:row['threads'].append({'tid':int(t.name),'comm':(t/'comm').read_text().strip(),'stat':(t/'stat').read_text(),'wchan':(t/'wchan').read_text().strip(),'syscall':(t/'syscall').read_text().strip()})
            except FileNotFoundError:pass
        rows.append(row)
    except FileNotFoundError:pass
modules={}
for name in ('steam','steamwebhelper','steamclient.so','chromehtml.so','steamui.so','libcef.so'):
    path=Path('/home/ideck/.local/share/Steam/steamrtarm64')/name
    before=path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_uid!=1000 or before.st_size>512*1024**2:raise RuntimeError('unexpected diagnostic ELF')
    with path.open('rb') as f:
        checksum=hashlib.file_digest(f,'sha256').hexdigest();f.seek(0);header=f.read(64)
        if header[:6]!=b'\x7fELF\x02\x01' or struct.unpack_from('<H',header,18)[0]!=183:raise RuntimeError('wrong ELF ABI')
        offset=struct.unpack_from('<Q',header,32)[0];size,count=struct.unpack_from('<HH',header,54)
        if size!=56 or count>128:raise RuntimeError('ELF header bound')
        f.seek(offset);raw=f.read(size*count)
    segments=[]
    for n in range(count):
        kind,flags,off,va,pa,filesz,memsz,align=struct.unpack_from('<IIQQQQQQ',raw,n*size)
        if kind==1:segments.append({'offset':off,'vaddr':va,'filesz':filesz,'memsz':memsz,'flags':flags,'align':align})
    after=path.lstat()
    if (before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns):raise RuntimeError('ELF changed during inventory')
    modules[name]={'sha256':checksum,'size':before.st_size,'uid':before.st_uid,'pt_load':segments}
(out/'module-identities.json').write_text(json.dumps(modules,indent=2)+'\n')
print('IDECK_MODULES='+json.dumps(modules),flush=True)
result={'time_ns':time.time_ns(),'summary':summary,'processes':rows,'network':{n:Path('/proc/net',n).read_text() for n in ('tcp','tcp6','unix')}}
(out/'thread-inventory.json').write_text(json.dumps(result,indent=2)+'\n')
print('IDECK_INVENTORY='+json.dumps({**result,'processes':[{k:v for k,v in r.items() if k not in ('maps','fds')} for r in rows]}),flush=True)
for argv in (['xset','q'],['xwininfo','-root','-tree']):
    r=subprocess.run(argv,capture_output=True,text=True,timeout=10);print('IDECK_DISPLAY_QUERY='+json.dumps({'command':argv,'exit':r.returncode,'stdout':r.stdout,'stderr':r.stderr}))
PY