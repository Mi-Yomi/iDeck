set -eu
python3 - <<'PY'
from pathlib import Path
import subprocess,json,os,time
out=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-gamepadui-v13')
r=json.loads((out/'game-process.json').read_text());i=json.loads((out/'game-input.json').read_text())
p=Path('/proc')/str(r['pid'])
assert os.readlink(p/'exe')==r['exe'] and (p/'stat').read_text().rsplit(') ',1)[1].split()[19]==r['starttime']
def xd(*args):return subprocess.check_output(['xdotool',*args],text=True,timeout=5).strip()
win=i['window_id'];assert xd('getwindowname',win)=='XGalaga'
xd('windowactivate',win);assert xd('getactivewindow')==win
xd('key','shift+q')
deadline=time.monotonic()+10
while not (out/'game-result.json').exists():
    assert time.monotonic()<deadline
    time.sleep(.1)
result=json.loads((out/'game-result.json').read_text());assert result['process_reaped'] and result['clean_application_exit']
print('GAME_EXIT='+json.dumps(result))
PY
