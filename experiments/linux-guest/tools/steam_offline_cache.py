#!/usr/bin/env python3
"""Pack/verify owner-obtained pinned files. Never downloads or executes Steam."""
import argparse
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('offline_cache', ROOT / 'guest/steam-offline-cache.py')
cache = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cache)


def pins():
    import steam_client
    s = importlib.util.spec_from_file_location('cached', ROOT / 'guest/steam/install-cached.py')
    common = importlib.util.module_from_spec(s); s.loader.exec_module(common)
    client = steam_client.validate(json.loads((ROOT / 'ipa/steam-client.lock.json').read_text()))
    deps = common.dependencies(json.loads((ROOT / 'ipa/steam-dependencies.lock.json').read_text()))
    return cache.entries(client, deps)


def regular(path):
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('offline cache requires paths without symlinks')
    state = path.stat()
    if not stat.S_ISREG(state.st_mode) or state.st_nlink != 1:
        raise ValueError('offline cache requires regular single-link files')
    return state


def identity(state):
    return tuple(getattr(state, key) for key in ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_uid', 'st_gid', 'st_mode', 'st_nlink'))


def open_regular(path):
    before = regular(path)
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    try:
        if identity(os.fstat(fd)) != identity(before): raise ValueError('input identity changed')
        return os.fdopen(fd, 'rb')
    except BaseException:
        os.close(fd)
        raise


def pack(client_directory, debs_directory, output, rows=None):
    rows = pins() if rows is None else rows
    cache.archive_size(rows)
    if output.exists() or output.is_symlink() or any(p.is_symlink() for p in output.parents):
        raise ValueError('output exists or has symlink ancestors')
    fd, temp = tempfile.mkstemp(prefix='.ideck-cache-', dir=output.parent)
    try:
        with os.fdopen(fd, 'wb') as target:
            for row in rows:
                path = (client_directory if row['name'].startswith('client/') else debs_directory) / Path(row['name']).name
                before = regular(path)
                if before.st_size != row['size']:
                    raise ValueError('input size mismatch')
                target.write(cache.header(row))
                digest = hashlib.sha256()
                count = 0
                with open_regular(path) as source:
                    while data := source.read(1024**2):
                        count += len(data)
                        if count > row['size']: raise ValueError('input grew')
                        digest.update(data); target.write(data)
                if count != row['size'] or digest.hexdigest() != row['sha256'] or identity(regular(path)) != identity(before):
                    raise ValueError('input digest or identity mismatch')
                target.write(bytes((-row['size']) % 512))
            target.write(bytes(cache.archive_size(rows) - target.tell()))
            target.flush(); os.fsync(target.fileno())
        verify(Path(temp), rows)
        os.link(temp, output)
        if os.name == 'posix':
            directory = os.open(output.parent, os.O_RDONLY | os.O_DIRECTORY)
            try: os.fsync(directory)
            finally: os.close(directory)
    finally:
        Path(temp).unlink(missing_ok=True)
    return {'size': output.stat().st_size, 'sha256': digest_file(output), 'parts': len(rows),
            'client_executed': False, 'agreement_accepted': False, 'owner_local_only': True}


def digest_file(path):
    h = hashlib.sha256()
    with open_regular(path) as stream:
        count = 0
        while chunk := stream.read(1024**2):
            count += len(chunk)
            if count > cache.LIMIT: raise ValueError('archive grew beyond limit')
            h.update(chunk)
    return h.hexdigest()


def verify(path, rows=None):
    rows = pins() if rows is None else rows
    if regular(path).st_size != cache.archive_size(rows): raise ValueError('archive size mismatch')
    with open_regular(path) as stream: return cache.validate(stream, rows)


def runtime_device_action():
    original = (ROOT / 'guest/steam/device-action.py').read_bytes()
    old = b'            installer.install()'
    new = b'''            offline_spec = importlib.util.spec_from_file_location('offline_cache', OPT / 'steam-offline-cache.py')
            offline = importlib.util.module_from_spec(offline_spec)
            offline_spec.loader.exec_module(offline)
            with offline.source(installer):
                installer.install()'''
    if original.count(old) != 1: raise ValueError('device-action runtime overlay source drift')
    original = original.replace(old, new)
    receipt = b"            print('IDECK_STEAM_INSTALLED', flush=True)"
    if original.count(receipt) != 1: raise ValueError('install completion receipt source drift')
    # A following launch must observe that the installer already released its lock.
    return original.replace(receipt, b'            resources.close()\n' + receipt)


def guest_suffix():
    files = [('ideck-steam/files/device-action.py', runtime_device_action()),
             ('ideck-steam/files/steam-offline-cache.py', (ROOT / 'guest/steam-offline-cache.py').read_bytes())]
    output = bytearray()
    for inode, (name, data) in enumerate([*files, ('TRAILER!!!', b'')], 1):
        name = name.encode(); mode = 0 if name == b'TRAILER!!!' else 0o100644
        values = (inode, mode, 0, 0, 1, 0, len(data), 0, 0, 0, 0, len(name)+1, 0)
        output += b'070701' + ''.join(f'{v:08x}' for v in values).encode() + name + b'\0'
        output += bytes(-len(output) % 4) + data
        output += bytes(-len(output) % 4)
    return bytes(output)


def swift():
    data = guest_suffix()
    lines = ['// Generated by tools/steam_offline_cache.py; no Valve bytes.', 'import Foundation',
             'enum LinuxSteamCacheContract {', f'    static let archiveSize: Int64 = {cache.archive_size(pins())}',
             f'    static let deviceSerial = "{cache.DEVICE_SERIAL}"',
             f'    static let suffixSHA256 = "{hashlib.sha256(data).hexdigest()}"',
             f'    static var suffix: Data {{ Data(base64Encoded: "{base64.b64encode(data).decode()}")! }}',
             '    static let entries: [LinuxSteamOfflineCache.Entry] = [']
    for row in pins():
        h = base64.b64encode(cache.header(row)).decode()
        lines.append(f'        .init(header: "{h}", size: {row["size"]}, sha256: "{row["sha256"]}"),')
    return '\n'.join([*lines, '    ]', '}', ''])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    commands = p.add_subparsers(dest='command', required=True)
    packer = commands.add_parser('pack')
    packer.add_argument('--client-directory', required=True, type=Path)
    packer.add_argument('--debs-directory', required=True, type=Path)
    packer.add_argument('--output', required=True, type=Path)
    verifier = commands.add_parser('verify'); verifier.add_argument('archive', type=Path)
    generate = commands.add_parser('swift'); generate.add_argument('output', type=Path)
    a = p.parse_args()
    if a.command == 'pack': print(json.dumps(pack(a.client_directory, a.debs_directory, a.output), indent=2))
    elif a.command == 'verify': verify(a.archive); print('OFFLINE_CACHE_VERIFIED')
    else: a.output.write_text(swift())


if __name__ == '__main__': main()
