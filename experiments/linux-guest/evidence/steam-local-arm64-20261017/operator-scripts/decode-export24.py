import base64,gzip,hashlib,json,re,sys
from pathlib import Path
root=Path(__file__).resolve().parent
run=root/(sys.argv[1] if len(sys.argv)>1 else 'run10')
out=root/'guest-evidence-post-pause'
out.mkdir(exist_ok=True)
records=[]
for path in sorted(run.glob('024-*.log')):
    if not re.match(r'^[0-9]{3}-',path.name):continue
    for line in path.read_text(errors='replace').splitlines():
        if not line.startswith('IDECK_BLOB='):continue
        name,encoded=line[len('IDECK_BLOB='):].split(':',1)
        if not re.fullmatch(r'[a-zA-Z0-9_.+-]+(?:__[a-zA-Z0-9_.+-]+)*',name):raise ValueError('unsafe blob name')
        raw=gzip.decompress(base64.b64decode(encoded,validate=True))
        if len(raw)>16*1024**2:raise ValueError('blob size bound')
        target=out/name
        if target.exists():
            if target.is_symlink() or target.read_bytes()!=raw:raise ValueError('export conflict')
        else:
            with target.open('xb') as f:f.write(raw)
        records.append({'file':target.name,'size':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'source_log':path.name})
(root/'export-receipt-post-pause.json').write_text(json.dumps(records,indent=2)+'\n')
print(json.dumps({'files':len(records),'directory':str(out)}))