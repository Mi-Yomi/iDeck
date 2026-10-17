#!/usr/bin/env python3
"""Finalize a NEW GUI seed from the verified disposable GUI acceptance snapshot.

Never opens iOS Documents/userdata. Cleanup runs inside a real offline VM after
all session writers terminate. e2image copies only allocated blocks to a NEW raw
image; it never resizes or modifies the source. Production Alpine GUI acceptance
is a separate mandatory gate before the seed is an app payload.
"""
import argparse
import ast
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys

import debian_rootfs as base
import gui_rootfs as gui
import gui_vm
import gui_host_tools
from check_debian_ext4_boot import cpio_suffix
import check_gui_vm
from check_gui_vm import boot
from stage_bundle import verify

ROOT=Path(__file__).resolve().parents[1]
SOURCE_SIZE=1_342_177_280


def provisioning_code(path):
    """Compare archived provisioning code without executing the saved runner.

    GUI-only serial/input fixes do not invalidate a completed package install.
    The ENTIRE runner except its `if provision` GUI else branch must still be
    identical, including imports/top-level code/failure/cleanup/fsck logic. Both
    GUI boots always require the exact current full runner hash.
    """
    if path.is_symlink() or not path.is_file() or path.stat().st_size>128*1024:
        raise ValueError('invalid archived provisioning runner')
    module=ast.parse(path.read_text())
    boot_function=next(node for node in module.body if isinstance(node,ast.FunctionDef) and node.name=='boot')
    branches=[node for node in ast.walk(boot_function) if isinstance(node,ast.If)
              and isinstance(node.test,ast.Name) and node.test.id=='provision']
    if len(branches)!=1:raise ValueError('ambiguous provisioning branch')
    branches[0].orelse=[]
    return ast.dump(module,include_attributes=False)


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


def accepted_snapshot(source, source_vm, acceptance, lock_path, source_sha256):
    """Bind a newly built lab snapshot to its actual clean two-boot evidence.

    The caller freezes the digest after boot2. A previous cloud snapshot hash
    cannot stand in for local provisioning. Only the disposable VM's named
    scratch image is accepted; the production seed is still a NEW e2image copy.
    """
    if (not re.fullmatch(r'[0-9a-f]{64}', source_sha256)
            or source.is_symlink() or source != source_vm/'scratch-gui.raw'
            or source.stat().st_size != SOURCE_SIZE or base.sha256(source) != source_sha256
            or base.ext4_header(source)['uuid'] != gui.UUID):
        raise ValueError('requires frozen disposable GUI lab snapshot; no user image accepted')
    def receipt(path):
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 128*1024:
            raise ValueError('invalid GUI lab receipt')
        return json.loads(path.read_text())
    prep=receipt(source_vm/'preparation.json')
    if prep.get('lock_sha256') != base.sha256(lock_path) or prep.get('host_only') is not True:
        raise ValueError('GUI lab preparation differs from locked inputs')
    expected_sources=[Path(gui_vm.__file__),Path(gui.__file__),Path(base.__file__),Path(gui_host_tools.__file__),
                      *sorted((ROOT/'guest/gui').iterdir())]
    if prep.get('sources') != {str(p.relative_to(ROOT)):base.sha256(p) for p in expected_sources}:
        raise ValueError('GUI lab preparation sources changed')
    reports={};provision_runner_hash=None
    for name in ('provision','boot1','boot2'):
        path=acceptance/name/'result.json';result=receipt(path)
        archived=acceptance/name/'runner-source.py'
        current=Path(check_gui_vm.__file__)
        if archived.is_symlink() or not archived.is_file() or archived.stat().st_size>128*1024:
            raise ValueError('missing archived GUI runner')
        if result.get('runner_sha256')!=base.sha256(archived):raise ValueError('changed archived GUI runner')
        if name=='provision':
            if provisioning_code(archived)!=provisioning_code(current):raise ValueError('provisioning code changed')
            provision_runner_hash=result['runner_sha256']
        elif result.get('runner_sha256')!=base.sha256(current):raise ValueError('stale GUI runner')
        if (result.get('status') != 'pass' or result.get('preparation') != prep
                or result.get('host_tools_sha256') != base.sha256(Path(gui_host_tools.__file__))
                or result.get('clean_unmount') is not True or result.get('read_only_fsck') is not True
                or result.get('qemu_exit') != 0 or result.get('forced_termination')):
            raise ValueError('missing/stale/unclean GUI lab acceptance')
        if name=='boot2' and result.get('disk_sha256') != source_sha256:
            raise ValueError('GUI lab boot2 covers a different snapshot')
        if name=='provision':
            if result.get('provision') is not True or result.get('package_configuration_verified') is not True:
                raise ValueError('GUI packages were not configured in the real VM')
        elif (result.get('provision') is not False or result.get('persistence_boot') != (name=='boot2')
                or not all(result.get(k) is True for k in ('gui_mapped','keyboard_input_verified',
                    'emulated_pointer_move_resize','wheel_evdev_verified','real_root_menu_launch'))
                or (name=='boot1' and result.get('editor_typed_saved') is not True)
                or (name=='boot2' and (result.get('persistence_read_before_write') is not True
                                      or result.get('editor_reopened_after_boot') is not True))):
            raise ValueError('incomplete GUI lab input/persistence acceptance')
        reports[name]=base.sha256(path)
    return {'source_snapshot_sha256':source_sha256,'source_size':SOURCE_SIZE,
            'preparation_sha256':base.sha256(source_vm/'preparation.json'),'boot_reports':reports,
            'runner_provenance':{'provision_source_sha256':provision_runner_hash,
                'gui_source_sha256':base.sha256(current),
                'provisioning_code_sha256':hashlib.sha256(provisioning_code(current).encode()).hexdigest(),
                'comparison':'whole runner AST except inactive GUI branch; archived source never executed'}}


