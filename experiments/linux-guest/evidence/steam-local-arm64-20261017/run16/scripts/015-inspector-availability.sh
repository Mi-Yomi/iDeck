set -eu
python3 - <<'PY'
from pathlib import Path
import subprocess,json,time
out=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-connect-5000-v9')
def get(args):return subprocess.check_output(['xdotool',*args],text=True,timeout=5).strip()
main='0x1c00051';friend='0x1c00057';assert get(['getwindowname',main])=='Steam';assert get(['getwindowname',friend])=='Friends List'
subprocess.run(['xdotool','windowminimize',friend],check=True,timeout=5);subprocess.run(['xdotool','windowactivate',main],check=True,timeout=5);time.sleep(1)
assert get(['getactivewindow','getwindowname'])=='Steam'
subprocess.run(['xdotool','key','ctrl+shift+i'],check=True,timeout=5);time.sleep(3)
args=Path('/proc/933/cmdline').read_bytes().split(b'\0');flags=[a.decode() for a in args if a.startswith(b'--remote-debugging')]
r={'time_ns':time.time_ns(),'action':'request built-in inspector with XTest Ctrl+Shift+I on verified Steam main window','debug_flags':flags,'active_after':get(['getactivewindow','getwindowname'])};(out/'inspector-request.json').write_text(json.dumps(r,indent=2)+'\n');print('INSPECTOR='+json.dumps(r),flush=True)
w=subprocess.run(['xwininfo','-root','-tree'],capture_output=True,text=True,timeout=5);print('WINDOWS='+'\n'.join(x for x in w.stdout.splitlines() if any(t in x for t in ('Steam','DevTools','Friends','Inspect'))))
PY
