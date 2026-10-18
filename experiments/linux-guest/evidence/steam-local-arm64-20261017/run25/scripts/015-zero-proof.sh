set -eu
python3 - <<'PROOF'
from pathlib import Path
import json,time,os
out=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-desktop-zero-v20')
end=time.monotonic()+300
while True:
 rows=[]
 for proc in Path('/proc').iterdir():
  if not proc.name.isdecimal():continue
  try:
   exe=os.readlink(proc/'exe')
   if not exe.endswith('/steamrtarm64/steamwebhelper'):continue
   maps=(proc/'maps').read_text()
   if 'libideck-shm-zero.so' not in maps:continue
   rows.append({'pid':int(proc.name),'zero_library_mapped':True,'ipc_timeout_library_mapped':'libideck-ipc-connect' in maps})
  except (FileNotFoundError,ProcessLookupError,PermissionError):pass
 events=[]
 for f in Path('/run/user/1000').glob('ideck-shm-zero-*.jsonl'):
  for line in f.read_text().splitlines():events.append(json.loads(line))
 if rows and any(x['event']=='ready' for x in events):break
 assert time.monotonic()<end,'no verified active browser zero library'
 time.sleep(.2)
assert all(not x['ipc_timeout_library_mapped'] for x in rows)
r={'processes':rows,'events':events,'native_ipc_deadline_ms':500,'client_elf_patched':False}
(out/'zero-proof.json').write_text(json.dumps(r,indent=2)+'\n');print('ZERO_PROOF='+json.dumps(r))
PROOF
