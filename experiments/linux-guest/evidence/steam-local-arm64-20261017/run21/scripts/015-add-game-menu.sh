set -eu
python3 - <<'PY'
from pathlib import Path
import subprocess
out=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-desktop-v16')
assert not (out/'summary.json').exists(), 'observer completed; do not inject input into frozen client'
r=subprocess.run(['xdotool','getwindowname','0x200003b'],capture_output=True,text=True,timeout=5)
assert r.returncode==0 and r.stdout.strip()=='Steam'
r=subprocess.run(['xdotool','windowactivate','0x200003b','mousemove','--window','0x200003b','80','575','click','1'],capture_output=True,text=True,timeout=5)
assert r.returncode==0
print('ADD_GAME_CLICK_SENT=true; visible outcome requires later screenshot')
PY
