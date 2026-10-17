import ast,hashlib,json,os,signal,subprocess,threading,time
from pathlib import Path
base=Path(__file__).resolve().parent;source=(base/'010-background-big-picture-narrow-v4.sh').read_text();code=source.split("<<'IDECKPY'\n",1)[1].split('\nIDECKPY',1)[0]
functions=ast.Module(body=[n for n in ast.parse(code).body if isinstance(n,ast.FunctionDef) and n.name in ('identity','pin_seen','freeze_pinned','roles')],type_ignores=[])
children=[subprocess.Popen(['/usr/bin/sleep','30'],user=1000,group=1000,extra_groups=[],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL) for _ in range(3)]
pins=[]
try:
    ctx=dict(Path=Path,os=os,signal=signal,threading=threading,time=time,root=Path('/fixture'),pins={},pin_lock=threading.Lock(),browser_pid=None,guard_result={},started=time.monotonic())
    exec(compile(functions,'actual-v3-protection-functions','exec'),ctx)
    for child in children:
        i=ctx['identity'](child.pid);fd=os.pidfd_open(child.pid);pins.append(fd);ctx['pins'][str(child.pid)]={'fd':fd,'identity':i,'stopped':False}
    real=ctx['identity']
    def fixture_identity(pid):
        i=real(pid)
        if int(pid)==children[0].pid:i['tracer']=children[1].pid
        return i
    def rows():
        return {str(c.pid):{'exe':real(c.pid)['exe'],'Uid':'1000 1000 1000 1000','PPid':str(os.getpid()),'TracerPid':str(children[1].pid) if c is children[0] else '0','cmdline':'own fixture sleep','stat':Path('/proc',str(c.pid),'stat').read_text()} for c in children}
    ctx['identity']=fixture_identity;ctx['processes']=rows
    ctx['freeze_pinned']('fixture_resource_guard');time.sleep(.02)
    states=[real(c.pid)['state'] for c in children]
    assert states[0]!='T' and states[1]!='T' and states[2]=='T',states
    receipt={'status':'pass','source_sha256':hashlib.sha256(source.encode()).hexdigest(),'kind':'actual functions with own harmless UID1000 children; tracer relation injected only in fixtures','traced_target_not_signaled':True,'active_dumper_not_signaled':True,'ordinary_owned_process_stopped':True,'states':states}
    (base/'fast-guard-v4-protection-tests.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
finally:
    for fd in pins:
        try:signal.pidfd_send_signal(fd,signal.SIGCONT)
        except ProcessLookupError:pass
        os.close(fd)
    for c in children:c.terminate();c.wait(timeout=5)