import hashlib,json,lzma,pathlib,sys,tarfile,urllib.parse
root=pathlib.Path('/workspace/iDeck/experiments/linux-guest');sys.path.insert(0,str(root/'tools'))
import debian_rootfs as b
b.OFFLINE=True
p=pathlib.Path('/workspace/steam-fresh-20261017/network-readonly-20261017')
release=pathlib.Path('/workspace/steam-fresh-20261017/debian-cache/metadata/InRelease')
lock=json.loads((root/'ipa/gui-inputs.lock.json').read_text())
assert release.stat().st_size==lock['release']['size'] and b.sha256(release)==lock['release']['sha256']
fields,signers=b.verify_release(release)
match=[x.split() for x in fields['SHA256'].splitlines() if x.split() and x.split()[-1]=='main/source/Sources.xz'];assert len(match)==1
digest,size,_=match[0];desc={'size':int(size),'sha256':digest,'url':b.BASE+'dists/trixie/main/source/by-hash/SHA256/'+digest}
xz=b.fetch(desc['url'],p/'Sources.xz',desc['size'],desc['sha256'])
record=None;paragraph=[];count=0
with lzma.open(xz,'rt') as f:
 for line in f:
  count+=len(line)
  assert count<256*1024**2
  if line.strip():paragraph.append(line)
  else:
   if paragraph and paragraph[0].startswith('Package: libslirp\n'):
    candidate=next(b.paragraphs(''.join(paragraph)))
    if candidate['Version']=='4.8.0-1+deb13u1':record=candidate;break
   paragraph=[]
assert record is not None and 'libslirp0' in record['Binary']
files=[]
for line in record['Checksums-Sha256'].splitlines():
 if not line.strip():continue
 sha,n,name=line.split();url=b.BASE+record['Directory']+'/'+name
 dest=b.fetch(url,p/name,int(n),sha)
 files.append({'file':name,'size':int(n),'sha256':sha,'url':url})
source=p/'libslirp-source-replay';source.mkdir(exist_ok=False)
for pin in files:
 if '.tar.' in pin['file']:
  with tarfile.open(p/pin['file']) as t:
   for m in t.getmembers():
    if m.isfile() and m.size<1024**2 and (m.name.endswith(('src/slirp.c','src/udp.c','src/socket.c','src/ip_input.c','src/libslirp.h','src/slirp.h','src/tcp_subr.c')) or m.name.startswith('debian/patches/')):
     dest=source/pathlib.PurePosixPath(m.name).name
     assert not dest.exists();dest.write_bytes(t.extractfile(m).read())
r={'authenticated_release_sha256':b.sha256(release),'signers':signers,'source_index':desc,'package':record['Package'],'version':record['Version'],'binary_packages':record['Binary'],'files':files,'read_source_files':[{ 'file':f.name,'size':f.stat().st_size,'sha256':b.sha256(f)} for f in sorted(source.iterdir())],'settings_changed':False}
(p/'pinned-slirp-source.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
