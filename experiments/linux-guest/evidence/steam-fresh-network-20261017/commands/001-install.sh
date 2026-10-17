#!/bin/sh
set -eu
python3 /opt/ideck-steam/install-cached.py --port "$IDECK_CACHE_PORT" --private-qemu-cache --retain-client-cache
python3 - <<'PY'
import hashlib,json,pathlib,subprocess
r=subprocess.run(['dpkg','--audit'],capture_output=True)
assert r.returncode==0 and r.stdout==b'' and r.stderr==b''
print('FRESH_DPKG_AUDIT='+json.dumps({'exit_code':r.returncode,'stdout_bytes':len(r.stdout),'stderr_bytes':len(r.stderr)}))
root=pathlib.Path('/home/ideck/.local/share/Steam')
print('FRESH_CLIENT_INSTALL='+pathlib.Path('/var/log/ideck-steam-install/result.json').read_text())
print('FRESH_LSOF_VERSION='+subprocess.run(['lsof','-v'],capture_output=True,text=True).stderr)
print('FRESH_GUEST_STORAGE='+subprocess.run(['df','-B1','/home/ideck','/dev/shm'],capture_output=True,text=True).stdout)
for n in ['steamrtarm64/steam','steamrtarm64/steamwebhelper','steamrtarm64/steamclient.so','steamrtarm64/chromehtml.so']:
 p=root/n
 print('FRESH_ELF='+json.dumps({'path':n,'size':p.stat().st_size,'sha256':hashlib.file_digest(p.open('rb'),'sha256').hexdigest()}))
PY
