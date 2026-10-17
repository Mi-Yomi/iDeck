import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('game_preflight', Path(__file__).resolve().parents[1] / 'tools/steam_game_preflight.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class GamePreflightTests(unittest.TestCase):
    def test_runtime_presence_never_claims_game_or_gpu_success_or_reads_accounts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            steam = root / 'Steam'
            proton = steam / 'steamapps/common/Proton fixture'
            (proton / 'files/bin').mkdir(parents=True)
            (proton / 'proton').write_text('do not execute')
            elf = bytearray(20)
            elf[:6] = b'\x7fELF\x02\x01'
            elf[18:20] = (183).to_bytes(2, 'little')
            (proton / 'files/bin/wine').write_bytes(elf)
            private = steam / 'config'
            private.mkdir()
            (private / 'loginusers.vdf').write_text('PRIVATE_ACCOUNT_MARKER')
            result = probe.inventory(steam, root)
            self.assertEqual(result['proton_candidates'][0]['wine_elf_machine'], 183)
            self.assertIsNone(result['proton_candidates'][0]['wine64_elf_machine'])
            self.assertFalse(result['game_launch_verified'])
            self.assertFalse(result['accelerated_graphics_verified'])
            self.assertNotIn('PRIVATE_ACCOUNT_MARKER', str(result))
            self.assertEqual((private / 'loginusers.vdf').read_text(), 'PRIVATE_ACCOUNT_MARKER')

    def test_non_elf_and_missing_runtime_are_not_native_binaries(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'wine'
            self.assertIsNone(probe.elf_machine(path))
            path.write_text('#!/bin/sh\nexit 0\n')
            self.assertIsNone(probe.elf_machine(path))


if __name__ == '__main__':
    unittest.main()
