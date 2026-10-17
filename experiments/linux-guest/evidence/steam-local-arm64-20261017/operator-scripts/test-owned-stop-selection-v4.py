import ast,hashlib,json,os,signal,subprocess,time
from pathlib import Path
base=Path(__file__).resolve().parent;source=(base/'stop-owned-before-vm-v4.sh').read_text();code=source.split("python3 - <<'PY'\n",1)[1].rsplit('\nPY',1)[0]
tree=ast.parse(code);functions=ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('info','scan','same','send')],type_ignores=[])
children=[subprocess.Popen(['/usr/bin/sleep','30'],user=1000,group=1000,extra_groups=[],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL) for _ in range(3)]
try:
    ctx=dict(Path=Path,os=os,signal=signal,root='/fixture/Steam/',original_ns='mnt:original',namespaces={'mnt:owned'},sent=[])
    exec(compile(functions,'actual-owned-stop-selection','exec'),ctx);real=ctx['info']
    def fixture_info(pid):
        i=real(pid)
        if int(pid)==children[0].pid:i.update(exe='/fixture/Steam/steam',mnt='mnt:owned')
        elif int(pid)==children[1].pid:i['mnt']='mnt:owned'
        else:i['mnt']='mnt:original'
        return i
    ctx['info']=fixture_info;rows=ctx['scan']();assert {r['pid'] for r in rows}=={children[0].pid,children[1].pid}
    first=next(r for r in rows if r['pid']==children[0].pid);ctx['send'](first,signal.SIGSTOP);time.sleep(.03);assert real(children[0].pid)['state']=='T';ctx['send'](first,signal.SIGCONT)
    stale={**first,'starttime':str(int(first['starttime'])-1)}
    try:ctx['send'](stale,signal.SIGSTOP)
    except AssertionError:pass
    else:raise AssertionError('stale identity signaled')
    time.sleep(.03);assert real(children[0].pid)['state']!='T' and real(children[2].pid)['state']!='T'
    result={'status':'pass','kind':'actual selection/signal functions with own harmless UID1000 children; namespace/executable fixtures only','source_sha256':hashlib.sha256(source.encode()).hexdigest(),'owned_tree_and_session_dependency_selected':True,'original_namespace_excluded':True,'stale_generation_refused':True,'only_own_child_signaled':True}
    (base/'owned-stop-selection-v4-tests.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
finally:
    for child in children:
        try:child.send_signal(signal.SIGCONT);child.terminate();child.wait(timeout=5)
        except ProcessLookupError:pass