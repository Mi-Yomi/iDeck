set -eu
export PYTHONDONTWRITEBYTECODE=1
python3 - <<'PY'
from pathlib import Path
import hashlib,json,subprocess,time
base=Path('/home/ideck/steam-experiment-logs')
before=json.loads((base/'resume-local-20261017-preflight/result.json').read_text())
def digest(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
for relative,record in before['client'].items():
    p=Path('/home/ideck/.local/share/Steam')/relative
    if p.stat().st_uid!=1000 or digest(p)!=record['sha256']:raise RuntimeError('client persistence mismatch: '+relative)
for path,key in (('/etc/machine-id','machine_id_sha256'),('/home/ideck/Documents/ideck-steam-continuation-20261017.txt','document_sha256')):
    if digest(Path(path))!=before[key]:raise RuntimeError('control persistence mismatch')
audit=subprocess.run(['dpkg','--audit'],capture_output=True)
if audit.returncode or audit.stdout or audit.stderr:raise RuntimeError('dpkg audit not empty')
lsof=subprocess.check_output(['dpkg-query','-W','-f=${Version}','lsof'],text=True)
if lsof!='4.99.4+dfsg-2':raise RuntimeError('lsof not persistent')
result={'status':'pass','time_ns':time.time_ns(),'client_sha256_unchanged':before['client'],'machine_id_sha256':before['machine_id_sha256'],'document_sha256':before['document_sha256'],'lsof_version':lsof,'audit_exit':0,'audit_output_bytes':0,'client_reinstalled':False,'display_recovery':json.loads(Path('/run/ideck/display-recovery.json').read_text())}
(base/'resume-local-20261017-persistence.json').write_text(json.dumps(result,indent=2)+'\n')
print('IDECK_PERSISTENCE='+json.dumps(result),flush=True)
PY