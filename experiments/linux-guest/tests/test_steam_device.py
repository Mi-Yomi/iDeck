"""Device source/IO regressions; no Apple, Steam execution or game claims."""
import copy
import gzip
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import urllib.error
import socket
import zipfile
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import prepare_steam_bootstrap as bootstrap
import steam_bundle as bundle
import steam_client as client

spec = importlib.util.spec_from_file_location('official_install', ROOT / 'guest/steam/install-official.py')
official = importlib.util.module_from_spec(spec)
spec.loader.exec_module(official)


class SteamDevice(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_persistent_bootstrap_has_no_growth_and_preserves_original_stop(self):
        original = (ROOT / 'guest/gui/ideck-desktop-init').read_bytes()
        result = bootstrap.persistent_init(original)
        stop = original[original.index(b'shutdown() {'):original.index(b'trap shutdown USR2 TERM INT')]
        self.assertIn(stop, result)
        for absent in (b'resize2fs', b'mkfs', b'steam_disk_grow=1', b'b66e1c8d-9cbf-45a7-b97b-dcc8f68efca7'):
            self.assertNotIn(absent, result)
        for present in (b'IDECK_STOP_V1', b'IDECK_STEAM_INSTALL', b'IDECK_STEAM_BIG_PICTURE', b'IDECK_STEAM_DESKTOP',
                        b'ideck.steam_persistent=1 ideck.steam_network=1', b'grep -qw atomics', b'/lse-probe', bootstrap.STEAM_UUID.encode()):
            self.assertIn(present, result)
        self.assertLess(result.index(b'IDECK_DESKTOP_RECOVERY_READY'), result.index(b'grep -qw atomics'))
        self.assertEqual(subprocess.run(['/bin/sh', '-n'], input=result, capture_output=True).returncode, 0)

    def test_persistent_gate_denies_before_any_network_or_disk_mutation(self):
        original = (ROOT / 'guest/gui/ideck-desktop-init').read_bytes()
        result = bootstrap.persistent_init(original)
        inject = result[result.index(bootstrap.MARKER) + len(bootstrap.MARKER):result.index(b'chroot /sysroot /bin/hostname')]
        for cmdline in ('console=ttyAMA0', 'ideck.steam_experiment=1', 'ideck.steam_experiment=1 ideck.steam_persistent=1'):
            script = b'fail() { exit 23; }; cat() { echo "' + cmdline.encode() + b'"; }; exec 3>/dev/null\n' + inject
            self.assertEqual(subprocess.run(['/bin/sh'], input=script, capture_output=True).returncode, 23)

    def test_only_official_tls_endpoints_and_redirects(self):
        for url in ('https://deb.debian.org/debian/pool/main/a.deb', client.CDN + '/part'):
            self.assertEqual(official.official_url(url), url)
        for url in ('http://deb.debian.org/file', 'http://10.0.2.2:8080/client', 'file:///tmp/a',
                    'https://evil.invalid/part', 'https://deb.debian.org:444/a', 'https://u:p@deb.debian.org/a',
                    'https://deb.debian.org/a?key=x'):
            with self.assertRaises(official.Failure):
                official.official_url(url)
        with self.assertRaises(official.Failure):
            official.OfficialRedirect().redirect_request(None, None, 302, 'Found', {}, 'http://deb.debian.org/a')

    def test_https_hash_download_restart_and_bad_cache_preservation(self):
        content = b'official response fixture'
        checksum = hashlib.sha256(content).hexdigest()
        temp = self.root / '.download-fixture.deb.partial'
        temp.write_bytes(b'interrupted')
        temp.chmod(0o600)
        response = io.BytesIO(content)
        response.status = 200
        opener = Mock()
        opener.open.return_value = response
        with patch.object(official.urllib.request, 'build_opener', return_value=opener):
            result = official.fetch('https://deb.debian.org/debian/fixture.deb', 'fixture.deb', len(content), checksum, self.root)
        self.assertEqual(result.read_bytes(), content)
        self.assertFalse(temp.exists())
        result.write_bytes(b'preserve corrupt input')
        with self.assertRaises(official.Failure):
            official.fetch('https://deb.debian.org/debian/fixture.deb', 'fixture.deb', len(content), checksum, self.root)
        self.assertEqual(result.read_bytes(), b'preserve corrupt input')

    def test_resumable_partial_symlink_cannot_touch_outside(self):
        outside = self.root / 'preserve'
        outside.write_bytes(b'user data')
        (self.root / '.download-fixture.deb.partial').symlink_to(outside)
        with self.assertRaisesRegex(official.Failure, 'unsafe_interrupted'):
            official.fetch('https://deb.debian.org/debian/fixture.deb', 'fixture.deb', 1, 'a' * 64, self.root)
        self.assertEqual(outside.read_bytes(), b'user data')

    def test_only_pinned_additions_can_resume_incomplete_dpkg_state(self):
        pins = [{'name': 'new-lib', 'version': '2'}]
        base = {'gui': '1'}
        good = 'gui\t1\tinstalled\nnew-lib\t2\tunpacked\n'
        self.assertEqual(official.inventory(base, pins, good), {'gui': '1', 'new-lib': '2'})
        for output in (good.replace('gui\t1', 'gui\t2'), good.replace('gui\t1\tinstalled', 'gui\t1\tunpacked'),
                       good + 'foreign\t1\tunpacked\n', good.replace('new-lib\t2', 'new-lib\t3'), 'new-lib\t2\tinstalled\n'):
            with self.assertRaises(official.Failure):
                official.inventory(base, pins, output)

    def test_dns_failure_is_an_exact_secret_free_blocker(self):
        opener = Mock()
        opener.open.side_effect = urllib.error.URLError(socket.gaierror(-3, 'private detail'))
        with patch.object(official.urllib.request, 'build_opener', return_value=opener):
            with self.assertRaisesRegex(official.Failure, '^official_dns_failed$'):
                official.fetch('https://deb.debian.org/debian/fixture.deb', 'fixture.deb', 1, 'a' * 64, self.root)

    def test_actual_journal_resumes_dependency_and_client_publication_interruptions(self):
        # Real journal/ZIP/publication/link IO, synthetic root/dpkg/network boundary.
        state, opt, home = [self.root / name for name in ('state', 'opt', 'home')]
        opt.mkdir(); home.mkdir()
        dest = home / '.local/share/Steam'
        elf = bytearray(64); elf[:6] = b'\x7fELF\x02\x01'; elf[18:20] = (183).to_bytes(2, 'little')
        data = io.BytesIO()
        with zipfile.ZipFile(data, 'w') as archive:
            archive.writestr('steamrtarm64/steam', bytes(elf))
        zipped = data.getvalue()
        part = {'component': 'bins_linuxarm64_linuxarm64', 'file': 'bins_linuxarm64_linuxarm64.zip.' + '0' * 40,
                'size': len(zipped), 'sha256': hashlib.sha256(zipped).hexdigest()}
        lock = {'schema': 1, 'kind': 'private-steam-arm64-experiment', 'channel': 'steamdeck_publicbeta',
                'version': '1792192922', 'redistribution_approved': False, 'manifest_url': client.CDN + '/' + client.MANIFEST,
                'manifest_sha256': 'a' * 64, 'parts': [part]}
        (opt / 'steam-client.lock.json').write_text(json.dumps(lock))
        (opt / 'steam-dependencies.lock.json').write_text('{}')
        pins = [{'name': 'added', 'version': '2', 'filename': 'pool/a.deb', 'size': 3, 'sha256': hashlib.sha256(b'deb').hexdigest()}]
        safe = official.common.safe_directory
        lstat = Path.lstat
        def fixture_lstat(path):
            row = lstat(path)
            if path == state / 'journal.json':
                values = list(row); values[4] = 0
                return os.stat_result(values)
            return row
        calls = []
        client_attempt = 0
        def process(args, **kwargs):
            nonlocal client_attempt
            calls.append(args[0])
            if args[0] == 'dpkg-query':
                return Mock(stdout=b'gui\t1\tinstalled\nadded\t2\tinstalled\n', returncode=0)
            if args[0] == 'setpriv':
                client_attempt += 1
                if client_attempt == 1:
                    raise OSError('interrupted before client publication')
                client.install(lock, Path(args[args.index('--cache') + 1]), dest, resume=True)
            return Mock(returncode=0)
        def transfer(url, name, size, checksum, directory):
            safe(directory)
            target = directory / name
            body = zipped if name == part['file'] else b'deb'
            if not target.exists(): target.write_bytes(body)
            official.common.checked(target, size, checksum)
            return target
        save = official.save
        def fail_after_publication(journal):
            if journal['phase'] == 'links':
                raise OSError('interrupted after client publication')
            save(journal)
        with patch.object(official, 'STATE', state), patch.object(official, 'OPT', opt), \
             patch.object(official, 'CACHE', self.root / 'cache'), \
             patch.object(official, 'HOME', home), patch.object(official, 'DEST', dest), \
             patch.object(official.common, 'HOME', home), patch.object(official.common, 'DEST', dest), \
             patch.object(official.common, 'LOG', self.root / 'logs'), \
             patch.object(official.common, 'safe_directory', side_effect=lambda p, owner=None: safe(p)), \
             patch.object(official.common, 'dependencies', return_value=pins), \
             patch.object(official.common, 'installed', side_effect=[{'gui': '1'}, {'gui': '1', 'added': '2'}]), \
             patch.object(official.common, 'audit'), patch.object(official.os, 'geteuid', return_value=0), \
             patch.object(official.os, 'sync'), patch.object(Path, 'lstat', fixture_lstat), \
             patch.object(official, 'fetch', side_effect=transfer), patch.object(official.subprocess, 'run', side_effect=process):
            with self.assertRaises(OSError): official.install()
            self.assertEqual(json.loads((state / 'journal.json').read_text())['phase'], 'client')
            self.assertFalse(dest.exists())
            with patch.object(official, 'save', side_effect=fail_after_publication):
                with self.assertRaises(OSError): official.install()
            self.assertTrue((dest / 'steamrtarm64/steam').is_file())
            sentinel = dest / 'userdata'; sentinel.write_bytes(b'preserved')
            official.install()
            self.assertEqual(json.loads((state / 'journal.json').read_text())['phase'], 'ready')
            self.assertEqual(sentinel.read_bytes(), b'preserved')
            self.assertEqual(calls.count('dpkg'), 1)
            self.assertEqual(calls.count('setpriv'), 2)
            official.install()  # A completed installation is never replaced.
            self.assertEqual(sentinel.read_bytes(), b'preserved')

    def test_journal_atomic_save_and_lock_bindings(self):
        with patch.object(official, 'STATE', self.root):
            official.save({'schema': 1, 'phase': 'dependencies'})
            self.assertEqual(json.loads((self.root / 'journal.json').read_text())['phase'], 'dependencies')
            official.save({'schema': 1, 'phase': 'client'})
            self.assertFalse((self.root / 'journal.partial').exists())
            self.assertEqual(json.loads((self.root / 'journal.json').read_text())['phase'], 'client')

    def test_existing_client_without_matching_journal_is_never_repaired(self):
        dest = self.root / 'Steam'
        dest.mkdir()
        (dest / 'userdata').write_bytes(b'preserve')
        with patch.object(official, 'DEST', dest):
            with self.assertRaisesRegex(official.Failure, 'not_owned'):
                official.published_client({'phase': 'dependencies'}, {'manifest_sha256': 'a' * 64})
        self.assertEqual((dest / 'userdata').read_bytes(), b'preserve')

    def test_missing_published_client_is_never_automatically_recreated(self):
        with patch.object(official, 'DEST', self.root / 'missing'):
            for phase in ('links', 'ready'):
                with self.assertRaisesRegex(official.Failure, 'missing_no_repair'):
                    official.published_client({'phase': phase}, {})
            self.assertFalse(official.published_client({'phase': 'client'}, {}))

    def test_blocked_asset_stage_is_honest_and_incremental(self):
        lock = ROOT / 'ipa/steam.lock.json'
        out = self.root / 'bundle'
        result = bundle.prepare_for_build(out, lock, self.root)
        self.assertEqual(result['blocker'], 'STEAM_PAYLOAD_NOT_SEALED')
        self.assertEqual({p.name for p in out.iterdir()}, {'STEAM-BLOCKER.txt'})
        bundle.stage(None, out, lock)
        (out / 'steam-profile.json').write_text('{}')
        with self.assertRaises(ValueError):
            bundle.verify(out, bundle.load_lock(lock))

    def test_payload_scope_cannot_enable_gui_or_bundle_client(self):
        lock = json.loads((ROOT / 'ipa/steam.lock.json').read_text())
        for field, value in [('disk_size_bytes', 16 * 1024**3), ('disk_uuid', 'other'), ('valve_client_bundled', True),
                             ('status', 'ready')]:
            bad = dict(lock, **{field: value})
            path = self.root / 'lock.json'
            path.write_text(json.dumps(bad))
            with self.assertRaises(ValueError):
                bundle.load_lock(path)

    def test_device_ui_and_single_owner_have_real_route_and_actions(self):
        source = (ROOT / 'ios/LinuxTerminalSession.swift').read_text()
        probe = (ROOT / 'ios/LinuxProbeSession.swift').read_text()
        self.assertIn('!LinuxTerminalSession.steam.attempted', source)
        self.assertIn('!LinuxTerminalSession.steam.attempted', probe)
        self.assertIn('"iDeckSteam-v1"', source)
        self.assertIn('self.control?.enqueue', source)
        self.assertIn('os_proc_available_memory()', source)
        view = (ROOT / 'ios/LinuxDesktopView.swift').read_text()
        for verb in ('INSTALL', 'BIG_PICTURE', 'DESKTOP'):
            self.assertIn('session.steamAction("' + verb + '")', view)
        self.assertIn('!session.steamPayloadAvailable', view)
        profile = (ROOT / 'ios/LinuxSteamProfile.swift').read_text()
        self.assertIn('gzdopen(compressed', profile)
        self.assertIn('expanded <= size', profile)
        self.assertIn('== digest', profile)


if __name__ == '__main__':
    unittest.main()
