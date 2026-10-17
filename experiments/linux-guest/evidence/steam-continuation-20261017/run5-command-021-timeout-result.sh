set -eu
python3 - <<'PY'
from pathlib import Path
import hashlib,json,os,time
p=Path('/home/ideck/Documents/ideck-steam-continuation-20261017.txt')
data=b'Official Steam self-update completed; namespace-corrected UID1000 experiment; no account login.\n'
if p.exists():
 assert p.read_bytes()==data
else:
 with p.open('xb') as f: f.write(data); f.flush(); os.fsync(f.fileno())
 os.chown(p,1000,1000)
client=Path('/home/ideck/.local/share/Steam/steamrtarm64/steam')
print('IDECK_PERSISTENCE_RECORD='+json.dumps({'machine_id':Path('/etc/machine-id').read_text().strip(),'canary_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'client_sha256':hashlib.sha256(client.read_bytes()).hexdigest(),'client_size':client.stat().st_size,'client_uid':client.stat().st_uid}))
PY
sleep 45
printf 'IDECK_TIMEOUT_UI_LOG\n'
tail -35 /home/ideck/.local/share/Steam/logs/steamui_html.txt
tail -25 /home/ideck/.local/share/Steam/logs/cef_log.txt
printf 'IDECK_WINDOWS\n'
DISPLAY=:0 XAUTHORITY=/run/ideck/Xauthority xwininfo -root -tree | head -30
