set -eu
python3 - <<'PY'
from pathlib import Path
import json,os,time
out=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-guarded-v2')
rows=[]
for pid in (2192,2295,2479):
    p=Path('/proc')/str(pid);row={'pid':pid}
    for name in ('status','stat','maps'):
        try:row[name]=(p/name).read_text()
        except OSError as e:row[name]={'errno':e.errno}
    for name in ('exe','cwd'):
        try:row[name]=os.readlink(p/name)
        except OSError as e:row[name]={'errno':e.errno}
    try:row['argv']=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
    except OSError as e:row['argv']={'errno':e.errno}
    rows.append(row)
files=[]
for directory in (Path('/tmp/dumps'),Path('/home/ideck/.local/share/Steam/dumps')):
    if not directory.exists():continue
    for p in directory.iterdir():
        s=p.lstat();files.append({'path':str(p),'size':s.st_size,'uid':s.st_uid,'mode':oct(s.st_mode),'mtime_ns':s.st_mtime_ns})
result={'time_ns':time.time_ns(),'processes':rows,'dump_files':files}
(out/'first-browser-crash-state.json').write_text(json.dumps(result,indent=2)+'\n')
print('IDECK_CRASH_STATE='+json.dumps({**result,'processes':[{k:v for k,v in r.items() if k!='maps'} for r in rows]}),flush=True)
PY