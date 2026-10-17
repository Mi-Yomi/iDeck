"""POSIX offline host-runner guards; fixtures never claim an actual VM boot."""
import os
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
if os.name == 'posix':
    import steam_vm
else:
    steam_vm = None


@unittest.skipUnless(os.name == 'posix', 'POSIX host-runner guard; fcntl unavailable')
class SteamHostGuards(unittest.TestCase):
    def test_fsync_or_marker_failure_cannot_later_become_clean(self):
        for phase in ('fsync', 'marker'):
            with self.subTest(phase=phase), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                disk, dirty = root/'disk', root/'needs-recovery'
                disk.write_bytes(b'user progress')
                dirty.write_text('dirty')
                report = {'clean_shutdown': False}
                target = patch.object(steam_vm.os, 'fsync', side_effect=OSError('fixture')) if phase == 'fsync' else patch.object(Path, 'unlink', side_effect=PermissionError('fixture'))
                with target:
                    with self.assertRaises(OSError): steam_vm.finalize_disk(report, disk, dirty)
                self.assertFalse(steam_vm.finalize_disk(report, disk, dirty))
                self.assertFalse(report['clean_shutdown'])
                self.assertTrue(dirty.exists())

    def continuation_fixture(self, root):
        (root/'owner.lock').touch()
        (root/'steam-experiment.qcow2').write_bytes(b'existing progress')
        result = {'host_only': True, 'clean_shutdown': True, 'qemu_exit_code': 0,
                  'seed_sha256': 'accepted-seed'}
        (root/'result.json').write_text(json.dumps(result))
        return result

    def test_explicit_clean_continuation_accepts_only_private_matching_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.continuation_fixture(root)
            self.assertEqual(steam_vm.validate_continuation(root, 'accepted-seed'), root/'steam-experiment.qcow2')
            with self.assertRaises(ValueError): steam_vm.validate_continuation(root, 'different-seed')
            self.assertEqual((root/'steam-experiment.qcow2').read_bytes(), b'existing progress')

    def test_dirty_forced_or_unconfirmed_continuation_never_repaired(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            original = self.continuation_fixture(root)
            for key, value in [('host_only', False), ('clean_shutdown', False),
                               ('qemu_exit_code', False), ('qemu_exit_code', 1), ('forced', True)]:
                (root/'result.json').write_text(json.dumps({**original, key: value}))
                with self.assertRaises(ValueError): steam_vm.validate_continuation(root, 'accepted-seed')
            (root/'result.json').write_text(json.dumps(original))
            (root/'needs-recovery').write_text('do not clear')
            with self.assertRaises(ValueError): steam_vm.validate_continuation(root, 'accepted-seed')
            self.assertEqual((root/'needs-recovery').read_text(), 'do not clear')

    def test_symlinked_continuation_disk_is_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.continuation_fixture(root)
            disk = root/'steam-experiment.qcow2'
            disk.rename(root/'actual')
            disk.symlink_to(root/'actual')
            with self.assertRaises(ValueError): steam_vm.validate_continuation(root, 'accepted-seed')

    def test_busy_continuation_refused_before_qemu_image_access(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.continuation_fixture(root)
            with (root/'owner.lock').open('rb') as owner:
                steam_vm.fcntl.flock(owner, steam_vm.fcntl.LOCK_EX | steam_vm.fcntl.LOCK_NB)
                with patch.object(steam_vm.subprocess, 'run', side_effect=AssertionError('no image access')):
                    with self.assertRaises(BlockingIOError):
                        steam_vm.continuation_copy(root, root/'new', root/'seed', 'accepted-seed', ['qemu-img'], {})
            self.assertFalse((root/'new').exists())

    def test_offline_fsck_failure_preserves_copy_and_never_repairs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            def run(argv, **kwargs):
                if argv[1] == 'info':
                    return SimpleNamespace(stdout=json.dumps({'virtual-size': 1024}))
                if argv[1] == 'convert':
                    self.assertTrue(argv[-1].startswith('/proc/self/fd/'))
                    os.write(kwargs['pass_fds'][0], b'failed filesystem')
                    return SimpleNamespace(returncode=0)
                self.assertEqual(argv, ['/usr/sbin/e2fsck', '-f', '-n', str(root/'offline-fsck.raw')])
                return SimpleNamespace(returncode=4, stdout='errors remain', stderr='')
            with patch.object(steam_vm.subprocess, 'run', side_effect=run), \
                 patch.object(steam_vm.shutil, 'disk_usage', return_value=SimpleNamespace(free=8*1024**3)):
                with self.assertRaises(RuntimeError): steam_vm.offline_fsck(root/'disk', root, ['qemu-img'], {})
            self.assertTrue((root/'offline-fsck.raw').exists())
            self.assertEqual(json.loads((root/'offline-fsck.json').read_text())['exit_code'], 4)

    def test_fsck_rechecks_remaining_capacity_before_flattening_copy(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            disk = root/'copied.qcow2'
            disk.write_bytes(b'continuation copy already consumes storage')
            with patch.object(steam_vm.subprocess, 'run', return_value=SimpleNamespace(
                     stdout=json.dumps({'virtual-size': 8*1024**3}))) as run, \
                 patch.object(steam_vm.shutil, 'disk_usage', return_value=SimpleNamespace(free=11*1024**3)):
                with self.assertRaisesRegex(ValueError, 'insufficient space for offline'):
                    steam_vm.offline_fsck(disk, root, ['qemu-img'], {})
            run.assert_called_once_with(['qemu-img', 'info', '--output=json', str(disk)],
                                         env={}, check=True, capture_output=True, text=True)
            self.assertFalse((root/'offline-fsck.raw').exists())
            self.assertEqual(disk.read_bytes(), b'continuation copy already consumes storage')

    def test_preparation_failure_saves_receipt_and_closes_resources_and_owner(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)/'new-run'
            cleaned = []
            def fail(args, profile_path, profile, out, report, cleanup):
                cleanup.callback(lambda: cleaned.append('closed'))
                report['continuation'] = {'original_preserved': True}
                # The caller holds ownership throughout preparation.
                with (out/'owner.lock').open('rb') as other:
                    with self.assertRaises(BlockingIOError):
                        steam_vm.fcntl.flock(other, steam_vm.fcntl.LOCK_EX | steam_vm.fcntl.LOCK_NB)
                raise OSError('fixture preparation failure')
            with patch.object(steam_vm, '_boot', side_effect=fail), \
                 patch.object(steam_vm.subprocess, 'Popen', side_effect=AssertionError('no VM')):
                with self.assertRaises(OSError):
                    steam_vm.boot(SimpleNamespace(output=output))
            receipt = json.loads((output/'result.json').read_text())
            self.assertTrue(receipt['preparation_failed'])
            self.assertFalse(receipt['qemu_started'])
            self.assertFalse(receipt['clean_shutdown'])
            self.assertEqual(receipt['failure']['class'], 'OSError')
            self.assertEqual(receipt['continuation'], {'original_preserved': True})
            self.assertEqual(cleaned, ['closed'])
            with (output/'owner.lock').open('rb') as other:
                steam_vm.fcntl.flock(other, steam_vm.fcntl.LOCK_EX | steam_vm.fcntl.LOCK_NB)

    def test_image_outputs_never_replace_files_or_dangling_links(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.continuation_fixture(root)
            for link in (False, True):
                destination = root/('dangling' if link else 'existing')
                if link: destination.symlink_to(root/'absent-target')
                else: destination.write_bytes(b'preserve')
                with patch.object(steam_vm.subprocess, 'run', side_effect=AssertionError('no image access')):
                    with self.assertRaises(FileExistsError):
                        steam_vm.exclusive_image_output(['qemu-img'], ['convert'], destination, {})
                    with self.assertRaises(FileExistsError):
                        steam_vm.continuation_copy(root, destination, root/'seed', 'accepted-seed', ['qemu-img'], {})
                if not link: self.assertEqual(destination.read_bytes(), b'preserve')
            (root/'offline-fsck.raw').symlink_to(root/'absent-target')
            with patch.object(steam_vm.subprocess, 'run', side_effect=AssertionError('no image access')):
                with self.assertRaises(FileExistsError):
                    steam_vm.offline_fsck(root/'disk', root, ['qemu-img'], {})

    def test_guest_clean_control_record_supports_lf_and_crlf(self):
        for output in (b'IDECK_DESKTOP_CLEAN_UNMOUNT\n', b'IDECK_DESKTOP_CLEAN_UNMOUNT\r\n',
                       b'BOOT\nIDECK_DESKTOP_CLEAN_UNMOUNT\nBYE\n'):
            with self.subTest(output=output):
                self.assertTrue(steam_vm.clean_stop_evidence(0, output))

    def test_failed_running_or_noninteger_exit_is_never_clean(self):
        output = b'IDECK_DESKTOP_CLEAN_UNMOUNT\n'
        for code in (None, -9, 1, 132, False, True, 0.0, '0'):
            with self.subTest(code=code):
                self.assertFalse(steam_vm.clean_stop_evidence(code, output))

    def test_control_marker_must_be_exact_line_not_a_substring(self):
        for output in (b'', b'IDECK_DESKTOP_READY\n', b'xIDECK_DESKTOP_CLEAN_UNMOUNT\n',
                       b'IDECK_DESKTOP_CLEAN_UNMOUNT_failed\n', b'IDECK_DESKTOP_CLEAN_UNMOUNT \n',
                       b' IDECK_DESKTOP_CLEAN_UNMOUNT\n', b'IDECK_DESKTOP_CLEAN_UNMOUNT\x00\n'):
            with self.subTest(output=output):
                self.assertFalse(steam_vm.clean_stop_evidence(0, output))

    def test_existing_output_is_refused_before_any_runtime_or_disk_action(self):
        with tempfile.TemporaryDirectory(prefix='ideck-steam-guard-') as temporary:
            output = Path(temporary) / 'existing-output'
            output.mkdir()
            sentinel = output / 'userdata'
            sentinel.write_bytes(b'keep my data')
            with patch.object(steam_vm.subprocess, 'Popen', side_effect=AssertionError('no VM')), \
                 patch.object(steam_vm.subprocess, 'run', side_effect=AssertionError('no image command')):
                with self.assertRaises(FileExistsError):
                    steam_vm.boot(SimpleNamespace(output=output))
            self.assertEqual(list(output.iterdir()), [sentinel])
            self.assertEqual(sentinel.read_bytes(), b'keep my data')


if __name__ == '__main__':
    unittest.main()
