"""Offline review regressions; mocked privilege/network boundaries, no VM/CI."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import prepare_steam_bootstrap as bootstrap
import steam_bundle as bundle


def guest_module(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), ROOT / 'guest/steam' / (name + '.py'))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


official = guest_module('install-official')
action = guest_module('device-action')
API = 'https://api.github.com/repos/Mi-Yomi/iDeck/releases/assets/123'
FALLBACK = 'fixture-only-existing-debian-token'
PRIMARY = 'fixture-only-steam-token'


class Environment(dict):
    def __init__(self, values):
        super().__init__(values); self.reads = []
    def get(self, key, default=None):
        self.reads.append(key)
        return super().get(key, default)


class DeviceReview(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def fetch(self, values, lock_url=API, *, redirect=False):
        body = b'exact offline HTTPS transport fixture'
        lock = {'archive': {'size': len(body), 'sha256': hashlib.sha256(body).hexdigest()}, 'payload_url': lock_url}
        env = Environment(values); requests = []; output = io.StringIO()
        def open_request(request, timeout):
            requests.append(request)
            if redirect:
                target = bundle.HTTPSOnly().redirect_request(request, None, 302, 'Found', {},
                    'https://release-assets.githubusercontent.com/fixture')
                self.assertFalse(target.has_header('Authorization'))
            return io.BytesIO(body)
        target = self.root / ('payload-' + str(len(list(self.root.iterdir()))))
        with patch.object(bundle.os, 'environ', env), patch.object(bundle.urllib.request, 'build_opener') as factory, \
             contextlib.redirect_stdout(output):
            factory.return_value.open.side_effect = open_request
            try:
                bundle.fetch(target, lock); error = None
            except Exception as caught:
                error = caught
        for secret in (PRIMARY, FALLBACK):
            self.assertNotIn(secret, output.getvalue() + (str(error) if error else ''))
        if error is None: self.assertEqual(target.read_bytes(), body)
        else: self.assertFalse(target.exists())
        self.assertFalse(list(self.root.glob('.steam-payload-*')))
        self.assertEqual(dict(env), values)
        return env, requests, error

    def test_pinned_api_url_uses_existing_group_token_without_new_secret(self):
        env, requests, error = self.fetch({'IDECK_DEBIAN_PAYLOAD_TOKEN': FALLBACK}, redirect=True)
        self.assertIsNone(error)
        self.assertEqual(requests[0].full_url, API)
        self.assertEqual(requests[0].get_header('Authorization'), 'Bearer ' + FALLBACK)
        self.assertIn('IDECK_DEBIAN_PAYLOAD_TOKEN', env.reads)
        self.assertNotIn('IDECK_DEBIAN_PAYLOAD_URL', env.reads)

    def test_primary_token_and_explicit_transport_override_precede_fallback(self):
        url = API[:-3] + '456'
        env, requests, error = self.fetch({'IDECK_STEAM_PAYLOAD_URL': url,
            'IDECK_STEAM_PAYLOAD_TOKEN': PRIMARY, 'IDECK_DEBIAN_PAYLOAD_TOKEN': FALLBACK})
        self.assertIsNone(error)
        self.assertEqual(requests[0].full_url, url)
        self.assertEqual(requests[0].get_header('Authorization'), 'Bearer ' + PRIMARY)
        self.assertNotIn('IDECK_DEBIAN_PAYLOAD_TOKEN', env.reads)

    def test_fallback_never_read_or_forwarded_outside_exact_repo_asset_api(self):
        for url in ('https://example.invalid/public', API.replace('/Mi-Yomi/', '/other/'),
                    API + '?signed=value', API.replace('/assets/', '/assets/../assets/')):
            env, requests, error = self.fetch({'IDECK_STEAM_PAYLOAD_URL': url, 'IDECK_DEBIAN_PAYLOAD_TOKEN': FALLBACK})
            self.assertIsNone(error)
            self.assertNotIn('IDECK_DEBIAN_PAYLOAD_TOKEN', env.reads)
            self.assertFalse(requests[0].has_header('Authorization'))
        _, requests, error = self.fetch({'IDECK_STEAM_PAYLOAD_URL': 'https://other.invalid', 'IDECK_STEAM_PAYLOAD_TOKEN': PRIMARY})
        self.assertEqual(str(error), 'STEAM_PAYLOAD_TOKEN_SCOPE')
        self.assertFalse(requests)

    def test_https_redirect_downgrade_and_bad_hash_never_publish(self):
        with self.assertRaises(ValueError):
            bundle.HTTPSOnly().redirect_request(None, None, 302, 'Found', {}, 'http://example.invalid')
        target = self.root / 'bad'
        with patch.dict(bundle.os.environ, {'IDECK_STEAM_PAYLOAD_URL': API}, clear=True), \
             patch.object(bundle.urllib.request, 'build_opener') as factory:
            factory.return_value.open.return_value = io.BytesIO(b'bad')
            with self.assertRaisesRegex(ValueError, 'STEAM_PAYLOAD_FETCH_FAILED'):
                bundle.fetch(target, {'archive': {'size': 3, 'sha256': '0' * 64}})
        self.assertFalse(target.exists())

    def test_blocked_build_needs_no_url_or_token_and_keeps_exact_marker(self):
        with patch.object(bundle.os, 'environ', Environment({})), \
             patch.object(bundle.urllib.request, 'build_opener', side_effect=AssertionError('blocked must not fetch')):
            result = bundle.prepare_for_build(self.root / 'bundle', ROOT / 'tests/fixtures/steam-blocked.lock.json', self.root)
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual({p.name for p in (self.root / 'bundle').iterdir()}, {'STEAM-BLOCKER.txt'})

    def test_actual_lse_failure_gate_propagates_error_before_network_ready(self):
        generated = bootstrap.persistent_init((ROOT / 'guest/gui/ideck-desktop-init').read_bytes())
        gate = generated[generated.index(b'grep -qw atomics'):generated.index(b'echo IDECK_STEAM_NETWORK_READY', generated.index(b'grep -qw atomics'))]
        for feature, probe, expected in ((1, 0, b'cpu_lse_not_advertised'), (0, 132, b'cpu_lse_probe_failed'), (0, 0, b'IDECK_STEAM_CPU_LSE_PASS')):
            script = (f'fail() {{ exit 23; }}; grep() {{ return {feature}; }}; chroot() {{ return {probe}; }}; exec 3>&1\n').encode() + gate
            result = subprocess.run(['/bin/sh'], input=script, capture_output=True)
            self.assertIn(expected, result.stdout)
            self.assertEqual(result.returncode, 0 if feature == probe == 0 else 23)
            if feature or probe: self.assertNotIn(b'IDECK_STEAM_CPU_LSE_PASS', result.stdout)

    def test_only_pending_triggers_may_resume_unchanged_baseline_during_dependencies(self):
        for status in ('triggers-pending', 'triggers-awaited'):
            output = 'gui\t1\t' + status + '\n'
            with self.assertRaises(official.Failure): official.inventory({'gui': '1'}, [], output)
            self.assertEqual(official.inventory({'gui': '1'}, [], output, allow_baseline_triggers=True), {'gui': '1'})
        for output in ('gui\t2\ttriggers-pending\n', 'gui\t1\tunpacked\n', 'foreign\t1\ttriggers-pending\n'):
            with self.assertRaises(official.Failure):
                official.inventory({'gui': '1'}, [], output, allow_baseline_triggers=True)

    def test_corrupt_install_phase_or_baseline_fails_before_resume(self):
        valid = {'schema': 1, 'bindings': {'client': 'hash'}, 'phase': 'client', 'baseline': {'gui': '1'}}
        official.validate_journal(valid, valid['bindings'])
        for key, value in [('phase', 'unknown'), ('baseline', {}), ('baseline', {'gui': 1}), ('baseline', None)]:
            bad = dict(valid, **{key: value})
            with self.assertRaisesRegex(official.Failure, 'invalid_install_journal'):
                official.validate_journal(bad, valid['bindings'])
        with self.assertRaisesRegex(official.Failure, 'installation_lock_changed'):
            official.validate_journal(valid, {'client': 'changed'})

    def test_published_client_receipt_is_bounded_regular_owned_single_link(self):
        dest = self.root / 'Steam'; (dest / 'package').mkdir(parents=True)
        receipt = dest / 'package/ideck-install.json'; receipt.write_bytes(b' ' * 65537)
        with patch.object(official, 'DEST', dest), patch.object(official.common, 'safe_directory'), \
             patch.object(official.os, 'fstat', return_value=Mock(st_mode=stat.S_IFREG | 0o600, st_nlink=1, st_uid=1000, st_size=65537)):
            with self.assertRaisesRegex(official.Failure, 'receipt_unsafe'):
                official.published_client({'phase': 'client'}, {'manifest_sha256': 'a' * 64})

    def test_loader_runs_uid1000_and_sets_vendor_path_only_after_setpriv(self):
        proc = self.root / 'proc'; proc.mkdir()
        (proc / 'cmdline').write_text('ideck.steam_experiment=1 ideck.steam_persistent=1 ideck.steam_network=1')
        before = Path.is_file
        def client_exists(path):
            return str(path).startswith('/home/ideck/.local/share/Steam/') or before(path)
        with patch.object(action, 'PROC', proc), patch.object(action, 'LOG', self.root / 'logs'), \
             patch.object(action, 'ACTION_LOCK', self.root / 'action.lock'), patch.object(action.os, 'geteuid', return_value=0), \
             patch.object(action.shutil, 'which', return_value='/fixture'), patch.object(Path, 'is_file', client_exists), \
             patch.object(action.subprocess, 'run', return_value=Mock(returncode=0, stdout='', stderr='')) as run, \
             contextlib.redirect_stdout(io.StringIO()):
            action.main('big-picture')
        self.assertEqual(len(run.call_args_list), 5)
        for call in run.call_args_list[:4]:
            args = call.args[0]
            self.assertEqual(args[:5], ['/usr/bin/setpriv', '--reuid=1000', '--regid=1000', '--init-groups', '/usr/bin/env'])
            self.assertNotIn('LD_LIBRARY_PATH', call.kwargs['env'])
            self.assertNotIn('LD_PRELOAD', call.kwargs['env'])
            self.assertTrue(any(p.startswith('LD_LIBRARY_PATH=') for p in args[6:]))
            self.assertEqual(args[-2], '/usr/bin/ldd')

    def test_return_desktop_waits_for_writers_and_launcher_without_signals(self):
        with patch.object(action, 'ACTION_LOCK', self.root / 'lock'), \
             patch.object(action, 'steam_writers', side_effect=[[123], [123], []]), \
             patch.object(action.time, 'sleep') as sleep, patch.object(action.os, 'kill', side_effect=AssertionError('no force')):
            action.wait_for_desktop()
        self.assertEqual(sleep.call_count, 2)
        with patch.object(action, 'ACTION_LOCK', self.root / 'lock'), patch.object(action, 'steam_writers', return_value=[123]):
            with self.assertRaisesRegex(RuntimeError, 'writers_remain'): action.wait_for_desktop(timeout=0)
        fd = os.open(self.root / 'lock', os.O_RDWR)
        try:
            action.fcntl.flock(fd, action.fcntl.LOCK_EX | action.fcntl.LOCK_NB)
            with patch.object(action, 'ACTION_LOCK', self.root / 'lock'), patch.object(action, 'steam_writers', return_value=[]):
                with self.assertRaisesRegex(RuntimeError, 'launcher_still_owned'): action.wait_for_desktop(timeout=0)
        finally:
            os.close(fd)

    def test_namespace_writer_inventory_preserves_original_desktop_processes(self):
        proc = self.root / 'proc'; (proc / 'self/ns').mkdir(parents=True)
        (proc / 'self/ns/mnt').symlink_to('mnt:[original]')
        for pid, ns, exe in [('41', 'original', '/usr/bin/openbox'), ('42', 'private', '/usr/bin/dbus-daemon'),
                             ('43', 'original', '/home/ideck/.local/share/Steam/steamrtarm64/steam')]:
            (proc / pid / 'ns').mkdir(parents=True)
            (proc / pid / 'ns/mnt').symlink_to('mnt:[' + ns + ']')
            (proc / pid / 'exe').symlink_to(exe)
        before = Path.stat
        def fixture_owner(path, *args, **kwargs):
            if path.parent == proc and path.name.isdecimal(): return Mock(st_uid=1000)
            return before(path, *args, **kwargs)
        with patch.object(Path, 'stat', fixture_owner):
            self.assertEqual(sorted(action.steam_writers(proc)), [42, 43])


if __name__ == '__main__': unittest.main()
