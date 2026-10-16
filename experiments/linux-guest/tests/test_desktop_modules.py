"""Offline closure/rejection tests; real signed evdev fixture is the locked probe.

These are not evidence that unavailable ext4 bytes load in the guest kernel.
"""
import gzip
import hashlib
import json
import struct
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

EXPERIMENT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXPERIMENT / "tools"))
import desktop_modules as modules
from test_terminal import cpio_entries


class DesktopModuleChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tarfile.open(EXPERIMENT / "husk/linux-probe-guest.tar.gz") as source:
            initrd = source.extractfile("initramfs-ideck.gz").read()
        cls.evdev = cpio_entries(gzip.decompress(initrd))["ideck/evdev.ko"][1]

    def test_source_lock_matches_original_probe_without_claiming_resolved_closure(self):
        lock = json.loads((EXPERIMENT / "ipa/desktop-kernel-source.lock.json").read_text())
        probe = json.loads((EXPERIMENT / "ipa/guest.lock.json").read_text())
        self.assertEqual(lock["archive"]["sha256"], modules.prepare_guest.SHA256)
        self.assertEqual(lock["archive"]["size"], modules.prepare_guest.SIZE)
        self.assertEqual(lock["kernel"]["sha256"], probe["files"]["vmlinuz-virt"]["sha256"])
        self.assertEqual(lock["kernel"]["expected_vermagic"], modules.VERMAGIC)
        self.assertEqual(lock["modloop"]["sha256"], modules.MODLOOP_SHA256)
        self.assertIsNone(lock["ext4_module_manifest"])
        self.assertIsNone(lock["ext4_module_bytes"])

    def test_real_locked_arm64_module_metadata_signature_and_vermagic(self):
        self.assertEqual(hashlib.sha256(self.evdev).hexdigest(),
                         "2959ebcb3ba19095d052be3cea1ec44e88982df94d52e5869612c30f9d9897c7")
        result = modules.module_metadata(self.evdev)
        self.assertEqual(result["vermagic"], modules.VERMAGIC)
        self.assertEqual(result["signature"]["kind"], "PKCS#7")
        self.assertEqual(result["signature"]["size"], 695)

    def test_unsigned_wrong_arch_and_wrong_vermagic_rejected(self):
        cases = [self.evdev[:-len(modules.SIGNATURE_MARKER)],
                 self.evdev.replace(b"6.18.35-0-virt", b"6.18.34-0-virt"),
                 self.evdev[:18] + b"\x3e\0" + self.evdev[20:]]
        for data in cases:
            with self.subTest(kind=len(data)), self.assertRaises(ValueError):
                modules.module_metadata(data)

    def test_stray_vermagic_and_truncated_section_tables_rejected(self):
        data = bytearray(self.evdev)
        struct.pack_into("<Q", data, 40, len(data) - 10)
        with self.assertRaises(ValueError):
            modules.module_metadata(data)
        data = self.evdev.replace(b".modinfo", b".notinfo")
        with self.assertRaises(ValueError):
            modules.module_metadata(data)

    def test_damaged_pkcs7_trailer_rejected(self):
        data = bytearray(self.evdev)
        trailer = len(data) - len(modules.SIGNATURE_MARKER) - 12
        data[trailer + 2] = 0  # Only PKCS#7 is accepted for these locked modules.
        with self.assertRaises(ValueError):
            modules.module_metadata(data)
        struct.pack_into(">I", data, trailer + 8, len(data))
        with self.assertRaises(ValueError):
            modules.module_metadata(data)
        data = bytearray(self.evdev)
        data[trailer - 695 + 1] = 0x80  # DER indefinite length is forbidden.
        with self.assertRaises(ValueError):
            modules.module_metadata(data)

    def test_dependency_and_soft_dependency_order_and_builtins(self):
        # Deliberately synthetic graph: no guessed ext4 dependency claim.
        dep = modules.dependencies(b"kernel/fs/ext4/ext4.ko: kernel/lib/helper.ko\n"
                                   b"kernel/lib/helper.ko:\n"
                                   b"kernel/lib/pre.ko:\n"
                                   b"kernel/lib/post.ko:\n")
        soft = modules.soft_dependencies(b"# fixture\nsoftdep ext4 pre: pre always_builtin post: post\n")
        result = modules.closure(dep, soft, b"kernel/lib/always_builtin.ko\n")
        self.assertEqual(result, ["kernel/lib/pre.ko", "kernel/lib/helper.ko",
                                  "kernel/fs/ext4/ext4.ko", "kernel/lib/post.ko"])

    def test_cycles_missing_and_ambiguous_modules_rejected(self):
        for dep in ({"kernel/ext4.ko": ["kernel/ext4.ko"]},
                    {"kernel/ext4.ko": ["kernel/missing.ko"]},
                    {"kernel/ext4.ko": [], "kernel/x/ext4.ko": []}):
            with self.subTest(dep=dep), self.assertRaises(ValueError):
                modules.closure(dep, {}, b"")
        with self.assertRaises(ValueError):
            modules.closure({"kernel/ext4.ko": []}, {"ext4": (["missing"], [])}, b"")

    def test_bad_or_duplicate_metadata_paths_rejected(self):
        for data in (b"kernel/../ext4.ko:\n", b"/kernel/ext4.ko:\n",
                     b"kernel/ext4.ko:\nkernel/ext4.ko:\n", b"kernel//ext4.ko:\n",
                     b"kernel/ext4.ko: kernel/missing.ko\n", b"kernel/ext4.ko.zst:\n"):
            with self.subTest(data=data), self.assertRaises(ValueError):
                modules.dependencies(data)
        for data in (b"softdep ext4 unknown\n", b"softdep ext4 pre: ../helper\n",
                     b"softdep ext4 pre: x\nsoftdep ext4 pre: y\n",
                     b"softdep foo_bar pre: x\nsoftdep foo-bar pre: y\n"):
            with self.assertRaises(ValueError):
                modules.soft_dependencies(data)

    def test_unverified_archive_and_existing_output_rejected_without_extraction(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "bad.tar.gz"
            archive.write_bytes(b"wrong bytes")
            with self.assertRaisesRegex(ValueError, "archive differs"):
                modules.prepare(archive, root / "out", root / "never-executed")
            self.assertFalse((root / "out").exists())
            with self.assertRaisesRegex(ValueError, "already exists"):
                modules.prepare(archive, root, root / "never-executed")


if __name__ == "__main__":
    unittest.main()
