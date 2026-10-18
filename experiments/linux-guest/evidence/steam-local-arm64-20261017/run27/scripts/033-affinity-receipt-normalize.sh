set -eu
python3 - <<'PY'
from pathlib import Path
import json
out=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-desktop-zero-watchdog-v22')
p=out/'affinity-phase27.json'
s=p.read_text()
normalized=s.endswith(chr(92)+'n')
if normalized:s=s[:-2]+chr(10)
row=json.loads(s)
if normalized:p.write_text(json.dumps(row,indent=2)+chr(10))
changed=[t for e in row['events'] for t in e.get('threads',[])]
print('AFFINITY_SUMMARY='+json.dumps({'owned_processes':len(row['owned_pids']),'changed_threads':len(changed),'original_guards_preserved':row['original_guards_and_deadlines_unchanged'],'signals_sent':row['signals_sent'],'own_receipt_newline_normalized':normalized}))
PY
