#!/usr/bin/env python3
"""Create a GUI payload/lock ONLY after real matching-kernel VM acceptance.

Writes a new output directory, never publishes/uploads or edits a committed
lock. Large artifacts stay outside git. The lock is a reviewable trust root.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import tarfile

import debian_rootfs as base
import gui_bundle as bundle

ROOT=Path(__file__).resolve().parents[1]


def read_json(path,limit=128*1024):
    if path.is_symlink() or not path.is_file() or path.stat().st_size>limit:raise ValueError('invalid receipt')
    return json.loads(path.read_text())


def seal(seed,bootstrap,acceptance,modules,output):
    gate=read_json(acceptance/'acceptance.json');info=read_json(seed/'gui-seed.json')
    package_lock=ROOT/'ipa/gui-inputs.lock.json'
    raw=seed/bundle.ROOTFS;compressed=seed/(bundle.ROOTFS+'.gz')
    if (gate.get('schema')!=1 or gate.get('kind')!='production-alpine-two-boots' or gate.get('status')!='pass'
            or gate.get('matching_kernel_gui') is not True or gate.get('two_boots_clean') is not True
            or gate.get('gui_package_lock_sha256')!=base.sha256(package_lock)
            or gate.get('runner_sha256')!=base.sha256(ROOT/'tools/gui_gate.py')
            or gate.get('bootstrap_receipt_sha256')!=base.sha256(bootstrap/'bootstrap.json')):
        raise ValueError('real matching-kernel GUI acceptance is absent/stale')
    boot_info=read_json(bootstrap/'bootstrap.json')
    for kind,name in [('rootfs',bundle.ROOTFS),('gzip',bundle.ROOTFS+'.gz')]:
        bundle.checked(seed/name,{k:info[kind][k] for k in ('size','sha256')})
    if (gate['rootfs_sha256']!=info['rootfs']['sha256'] or info['rootfs']['size']!=bundle.ROOTFS_SIZE
            or info.get('read_only_fsck') is not True):raise ValueError('acceptance covers a different seed')
    machine_id=None
    for name in ('boot1','boot2'):
        path=acceptance/name/'result.json';result=read_json(path)
        if base.sha256(path)!=gate['boot_reports'][name] or result.get('status')!='pass':raise ValueError('changed/failed real boot')
        if not all(result.get(k) is True for k in ('production_bootstrap','gui_mapped','emulated_pointer_move_resize',
                    'wheel_evdev_verified','real_root_menu_launch','keyboard_input_verified','clean_unmount','read_only_fsck')):raise ValueError('incomplete real GUI acceptance')
        if result.get('runner_sha256')!=base.sha256(ROOT/'tools/check_gui_vm.py'):raise ValueError('stale GUI runner')
        identity=result.get('machine_id_sha256')
        if not isinstance(identity,str) or len(identity)!=64 or (machine_id is not None and machine_id!=identity):
            raise ValueError('missing or inconsistent guest machine ID')
        machine_id=identity
        if (name=='boot1' and result.get('editor_typed_saved') is not True) or (name=='boot2' and
                (result.get('persistence_read_before_write') is not True or result.get('editor_reopened_after_boot') is not True)):
            raise ValueError('editor/persistence acceptance incomplete')
    for name in ('start','session','tint2rc','xorg.conf'):
        bundle.checked(ROOT/'guest/gui'/name,info.get('guest_files',{}).get(name,{}))
    for kind,name in [('kernel','vmlinuz-virt'),('initramfs','initramfs-desktop.gz')]:
        bundle.checked(bootstrap/name,boot_info[kind])
        if gate[kind+'_sha256']!=boot_info[kind]['sha256']:raise ValueError('different bootstrap acceptance')
    if gate['kernel_sha256']!=bundle.KERNEL_SHA256:raise ValueError('original kernel required')
    if base.sha256(modules/'manifest.json')!=boot_info['module_manifest_sha256']:raise ValueError('different modules')
    count=0;digest=hashlib.sha256()
    with gzip.open(compressed,'rb') as stream:
        while chunk:=stream.read(1024*1024):
            count+=len(chunk)
            if count>bundle.ROOTFS_SIZE:raise ValueError('gzip exceeds locked root size')
            digest.update(chunk)
    if count!=bundle.ROOTFS_SIZE or digest.hexdigest()!=info['rootfs']['sha256']:raise ValueError('gzip/raw mismatch')
    if shutil.disk_usage(output.parent).free<bundle.ROOTFS_SIZE+compressed.stat().st_size+512*1024**2:
        raise ValueError('insufficient payload preparation space')
    output.mkdir(parents=True,exist_ok=False);assets=output/'bundle';assets.mkdir()
    for name in ('vmlinuz-virt','initramfs-desktop.gz'):shutil.copyfile(bootstrap/name,assets/name)
    shutil.copyfile(raw,assets/bundle.ROOTFS)
    image={'size_bytes':bundle.ROOTFS_SIZE,**{k:info['image'][k] for k in ('uuid','block_size','features')}}
    profile={'schema':1,'mode':'desktop','control_port':'org.ideck.control','image':image,
             'kernel':{'file':'vmlinuz-virt',**bundle.metadata(assets/'vmlinuz-virt')},
             'initramfs':{'file':'initramfs-desktop.gz',**bundle.metadata(assets/'initramfs-desktop.gz')},
             'rootfs':{'file':bundle.ROOTFS,**bundle.metadata(raw)}}
    (assets/'desktop-profile.json').write_text(json.dumps(profile,sort_keys=True,indent=2)+'\n')
    (assets/'LICENSES-desktop.txt').write_bytes((ROOT/'guest/gui/LICENSES-desktop.txt').read_bytes())
    transport={name:assets/name for name in bundle.NAMES-{bundle.ROOTFS}}
    transport[bundle.ROOTFS+'.gz']=compressed
    archive=output/'ideck-debian-gui-v1.tar'
    with tarfile.open(archive,'w',format=tarfile.USTAR_FORMAT) as tar:
        for name,path in sorted(transport.items()):
            entry=tarfile.TarInfo(name);entry.size=path.stat().st_size;entry.mode=0o644
            with path.open('rb') as stream:tar.addfile(entry,stream)
    contract={k:gate[k] for k in ('kind','matching_kernel_gui','two_boots_clean','kernel_sha256','initramfs_sha256','rootfs_sha256')}
    contract['report_sha256']=base.sha256(acceptance/'acceptance.json')
    lock={'schema':1,'kind':'ideck-debian-gui','status':'ready','acceptance':contract,
          'files':{name:bundle.metadata(assets/name) for name in sorted(bundle.NAMES)},
          'transport_files':{name:bundle.metadata(path) for name,path in sorted(transport.items())},
          'payload':{'filename':archive.name,**bundle.metadata(archive)},
          'inputs':{'seed':{name:bundle.metadata(seed/name) for name in (bundle.ROOTFS,bundle.ROOTFS+'.gz')},
                    'modules':bundle.metadata(modules/'manifest.json'),
                    'guest':{name:bundle.metadata(ROOT/'guest/gui'/name) for name in
                             ('ideck-desktop-init','ideck-desktop-login','LICENSES-desktop.txt')}}}
    bundle.validate_lock(lock);bundle.verify(assets,lock)
    (output/'gui.lock.json').write_text(json.dumps(lock,indent=2)+'\n')
    # Small source inputs for an exact offline rebuild; keep the clean seed immutable.
    rebuild=output/'rebuild-inputs';rebuild.mkdir()
    for name in ('desktop-profile.json','LICENSES-desktop.txt'):shutil.copyfile(assets/name,rebuild/name)
    return {'status':'sealed_for_review','lock':str(output/'gui.lock.json'),'payload':lock['payload'],'published':False,'device_verified':False}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('seed','bootstrap','acceptance','modules','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();print(json.dumps(seal(a.seed.resolve(),a.bootstrap.resolve(),a.acceptance.resolve(),a.modules.resolve(),a.output.resolve()),indent=2))
