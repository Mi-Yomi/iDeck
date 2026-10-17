"""Offline resolver contracts; signatures/closure are simulated in unit fixtures.

The real pinned-index regeneration is a separate recorded command, not claimed
by these tests. No package installation, download or VM operation occurs here.
"""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import steam_dependencies as dependencies


class SteamDependencies(unittest.TestCase):
    def setUp(self):
        self.gui_path = ROOT/'ipa/gui-inputs.lock.json'
        self.inventory_path = ROOT/'evidence/steam-arm64-20261017/elf-needed.json'
        self.gui = json.loads(self.gui_path.read_text())
        self.lock = json.loads((ROOT/'ipa/steam-dependencies.lock.json').read_text())
        self.closure = self.gui['packages']+self.lock['extra_packages']
        self.records = [{'Package': pin['name'], 'Version': pin['version'],
                         'Architecture': pin['architecture'], 'Filename': pin['filename'],
                         'SHA256': pin['sha256'], 'Size': str(pin['size']),
                         'Installed-Size': str(pin['installed_size_kib'])} for pin in self.closure]

    def generate(self, closure):
        release = self.gui['release']
        # Paths are read-only fixtures here; all filesystem/network solver calls
        # are mocked. The real create() still validates GUI pins and preservation.
        with patch.object(dependencies.base, 'fetch', return_value=Path('/unused/InRelease')), \
             patch.object(dependencies.base, 'verify_release', return_value=({}, release['signer_fingerprints'])), \
             patch.object(dependencies.base, 'index_descriptor', return_value=release['indexes'][0]), \
             patch.object(dependencies.base, 'load_index', return_value=(self.records, Path('/unused/Packages'))), \
             patch.object(dependencies.base, 'resolve', return_value=closure) as solver:
            value = dependencies.create(self.gui_path, self.inventory_path, Path('/unused'), Path('/unused/keyring'))
        return value, solver.call_args.args[2]

    def test_program_dependency_reaches_solver_and_keeps_soname_evidence_separate(self):
        value, selected = self.generate(self.closure)
        self.assertIn('lsof', selected)
        self.assertIn('lsof', value['selection']['direct'])
        self.assertEqual(value['observed_program_dependencies']['lsof']['package'], 'lsof')
        self.assertEqual(value['observed_program_dependencies']['lsof']['required_by'], 'GetIPCConnectionDetails')
        self.assertNotIn('lsof', value['observed_soname_packages'])
        self.assertEqual(value['release'], self.gui['release'])
        self.assertEqual(value['gui_inputs_sha256'], dependencies.base.sha256(self.gui_path))
        self.assertEqual(len(value['extra_packages']), 45)
        self.assertEqual(value['combined_closure_count'], 386)
        self.assertFalse(value['boundaries']['steam_window_verified'])

    def test_gui_removal_or_version_change_is_refused(self):
        for change in ('remove', 'version'):
            closure = copy.deepcopy(self.closure)
            if change == 'remove': closure.pop(0)
            else: closure[0]['version'] += '-changed'
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, 'accepted GUI package'):
                self.generate(closure)

    def test_gui_pin_must_still_match_authenticated_index(self):
        self.records[0]['SHA256'] = '0'*64
        with self.assertRaisesRegex(ValueError, 'authenticated index'):
            self.generate(self.closure)


if __name__ == '__main__': unittest.main()
