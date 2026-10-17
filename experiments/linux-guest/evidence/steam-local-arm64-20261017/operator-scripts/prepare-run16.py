from pathlib import Path
import ast,json,hashlib
task=Path(__file__).parent;commands=task/'commands16';commands.mkdir(exist_ok=False)
(commands/'001-persistence.sh').write_bytes((task/'commands15/001-persistence.sh').read_bytes())
s=(task/'commands15/002-start-same-client-profile.sh').read_text()
old="assert result['passed'] and all(t['exit']==0 and not t['stderr'] for t in result['tests'])"
assert s.count(old)==1
s=s.replace(old,"assert result['corrected_cases_pass'] and result['old_stack_bug_reproduced'] and len(result['tests'])==6;assert all(t['exit']==0 and not t['stderr'] for t in result['tests'] if t['case']!='clone-old-v2')")
s=s.replace('resume-local-20261017-connect-5000-preflight/runtime-tests.json','resume-local-20261017-connect-5000-v7/v3-runtime-tests.json')
s=s.replace('9a45229272c8832fc247414dc6cb3de39db2a4a76629664157deaa01b652d873','dd7a19b8531294772b3b11e1742c12341d1df2bd77186fdbf042accdb9c9b4c6')
s=s.replace('0bafcde8555281d433e9537e5bbdce669d932b9aa7e77323b924093f928f9339','14ae446d263a783d341c0236b7fe9a710f4fe7946eb43afde435063473cabb1c')
s=s.replace('/opt/ideck-ipc-probe/','/opt/ideck-ipc-probe-v3/').replace('connect-5000-v7','connect-5000-v9').replace('local-guarded-v7-connect','local-guarded-v9-connect')
# The preflight result stays in the previous run's persistent directory.
s=s.replace('resume-local-20261017-connect-5000-v9/v3-runtime-tests.json','resume-local-20261017-connect-5000-v7/v3-runtime-tests.json')
s=s.replace('# One-parameter experiment: only the verified native connect wait uses 5s.','# Run16: only the interposer forwarding implementation changes; connect wait, scope, launcher mode and resources match run15.')
body=s.split("<<'IDECKPY'\n",1)[1].split('\nIDECKPY',1)[0];compile(body,'run16-monitor','exec')
def funcs(text):return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(text).body if isinstance(n,ast.FunctionDef)}
oldbody=(task/'commands15/002-start-same-client-profile.sh').read_text().split("<<'IDECKPY'\n",1)[1].split('\nIDECKPY',1)[0]
assert funcs(body)==funcs(oldbody)
(commands/'002-start-stack-safe-profile.sh').write_text(s)
progress=(task/'progress-compact-v7.sh').read_text().replace('connect-5000-v7','connect-5000-v9');(commands/'003-first-progress.sh').write_text(progress)
run=(task/'run15.sh').read_text().replace('commands15','commands16').replace('--output "$task/run15" --continue-from "$task/run14"','--output "$task/run16" --continue-from "$task/run15"');(task/'run16.sh').write_text(run)
profile={'comparison':'run15','only_new_steam_runtime_change':'interposer v2 to stack-preserving AArch64 v3 forwarding','source_sha256':'dd7a19b8531294772b3b11e1742c12341d1df2bd77186fdbf042accdb9c9b4c6','library_sha256':'14ae446d263a783d341c0236b7fe9a710f4fe7946eb43afde435063473cabb1c','launcher_mode':'desktop','connect_deadline_ms':5000,'preload_scope':'unchanged','cpu_ram_shm_rendering_unchanged':True,'monitor_functions_ast_identical':True,'script_sha256':hashlib.sha256(s.encode()).hexdigest()}
(task/'profile16.json').write_text(json.dumps(profile,indent=2)+'\n');print(json.dumps(profile))
