#!/usr/bin/env python3
"""Finalize a NEW GUI seed from the verified disposable GUI acceptance snapshot.

Never opens iOS Documents/userdata. Cleanup runs inside a real offline VM after
all session writers terminate. e2image copies only allocated blocks to a NEW raw
image; it never resizes or modifies the source. Production Alpine GUI acceptance
is a separate mandatory gate before the seed is an app payload.
"""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

import debian_rootfs as base
import gui_rootfs as gui
import gui_vm
from check_debian_ext4_boot import cpio_suffix
from check_gui_vm import boot
from stage_bundle import verify

ROOT=Path(__file__).resolve().parents[1]
SOURCE_SHA='a32f7b9c0c59e651492811458e3a46667010eb4be54d07a79487e94c5e43ed06'
CLEANUP='''set -eu
for name in start session; do
    cp /ideck/seed-files/$name /sysroot/usr/local/lib/ideck/$name
    chmod 0755 /sysroot/usr/local/lib/ideck/$name
done
cp /ideck/seed-files/tint2rc /sysroot/usr/local/share/ideck/tint2rc
cp /ideck/seed-files/xorg.conf /sysroot/etc/X11/ideck.conf
chmod 0644 /sysroot/usr/local/share/ideck/tint2rc /sysroot/etc/X11/ideck.conf
rm -f /sysroot/home/ideck/Documents/check.txt /sysroot/home/ideck/Documents/editor.txt
rm -f /sysroot/home/ideck/.bash_history /sysroot/root/.bash_history
rm -f /sysroot/home/ideck/.local/share/recently-used.xbel
rm -f /sysroot/var/log/Xorg.0.log /sysroot/var/log/Xorg.0.log.old
rm -f /sysroot/usr/local/lib/ideck/provision
: > /sysroot/etc/machine-id
rm -f /sysroot/var/lib/dbus/machine-id
ln -s /etc/machine-id /sysroot/var/lib/dbus/machine-id
chroot /sysroot dpkg --configure -a 3>&- || fail seed_configure
chroot /sysroot dpkg --audit > /run/seed-audit 3>&- || fail seed_audit
[ ! -s /run/seed-audit ] || fail seed_audit_output
'''


