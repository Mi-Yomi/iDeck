set -eu
python3 - <<'PY'
from pathlib import Path
import subprocess,json,os
out=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-connect-5000-v9')
for name in ('uri-guardian-summary.json','games-result.json','games-guardian-summary.json','games-dispatch.log','launcher.log'):
 p=out/name
 if p.exists():print(name+'='+p.read_text(errors='replace')[-6000:])
p=Path('/run/ideck/games-guardian16.log')
if p.exists():print('GAMES_GUARD_LOG='+p.read_text(errors='replace')[-6000:])
for name in ('webhelper.txt','steamui_html.txt','cef_log.txt'):
 p=Path('/home/ideck/.local/share/Steam/logs')/name
 if p.exists():print('PRIVATE_UI='+name+'\n'+'\n'.join(p.read_text(errors='replace').splitlines()[-15:]))
r=subprocess.run(['xwininfo','-root','-tree'],capture_output=True,text=True,timeout=5);print('WINDOWS='+'\n'.join(x for x in r.stdout.splitlines() if any(t in x for t in ('Steam','Friends','Special Offers','Sign in'))))
PY
