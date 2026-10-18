set -eu
python3 - <<'PY'
from pathlib import Path
import os,json
out=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-desktop-zero-watchdog-v22')
rows=[]
for p in Path('/proc').iterdir():
 if not p.name.isdecimal():continue
 try:
  exe=os.readlink(p/'exe')
  if exe not in ('/home/ideck/.local/share/Steam/steamrtarm64/steam','/home/ideck/.local/share/Steam/steamrtarm64/steamwebhelper'):continue
  status=dict(x.split(':',1) for x in (p/'status').read_text().splitlines() if ':' in x)
  if status['Uid'].split()!=['1000']*4:continue
  args=(p/'cmdline').read_bytes().split(b'\0')
  rows.append({'pid':int(p.name),'executable':Path(exe).name,'cpus_allowed':status['Cpus_allowed_list'].strip(),'seccomp':status['Seccomp'].strip(),'native_watchdog_flag':b'-cef-disable-hang-timeouts' in args,'native_force_sandbox_flag':b'-cef-force-sandbox' in args,'browser_hang_argument_names':[x.decode(errors='replace').split('=',1)[0] for x in args if b'hang' in x.lower() and x.startswith(b'-')]})
 except (OSError,KeyError):pass
assert any(x['executable']=='steam' and x['native_watchdog_flag'] and x['native_force_sandbox_flag'] for x in rows)
r={'processes':rows,'native_ipc_deadline_ms':500,'outer_monitor_seconds':1500,'hang_flag_is_not_ui_acceptance':True}
(out/'watchdog-proof.json').write_text(json.dumps(r,indent=2)+'\n');print('WATCHDOG_PROOF='+json.dumps(r))
PY
