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

    def test_arm64_proton_layout_is_detected_without_running_it(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            steam = root / 'Steam'
            proton = steam / 'compatibilitytools.d/ARM64 fixture'
            binary = proton / 'files/bin-arm64'
            binary.mkdir(parents=True)
            (proton / 'proton').write_text('must not execute')
            elf = bytearray(20)
            elf[:6] = b'\x7fELF\x02\x01'
            elf[18:20] = (183).to_bytes(2, 'little')
            for name in ('wine', 'wineserver'):
                (binary / name).write_bytes(elf)
            result = probe.inventory(steam, root)
            tool = result['proton_candidates'][0]
            self.assertIsNone(tool['wine_elf_machine'])
            self.assertIsNone(tool['wine64_elf_machine'])
            self.assertEqual(tool['wine_arm64_elf_machine'], 183)
            self.assertEqual(tool['wineserver_arm64_elf_machine'], 183)
            self.assertFalse(result['execution_tested'])
            self.assertFalse(result['game_launch_verified'])
            outside = root / 'private-file'
            outside.write_bytes(elf)
            (binary / 'wine').unlink()
            (binary / 'wine').symlink_to(outside)
            confined = probe.inventory(steam, root)['proton_candidates'][0]
            self.assertIsNone(confined['wine_arm64_elf_machine'])
            self.assertEqual(confined['wineserver_arm64_elf_machine'], 183)

    def test_launcher_symlink_keeps_architecture_and_does_not_follow_escape(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            steam = root / 'Steam'
            directory = steam / 'steamrt64/pv-runtime/steam-runtime-steamrt/bin'
            directory.mkdir(parents=True)
            target = directory / 'srt-launcher-service'
            elf = bytearray(20)
            elf[:6] = b'\x7fELF\x02\x01'
            elf[18:20] = (62).to_bytes(2, 'little')
            target.write_bytes(elf)
            target.chmod(0o755)
            link = directory / 'steam-runtime-launcher-service'
            link.symlink_to(target.name)
            result = probe.inventory(steam, root)
            self.assertEqual(result['runtime_launcher_candidates'][0]['elf_machine'], 62)
            self.assertTrue(result['runtime_launcher_candidates'][0]['executable'])
            self.assertFalse(result['game_launch_verified'])
            link.unlink()
            outside = root / 'private-account-file'
            outside.write_text('DO_NOT_INSPECT')
            link.symlink_to(outside)
            self.assertEqual(probe.inventory(steam, root)['runtime_launcher_candidates'], [])


if __name__ == '__main__':
    unittest.main()
