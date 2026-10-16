"""Acceptance-report rejection tests; synthetic logs are not boot evidence."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from check_debian_ext4_boot import boot_pass, cpio_suffix
from test_terminal import cpio_entries


class Ext4BootAcceptance(unittest.TestCase):
    def test_suffix_preserves_alpine_merged_usr_aliases(self):
        for prefix in ("lib", "bin", "sbin"):
            with self.assertRaisesRegex(ValueError, "merged-/usr alias"):
                cpio_suffix({prefix + "/fixture": (b"fixture", 0o644)})
        entries = cpio_entries(cpio_suffix({"usr/lib/modules/fixture.ko": (b"fixture", 0o644)}))
        self.assertNotIn("lib", entries)
        self.assertEqual(entries["usr/lib/modules/fixture.ko"][1], b"fixture")

    def test_all_stages_and_clean_shutdown_are_required(self):
        markers = ["IDECK_EXT4_BOOT:1", "IDECK_EXT4_MOUNTED", "IDECK_DEBIAN_GLIBC:glibc 2.41",
                   "IDECK_DEBIAN_PACKAGE_AUDIT_PASS", "IDECK_POSIX_PASS:1", "IDECK_EXT4_CLEAN_UNMOUNT:1"]
        text = "\n".join(markers)
        self.assertTrue(boot_pass(text, 1, 0))
        self.assertFalse(boot_pass(text, 2, 0))
        self.assertFalse(boot_pass(text, 1, 1))
        for marker in markers:
            self.assertFalse(boot_pass(text.replace(marker, ""), 1, 0))
        for failure in ("IDECK_EXT4_FAILED:unmount", "Kernel panic", "EXT4-fs error"):
            self.assertFalse(boot_pass(text + "\n" + failure, 1, 0))


if __name__ == "__main__":
    unittest.main()
