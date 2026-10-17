from pathlib import Path
import ast,hashlib,json,textwrap
b=Path(__file__).resolve().parent;s=(b/'011-background-observe-v5.sh').read_text()
s=s.replace('resume-local-20261017-connect-observe-v5','resume-local-20261017-connect-5000-v6').replace('local-guarded-v5-observe','local-guarded-v6-connect').replace('namespace-connect-observe.py','namespace-connect-5000.py').replace('ipc-observe-profile.json','ipc-connect-5000-profile.json')
s=s.replace('IDECK_IPC_WAIT_MODE=observe','IDECK_IPC_WAIT_MODE=extend-5000').replace("'mode':'observe'","'mode':'extend-5000'").replace("'effective_deadline_ms':500,","'effective_deadline_ms':5000,")
s=s.replace('# Observer baseline: the verified library leaves every IPC deadline unchanged.','# One-parameter experiment: only the verified native connect wait uses 5s.')
helper='''def display_probe(argv):
    try:
        return subprocess.run(argv,capture_output=True,text=True,timeout=5)
    except (subprocess.TimeoutExpired,OSError) as error:
        emit('display_probe_unavailable',command=argv[0],failure_class=type(error).__name__)
        return subprocess.CompletedProcess(argv,-1,stdout='',stderr='unavailable')

'''
s=s.replace('def read(path):',helper+'def read(path):')
for point in ('400','410'):
    y='300';needle="subprocess.run(['xdotool','mousemove','"+point+"','"+y+"'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=5)";s=s.replace(needle,"display_probe(['xdotool','mousemove','"+point+"','"+y+"'])")
s=s.replace("subprocess.run(['xwininfo','-root','-tree'],capture_output=True,text=True,timeout=5)","display_probe(['xwininfo','-root','-tree'])")
start=s.index('while time.monotonic()-started < 600:');end=s.index('finish_guard.set();guard_thread.join(10)',start);body=s[start:end]
s=s[:start]+"observer_failure_class=None\ntry:\n"+textwrap.indent(body,'    ')+"except BaseException as error:\n    observer_failure_class=type(error).__name__\n    reason='observer_failure'\n"+s[end:]
s=s.replace("'reason':reason,'seconds':time.monotonic()-started","'reason':reason,'observer_failure_class':observer_failure_class,'seconds':time.monotonic()-started")
code=s.split("<<'IDECKPY'\n",1)[1].split('\nIDECKPY',1)[0];tree=ast.parse(code)
(b/'012-background-connect-5000-v6.sh').write_text(s)
old=(b/'010-background-big-picture-narrow-v4.sh').read_text().split("<<'IDECKPY'\n",1)[1].split('\nIDECKPY',1)[0]
checks={}
for name in ('identity','roles','pin_seen','freeze_pinned','watch'):
    a=next(n for n in ast.parse(old).body if isinstance(n,ast.FunctionDef) and n.name==name);c=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
    assert ast.dump(a,include_attributes=False)==ast.dump(c,include_attributes=False),name;checks[name]='identical to tested v4 functions'
(b/'connect-v6-guard-equivalence.json').write_text(json.dumps({'source_sha256':hashlib.sha256(s.encode()).hexdigest(),'guards':checks,'source_compiles':True},indent=2)+'\n')
print(json.dumps({'source_sha256':hashlib.sha256(s.encode()).hexdigest(),'guard_functions_identical':list(checks),'not_deployed_yet':True}))