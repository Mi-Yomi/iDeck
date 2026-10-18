#!/usr/bin/env python3
"""Separate Steam assets. A blocked contract packages only an honest blocker."""
import argparse
import hashlib
import re
import time
import urllib.request
import urllib.parse
import json
import os
from pathlib import Path
import shutil
import tarfile
import tempfile

def metadata(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return {'size': path.stat().st_size, 'sha256': digest.hexdigest()}


def safe_destination(path):
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('symlink Steam asset path')


def real_directory(path):
    safe_destination(path)
    if not path.is_dir():
        raise ValueError('Steam asset directory missing')


def checked(path, pin):
    safe_destination(path)
    if not path.is_file() or path.stat().st_size != pin['size'] or metadata(path) != pin:
        raise ValueError('Steam asset integrity mismatch: ' + path.name)


NAMES = {'vmlinuz-virt', 'initramfs-steam.gz', 'steam-rootfs-v1.raw.gz', 'steam-profile.json', 'LICENSES-steam.txt'}
UUID = 'c6a66b17-1b3e-4fe9-a07b-70c185fb2718'
SIZE = 12 * 1024**3
BLOCKED = b'STEAM_PAYLOAD_NOT_SEALED\n'
ROOT = Path(__file__).resolve().parents[1]
SOURCE_NAMES = {
    'guest/steam/' + name for name in ('ideck-steam', 'install-cached.py', 'install-official.py',
    'device-action.py', 'namespace-check.py', 'prepare-display.py', 'shm-recovery.py')
} | {'tools/' + name for name in ('steam_client.py', 'steam_cpu_probe.py', 'prepare_steam_bootstrap.py',
                                'prepare_steam_payload.py', 'steam_bundle.py', 'steam_vm.py', 'debian_rootfs.py', 'desktop_modules.py', 'gui_bundle.py')} | {
    'ipa/steam-client.lock.json', 'ipa/steam-dependencies.lock.json', 'ipa/gui.lock.json',
    'ipa/gui-inputs.lock.json', 'ipa/desktop-kernel-source.lock.json', 'guest/gui/LICENSES-desktop.txt', 'guest/TERMINAL-LICENSES.txt'}


def load_lock(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 65536:
        raise ValueError('unsafe Steam asset lock')
    lock = json.loads(path.read_text())
    if (lock.get('schema') != 1 or lock.get('kind') != 'ideck-steam-device-experiment'
            or lock.get('disk_uuid') != UUID or lock.get('disk_size_bytes') != SIZE
            or lock.get('memory_mib') != 1536 or lock.get('valve_client_bundled') is not False
            or lock.get('device_verified') is not False):
        raise ValueError('invalid Steam asset scope')
    if lock.get('status') == 'blocked' and lock.get('blocker') == 'STEAM_PAYLOAD_NOT_SEALED':
        return lock
    if lock.get('status') != 'ready' or set(lock.get('files', {})) != NAMES:
        raise ValueError('Steam payload is not sealed')
    for name, pin in lock['files'].items():
        limit = 2 * 1024**3 if name.endswith('.raw.gz') else 128 * 1024**2 if name.endswith('.gz') else 32 * 1024**2 if name == 'vmlinuz-virt' else 65536
        if (set(pin) != {'size', 'sha256'} or type(pin['size']) is not int or not 0 < pin['size'] <= limit
                or not re.fullmatch('[0-9a-f]{64}', pin['sha256'])):
            raise ValueError('invalid Steam asset pin')
    inputs = lock.get('source_inputs', {})
    if set(inputs) != SOURCE_NAMES or any(set(p) != {'size', 'sha256'} or type(p['size']) is not int or p['size'] <= 0
        or not re.fullmatch('[0-9a-f]{64}', p['sha256']) for p in inputs.values()):
        raise ValueError('Steam source input bindings missing')
    archive = lock.get('archive', {})
    if (set(archive) != {'size', 'sha256'} or type(archive['size']) is not int or not 0 < archive['size'] <= 3 * 1024**3
            or not re.fullmatch('[0-9a-f]{64}', archive['sha256']) or not re.fullmatch('[0-9a-f]{64}', lock.get('seed_sha256', ''))):
        raise ValueError('invalid Steam archive/raw pin')
    if 'payload_url' in lock and (not isinstance(lock['payload_url'], str) or not re.fullmatch(r'https://api\.github\.com/repos/Mi-Yomi/iDeck/releases/assets/[0-9]+', lock['payload_url'])):
        raise ValueError('pinned Steam URL must be the same repository asset API, without credentials/query')
    if lock['files']['vmlinuz-virt'] != {'size': 10351104, 'sha256': '47970e0ee0478fe5c60824a89f162d5a353fa29466e5d3bddb0f9c506f1ed756'}:
        raise ValueError('Steam kernel must retain the accepted kernel')
    return lock


def verify(source, lock):
    real_directory(source)
    expected = NAMES if lock['status'] == 'ready' else {'STEAM-BLOCKER.txt'}
    if {p.name for p in source.iterdir()} != expected:
        raise ValueError('unexpected Steam bundle contents')
    if lock['status'] == 'blocked':
        checked(source / 'STEAM-BLOCKER.txt', {'size': len(BLOCKED), 'sha256': __import__('hashlib').sha256(BLOCKED).hexdigest()})
        return {'status': 'blocked', 'blocker': 'STEAM_PAYLOAD_NOT_SEALED'}
    for name, pin in lock['files'].items():
        checked(source / name, pin)
    profile = json.loads((source / 'steam-profile.json').read_text())
    if (profile.get('schema') != 1 or profile.get('mode') != 'steam-experimental'
            or profile.get('control_port') != 'org.ideck.control'
            or profile.get('image') != {'size_bytes': SIZE, 'uuid': UUID, 'block_size': 4096,
                                      'features': {'compat': 44, 'incompat': 194, 'ro_compat': 1091}}):
        raise ValueError('Steam profile/disk identity differs')
    for key, name in [('kernel', 'vmlinuz-virt'), ('initramfs', 'initramfs-steam.gz'), ('rootfs', 'steam-rootfs-v1.raw.gz')]:
        if profile[key] != {'file': name, **lock['files'][name]}:
            raise ValueError('Steam profile asset differs')
    if profile.get('seed_sha256') != lock.get('seed_sha256'):
        raise ValueError('Steam expanded seed digest differs')
    return lock['files']


def stage(source, destination, lock_path):
    lock = load_lock(lock_path)
    if lock['status'] == 'ready':
        verify(source, lock)
    safe_destination(destination)
    if source is not None and (source.resolve() == destination.resolve() or source.resolve() in destination.resolve().parents):
        raise ValueError('Steam staging overlaps source')
    if destination.exists():
        return verify(destination, lock)
    destination.mkdir(parents=True, exist_ok=False)
    if lock['status'] == 'blocked':
        (destination / 'STEAM-BLOCKER.txt').write_bytes(BLOCKED)
    else:
        for name in sorted(NAMES):
            shutil.copyfile(source / name, destination / name)
    return verify(destination, lock)


def restore(archive, destination, lock_path):
    lock = load_lock(lock_path)
    if lock['status'] != 'ready':
        raise ValueError('Steam payload has no reviewed ready lock')
    checked(archive, lock['archive'])
    safe_destination(destination)
    if destination.exists():
        raise ValueError('Steam restore requires a new destination')
    if shutil.disk_usage(destination.parent).free < sum(p['size'] for p in lock['files'].values()) + 1024**3:
        raise ValueError('insufficient Steam asset space')
    with tarfile.open(archive, 'r:') as source:
        members = source.getmembers()
        if (len(members) != len(NAMES) or {m.name for m in members} != NAMES
                or any(not m.isfile() or m.size != lock['files'][m.name]['size'] for m in members)):
            raise ValueError('unsafe Steam payload archive')
        destination.mkdir()
        for member in members:
            with source.extractfile(member) as inp, (destination / member.name).open('xb') as out:
                shutil.copyfileobj(inp, out, 1024**2)
    return verify(destination, lock)


class HTTPSOnly(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, url):
        p = urllib.parse.urlsplit(url)
        if p.scheme != 'https' or not p.hostname or p.username or p.password:
            raise ValueError('Steam asset redirect requires HTTPS')
        result = super().redirect_request(req, fp, code, msg, headers, url)
        if result is not None:
            result.remove_header('Authorization')
        return result


def fetch(destination, lock):
    # URL/token never enter logs or receipts. No changes to CI secret settings.
    url = os.environ.get('IDECK_STEAM_PAYLOAD_URL', '') or lock.get('payload_url', '')
    p = urllib.parse.urlsplit(url)
    if p.scheme != 'https' or not p.hostname or p.username or p.password:
        raise ValueError('STEAM_PAYLOAD_URL_MISSING_OR_NOT_HTTPS')
    asset_api = (p.hostname == 'api.github.com' and p.port in (None, 443) and not p.query and not p.fragment
                 and re.fullmatch('/repos/Mi-Yomi/iDeck/releases/assets/[0-9]+', p.path))
    token = os.environ.get('IDECK_STEAM_PAYLOAD_TOKEN', '')
    if not token and asset_api:
        token = os.environ.get('IDECK_DEBIAN_PAYLOAD_TOKEN', '')
    if token and not asset_api:
        raise ValueError('STEAM_PAYLOAD_TOKEN_SCOPE')
    safe_destination(destination)
    if destination.exists():
        raise ValueError('Steam asset download destination exists')
    request = urllib.request.Request(url, headers={'Accept': 'application/octet-stream'})
    if token:
        request.add_unredirected_header('Authorization', 'Bearer ' + token)
    fd, temp = tempfile.mkstemp(prefix='.steam-payload-', dir=destination.parent)
    try:
        count = 0
        deadline = time.monotonic() + 300
        with os.fdopen(fd, 'wb') as out, urllib.request.build_opener(HTTPSOnly()).open(request, timeout=60) as inp:
            while block := inp.read(1024**2):
                count += len(block)
                if count > lock['archive']['size'] or time.monotonic() > deadline:
                    raise ValueError('Steam asset download bound')
                out.write(block)
            out.flush()
            os.fsync(out.fileno())
        checked(Path(temp), lock['archive'])
        os.link(temp, destination)
    except Exception:
        raise ValueError('STEAM_PAYLOAD_FETCH_FAILED') from None
    finally:
        Path(temp).unlink(missing_ok=True)


def prepare_for_build(destination, lock_path, scratch):
    lock = load_lock(lock_path)
    if lock['status'] == 'blocked':
        return stage(None, destination, lock_path)
    for name, pin in lock['source_inputs'].items():
        checked(ROOT / name, pin)
    archive = scratch / 'ideck-steam-device-v1.tar'
    fetch(archive, lock)
    restored = scratch / 'steam-restored'
    restore(archive, restored, lock_path)
    return stage(restored, destination, lock_path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('stage', 'verify', 'restore'))
    parser.add_argument('source', type=Path)
    parser.add_argument('lock', type=Path)
    parser.add_argument('--destination', type=Path)
    args = parser.parse_args()
    if args.command == 'verify':
        result = verify(args.source, load_lock(args.lock))
    else:
        if args.destination is None:
            parser.error('--destination required')
        result = globals()[args.command](args.source, args.destination, args.lock)
    print(json.dumps(result, indent=2))
