from pathlib import Path
import json,hashlib
base=Path(__file__).resolve().parent;folder=base/'guest-evidence-post-pause';rows=[]
for pid,address in ((2192,0xffff196937a8),(2316,0xffff7fc907a8)):
    group=2192 if pid==2192 else 2295
    for phase in ('before','after'):
        p=folder/f'post-pause-trace__{phase}-{group}.maps'
        for line in p.read_text().splitlines():
            f=line.split(None,5);lo,hi=(int(x,16) for x in f[0].split('-'))
            if lo<=address<hi:
                rows.append({'tid':pid,'phase':phase,'address':hex(address),'mapping_line':line,'device':f[3],'inode':int(f[4]),'file_offset':hex(address-lo+int(f[2],16)),'maps_sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
result={'kind':'address/map metadata only; paused instrumented interval','mappings':rows,'same_backing_and_offset':len(rows)==4 and len({(r['device'],r['inode'],r['file_offset']) for r in rows})==1,'baseline_cause_proven':False}
(base/'post-pause-wait-mapping.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))