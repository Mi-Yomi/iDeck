set -eu
python3 - <<'PY'
from pathlib import Path
import json,hashlib,os,stat
root=Path('/home/ideck/.local/share/Steam')
names={'steam-runtime-launcher-service','steam-runtime-launcher-interface-0','_v2-entry-point','steamwebhelper.sh','run.sh'}
rows=[]
for base in ('steamrtarm64','steamrt64','ubuntu12_64'):
    directory=root/base
    if not directory.is_dir():continue
    for parent,dirs,files in os.walk(directory,followlinks=False):
        for name in files:
            if name not in names:continue
            p=Path(parent)/name;s=p.lstat()
            row={'path':str(p.relative_to(root)),'bytes':s.st_size,'regular':stat.S_ISREG(s.st_mode),'executable':bool(s.st_mode&0o111)}
            if row['regular'] and s.st_size<8*1024**2:
                b=p.read_bytes();row['sha256']=hashlib.sha256(b).hexdigest()
                row['elf_machine']=int.from_bytes(b[18:20],'little') if b[:4]==b'\x7fELF' else None
                if name=='steamwebhelper.sh':
                    row['runtime_lines']=[line for line in b.decode(errors='replace').splitlines() if any(s in line for s in ('STEAM_RUNTIME','steamrt','launcher-service','arm64','LD_LIBRARY_PATH'))]
            rows.append(row)
out=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-gamepadui-v14')
(out/'runtime-service-files.json').write_text(json.dumps(rows,indent=2)+'\n')
print('RUNTIME_SERVICE_FILES='+json.dumps(rows))
PY
