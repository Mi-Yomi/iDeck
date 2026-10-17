set -eu
python3 - <<'PY'
from pathlib import Path
import os,json,re
rows=[]
for p in Path('/proc').iterdir():
    if not p.name.isdecimal():continue
    try:
        if os.readlink(p/'exe')!='/home/ideck/.local/share/Steam/steamrtarm64/steamwebhelper':continue
        raw=(p/'cmdline').read_bytes()
        rows.append({'pid':int(p.name),'bytes':len(raw),'nul_count':raw.count(b'\0'),'roles':[s.decode(errors='replace') for s in re.findall(rb'--(?:type|utility-sub-type|service-sandbox-type)=[a-zA-Z0-9_.-]+',raw)]})
    except (FileNotFoundError,ProcessLookupError):pass
out=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-gamepadui-v14')
p=out/'delta-webhelper.txt'
lines=p.read_text(errors='replace').splitlines() if p.exists() else []
print('ROLE_PROBE='+json.dumps({'processes':rows,'renderer_spawn_count':sum('--type=renderer' in s for s in lines),'restart_lines':sum('Restart' in s for s in lines)}))
PY
