set -eu
python3 - <<'PY'
from pathlib import Path
import json,os,struct
out=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-guarded-v2')
p=Path('/tmp/dumps/assert_20261017181345_5.dmp')
with p.open('rb') as f:
    header=f.read(32);count,directory=struct.unpack_from('<II',header,8)
    if count>128:raise RuntimeError('directory bound')
    comments=[]
    for n in range(count):
        f.seek(directory+12*n);kind,size,rva=struct.unpack('<III',f.read(12))
        if kind==10:
            if size>4096 or rva+size>p.stat().st_size:raise RuntimeError('comment size bound')
            f.seek(rva);comments.append(f.read(size).decode(errors='replace').rstrip('\0'))
result={'software_assertion_comments':comments,'full_dump_hashed_but_only_selected_metadata_and_frame_addresses_decoded':True,'environment_stream_decoded':False}
(out/'assertion-comments.json').write_text(json.dumps(result,indent=2)+'\n')
print('IDECK_ASSERTION_COMMENTS='+json.dumps(result),flush=True)
PY