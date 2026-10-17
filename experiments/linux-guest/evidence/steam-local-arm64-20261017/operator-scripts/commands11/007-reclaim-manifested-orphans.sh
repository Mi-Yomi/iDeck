set -eu
export PYTHONDONTWRITEBYTECODE=1
python3 - <<'PY'
from pathlib import Path
import hashlib,json,os,re,stat,subprocess
out=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-guarded-attempt-11')
stop=json.loads((out/'owned-stop.json').read_text())
if not stop['ready_for_orphan_check'] or stop['remaining']:raise RuntimeError('Steam not stopped')
timeline=[json.loads(line) for line in (out/'timeline.jsonl').read_text().splitlines()]
baseline=next(row for row in timeline if row['kind']=='preflight')
if baseline['shm']['objects'] or baseline['shm']['used'] or baseline['processes']:raise RuntimeError('same-boot empty baseline required')
processes={}
for row in timeline:
    for pid,info in row.get('processes',{}).items():
        start=int(info['stat'].rsplit(') ',1)[1].split()[19])
        if pid in processes and processes[pid]!=start:raise RuntimeError('PID reused in captured attempt')
        processes[pid]=start
for row in stop['captured']:processes[str(row['pid'])]=int(row['starttime'])
objects=[]
for p in Path('/dev/shm').iterdir():
    if not re.fullmatch(r'u1000-(?:Shm_[0-9a-f]{1,8}|ValveIPCSharedObj-Steam)',p.name):raise RuntimeError('unexpected SHM name; nothing removed')
    s=p.lstat()
    if not stat.S_ISREG(s.st_mode) or s.st_nlink!=1 or s.st_uid!=1000 or stat.S_IMODE(s.st_mode)!=0o700:raise RuntimeError('unexpected SHM identity')
    objects.append({'name':p.name,'device':s.st_dev,'inode':s.st_ino,'uid':s.st_uid,'size':s.st_size,'mode':stat.S_IMODE(s.st_mode)})
manifest={'schema':1,'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'baseline_empty':True,'capture_complete':True,'objects':objects,'processes':[{'pid':int(pid),'starttime':start} for pid,start in sorted(processes.items(),key=lambda pair:int(pair[0]))]}
path=out/'orphan-manifest-v1.json'
data=(json.dumps(manifest,indent=2)+'\n').encode()
fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
checksum=hashlib.sha256(data).hexdigest()
helper=Path('/opt/ideck-steam/shm-recovery.py')
if hashlib.sha256(helper.read_bytes()).hexdigest()!='f90092f629593f6f653825e35359dd9f4a08a3ffef7a370d417719a1a9070b7e':raise RuntimeError('recovery helper differs')
print('IDECK_ORPHAN_MANIFEST='+json.dumps({'sha256':checksum,'path':str(path),'objects':len(objects),'captured_processes':len(processes)}),flush=True)
result=subprocess.run(['python3',str(helper),'--manifest',str(path),'--manifest-sha256',checksum,'--result',str(out/'shm-recovery-v1.json'),'--confirm-orphan-cleanup'],capture_output=True,text=True)
print('IDECK_SHM_RECOVERY='+result.stdout,flush=True)
if result.returncode:raise RuntimeError('strict orphan recovery refused; inspect receipt')
v=os.statvfs('/dev/shm')
print('IDECK_SHM_AFTER='+json.dumps({'capacity':v.f_blocks*v.f_frsize,'free':v.f_bavail*v.f_frsize,'remaining_names':[p.name for p in Path('/dev/shm').iterdir()]}),flush=True)
if list(Path('/dev/shm').iterdir()) or v.f_bavail*v.f_frsize<700*1024**2:raise RuntimeError('clean SHM baseline not restored')
PY