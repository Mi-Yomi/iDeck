import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.parse

ROOT = Path('/workspace/iDeck/experiments/linux-guest')
TASK = Path('/workspace/steam-fresh-20261017')
sys.path.insert(0, str(ROOT/'tools'))
import debian_rootfs as base
import gui_rootfs
import gui_host_tools
import steam_vm

def save(name, value):
    (TASK/'probes'/name).write_text(json.dumps(value, indent=2)+'\n')

lock = json.loads((ROOT/'ipa/gui-inputs.lock.json').read_text())
cache = TASK/'debian-cache'
metadata = cache/'metadata'
print('Authenticating signed pinned Debian indexes and APT closures', flush=True)
gui_rootfs.authenticate(lock, metadata)
amd, plain = base.load_index(metadata, lock['release']['indexes'][1])
known = {p['name']:p for p in lock['host_packages']}
extra = []
for package in ('qemu-utils', 'squashfs-tools'):
    for pin in base.resolve(amd, plain, [package], metadata, architecture='amd64'):
        if pin['name'] in known:
            if known[pin['name']] != pin:
                raise ValueError('Host dependency pin conflict')
        else:
            known[pin['name']] = pin
            extra.append(pin)
qpin = known['qemu-utils']
assert qpin['sha256'] == '6d31339b1630153fe7c5f8a51426b8fa6ce35731aeb015a84f2d333c4e4dca30'
deps = json.loads((ROOT/'ipa/steam-dependencies.lock.json').read_text())
assert deps['gui_inputs_sha256'] == base.sha256(ROOT/'ipa/gui-inputs.lock.json')
assert deps['release'] == lock['release']
arm, _ = base.load_index(metadata, lock['release']['indexes'][0])
indexed = {r['Filename']:base.package_pin(r) for r in arm if 'Filename' in r}
assert all(indexed.get(p['filename']) == p for p in deps['extra_packages'])
free = shutil.disk_usage(TASK).free
pins = list(known.values()) + deps['extra_packages']
budget = sum(p['size']+p['installed_size_kib']*1024 for p in pins)
if free < budget+16*1024**3:
    raise ValueError('Insufficient staging space and Steam entry reserve')
save('inputs-before-staging.json', {'free_bytes':free,'staging_download_and_declared_install_bytes':budget,
    'host_package_count':len(known),'additional_host_packages':extra,'guest_extra_packages':45,
    'storage_preflight':steam_vm.storage_preflight(TASK,json.loads((ROOT/'profiles/steam-host-experiment.json').read_text()))})
host = TASK/'host'
host.mkdir(exist_ok=False)
for n,pin in enumerate(known.values(),1):
    path=cache/'debs'/Path(pin['filename']).name
    base.fetch(base.BASE+urllib.parse.quote(pin['filename'],safe='/+'),path,pin['size'],pin['sha256'])
    subprocess.run(['dpkg-deb','-x',str(path),str(host)],check=True,capture_output=True)
    if n%10==0:print(f'Authenticated/extracted host packages {n}/{len(known)}',flush=True)
for n,pin in enumerate(deps['extra_packages'],1):
    path=TASK/'deps-cache/debs'/Path(pin['filename']).name
    base.fetch(base.BASE+urllib.parse.quote(pin['filename'],safe='/+'),path,pin['size'],pin['sha256'])
    if n%10==0:print(f'Authenticated guest dependency cache {n}/45',flush=True)
versions={}
for name,args in [('qemu-system-aarch64',['--version']),('qemu-img',['--version']),('unsquashfs',['-version']),('e2fsck',['-V'])]:
    binary=host/('usr/sbin' if name=='e2fsck' else 'usr/bin')/name
    cmd=gui_host_tools.command(host,[binary,*args])
    r=subprocess.run(cmd,capture_output=True,text=True,env={'PATH':os.defpath,'LC_ALL':'C'})
    if r.returncode:raise RuntimeError(name+' version probe failed')
    versions[name]={'sha256':base.sha256(binary),'exit_code':r.returncode,'version':(r.stdout+r.stderr).strip()}
save('host-tools.json', {'lock_sha256':base.sha256(ROOT/'ipa/gui-inputs.lock.json'),
    'authenticated_release':lock['release'],'host_packages':list(known.values()),'versions':versions,
    'system_install':False,'staging_only':True})
save('qemu-img-receipt.json', {'binary_sha256':versions['qemu-img']['sha256'],
    'package':qpin,'authenticated_index':lock['release']['indexes'][1],
    'loader_sha256':base.sha256(host/'usr/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2'),
    'closure_receipt_sha256':base.sha256(TASK/'probes/host-tools.json'),'system_install':False})
save('dependency-cache.json', {'packages_verified':45,'download_bytes':sum(p['size'] for p in deps['extra_packages']),
    'installed':False,'dpkg_audit':'NOT RUN'})
print('All pinned host tools and 45 dependency packages authenticated; no guest install yet',flush=True)
