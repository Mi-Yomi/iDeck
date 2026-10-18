set -eu
ulimit -c 0
export PYTHONDONTWRITEBYTECODE=1
python3 - <<'PY'
from pathlib import Path
import os,stat,hashlib,json,subprocess
root=Path('/opt/ideck-shm-zero');s=root.lstat()
assert stat.S_ISDIR(s.st_mode) and s.st_uid==0 and stat.S_IMODE(s.st_mode)==0o755
pins={'libideck-shm-zero.so':'c350f21128358eb4bdc942db571affe38b5817341e9656cadb7e592c74e36f9d','arm64-unit':'899c58f026debed7d28deffb660894fc5c0e4c809191974a0de72e61b6104cfc','shm-zero-ipc27-wake':'8693c717ca50ac2f1199db189555d68df4f00002411e7a404379504eaa8f57b1'}
files={}
for n,digest in pins.items():
 p=root/n;s=p.lstat()
 assert stat.S_ISREG(s.st_mode) and s.st_uid==0 and stat.S_IMODE(s.st_mode)==0o555 and s.st_nlink==1
 assert hashlib.sha256(p.read_bytes()).hexdigest()==digest
 files[n]={'size':s.st_size,'sha256':digest}
results=[]
for label,extra in (('arm64-unit',[]),('arm64-preload-fallback',['LD_PRELOAD='+str(root/'libideck-shm-zero.so')])):
 p=subprocess.run(['setpriv','--reuid=1000','--regid=1000','--init-groups','env',*extra,str(root/'arm64-unit')],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=45)
 results.append({'case':label,'exit':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
for label,extra in (('arm64-ipc',[]),('arm64-ipc-preload-fallback',['LD_PRELOAD='+str(root/'libideck-shm-zero.so')])):
 p=subprocess.run(['setpriv','--reuid=1000','--regid=1000','--init-groups','env',*extra,str(root/'shm-zero-ipc27-wake')],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=45)
 results.append({'case':label,'exit':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
r={'platform':'actual ARM64 guest','files':files,'tests':results,'passed':all(x['exit']==0 and not x['stderr'] for x in results),'steam_started':False,'reuses_verified_unchanged_v5_library':True}
print('ZERO_UNIT='+json.dumps(r),flush=True)
assert r['passed'],'do not start Steam after failed fresh fixture'
p=Path('/run/ideck/shm-zero-29-runtime-tests.json');fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
with os.fdopen(fd,'w') as f:json.dump(r,f,indent=2);f.write('\n')
PY
