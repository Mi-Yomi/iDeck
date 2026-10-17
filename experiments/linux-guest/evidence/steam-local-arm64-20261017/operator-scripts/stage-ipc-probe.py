from pathlib import Path
import base64,gzip,hashlib,json
b=Path(__file__).resolve().parent
files={'libideck-ipc-connect.so':b/'ipc-probe-build-v2/libideck-ipc-connect.so','arm64-unit':b/'ipc-probe-tests-build-v2/arm64-unit','arm64-abi':b/'ipc-probe-tests-build-v2/arm64-abi'}
records={name:{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'size':p.stat().st_size,'gzip_base64':base64.b64encode(gzip.compress(p.read_bytes(),mtime=0)).decode()} for name,p in files.items()}
code="""set -eu
ulimit -c 0
export PYTHONDONTWRITEBYTECODE=1
python3 - <<'PY'
from pathlib import Path
import os,json,hashlib,base64,gzip,subprocess,time
root=Path('/opt/ideck-ipc-probe');assert not root.exists();root.mkdir(mode=0o755)
records=RECORDS
for name,r in records.items():
    data=gzip.decompress(base64.b64decode(r['gzip_base64'],validate=True));assert len(data)==r['size'] and hashlib.sha256(data).hexdigest()==r['sha256']
    fd=os.open(root/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o555)
    with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
    assert hashlib.sha256((root/name).read_bytes()).hexdigest()==r['sha256']
(root/'staged-files.json').write_text(json.dumps({n:{k:v for k,v in r.items() if k!='gzip_base64'} for n,r in records.items()},indent=2)+'\\n')
out=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-connect-5000-preflight');out.mkdir(exist_ok=False)
results=[]
for name,extra in (('unit',[]),('abi-baseline',[]),('abi-preload',['LD_PRELOAD='+str(root/'libideck-ipc-connect.so'),'IDECK_EXPECT_PRELOAD_LEAF=libideck-ipc-connect.so'])):
    binary=root/('arm64-unit' if name=='unit' else 'arm64-abi')
    env={'PATH':'/usr/bin:/bin','HOME':'/home/ideck','USER':'ideck','LOGNAME':'ideck','LANG':'C.UTF-8'}
    r=subprocess.run(['setpriv','--reuid=1000','--regid=1000','--init-groups','env','IDECK_IPC_WAIT_MODE=extend-5000',*extra,str(binary)],env=env,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=30)
    record={'case':name,'exit':r.returncode,'stdout':r.stdout,'stderr':r.stderr};results.append(record);print('IDECK_ARM64_PROBE_TEST='+json.dumps(record),flush=True)
result={'time_ns':time.time_ns(),'source_sha256':'SOURCE_HASH','platform':'actual AArch64 guest','files':{n:{k:v for k,v in r.items() if k!='gzip_base64'} for n,r in records.items()},'tests':results,'passed':all(r['exit']==0 and not r['stderr'] for r in results),'steam_started':False}
(out/'runtime-tests.json').write_text(json.dumps(result,indent=2)+'\\n');print('IDECK_ARM64_PROBE_VALIDATION='+json.dumps(result),flush=True)
assert result['passed'],'do not launch the Steam experiment'
PY
""".replace('RECORDS',repr(records)).replace('SOURCE_HASH',hashlib.sha256((b/'ipc-connect-wait.c').read_bytes()).hexdigest())
assert len(code.encode())<65536,len(code.encode())
(b/'commands13/002-stage-validate-ipc-probe.sh').write_text(code)
print(json.dumps({'command_bytes':len(code.encode()),'files':{n:{k:v for k,v in r.items() if k!='gzip_base64'} for n,r in records.items()}}))