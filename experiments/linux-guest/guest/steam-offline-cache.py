"""Canonical pinned data-only tar source; no extraction, client execution or HTTP."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import struct
import tarfile

LIMIT = 512 * 1024**2
MARKER = 'ideck.steam_offline_cache=1'


def entries(client, dependencies):
    rows = [{'name': 'client/' + p['file'], 'size': p['size'], 'sha256': p['sha256']}
            for p in client['parts']]
    rows += [{'name': 'debs/' + Path(p['filename']).name, 'size': p['size'], 'sha256': p['sha256']}
             for p in dependencies]
    rows.sort(key=lambda row: row['name'])
    if len(rows) != 62 or len({r['name'] for r in rows}) != 62:
        raise ValueError('offline_cache_pin_count')
    return rows


def header(row):
    name = row['name']
    if (name.count('/') != 1 or name.split('/')[0] not in ('client', 'debs')
            or any(x in name for x in ('..', '\\', '\0'))
            or not name.isascii() or not 0 < row['size'] < 1024**3):
        raise ValueError('offline_cache_pin_path')
    info = tarfile.TarInfo(name)
    info.size = row['size']
    info.mode = 0o644
    return info.tobuf(format=tarfile.USTAR_FORMAT)


def archive_size(rows):
    count = sum(512 + ((r['size'] + 511) // 512) * 512 for r in rows) + 1024
    count = ((count + 10239) // 10240) * 10240
    if not 0 < count <= LIMIT:
        raise ValueError('offline_cache_archive_limit')
    return count


def exact(stream, count):
    result = bytearray()
    while len(result) < count:
        block = stream.read(count - len(result))
        if not block:
            raise ValueError('offline_cache_truncated')
        result += block
    return bytes(result)


def validate(stream, rows):
    offsets = {}
    offset = 0
    for row in rows:
        if exact(stream, 512) != header(row):
            raise ValueError('offline_cache_header')
        offset += 512
        offsets[row['name']] = offset
        digest = hashlib.sha256()
        left = row['size']
        while left:
            data = exact(stream, min(left, 1024**2))
            digest.update(data)
            left -= len(data)
        if digest.hexdigest() != row['sha256']:
            raise ValueError('offline_cache_digest')
        padding = (-row['size']) % 512
        if exact(stream, padding) != bytes(padding):
            raise ValueError('offline_cache_padding')
        offset += row['size'] + padding
    tail = archive_size(rows) - offset
    if exact(stream, tail) != bytes(tail):
        raise ValueError('offline_cache_tail')
    return offsets


class Slice:
    status = 200
    def __init__(self, fd, offset, size):
        self.fd, self.offset, self.left = fd, offset, size
    def read(self, count):
        count = min(count, self.left)
        data = os.pread(self.fd, count, self.offset)
        self.offset += len(data)
        self.left -= len(data)
        return data
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass


def open_device(size):
    import fcntl
    # The reviewed argv attaches only root=vda and this optional readonly=vdb.
    fd = os.open('/dev/vdb', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        if not stat.S_ISBLK(os.fstat(fd).st_mode):
            raise ValueError('offline_cache_not_block_device')
        if struct.unpack('i', fcntl.ioctl(fd, 0x125e, bytes(4)))[0] != 1:  # BLKROGET
            raise ValueError('offline_cache_not_readonly')
        if struct.unpack('Q', fcntl.ioctl(fd, 0x80081272, bytes(8)))[0] != size:  # BLKGETSIZE64
            raise ValueError('offline_cache_device_size')
        return fd
    except BaseException:
        os.close(fd)
        raise


@contextlib.contextmanager
def source(installer):
    if MARKER not in Path('/proc/cmdline').read_text().split():
        yield
        return
    client = installer.client.validate(json.loads((installer.OPT / 'steam-client.lock.json').read_text()))
    deps = installer.common.dependencies(json.loads((installer.OPT / 'steam-dependencies.lock.json').read_text()))
    rows = entries(client, deps)
    fd = open_device(archive_size(rows))
    original = installer.fetch
    original_cache = installer.CACHE
    try:
        # Verify the entire source before any installer/journal/userdata writes.
        with os.fdopen(os.dup(fd), 'rb') as stream:
            offsets = validate(stream, rows)
        pins = {r['name']: r for r in rows}
        urls = {installer.client.CDN + '/' + p['file']: 'client/' + p['file'] for p in client['parts']}
        urls.update({'https://deb.debian.org/debian/' + p['filename']: 'debs/' + Path(p['filename']).name for p in deps})
        class LocalOpener:
            def open(self, url, timeout):
                name = urls.get(url)
                if name is None:
                    raise ValueError('offline_cache_url_not_pinned')
                return Slice(fd, offsets[name], pins[name]['size'])
        def fetch(url, name, size, checksum, directory):
            key = urls.get(installer.official_url(url))
            if key is None or pins[key] != {'name': key, 'size': size, 'sha256': checksum} or Path(key).name != name:
                raise ValueError('offline_cache_request_not_pinned')
            return installer.common.fetch(8080, key.split('/')[0], name, size, checksum, directory,
                official_url=url, official_opener=LocalOpener(), resume=True)
        # Keep prior failed network downloads untouched. The same journal and
        # pinned installer use a separate reserved cache for this verified source.
        installer.CACHE = original_cache.with_name(original_cache.name + '-offline-v1')
        installer.fetch = fetch
        yield
    finally:
        installer.fetch = original
        installer.CACHE = original_cache
        os.close(fd)