def prepare(source, source_vm, cache, output, lock_path):
    lock=json.loads(lock_path.read_text());base.OFFLINE=True
    gui.download(lock,cache)
    if source.is_symlink() or source.stat().st_size!=1_342_177_280 or base.sha256(source)!=SOURCE_SHA:
        raise ValueError('requires exact immutable two-boot GUI lab snapshot; no user image accepted')
    if shutil.disk_usage(output.parent).free<5*1024**3:raise ValueError('insufficient seed-finalization space')
    output.mkdir(parents=True,exist_ok=False)
    vm=output/'vm';vm.mkdir()
    for group,name in [('host_packages','host'),('provision_kernel','kernel')]:
        for pin in lock[group]:base.run(['dpkg-deb','-x',cache/'debs'/Path(pin['filename']).name,vm/name])
    env={'PATH':os.defpath,'LC_ALL':'C','LD_LIBRARY_PATH':str(vm/'host/usr/lib/x86_64-linux-gnu')}
    release,files,order=gui_vm.module_inputs(vm/'kernel',vm/'host',env)
    root=vm/'scratch-gui.raw';shutil.copyfile(source,root)
    # Only an offline read-only package volume is shared. Root is always a copy.
    os.link(source_vm/'packages.raw',vm/'packages.raw')
    (vm/'packages').symlink_to(source_vm/'packages',target_is_directory=True)
    script=(ROOT/'guest/gui/ideck-gui-host-init').read_text()
    needle='    $BB sync || fail sync' if '    $BB sync || fail sync' in script else '    sync || fail sync'
    if needle not in script:raise ValueError('unrecognized host shutdown sequence')
    # The exact tested host supervisor is a preparation instrument, not the app bootstrap.
    script=script.replace(needle,'    . /ideck/seed-cleanup || fail seed_cleanup\n'+needle,1)
    files['ideck-gui-host-init']=(script.encode(),0o755)
    files['ideck-gui-host-login']=((ROOT/'guest/gui/ideck-gui-host-login').read_bytes(),0o755)
    files['ideck/seed-cleanup']=(CLEANUP.encode(),0o644)
    for name in ('start','session','tint2rc','xorg.conf'):files['ideck/seed-files/'+name]=((ROOT/'guest/gui'/name).read_bytes(),0o644)
    probe=verify(source_vm/'probe')
    initrd=vm/'initramfs-gui-host.gz';initrd.write_bytes(probe['initramfs-ideck.gz']+gzip.compress(cpio_suffix(files),mtime=0))
    prep={'schema':1,'status':'seed_finalization_host_only','kernel_release':release,
          'kernel_sha256':base.sha256(vm/'kernel/boot'/('vmlinuz-'+release)),
          'initramfs_sha256':base.sha256(initrd),'source_snapshot_sha256':SOURCE_SHA,
          'module_load_order':order,'production_kernel_changed':False}
    (vm/'preparation.json').write_text(json.dumps(prep,indent=2)+'\n')
    result=boot(vm,output/'cleanup-boot',persistence=True)
    if result['status']!='pass' or not result['clean_unmount']:raise ValueError('seed cleanup VM failed')
    seed=output/'seed';seed.mkdir();raw=seed/'gui-rootfs-v1.raw'
    base.run([vm/'host/usr/sbin/e2image','-ra',root,raw],env=env)
    if raw.stat().st_size>1_342_177_280:raise ValueError('unexpected e2image geometry')
    with raw.open('r+b') as f:f.truncate(1_342_177_280);f.flush();os.fsync(f.fileno())
    fsck=base.run([vm/'host/usr/sbin/e2fsck','-fn',raw],env=env);(output/'seed-fsck.log').write_text(fsck.stdout+fsck.stderr)
    for path in ['/home/ideck/Documents/check.txt','/home/ideck/Documents/editor.txt','/home/ideck/.bash_history']:
        r=base.run([vm/'host/usr/sbin/debugfs','-R','stat '+base.debugfs_quote(path),raw],env=env)
        if 'File not found' not in r.stderr:raise ValueError('acceptance artifact remained in seed')
    header=base.ext4_header(raw)
    if header['uuid']!=gui.UUID or raw.stat().st_size!=1_342_177_280:raise ValueError('GUI seed identity mismatch')
    guest_files={}
    for name,target in [('start','/usr/local/lib/ideck/start'),('session','/usr/local/lib/ideck/session'),
                        ('tint2rc','/usr/local/share/ideck/tint2rc'),('xorg.conf','/etc/X11/ideck.conf')]:
        data=base.run([vm/'host/usr/sbin/debugfs','-R','cat '+target,raw],env=env).stdout.encode()
        expected=(ROOT/'guest/gui'/name).read_bytes()
        if data!=expected:raise ValueError('final seed desktop file differs: '+name)
        guest_files[name]={'size':len(data),'sha256':hashlib.sha256(data).hexdigest()}
    compressed=seed/'gui-rootfs-v1.raw.gz'
    with raw.open('rb') as src,compressed.open('xb') as dst,gzip.GzipFile(filename='',mode='wb',fileobj=dst,mtime=0,compresslevel=6) as gz:
        shutil.copyfileobj(src,gz,1024*1024)
    if base.sha256(source)!=SOURCE_SHA:raise ValueError('source snapshot changed')
    report={'schema':1,'mode':'gui-seed','source_snapshot_sha256':SOURCE_SHA,
        'rootfs':{'file':raw.name,'size':raw.stat().st_size,'sha256':base.sha256(raw)},
        'gzip':{'file':compressed.name,'size':compressed.stat().st_size,'sha256':base.sha256(compressed)},
        'image':header,'cleanup_boot':result,'read_only_fsck':True,'guest_files':guest_files,
        'production_matching_kernel_gui_verified':False,'app_payload_ready':False,
        'gui_package_lock_sha256':base.sha256(lock_path),'builder_sha256':base.sha256(Path(__file__))}
    (seed/'gui-seed.json').write_text(json.dumps(report,indent=2)+'\n');return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for flag in ['source','source-vm','cache','output','lock']:p.add_argument('--'+flag,type=Path,required=True)
    a=p.parse_args();print(json.dumps(prepare(a.source.resolve(),a.source_vm.resolve(),a.cache.resolve(),a.output.resolve(),a.lock.resolve()),indent=2))
