#!/usr/bin/env python3
"""Device installer: pinned official HTTPS only; resumable, never accepts terms."""
import fcntl
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import socket
import ssl
import stat
import subprocess
import urllib.error
import urllib.parse
import urllib.request

import steam_client as client

spec = importlib.util.spec_from_file_location('cached_install', Path(__file__).with_name('install-cached.py'))
common = importlib.util.module_from_spec(spec)
spec.loader.exec_module(common)
Failure = common.Failure
STATE = Path('/var/lib/ideck-steam')
CACHE = Path('/var/cache/ideck-steam')
OPT = Path('/opt/ideck-steam')
DEST = common.DEST
HOME = common.HOME


def official_url(url):
    p = urllib.parse.urlsplit(url)
    if (p.scheme != 'https' or p.hostname not in client.HOSTS | {'deb.debian.org'}
            or p.port not in (None, 443) or p.username or p.password or p.fragment or p.query):
        raise Failure('unapproved_official_https_url')
    return url


class OfficialRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return super().redirect_request(req, fp, code, msg, headers, official_url(newurl))


def fetch(url, name, size, checksum, directory):
    official_url(url)
    # Reuse the bounded hash/size/no-replace downloader, with an explicit HTTPS
    # endpoint and normal certificate verification instead of its host cache.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), OfficialRedirect(),
                                        urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    try:
        return common.fetch(8080, 'debs', name, size, checksum, directory,
                            official_url=url, official_opener=opener, resume=True)
    except urllib.error.HTTPError as error:
        raise Failure('official_http_status_' + str(error.code)) from None
    except urllib.error.URLError as error:
        if isinstance(error.reason, socket.gaierror):
            raise Failure('official_dns_failed') from None
        if isinstance(error.reason, ssl.SSLError):
            raise Failure('official_tls_verification_failed') from None
        raise Failure('official_https_connection_failed') from None
    except TimeoutError:
        raise Failure('official_https_timeout') from None


