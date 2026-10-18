set -eu
export PYTHONDONTWRITEBYTECODE=1
python3 - <<'PY'
from pathlib import Path
import base64,gzip,os,stat,json
out=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-desktop-zero-v20')
for p in Path('/run/user/1000').glob('ideck-ipc-connect-*.jsonl'):
    s=p.lstat();assert stat.S_ISREG(s.st_mode) and s.st_uid==1000 and s.st_size<131072
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,'rb') as f:b=f.read(131073)
    assert len(b)<=131072;(out/p.name).write_bytes(b)
for z in Path('/run/user/1000').glob('ideck-shm-zero-*.jsonl'):
    assert z.stat().st_size<65536;(out/z.name).write_bytes(z.read_bytes())
for name in ('steamui_html.txt','webhelper.txt','cef_log.txt'):
    p=Path('/home/ideck/.local/share/Steam/logs')/name
    if p.is_file() and not p.is_symlink():
        with p.open('rb') as f:f.seek(max(0,p.stat().st_size-32768));b=f.read(32768)
        (out/('post-stop-tail-'+name)).write_bytes(b)
for folder in (out,Path('/home/ideck/steam-experiment-logs/resume-local-20261017-connect-5000-preflight')):
    for p in sorted(folder.rglob('*')):
        if p.is_file() and not p.is_symlink():
            b=p.read_bytes();assert len(b)<=16*1024**2
            print('IDECK_BLOB='+folder.name+'__'+str(p.relative_to(folder)).replace('/','__')+':'+base64.b64encode(gzip.compress(b)).decode(),flush=True)
p=Path('/run/ideck/local-guarded-v20-connect.log');b=p.read_bytes();assert len(b)<=1024**2
print('IDECK_BLOB=connect-monitor.log:'+base64.b64encode(gzip.compress(b)).decode(),flush=True)
PY
