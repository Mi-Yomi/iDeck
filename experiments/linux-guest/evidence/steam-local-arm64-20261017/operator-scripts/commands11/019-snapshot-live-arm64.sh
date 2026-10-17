set -eu
export PYTHONDONTWRITEBYTECODE=1
python3 /run/ideck/snapshot-ipc-stack.py --main-pid 2192 --browser-pid 2295 --tid 2192 --tid 2296 --tid 2295 --tid 2316 --output /home/ideck/steam-experiment-logs/resume-local-20261017-guarded-v2/address-snapshot.json
python3 - <<'PY'
from pathlib import Path
print('IDECK_ADDRESS_SNAPSHOT='+Path('/home/ideck/steam-experiment-logs/resume-local-20261017-guarded-v2/address-snapshot.json').read_text(),flush=True)
PY