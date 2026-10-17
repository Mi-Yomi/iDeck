from pathlib import Path
import ast,hashlib,json
task=Path(__file__).parent
p=task/'commands15/002-start-same-client-profile.sh';s=p.read_text()
assert s.count("'launch','big-picture'")==1
s=s.replace("'launch','big-picture'","'launch','desktop'")
old=(task/'012-background-connect-5000-v6.sh').read_text()
def body(x):return x.split("<<'IDECKPY'\n",1)[1].split('\nIDECKPY',1)[0]
compile(body(s),'profile15','exec')
def funcs(x):return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(body(x)).body if isinstance(n,ast.FunctionDef)}
assert funcs(s)==funcs(old)
p.write_text(s)
record={'profile_mode':'desktop','comparison_run':'run14','only_new_steam_runtime_variable':'launcher mode big-picture to desktop; removes SteamOS/SteamDeck flags via existing supported launcher','connect_probe_unchanged':True,'library_sha256':'0bafcde8555281d433e9537e5bbdce669d932b9aa7e77323b924093f928f9339','cpu_ram_shm_unchanged':True,'monitor_functions_ast_identical':True,'operator_monitor_budget_seconds':1200,'runner_budget_seconds':2100,'script_sha256':hashlib.sha256(s.encode()).hexdigest()}
(task/'profile15.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record))
