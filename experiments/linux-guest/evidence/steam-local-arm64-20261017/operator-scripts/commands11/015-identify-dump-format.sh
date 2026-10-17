set -eu
python3 - <<'PY'
from pathlib import Path
import json,struct
p=Path('/tmp/dumps/assert_20261017181345_5.dmp')
with p.open('rb') as f:b=f.read(32)
print('IDECK_DUMP_HEADER='+json.dumps({'size':p.stat().st_size,'header_hex':b.hex(),'header_words_le':list(struct.unpack('<8I',b))}),flush=True)
PY