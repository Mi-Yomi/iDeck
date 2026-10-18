set -eu
python3 - <<'PY'
from pathlib import Path
import subprocess,json,time
out=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-desktop-zero-watchdog-v22')
assert (out/'bp-guardian-started27.json').exists() and not (out/'bp-guardian-summary27.json').exists()
window='0x1e00089'
def run(args):
 p=subprocess.run(args,capture_output=True,text=True,timeout=8)
 assert p.returncode==0,p.stderr
 return p.stdout
assert run(['xdotool','getwindowname',window]).strip()=='Steam Big Picture Mode'
assert 'steamwebhelper' in run(['xprop','-id',window,'WM_CLASS'])
geometry=run(['xdotool','getwindowgeometry','--shell',window])
assert 'WIDTH=800' in geometry and 'HEIGHT=600' in geometry
run(['xdotool','windowactivate','--sync',window])
run(['xdotool','key','space'])
time.sleep(15)
print('BP_INPUT='+json.dumps({'window':window,'action':'Space at actual Welcome to Big Picture tip screen','legal_agreement_accepted':False,'geometry':geometry}))
PY
