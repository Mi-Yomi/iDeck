set -eu
python3 - <<'PY'
from pathlib import Path
import subprocess,json,time
out=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-connect-5000-v9')
assert not (out/'bp-guardian-summary.json').exists(),'guard must still be active'
def get(a):return subprocess.check_output(['xdotool',*a],text=True,timeout=5).strip()
assert get(['getactivewindow','getwindowname'])=='Steam'
wid=get(['getactivewindow'])
print('BEFORE='+get(['getwindowgeometry','--shell',wid]),flush=True)
# Current QMP pixels show LIBRARY at x155..230,y38..58.
subprocess.run(['xdotool','mousemove','185','47','click','1'],check=True,timeout=5)
r={'time_ns':time.time_ns(),'action':'XTest click visible LIBRARY navigation','target_window':wid,'active_title':get(['getactivewindow','getwindowname']),'x':185,'y':47,'no_game_or_account_action':True}
(out/'library-input.json').write_text(json.dumps(r,indent=2)+'\n');print('INPUT='+json.dumps(r),flush=True)
time.sleep(12)
print('AFTER_TITLE='+get(['getactivewindow','getwindowname']),flush=True)
PY
