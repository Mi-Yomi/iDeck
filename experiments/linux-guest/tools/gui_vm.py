#!/usr/bin/env python3
"""Prepare disposable GUI acceptance inputs using an OFFLINE authenticated cache.

The Debian kernel here is exclusively a host provisioning instrument. Outputs
are deliberately not app assets and have no iOS profile or packaging path.
"""
import argparse
import gzip
import json
import os
from pathlib import Path
import re
import resource
import shutil
import subprocess
import tarfile

import debian_rootfs as base
import desktop_modules as modules
import gui_rootfs as gui
import gui_host_tools
from check_debian_ext4_boot import cpio_suffix

ROOT = Path(__file__).resolve().parents[1]


PUBLIC_DIRECTORIES = ('usr/local','usr/local/lib','usr/local/lib/ideck','usr/local/share',
                      'usr/local/share/ideck','usr/local/share/applications',
                      'proc','sys','dev','dev/pts','dev/shm','run','packages','var/lib/ideck')


def canonical_gui_modes(root):
    # Keep the host output private while making only public guest paths
    # traversable/readable for UID1000, independently of host umask0077.
    root.chmod(0o755)
    for name in PUBLIC_DIRECTORIES:
        (root/name).chmod(0o755)
    for path in [root/'usr/local/share/ideck/tint2rc',root/'etc/X11/ideck.conf',
                 *(root/'usr/local/share/applications').iterdir()]:
        path.chmod(0o644)


def run(args, env=None):
    return subprocess.run([str(a) for a in args], env=env, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True)


def module_inputs(kernel, host, env):
    releases = list((kernel / 'usr/lib/modules').iterdir())
    if len(releases) != 1:
        raise ValueError('ambiguous provision kernel')
    release = releases[0].name
    run(gui_host_tools.command(host,[host / 'usr/sbin/depmod', '-b', kernel, '-m', '/usr/lib/modules', release]), env)
    # Ask the real pinned kmod to resolve hard dependencies, aliases (including
    # crypto_crc32c), builtins and softdeps. A hand-written name graph cannot
    # safely interpret alias softdeps from this kernel.
    (kernel / 'lib').symlink_to('usr/lib')
    needed = ['virtio_pci', 'virtio_mmio', 'virtio_blk', 'virtio_gpu', 'virtio_input', 'evdev', 'ext4', 'virtio_console']
    order = []
    for name in needed:
        result = run(gui_host_tools.command(host,[host/'usr/sbin/modprobe','-d',kernel,'-S',release,'--show-depends',name]),env)
        for row in result.stdout.splitlines():
            if row.startswith('builtin '): continue
            instruction, separator, module = row.rstrip().partition(' ')
            if not separator or instruction != 'insmod' or not module:
                raise ValueError('unsupported provision module instruction')
            path = Path(module).resolve().relative_to(releases[0].resolve()).as_posix()
            if not path.endswith('.ko.xz'):
                raise ValueError('unsupported provision module compression')
            path = modules.module_path(path[:-3])
            if path not in order: order.append(path)
    files = {}
    import lzma
    for path in order:
        data = lzma.decompress((releases[0] / (path + '.xz')).read_bytes(), memlimit=64*1024**2)
        if release.encode() + b' ' not in data or data[:4] != b'\x7fELF':
            raise ValueError('provision module vermagic/ELF mismatch')
        files['ideck/modules/' + path] = (data, 0o644)
    files['ideck/gui-load-order'] = (('\n'.join(order) + '\n').encode(), 0o644)
    return release, files, order


