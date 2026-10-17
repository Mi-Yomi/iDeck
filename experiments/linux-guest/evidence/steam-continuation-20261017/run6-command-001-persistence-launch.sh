set -eu
sha256sum /opt/ideck-steam/namespace-check.py /usr/local/bin/ideck-steam
python3 - <<'PY'
from pathlib import Path
import hashlib,json
p=Path('/home/ideck/Documents/ideck-steam-continuation-20261017.txt')
assert hashlib.sha256(p.read_bytes()).hexdigest()=='da4a878f74aad07470b03d8811ed1e86bec4ac181c3fa01bc0d4a91bc67a5aa6'
assert Path('/etc/machine-id').read_text().strip()=='01565bdc88738f43157a024d6ad341d2'
c=Path('/home/ideck/.local/share/Steam/steamrtarm64/steam')
assert hashlib.sha256(c.read_bytes()).hexdigest()=='73da03ead208a74e14bee566869a4235063dc4a9e1063f29c4608de6d78bd4ea'
assert c.stat().st_uid==1000
assert hashlib.sha256(Path('/opt/ideck-steam/namespace-check.py').read_bytes()).hexdigest()=='96c929eafefb2f76aa7751fb1869baa6def54e5e31be2a0e6620a486bca64b0d'
print('IDECK_PERSISTENCE_AFTER_REBOOT=PASS')
p=Path('/usr/local/bin/ideck-steam'); b=p.read_bytes()
assert hashlib.sha256(b).hexdigest()=='470bdf1559fb5272776dd076cf04a58a3a81b4c451bf97b9a870d8e1f9957603'
old=b'set -- -clientbeta steamdeck_publicbeta -cef-ozone-platform=x11 -cef-disable-gpu\n'
assert b.count(old)==1
with Path('/run/ideck/ideck-steam-before-composer-probe').open('xb') as f: f.write(b)
p.write_bytes(b.replace(old,old[:-1]+b' -system-composer\n'))
print('IDECK_SYSTEM_COMPOSER_PROBE=enabled_for_this_launch_only')
PY
df -B1 / /dev/shm
python3 /opt/ideck-steam/namespace-check.py launch desktop > /home/ideck/steam-experiment-logs/rooted-desktop-composer-probe.log 2>&1 </dev/null &
sleep 35
grep -v '^IDECK_NAMESPACE_ROOT_READY=' /home/ideck/steam-experiment-logs/rooted-desktop-composer-probe.log | tail -45
