set -eu
python3 - <<'PY'
from pathlib import Path
import os,json
root='/home/ideck/.local/share/Steam/steamrtarm64/'
rows=[]
for p in Path('/proc').iterdir():
    if not p.name.isdecimal():continue
    try:
        exe=os.readlink(p/'exe')
        if exe not in (root+'steam',root+'steamwebhelper'):continue
        args=(p/'cmdline').read_bytes().split(b'\0')
        fields=dict(s.split(':',1) for s in (p/'status').read_text().splitlines() if ':' in s)
        rows.append({'pid':int(p.name),'comm':(p/'comm').read_text().strip(),'renderer':b'--type=renderer' in args,'state':fields['State'].strip(),'uid':fields['Uid'].split(),'rss':fields.get('VmRSS','').strip(),'seccomp':fields['Seccomp'].strip()})
    except (FileNotFoundError,ProcessLookupError):pass
print('INVENTORY='+json.dumps(rows))
PY
