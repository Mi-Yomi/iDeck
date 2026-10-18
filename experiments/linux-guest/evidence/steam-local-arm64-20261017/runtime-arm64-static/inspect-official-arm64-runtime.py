from pathlib import Path,PurePosixPath
import hashlib,json,os,posixpath,tarfile,time,urllib.request
t=Path(__file__).parent;out=t/'runtime-arm64-static-20261018';out.mkdir(exist_ok=False)
base='https://repo.steampowered.com/steamrt3c/images/3c.0.20260824.257593/'
name='steam-runtime-steamrt-arm64.tar.xz'
def fetch(filename,limit):
    target=out/filename;start=time.monotonic();h=hashlib.sha256();size=0
    with urllib.request.urlopen(base+filename,timeout=30) as response,target.open('xb') as f:
        assert response.geturl().startswith(base),'unexpected redirect'
        while chunk:=response.read(1024*1024):
            size+=len(chunk);assert size<=limit and time.monotonic()-start<180
            f.write(chunk);h.update(chunk)
    return {'url':base+filename,'size':size,'sha256':h.hexdigest()}
checks=fetch('SHA256SUMS',1024**2)
matches=[line.split()[0] for line in (out/'SHA256SUMS').read_text().splitlines() if line.split()[-1].lstrip('*')==name]
assert len(matches)==1 and len(matches[0])==64
archive=fetch(name,96*1024**2);assert archive['sha256']==matches[0],'checksum mismatch'
def normalize(path):
    value=posixpath.normpath(path)
    assert not value.startswith('/') and value!='..' and not value.startswith('../')
    return value
assert normalize('./a/b')=='a/b'
for bad in ('../escape','/absolute','a/../../escape'):
    try:normalize(bad)
    except AssertionError:pass
    else:raise AssertionError('unsafe path accepted')
rows=[]
with tarfile.open(out/name,'r:xz') as tar:
    members={};size=0
    for member in tar:
        key=normalize(member.name);assert key not in members
        members[key]=member;size+=member.size
        assert len(members)<=100000 and size<=2*1024**3,'archive inspection budget'
    def resolve(key):
        seen=set()
        for _ in range(20):
            assert key not in seen;seen.add(key);m=members[key]
            if m.isfile():return key,m
            assert m.issym() or m.islnk()
            key=normalize(posixpath.join(posixpath.dirname(key),m.linkname) if m.issym() else m.linkname)
        raise AssertionError('link depth')
    for key,m in members.items():
        if PurePosixPath(key).name not in ('steam-runtime-launcher-service','steam-runtime-launcher-interface-0','srt-bwrap','pressure-vessel-wrap','pv-adverb','_v2-entry-point','VERSIONS.txt'):continue
        row={'path':key,'kind':'regular' if m.isfile() else 'link'}
        try:
            resolved,target=resolve(key);assert target.size<=8*1024**2
            with tar.extractfile(target) as f:data=f.read(target.size+1)
            assert len(data)==target.size
            row.update(resolved=resolved,size=len(data),sha256=hashlib.sha256(data).hexdigest(),elf_machine=int.from_bytes(data[18:20],'little') if data[:5]==b'\x7fELF\x02' and data[5]==1 else None)
        except (KeyError,AssertionError) as error:row['not_resolved']=type(error).__name__
        rows.append(row)
receipt={'source':'official Valve HTTPS repository; digest compared with SHA256SUMS from same origin, not a detached signature','build':'3c.0.20260824.257593','checksum_document':checks,'archive':archive,'checksum_matches':True,'members':len(members),'declared_uncompressed_bytes':size,'selected_files':rows,'installed':False,'executed':False,'guest_modified':False,'iphone_tested':False,'compatibility_with_current_client':'unverified; its bundled x86 runtime reports3c.0.20261007.263964'}
(out/'inspection.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2),flush=True)
