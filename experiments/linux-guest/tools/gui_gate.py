#!/usr/bin/env python3
"""Run two real GUI boots with the original production Alpine kernel/initrd.

Only a NEW private copy of the seed is writable. The exact rootfs, bootstrap,
package lock and both real-VM reports are bound into the receipt. This is a
Linux-host QEMU test; Apple/iOS execution remains a separate acceptance gate.
"""
import argparse
import json
import os
from pathlib import Path
import shutil

import debian_rootfs as base
import desktop_modules as modules
import gui_rootfs as inputs
from check_gui_vm import boot

ROOT=Path(__file__).resolve().parents[1]


def run(seed, bootstrap, cache, output, lock_path):
    lock=json.loads(lock_path.read_text());base.OFFLINE=True
    inputs.download(lock,cache)
    raw=seed/'gui-rootfs-v1.raw'
    if raw.is_symlink() or raw.stat().st_size!=1_342_177_280 or base.ext4_header(raw)['uuid']!=inputs.UUID:
        raise ValueError('unexpected GUI seed identity')
    root_hash=base.sha256(raw)
    info=json.loads((bootstrap/'bootstrap.json').read_text())
    for name,kind in [('vmlinuz-virt','kernel'),('initramfs-desktop.gz','initramfs')]:
        path=bootstrap/name
        if path.is_symlink() or path.stat().st_size!=info[kind]['size'] or base.sha256(path)!=info[kind]['sha256']:
            raise ValueError('bootstrap integrity mismatch')
    if info['kernel']['sha256']!=modules.KERNEL_SHA256:raise ValueError('production kernel changed')
    if shutil.disk_usage(output.parent).free<3*1024**3:raise ValueError('insufficient private VM test space')
    output.mkdir(parents=True,exist_ok=False);vm=output/'vm';vm.mkdir()
    for pin in lock['host_packages']:
        base.run(['dpkg-deb','-x',cache/'debs'/Path(pin['filename']).name,vm/'host'])
    (vm/'kernel/boot').mkdir(parents=True)
    shutil.copyfile(bootstrap/'vmlinuz-virt',vm/'kernel/boot'/('vmlinuz-'+modules.KERNEL))
    shutil.copyfile(bootstrap/'initramfs-desktop.gz',vm/'initramfs-gui-host.gz')
    shutil.copyfile(raw,vm/'scratch-gui.raw')
    (vm/'packages').mkdir()
    expected=''.join(sorted('\t'.join([p['name'],p['version'],p['architecture'],'install ok installed'])+'\n' for p in lock['packages']))
    (vm/'packages/expected-packages.tsv').write_text(expected)
    prep={'schema':1,'production_bootstrap':True,'kernel_release':modules.KERNEL,
          'kernel_sha256':modules.KERNEL_SHA256,'initramfs_sha256':info['initramfs']['sha256']}
    (vm/'preparation.json').write_text(json.dumps(prep,indent=2)+'\n')
    env={'PATH':os.defpath,'LC_ALL':'C','LD_LIBRARY_PATH':str(vm/'host/usr/lib/x86_64-linux-gnu')}
    version=base.run([vm/'host/usr/bin/qemu-system-aarch64','--version'],env=env).stdout
    first=boot(vm,output/'boot1');second=boot(vm,output/'boot2',persistence=True)
    for result in (first,second):
        if result['status']!='pass' or not all(result.get(k) is True for k in
                ('production_bootstrap','gui_mapped','emulated_pointer_move_resize','wheel_evdev_verified','real_root_menu_launch','keyboard_input_verified','clean_unmount','read_only_fsck')):
            raise ValueError('real production GUI gate failed')
    if base.sha256(raw)!=root_hash:raise ValueError('immutable seed changed during private-copy acceptance')
    report={'schema':1,'kind':'production-alpine-two-boots','status':'pass',
            'kernel_sha256':modules.KERNEL_SHA256,'initramfs_sha256':info['initramfs']['sha256'],
            'rootfs_sha256':root_hash,'gui_package_lock_sha256':base.sha256(lock_path),
            'bootstrap_receipt_sha256':base.sha256(bootstrap/'bootstrap.json'),
            'boot_reports':{n:base.sha256(output/n/'result.json') for n in ('boot1','boot2')},
            'matching_kernel_gui':True,'two_boots_clean':True,'host_qemu_version':version.strip(),
            'ios_qemu_version':'10.0.12-utm','ios_compiled':False,'device_verified':False,
            'runner_sha256':base.sha256(Path(__file__))}
    (output/'acceptance.json').write_text(json.dumps(report,indent=2)+'\n');return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for flag in ('seed','bootstrap','cache','output','lock'):p.add_argument('--'+flag,type=Path,required=True)
    a=p.parse_args();print(json.dumps(run(a.seed.resolve(),a.bootstrap.resolve(),a.cache.resolve(),a.output.resolve(),a.lock.resolve()),indent=2))
