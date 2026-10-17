import io,os,sys,json,hashlib,tarfile,shutil,urllib.parse,ast
from pathlib import Path,PurePosixPath
base=Path(__file__).resolve().parent;top=base.parent;sys.path.insert(0,str(top/'source/experiments/linux-guest/tools'))
import debian_rootfs as d
out=base/'private-cross-v5';out.mkdir(exist_ok=False);meta=out/'metadata';meta.mkdir();cache=out/'debs';cache.mkdir();tree=out/'root';tree.mkdir()
for name in ('InRelease','Packages-amd64.xz'):shutil.copyfile(top/'deps-cache/metadata'/name,meta/name)
keyring=top/'prior-build/lab-long-provision/tree/usr/share/keyrings/debian-archive-keyring.gpg'
fields,signatures=d.verify_release(meta/'InRelease',keyring);descriptor=d.index_descriptor(fields,'amd64');records,plain=d.load_index(meta,descriptor)
failed=json.loads((base/'private-cross-v4/resolver-failure.json').read_text())
plan=failed['stdout'].split('The following additional packages will be installed:\n',1)[1].split('Suggested packages:',1)[0]
seeds=['gcc-14-aarch64-linux-gnu','libc6-dev-arm64-cross'];names=set(plan.split())|set(seeds);pins=[]
for name in sorted(names):
    candidates=[r for r in records if r.get('Package')==name and r.get('Architecture') in ('amd64','all')]
    assert len(candidates)==1,(name,len(candidates));pins.append(d.package_pin(candidates[0]))
assert all(p['architecture'] in ('amd64','all') for p in pins)
assert sum(p['size'] for p in pins)<256*1024**2 and sum(p['installed_size_kib']*1024 for p in pins)<1024**3
lock={'purpose':'private host-only ARM64 compiler; no host or guest installation','selection_method':'explicit package names from partial APT plan, one candidate/version each in signed index; successful APT solve is NOT claimed; runtime/link closure must be independently validated','release_sha256':d.sha256(meta/'InRelease'),'keyring_sha256':d.sha256(keyring),'signatures':signatures,'index':descriptor,'seeds':seeds,'packages':pins,'download_bytes':sum(p['size'] for p in pins)}
(out/'lock.json').write_text(json.dumps(lock,indent=2)+'\n');print('CROSS_LOCK='+json.dumps({'packages':len(pins),'bytes':lock['download_bytes']}),flush=True)
source=ast.parse((base/'prepare-private-cross.py').read_text());functions=ast.Module(body=[n for n in source.body if isinstance(n,ast.FunctionDef) and n.name in ('payload','extraction_filter')],type_ignores=[]);exec(compile(functions,'owned-safe-payload-extraction','exec'))
for p in pins:
    path=d.fetch(d.BASE+urllib.parse.quote(p['filename'],safe='/+'),cache/Path(p['filename']).name,p['size'],p['sha256'])
    with tarfile.open(fileobj=io.BytesIO(payload(path)),mode='r:*') as archive:
        members=archive.getmembers();assert sum(max(0,m.size) for m in members)<512*1024**2
        archive.extractall(tree,members=members,filter=extraction_filter)
    print('CROSS_EXTRACTED='+p['name'],flush=True)
receipt={'lock_sha256':d.sha256(out/'lock.json'),'source_script_sha256':d.sha256(Path(__file__)),'system_install':False,'package_count':len(pins),'root':str(tree),'compiler_runtime_validated':False}
(out/'extraction.json').write_text(json.dumps(receipt,indent=2)+'\n');print('CROSS_DONE='+json.dumps(receipt),flush=True)