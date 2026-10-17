"""POSIX offline host-runner guards; fixtures never claim an actual VM boot."""
import os
import json
import hashlib
import importlib.util
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
    def test_explicit_memory_control_records_effective_budget_without_changing_profile(self):
        profile_path = ROOT/'profiles/steam-host-experiment.json'
        original = profile_path.read_bytes()
        for override, expected in ((None, 1536), (1536, 1536), (2560, 2560)):
            with self.subTest(override=override), tempfile.TemporaryDirectory() as temporary:
                output = Path(temporary)/'run'
                def prepare(args, path, profile, out, report, cleanup):
                    self.assertEqual(profile['memory_mib'], expected)
                    self.assertFalse(profile['app_route_enabled'])
                with patch.object(steam_vm, '_boot', side_effect=prepare) as boot, \
                     patch.object(steam_vm.subprocess, 'Popen', side_effect=AssertionError('no VM')):
                    steam_vm.boot(SimpleNamespace(output=output, experimental_memory_mib=override))
                boot.assert_called_once()
                report = json.loads((output/'result.json').read_text())
                self.assertEqual(report['profile_memory_mib'], 1536)
                self.assertEqual(report['effective_memory_mib'], expected)
                self.assertEqual(report['experimental_memory_override'], override is not None)
                self.assertEqual(profile_path.read_bytes(), original)

    def test_unsupported_memory_control_refuses_before_creating_run(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)/'run'
            for value in (True, 0, -1, 2560.0, '2560', 65536):
                with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'unsupported host memory'):
                    steam_vm.boot(SimpleNamespace(output=output, experimental_memory_mib=value))
                self.assertFalse(output.exists())

    def test_runner_source_and_hash_share_import_snapshot_after_source_edits(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root/'steam_vm_fixture.py'
            original = Path(steam_vm.__file__).read_bytes()
            source.write_bytes(original)
            spec = importlib.util.spec_from_file_location('steam_vm_snapshot_fixture', source)
            loaded = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(loaded)
            source.write_bytes(b'# edited after import, before preparation\n')
            output = root/'new-run'
            def prepare(args, profile_path, profile, out, report, cleanup):
                self.assertEqual(report['runner_sha256'], hashlib.sha256(original).hexdigest())
                self.assertEqual((out/'runner-source.py').read_bytes(), original)
                source.write_bytes(b'# edited again during long preparation\n')
            with patch.object(loaded, 'ROOT', ROOT), \
                 patch.object(loaded, '_boot', side_effect=prepare) as boot, \
                 patch.object(loaded.subprocess, 'Popen', side_effect=AssertionError('no VM')):
                loaded.boot(SimpleNamespace(output=output))
            boot.assert_called_once()
            saved = (output/'runner-source.py').read_bytes()
            receipt = json.loads((output/'result.json').read_text())
            self.assertEqual(saved, original)
            self.assertNotEqual(saved, source.read_bytes())
            self.assertEqual(receipt['runner_sha256'], hashlib.sha256(saved).hexdigest())

    def clean_fsck_output(self, target):
        # e2fsck prints this sanitized device name, not the original path.
        printed_target = str(target).replace(' ', '_').replace(':', '_')
        stdout = ('Pass 1: Checking inodes, blocks, and sizes\n'
                  'Pass 2: Checking directory structure\n'
                  'Pass 3: Checking directory connectivity\n'
                  'Pass 4: Checking reference counts\n'
                  'Pass 5: Checking group summary information\n'
                  f'{printed_target}: 12/100 files (0.4% non-contiguous), 30/200 blocks\n')
        return stdout, 'e2fsck 1.47.4 (6-Mar-2025)\n'

    def test_fsck_accepts_only_complete_uneventful_check(self):
        stdout, stderr = self.clean_fsck_output('/fixture.raw')
        result = steam_vm.evaluate_offline_fsck(0, stdout, stderr, '/fixture.raw')
        self.assertTrue(result['accepted'])
        self.assertEqual(result['reason_codes'], [])
        self.assertEqual(result['passes_and_summary'], [1, 2, 3, 4, 5, 'summary'])

    def test_fsck_replays_actual_clean_and_declined_optimization_logs(self):
        samples = [('steam-continuation-20261017/run6-offline-fsck.log', True),
                   ('gui-local-20261017/build-volume-fsck.log', False)]
        for relative, accepted in samples:
            with self.subTest(relative=relative):
                data = (ROOT/'evidence'/relative).read_text()
                target = next(line.rsplit(': ', 1)[0] for line in data.splitlines()
                              if ' files (' in line and line.endswith(' blocks'))
                target = target.replace('Freddy_Fazbear', 'Freddy Fazbear')
                result = steam_vm.evaluate_offline_fsck(0, data, '', target)
                self.assertEqual(result['accepted'], accepted)

    def test_fsck_matches_e2fsck_display_normalization_without_loosening_target(self):
        target = '/fixture directory/disk:name.raw'
        stdout, stderr = self.clean_fsck_output(target)
        self.assertIn('/fixture_directory/disk_name.raw:', stdout)
        self.assertTrue(steam_vm.evaluate_offline_fsck(0, stdout, stderr, target)['accepted'])
        self.assertFalse(steam_vm.evaluate_offline_fsck(0, stdout, stderr, '/other.raw')['accepted'])

    def test_fsck_zero_exit_cannot_hide_proposals_errors_or_unknown_output(self):
        stdout, stderr = self.clean_fsck_output('/fixture.raw')
        diagnostics = [
            'Inode 419625 extent tree (at level 2) could be narrower.  Optimize? no',
            'Deleted inode 370 has zero dtime.  Fix? no',
            'Inode 1192 was part of the orphaned inode list.  IGNORED.',
            '/fixture.raw: ********** WARNING: Filesystem still has errors **********',
            '/fixture.raw: recovering journal',
            'Warning: skipping journal recovery because doing a read-only filesystem check.',
            '/fixture.raw: ***** FILE SYSTEM WAS MODIFIED *****',
            'An unfamiliar future-tool diagnostic requires review',
        ]
        for diagnostic in diagnostics:
            for stream in ('stdout', 'stderr'):
                with self.subTest(diagnostic=diagnostic, stream=stream):
                    out = stdout + (diagnostic+'\n' if stream == 'stdout' else '')
                    err = stderr + (diagnostic+'\n' if stream == 'stderr' else '')
                    result = steam_vm.evaluate_offline_fsck(0, out, err, '/fixture.raw')
                    self.assertFalse(result['accepted'])
                    self.assertIn('unapproved_output', result['reason_codes'])
                    self.assertEqual(result['unexpected_lines'][0]['stream'], stream)

    def test_fsck_rejects_incomplete_wrong_target_and_duplicate_evidence(self):
        stdout, stderr = self.clean_fsck_output('/fixture.raw')
        lines = stdout.splitlines(keepends=True)
        cases = [('', ''), (stdout, ''), (''.join(lines[1:]), stderr),
                 (''.join(lines[:-1]), stderr), (stdout+lines[-1], stderr),
                 (lines[1]+lines[0]+''.join(lines[2:]), stderr),
                 (stdout.replace('/fixture.raw:', '/other.raw:'), stderr),
                 (stdout, stderr+stderr)]
        for out, err in cases:
            with self.subTest(stdout=out, stderr=err):
                self.assertFalse(steam_vm.evaluate_offline_fsck(0, out, err, '/fixture.raw')['accepted'])

    def test_fsck_rejects_nonzero_or_noninteger_exit_even_with_clean_text(self):
        stdout, stderr = self.clean_fsck_output('/fixture.raw')
        for code in (1, 2, 4, 8, 16, 32, 128, -9, None, False, 0.0, '0'):
            with self.subTest(code=code):
                result = steam_vm.evaluate_offline_fsck(code, stdout, stderr, '/fixture.raw')
                self.assertFalse(result['accepted'])
                self.assertIn('nonzero_or_invalid_exit', result['reason_codes'])

    def test_fsck_exit_zero_with_proposal_preserves_copy_and_full_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            stdout, stderr = self.clean_fsck_output(root/'offline-fsck.raw')
            stderr += 'Inode 419625 extent tree (at level 2) could be narrower.  Optimize? no\n'
            def run(argv, **kwargs):
                if argv[1] == 'info':
                    return SimpleNamespace(stdout=json.dumps({'virtual-size': 1024}))
                if argv[1] == 'convert':
                    os.write(kwargs['pass_fds'][0], b'preserve rejected filesystem')
                    return SimpleNamespace(returncode=0)
                self.assertEqual(argv, ['/usr/sbin/e2fsck', '-f', '-n', str(root/'offline-fsck.raw')])
                self.assertEqual(kwargs['env']['LC_ALL'], 'C')
                return SimpleNamespace(returncode=0, stdout=stdout, stderr=stderr)
            with patch.object(steam_vm.subprocess, 'run', side_effect=run), \
                 patch.object(steam_vm.shutil, 'disk_usage', return_value=SimpleNamespace(free=8*1024**3)):
                with self.assertRaisesRegex(RuntimeError, 'no repair or boot'):
                    steam_vm.offline_fsck(root/'disk', root, ['qemu-img'], {'LC_ALL': 'non-C-fixture'})
            self.assertEqual((root/'offline-fsck.raw').read_bytes(), b'preserve rejected filesystem')
            self.assertEqual((root/'offline-fsck.stdout.log').read_text(), stdout)
            self.assertEqual((root/'offline-fsck.stderr.log').read_text(), stderr)
            self.assertEqual((root/'offline-fsck.log').read_text(), stdout+stderr)
            receipt = json.loads((root/'offline-fsck.json').read_text())
            self.assertEqual(receipt['exit_code'], 0)
            self.assertEqual(receipt['status'], 'failed')
            self.assertFalse(receipt['evaluation']['accepted'])

    def test_fsck_removes_own_flattened_copy_only_after_strict_acceptance(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            stdout, stderr = self.clean_fsck_output(root/'offline-fsck.raw')
            def run(argv, **kwargs):
                if argv[1] == 'info':
                    return SimpleNamespace(stdout=json.dumps({'virtual-size': 1024}))
                if argv[1] == 'convert':
                    os.write(kwargs['pass_fds'][0], b'checked filesystem')
                    return SimpleNamespace(returncode=0)
                return SimpleNamespace(returncode=0, stdout=stdout, stderr=stderr)
            with patch.object(steam_vm.subprocess, 'run', side_effect=run), \
                 patch.object(steam_vm.shutil, 'disk_usage', return_value=SimpleNamespace(free=8*1024**3)):
                receipt = steam_vm.offline_fsck(root/'disk', root, ['qemu-img'], {})
            self.assertEqual(receipt['status'], 'pass')
            self.assertTrue(receipt['evaluation']['accepted'])
            self.assertFalse((root/'offline-fsck.raw').exists())

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

    def test_offline_fsck_uses_supplied_pinned_loader_and_keeps_read_only_flags(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);stdout,stderr=self.clean_fsck_output(root/'offline-fsck.raw')
            checker=['/fixture/ld-linux','--library-path','/fixture/lib','/fixture/e2fsck']
            def run(argv,**kwargs):
                if argv[1]=='info':return SimpleNamespace(stdout=json.dumps({'virtual-size':1024}))
                if argv[1]=='convert':
                    os.write(kwargs['pass_fds'][0],b'checked fixture');return SimpleNamespace(returncode=0)
                self.assertEqual(argv,[*checker,'-f','-n',str(root/'offline-fsck.raw')])
                return SimpleNamespace(returncode=0,stdout=stdout,stderr=stderr)
            with patch.object(steam_vm.subprocess,'run',side_effect=run), \
                    patch.object(steam_vm.shutil,'disk_usage',return_value=SimpleNamespace(free=8*1024**3)):
                receipt=steam_vm.offline_fsck(root/'disk',root,['qemu-img'],{},fsck_command=checker)
            self.assertTrue(receipt['evaluation']['accepted'])
            self.assertEqual(receipt['fsck_command'],[*checker,'-f','-n',str(root/'offline-fsck.raw')])

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
