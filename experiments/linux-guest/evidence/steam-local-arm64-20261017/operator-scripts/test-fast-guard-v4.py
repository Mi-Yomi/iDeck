"""Exercise the actual watcher functions on this test's own harmless children."""
import ast,hashlib,json,os,select,signal,subprocess,threading,time
from pathlib import Path
from types import SimpleNamespace
root=Path(__file__).resolve().parent
source=(root/'010-background-big-picture-narrow-v4.sh').read_text()
code=source.split("<<'IDECKPY'\n",1)[1].split('\nIDECKPY',1)[0]
tree=ast.parse(code)
functions=ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('identity','pin_seen','freeze_pinned','watch')],type_ignores=[])
compiled=compile(functions,'actual-fast-guard-functions','exec')
results=[]
for case in ('resource_reserve','first_browser_exit','wrong_uid_refused','owned_exec_change'):
    command=['/usr/bin/python3','-c',"import os,time;time.sleep(.4);os.execl('/usr/bin/sleep','sleep','30')"] if case=='owned_exec_change' else ['/usr/bin/sleep','30']
    child=subprocess.Popen(command,user=1000,group=1000,extra_groups=[],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    descriptors=[]
    try:
        exe=os.readlink('/proc/'+str(child.pid)+'/exe')
        class FixtureRoot:
            def __truediv__(self,_):return exe
        class OSProxy:
            def __getattr__(self,name):return getattr(os,name)
            def statvfs(self,_):return SimpleNamespace(f_bavail=350*1024 if case in ('resource_reserve','owned_exec_change') else 700*1024,f_frsize=1024)
        context=dict(Path=Path,os=OSProxy(),signal=signal,select=select,time=time,threading=threading,
            root=FixtureRoot(),read=lambda p:p.read_text(),finish_guard=threading.Event(),guard_tripped=threading.Event(),pin_lock=threading.Lock(),pins={},browser_pid=None,guard_result={},started=time.monotonic())
        exec(compiled,context)
        context['roles']=lambda ps:([],[],set())
        def process_rows():
            try:
                p=Path('/proc')/str(child.pid)
                return {str(child.pid):{'exe':exe,'Uid':'0 0 0 0' if case=='wrong_uid_refused' else '1000 1000 1000 1000','stat':(p/'stat').read_text(),'cmdline':'fixture owned sleep'}}
            except FileNotFoundError:return {}
        context['processes']=process_rows
        context['pin_seen'](process_rows())
        if case=='wrong_uid_refused':
            assert not context['pins'];results.append({'case':case,'status':'pass'});continue
        descriptors=[pin['fd'] for pin in context['pins'].values()]
        if case=='owned_exec_change':
            time.sleep(.6);assert os.readlink('/proc/'+str(child.pid)+'/exe')!=exe
        context['browser_pid']=str(child.pid)
        if case=='first_browser_exit':child.terminate()
        thread=threading.Thread(target=context['watch']);thread.start();thread.join(3)
        assert not thread.is_alive() and context['guard_tripped'].is_set(),context['guard_result']
        result=context['guard_result'];assert 'failure_class' not in result,result
        assert result['cause']==('shared_memory_reserve' if case in ('resource_reserve','owned_exec_change') else 'first_browser_exit'),result
        if case in ('resource_reserve','owned_exec_change'):
            state=(Path('/proc')/str(child.pid)/'status').read_text()
            assert 'State:\tT' in state and 'TracerPid:\t0' in state,state
            signal.pidfd_send_signal(descriptors[0],signal.SIGCONT)
        if case=='owned_exec_change':assert result.get('owned_exec_changes'),result
        results.append({'case':case,'status':'pass','guard':result,'own_child_pid':child.pid})
    finally:
        for fd in descriptors:
            try:signal.pidfd_send_signal(fd,signal.SIGCONT)
            except ProcessLookupError:pass
            os.close(fd)
        child.terminate();child.wait(timeout=5)
receipt={'kind':'watcher functions, own harmless host children only','steam_guest_tested':False,'script_sha256':hashlib.sha256(source.encode()).hexdigest(),'results':results}
(root/'fast-guard-v4-tests.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))