"""Input trust regressions only. No mocked X server is a GUI acceptance gate."""
import copy
import json
import os
import stat
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import gui_rootfs as gui
import gui_vm
import debian_rootfs as base


class GUIInputs(unittest.TestCase):
    def setUp(self):
        self.lock=json.loads((ROOT/'ipa/gui-inputs.lock.json').read_text())

    def test_real_closure_and_separate_image_identity(self):
        gui.validate(self.lock)
        names={p['name'] for p in self.lock['packages']}
        self.assertTrue(set(gui.GUI).issubset(names))
        self.assertTrue({'libsystemd-shared','libgtk-3-0t64','libinput10','libdrm2'}.issubset(names))
        self.assertEqual(self.lock['totals']['guest']['package_count'],341)
        self.assertGreater(self.lock['totals']['guest']['installed_size_bytes'],512*1024**2)
        self.assertNotEqual(gui.UUID,base.IMAGE_UUID)
        self.assertIsNone(self.lock['future_image']['size_bytes'])
        self.assertFalse(self.lock['boundaries']['gui_verified'])
        self.assertFalse(self.lock['boundaries']['package_configuration_verified'])

    def test_invalid_inputs_fail_before_fetch(self):
        cases=[lambda x:x['packages'][0].update(architecture='amd64'),
               lambda x:x['packages'][0].update(filename='pool/../escape.deb'),
               lambda x:x['packages'][0].update(size=True),
               lambda x:x['packages'][0].update(sha256='a'*63),
               lambda x:x['packages'].append(x['packages'][0]),
               lambda x:x['selection'].update(install_recommends=True),
               lambda x:x['selection']['direct'].remove('udev'),
               lambda x:x['future_image'].update(size_bytes=4*1024**3),
               lambda x:x['future_image'].update(uuid=base.IMAGE_UUID),
               lambda x:x['release'].update(url='https://security.debian.org/debian-security/dists/trixie-security/InRelease'),
               lambda x:x['totals']['guest'].update(download_bytes=0),
               lambda x:x['boundaries'].update(gui_verified=True)]
        for mutation in cases:
            lock=copy.deepcopy(self.lock);mutation(lock)
            with self.subTest(mutation=mutation),mock.patch.object(base,'fetch') as fetch:
                with self.assertRaises(ValueError):gui.authenticate(lock,Path('/uncreated'))
                fetch.assert_not_called()

    def test_authentic_subset_cannot_be_called_a_dependency_closure(self):
        # Test just the trust boundary. All real VM acceptance uses actual QEMU.
        lock=self.lock
        records=[{'Filename':p['filename'],'pin':p} for p in lock['packages']+lock['provision_kernel']]
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(base,'fetch',return_value=Path(tmp)/'InRelease'), \
             mock.patch.object(base,'verify_release',return_value=({},lock['release']['signer_fingerprints'])), \
             mock.patch.object(base,'index_descriptor',return_value=lock['release']['indexes'][0]), \
             mock.patch.object(base,'load_index',return_value=(records,Path(tmp)/'Packages')), \
             mock.patch.object(base,'package_pin',side_effect=lambda r:r['pin']), \
             mock.patch.object(base,'resolve',return_value=lock['packages'][1:]):
            with self.assertRaisesRegex(ValueError,'dependency closure'):
                gui.authenticate(lock,Path(tmp))

    def test_untrusted_pin_fails_before_solver(self):
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(base,'fetch',return_value=Path(tmp)/'InRelease'), \
             mock.patch.object(base,'verify_release',return_value=({},self.lock['release']['signer_fingerprints'])), \
             mock.patch.object(base,'index_descriptor',return_value=self.lock['release']['indexes'][0]), \
             mock.patch.object(base,'load_index',return_value=([],Path(tmp)/'Packages')), \
             mock.patch.object(base,'resolve') as solve:
            with self.assertRaisesRegex(ValueError,'package is not authenticated'):
                gui.authenticate(self.lock,Path(tmp))
            solve.assert_not_called()

    def test_missing_offline_cache_creates_no_vm_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);out=root/'vm'
            with self.assertRaisesRegex(ValueError,'offline cache missing'):
                gui_vm.prepare(ROOT/'ipa/gui-inputs.lock.json',root/'cache',out)
            self.assertFalse(out.exists())
        base.OFFLINE=False

    def test_guest_public_modes_survive_private_host_umask(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'tree'; old=os.umask(0o077)
            try:
                for name in gui_vm.PUBLIC_DIRECTORIES:
                    (root/name).mkdir(parents=True,exist_ok=True)
                (root/'etc/X11').mkdir(parents=True)
                for name in ('usr/local/share/ideck/tint2rc','etc/X11/ideck.conf',
                             'usr/local/share/applications/editor.desktop'):
                    (root/name).write_text('fixture')
                (root/'home/ideck').mkdir(parents=True)
                (root/'home/ideck/private').write_text('private')
            finally:os.umask(old)
            gui_vm.canonical_gui_modes(root)
            mode=lambda p:stat.S_IMODE(p.stat().st_mode)
            self.assertEqual(mode(root),0o755)
            for name in gui_vm.PUBLIC_DIRECTORIES:self.assertEqual(mode(root/name),0o755)
            self.assertEqual(mode(root/'usr/local/share/ideck/tint2rc'),0o644)
            self.assertEqual(mode(root/'usr/local/share/applications/editor.desktop'),0o644)
            self.assertEqual(mode(root/'home/ideck'),0o700)
            self.assertEqual(mode(root/'home/ideck/private'),0o600)

    def test_low_space_refuses_before_any_vm_output(self):
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(gui,'download'), \
             mock.patch.object(gui_vm.shutil,'disk_usage',return_value=type('Usage',(),{'free':1})()):
            out=Path(tmp)/'vm'
            with self.assertRaisesRegex(ValueError,'insufficient space'):
                gui_vm.prepare(ROOT/'ipa/gui-inputs.lock.json',Path(tmp)/'cache',out)
            self.assertFalse(out.exists())
        base.OFFLINE=False

    def test_unsupported_resolver_architecture_rejected(self):
        with self.assertRaisesRegex(ValueError,'unsupported resolver architecture'):
            base.resolve([],Path('/uncreated'),[],Path('/uncreated'),architecture='x86_64')
