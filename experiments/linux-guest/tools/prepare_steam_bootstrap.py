#!/usr/bin/env python3
"""Append a private Steam experiment to the exact accepted desktop initramfs.

The original PID1 Stop function is retained byte-for-byte. The caller must use a
new, expanded qcow2 overlay with the accepted GUI seed as read-only backing; this
builder never opens or modifies a disk. No Valve client is included here.
"""
import argparse
import gzip
import io
import json
from pathlib import Path
import re
import tempfile

import desktop_modules as modules
from check_debian_ext4_boot import checked, cpio_suffix
from debian_rootfs import sha256

ROOT = Path(__file__).resolve().parents[1]
MARKER = b'shell_pid=$!\n'
INJECT = b'''# Separate Steam host experiment only; never enable this on a user disk.
case " $(cat /proc/cmdline) " in
    *' ideck.steam_experiment=1 '*) ;;
    *) fail steam_experiment_opt_in_required;;
esac
case " $(cat /proc/cmdline) " in
    *' ideck.steam_disk_grow=1 '*) ;;
    *) fail steam_disposable_overlay_required;;
esac
while read -r name path; do
    [ -d "/sys/module/$name" ] || insmod "/usr/lib/modules/6.18.35-0-virt/$path" || fail "steam_net_module_$name"
done < /ideck-steam/network-load-order
# This online resize is ONLY for the caller's newly expanded disposable overlay.
chroot /sysroot /usr/sbin/resize2fs "$root_disk" 3>&- || fail steam_overlay_resize
n=0
while [ ! -d /sys/class/net/eth0 ]; do
    n=$((n+1)); [ "$n" -le 20 ] || fail steam_network_device
    sleep 1
done
$BB ip link set lo up || fail steam_network_loopback
$BB ip link set eth0 up || fail steam_network_link
$BB ip addr add 10.0.2.15/24 dev eth0 || fail steam_network_address
$BB ip route add default via 10.0.2.2 dev eth0 || fail steam_network_route
[ ! -L /sysroot/etc/resolv.conf ] || fail steam_resolver_symlink
printf 'nameserver 10.0.2.3\\n' > /sysroot/etc/resolv.conf || fail steam_resolver
mkdir -p /sysroot/opt/ideck-steam /sysroot/usr/local/bin || fail steam_tool_directories
cp /ideck-steam/files/* /sysroot/opt/ideck-steam/ || fail steam_tool_install
cp /ideck-steam/files/ideck-steam /sysroot/usr/local/bin/ideck-steam || fail steam_launcher_install
chmod 0755 /sysroot/usr/local/bin/ideck-steam || fail steam_launcher_mode
echo IDECK_STEAM_NETWORK_READY
echo IDECK_STEAM_NETWORK_READY >&3
'''


def experimental_init(original):
    if original.count(MARKER) != 1:
        raise ValueError('desktop recovery insertion point changed')
    result = original.replace(MARKER, MARKER + INJECT)
    stop = original[original.index(b'shutdown() {'):original.index(b'trap shutdown USR2 TERM INT')]
    if stop not in result:
        raise ValueError('original Stop function changed')
    return result


def module_destination(path):
    # Keep Alpine's /lib merged-/usr symlink intact in the appended CPIO.
    return 'usr/lib/modules/'+modules.KERNEL+'/'+modules.module_path(path)


