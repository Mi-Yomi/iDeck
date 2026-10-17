set -eu
python3 - <<'PY'
from pathlib import Path
import subprocess,json,time,os
out=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-connect-5000-v9')
r={'time_ns':time.time_ns(),'processes':[],'shm_free':os.statvfs('/dev/shm').f_bavail*os.statvfs('/dev/shm').f_frsize}
for p in Path('/proc').iterdir():
 if not p.name.isdecimal():continue
 try:
  exe=os.readlink(p/'exe')
  if not exe.startswith('/home/ideck/.local/share/Steam/'):continue
  d=dict(x.split(':',1) for x in (p/'status').read_text().splitlines() if ':' in x)
  r['processes'].append({'pid':int(p.name),'exe':exe,'state':d['State'].strip(),'tracer':int(d['TracerPid']),'seccomp':d['Seccomp'].strip(),'rss':d.get('VmRSS','').strip(),'stat':(p/'stat').read_text()})
 except (FileNotFoundError,ProcessLookupError):pass
(out/'ui-health.json').write_text(json.dumps(r,indent=2)+'\n');print('HEALTH='+json.dumps(r),flush=True)
for n in ('webhelper.txt','steamui_html.txt','cef_log.txt'):
 p=Path('/home/ideck/.local/share/Steam/logs')/n
 if p.exists():print('PRIVATE_UI='+n+'\n'+'\n'.join(p.read_text(errors='replace').splitlines()[-30:]))
print(subprocess.check_output(['xdotool','getactivewindow','getwindowname'],text=True,timeout=5))
PY
