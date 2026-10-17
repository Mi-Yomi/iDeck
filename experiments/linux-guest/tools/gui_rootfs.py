#!/usr/bin/env python3
"""Separate authenticated GUI inputs. Never changes the accepted console lock.

Only Debian trixie/main is trusted here. Package configuration belongs in a
real disposable system VM; this tool never runs maintainer scripts on the host.
"""
import argparse
import json
from pathlib import Path
import re
import urllib.parse

import debian_rootfs as base

GUI = ['udev', 'systemd-standalone-sysusers', 'xserver-xorg-core',
       'xserver-xorg-input-libinput', 'xinit', 'xauth', 'xkb-data',
       'keyboard-configuration', 'openbox', 'tint2', 'pcmanfm', 'mousepad',
       'xterm', 'dbus', 'dbus-bin', 'dbus-daemon', 'dbus-x11',
       'fonts-dejavu-core', 'fonts-dejavu-mono', 'xfonts-base', 'x11-utils',
       'x11-xserver-utils', 'xdotool', 'librsvg2-common', 'adwaita-icon-theme-legacy']
HOST = ['qemu-system-arm', 'e2fsprogs', 'kmod']
KERNEL = 'linux-image-arm64'
UUID = 'b66e1c8d-9cbf-45a7-b97b-dcc8f68efca7'


def totals(pins):
    return {'package_count': len(pins), 'download_bytes': sum(p['size'] for p in pins),
            'installed_size_bytes': sum(p['installed_size_kib'] * 1024 for p in pins)}


def create_lock(cache, output, keyring=base.KEYRING):
    cache = cache.resolve()
    cache.mkdir(parents=True, exist_ok=True)
    release = base.fetch(base.RELEASE_URL, cache / 'InRelease', limit=1024**2)
    fields, signers = base.verify_release(release, keyring)
    indexes = [base.index_descriptor(fields, arch) for arch in ('arm64', 'amd64')]
    arm, plain = base.load_index(cache, indexes[0])
    direct = sorted(set(base.POSIX + GUI + [r['Package'] for r in arm
                        if r.get('Essential') == 'yes' or r.get('Priority') == 'required']))
    packages = base.resolve(arm, plain, direct, cache)
    kernel_meta = next(r for r in arm if r['Package'] == KERNEL)
    match = re.fullmatch(r'(linux-image-[a-zA-Z0-9.+-]+) \(= ([^)]+)\)', kernel_meta['Depends'])
    if not match:
        raise ValueError('unexpected provision kernel dependency')
    kernel = [base.package_pin(next(r for r in arm if (r['Package'], r['Version']) == match.groups()))]
    amd, plain = base.load_index(cache, indexes[1])
    host = base.resolve(amd, plain, HOST, cache, architecture='amd64')
    lock = {'schema': 1, 'kind': 'ideck-gui-inputs', 'suite': 'trixie',
            'release': {'url': base.RELEASE_URL, **{'size': release.stat().st_size,
                        'sha256': base.sha256(release)}, 'indexes': indexes,
                        'signer_fingerprints': signers, 'date': fields['Date'],
                        'max_age_days': 90},
            'selection': {'direct': direct, 'host_direct': HOST, 'install_recommends': False},
            'packages': packages, 'host_packages': host, 'provision_kernel': kernel,
            'totals': {key: totals(value) for key, value in
                       [('guest', packages), ('host', host), ('provision_kernel', kernel)]},
            'future_image': {'uuid': UUID, 'filename': 'gui-rootfs-v1.raw',
                             'size_bytes': None, 'size_status': 'requires VM and used-block measurements'},
            'boundaries': {'package_configuration_verified': False, 'gui_verified': False,
                           'production_kernel_changed': False, 'payload_published': False}}
    validate(lock)
    with output.open('x') as stream:
        stream.write(json.dumps(lock, indent=2) + '\n')
    return lock


