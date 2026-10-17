set -eu
python3 - <<'PY'
from pathlib import Path
import json,os,signal,time
out=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-guarded-attempt-11')
allowed={'/home/ideck/.local/share/Steam/steamrtarm64/steam','/home/ideck/.local/share/Steam/steamrtarm64/steamwebhelper'}
def info(p):
    st=dict(x.split(':',1) for x in (p/'status').read_text().splitlines() if ':' in x)
    raw=(p/'stat').read_text().rsplit(') ',1)[1].split()
    return {'pid':int(p.name),'exe':os.readlink(p/'exe'),'uid':st['Uid'].split(),'tracer':int(st['TracerPid']),'starttime':raw[19],'state':raw[0],'browser':b'-steampid=' in (p/'cmdline').read_bytes() and b'--type=' not in (p/'cmdline').read_bytes()}
rows=[]
for p in Path('/proc').iterdir():
    if not p.name.isdecimal():continue
    try:
        row=info(p)
        if row['exe'] in allowed and row['uid']==['1000']*4 and not row['tracer']:rows.append(row)
    except FileNotFoundError:pass
frozen=[]
for before in sorted(rows,key=lambda r:0 if r['browser'] else 1 if r['exe'].endswith('/steam') else 2):
    fd=os.pidfd_open(before['pid'])
    try:
        now=info(Path('/proc')/str(before['pid']))
        if any(now[k]!=before[k] for k in ('pid','starttime','exe','uid')) or now['tracer']:continue
        signal.pidfd_send_signal(fd,signal.SIGSTOP);frozen.append({k:now[k] for k in ('pid','starttime','exe')})
    except FileNotFoundError:pass
    except ProcessLookupError:pass
    finally:os.close(fd)
time.sleep(.1)
v=os.statvfs('/dev/shm')
result={'frozen':frozen,'shm_free_bytes':v.f_bavail*v.f_frsize,'time_ns':time.time_ns()}
(out/'manual-current-freeze.json').write_text(json.dumps(result,indent=2)+'\n')
(out/'freeze-identities.json').write_text(json.dumps(frozen,indent=2)+'\n')
print('IDECK_CURRENT_FREEZE='+json.dumps(result),flush=True)
PY