set -eu
python3 - <<'PY'
from pathlib import Path
import json,os,re
out=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-desktop-v16')
m=dict(re.findall(r'^(\w+):\s+(\d+) kB',Path('/proc/meminfo').read_text(),re.M))
assert all(k in m for k in ('MemTotal','MemAvailable','SwapTotal'))
s=os.statvfs('/dev/shm')
r={'memory_kib':{k:int(m[k]) for k in ('MemTotal','MemAvailable','SwapTotal')},'shm_total_bytes':s.f_blocks*s.f_frsize,'shm_free_bytes':s.f_bavail*s.f_frsize,'note':'SHM tmpfs default capacity also changes with RAM; this is not a fixed-SHM-capacity control'}
(out/'guest-resource-budget.json').write_text(json.dumps(r,indent=2)+'\n')
print('RESOURCE_BUDGET='+json.dumps(r))
PY