def validate(lock):
    if (lock.get('schema'), lock.get('kind'), lock.get('suite')) != (1, 'ideck-gui-inputs', 'trixie'):
        raise ValueError('unexpected GUI input schema')
    if lock['release']['url'] != base.RELEASE_URL or lock['release']['max_age_days'] != 90:
        raise ValueError('unexpected GUI release')
    if [d['architecture'] for d in lock['release']['indexes']] != ['arm64', 'amd64']:
        raise ValueError('unexpected GUI indexes')
    for key, arches in [('packages', {'arm64', 'all'}), ('host_packages', {'amd64', 'all'}),
                        ('provision_kernel', {'arm64'})]:
        pins = lock[key]
        if not pins or len({p['name'] for p in pins}) != len(pins):
            raise ValueError('empty/duplicate GUI pins')
        for p in pins:
            if (p['architecture'] not in arches or not re.fullmatch(r'[a-z0-9][a-z0-9+.-]*', p['name'])
                    or not re.fullmatch(r'[0-9a-f]{64}', p['sha256'])
                    or type(p['size']) is not int or not 0 < p['size'] <= 128*1024**2
                    or type(p['installed_size_kib']) is not int or p['installed_size_kib'] < 0
                    or not re.fullmatch(r'pool/[A-Za-z0-9+._~/-]+\.deb', p['filename'])
                    or '..' in p['filename'].split('/')):
                raise ValueError('invalid GUI package pin')
    if (lock['selection']['install_recommends'] is not False
            or not set(GUI + base.POSIX).issubset(lock['selection']['direct'])
            or not set(lock['selection']['direct']).issubset({p['name'] for p in lock['packages']})
            or lock['selection']['host_direct'] != HOST):
        raise ValueError('unexpected GUI selection')
    if any(value is not False for value in lock['boundaries'].values()):
        raise ValueError('input lock cannot claim runtime verification')
    if lock['future_image']['uuid'] != UUID or lock['future_image']['filename'] != 'gui-rootfs-v1.raw':
        raise ValueError('unexpected GUI identity')
    if lock['future_image']['size_bytes'] is not None:
        raise ValueError('input lock cannot declare a measured output image')
    for key, value in [('guest', lock['packages']), ('host', lock['host_packages']),
                       ('provision_kernel', lock['provision_kernel'])]:
        if lock['totals'][key] != totals(value):
            raise ValueError('GUI totals mismatch')


def authenticate(lock, cache, keyring=base.KEYRING):
    validate(lock)
    release = lock['release']
    path = base.fetch(release['url'], cache / 'InRelease', release['size'], release['sha256'], limit=1024**2)
    fields, signers = base.verify_release(path, keyring)
    if not set(release['signer_fingerprints']).issubset(signers):
        raise ValueError('GUI signer mismatch')
    for desc in release['indexes']:
        if desc != base.index_descriptor(fields, desc['architecture']):
            raise ValueError('GUI index is not authenticated')
        records, plain = base.load_index(cache, desc)
        known = {r['Filename']: base.package_pin(r) for r in records if 'Filename' in r}
        pins = lock['packages'] + lock['provision_kernel'] if desc['architecture'] == 'arm64' else lock['host_packages']
        if any(known.get(p['filename']) != p for p in pins):
            raise ValueError('GUI package is not authenticated')
        # Replay the actual solver too: an authentic subset is not a closure.
        seeds = lock['selection']['direct'] if desc['architecture'] == 'arm64' else HOST
        expected = lock['packages'] if desc['architecture'] == 'arm64' else lock['host_packages']
        if base.resolve(records, plain, seeds, cache, architecture=desc['architecture']) != expected:
            raise ValueError('GUI dependency closure differs from locked resolution')
    return fields


def download(lock, cache, keyring=base.KEYRING):
    authenticate(lock, cache / 'metadata', keyring)
    result = {}
    for group in ('packages', 'host_packages', 'provision_kernel'):
        for pin in lock[group]:
            path = cache / 'debs' / Path(pin['filename']).name
            base.fetch(base.BASE + urllib.parse.quote(pin['filename'], safe='/+'), path, pin['size'], pin['sha256'])
            result[path.name] = {'size': pin['size'], 'sha256': pin['sha256']}
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['lock', 'download', 'verify'])
    p.add_argument('--cache', type=Path, required=True)
    p.add_argument('--lock', type=Path, required=True)
    p.add_argument('--keyring', type=Path, default=base.KEYRING)
    p.add_argument('--offline', action='store_true')
    a = p.parse_args(); base.OFFLINE = a.offline
    if a.action == 'lock':
        if a.offline:
            p.error('offline cannot create a new lock')
        result = create_lock(a.cache / 'metadata', a.lock, a.keyring)['totals']
    else:
        lock = json.loads(a.lock.read_text())
        if a.action == 'verify':
            authenticate(lock, a.cache.resolve() / 'metadata', a.keyring); result = lock['totals']
        else:
            result = {'verified_files': len(download(lock, a.cache.resolve(), a.keyring)), 'totals': lock['totals']}
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
