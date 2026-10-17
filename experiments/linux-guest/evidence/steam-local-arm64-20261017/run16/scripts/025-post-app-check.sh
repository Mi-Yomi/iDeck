set -eu
export PYTHONDONTWRITEBYTECODE=1
python3 - <<'PY'
from pathlib import Path
import os,hashlib,json,gzip,base64,subprocess,time
out=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-connect-5000-v9')
stop=json.loads((out/'application-stop.json').read_text());assert stop['ready_for_original_vm_stop']
holders=[]
for p in Path('/proc').iterdir():
    if not p.name.isdecimal():continue
    try:
        ns=os.readlink(p/'ns/mnt')
        if ns in stop['owned_mount_namespaces']:
            holders.append({'pid':int(p.name),'mnt':ns,'exe':os.readlink(p/'exe'),'status':(p/'status').read_text()})
    except FileNotFoundError:continue
before=json.loads(Path('/home/ideck/steam-experiment-logs/resume-local-20261017-preflight/result.json').read_text());client={}
for relative,expected in before['client'].items():
    p=Path('/home/ideck/.local/share/Steam')/relative
    with p.open('rb') as f:sha=hashlib.file_digest(f,'sha256').hexdigest()
    client[relative]={'sha256':sha,'unchanged':sha==expected['sha256']}
audit=subprocess.run(['dpkg','--audit'],capture_output=True)
result={'client':client,'private_namespace_holders':holders,'audit_exit':audit.returncode,'audit_stdout_bytes':len(audit.stdout),'audit_stderr_bytes':len(audit.stderr),'time_ns':time.time_ns(),'ready_for_original_vm_stop':not holders}
(out/'post-application-check.json').write_text(json.dumps(result,indent=2)+'\n');print('IDECK_POST_APPLICATION='+json.dumps(result),flush=True)
for name in ('application-stop.json','post-application-check.json','shutdown-request.log'):
    p=out/name;b=p.read_bytes();assert len(b)<=1024**2
    print('IDECK_BLOB='+name+':'+base64.b64encode(gzip.compress(b)).decode(),flush=True)
assert not holders,'private namespace still held; do not request VM Stop'
assert audit.returncode==0 and not audit.stdout and not audit.stderr
PY