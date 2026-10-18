set -eu
python3 - <<'PY'
from pathlib import Path
import subprocess,json,time
out=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-desktop-zero-watchdog-v22')
assert not (out/'summary.json').exists(),'observer finished'
window='0x1e0003b'
def run(args):
 p=subprocess.run(args,capture_output=True,text=True,timeout=8)
 assert p.returncode==0,p.stderr
 return p.stdout
assert run(['xdotool','getwindowname',window]).strip()=='Steam'
assert 'steamwebhelper' in run(['xprop','-id',window,'WM_CLASS'])
geometry=run(['xdotool','getwindowgeometry','--shell',window])
assert 'WIDTH=800' in geometry and 'HEIGHT=600' in geometry
run(['xdotool','windowactivate','--sync',window])
run(['xdotool','mousemove','--window',window,'680','18'])
time.sleep(10)
print('NAVIGATION='+json.dumps({'window':window,'action':'hover visible upper-right display icon at680,18','geometry':geometry}))
PY
