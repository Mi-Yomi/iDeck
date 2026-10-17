set -eu
python3 - <<'PY'
from pathlib import Path
import json,os
out=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-connect-5000-v9')
for name in ('summary.json','fast-guard.json'):
 p=out/name
 if p.is_file():print(name+'='+p.read_text())
p=out/'timeline.jsonl';sample=None
if p.exists():
 for line in p.read_text().splitlines():
  try:row=json.loads(line)
  except json.JSONDecodeError:continue
  if row.get('kind')=='sample':sample=row
if sample:
 rows={}
 for pid,r in sample['processes'].items():
  row={k:r.get(k) for k in ('State','Seccomp','NoNewPrivs','PPid')}
  if r.get('exe','').endswith('/steam'):
   row['mode_flags']=[x for x in r['cmdline'].split() if x in ('-nobigpicture','-gamepadui','-steamdeck','-steamos3')]
  rows[pid]=row
 print('SAMPLE='+json.dumps({'seconds':sample['seconds'],'shm_free':sample['shm']['free'],'processes':rows}))
for p in out.glob('ideck-ipc-connect-*.jsonl'):print('CONNECT='+p.read_text())
for name in ('steamui_html.txt','webhelper.txt'):
 p=out/('delta-'+name)
 if p.exists():print('LOG='+name+'\n'+'\n'.join(p.read_text(errors='replace').splitlines()[-20:]))
PY