def prepare(lock_path, cache, output):
    lock = json.loads(lock_path.read_text())
    base.OFFLINE = True
    gui.download(lock, cache)
    source_paths = [Path(__file__), Path(gui.__file__), Path(base.__file__),Path(gui_host_tools.__file__),
                    *sorted((ROOT/'guest/gui').iterdir())]
    source_hashes = {str(p.relative_to(ROOT)):base.sha256(p) for p in source_paths}
    # Budget actual full copies, without relying on sparse allocation savings.
    required = (2*1024**3 + 256*1024**2 + 32*1024**2
                + sum(lock['totals'][k]['installed_size_bytes']
                      for k in ('guest','host','provision_kernel')))
    ancestor = next(p for p in [output.parent,*output.parents] if p.is_dir())
    if shutil.disk_usage(ancestor).free < required:
        raise ValueError('insufficient space for disposable GUI preparation')
    output.mkdir(parents=True, exist_ok=False)
    host, kernel, root, packages = [output / n for n in ['host', 'kernel', 'tree', 'packages']]
    for group, dest in [('host_packages', host), ('provision_kernel', kernel)]:
        for pin in lock[group]: run(['dpkg-deb', '-x', cache / 'debs' / Path(pin['filename']).name, dest])
    env = {'PATH': os.defpath, 'LC_ALL': 'C',
           'LD_LIBRARY_PATH': str(host / 'usr/lib/x86_64-linux-gnu')}
    for name in ('bin', 'sbin', 'lib'):
        (root / 'usr' / name).mkdir(parents=True, exist_ok=True)
        (root / name).symlink_to('usr/' + name)
    ownership = {}
    packages.mkdir()
    for pin in lock['packages']:
        deb = cache / 'debs' / Path(pin['filename']).name
        ownership.update(base.package_ownership(deb))
        run(['dpkg-deb', '-x', deb, root])
        os.link(deb, packages / deb.name)
    for name in ('proc', 'sys', 'dev/pts', 'dev/shm', 'run', 'tmp', 'packages', 'var/lib/dpkg', 'var/lib/ideck'):
        (root / name).mkdir(parents=True, exist_ok=True)
    (root / 'tmp').chmod(0o1777)
    (root / 'var/lib/dpkg/status').touch()
    policy = root / 'usr/sbin/policy-rc.d'; policy.write_text('#!/bin/sh\nexit 101\n'); policy.chmod(0o755)
    scripts = root / 'usr/local/lib/ideck'; scripts.mkdir(parents=True)
    for name in ('provision', 'start', 'session'):
        shutil.copyfile(ROOT / 'guest/gui' / name, scripts / name); (scripts / name).chmod(0o755)
    shared = root / 'usr/local/share/ideck'; shared.mkdir(parents=True)
    shutil.copyfile(ROOT / 'guest/gui/tint2rc', shared / 'tint2rc')
    (root / 'etc/X11').mkdir(exist_ok=True)
    shutil.copyfile(ROOT / 'guest/gui/xorg.conf', root / 'etc/X11/ideck.conf')
    apps = root / 'usr/local/share/applications'; apps.mkdir(parents=True)
    for name, title, command, icon in [('terminal', 'Terminal', 'xterm', 'utilities-terminal'),
                                      ('files', 'Files', 'pcmanfm', 'system-file-manager'),
                                      ('editor', 'Editor', 'mousepad', 'accessories-text-editor')]:
        (apps / f'ideck-{name}.desktop').write_text(f'[Desktop Entry]\nType=Application\nName={title}\nExec={command}\nIcon={icon}\nTerminal=false\n')
    canonical_gui_modes(root)
    (packages / 'SHA256SUMS').write_text(''.join(p['sha256']+'  '+Path(p['filename']).name+'\n' for p in lock['packages']))
    (packages / 'expected-packages.tsv').write_text(''.join(sorted('\t'.join([p['name'],p['version'],p['architecture'],'install ok installed'])+'\n' for p in lock['packages'])))
    tree_bytes = sum(p.stat().st_size for p in root.rglob('*') if p.is_file() and not p.is_symlink())
    # Disposable provisioning capacity: measured extraction + 512 MiB workspace,
    # rounded to 256 MiB. This is not a production image capacity decision.
    size = ((tree_bytes + 512*1024**2 + 256*1024**2-1)//(256*1024**2))*(256*1024**2)
    if not 1024**3 <= size <= 2*1024**3: raise ValueError('scratch image capacity exceeds reviewed budget')
    config = output / 'mke2fs.conf'; config.write_text('[defaults]\nblocksize = 4096\ninode_size = 256\n')
    env['MKE2FS_CONFIG'] = str(config)
    def image(name, tree, capacity, uuid):
        path = output / name
        with path.open('xb') as f: f.truncate(capacity)
        run(gui_host_tools.command(host,[host/'usr/sbin/mke2fs', '-q','-F','-t','ext4','-b','4096','-I','256',
             '-O',base.FEATURE_NAMES,'-E','lazy_itable_init=0,lazy_journal_init=0,root_owner=0:0',
             '-m','0','-U',uuid,'-d',tree,path]), env)
        return path
    raw = image('scratch-gui.raw', root, size, gui.UUID)
    commands = []
    for path in sorted(root.rglob('*')):
        rel = path.relative_to(root).as_posix(); uid,gid = ownership.get(rel,[0,0])
        commands += [f'sif {base.debugfs_quote("/"+rel)} uid {uid}', f'sif {base.debugfs_quote("/"+rel)} gid {gid}']
    script = output/'ownership.debugfs'; script.write_text('\n'.join(commands)+'\n')
    result = run(gui_host_tools.command(host,[host/'usr/sbin/debugfs','-w','-f',script,raw]),env)
    (output/'ownership.log').write_text(result.stdout)
    if any(s in result.stdout for s in ['File not found','not found by ext2_lookup','Command not found']):
        raise ValueError('scratch ownership publication failed')
    package_image = image('packages.raw',packages,256*1024**2,'691da426-5867-4e6e-bcab-dc62b40715b6')
    release, files, order = module_inputs(kernel, host, env)
    for name in ('ideck-gui-host-init','ideck-gui-host-login'):
        files[name] = ((ROOT/'guest/gui'/name).read_bytes(),0o755)
    from stage_bundle import verify
    with tarfile.open(ROOT/'husk/linux-probe-guest.tar.gz') as tar:
        # Verify the exact committed bundle before extracting fixed members.
        bundle = output/'probe'; bundle.mkdir()
        for name in ['profile.json','vmlinuz-virt','initramfs-ideck.gz']:
            data=tar.extractfile(name).read(); (bundle/name).write_bytes(data)
    verified=verify(bundle)
    initrd=output/'initramfs-gui-host.gz'
    initrd.write_bytes(verified['initramfs-ideck.gz']+gzip.compress(cpio_suffix(files),mtime=0))
    kernel_image=kernel/'boot'/('vmlinuz-'+release)
    if any(base.sha256(ROOT/name) != digest for name,digest in source_hashes.items()):
        raise ValueError('GUI preparation source changed during execution')
    report={'schema':1,'status':'prepared_not_booted','host_only':True,'production_kernel_changed':False,
            'lock_sha256':base.sha256(lock_path),'tree_logical_bytes':tree_bytes,'scratch_size_bytes':size,
            'kernel_release':release,'kernel_sha256':base.sha256(kernel_image),
            'module_load_order':order,'initramfs_sha256':base.sha256(initrd),
            'qemu_version':run(gui_host_tools.command(host,[host/'usr/bin/qemu-system-aarch64','--version']),env).stdout.splitlines()[0],
            'builder_peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
            'sources':source_hashes,
            'notice_policy':'All authenticated package /usr/share/doc files retained; no stripping'}
    (output/'preparation.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--lock',type=Path,required=True); p.add_argument('--cache',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args(); print(json.dumps(prepare(a.lock.resolve(),a.cache.resolve(),a.output.resolve()),indent=2))
