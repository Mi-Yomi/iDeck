set -eu
if pgrep -u 1000 -x steam >/dev/null || pgrep -u 1000 -x steamwebhelper >/dev/null; then exit 1; fi
python3 - <<'PY'
from pathlib import Path
import hashlib
p=Path('/usr/local/bin/ideck-steam')
b=p.read_bytes()
old=b'set -- -clientbeta steamdeck_publicbeta -cef-ozone-platform=x11 -cef-disable-gpu\n'
assert b.count(old)==1
backup=Path('/run/ideck/ideck-steam-before-timeout-probe')
with backup.open('xb') as f: f.write(b)
p.write_bytes(b.replace(old,old[:-1]+b' -cef-disable-hang-timeouts\n'))
print('IDECK_TIMEOUT_PROBE_ORIGINAL_SHA256='+hashlib.sha256(b).hexdigest())
print('IDECK_TIMEOUT_PROBE_MODIFIED_SHA256='+hashlib.sha256(p.read_bytes()).hexdigest())
PY
python3 /run/ideck/namespace-check.py launch desktop > /home/ideck/steam-experiment-logs/rooted-desktop-timeout-probe.log 2>&1 </dev/null &
sleep 35
grep -v '^IDECK_NAMESPACE_ROOT_READY=' /home/ideck/steam-experiment-logs/rooted-desktop-timeout-probe.log | tail -30
