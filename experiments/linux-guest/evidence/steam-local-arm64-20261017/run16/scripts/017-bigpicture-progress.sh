set -eu
python3 - <<'PY'
from pathlib import Path
import subprocess,json,os,time
out=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-connect-5000-v9')
for n in ('games-guardian-summary.json','bp-result.json','bp-guardian-summary.json','bp-dispatch.log'):
 p=out/n
 if p.exists():print(n+'='+p.read_text()[-6000:])
p=Path('/run/ideck/bp-guardian16.log')
if p.exists():print('BP_GUARD='+p.read_text()[-3000:])
print(subprocess.check_output(['xwininfo','-root','-tree'],text=True,timeout=5))
for n in ('steamui_html.txt','webhelper.txt'):
 p=Path('/home/ideck/.local/share/Steam/logs')/n
 if p.exists():print('PRIVATE_UI='+n+'\n'+'\n'.join(p.read_text(errors='replace').splitlines()[-20:]))
PY
