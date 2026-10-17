from pathlib import Path
import json,os
root=Path(__file__).resolve().parent
prefix='resume-local-20261017-guarded-v2__'
base=root/'guest-evidence-v2'
modules=json.loads((base/(prefix+'module-identities.json')).read_text())
inventory=json.loads((base/(prefix+'thread-inventory.json')).read_text())
snapshot=json.loads((base/(prefix+'address-snapshot.json')).read_text())
processes={p['pid']:p for p in inventory['processes']}
def resolve(value,pid):
    result=dict(value)
    if 'file_offset' not in value:return result
    record=modules.get(Path(value.get('module','')).name)
    if not record:return {**result,'resolution':'module metadata not captured'}
    address=int(value['address'],16);offset=int(value['file_offset'],16)
    matching=[]
    for line in processes[pid]['maps'].splitlines():
        fields=line.split(None,5);lo,hi=(int(x,16) for x in fields[0].split('-'))
        if not lo<=address<hi:continue
        major,minor=(int(x,16) for x in fields[3].split(':'))
        if os.makedev(major,minor)!=record['device'] or int(fields[4])!=record['inode']:raise RuntimeError('mapped inode differs from verified ELF')
        if fields[5]!=record['path']:raise RuntimeError('mapped path differs from verified ELF')
        matching.append(line)
    if len(matching)!=1:raise RuntimeError('unique address mapping required')
    loads=[s for s in record['pt_load'] if s['offset']<=offset<s['offset']+s['filesz']]
    if len(loads)!=1:raise RuntimeError('unique file-backed PT_LOAD required')
    segment=loads[0];va=segment['vaddr']+offset-segment['offset']
    result.update(elf_va=hex(va),elf_sha256=record['sha256'],inode_verified=True,pt_load=segment)
    if Path(record['path']).name=='chromehtml.so':
        for start,end,name in ((0x5b078,0x5b524,'Chrome IPC connect/response validation'),(0x480b8,0x48138,'controller pump'),(0x4ea10,0x4ea20,'controller readiness predicate'),(0x5ac78,0x5aca0,'IPC disconnect/reset'),(0x53228,0x532b0,'AF_UNIX shared-memory channel connect')):
            if start<=va<end:result['previously_verified_static_region']=name
    return result
rows=[]
for t in snapshot['threads']:
    row={'tid':t['tid'],'tgid':t['tgid'],'status':t['status'],'detached':t['detached'],'state_after':t.get('state_after'),'frames':[]}
    if 'snapshot' in t:
        row['registers']={key:resolve(value,t['tgid']) for key,value in t['snapshot']['registers'].items()}
        row['unwind_stop']=t['snapshot']['unwind_stop']
        row['frames']=[resolve(f['return'],t['tgid']) for f in t['snapshot']['frames']]
    rows.append(row)
result={'snapshot_status':snapshot['status'],'method':'verified mapped dev/inode, actual ELF PT_LOAD VA translation; no guessed PAC stripping','threads':rows}
(root/'resolved-address-snapshot.json').write_text(json.dumps(result,indent=2)+'\n')
for t in rows:
    print('TID',t['tid'],t['status'],'detached',t['detached'],'after',t.get('state_after'))
    for label,value in [*t.get('registers',{}).items(),*[(str(i),f) for i,f in enumerate(t['frames'])]]:
        if label in ('fp','sp'):continue
        print(label,Path(value.get('module','?')).name,value.get('elf_va',value['address']),value.get('previously_verified_static_region',''))