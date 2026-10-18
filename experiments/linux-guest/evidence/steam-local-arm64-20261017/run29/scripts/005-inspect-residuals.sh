set -eu
python3 - <<'PY'
from pathlib import Path
import os,json,time
out=Path('/home/ideck/steam-experiment-logs/runtime-tools-run29')
baseline=set(json.loads((out/'baseline-namespaces.json').read_text()))
cases={json.loads(p.read_text())['rooted']['mount_namespace']:p.stem for p in out.glob('namespace-*.json')}
rows=[]
for p in Path('/proc').iterdir():
 if not p.name.isdecimal():continue
 try:
  ns=os.readlink(p/'ns/mnt')
  if ns in baseline:continue
  status=dict(s.split(':',1) for s in p.joinpath('status').read_text().splitlines() if ':' in s)
  row={'pid':int(p.name),'starttime':p.joinpath('stat').read_text().rsplit(') ',1)[1].split()[19],
       'exe':os.readlink(p/'exe'),'cmdline':p.joinpath('cmdline').read_text().replace(chr(0),' '),
       'uid':status['Uid'].split(),'ppid':int(status['PPid']),'tracer':int(status['TracerPid']),
       'state':status['State'].strip(),'mnt':ns,'source_case':cases.get(ns),'root':os.readlink(p/'root'),
       'cwd':os.readlink(p/'cwd')}
  rows.append(row)
 except (FileNotFoundError,ProcessLookupError):pass
r={'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'time_ns':time.time_ns(),'processes':rows}
(out/'residuals-inspected.json').write_text(json.dumps(r,indent=2)+'\n')
print('RESIDUALS='+json.dumps(r))
PY
