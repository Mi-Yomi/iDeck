"""POSIX offline host-runner guards; fixtures never claim an actual VM boot."""
import os
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
