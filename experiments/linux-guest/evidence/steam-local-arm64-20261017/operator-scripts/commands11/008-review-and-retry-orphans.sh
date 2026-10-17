set -eu
python3 - <<'PY'
from pathlib import Path
import json,os,subprocess,time
out=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-guarded-attempt-11')
issues=[]
for p in Path('/proc').iterdir():
    if not p.name.isdecimal():continue
    state=None
    try:
        status=(p/'status').read_text();state=next(x for x in status.splitlines() if x.startswith('State:'))
        (p/'stat').read_text()
        for fd in (p/'fd').iterdir():
            try:fd.stat()
            except FileNotFoundError:pass
        (p/'maps').read_text()
    except OSError as e:issues.append({'pid':int(p.name),'state':state,'errno':e.errno,'path_still_exists':p.exists()})
(out/'proc-readability-after-stop.json').write_text(json.dumps(issues,indent=2)+'\n')
print('IDECK_PROC_ISSUES='+json.dumps(issues),flush=True)
if any(r['path_still_exists'] for r in issues):raise RuntimeError('live proc unreadable; recovery retry refused')
manifest=out/'orphan-manifest-v1.json'
import hashlib
checksum=hashlib.sha256(manifest.read_bytes()).hexdigest()
if checksum!='3d965693a88eaf72c3e82bb8a87b96cdf5712b673df30dbd67448edb1579f7fc':raise RuntimeError('manifest changed')
r=subprocess.run(['python3','/opt/ideck-steam/shm-recovery.py','--manifest',str(manifest),'--manifest-sha256',checksum,'--result',str(out/'shm-recovery-v2.json'),'--confirm-orphan-cleanup'],capture_output=True,text=True)
print('IDECK_SHM_RECOVERY='+r.stdout,flush=True)
if r.returncode:raise RuntimeError('strict recovery still refused')
v=os.statvfs('/dev/shm');print('IDECK_SHM_AFTER='+json.dumps({'capacity':v.f_blocks*v.f_frsize,'free':v.f_bavail*v.f_frsize,'remaining_names':[p.name for p in Path('/dev/shm').iterdir()]}),flush=True)
if list(Path('/dev/shm').iterdir()):raise RuntimeError('SHM not empty')
PY