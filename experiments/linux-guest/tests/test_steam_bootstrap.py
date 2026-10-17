"""Separate bootstrap source guards; these do not substitute for a real VM boot."""
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import prepare_steam_bootstrap as bootstrap


class SteamBootstrap(unittest.TestCase):
    def test_original_shutdown_and_every_original_byte_preserved(self):
        original = (ROOT/'guest/gui/ideck-desktop-init').read_bytes()
        generated = bootstrap.experimental_init(original)
        self.assertEqual(generated.replace(bootstrap.INJECT, b'', 1), original)
        start = original.index(b'shutdown() {')
        end = original.index(b'trap shutdown USR2 TERM INT')
        self.assertEqual(generated[start:end], original[start:end])
        self.assertIn(bootstrap.MARKER+bootstrap.INJECT+b'echo IDECK_DESKTOP_RECOVERY_READY', generated)

    def test_changed_or_ambiguous_insertion_point_rejected(self):
        original = (ROOT/'guest/gui/ideck-desktop-init').read_bytes()
        for source in (original.replace(bootstrap.MARKER, b''), original+bootstrap.MARKER):
            with self.assertRaisesRegex(ValueError, 'insertion point'):
                bootstrap.experimental_init(source)

    def test_network_module_paths_preserve_merged_usr_and_reject_alias_escape(self):
        self.assertEqual(bootstrap.module_destination('kernel/drivers/net/virtio_net.ko'),
                         'usr/lib/modules/6.18.35-0-virt/kernel/drivers/net/virtio_net.ko')
        for path in ('../lib/virtio_net.ko', '/lib/virtio_net.ko', 'kernel/../virtio_net.ko', 'kernel/net.ko/extra'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                bootstrap.module_destination(path)

    @unittest.skipUnless(os.name == 'posix', 'actual POSIX shell required')
    def test_generated_shell_parses(self):
        original = (ROOT/'guest/gui/ideck-desktop-init').read_bytes()
        result = subprocess.run(['/bin/sh','-n'], input=bootstrap.experimental_init(original), capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    @unittest.skipUnless(os.name == 'posix', 'actual POSIX shell required')
    def test_explicit_experiment_and_disposable_growth_optins_precede_mutation(self):
        # Execute the real guard against fixture cmdlines. Both denied routes
        # must exit before touching modules, addresses, resolver or guest files.
        for cmdline, error in (('console=ttyAMA0', 'steam_experiment_opt_in_required'),
                               ('ideck.steam_experiment=1', 'steam_disposable_overlay_required')):
            script = ('fail() { printf "%s\\n" "$1"; exit 23; }\n'
                      'cat() { printf "%s\\n" "'+cmdline+'"; }\n').encode()+bootstrap.INJECT
            result = subprocess.run(['/bin/sh'], input=script, capture_output=True)
            self.assertEqual(result.returncode, 23, result.stderr)
            self.assertEqual(result.stdout.decode().strip(), error)


if __name__ == '__main__':
    unittest.main()
