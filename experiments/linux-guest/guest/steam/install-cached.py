#!/usr/bin/env python3
"""Install pinned private-cache inputs in the NEW networked Steam guest only.

The HTTP endpoint is the explicit QEMU host alias, never a general TLS fallback.
Every byte is checked against independently captured official-source locks.
No client execution, agreement acceptance, login or automatic repair occurs.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request

OPT = Path('/opt/ideck-steam')
HOME = Path('/home/ideck')
DEST = HOME / '.local/share/Steam'
LOG = Path('/var/log/ideck-steam-install')


class Failure(Exception):
    pass


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def checked(path, size, checksum):
    if path.is_symlink() or not path.is_file() or path.stat().st_size != size or digest(path) != checksum:
        raise Failure('cache_integrity_failed')


def cleanup_client_cache(cache, pins, owner=1000, retain=False):
    """Delete only verified installed-client ZIP inputs; preserve unrelated files."""
    if (cache.is_symlink() or not cache.is_dir()
            or any(p.is_symlink() for p in cache.parents) or cache.stat().st_uid != owner):
        raise Failure('unsafe_client_cache_cleanup')
    verified = []
    names = set()
    for pin in pins:
        name = pin['file']
        cache_url(8080, 'client', name)
        if name in names:
            raise Failure('duplicate_client_cache_cleanup_pin')
        names.add(name)
        path = cache / name
        checked(path, pin['size'], pin['sha256'])
        metadata = path.stat()
        if metadata.st_uid != owner:
            raise Failure('wrong_client_cache_file_owner')
        verified.append((path, metadata))
    # Verify the entire set before deleting any file. Never remove the directory.
    for path, before in verified:
        after = path.lstat()
        if (path.is_symlink() or (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_uid)
                != (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, owner)):
            raise Failure('client_cache_changed_before_cleanup')
        if not retain:
            path.unlink()
    return len(verified)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise Failure('cache_redirect_refused')


def cache_url(port, group, name):
    if type(port) is not int or not 1024 <= port <= 65535 or group not in ('client', 'debs'):
        raise Failure('invalid_private_cache_endpoint')
    if not re.fullmatch(r'[A-Za-z0-9_.+~-]+', name) or name in ('.', '..'):
        raise Failure('invalid_cache_filename')
    return 'http://10.0.2.2:' + str(port) + '/' + group + '/' + urllib.parse.quote(name, safe='')


def fetch(port, group, name, size, checksum, directory, *, official_url=None, official_opener=None, resume=False):
    url = cache_url(port, group, name)
    if official_url is not None:
        if not official_url.startswith("https://") or official_opener is None:
            raise Failure("official_https_required")
        url = official_url
    if type(size) is not int or not 0 < size < 1024**3 or not re.fullmatch('[0-9a-f]{64}', checksum):
        raise Failure('invalid_cache_pin')
    safe_directory(directory)
    target = directory / name
    if os.path.lexists(target):
        checked(target, size, checksum)
        return target
    if resume:
        temporary = directory / ('.download-' + name + '.partial')
        if os.path.lexists(temporary):
            state = temporary.lstat()
            if (not stat.S_ISREG(state.st_mode) or state.st_nlink != 1 or state.st_uid != os.geteuid()
                    or stat.S_IMODE(state.st_mode) != 0o600):
                raise Failure('unsafe_interrupted_download')
            temporary.unlink()
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    else:
        fd, temporary = tempfile.mkstemp(prefix='.private-cache-', dir=directory)
        temporary = Path(temporary)
    try:
        opener = official_opener or urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        count = 0
        with os.fdopen(fd, 'wb') as out, opener.open(url, timeout=60) as response:
            if response.status != 200:
                raise Failure('cache_http_status')
            while block := response.read(1024 * 1024):
                count += len(block)
                if count > size:
                    raise Failure('cache_extra_bytes')
                out.write(block)
            out.flush()
            os.fsync(out.fileno())
        checked(temporary, size, checksum)
        os.link(temporary, target)
        return target
    finally:
        temporary.unlink(missing_ok=True)


def safe_directory(path, owner=None):
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise Failure('symlink_directory_refused')
    missing = []
    current = path
    while not current.exists():
        missing.append(current)
        current = current.parent
    if not current.is_dir():
        raise Failure('not_directory')
    for item in reversed(missing):
        item.mkdir(mode=0o700 if owner is not None else 0o755)
        if owner is not None:
            os.chown(item, owner, owner)
    if owner is not None and path.stat().st_uid != owner:
        raise Failure('wrong_directory_owner')


def dependencies(lock):
    if lock.get('schema') != 1 or lock.get('kind') != 'ideck-experimental-steam-dependencies' or lock.get('architecture') != 'arm64':
        raise Failure('invalid_dependency_lock')
    packages = lock.get('extra_packages', [])
    if len(packages) != 45:
        raise Failure('unexpected_dependency_count')
    names, files = set(), set()
    for p in packages:
        name = p.get('name', '')
        filename = p.get('filename', '')
        base = PurePosixPath(filename).name
        if (not re.fullmatch(r'[a-z0-9][a-z0-9+.-]*', name) or name in names
                or p.get('architecture') not in ('arm64', 'all')
                or not isinstance(p.get('version'), str) or not p['version']
                or not filename.startswith('pool/') or '..' in PurePosixPath(filename).parts
                or not base.endswith('.deb') or base in files
                or type(p.get('size')) is not int or not 0 < p['size'] < 1024**3
                or not re.fullmatch('[0-9a-f]{64}', p.get('sha256', ''))):
            raise Failure('invalid_dependency_pin')
        cache_url(8080, 'debs', base)
        names.add(name)
        files.add(base)
    return packages


def installed():
    result = subprocess.run(['dpkg-query', '-W', '-f=${Package}\t${Version}\t${db:Status-Status}\n'], capture_output=True)
    if result.returncode:
        raise Failure('package_inventory_failed')
    records = {}
    for line in result.stdout.decode('utf-8').splitlines():
        name, version, status = line.split('\t')
        if status != 'installed':
            raise Failure('existing_package_not_configured')
        if name in records:
            raise Failure('duplicate_installed_package')
        records[name] = version
    return records


def audit():
    result = subprocess.run(['dpkg', '--audit'], capture_output=True)
    if result.returncode != 0 or result.stdout != b'' or result.stderr != b'':
        raise Failure('dpkg_audit_failed')


def links():
    return {HOME / '.steam' / name: DEST / sub for name, sub in {
        'root': '', 'steam': '', 'bin64': 'steamrtarm64', 'sdk64': 'linuxarm64',
        'sdkarm64': 'linuxarm64', 'binarm64': 'steamrtarm64', 'sdk32': 'linux32',
    }.items()}


def install(port, report, retain_client_cache=False):
    if os.geteuid() != 0:
        raise Failure('requires_guest_root')
    if os.path.lexists(DEST):
        raise Failure('client_already_exists_no_repair')
    for link in links():
        if os.path.lexists(link):
            raise Failure('existing_steam_link_no_replacement')
    safe_directory(HOME / '.steam', 1000)
    safe_directory(DEST.parent, 1000)
    safe_directory(LOG)
    deps_path, client_path = OPT / 'steam-dependencies.lock.json', OPT / 'steam-client.lock.json'
    package_pins = dependencies(json.loads(deps_path.read_text()))
    spec = importlib.util.spec_from_file_location('private_steam_client', OPT / 'steam_client.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    client_lock = module.validate(json.loads(client_path.read_text()))
    if len(client_lock['parts']) != 17:
        raise Failure('unexpected_client_component_count')
    report['dependency_lock_sha256'], report['client_lock_sha256'] = digest(deps_path), digest(client_path)
    before = installed()
    audit()
    if any(p['name'] in before and before[p['name']] != p['version'] for p in package_pins):
        raise Failure('existing_package_version_conflict')
    debcache = Path('/var/cache/ideck-steam/debs')
    required = sum(p['size'] for p in package_pins) + sum(p['size'] for p in client_lock['parts']) + 1024**3
    if shutil.disk_usage(HOME).free < required:
        raise Failure('insufficient_guest_space')
    debs = [fetch(port, 'debs', PurePosixPath(p['filename']).name, p['size'], p['sha256'], debcache) for p in package_pins]
    report['verified_debs'] = len(debs)
    env = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'HOME': '/root', 'LANG': 'C.UTF-8', 'DEBIAN_FRONTEND': 'noninteractive'}
    with (LOG / 'dpkg.log').open('wb') as out:
        result = subprocess.run(['dpkg', '-i', *map(str, debs)], env=env, stdout=out, stderr=subprocess.STDOUT)
    report['dpkg_exit_code'] = result.returncode
    if result.returncode:
        raise Failure('dpkg_install_failed')
    audit()
    after = installed()
    if any(after.get(name) != version for name, version in before.items()):
        raise Failure('existing_gui_packages_changed')
    if any(after.get(p['name']) != p['version'] for p in package_pins):
        raise Failure('installed_dependency_version_mismatch')
    report['unchanged_existing_packages'] = len(before)
    report['dpkg_audit_empty'] = True
    parts_cache = HOME / '.cache/ideck-steam-parts'
    safe_directory(parts_cache, 1000)
    for p in client_lock['parts']:
        path = fetch(port, 'client', p['file'], p['size'], p['sha256'], parts_cache)
        os.chown(path, 1000, 1000)
    report['verified_client_parts'] = len(client_lock['parts'])
    args = ['setpriv', '--reuid=1000', '--regid=1000', '--init-groups', 'env', '-i',
            'HOME=' + str(HOME), 'USER=ideck', 'LOGNAME=ideck', 'PATH=/usr/local/bin:/usr/bin:/bin',
            'LANG=C.UTF-8', 'PYTHONDONTWRITEBYTECODE=1', 'python3', str(OPT / 'steam_client.py'),
            'install', '--lock', str(client_path), '--cache', str(parts_cache), '--destination', str(DEST)]
    with (LOG / 'client-install.log').open('wb') as out:
        result = subprocess.run(args, stdout=out, stderr=subprocess.STDOUT)
    report['client_installer_exit_code'] = result.returncode
    if result.returncode:
        raise Failure('client_installer_failed')
    for link, target in {**links(), DEST / 'steamrtarm32': DEST / 'steamrtarm64'}.items():
        if os.path.lexists(link):
            raise Failure('steam_link_conflict_no_replacement')
        link.symlink_to(target)
        os.lchown(link, 1000, 1000)
    cache_count = cleanup_client_cache(parts_cache, client_lock['parts'], retain=retain_client_cache)
    report['retained_verified_client_cache_parts' if retain_client_cache else
           'removed_verified_client_cache_parts'] = cache_count
    report['status'] = 'installed_private_client_not_launched'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--private-qemu-cache', action='store_true', required=True)
    parser.add_argument('--retain-client-cache', action='store_true',
                        help='Verify and preserve all pinned installer ZIPs after installation')
    args = parser.parse_args()
    cache_url(args.port, 'client', 'check')
    started = time.monotonic()
    report = {'status': 'failed', 'client_executed': False, 'agreement_accepted': False, 'login_performed': False}
    code = 1
    try:
        install(args.port, report, retain_client_cache=args.retain_client_cache)
        code = 0
    except Exception as error:
        report['failure_code'] = str(error) if isinstance(error, Failure) else 'guest_install_failed'
        report['exception_class'] = type(error).__name__
    finally:
        report['elapsed_seconds'] = round(time.monotonic() - started, 3)
        if LOG.is_dir() and not LOG.is_symlink():
            (LOG / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
        print('IDECK_STEAM_INSTALL=' + json.dumps(report, sort_keys=True))
    raise SystemExit(code)


if __name__ == '__main__':
    main()
