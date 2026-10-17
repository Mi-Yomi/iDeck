set -eu
export PYTHONDONTWRITEBYTECODE=1
python3 - <<'PY'
from pathlib import Path
import base64,gzip
base=Path('/home/ideck/steam-experiment-logs')
for folder in ('resume-local-20261017-preflight','resume-local-20261017-first-attempt'):
    root=base/folder
    for p in sorted(root.rglob('*')):
        if p.is_file() and not p.is_symlink() and not p.name.endswith('.deb'):
            b=p.read_bytes();assert len(b)<=16*1024**2
            print('IDECK_BLOB='+folder+'__'+str(p.relative_to(root)).replace('/','__')+':'+base64.b64encode(gzip.compress(b)).decode(),flush=True)
PY