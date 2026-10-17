"""Recovery fixtures are tiny temporary files; no guest, real SHM or VM access."""
from contextlib import ExitStack
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if os.name == 'posix':
    spec = importlib.util.spec_from_file_location('shm_recovery', ROOT/'guest/steam/shm-recovery.py')
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)


@unittest.skipUnless(os.name == 'posix', 'POSIX guest utility')
class OrphanRecovery(unittest.TestCase):
    def test_guard_requires_root_pinned_guest_optin_and_full_pid_view(self):
        cases = [('root', {'uid': 1000}), ('kernel', {'release': 'host'}),
                 ('opt_in', {'cmdline': 'console=ttyAMA0'}), ('pid1', {'init': False}),
                 ('guest_root', {'roots': False}), ('visibility', {'namespaces': False}),
                 ('tmpfs', {'mounts': '31 28 0:6 / /dev rw - devtmpfs devtmpfs rw'})]
        for reason, changes in cases:
            with self.subTest(reason=reason), ExitStack() as stack:
                stack.enter_context(patch.object(helper.os, 'geteuid', return_value=changes.get('uid', 0)))
                stack.enter_context(patch.object(helper.os, 'uname', return_value=SimpleNamespace(release=changes.get('release', '6.18.35-0-virt'))))
                stack.enter_context(patch.object(Path, 'is_file', return_value=changes.get('init', True)))
                def read(path, *args, **kwargs):
                    if path.name == 'cmdline': return changes.get('cmdline', 'ideck.steam_experiment=1')
                    return changes.get('mounts', '33 31 0:27 / /dev/shm rw - tmpfs tmpfs rw')
                stack.enter_context(patch.object(Path, 'read_text', read))
                stack.enter_context(patch.object(helper.os, 'stat', side_effect=[
                    SimpleNamespace(st_dev=1, st_ino=1),
                    SimpleNamespace(st_dev=1, st_ino=1 if changes.get('roots', True) else 2)]))
                stack.enter_context(patch.object(helper.os, 'readlink', side_effect=[
                    'pid:[1]', 'pid:[1]' if changes.get('namespaces', True) else 'pid:[2]']))
                with self.assertRaises(helper.Refused): helper.guard()

    def manifest(self, info=None):
        item = {'name': 'u1000-Shm_123', 'device': 27, 'inode': 123, 'uid': 1000,
                'size': 16, 'mode': 0o700}
        if info is not None:
            item.update(device=info.st_dev, inode=info.st_ino, size=info.st_size)
        return {'schema': 1, 'boot_id': 'test-boot', 'baseline_empty': True,
                'capture_complete': True, 'objects': [item],
                'processes': [{'pid': 972, 'starttime': 12345}]}

    def test_manifest_rejects_incomplete_crossboot_duplicates_and_names(self):
        changes = [('schema', 0), ('boot_id', 'old-boot'), ('baseline_empty', False),
                   ('capture_complete', False), ('objects', []), ('processes', [])]
        for key, value in changes:
            manifest = self.manifest(); manifest[key] = value
            with self.subTest(key=key), self.assertRaises(helper.Refused):
                helper.validate_manifest(manifest, 'test-boot')
        for key, value in [('name', '../u1000-Shm_123'), ('name', 'unrelated'),
                           ('uid', 0), ('size', 129*1024**2), ('mode', 0o777), ('device', False)]:
            manifest = self.manifest(); manifest['objects'][0][key] = value
            with self.subTest(key=key), self.assertRaises(helper.Refused):
                helper.validate_manifest(manifest, 'test-boot')
        manifest = self.manifest(); manifest['objects'] *= 2
        with self.assertRaises(helper.Refused): helper.validate_manifest(manifest, 'test-boot')

    def proc_fixture(self, root, name='worker', uid=0, state='S', starttime=100, pid='200'):
        process = root/pid; process.mkdir(); (process/'fd').mkdir()
        fields = [state] + ['0']*18 + [str(starttime)]
        (process/'stat').write_text('200 (worker) '+' '.join(fields)+'\n')
        (process/'status').write_text(f'Name:\t{name}\nUid:\t{uid}\t{uid}\t{uid}\t{uid}\n')
        (process/'cmdline').write_bytes(b'/usr/bin/worker\x00')
        (process/'maps').write_text('')
        return process

    def test_live_fd_and_mapping_reference_refuse_regardless_of_process_name(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); proc = root/'proc'; proc.mkdir()
            process = self.proc_fixture(proc)
            item = root/'shm'; item.write_bytes(b'not a real SHM object')
            manifest = self.manifest(item.stat())['objects']
            (process/'fd/7').symlink_to(item)
            with self.assertRaisesRegex(helper.Refused, 'live_fd_reference'):
                helper.scan_references(manifest, {}, proc)
            (process/'fd/7').unlink()
            info = item.stat()
            (process/'maps').write_text(f'1000-2000 rw-s 00000000 {os.major(info.st_dev):x}:{os.minor(info.st_dev):x} {info.st_ino} /old-name (deleted)\n')
            with self.assertRaisesRegex(helper.Refused, 'live_mapping_reference'):
                helper.scan_references(manifest, {}, proc)

    def test_captured_identity_or_uncaptured_steam_refuses_but_pid_reuse_is_distinguished(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); process = self.proc_fixture(root)
            with self.assertRaisesRegex(helper.Refused, 'captured_process_alive'):
                helper.scan_references(self.manifest()['objects'], {200: 100}, root)
            helper.scan_references(self.manifest()['objects'], {200: 99}, root)
            (process/'status').write_text('Name:\tsteamwebhelper\nUid:\t1000\t1000\t1000\t1000\n')
            with self.assertRaisesRegex(helper.Refused, 'steam_process_alive'):
                helper.scan_references(self.manifest()['objects'], {}, root)

    def test_unreadable_surviving_proc_and_new_steam_pid_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); process = self.proc_fixture(root)
            real_read = Path.read_text
            def read(path, *args, **kwargs):
                if path == process/'maps': raise PermissionError('fixture')
                return real_read(path, *args, **kwargs)
            with patch.object(Path, 'read_text', read), self.assertRaisesRegex(helper.Refused, 'proc_unreadable'):
                helper.scan_references(self.manifest()['objects'], {}, root)
            real_iter = Path.iterdir; count = 0
            def listing(path):
                nonlocal count
                if path == root:
                    count += 1
                    if count == 2: self.proc_fixture(root, name='steamwebhelper', uid=1000, pid='201')
                return real_iter(path)
            with patch.object(Path, 'iterdir', listing), self.assertRaisesRegex(helper.Refused, 'steam_process_alive'):
                helper.scan_references(self.manifest()['objects'], {}, root)

    def test_new_pid_is_fully_checked_and_finite_churn_converges(self):
        for referenced in (False, True):
            with self.subTest(referenced=referenced), tempfile.TemporaryDirectory() as temp:
                root = Path(temp); self.proc_fixture(root)
                real_iter = Path.iterdir; count = 0
                def listing(path):
                    nonlocal count
                    if path == root:
                        count += 1
                        if count == 2:
                            child = self.proc_fixture(root, name='sleep', pid='201')
                            if referenced:
                                (child/'maps').write_text('1000-2000 rw-s 0 00:1b 123 /dev/shm/u1000-Shm_123\n')
                    return real_iter(path)
                with patch.object(Path, 'iterdir', listing):
                    if referenced:
                        with self.assertRaisesRegex(helper.Refused, 'live_mapping_reference'):
                            helper.scan_references(self.manifest()['objects'], {}, root)
                    else: helper.scan_references(self.manifest()['objects'], {}, root)

    def test_continuing_pid_churn_has_bounded_refusal(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); self.proc_fixture(root)
            real_iter = Path.iterdir; count = 0
            def listing(path):
                nonlocal count
                if path == root:
                    count += 1
                    self.proc_fixture(root, name='sleep', pid=str(200+count))
                return real_iter(path)
            with patch.object(Path, 'iterdir', listing), self.assertRaisesRegex(helper.Refused, 'did_not_converge'):
                helper.scan_references(self.manifest()['objects'], {}, root)
            self.assertEqual(count, 9)

    def fixture(self, root, stack):
        shm, runtime, proc = root/'shm', root/'runtime', root/'proc'
        shm.mkdir(mode=0o1777); shm.chmod(0o1777); runtime.mkdir(mode=0o700)
        (proc/'sys/kernel/random').mkdir(parents=True)
        (proc/'sys/kernel/random/boot_id').write_text('test-boot\n')
        lock = runtime/'ideck-steam.lock'; lock.touch(mode=0o600)
        item = shm/'u1000-Shm_123'; item.write_bytes(b'fixture buffer'); item.chmod(0o700)
        manifest = self.manifest(item.stat())
        stack.enter_context(patch.object(helper, 'guard'))
        for key, value in [('SHM', shm), ('RUNTIME', runtime), ('PROC', proc)]:
            stack.enter_context(patch.object(helper, key, value))
        # Ownership checks are exercised without chown or privileged host setup.
        real_stat, real_fstat = helper.os.stat, helper.os.fstat
        def owners(info, path):
            result = SimpleNamespace(**{field: getattr(info, field) for field in
                ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_uid', 'st_size')})
            path = Path(path)
            if path == runtime or path == lock or path.parent == shm:
                result.st_uid = 1000
                result.st_mode = stat.S_IFMT(result.st_mode) | (0o600 if path == lock else 0o700)
            elif path == shm:
                result.st_uid = 0
                result.st_mode = stat.S_IFMT(result.st_mode) | 0o1777
            return result
        def current_stat(path, *args, **kwargs):
            full = Path(path)
            if kwargs.get('dir_fd') is not None:
                full = Path(os.readlink(f'/proc/self/fd/{kwargs["dir_fd"]}'))/full
            return owners(real_stat(path, *args, **kwargs), full)
        def current_fstat(fd):
            return owners(real_fstat(fd), os.readlink(f'/proc/self/fd/{fd}'))
        stack.enter_context(patch.object(helper.os, 'stat', current_stat))
        stack.enter_context(patch.object(helper.os, 'fstat', current_fstat))
        return shm, runtime, item, manifest

    def test_cleanup_removes_only_manifested_orphans_and_retains_unrelated(self):
        with tempfile.TemporaryDirectory() as temp, ExitStack() as stack:
            shm, runtime, item, manifest = self.fixture(Path(temp), stack)
            unrelated = shm/'other-application'; unrelated.write_bytes(b'preserve')
            report = {'removed': []}
            with patch.object(helper, 'scan_references') as scan:
                helper.recover(manifest, report)
            self.assertEqual(scan.call_count, 2)
            self.assertFalse(item.exists()); self.assertEqual(unrelated.read_bytes(), b'preserve')
            self.assertEqual(report['status'], 'reclaimed_manifested_orphans')
            self.assertEqual(report['removed'], manifest['objects'])

    def test_partial_manifest_busy_lock_and_references_never_unlink(self):
        for reason in ('partial', 'lock', 'reference'):
            with self.subTest(reason=reason), tempfile.TemporaryDirectory() as temp, ExitStack() as stack:
                shm, runtime, item, manifest = self.fixture(Path(temp), stack)
                if reason == 'partial': (shm/'u1000-Shm_999').touch()
                if reason == 'lock':
                    owner = stack.enter_context((runtime/'ideck-steam.lock').open('rb'))
                    helper.fcntl.flock(owner, helper.fcntl.LOCK_EX | helper.fcntl.LOCK_NB)
                scan = stack.enter_context(patch.object(helper, 'scan_references',
                    side_effect=helper.Refused('live_mapping_reference') if reason == 'reference' else None))
                with self.assertRaises((helper.Refused, BlockingIOError)):
                    helper.recover(manifest, {'removed': []})
                self.assertEqual(item.read_bytes(), b'fixture buffer')

    def test_replaced_inode_or_symlink_before_unlink_refuses(self):
        for replacement in ('file', 'symlink'):
            with self.subTest(replacement=replacement), tempfile.TemporaryDirectory() as temp, ExitStack() as stack:
                shm, runtime, item, manifest = self.fixture(Path(temp), stack)
                calls = 0
                def race(*args):
                    nonlocal calls
                    calls += 1
                    if calls == 2:
                        item.rename(shm/'preserved-original')
                        if replacement == 'symlink': item.symlink_to(shm/'preserved-original')
                        else: item.write_bytes(b'new unrelated'); item.chmod(0o700)
                with patch.object(helper, 'scan_references', side_effect=race), self.assertRaisesRegex(helper.Refused, 'identity_changed'):
                    helper.recover(manifest, {'removed': []})
                self.assertTrue(item.exists())
                self.assertEqual((shm/'preserved-original').read_bytes(), b'fixture buffer')

    def test_manifest_hash_is_checked_before_cleanup_and_symlink_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); path = root/'manifest.json'
            path.write_text(json.dumps(self.manifest())); path.chmod(0o600)
            real_fstat = helper.os.fstat
            def root_owned(fd):
                value = real_fstat(fd)
                return SimpleNamespace(st_mode=stat.S_IFMT(value.st_mode) | 0o600,
                                       st_uid=0, st_nlink=1, st_size=value.st_size)
            with patch.object(helper.os, 'fstat', root_owned):
                with self.assertRaisesRegex(helper.Refused, 'hash_mismatch'):
                    helper.read_manifest(path, '0'*64)
                self.assertEqual(helper.read_manifest(path, hashlib.sha256(path.read_bytes()).hexdigest()), self.manifest())
                link = root/'link'; link.symlink_to(path)
                with self.assertRaises(OSError): helper.read_manifest(link, '0'*64)

    def test_refusal_retains_json_result_and_existing_result_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            result = Path(temp)/'result.json'
            argv = ['shm-recovery', '--manifest', str(Path(temp)/'manifest.json'),
                    '--manifest-sha256', '0'*64, '--result', str(result), '--confirm-orphan-cleanup']
            with patch.object(sys, 'argv', argv), patch.object(helper.os, 'geteuid', return_value=0), \
                 patch.object(Path, 'stat', return_value=SimpleNamespace(st_uid=0, st_mode=stat.S_IFDIR | 0o700)), \
                 patch.object(helper, 'read_manifest', side_effect=helper.Refused('manifest_hash_mismatch')), \
                 patch('builtins.print'), patch.object(helper, 'recover') as recover:
                self.assertEqual(helper.main(), 1)
                with self.assertRaises(FileExistsError): helper.main()
            recover.assert_not_called()
            report = json.loads(result.read_text())
            self.assertEqual(report['status'], 'refused')
            self.assertEqual(report['reason'], 'manifest_hash_mismatch')
            self.assertEqual(report['removed'], [])


if __name__ == '__main__': unittest.main()