def prepare(source, source_vm, cache, output, lock_path, acceptance, source_sha256):
    lock=json.loads(lock_path.read_text());base.OFFLINE=True
    gui.download(lock,cache)
    snapshot=accepted_snapshot(source,source_vm,acceptance,lock_path,source_sha256)
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
          'initramfs_sha256':base.sha256(initrd),'source_snapshot_sha256':source_sha256,
          'module_load_order':order,'production_kernel_changed':False}
    (vm/'preparation.json').write_text(json.dumps(prep,indent=2)+'\n')
    result=boot(vm,output/'cleanup-boot',persistence=True)
    if result['status']!='pass' or not result['clean_unmount']:raise ValueError('seed cleanup VM failed')
    seed=output/'seed';seed.mkdir();raw=seed/'gui-rootfs-v1.raw'
    base.run(gui_host_tools.command(vm/'host',[vm/'host/usr/sbin/e2image','-ra',root,raw]),env=env)
    if raw.stat().st_size>1_342_177_280:raise ValueError('unexpected e2image geometry')
    with raw.open('r+b') as f:f.truncate(1_342_177_280);f.flush();os.fsync(f.fileno())
    fsck=base.run(gui_host_tools.command(vm/'host',[vm/'host/usr/sbin/e2fsck','-fn',raw]),env=env);(output/'seed-fsck.log').write_text(fsck.stdout+fsck.stderr)
    for path in ['/home/ideck/Documents/check.txt','/home/ideck/Documents/editor.txt','/home/ideck/.bash_history']:
        r=base.run(gui_host_tools.command(vm/'host',[vm/'host/usr/sbin/debugfs','-R','stat '+base.debugfs_quote(path),raw]),env=env)
        if 'File not found' not in r.stderr:raise ValueError('acceptance artifact remained in seed')
    header=base.ext4_header(raw)
    if header['uuid']!=gui.UUID or raw.stat().st_size!=1_342_177_280:raise ValueError('GUI seed identity mismatch')
    guest_files={}
    for name,target in [('start','/usr/local/lib/ideck/start'),('session','/usr/local/lib/ideck/session'),
                        ('tint2rc','/usr/local/share/ideck/tint2rc'),('xorg.conf','/etc/X11/ideck.conf')]:
        data=base.run(gui_host_tools.command(vm/'host',[vm/'host/usr/sbin/debugfs','-R','cat '+target,raw]),env=env).stdout.encode()
        expected=(ROOT/'guest/gui'/name).read_bytes()
        if data!=expected:raise ValueError('final seed desktop file differs: '+name)
        guest_files[name]={'size':len(data),'sha256':hashlib.sha256(data).hexdigest()}
    compressed=seed/'gui-rootfs-v1.raw.gz'
    with raw.open('rb') as src,compressed.open('xb') as dst,gzip.GzipFile(filename='',mode='wb',fileobj=dst,mtime=0,compresslevel=6) as gz:
        shutil.copyfileobj(src,gz,1024*1024)
    if base.sha256(source)!=source_sha256:raise ValueError('source snapshot changed')
    report={'schema':1,'mode':'gui-seed',**snapshot,
        'rootfs':{'file':raw.name,'size':raw.stat().st_size,'sha256':base.sha256(raw)},
        'gzip':{'file':compressed.name,'size':compressed.stat().st_size,'sha256':base.sha256(compressed)},
        'image':header,'cleanup_boot':result,'read_only_fsck':True,'guest_files':guest_files,
        'production_matching_kernel_gui_verified':False,'app_payload_ready':False,
        'gui_package_lock_sha256':base.sha256(lock_path),'builder_sha256':base.sha256(Path(__file__))}
    (seed/'gui-seed.json').write_text(json.dumps(report,indent=2)+'\n');return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for flag in ['source','source-vm','cache','output','lock','acceptance']:p.add_argument('--'+flag,type=Path,required=True)
    p.add_argument('--source-sha256',required=True,help='frozen SHA-256 after the local lab boot2')
    a=p.parse_args();print(json.dumps(prepare(a.source.resolve(),a.source_vm.resolve(),a.cache.resolve(),a.output.resolve(),a.lock.resolve(),a.acceptance.resolve(),a.source_sha256),indent=2))
