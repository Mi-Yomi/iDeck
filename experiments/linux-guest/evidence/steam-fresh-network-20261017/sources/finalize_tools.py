import json, os, subprocess, sys
from pathlib import Path
ROOT=Path('/workspace/iDeck/experiments/linux-guest')
TASK=Path('/workspace/steam-fresh-20261017')
sys.path.insert(0,str(ROOT/'tools'))
import debian_rootfs as base
import gui_host_tools
lock=json.loads((ROOT/'ipa/gui-inputs.lock.json').read_text())
stage=json.loads((TASK/'probes/inputs-before-staging.json').read_text())
pins=lock['host_packages']+stage['additional_host_packages']
for pin in pins:
    p=TASK/'debian-cache/debs'/Path(pin['filename']).name
    assert p.stat().st_size==pin['size'] and base.sha256(p)==pin['sha256']
deps=json.loads((ROOT/'ipa/steam-dependencies.lock.json').read_text())
for pin in deps['extra_packages']:
    p=TASK/'deps-cache/debs'/Path(pin['filename']).name
    assert p.stat().st_size==pin['size'] and base.sha256(p)==pin['sha256']
host=TASK/'host'; versions={}
for name,args in [('qemu-system-aarch64',['--version']),('qemu-img',['--version']),('unsquashfs',['-version']),('e2fsck',['-V'])]:
    binary=host/('usr/sbin' if name=='e2fsck' else 'usr/bin')/name
    r=subprocess.run(gui_host_tools.command(host,[binary,*args]),capture_output=True,text=True,
                     env={'PATH':os.defpath,'LC_ALL':'C'})
    if name=='unsquashfs':
        assert r.returncode==1 and r.stdout.startswith('unsquashfs version 4.6.1') and not r.stderr
    else:assert r.returncode==0
    versions[name]={'sha256':base.sha256(binary),'exit_code':r.returncode,'version':(r.stdout+r.stderr).strip()}
def save(name,value):(TASK/'probes'/name).write_text(json.dumps(value,indent=2)+'\n')
save('host-tools.json',{'lock_sha256':base.sha256(ROOT/'ipa/gui-inputs.lock.json'),
    'authenticated_release':lock['release'],'host_packages':pins,'versions':versions,
    'system_install':False,'staging_only':True,'unsquashfs_version_exit_one_observed':True})
save('qemu-img-receipt.json',{'binary_sha256':versions['qemu-img']['sha256'],
    'package':next(p for p in pins if p['name']=='qemu-utils'),
    'authenticated_index':lock['release']['indexes'][1],
    'loader_sha256':base.sha256(host/'usr/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2'),
    'closure_receipt_sha256':base.sha256(TASK/'probes/host-tools.json'),'system_install':False})
save('dependency-cache.json',{'packages_verified':45,'download_bytes':sum(p['size'] for p in deps['extra_packages']),
    'installed':False,'dpkg_audit':'NOT RUN'})
wrapper=TASK/'unsquashfs'
wrapper.write_text('#!/bin/sh\nexec '+str(host/'usr/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2')+
    ' --library-path '+str(host/'usr/lib/x86_64-linux-gnu')+' '+str(host/'usr/bin/unsquashfs')+' "$@"\n')
wrapper.chmod(0o700)
print(json.dumps({'host_packages_verified':len(pins),'dependency_cache_verified':45,
    'qemu_img_sha256':versions['qemu-img']['sha256']},indent=2))
