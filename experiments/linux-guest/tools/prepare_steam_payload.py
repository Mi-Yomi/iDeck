#!/usr/bin/env python3
"""Create NEW offline Steam assets from the exact approved GUI seed. No uploads.

Never accepts qcow2 or mutable/user disks. The result is a candidate lock for
review, not Apple/device acceptance. Existing payloads/locks are never edited.
"""
import argparse
import gzip
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

import gui_bundle
import steam_bundle as bundle
from debian_rootfs import ext4_header
from prepare_steam_bootstrap import prepare
from steam_vm import evaluate_offline_fsck

ROOT = Path(__file__).resolve().parents[1]


def build(gui, modloop, unsquashfs, e2fsck, tune2fs, resize2fs, output):
    gui_bundle.verify(gui, gui_bundle.load_lock(ROOT / 'ipa/gui.lock.json'))
    source_inputs = {name: bundle.metadata(ROOT / name) for name in sorted(bundle.SOURCE_NAMES)}
    bundle.safe_destination(output)
    if output.exists():
        raise ValueError('Steam build output must be new')
    output.parent.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(output.parent).free < bundle.SIZE + 4 * 1024**3:
        raise ValueError('Steam offline builder needs 16 GiB free; no sparse capacity assumption')
    output.mkdir()
    tools = {name: bundle.metadata(path) for name, path in [('e2fsck', e2fsck), ('tune2fs', tune2fs),
                                                          ('resize2fs', resize2fs), ('unsquashfs', unsquashfs)]}
    def run(label, command, *, allowed=(0,)):
        result = subprocess.run(list(map(str, command)), capture_output=True, timeout=600, env={**os.environ, "LC_ALL": "C", "LANG": "C"})
        (output / (label + '.log')).write_bytes(result.stdout + result.stderr)
        if result.returncode not in allowed:
            raise ValueError('Steam offline tool failed: ' + label)
        return result
    # Every write, UUID change and growth operation targets this NEW copy only.
    raw = output / 'steam-rootfs-v1.raw'
    shutil.copyfile(gui / 'gui-rootfs-v1.raw', raw)
    initial = run('pre-fsck', [e2fsck, '-f', '-n', raw])
    before_fsck = evaluate_offline_fsck(initial.returncode, initial.stdout.decode(), initial.stderr.decode(), raw)
    if not before_fsck['accepted']:
        raise ValueError('Steam seed input requires uneventful full read-only fsck')
    # tune2fs requires a fresh writable check; this targets only the new copy.
    run('prepare-check', [e2fsck, '-f', '-p', raw])
    run('new-uuid', [tune2fs, '-U', bundle.UUID, raw])
    with raw.open('r+b') as held:
        held.truncate(bundle.SIZE)
        held.flush()
        os.fsync(held.fileno())
    run('offline-grow', [resize2fs, raw])
    # Offline growth can leave optimizable extents. Normalize only this new copy.
    run('normalize-new-copy', [e2fsck, '-f', '-y', raw], allowed=(0, 1))
    final = run('post-fsck', [e2fsck, '-f', '-n', raw])
    after_fsck = evaluate_offline_fsck(final.returncode, final.stdout.decode(), final.stderr.decode(), raw)
    if not after_fsck['accepted']:
        raise ValueError('Steam new seed requires uneventful full read-only fsck')
    header = ext4_header(raw)
    if header != {'uuid': bundle.UUID, 'block_size': 4096, 'features': {'compat': 44, 'incompat': 194, 'ro_compat': 1091},
                  'inode_size': 256, 'descriptor_size': 64}:
        raise ValueError('Steam raw filesystem contract differs')
    bootstrap = prepare(gui / 'initramfs-desktop.gz', modloop, unsquashfs, output / 'bootstrap', persistent=True)
    assets = output / 'assets'
    assets.mkdir()
    shutil.copyfile(gui / 'vmlinuz-virt', assets / 'vmlinuz-virt')
    shutil.copyfile(output / 'bootstrap/initramfs-steam.gz', assets / 'initramfs-steam.gz')
    compressed = assets / 'steam-rootfs-v1.raw.gz'
    with raw.open('rb') as inp, compressed.open('xb') as out:
        with gzip.GzipFile(filename='', fileobj=out, mode='wb', mtime=0, compresslevel=6) as zipped:
            shutil.copyfileobj(inp, zipped, 1024**2)
    profile = {'schema': 1, 'mode': 'steam-experimental', 'control_port': 'org.ideck.control',
               'image': {'uuid': bundle.UUID, 'size_bytes': bundle.SIZE, 'block_size': 4096, 'features': header['features']},
               'seed_sha256': bundle.metadata(raw)['sha256']}
    for key, name in [('kernel', 'vmlinuz-virt'), ('initramfs', 'initramfs-steam.gz'), ('rootfs', compressed.name)]:
        profile[key] = {'file': name, **bundle.metadata(assets / name)}
    (assets / 'steam-profile.json').write_text(json.dumps(profile, indent=2) + '\n')
    notices = (gui / 'LICENSES-desktop.txt').read_text() + '\nSteam experiment: original iDeck bootstrap/install tools; Valve client is NOT bundled.\nOfficial pinned client/dependencies are fetched on device after network consent.\n'
    (assets / 'LICENSES-steam.txt').write_text(notices)
    lock = bundle.load_lock(ROOT / 'ipa/steam.lock.json')
    lock.update(status='ready', files={name: bundle.metadata(assets / name) for name in sorted(bundle.NAMES)},
                seed_sha256=profile['seed_sha256'],
                source_inputs=source_inputs)
    lock.pop('blocker', None)
    archive = output / 'ideck-steam-device-v1.tar'
    with tarfile.open(archive, 'w', format=tarfile.USTAR_FORMAT) as target:
        for name in sorted(bundle.NAMES):
            info = tarfile.TarInfo(name)
            info.size = lock['files'][name]['size']
            info.mode = 0o644
            with (assets / name).open('rb') as inp:
                target.addfile(info, inp)
    for name, pin in source_inputs.items():
        bundle.checked(ROOT / name, pin)
    lock['archive'] = bundle.metadata(archive)
    candidate = output / 'steam.lock.candidate.json'
    candidate.write_text(json.dumps(lock, indent=2) + '\n')
    bundle.verify(assets, bundle.load_lock(candidate))
    gui_bundle.verify(gui, gui_bundle.load_lock(ROOT / 'ipa/gui.lock.json'))
    report = {'schema': 1, 'status': 'candidate_prepared_not_device_accepted', 'tools': tools, 'bootstrap': bootstrap,
              'source_gui_preserved': True, 'pre_fsck': before_fsck, 'post_fsck': after_fsck, 'raw': bundle.metadata(raw), 'lock': bundle.metadata(candidate),
              'apple_compiled': False, 'guest_boot_tested': False, 'device_verified': False, 'uploaded': False}
    (output / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('gui-assets', 'modloop', 'unsquashfs', 'e2fsck', 'tune2fs', 'resize2fs', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    a = parser.parse_args()
    print(json.dumps(build(a.gui_assets.absolute(), a.modloop.absolute(), a.unsquashfs.absolute(), a.e2fsck.absolute(),
                           a.tune2fs.absolute(), a.resize2fs.absolute(), a.output.absolute()), indent=2))