def save(journal):
    temp = STATE / 'journal.partial'
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as out:
        json.dump(journal, out, sort_keys=True)
        out.flush()
        os.fsync(out.fileno())
    os.replace(temp, STATE / 'journal.json')
    fd = os.open(STATE, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def inventory(baseline, pins, output):
    """Only the pinned additions may be incompletely configured on a retry."""
    allowed = {p['name']: p['version'] for p in pins}
    found = {}
    for line in output.splitlines():
        name, version, status = line.split('\t')
        if name in found:
            raise Failure('duplicate_package')
        if name in baseline:
            if version != baseline[name] or status != 'installed':
                raise Failure('existing_gui_packages_changed')
        elif name not in allowed or version != allowed[name] or status not in (
                'installed', 'unpacked', 'half-configured', 'half-installed', 'triggers-pending', 'triggers-awaited'):
            raise Failure('unrelated_or_conflicting_package_state')
        found[name] = version
    if not baseline.keys() <= found.keys():
        raise Failure('missing_gui_packages')
    return found


def published_client(journal, lock):
    if not os.path.lexists(DEST):
        if journal.get('phase') in ('links', 'ready'):
            raise Failure('published_client_missing_no_repair')
        return False
    if journal.get('phase') not in ('client', 'links', 'ready'):
        raise Failure('existing_client_not_owned_by_install_journal')
    common.safe_directory(DEST, 1000)
    receipt = DEST / 'package/ideck-install.json'
    if any(p.is_symlink() for p in (receipt, receipt.parent)) or not receipt.is_file():
        raise Failure('client_publication_receipt_missing')
    row = json.loads(receipt.read_text())
    if row.get('manifest_sha256') != lock['manifest_sha256'] or row.get('agreement_accepted') is not False:
        raise Failure('client_publication_receipt_mismatch')
    binary = DEST / 'steamrtarm64/steam'
    if binary.is_symlink() or not binary.is_file() or binary.stat().st_uid != 1000:
        raise Failure('client_missing_or_wrong_owner')
    return True


def install():
    if os.geteuid() != 0:
        raise Failure('requires_guest_root')
    common.safe_directory(STATE, 0)
    fd = os.open(STATE / 'install.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'r+') as held:
        try:
            fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Failure('installer_busy') from None
        deps = json.loads((OPT / 'steam-dependencies.lock.json').read_text())
        pins = common.dependencies(deps)
        lock = client.validate(json.loads((OPT / 'steam-client.lock.json').read_text()))
        bindings = {name: common.digest(OPT / name) for name in ('steam-dependencies.lock.json', 'steam-client.lock.json')}
        path = STATE / 'journal.json'
        if os.path.lexists(path):
            meta = path.lstat()
            if not stat.S_ISREG(meta.st_mode) or meta.st_uid != 0 or meta.st_nlink != 1 or meta.st_size > 65536:
                raise Failure('unsafe_install_journal')
            journal = json.loads(path.read_text())
            if journal.get('bindings') != bindings or journal.get('schema') != 1:
                raise Failure('installation_lock_changed')
        else:
            if os.path.lexists(DEST) or any(os.path.lexists(p) for p in common.links()):
                raise Failure('existing_client_no_replacement')
            before = common.installed()
            common.audit()
            if any(p['name'] in before and before[p['name']] != p['version'] for p in pins):
                raise Failure('existing_package_version_conflict')
            journal = {'schema': 1, 'bindings': bindings, 'baseline': before, 'phase': 'dependencies'}
            save(journal)
        published = published_client(journal, lock)
        if journal['phase'] == 'ready':
            if not published:
                raise Failure('installed_client_missing_no_repair')
            return
        common.safe_directory(common.LOG, 0)
        result = subprocess.run(['dpkg-query', '-W', '-f=${Package}\t${Version}\t${db:Status-Status}\n'], capture_output=True, check=True)
        inventory(journal['baseline'], pins, result.stdout.decode())
        # Downloads, expanded client and updater reserve. No sparse-space promise.
        required = sum(p['size'] for p in pins) + sum(p['size'] for p in lock['parts']) + 5 * 1024**3
        if not published and shutil.disk_usage(HOME).free < required:
            raise Failure('insufficient_guest_space_5gib_expansion_and_update_reserve')
        if journal['phase'] == 'dependencies':
            cache = CACHE / 'debs'
            debs = [fetch('https://deb.debian.org/debian/' + p['filename'], PurePosixPath(p['filename']).name,
                          p['size'], p['sha256'], cache) for p in pins if p['name'] not in journal['baseline']]
            env = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'HOME': '/root', 'LANG': 'C.UTF-8', 'DEBIAN_FRONTEND': 'noninteractive'}
            with (common.LOG / 'dpkg.log').open('ab') as out:
                if debs:
                    subprocess.run(['dpkg', '-i', *map(str, debs)], env=env, stdout=out, stderr=subprocess.STDOUT, check=True)
            common.audit()
            after = common.installed()
            if any(after.get(k) != v for k, v in journal['baseline'].items()) or any(after.get(p['name']) != p['version'] for p in pins):
                raise Failure('post_install_package_mismatch')
            journal['phase'] = 'client'
            save(journal)
        cache = CACHE / 'client'
        common.safe_directory(HOME / '.steam', 1000)
        common.safe_directory(DEST.parent, 1000)
        if not published:
            common.safe_directory(cache, 0)
            cache.chmod(0o755)
            for p in lock['parts']:
                part = fetch(client.CDN + '/' + p['file'], p['file'], p['size'], p['sha256'], cache)
                part.chmod(0o644)
            args = ['setpriv', '--reuid=1000', '--regid=1000', '--init-groups', 'env', '-i',
                    'HOME=' + str(HOME), 'PATH=/usr/local/bin:/usr/bin:/bin', 'PYTHONDONTWRITEBYTECODE=1',
                    'python3', str(OPT / 'steam_client.py'), 'install', '--resume', '--lock',
                    str(OPT / 'steam-client.lock.json'), '--cache', str(cache), '--destination', str(DEST)]
            with (common.LOG / 'client-install.log').open('ab') as out:
                subprocess.run(args, stdout=out, stderr=subprocess.STDOUT, check=True)
        journal['phase'] = 'links'
        save(journal)
        for link, target in {**common.links(), DEST / 'steamrtarm32': DEST / 'steamrtarm64'}.items():
            if os.path.lexists(link):
                if not link.is_symlink() or os.readlink(link) != str(target):
                    raise Failure('steam_link_conflict_no_replacement')
            else:
                link.symlink_to(target)
                os.lchown(link, 1000, 1000)
        # Retain verified ZIPs for bounded retry; never erase user/account files.
        os.sync()
        journal['phase'] = 'ready'
        save(journal)


if __name__ == '__main__':
    try:
        install()
        print('IDECK_STEAM_INSTALLED', flush=True)
    except Exception as error:
        reason = str(error) if isinstance(error, Failure) else type(error).__name__
        print('IDECK_STEAM_BLOCKER:' + reason, flush=True)
        raise SystemExit(1)
