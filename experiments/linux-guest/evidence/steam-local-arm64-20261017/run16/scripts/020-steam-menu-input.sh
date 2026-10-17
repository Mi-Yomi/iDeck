set -eu
python3 - <<'PY'
from pathlib import Path
import subprocess,json,time
out=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-connect-5000-v9')
assert not (out/'bp-guardian-summary.json').exists()
assert subprocess.check_output(['xdotool','getactivewindow','getwindowname'],text=True,timeout=5).strip()=='Steam'
subprocess.run(['xdotool','mousemove','40','19','click','1'],check=True,timeout=5)
r={'time_ns':time.time_ns(),'action':'XTest click visible Steam menu at40,19','result':'awaiting visible menu; injection alone does not prove navigation'}
(out/'steam-menu-input.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r),flush=True)
time.sleep(10)
PY
