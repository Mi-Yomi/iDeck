set -eu
python3 - <<'PY'
from pathlib import Path
import time,json
out=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-desktop-v15')
if not (out/'summary.json').exists():
    with (out/'finish-monitor').open('x') as f:f.write('stop\n')
deadline=time.monotonic()+25
while not (out/'summary.json').exists():
    assert time.monotonic()<deadline
    time.sleep(.1)
print('FINAL_MONITOR='+ (out/'summary.json').read_text())
PY
