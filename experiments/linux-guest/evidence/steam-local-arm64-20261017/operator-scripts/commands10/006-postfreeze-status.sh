set -eu
python3 - <<'PY'
from pathlib import Path
import json,os,subprocess
out=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-first-attempt')
rows=[]
for row in json.loads((out/'freeze-identities.json').read_text()):
    p=Path('/proc')/str(row['pid']);result={'pid':row['pid']}
    for name in ('status','stat','wchan','syscall'):
        try:result[name]=(p/name).read_text()
        except OSError as e:result[name]={'errno':e.errno}
    try:result['exe']=os.readlink(p/'exe')
    except OSError as e:result['exe_error']={'errno':e.errno}
    rows.append(result)
dmesg=subprocess.run(['dmesg'],capture_output=True,text=True)
result={'processes':rows,'kernel_tail':'\n'.join(dmesg.stdout.splitlines()[-120:]),'dmesg_exit':dmesg.returncode,'meminfo':Path('/proc/meminfo').read_text(),'observer_status':Path('/proc/self/status').read_text()}
(out/'postfreeze-status.json').write_text(json.dumps(result,indent=2)+'\n')
print('IDECK_POSTFREEZE='+json.dumps(result),flush=True)
PY