import hashlib
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from steam_abi import elf, packages
from host_smoke import decode_events, validate_events, verify_assets, ppm_rgb


class InputGuards(unittest.TestCase):
    def test_listing_and_syn_are_not_input(self):
        with self.assertRaises(ValueError):
            decode_events('QEMU Virtio Keyboard', 'keyboard')
        with self.assertRaises(ValueError):
            validate_events([{"type": 0, "code": 0, "value": 0}], [])

    def test_truncated_event_rejected(self):
        with self.assertRaises(ValueError):
            decode_events('IDECK_EVENTS_BEGIN:keyboard\n01 02\nIDECK_EVENTS_END:keyboard', 'keyboard')

    def test_missing_release_rejected(self):
        with self.assertRaises(ValueError):
            validate_events([{"type": 1, "code": 30, "value": 1}], [])

    def test_independent_linux_event_decode(self):
        raw = struct.pack('<qqHHi', 17, 500, 1, 30, 1)
        result = decode_events('IDECK_EVENTS_BEGIN:keyboard\n' + raw.hex() + '\nIDECK_EVENTS_END:keyboard', 'keyboard')
        self.assertEqual(result, [{"seconds": 17, "microseconds": 500, "type": 1, "code": 30, "value": 1}])


class IntegrityGuards(unittest.TestCase):
    def test_bad_elfs_rejected(self):
        for data in (b'MZ' + bytes(64), b'\x7fELF', b'\x7fELF\x03\x01' + bytes(64)):
            with self.assertRaises(ValueError):
                elf(data)

    def test_valid_elf32_and_missing_program_headers(self):
        identity = b'\x7fELF\x01\x01\x01' + bytes(9)
        header = struct.pack('<HHIIIIIHHHHHH', 2, 3, 1, 0, 0, 0, 0, 52, 32, 0, 0, 0, 0)
        self.assertEqual(elf(identity + header)['machine'], 'i386')
        corrupt = bytearray(identity + header)
        struct.pack_into('<I', corrupt, 28, 52)
        struct.pack_into('<H', corrupt, 44, 1)
        with self.assertRaises(ValueError):
            elf(bytes(corrupt))

    def test_manifest_paths_and_hashes_rejected(self):
        for name, digest in (('../bad.zip', 'a'*64), ('good.zip', 'no-hash')):
            content = f'"linuxarm64"\n{{\n"version" "1"\n\t"bins_linuxarm64_linuxarm64"\n{{"file" "{name}" "sha2" "{digest}" "size" "10"}}\n}}'
            with self.assertRaises(ValueError):
                packages(content.encode())

    def test_corrupt_and_traversal_assets_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = b'original'
            asset = {"file": "vmlinuz-virt", "size": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
            profile = {"schema": 1, "kernel": asset, "initramfs": dict(asset, file='initramfs-ideck.gz'),
                       "width": 800, "height": 600, "cpu": "cortex-a72", "memory_mib": 1024,
                       "vcpus": 4, "tcg_cache_mib": 256}
            (root / 'vmlinuz-virt').write_bytes(b'changed!')
            (root / 'initramfs-ideck.gz').write_bytes(payload)
            (root / 'profile.json').write_text(json.dumps(profile))
            with self.assertRaises(ValueError):
                verify_assets(root)
            profile['kernel']['file'] = '../vmlinuz-virt'
            (root / 'profile.json').write_text(json.dumps(profile))
            with self.assertRaises(ValueError):
                verify_assets(root)

    def test_empty_screenshot_rejected(self):
        with self.assertRaises(ValueError):
            ppm_rgb(b'P6\n800 600\n255\n')


if __name__ == '__main__':
    unittest.main()
