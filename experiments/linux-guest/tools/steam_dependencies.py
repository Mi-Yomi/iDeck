#!/usr/bin/env python3
"""Pin Steam's observed external ELF dependencies against the accepted GUI index.

APT is simulation-only. Package configuration belongs only in the separate guest.
This records static input requirements, not successful client or CEF execution.
"""
import argparse
import json
from pathlib import Path
import debian_rootfs as base

# DT_NEEDED from the pinned official ARM64 client's active UI libraries and its
# driver query. Normal GUI dependencies are already in the accepted GUI closure.
OBSERVED = {
    'libasound.so.2': 'libasound2t64', 'libasyncns.so.0': 'libasyncns0',
    'libgtk-x11-2.0.so.0': 'libgtk2.0-0t64', 'libibus-1.0.so.5': 'libibus-1.0-5',
    'libnm.so.0': 'libnm0', 'libnspr4.so': 'libnspr4',
    'libnss3.so': 'libnss3', 'libnssutil3.so': 'libnss3', 'libsmime3.so': 'libnss3',
    'libopenal.so.1': 'libopenal1', 'libpipewire-0.3.so.0': 'libpipewire-0.3-0t64',
    'libpulse.so.0': 'libpulse0', 'libSDL2-2.0.so.0': 'libsdl2-2.0-0',
    'libsndfile.so.1': 'libsndfile1', 'libssh2.so.1': 'libssh2-1t64',
    'libnghttp2.so.14': 'libnghttp2-14', 'libva.so.2': 'libva2', 'libvdpau.so.1': 'libvdpau1',
}


def create(gui_path, inventory_path, metadata, keyring):
    gui = json.loads(gui_path.read_text())
    inventory = json.loads(inventory_path.read_text())
    observed = {name for entry in inventory for name in entry['needed']}
    if not set(OBSERVED).issubset(observed):
        raise ValueError('required sonames were not observed in official client ELF')
    release = gui['release']
    path = base.fetch(release['url'], metadata/'InRelease', release['size'], release['sha256'])
    fields, signers = base.verify_release(path, keyring)
    if not set(release['signer_fingerprints']).issubset(signers):
        raise ValueError('Debian signer mismatch')
    desc = release['indexes'][0]
    if desc != base.index_descriptor(fields, 'arm64'):
        raise ValueError('Debian ARM64 index mismatch')
    records, plain = base.load_index(metadata, desc)
    authentic = {r['Filename']: base.package_pin(r) for r in records if 'Filename' in r}
    if any(authentic.get(p['filename']) != p for p in gui['packages']):
        raise ValueError('GUI package pin differs from authenticated index')
    direct = sorted(set(OBSERVED.values()))
    closure = base.resolve(records, plain, sorted(set(gui['selection']['direct'] + direct)), metadata)
    existing = {p['name']: p for p in gui['packages']}
    if not set(existing).issubset({p['name'] for p in closure}):
        raise ValueError('Steam dependencies would remove accepted GUI packages')
    if any(p['name'] in existing and p != existing[p['name']] for p in closure):
        raise ValueError('Steam dependencies would change accepted GUI package versions')
    extras = [p for p in closure if p['name'] not in existing]
    return {'schema': 1, 'kind': 'ideck-experimental-steam-dependencies', 'architecture': 'arm64',
            'gui_inputs_sha256': base.sha256(gui_path), 'elf_inventory_sha256': base.sha256(inventory_path),
            'release': release, 'observed_soname_packages': OBSERVED,
            'selection': {'direct': direct, 'install_recommends': False}, 'extra_packages': extras,
            'combined_closure_count': len(closure),
            'boundaries': {'client_executed': False, 'package_configuration_verified': False,
                           'steam_window_verified': False, 'iphone_verified': False},
            'scope': 'Active client UI/driver-query dependencies; unrelated legacy bundled FFmpeg aliases are not claimed independently loadable.'}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--gui-lock', type=Path, required=True)
    p.add_argument('--elf-inventory', type=Path, required=True)
    p.add_argument('--metadata', type=Path, required=True)
    p.add_argument('--keyring', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    base.OFFLINE = True
    lock = create(a.gui_lock, a.elf_inventory, a.metadata, a.keyring)
    with a.output.open('x') as out:
        out.write(json.dumps(lock, indent=2)+'\n')
    print(json.dumps({'extra_packages': len(lock['extra_packages']),
                      'download_bytes': sum(p['size'] for p in lock['extra_packages'])}))
