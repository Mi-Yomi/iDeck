set -eu
python3 - <<'PY'
from pathlib import Path
import time,json
out=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-desktop-zero-watchdog-v22')
if not (out/'summary.json').exists():
    with (out/'finish-monitor').open('x') as f:f.write('stop\n')
deadline=time.monotonic()+25
while not (out/'summary.json').exists():
    assert time.monotonic()<deadline
    time.sleep(.1)
print('FINAL_MONITOR='+ (out/'summary.json').read_text())
PY

python3 - <<'BP_FINISH'
from pathlib import Path
import json,time
out=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-desktop-zero-watchdog-v22')
if (out/'bp-guardian-started27.json').exists():
 (out/'finish-bp-guardian27').touch(exist_ok=True)
 deadline=time.monotonic()+40
 while not (out/'bp-guardian-summary27.json').exists():
  assert time.monotonic()<deadline
  time.sleep(.2)
 print('BP_GUARDIAN_FINISHED='+json.dumps(json.loads((out/'bp-guardian-summary27.json').read_text())))
BP_FINISH
