set -eu
export PYTHONDONTWRITEBYTECODE=1
python3 - <<'PY'
from pathlib import Path
import gzip,base64,json
root=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-guarded-v2')
paths=[root/'address-snapshot-parent.json',root/'parent-checked-tools.json',root/'post-pause-probe.json',*sorted((root/'post-pause-trace').glob('*'))]
for p in paths:
    if p.is_file() and not p.is_symlink():
        b=p.read_bytes();assert len(b)<=16*1024**2
        print('IDECK_BLOB='+str(p.relative_to(root)).replace('/','__')+':'+base64.b64encode(gzip.compress(b)).decode(),flush=True)
PY