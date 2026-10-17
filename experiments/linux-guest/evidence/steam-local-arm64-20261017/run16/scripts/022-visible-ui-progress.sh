set -eu
sleep 25
python3 - <<'PY'
from pathlib import Path
import json,subprocess
out=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-connect-5000-v9')
for n in ('bp-guardian-summary.json','ui-guardian-summary.json'):
 p=out/n
 if p.exists():print(n+'='+p.read_text())
print('UI_GUARD='+Path('/run/ideck/ui-guardian16.log').read_text()[-3000:])
print('WINDOWS='+subprocess.check_output(['xwininfo','-root','-tree'],text=True,timeout=5))
for n in ('steamui_html.txt','webhelper.txt'):
 p=Path('/home/ideck/.local/share/Steam/logs')/n
 print('PRIVATE_UI='+n+'\n'+'\n'.join(p.read_text(errors='replace').splitlines()[-10:]))
PY
