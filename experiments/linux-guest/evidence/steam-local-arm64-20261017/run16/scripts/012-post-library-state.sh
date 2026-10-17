set -eu
python3 - <<'PY'
from pathlib import Path
import subprocess,json
out=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-connect-5000-v9')
for name in ('summary.json','uri-result.json','uri-guardian-summary.json','uri-dispatch.log'):
 p=out/name
 if p.exists():print(name+'='+p.read_text(errors='replace')[-6000:])
p=Path('/run/ideck/uri-guardian16.log')
if p.exists():print('URI_GUARD_LOG='+p.read_text(errors='replace')[-6000:])
for name in ('webhelper.txt','steamui_html.txt'):
 p=Path('/home/ideck/.local/share/Steam/logs')/name
 if p.exists():print('PRIVATE_UI='+name+'\n'+'\n'.join(p.read_text(errors='replace').splitlines()[-30:]))
try:
 r=subprocess.run(['xdotool','getactivewindow','getwindowname'],capture_output=True,text=True,timeout=5);print('ACTIVE='+json.dumps({'exit':r.returncode,'name':r.stdout.strip()}))
except subprocess.TimeoutExpired:print('ACTIVE_UNAVAILABLE')
PY
