set -eu
python3 - <<'PY'
from pathlib import Path
import subprocess,json,os,time
out=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-connect-5000-v9');rows=[]
for p in Path('/proc').iterdir():
 if not p.name.isdecimal():continue
 try:
  exe=os.readlink(p/'exe')
  if exe not in ('/home/ideck/.local/share/Steam/steamrtarm64/steam','/home/ideck/.local/share/Steam/steamrtarm64/steamwebhelper'):continue
  argv=(p/'cmdline').read_bytes().split(b'\0');flags=[a.decode(errors='replace') for a in argv if a.startswith((b'--type=',b'--disable-gpu',b'--use-gl=',b'--use-angle=',b'--in-process-gpu',b'--no-sandbox',b'-cef-'))]
  rows.append({'pid':int(p.name),'exe_leaf':Path(exe).name,'selected_graphics_flags':flags,'v3_interposer_mapped':'/opt/ideck-ipc-probe-v3/libideck-ipc-connect.so' in (p/'maps').read_text()})
 except FileNotFoundError:continue
r={'time_ns':time.time_ns(),'processes':rows};(out/'preload-and-graphics.json').write_text(json.dumps(r,indent=2)+'\n');print('PROFILE='+json.dumps(r),flush=True)
w=subprocess.run(['xwininfo','-root','-tree'],capture_output=True,text=True,timeout=5);print('WINDOWS='+'\n'.join(x for x in w.stdout.splitlines() if 'Steam' in x or 'Special Offers' in x))
PY
