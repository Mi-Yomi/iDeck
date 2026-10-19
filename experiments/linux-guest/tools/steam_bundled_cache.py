#!/usr/bin/env python3
"""Stage the separately pinned owner cache, never download/execute Steam in Xcode."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import stat

ROOT = Path(__file__).resolve().parents[1]
format_path = ROOT / 'guest/steam-offline-cache.py'
if not format_path.is_file():
    format_path = Path(__file__).with_name('ideck-steam-cache-format.py')
spec = importlib.util.spec_from_file_location('steam_cache_format', format_path)
cache = importlib.util.module_from_spec(spec); spec.loader.exec_module(cache)
FILENAME = 'owner-steam-cache.tar'
MANIFEST = 'steam-cache.json'


def regular(path):
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('unsafe bundled cache path')
    state = path.stat()
    if not stat.S_ISREG(state.st_mode) or state.st_nlink != 1:
        raise ValueError('bundled cache requires a single-link regular file')
    return state


def load_lock(path):
    if regular(path).st_size > 65536:
        raise ValueError('oversized bundled cache lock')
    lock = json.loads(path.read_bytes())
    pin = lock.get('archive', {})
    rows = lock.get('entries', [])
    if (lock.get('schema') != 1 or lock.get('kind') != 'ideck-owner-steam-bundled-cache'
            or lock.get('status') != 'ready' or lock.get('client_executed') is not False
            or lock.get('agreement_accepted') is not False or len(rows) != 62
            or set(pin) != {'size', 'sha256'} or pin['size'] != cache.archive_size(rows)
            or not re.fullmatch('[0-9a-f]{64}', pin.get('sha256', ''))
            or len({r['name'] for r in rows}) != 62
            or rows != sorted(rows, key=lambda r: r['name'])):
        raise ValueError('unsealed bundled Steam cache')
    for row in rows:
        if (set(row) != {'name', 'size', 'sha256'} or type(row['size']) is not int
                or not re.fullmatch('[0-9a-f]{64}', row['sha256'])):
            raise ValueError('invalid bundled cache entry')
        cache.header(row)
    if 'payload_url' in lock and not re.fullmatch(r'https://api\.github\.com/repos/Mi-Yomi/iDeck/releases/assets/[0-9]+', lock['payload_url']):
        raise ValueError('invalid private bundled cache asset URL')
    return lock


def verify_archive(path, lock):
    before = regular(path)
    if before.st_size != lock['archive']['size']:
        raise ValueError('bundled cache size mismatch')
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    with os.fdopen(fd, 'rb') as stream:
        opened = os.fstat(stream.fileno())
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            raise ValueError('bundled cache identity changed')
        digest = hashlib.sha256(); count = 0
        while chunk := stream.read(1024**2):
            count += len(chunk)
            if count > lock['archive']['size']: raise ValueError('bundled cache grew')
            digest.update(chunk)
        if count != lock['archive']['size'] or digest.hexdigest() != lock['archive']['sha256']:
            raise ValueError('bundled cache SHA-256 mismatch')
        stream.seek(0); cache.validate(stream, lock['entries'])
    after = regular(path)
    fields = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
    if any(getattr(before, k) != getattr(after, k) for k in fields):
        raise ValueError('bundled cache changed during verification')
    return {'size': count, 'sha256': digest.hexdigest(), 'parts': len(lock['entries'])}


def verify(directory, lock_path):
    lock = load_lock(lock_path)
    if directory.is_symlink() or {p.name for p in directory.iterdir()} != {FILENAME, MANIFEST}:
        raise ValueError('unexpected bundled cache resources')
    regular(directory / MANIFEST)
    if (directory / MANIFEST).read_bytes() != lock_path.read_bytes():
        raise ValueError('bundled cache manifest differs from lock')
    return verify_archive(directory / FILENAME, lock)


def stage(archive, destination, lock_path):
    lock = load_lock(lock_path)
    verify_archive(archive, lock)
    if any(p.is_symlink() for p in (destination, *destination.parents)):
        raise ValueError('unsafe bundled cache destination')
    if destination.exists(): return verify(destination, lock_path)
    destination.mkdir(parents=True, exist_ok=False)
    for source, name in [(archive, FILENAME), (lock_path, MANIFEST)]:
        with source.open('rb') as src, (destination / name).open('xb') as dst:
            shutil.copyfileobj(src, dst, 1024**2)
    return verify(destination, lock_path)


def prepare_for_build(destination, lock_path, scratch):
    lock = load_lock(lock_path)
    source = os.environ.get('IDECK_STEAM_CACHE_FILE')
    if source:
        archive = Path(source)
    else:
        if not lock.get('payload_url'):
            raise ValueError('STEAM_BUNDLED_CACHE_ASSET_NOT_UPLOADED: private upload returned HTTP401; provide verified local IDECK_STEAM_CACHE_FILE or pin the real asset URL')
        if os.environ.get('IDECK_STEAM_PAYLOAD_URL'):
            raise ValueError('Use the reviewed cache asset pin; the Linux seed URL override cannot select cache bytes')
        # Same existing private payload token and HTTPS transport; no new secret.
        from steam_bundle import fetch
        archive = scratch / FILENAME
        fetch(archive, lock)
    return stage(archive, destination, lock_path)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=('stage', 'verify'))
    p.add_argument('source', type=Path)
    p.add_argument('lock', type=Path)
    p.add_argument('--destination', type=Path)
    a = p.parse_args()
    print(json.dumps(stage(a.source, a.destination, a.lock) if a.command == 'stage' else verify(a.source, a.lock)))
