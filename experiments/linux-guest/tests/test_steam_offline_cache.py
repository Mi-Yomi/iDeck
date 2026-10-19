"""Synthetic owner cache + actual guest installer path, never Valve downloads/exec."""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile
from unittest.mock import Mock, patch
from test_terminal import swift_block

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import steam_offline_cache as tool
from test_steam_device import official
cache = tool.cache


class OfflineCache(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.client = self.root / 'client'; self.client.mkdir()
        self.debs = self.root / 'debs'; self.debs.mkdir()
        self.body = b'original fixture content, never Valve data'
        self.row = {'name': 'client/fixture.zip', 'size': len(self.body), 'sha256': hashlib.sha256(self.body).hexdigest()}
        (self.client / 'fixture.zip').write_bytes(self.body)

    def pack(self):
        out = self.root / 'owner.tar'
        return out, tool.pack(self.client, self.debs, out, [self.row])

    def test_pack_is_canonical_deterministic_and_verified_without_download(self):
        out, report = self.pack()
        self.assertEqual(report['parts'], 1); self.assertFalse(report['client_executed'])
        self.assertEqual(tool.verify(out, [self.row]), {'client/fixture.zip': 512})
        second = self.root / 'second.tar'; tool.pack(self.client, self.debs, second, [self.row])
        self.assertEqual(second.read_bytes(), out.read_bytes())
        with self.assertRaises(ValueError): tool.pack(self.client, self.debs, out, [self.row])
        self.assertEqual(out.read_bytes(), second.read_bytes())

    def test_corruption_truncation_trailing_data_links_and_traversal_rejected(self):
        out, _ = self.pack(); original = out.read_bytes()
        for index in (0, 156, 345, 512, 512 + len(self.body), len(original)-1):
            bad = bytearray(original); bad[index] ^= 1; out.write_bytes(bad)
            with self.assertRaises(ValueError): tool.verify(out, [self.row])
        for bad in (original[:-1], original + bytes(512)):
            out.write_bytes(bad)
            with self.assertRaises(ValueError): tool.verify(out, [self.row])
        for name in ('client/../escape', '/absolute', 'client/a/b', 'client/a\\b'):
            with self.assertRaises(ValueError): cache.header(dict(self.row, name=name))
        out.write_bytes(original)
        link = self.root / 'link.tar'; link.symlink_to(out)
        with self.assertRaises(ValueError): tool.verify(link, [self.row])

    def test_bad_input_and_output_symlink_preserve_originals(self):
        p = self.client / 'fixture.zip'; p.write_bytes(b'bad')
        with self.assertRaises(ValueError): tool.pack(self.client, self.debs, self.root / 'bad.tar', [self.row])
        self.assertFalse((self.root / 'bad.tar').exists())
        p.unlink(); target = self.root / 'private'; target.write_bytes(self.body); p.symlink_to(target)
        with self.assertRaises(ValueError): tool.pack(self.client, self.debs, self.root / 'bad.tar', [self.row])
        self.assertEqual(target.read_bytes(), self.body)
        self.assertFalse(list(self.root.glob('.ideck-cache-*')))

    def test_contract_and_suffix_generated_exactly_and_existing_payload_bindings_match(self):
        self.assertEqual(tool.swift(), (ROOT / 'ios/LinuxSteamCacheContract.swift').read_text())
        rows = tool.pins(); self.assertEqual(len(rows), 62)
        self.assertLess(cache.archive_size(rows), cache.LIMIT)
        self.assertEqual(sum(r['size'] for r in rows), 379176939)
        import steam_bundle
        lock = steam_bundle.load_lock(ROOT / 'ipa/steam.lock.json')
        for name, pin in lock['source_inputs'].items(): steam_bundle.checked(ROOT / name, pin)
        suffix = tool.guest_suffix()
        self.assertIn(b'with offline.source(installer):', suffix)
        self.assertIn(b'os.O_RDONLY', suffix)
        self.assertNotIn(b'installer.fetch = original\n        yield', suffix)

    def test_actual_offline_source_installer_extracts_and_resumes_existing_userdata(self):
        # Only root/dpkg/setpriv/device boundaries are modeled; real canonical tar,
        # pinned local reads, journal, ZIP extraction, publication and link IO run.
        state, opt, home = [self.root / x for x in ('state', 'opt', 'home')]
        opt.mkdir(); home.mkdir(); sentinel = home / 'preserved-file'; sentinel.write_bytes(b'owner data')
        dest = home / '.local/share/Steam'
        parts = []
        for n in range(17):
            component = 'bins_linuxarm64_linuxarm64' if n == 0 else 'fixture' + str(n) + '_all'
            name = component + '.zip.' + '0' * 40
            z = io.BytesIO()
            with zipfile.ZipFile(z, 'w') as archive:
                elf = bytearray(64); elf[:6] = b'\x7fELF\x02\x01'; elf[18:20] = (183).to_bytes(2, 'little')
                archive.writestr('steamrtarm64/steam' if n == 0 else 'resource/' + str(n), bytes(elf) if n == 0 else b'fixture')
            body = z.getvalue(); (self.client / name).write_bytes(body)
            parts.append({'component': component, 'file': name, 'size': len(body), 'sha256': hashlib.sha256(body).hexdigest()})
        client = {'schema': 1, 'kind': 'private-steam-arm64-experiment', 'channel': 'steamdeck_publicbeta',
                  'version': '1792192922', 'manifest_url': official.client.CDN + '/' + official.client.MANIFEST,
                  'manifest_sha256': 'a' * 64, 'redistribution_approved': False, 'parts': parts}
        deps = []
        for n in range(45):
            name = 'fixture' + str(n); body = b'synthetic deb data'
            (self.debs / (name + '.deb')).write_bytes(body)
            deps.append({'name': name, 'version': '1', 'architecture': 'arm64', 'filename': 'pool/' + name + '.deb',
                         'size': len(body), 'sha256': hashlib.sha256(body).hexdigest()})
        (opt / 'steam-client.lock.json').write_text(json.dumps(client))
        (opt / 'steam-dependencies.lock.json').write_text(json.dumps({'schema': 1, 'kind': 'ideck-experimental-steam-dependencies', 'architecture': 'arm64', 'extra_packages': deps}))
        legacy = self.root / 'reserved-cache/client'
        legacy.mkdir(parents=True)
        damaged = legacy / parts[0]['file']; damaged.write_bytes(b'old incomplete network download preserved')
        rows = cache.entries(client, deps); archive = self.root / 'complete.tar'
        tool.pack(self.client, self.debs, archive, rows)
        base = {'gui': '1'}; installed = dict(base, **{p['name']: p['version'] for p in deps})
        original_safe = official.common.safe_directory; original_lstat = Path.lstat; original_read = Path.read_text
        def lstat(path):
            row = original_lstat(path)
            if path == state / 'journal.json':
                values = list(row); values[4] = 0; return os.stat_result(values)
            return row
        calls = []
        def process(args, **kwargs):
            calls.append(args[0])
            if args[0] == 'dpkg-query':
                return Mock(stdout=b'gui\t1\tinstalled\n', returncode=0)
            if args[0] == 'setpriv':
                if calls.count('setpriv') == 1: raise OSError('synthetic interruption before publication')
                official.client.install(client, Path(args[args.index('--cache') + 1]), dest, resume=True)
            return Mock(returncode=0)
        with patch.object(official, 'STATE', state), patch.object(official, 'OPT', opt), \
             patch.object(official, 'CACHE', self.root / 'reserved-cache'), patch.object(official, 'HOME', home), \
             patch.object(official, 'DEST', dest), patch.object(official.common, 'HOME', home), \
             patch.object(official.common, 'DEST', dest), patch.object(official.common, 'LOG', self.root / 'logs'), \
             patch.object(official.common, 'safe_directory', side_effect=lambda p, owner=None: original_safe(p)), \
             patch.object(official.common, 'installed', side_effect=[base, installed]), patch.object(official.common, 'audit'), \
             patch.object(official.os, 'geteuid', return_value=0), patch.object(official.os, 'sync'), \
             patch.object(Path, 'lstat', lstat), patch.object(Path, 'read_text', lambda p,*a,**kw: cache.MARKER if p == Path('/proc/cmdline') else original_read(p,*a,**kw)), \
             patch.object(cache, 'open_device', side_effect=lambda size: os.open(archive, os.O_RDONLY)), \
             patch.object(official.subprocess, 'run', side_effect=process), \
             patch.object(official.urllib.request, 'build_opener', side_effect=AssertionError('network forbidden')):
            with self.assertRaises(OSError):
                with cache.source(official): official.install()
            self.assertEqual(json.loads((state / 'journal.json').read_text())['phase'], 'client')
            self.assertFalse(dest.exists())
            with cache.source(official): official.install()
            self.assertEqual(json.loads((state / 'journal.json').read_text())['phase'], 'ready')
            self.assertTrue((dest / 'steamrtarm64/steam').is_file())
            self.assertEqual(sentinel.read_bytes(), b'owner data')
            with cache.source(official): official.install()
            self.assertEqual(calls.count('dpkg'), 1); self.assertEqual(calls.count('setpriv'), 2)
        self.assertEqual(sentinel.read_bytes(), b'owner data')
        self.assertEqual(damaged.read_bytes(), b'old incomplete network download preserved')

    def test_guest_block_device_must_be_readonly_and_exact_size(self):
        import struct
        out, _ = self.pack()
        actual = os.stat(out)
        fake = Mock(st_mode=__import__('stat').S_IFBLK)
        for readonly, size, valid in [(0, 10240, False), (1, 10241, False), (1, 10240, True)]:
            fd = os.open(out, os.O_RDONLY)
            with patch.object(cache.os, 'open', return_value=fd), patch.object(cache.os, 'fstat', return_value=fake), \
                 patch('fcntl.ioctl', side_effect=[struct.pack('i', readonly), struct.pack('Q', size)]):
                if valid:
                    opened = cache.open_device(10240); self.assertEqual(opened, fd); os.close(opened)
                else:
                    with self.assertRaises(ValueError): cache.open_device(10240)

    def test_auto_policy_is_shared_by_preview_start_argv_and_final_entry(self):
        memory = (ROOT / 'ios/LinuxSteamMemory.swift').read_text()
        self.assertIn('addingReportingOverflow', memory)
        self.assertIn('guard available >= retained', memory)
        self.assertIn('static let ceiling = 4096', memory)
        self.assertIn('min(room, UInt64(ceiling)) / 256', memory)
        session = (ROOT / 'ios/LinuxTerminalSession.swift').read_text()
        start = swift_block(session, 'func start()')
        self.assertLess(start.index('JITBootstrap.prewarm()'), start.index('LinuxSteamMemory.plan'))
        self.assertLess(start.index('LinuxSteamMemory.plan'), start.index('attempted = true'))
        self.assertIn('memoryMib: plan.guestMib, offlineCache:', session)
        self.assertIn('self.report["profile_memory_mib"] = plan.guestMib', session)
        fixtures = (ROOT / 'ios/tests/SteamOfflineChecks.swift').read_text()
        for case in ('autoMinimum - 1', 'UInt64.max', 'hostOverhead: 4096 * mib', 'floor.recheck(nil)', 'floor.recheck(autoMinimum - 1)', 'mode: .fixed1536'):
            self.assertIn(case, fixtures)

    def test_app_import_readonly_argv_memory_and_one_vm_wiring(self):
        source = (ROOT / 'ios/LinuxSteamOfflineCache.swift').read_text()
        for required in ('O_NOFOLLOW', 'LOCK_EX | LOCK_NB', 'linkat(', 'fsync(parent)', 'LinuxSteamCacheContract.entries', 'try verify(output'):
            self.assertIn(required, source)
        self.assertNotIn('extract', swift_block(source, 'static func importArchive('))
        profile = (ROOT / 'ios/LinuxSteamProfile.swift').read_text()
        self.assertIn('readonly=on,file.locking=off', profile)
        self.assertIn('LinuxSteamOfflineCache.appendRuntime', profile)
        session = (ROOT / 'ios/LinuxTerminalSession.swift').read_text()
        self.assertIn('guard !attempted, !steamCacheImportBusy', session)
        entry = swift_block(session, 'private func prepareNativeEntry(')
        self.assertLess(entry.index('plan.recheck'), entry.index('preparation.enterNative()'))
        self.assertIn('steamOfflineCache?.validateIdentity()', entry)
        self.assertEqual(session.count('attempted = false'), 1)
        ci = (ROOT.parents[1] / 'ci/check_linux_guest_profile.py').read_text()
        for marker in ('LINUX_STEAM_OFFLINE_CACHE_PASS', 'LINUX_STEAM_AUTO_MEMORY_PASS'): self.assertIn(marker, ci)

if __name__ == '__main__': unittest.main()
