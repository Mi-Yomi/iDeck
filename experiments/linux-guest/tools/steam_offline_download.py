#!/usr/bin/env python3
"""Prepare an owner-local pinned Steam cache; never execute or upload its bytes."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import ssl
import stat
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

import steam_client
import steam_offline_cache as packer

ROOT = packer.ROOT
DEBIAN_RELEASE = 'https://deb.debian.org/debian/dists/trixie/InRelease'
DEBIAN_BASE = 'https://deb.debian.org/debian/'  # Existing install-official.py contract.
CHUNK = 1024**2


def safe_path(path):
    for item in (path, *path.parents):
        try:
            state = item.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(state.st_mode) or getattr(state, 'st_file_attributes', 0) & 0x400:
            raise ValueError('symlink or Windows reparse path refused')


def read_lock(path):
    safe_path(path)
    with packer.open_regular(path) as stream:
        data = stream.read(256 * 1024 + 1)
    if len(data) > 256 * 1024:
        raise ValueError('lock exceeds bound')
    return data, json.loads(data)


def official_url(base, relative):
    if base not in (steam_client.CDN + '/', DEBIAN_BASE):
        raise ValueError('unreviewed source origin')
    if any(not re.fullmatch(r'[A-Za-z0-9_+.~-]+', p) or p in ('.', '..')
           for p in relative.split('/')):
        raise ValueError('unsafe official source path')
    url = base + relative
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != 'https' or parsed.username or parsed.password or parsed.port
            or parsed.query or parsed.fragment):
        raise ValueError('invalid official URL')
    return url


def inputs():
    _, client = read_lock(ROOT / 'ipa/steam-client.lock.json')
    _, deps = read_lock(ROOT / 'ipa/steam-dependencies.lock.json')
    gui_bytes, gui = read_lock(ROOT / 'ipa/gui-inputs.lock.json')
    steam_client.validate(client)
    spec = importlib.util.spec_from_file_location('download_dependencies', ROOT / 'guest/steam/install-cached.py')
    common = importlib.util.module_from_spec(spec); spec.loader.exec_module(common)
    try:
        packages = common.dependencies(deps)
    except common.Failure as error:
        raise ValueError('invalid dependency lock') from error
    if (deps.get('gui_inputs_sha256') != hashlib.sha256(gui_bytes).hexdigest()
            or deps.get('release') != gui.get('release')
            or deps['release'].get('url') != DEBIAN_RELEASE):
        raise ValueError('Debian source provenance binding mismatch')
    rows = packer.cache.entries(client, packages)
    urls = {'client/' + p['file']: official_url(client['manifest_url'].rsplit('/', 1)[0] + '/', p['file'])
            for p in client['parts']}
    urls.update({'debs/' + Path(p['filename']).name: official_url(DEBIAN_BASE, p['filename'])
                 for p in packages})
    if set(urls) != {r['name'] for r in rows}:
        raise ValueError('source URL set mismatch')
    packer.cache.archive_size(rows)
    return rows, urls


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('official source redirect refused; source review required')


def opener():
    # Normal CA/hostname verification; no credentials or alternate transport.
    return urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect(),
                                      urllib.request.HTTPSHandler(context=ssl.create_default_context()))


def checked(path, row):
    safe_path(path)
    before = packer.regular(path)
    if before.st_size != row['size']:
        raise ValueError('cached input size mismatch: ' + row['name'])
    h = hashlib.sha256(); count = 0
    with packer.open_regular(path) as stream:
        while chunk := stream.read(min(CHUNK, row['size'] - count + 1)):
            count += len(chunk)
            if count > row['size']:
                raise ValueError('cached input grew')
            h.update(chunk)
    if (count != row['size'] or h.hexdigest() != row['sha256']
            or packer.identity(packer.regular(path)) != packer.identity(before)):
        raise ValueError('cached input digest or identity mismatch: ' + row['name'])


def publish(stage, destination, validate):
    safe_path(destination)
    try:
        steam_client.publish(stage, destination)
    except FileExistsError:
        validate(destination)  # A concurrent valid publication may be reused, never replaced.


def download(row, url, destination, source):
    safe_path(destination)
    if os.path.lexists(destination):
        checked(destination, row)
        return False
    fd, temporary = tempfile.mkstemp(prefix='.ideck-download-', dir=destination.parent)
    temporary = Path(temporary)
    try:
        count = 0; digest = hashlib.sha256(); started = time.monotonic()
        with os.fdopen(fd, 'wb') as target, source.open(url, timeout=60) as response:
            if response.status != 200 or response.geturl() != url:
                raise ValueError('unexpected official response status or URL')
            length = response.headers.get('Content-Length')
            if length is not None and (not re.fullmatch(r'[0-9]+', length) or int(length) != row['size']):
                raise ValueError('official response length differs from lock')
            encoding = response.headers.get('Content-Encoding')
            if encoding not in (None, 'identity'):
                raise ValueError('encoded official response refused')
            while chunk := response.read(min(CHUNK, row['size'] - count + 1)):
                if time.monotonic() - started > 15 * 60:
                    raise ValueError('component download time bound')
                count += len(chunk)
                if count > row['size']:
                    raise ValueError('official response exceeds lock')
                digest.update(chunk); target.write(chunk)
            if count != row['size'] or digest.hexdigest() != row['sha256']:
                raise ValueError('official response size or SHA-256 mismatch')
            target.flush(); os.fsync(target.fileno())
        checked(temporary, row)
        publish(temporary, destination, lambda p: checked(p, row))
        checked(destination, row)
        return True
    finally:
        temporary.unlink(missing_ok=True)


def prepare(directory):
    rows, urls = inputs()
    directory = directory.absolute()
    safe_path(directory)
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    output = directory / 'owner-steam-cache.tar'
    safe_path(output)
    if os.path.lexists(output):
        packer.verify(output, rows)
    else:
        missing = 0
        for group in ('client', 'debs'):
            folder = directory / group
            safe_path(folder); folder.mkdir(mode=0o700, exist_ok=True)
        for row in rows:
            path = directory / row['name']
            if os.path.lexists(path): checked(path, row)
            else: missing += row['size']
        if shutil.disk_usage(directory).free < missing + packer.cache.archive_size(rows) + 1024**3:
            raise ValueError('insufficient preparation space (1 GiB reserve required)')
        source = opener()
        for index, row in enumerate(rows, 1):
            downloaded = download(row, urls[row['name']], directory / row['name'], source)
            print(f'{index}/{len(rows)} {row["name"]}: {"downloaded and verified" if downloaded else "verified existing"}', flush=True)
        # Keep packer's intermediate link private; only a verified single-link file reaches output.
        with tempfile.TemporaryDirectory(prefix='.ideck-pack-', dir=directory) as temp:
            stage = Path(temp) / 'cache.tar'
            packer.pack(directory / 'client', directory / 'debs', stage, rows)
            publish(stage, output, lambda p: packer.verify(p, rows))
        packer.verify(output, rows)
    return {'path': str(output), 'size': packer.regular(output).st_size,
            'sha256': packer.digest_file(output), 'parts': len(rows),
            'client_executed': False, 'agreement_accepted': False, 'owner_local_only': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', required=True, type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(prepare(args.directory), indent=2))
    except urllib.error.HTTPError as error:
        print('DOWNLOAD_FAILED: HTTP ' + str(error.code) + '; exact pins retained', file=sys.stderr)
        return 1
    except ValueError as error:
        print('PREPARATION_REFUSED: ' + str(error), file=sys.stderr)
        return 1
    except (OSError, urllib.error.URLError) as error:
        # Do not echo proxy settings, response bodies, local paths or credential-bearing errors.
        print('PREPARATION_FAILED: ' + type(error).__name__ + '; verified files retained; rerun the same command', file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print('PREPARATION_INTERRUPTED: rerun the same command; verified files retained', file=sys.stderr)
        return 130
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
