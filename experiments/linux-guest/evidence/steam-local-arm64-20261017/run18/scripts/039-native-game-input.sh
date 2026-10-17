set -eu
python3 - <<'PY'
from pathlib import Path
import subprocess,json,os,time
out=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-gamepadui-v13')
r=json.loads((out/'game-process.json').read_text());p=Path('/proc')/str(r['pid'])
assert os.readlink(p/'exe')==r['exe'] and (p/'stat').read_text().rsplit(') ',1)[1].split()[19]==r['starttime']
def xd(*args):return subprocess.check_output(['xdotool',*args],text=True,timeout=5).strip()
ids=xd('search','--onlyvisible','--name','^XGalaga$').split();assert len(ids)==1
win=ids[0];xd('windowactivate',win)
assert xd('getactivewindow')==win and xd('getwindowname',win)=='XGalaga'
xd('key','k');time.sleep(1)
xd('keydown','Right');time.sleep(.5);xd('keyup','Right')
xd('key','space');time.sleep(1)
report={'identity':r,'window_id':win,'title':'XGalaga','pid_window_property_unavailable':True,'actions':['k','Right held 0.5s','space'],'game_acceptance':'requires actual frame inspection'}
(out/'game-input.json').write_text(json.dumps(report,indent=2)+'\n')
print('GAME_INPUT='+json.dumps(report))
PY
