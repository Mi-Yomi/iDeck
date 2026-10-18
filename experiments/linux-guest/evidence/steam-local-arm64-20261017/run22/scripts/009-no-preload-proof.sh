set -eu
python3 - <<'PY'
from pathlib import Path
import os,json,time
out=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-desktop-native-v17')
end=time.monotonic()+90
while True:
 rows=[]
 for p in Path('/proc').iterdir():
  if not p.name.isdecimal():continue
  try:
   exe=os.readlink(p/'exe')
   if not exe.startswith('/home/ideck/.local/share/Steam/steamrtarm64/'):continue
   maps=(p/'maps').read_text();env=(p/'environ').read_bytes().split(b'\0')
   assert 'libideck-ipc-connect' not in maps,'unexpected diagnostic library mapping'
   assert not any(v.startswith(b'LD_PRELOAD=') or v.startswith(b'IDECK_IPC_WAIT_MODE=') for v in env),'unexpected diagnostic environment'
   status=dict(x.split(':',1) for x in (p/'status').read_text().splitlines() if ':' in x)
   rows.append({'pid':int(p.name),'exe':exe,'state':status['State'].strip(),'uid':status['Uid'].split(),'seccomp':status['Seccomp'].strip(),'no_new_privs':status['NoNewPrivs'].strip(),'tracer':int(status['TracerPid']),'diagnostic_mapping':False,'diagnostic_environment':False})
  except (FileNotFoundError,ProcessLookupError):pass
 if any(x['exe'].endswith('/steamwebhelper') for x in rows):break
 assert time.monotonic()<end,'no browser to verify'
 time.sleep(.2)
r={'time_ns':time.time_ns(),'normal_original_helper':False,'private_helper_launcher_only':True,'no_preload':True,'processes':rows}
(out/'no-preload-proof.json').write_text(json.dumps(r,indent=2)+'\n');print('PROOF='+json.dumps(r),flush=True)
PY
