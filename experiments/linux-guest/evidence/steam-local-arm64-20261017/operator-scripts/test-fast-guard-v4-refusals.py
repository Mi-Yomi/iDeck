import ast,hashlib,json,os,select,signal,subprocess,threading,time
from pathlib import Path
from types import SimpleNamespace
root=Path(__file__).resolve().parent
source=(root/'010-background-big-picture-narrow-v4.sh').read_text();code=source.split("<<'IDECKPY'\n",1)[1].split('\nIDECKPY',1)[0]
compiled=compile(ast.Module(body=[n for n in ast.parse(code).body if isinstance(n,ast.FunctionDef) and n.name in ('identity','pin_seen','freeze_pinned','watch')],type_ignores=[]),'actual-watcher-functions','exec')
results=[]
for case in ('existing_tracer','generation_changed'):
    children=[subprocess.Popen(['/usr/bin/sleep','30'],user=1000,group=1000,extra_groups=[],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL) for _ in range(2)]
    pins=[]
    try:
        exe=os.readlink('/proc/'+str(children[0].pid)+'/exe')
        class FixtureRoot:
            def __truediv__(self,_):return exe
        class OSProxy:
            def __getattr__(self,key):return getattr(os,key)
            def statvfs(self,_):return SimpleNamespace(f_bavail=350*1024,f_frsize=1024)
        context=dict(Path=Path,os=OSProxy(),signal=signal,select=select,time=time,threading=threading,root=FixtureRoot(),read=lambda p:p.read_text(),finish_guard=threading.Event(),guard_tripped=threading.Event(),pin_lock=threading.Lock(),pins={},browser_pid=None,guard_result={},started=time.monotonic())
        exec(compiled,context)
        context['roles']=lambda ps:([],[],set())
        def rows():return {str(c.pid):{'exe':exe,'Uid':'1000 1000 1000 1000','stat':Path('/proc',str(c.pid),'stat').read_text(),'cmdline':'fixture own sleep'} for c in children}
        context['processes']=rows;context['pin_seen'](rows());pins=[p['fd'] for p in context['pins'].values()]
        real_identity=context['identity']
        def fixture_identity(pid):
            info=real_identity(pid)
            if int(pid)==children[1].pid:
                if case=='existing_tracer':info['tracer']=99999
                else:info['starttime']=str(int(info['starttime'])+1)
            return info
        context['identity']=fixture_identity;context['browser_pid']=str(children[0].pid)
        thread=threading.Thread(target=context['watch']);thread.start();thread.join(3)
        assert not thread.is_alive() and context['guard_tripped'].is_set(),context['guard_result']
        assert 'failure_class' not in context['guard_result'] and context['guard_result'].get('refused_pins'),context['guard_result']
        assert 'State:\tT' in Path('/proc',str(children[0].pid),'status').read_text()
        assert 'State:\tT' not in Path('/proc',str(children[1].pid),'status').read_text()
        results.append({'case':case,'status':'pass','valid_target_stopped':True,'refused_target_untouched':True})
    finally:
        for fd in pins:
            try:signal.pidfd_send_signal(fd,signal.SIGCONT)
            except ProcessLookupError:pass
            os.close(fd)
        for c in children:c.terminate();c.wait(timeout=5)
receipt={'kind':'actual watcher functions, own harmless host children; tracer/starttime values injected only in fixtures','steam_guest_tested':False,'script_sha256':hashlib.sha256(source.encode()).hexdigest(),'results':results}
(root/'fast-guard-v4-refusal-tests.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))