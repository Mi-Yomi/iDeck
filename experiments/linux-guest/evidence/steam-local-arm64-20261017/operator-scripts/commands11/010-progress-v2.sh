set -eu
python3 - <<'PY'
from pathlib import Path
import json,subprocess
out=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-guarded-v2')
for name in ('summary.json','fast-guard.json'):
    p=out/name
    if p.exists():print('IDECK_PROGRESS_'+name+'='+p.read_text())
p=out/'timeline.jsonl'
if p.exists():
    rows=p.read_text().splitlines()
    samples=[json.loads(r) for r in rows if '"kind": "sample"' in r]
    if samples:
        row=samples[-1];print('IDECK_PROGRESS='+json.dumps({'seconds':row['seconds'],'shm_free':row['shm']['free'],'processes':{pid:{k:v for k,v in info.items() if k in ('exe','Uid','State','Seccomp','NoNewPrivs')} for pid,info in row['processes'].items()}}))
p=Path('/run/ideck/local-guarded-v2.log')
if p.exists():print('IDECK_MONITOR_LOG='+p.read_text(errors='replace')[-8000:])
subprocess.run(['xdotool','mousemove','405','300'],check=True)
r=subprocess.run(['xwininfo','-root','-tree'],capture_output=True,text=True,timeout=10)
print('IDECK_WINDOWS='+r.stdout)
PY