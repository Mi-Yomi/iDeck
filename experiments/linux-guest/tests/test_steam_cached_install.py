"""No-network/no-dpkg checks for the explicit private-QEMU cache installer."""
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('steam_cached_install', ROOT / 'guest/steam/install-cached.py')
guest = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guest)


class CachedSteamInstall(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ideck-private-cache-test-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.body = b'hashed private fixture'
        self.hash = hashlib.sha256(self.body).hexdigest()

    def test_endpoint_is_fixed_qemu_alias_and_explicit_high_port(self):
        self.assertEqual(guest.cache_url(8123, 'debs', 'liba_1+2_arm64.deb'),
                         'http://10.0.2.2:8123/debs/liba_1%2B2_arm64.deb')
        for port, group, name in ((80, 'debs', 'a'), (65536, 'debs', 'a'), (True, 'debs', 'a'),
                                  (8123, 'else', 'a'), (8123, 'debs', '../a'), (8123, 'client', 'a?b')):
            with self.subTest(port=port, group=group, name=name), self.assertRaises(guest.Failure):
                guest.cache_url(port, group, name)

    def test_every_redirect_is_refused_in_private_cache_mode(self):
        with self.assertRaisesRegex(guest.Failure, 'redirect'):
            guest.NoRedirect().redirect_request(None, None, 302, 'Found', {}, 'https://official.invalid/file')

    def response(self, body):
        result = io.BytesIO(body)
        result.status = 200
        return result

    def test_actual_cache_bytes_verified_then_reused_without_network(self):
        opener = Mock()
        opener.open.return_value = self.response(self.body)
        with patch.object(guest.urllib.request, 'build_opener', return_value=opener):
            path = guest.fetch(8123, 'client', 'fixture.zip', len(self.body), self.hash, self.root)
        self.assertEqual(path.read_bytes(), self.body)
        with patch.object(guest.urllib.request, 'build_opener', side_effect=AssertionError('must use cache')):
            self.assertEqual(guest.fetch(8123, 'client', 'fixture.zip', len(self.body), self.hash, self.root), path)
        self.assertEqual(list(self.root.glob('.private-cache-*')), [])

    def test_short_extra_corrupt_response_never_published(self):
        for body in (self.body[:-1], self.body + b'x', bytes(len(self.body))):
            opener = Mock()
            opener.open.return_value = self.response(body)
            with patch.object(guest.urllib.request, 'build_opener', return_value=opener):
                with self.assertRaises(guest.Failure):
                    guest.fetch(8123, 'debs', 'fixture.deb', len(self.body), self.hash, self.root)
            self.assertEqual(list(self.root.iterdir()), [])

    def test_bad_existing_cache_is_not_repaired(self):
        path = self.root / 'fixture.deb'
        path.write_bytes(b'preserve')
        with patch.object(guest.urllib.request, 'build_opener', side_effect=AssertionError('no repair')):
            with self.assertRaises(guest.Failure):
                guest.fetch(8123, 'debs', path.name, len(self.body), self.hash, self.root)
        self.assertEqual(path.read_bytes(), b'preserve')

    def test_dpkg_audit_requires_zero_and_exactly_empty_streams(self):
        for rc, out, err in ((1, b'', b''), (0, b'\n', b''), (0, b'', b'warning')):
            with patch.object(guest.subprocess, 'run', return_value=Mock(returncode=rc, stdout=out, stderr=err)):
                with self.assertRaisesRegex(guest.Failure, 'audit'):
                    guest.audit()
        with patch.object(guest.subprocess, 'run', return_value=Mock(returncode=0, stdout=b'', stderr=b'')):
            guest.audit()

    def test_inventory_requires_installed_and_preserves_version(self):
        with patch.object(guest.subprocess, 'run', return_value=Mock(returncode=0, stdout=b'liba\t1:2-3\tinstalled\n')):
            self.assertEqual(guest.installed(), {'liba': '1:2-3'})
        for output in (b'liba\t1\tunpacked\n', b'liba\t1\tinstalled\nliba\t2\tinstalled\n'):
            with patch.object(guest.subprocess, 'run', return_value=Mock(returncode=0, stdout=output)):
                with self.assertRaises(guest.Failure):
                    guest.installed()

    def test_exact_dependency_lock_and_invalid_inputs(self):
        lock = json.loads((ROOT / 'ipa/steam-dependencies.lock.json').read_text())
        self.assertEqual(len(guest.dependencies(lock)), 41)
        for field, value in (('name', '-bad'), ('architecture', 'amd64'), ('filename', 'pool/../escape.deb'),
                             ('sha256', 'bad'), ('size', True)):
            changed = copy.deepcopy(lock)
            changed['extra_packages'][0][field] = value
            with self.subTest(field=field), self.assertRaises(guest.Failure):
                guest.dependencies(changed)

    def test_existing_client_stops_before_any_dpkg_or_download(self):
        destination = self.root / 'Steam'
        destination.mkdir()
        (destination / 'userdata').write_bytes(b'untouched')
        with patch.object(guest, 'DEST', destination), patch.object(guest.os, 'geteuid', return_value=0, create=True), \
             patch.object(guest.subprocess, 'run', side_effect=AssertionError('must stop before dpkg')):
            with self.assertRaisesRegex(guest.Failure, 'client_already_exists'):
                guest.install(8123, {})
        self.assertEqual((destination / 'userdata').read_bytes(), b'untouched')

    def cleanup_pins(self):
        pins = []
        for name, content in (('first.zip', b'first'), ('second.zip', b'second')):
            (self.root / name).write_bytes(content)
            pins.append({'file': name, 'size': len(content), 'sha256': hashlib.sha256(content).hexdigest()})
        return pins

    def test_cleanup_removes_only_verified_pins_and_preserves_foreign_files(self):
        pins = self.cleanup_pins()
        foreign = self.root / 'userdata'
        foreign.write_bytes(b'preserve')
        count = guest.cleanup_client_cache(self.root, pins, owner=self.root.stat().st_uid)
        self.assertEqual(count, 2)
        self.assertEqual(list(self.root.iterdir()), [foreign])
        self.assertEqual(foreign.read_bytes(), b'preserve')

    def test_cleanup_validates_every_hash_before_any_deletion(self):
        pins = self.cleanup_pins()
        (self.root / 'second.zip').write_bytes(b'CORRUPT')
        with self.assertRaisesRegex(guest.Failure, 'integrity'):
            guest.cleanup_client_cache(self.root, pins, owner=self.root.stat().st_uid)
        self.assertEqual((self.root / 'first.zip').read_bytes(), b'first')
        self.assertEqual((self.root / 'second.zip').read_bytes(), b'CORRUPT')

    def test_cleanup_refuses_wrong_owner_and_missing_last_pin_before_deletion(self):
        pins = self.cleanup_pins()
        with self.assertRaisesRegex(guest.Failure, 'unsafe'):
            guest.cleanup_client_cache(self.root, pins, owner=self.root.stat().st_uid + 1)
        (self.root / 'second.zip').unlink()
        with self.assertRaisesRegex(guest.Failure, 'integrity'):
            guest.cleanup_client_cache(self.root, pins, owner=self.root.stat().st_uid)
        self.assertEqual((self.root / 'first.zip').read_bytes(), b'first')


if __name__ == '__main__':
    unittest.main()
