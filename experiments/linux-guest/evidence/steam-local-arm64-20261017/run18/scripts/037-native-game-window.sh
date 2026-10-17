set -eu
python3 - <<'PY'
from pathlib import Path
import os,json,subprocess,time
out=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-gamepadui-v13')
deadline=time.monotonic()+10
while not (out/'game-process.json').exists():
    assert time.monotonic()<deadline
    time.sleep(.1)
r=json.loads((out/'game-process.json').read_text());p=Path('/proc')/str(r['pid'])
assert os.readlink(p/'exe')==r['exe'] and (p/'stat').read_text().rsplit(') ',1)[1].split()[19]==r['starttime']
result=subprocess.run(['xdotool','search','--onlyvisible','--pid',str(r['pid'])],capture_output=True,text=True,timeout=5)
ids=result.stdout.split();assert result.returncode==0 and len(ids)==1,repr(result)
win=ids[0]
subprocess.run(['xdotool','windowactivate',win],check=True,timeout=5)
name=subprocess.check_output(['xdotool','getwindowname',win],text=True,timeout=5).strip()
report={'game_pid':r['pid'],'window_id':win,'title':name}
(out/'game-window.json').write_text(json.dumps(report,indent=2)+'\n')
print('GAME_WINDOW='+json.dumps(report))
PY
