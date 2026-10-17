set -eu
python3 - <<'PY'
import subprocess,json
for argv in (['xwininfo','-root','-tree'],['xdotool','getactivewindow','getwindowname']):
 try:
  r=subprocess.run(argv,capture_output=True,text=True,timeout=5)
  text=r.stdout
  if argv[0]=='xwininfo':text='\n'.join(line for line in text.splitlines() if any(s in line.lower() for s in ('steam','sharedjs','login','root window')))
  print('WINDOWS='+json.dumps({'argv':argv,'exit':r.returncode,'stdout':text,'stderr':r.stderr}))
 except subprocess.TimeoutExpired:print('WINDOWS_TIMEOUT')
PY
