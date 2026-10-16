"""Offline closure/rejection tests; real signed evdev fixture is the locked probe.

These are not evidence that unavailable ext4 bytes load in the guest kernel.
"""
import gzip
import hashlib
import json
import io
import os
import struct
import sys
import tarfile
import tempfile
import unittest
from unittest import mock
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
        external = lock["minimal_external_input"]
        self.assertEqual(external["sha256"], modules.MODLOOP_SHA256)
        self.assertEqual(external["maximum_size_bytes"], modules.MAX_MODLOOP_SIZE)
        self.assertIsNone(external["size"])
        self.assertFalse(external["standalone_boundaries"]["archive_bytes_verified"])
        self.assertFalse(external["standalone_boundaries"]["kernel_bytes_verified"])
        evidence = EXPERIMENT.parents[1] / external["source_provenance"]["evidence"]
        self.assertEqual(modules.sha(evidence.read_bytes()), external["source_provenance"]["evidence_sha256"])
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

    def test_standalone_wrong_missing_nonregular_and_reused_inputs_fail_before_tool(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, out = root / "modloop-virt", root / "out"
            with mock.patch.object(modules, "extract_closure") as extract:
                with self.assertRaises(FileNotFoundError):
                    modules.prepare(None, out, root / "never-executed", modloop=source)
                source.write_bytes(b"not the locked module image")
                with self.assertRaisesRegex(ValueError, "modloop differs"):
                    modules.prepare(None, out, root / "never-executed", modloop=source)
                with mock.patch.object(modules, "MAX_MODLOOP_SIZE", 1):
                    with self.assertRaisesRegex(ValueError, "bounded regular"):
                        modules.prepare(None, out, root / "never-executed", modloop=source)
                link = root / "symlink"
                link.symlink_to(source)
                with self.assertRaises(OSError):
                    modules.prepare(None, out, root / "never-executed", modloop=link)
                fifo = root / "fifo"
                os.mkfifo(fifo)
                with self.assertRaisesRegex(ValueError, "bounded regular"):
                    modules.prepare(None, out, root / "never-executed", modloop=fifo)
                out.mkdir()
                with self.assertRaisesRegex(ValueError, "already exists"):
                    modules.prepare(None, out, root / "never-executed", modloop=source)
                extract.assert_not_called()

    def test_both_input_modes_use_same_guarded_closure_with_honest_verification_flags(self):
        # Small synthetic transport fixtures, never a claimed ext4 payload.
        image_bytes, kernel = b"synthetic image transport fixture", b"synthetic kernel fixture"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image = root / "modloop-virt"
            image.write_bytes(image_bytes)
            archive = root / "fixture.tar"
            with tarfile.open(archive, "w") as stream:
                for name, data in (("boot/modloop-virt", image_bytes), ("boot/vmlinuz-virt", kernel)):
                    member = tarfile.TarInfo(name)
                    member.size = len(data)
                    stream.addfile(member, io.BytesIO(data))

            def capture(snapshot, out, tool, verification):
                self.assertEqual(snapshot.read_bytes(), image_bytes)
                return verification

            with mock.patch.object(modules, "MODLOOP_SHA256", modules.sha(image_bytes)), \
                    mock.patch.object(modules, "KERNEL_SHA256", modules.sha(kernel)), \
                    mock.patch.object(modules.prepare_guest, "SIZE", archive.stat().st_size), \
                    mock.patch.object(modules.prepare_guest, "SHA256", modules.sha(archive.read_bytes())), \
                    mock.patch.object(modules, "extract_closure", side_effect=capture) as extract:
                standalone = modules.prepare(None, root / "standalone", root / "tool", modloop=image)
                packed = modules.prepare(archive, root / "packed", root / "tool")
                self.assertEqual(extract.call_count, 2)
                self.assertFalse(standalone["archive_bytes_verified"])
                self.assertFalse(standalone["kernel_bytes_verified"])
                self.assertIsNone(standalone["kernel_sha256"])
                self.assertIsNone(standalone["archive_sha256"])
                self.assertIsNone(standalone["archive_size"])
                self.assertTrue(packed["archive_bytes_verified"])
                self.assertTrue(packed["kernel_bytes_verified"])
                self.assertEqual(packed["kernel_sha256"], modules.sha(kernel))

    def test_common_closure_validates_real_module_and_publishes_truthful_manifest(self):
        # Use the existing real evdev fixture to exercise the common validator;
        # requested closure is mocked, so this test does not claim ext4 evidence.
        path = "kernel/drivers/input/evdev.ko"
        members = {"modules.dep": (path + ":\n").encode(), "modules.softdep": b"",
                   "modules.builtin": b"kernel/test/builtin.ko\n", path: self.evdev}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image = root / "snapshot"
            image.write_bytes(b"fixture")
            with mock.patch.object(modules, "closure", return_value=[path]), \
                    mock.patch.object(modules, "cat_image", side_effect=lambda tool, image, name, *a, **k: members[name.removeprefix(modules.MODULE_PREFIX)]):
                result = modules.extract_closure(image, root / "out", root / "tool", {
                    "archive_bytes_verified": False, "kernel_bytes_verified": False, "kernel_sha256": None})
                self.assertEqual(result["modules"][0]["sha256"], modules.sha(self.evdev))
                self.assertEqual(result["total_module_bytes"], len(self.evdev))
                self.assertEqual(result["expected_kernel_sha256"], modules.KERNEL_SHA256)
                self.assertFalse(result["kernel_bytes_verified"])
                self.assertIsNone(result["kernel_sha256"])
                self.assertEqual(result["kernel_load_and_ext4_mount"], "not_tested")
                self.assertEqual((root / "out" / modules.MODULE_PREFIX / path).read_bytes(), self.evdev)

    def test_input_modes_mutually_exclusive_in_api_and_cli(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for archive, modloop in ((None, None), (root / "a", root / "m")):
                with self.assertRaisesRegex(ValueError, "exactly one"):
                    modules.prepare(archive, root / "out", root / "tool", modloop=modloop)
            import subprocess
            script = EXPERIMENT / "tools/desktop_modules.py"
            for inputs in ([], ["--archive", "a", "--modloop", "m"]):
                result = subprocess.run([sys.executable, str(script), *inputs,
                                         "--out", str(root / "out"), "--unsquashfs", str(root / "tool")],
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 2)
            self.assertFalse((root / "out").exists())


if __name__ == "__main__":
    unittest.main()
