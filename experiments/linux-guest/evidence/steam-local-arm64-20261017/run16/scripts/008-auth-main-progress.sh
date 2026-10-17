set -eu
python3 - <<'PY'
from pathlib import Path
import json,re,time
out=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-connect-5000-v9')
p=out/'delta-connection_log.txt';s=p.read_text(errors='replace') if p.exists() else ''
rows=[x for x in s.splitlines() if 'RecvMsgClientLogOnResponse()' in x and "'OK'" in x]
r={'time_ns':time.time_ns(),'post_boot_authentication_ok_seen':bool(rows),'latest_ok_timestamp':re.match(r'\[([^]]+)\]',rows[-1]).group(1) if rows else None,'no_account_input_issued_in_run16':True,'raw_account_identifiers_included':False}
(out/'auth-state.json').write_text(json.dumps(r,indent=2)+'\n');print('AUTH_STATE='+json.dumps(r))
for name in ('steamui_html.txt','webhelper.txt'):
 p=out/('delta-'+name)
 if p.exists():print('UI_LOG='+name+'\n'+'\n'.join(p.read_text(errors='replace').splitlines()[-15:]))
PY
