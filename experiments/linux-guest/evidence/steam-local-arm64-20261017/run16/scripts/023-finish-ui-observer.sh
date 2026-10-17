set -eu
python3 - <<'PY'
from pathlib import Path
import time,json
o=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-connect-5000-v9')
p=o/'finish-ui-guardian';assert not p.exists();p.write_text('stop\n')
deadline=time.monotonic()+25
while not (o/'ui-guardian-summary.json').exists():
 assert time.monotonic()<deadline,'UI guard did not complete; do not stop VM'
 time.sleep(.1)
print('UI_FINAL='+ (o/'ui-guardian-summary.json').read_text(),flush=True)
print('UI_GUARD='+Path('/run/ideck/ui-guardian16.log').read_text(),flush=True)
PY
