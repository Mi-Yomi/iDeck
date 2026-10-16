"""Cross-check the actual mke2fs golden header and opt-in real Swift helper.

The Swift helper runs real IO/ownership tests; no Apple or guest-boot emulation.
"""
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
EXPERIMENT = ROOT / "experiments/linux-guest"


class DesktopDiskChecks(unittest.TestCase):
    def test_real_mke2fs_header_matches_documented_contract(self):
        golden = json.loads((EXPERIMENT / "ios/tests/fixtures/desktop-ext4-superblock.json").read_text())
        header = bytes.fromhex(golden["header_hex"])
        self.assertEqual(len(header), 1024)
        self.assertEqual(hashlib.sha256(header).hexdigest(), golden["superblock_sha256"])
        self.assertEqual(struct.unpack_from("<H", header, 0x38)[0], 0xEF53)
        self.assertEqual(struct.unpack_from("<III", header, 0x5c), (44, 194, 1091))
        lock = json.loads((EXPERIMENT / "ipa/desktop-rootfs.lock.json").read_text())
        self.assertEqual(lock["image"]["features"], golden["features"])

    @unittest.skipUnless(os.environ.get("IDECK_SWIFTC"), "explicit existing Swift toolchain required")
    def test_actual_swift_owner_and_validation_regressions(self):
        with tempfile.TemporaryDirectory(prefix="ideck-desktop-swift-") as temporary:
            executable = Path(temporary) / "disk-checks"
            sources = [EXPERIMENT / name for name in (
                "ios/LinuxDesktopDisk.swift", "ios/tests/DesktopDiskChecks.swift", "ios/tests/desktop/main.swift")]
            subprocess.run([os.environ["IDECK_SWIFTC"], "-module-cache-path", str(Path(temporary) / "module-cache"),
                            *map(str, sources), "-o", str(executable)], cwd=ROOT, check=True,
                           capture_output=True, text=True, timeout=90)
            result = subprocess.run([str(executable)], cwd=ROOT, check=True, capture_output=True,
                                    text=True, timeout=30)
            self.assertIn("LINUX_DESKTOP_DISK_CHECKS_PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
