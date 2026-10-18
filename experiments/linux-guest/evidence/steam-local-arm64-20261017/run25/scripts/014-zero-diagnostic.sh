set -eu
python3 - <<'PY'
from pathlib import Path
import os,json,hashlib,stat
out=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-desktop-zero-v20')
rows=[]
for p in Path('/proc').iterdir():
 if not p.name.isdecimal():continue
 try:
  if (p/'comm').read_text().strip() not in ('steam','steamwebhelper'):continue
  args=(p/'cmdline').read_bytes().split(b'\0')
  env=(p/'environ').read_bytes().split(b'\0')
  st=(p/'status').read_text().splitlines()
  rows.append({'pid':int(p.name),'exe':os.readlink(p/'exe'),'type':[x.decode(errors='replace') for x in args if x.startswith(b'--type=')], 'preload':[x.decode(errors='replace') for x in env if x.startswith(b'LD_PRELOAD=')], 'state':[x for x in st if x.startswith(('State:','Seccomp:','NoNewPrivs:'))], 'zero_mapped':'libideck-shm-zero.so' in (p/'maps').read_text()})
 except (FileNotFoundError,PermissionError,ProcessLookupError):pass
paths={}
for name in ('/run/user/1000','/usr/lib/aarch64-linux-gnu/libcrypto.so.3','/home/ideck/.local/share/Steam/steamrtarm64/steamwebhelper'):
 p=Path(name)
 try:
  s=p.stat();paths[name]={'uid':s.st_uid,'mode':oct(stat.S_IMODE(s.st_mode)),'nlink':s.st_nlink,'size':s.st_size}
  if p.name=='steamwebhelper':paths[name]['sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
 except OSError as e:paths[name]={'errno':e.errno}
logs=[]
for p in Path('/run/user/1000').glob('ideck-shm-zero-*.jsonl'):
 s=p.stat();logs.append({'name':p.name,'size':s.st_size,'uid':s.st_uid,'mode':oct(stat.S_IMODE(s.st_mode))})
r={'processes':rows,'paths':paths,'logs':logs,'observer_finished':(out/'summary.json').exists()}
(out/'zero-diagnostic.json').write_text(json.dumps(r,indent=2)+'\n');print('ZERO_DIAGNOSTIC='+json.dumps(r))
PY
