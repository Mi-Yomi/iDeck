import ast,hashlib,json,os,signal,subprocess,threading,time
from pathlib import Path
from types import SimpleNamespace
b=Path(__file__).resolve().parent;source=(b/'012-background-connect-5000-v6.sh').read_text();code=source.split("<<'IDECKPY'\n",1)[1].split('\nIDECKPY',1)[0];tree=ast.parse(code)
functions=ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('identity','roles','pin_seen','freeze_pinned','display_probe')],type_ignores=[])
child=subprocess.Popen(['/usr/bin/sleep','30'],user=1000,group=1000,extra_groups=[],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);fds=[]
try:
    exe=os.readlink('/proc/'+str(child.pid)+'/exe')
    class FixtureRoot:
        def __truediv__(self,_):return exe
    ctx=dict(Path=Path,os=os,signal=signal,time=time,threading=threading,subprocess=subprocess,root=FixtureRoot(),read=lambda p:p.read_text(),pins={},pin_lock=threading.Lock(),browser_pid=None,guard_result={},started=time.monotonic(),finish_guard=threading.Event(),guard_tripped=threading.Event())
    exec(compile(functions,'actual-v6-functions','exec'),ctx)
    def rows():return {str(child.pid):{'exe':exe,'Uid':'1000 1000 1000 1000','PPid':str(os.getpid()),'TracerPid':'0','stat':Path('/proc',str(child.pid),'stat').read_text(),'cmdline':'fixture own sleep'}}
    ctx['processes']=rows;ctx['pin_seen'](rows());fds=[p['fd'] for p in ctx['pins'].values()]
    emitted=[];ctx['emit']=lambda kind,**data:emitted.append({'kind':kind,**data})
    for error in (subprocess.TimeoutExpired('xwininfo',5),OSError('fixture')):
        def fail(*_,**__):raise error
        ctx['subprocess']=SimpleNamespace(run=fail,TimeoutExpired=subprocess.TimeoutExpired,CompletedProcess=subprocess.CompletedProcess)
        result=ctx['display_probe'](['xwininfo','-root','-tree']);assert result.returncode==-1 and emitted[-1]['kind']=='display_probe_unavailable'
    ctx['subprocess']=SimpleNamespace(run=lambda *a,**k:subprocess.CompletedProcess(a[0],0,stdout='fixture',stderr=''),TimeoutExpired=subprocess.TimeoutExpired,CompletedProcess=subprocess.CompletedProcess)
    assert ctx['display_probe'](['xwininfo']).returncode==0
    ctx['subprocess']=subprocess;ctx['real_subprocess']=subprocess
    index=next(i for i,n in enumerate(tree.body) if isinstance(n,ast.Try) and any(isinstance(x,ast.While) for x in n.body))
    attempt=tree.body[index];failure=ast.Raise(exc=ast.Call(func=ast.Attribute(value=ast.Name(id='real_subprocess',ctx=ast.Load()),attr='TimeoutExpired',ctx=ast.Load()),args=[ast.Constant('xwininfo'),ast.Constant(5)],keywords=[]),cause=None)
    injected=ast.Try(body=[failure],handlers=attempt.handlers,orelse=[],finalbody=[])
    end=next(i for i in range(index+1,len(tree.body)) if isinstance(tree.body[i],ast.Assign) and any(isinstance(t,ast.Name) and t.id=='frozen' for t in tree.body[i].targets))
    cleanup=tree.body[index+1:end]
    ctx['guard_thread']=threading.Thread(target=lambda:ctx['finish_guard'].wait(5));ctx['guard_thread'].start()
    module=ast.fix_missing_locations(ast.Module(body=[injected,*cleanup],type_ignores=[]));exec(compile(module,'actual-loop-exception-and-cleanup','exec'),ctx)
    time.sleep(.03);assert ctx['observer_failure_class']=='TimeoutExpired' and ctx['reason']=='observer_failure'
    assert 'State:\tT' in Path('/proc',str(child.pid),'status').read_text()
    result={'status':'pass','source_sha256':hashlib.sha256(source.encode()).hexdigest(),'display_timeout_nonfatal':True,'display_oserror_nonfatal':True,'display_success':True,'unhandled_loop_exception_stops_owned_child':True,'scope':'actual display/exception/cleanup functions with one own harmless UID1000 child; failure injected only in fixture'}
    (b/'connect-v6-failure-tests.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
finally:
    for fd in fds:
        try:signal.pidfd_send_signal(fd,signal.SIGCONT)
        except ProcessLookupError:pass
        os.close(fd)
    child.terminate();child.wait(timeout=5)