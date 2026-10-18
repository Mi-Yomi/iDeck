set -eu
python3 - <<'PY'
from pathlib import Path
import json
out=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-desktop-zero-v20')
rows=[];bad=0
for f in Path('/run/user/1000').glob('ideck-shm-zero-*.jsonl'):
 assert f.stat().st_size<65536
 for line in f.read_text().splitlines():
  try:rows.append(json.loads(line))
  except json.JSONDecodeError:bad+=1
r={'ready':sum(x['event']=='ready' for x in rows),'zero_calls':sum(x['event']=='stream_zero' for x in rows),'lazy_zero_calls':sum(x.get('already_zero') is True for x in rows),'ordinary_fallback_calls':sum(x['event']=='stream_zero' and not x.get('already_zero') for x in rows),'invalid_log_lines':bad,'events':rows}
(out/'zero-events-snapshot.json').write_text(json.dumps(r,indent=2)+'\n')
print('ZERO_EVENTS='+json.dumps(r))
PY