from pathlib import Path
import ast,hashlib,json
task=Path(__file__).parent
source=(task/'012-background-connect-5000-v6.sh').read_text().split("<<'IDECKPY'\n",1)[1].split('\nIDECKPY',1)[0]
tree=ast.parse(source)
names=('read','link','processes','identity','roles','pin_seen','freeze_pinned','watch')
functions='\n\n'.join(ast.get_source_segment(source,n) for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names)
assert sum(isinstance(n,ast.FunctionDef) and n.name in names for n in tree.body)==len(names)
script='''import os,time,json,subprocess,signal,hashlib,threading,select,stat
from pathlib import Path
out=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-connect-5000-v6')
root=Path('/home/ideck/.local/share/Steam')
started=time.monotonic()
finish_guard=threading.Event();guard_tripped=threading.Event()
pin_lock=threading.Lock();pins={};browser_pid=None;guard_result={}
'''+functions+r'''
expected=json.loads((out/'freeze-identities.json').read_text())
assert expected and json.loads((out/'summary.json').read_text())['reason']=='deadline'
pin_seen(processes())
assert {int(p) for p in pins}=={r['pid'] for r in expected}
for row in expected:
    now=identity(row['pid'])
    assert all(now[k]==row[k] for k in ('pid','starttime','exe')) and now['tracer']==0 and now['state']=='T'
guard_thread=threading.Thread(target=watch,daemon=True);guard_thread.start()
records=[]
try:
    for pid,pin in pins.items():
        now=identity(pid);before=pin['identity']
        assert all(now[k]==before[k] for k in ('pid','starttime','uid','exe')) and now['tracer']==0
        signal.pidfd_send_signal(pin['fd'],signal.SIGCONT)
    # Wake Steam's own screensaver through real X11 input, no account action.
    subprocess.run(['xdotool','mousemove_relative','--','35','15'],timeout=5,check=True)
    subprocess.run(['xdotool','key','Escape'],timeout=5,check=True)
    while time.monotonic()-started<300 and not guard_tripped.is_set():
        if (out/'finish-resume').exists():break
        ps=processes();pin_seen(ps)
        v=os.statvfs('/dev/shm')
        row={'seconds':time.monotonic()-started,'shm_free':v.f_bavail*v.f_frsize,'processes':ps}
        records.append(row)
        with (out/'resume-timeline.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
        time.sleep(2)
finally:
    finish_guard.set();guard_thread.join(10)
    if not guard_tripped.is_set():freeze_pinned('resume_operator_budget')
    result={'seconds':time.monotonic()-started,'guard':guard_result,'resume_only_same_client':True,'steam_runtime_configuration_changed':False}
    (out/'resume-summary.json').write_text(json.dumps(result,indent=2)+'\n')
    for pin in pins.values():os.close(pin['fd'])
'''
compile(script,'resume14','exec')
command="set -eu\ncat > /run/ideck/resume14.py <<'RESUME'\n"+script+"\nRESUME\nsetsid python3 /run/ideck/resume14.py </dev/null >/run/ideck/resume14.log 2>&1 &\nprintf 'IDECK_RESUME_PID=%s\\n' \"$!\"\n"
(task/'commands14/010-resume-existing.sh').write_text(command)
(task/'resume14-source.json').write_text(json.dumps({'selected_functions_ast_identical':list(names),'command_sha256':hashlib.sha256(command.encode()).hexdigest(),'source_sha256':hashlib.sha256(source.encode()).hexdigest()},indent=2)+'\n')
print('queued resume existing client with identical guard functions')
