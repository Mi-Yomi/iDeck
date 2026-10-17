set -eu
python3 - <<'PY'
import hashlib,json
from pathlib import Path
root=Path('/home/ideck/.cache/ideck-steam-parts')
assert not root.is_symlink()
report=json.loads(Path('/var/log/ideck-steam-install/result.json').read_text())
assert report['status']=='installed_private_client_not_launched'
parts=json.loads(Path('/opt/ideck-steam/steam-client.lock.json').read_text())['parts']
for p in parts:
 f=root/p['file']
 assert f.parent==root and f.is_file() and not f.is_symlink() and f.stat().st_size==p['size']
 with f.open('rb') as s:assert hashlib.file_digest(s,'sha256').hexdigest()==p['sha256']
for p in parts:(root/p['file']).unlink()
print('VERIFIED_PRIVATE_INSTALLER_CACHE_REMOVED_BYTES',sum(p['size'] for p in parts))
PY
df -h /
tail -25 /home/ideck/steam-experiment-logs/desktop.log
