set -eu
export PYTHONDONTWRITEBYTECODE=1
python3 - <<'PY'
from pathlib import Path
import hashlib,json,os
out=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-first-attempt')
rows=[]
for row in json.loads((out/'freeze-identities.json').read_text()):
    pid=row['pid'];p=Path('/proc')/str(pid)
    try:
        row.update(exe_now=os.readlink(p/'exe'),argv=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace'),status=(p/'status').read_text(),threads=[])
        with (p/'exe').open('rb') as f:row['running_elf_sha256']=hashlib.file_digest(f,'sha256').hexdigest()
        row['exe_stat']={k:getattr((p/'exe').stat(),k) for k in ('st_dev','st_ino','st_size','st_uid')}
        for t in (p/'task').iterdir():
            row['threads'].append({'tid':int(t.name),'comm':(t/'comm').read_text().strip(),'stat':(t/'stat').read_text(),'wchan':(t/'wchan').read_text().strip(),'syscall':(t/'syscall').read_text().strip()})
        rows.append(row)
    except FileNotFoundError:rows.append({'pid':pid,'exited':True})
(out/'frozen-processes.json').write_text(json.dumps(rows,indent=2)+'\n')
print('IDECK_FROZEN='+json.dumps(rows),flush=True)
PY