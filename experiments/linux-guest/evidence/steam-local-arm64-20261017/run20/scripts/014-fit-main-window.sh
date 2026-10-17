set -eu
python3 - <<'PY'
import subprocess,json
# Exact windows observed in command013; require unchanged window names before input.
for window,name in [('0x200003b','Steam'),('0x2000041','Friends List')]:
 result=subprocess.run(['xdotool','getwindowname',window],capture_output=True,text=True,timeout=5)
 assert result.returncode==0 and result.stdout.strip()==name
for args in [['windowminimize','0x2000041'],['windowsize','0x200003b','800','600'],['windowmove','0x200003b','0','0'],['windowactivate','0x200003b']]:
 result=subprocess.run(['xdotool']+args,capture_output=True,text=True,timeout=5)
 assert result.returncode==0, result.stderr
print('WINDOW_FIT='+json.dumps({'steam_window':'0x200003b','width':800,'height':600,'friends_minimized':True,'main_activated':True}))
PY