def prepare(initramfs, modloop, unsquashfs, output):
    if output.exists() or output.is_symlink():
        raise ValueError('output already exists')
    lock = json.loads((ROOT/'ipa/gui.lock.json').read_text())
    original_initrd = checked(initramfs, lock['files']['initramfs-desktop.gz'])
    original_init = checked(ROOT/'guest/gui/ideck-desktop-init', lock['inputs']['guest']['ideck-desktop-init'])
    files = {'ideck-steam-init': (experimental_init(original_init), 0o755)}
    inputs = {}
    sources = list(sorted((ROOT/'guest/steam').iterdir())) + [ROOT/'tools/steam_client.py',
                  ROOT/'ipa/steam-client.lock.json', ROOT/'ipa/steam-dependencies.lock.json']
    for source in sources:
        if source.is_symlink() or not source.is_file() or not re.fullmatch(r'[A-Za-z0-9_.-]+', source.name):
            raise ValueError('unexpected Steam tool input')
        key = 'ideck-steam/files/' + source.name
        if key in files:
            raise ValueError('duplicate Steam input filename')
        data = source.read_bytes()
        files[key] = (data, 0o755 if data.startswith(b'#!') else 0o644)
        inputs[source.relative_to(ROOT).as_posix()] = {'size': len(data), 'sha256': modules.sha(data)}
    if 'ideck-steam/files/ideck-steam' not in files:
        raise ValueError('Steam launcher missing')
    with tempfile.TemporaryDirectory(prefix='steam-modules-', dir=output.parent) as temp:
        image = Path(temp)/'modloop-virt'
        modules.copy_verified_modloop(modloop, image)
        metadata = {name: modules.cat_image(unsquashfs, image, modules.MODULE_PREFIX+name, 8*1024**2,
                    allow_empty=name == 'modules.softdep') for name in ('modules.dep','modules.softdep','modules.builtin')}
        dep = modules.dependencies(metadata['modules.dep'])
        order = modules.closure(dep, modules.soft_dependencies(metadata['modules.softdep'], reachable_only=True),
                                metadata['modules.builtin'], requested='virtio_net')
        manifest = []
        for path in order:
            data = modules.cat_image(unsquashfs, image, modules.MODULE_PREFIX+path, 16*1024**2)
            info = modules.module_metadata(data)
            if not {n.replace('-', '_') for n in info['depends']} <= {modules.module_name(p) for p in dep[path]}:
                raise ValueError('network module ELF dependencies differ from modules.dep')
            files[module_destination(path)] = (data, 0o644)
            manifest.append({'path': path, 'name': modules.module_name(path), 'size':len(data),
                             'sha256': modules.sha(data), **info})
    rows = ''.join(modules.module_name(path)+' '+path+'\n' for path in order).encode()
    files['ideck-steam/network-load-order'] = (rows, 0o644)
    suffix = io.BytesIO()
    with gzip.GzipFile(filename='',mode='wb',fileobj=suffix,mtime=0,compresslevel=0) as stream:
        stream.write(cpio_suffix(files))
    output.mkdir()
    destination = output/'initramfs-steam.gz'
    destination.write_bytes(original_initrd + suffix.getvalue())
    report = {'schema':1,'purpose':'private disposable Steam experiment; runtime unverified',
              'base_initramfs': lock['files']['initramfs-desktop.gz'],
              'initramfs': {'size':destination.stat().st_size,'sha256':sha256(destination)},
              'required_kernel_sha256': modules.KERNEL_SHA256,'modloop_sha256':modules.MODLOOP_SHA256,
              'module_metadata':{name:{'size':len(data),'sha256':modules.sha(data)} for name,data in metadata.items()},
              'network_load_order':order,'network_modules':manifest,'inputs':inputs,
              'original_shutdown_function_preserved':True,
              'required_cmdline':['rdinit=/ideck-steam-init','ideck.steam_experiment=1','ideck.steam_disk_grow=1'],
              'guest_network':{'device':'virtio-net-device','address':'10.0.2.15/24','gateway':'10.0.2.2','dns':'10.0.2.3'},
              'gui_payload_changed':False,'valve_client_bundled':False,'guest_boot_verified':False,'iphone_verified':False}
    (output/'bootstrap.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--initramfs', type=Path, required=True)
    parser.add_argument('--modloop', type=Path, required=True)
    parser.add_argument('--unsquashfs', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    a = parser.parse_args()
    print(json.dumps(prepare(a.initramfs.resolve(),a.modloop.resolve(),a.unsquashfs.resolve(),a.output.resolve()),indent=2))
