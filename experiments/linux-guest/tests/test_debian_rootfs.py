"""Offline trust/geometry/child-compat regressions; never downloads guest payload."""
import copy
import ctypes
import datetime as dt
import errno
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import struct
import sys
import tempfile
import unittest
from unittest import mock

EXPERIMENT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXPERIMENT / "tools"))
import debian_rootfs as builder


class DebianRootfsChecks(unittest.TestCase):
    def setUp(self):
        self.lock = json.loads((EXPERIMENT / "ipa/desktop-rootfs.lock.json").read_text())

    @unittest.skipUnless(shutil.which("sh"), "POSIX shell required")
    def test_audit_requires_successful_command_and_empty_output(self):
        for body, success in (("return 0", True), ("return 42", False),
                              ("echo broken-package; return 0", False),
                              ("echo broken-package; return 42", False)):
            with self.subTest(body=body):
                # Run the actual guard with a controlled command: an empty
                # failing audit must never reach the acceptance marker.
                script = ("set -eu\ndpkg() { " + body + "; }\n"
                          + builder.DPKG_AUDIT_CHECK + "echo AUDIT_ACCEPTED\n")
                result = subprocess.run(["sh", "-c", script], capture_output=True, text=True)
                self.assertEqual(result.returncode == 0, success)
                self.assertEqual("AUDIT_ACCEPTED" in result.stdout, success)

    def test_qemu_staging_handles_space_path_and_rechecks_digest(self):
        with tempfile.TemporaryDirectory(prefix="ideck spaced ") as temporary:
            root = Path(temporary)
            source = root / "input with spaces"
            source.write_bytes(b"reviewed helper fixture")
            output = root / "build with spaces"
            output.mkdir()
            relative = builder.stage_qemu_helper(source, output, builder.sha256(source))
            self.assertNotIn(" ", relative)
            self.assertEqual((output / relative).read_bytes(), source.read_bytes())
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                builder.stage_qemu_helper(source, output, "0" * 64)

    def test_locked_closure_is_exact_and_small_base_without_gui(self):
        builder.validate_lock(self.lock)
        packages = self.lock["packages"]
        self.assertEqual(len(packages), 90)
        self.assertEqual(sum(p["size"] for p in packages), 35157424)
        self.assertEqual(sum(p["installed_size_kib"] * 1024 for p in packages), 155331584)
        self.assertTrue({"libc6", "dash", "apt", "dpkg", "e2fsprogs", "passwd"}.issubset({p["name"] for p in packages}))
        self.assertEqual({p["name"] for p in self.lock["deferred_desktop_packages"]}, set(builder.DEFERRED))
        self.assertFalse(any(p["name"].startswith(("xserver-", "openbox", "xterm", "steam")) for p in packages))

    def test_reject_corrupt_lock_before_network_or_image_allocation(self):
        for change in (lambda x: x["image"].update(size_bytes=8 * 1024**3),
                       lambda x: x["image"].update(size_bytes=True),
                       lambda x: x["image"].update(size_bytes=64 * 1024**2 + 1),
                       lambda x: x["image"]["features"].update(incompat=0x2c2),
                       lambda x: x["packages"][0].update(architecture="amd64"),
                       lambda x: x["packages"].append(x["packages"][0]),
                       lambda x: x["packages"][0].update(sha256="0" * 63),
                       lambda x: x["selection"]["direct"].append("unlocked-package")):
            value = copy.deepcopy(self.lock)
            change(value)
            with self.assertRaises(ValueError):
                builder.validate_lock(value)

    def test_expired_future_and_wrong_release_rejected(self):
        now = dt.datetime(2026, 10, 16, tzinfo=dt.timezone.utc)
        base = {"Origin": "Debian", "Codename": "trixie", "Date": "Sat, 12 Sep 2026 07:55:41 UTC"}
        builder.check_freshness(base, now)
        for fields in ({**base, "Valid-Until": "Thu, 15 Oct 2026 00:00:00 UTC"},
                       {**base, "Date": "Sat, 17 Oct 2026 00:00:00 UTC"},
                       {**base, "Date": "Thu, 01 Jan 2026 00:00:00 UTC"},
                       {**base, "Codename": "sid"}):
            with self.assertRaises(ValueError):
                builder.check_freshness(fields, now)

    def test_signed_release_index_selects_exact_hash_address(self):
        fields = {"SHA256": "\n" + "a" * 64 + " 123 main/binary-arm64/Packages.xz\n"}
        descriptor = builder.index_descriptor(fields, "arm64")
        self.assertEqual(descriptor["size"], 123)
        self.assertTrue(descriptor["url"].endswith("/by-hash/SHA256/" + "a" * 64))
        with self.assertRaises(ValueError):
            builder.index_descriptor(fields, "amd64")

    def test_missing_or_invalid_signature_never_reaches_metadata_parser(self):
        with tempfile.TemporaryDirectory() as temporary:
            p = Path(temporary) / "fake-release"
            p.write_text("Origin: Debian\nCodename: trixie\n")
            with self.assertRaises(subprocess.CalledProcessError):
                builder.verify_release(p)

    def test_tampered_cached_blob_is_not_trusted(self):
        with tempfile.TemporaryDirectory() as temporary:
            p = Path(temporary) / "blob"
            p.write_bytes(b"bad")
            with mock.patch.object(builder.urllib.request, "urlopen", side_effect=OSError("offline")):
                with self.assertRaises(OSError):
                    builder.fetch("https://deb.debian.org/debian/blob", p, 3, "0" * 64)
            self.assertEqual(p.read_bytes(), b"bad")
            with self.assertRaises(ValueError):
                builder.fetch("http://deb.debian.org/debian/blob", p)

    def test_offline_cache_rehashes_and_never_fetches_or_allocates_on_miss(self):
        with tempfile.TemporaryDirectory() as temporary, mock.patch.object(builder, "OFFLINE", True):
            root = Path(temporary)
            good = root / "good"
            good.write_bytes(b"verified")
            digest = hashlib.sha256(b"verified").hexdigest()
            with mock.patch.object(builder.urllib.request, "urlopen") as network:
                self.assertEqual(builder.fetch("https://deb.debian.org/debian/blob", good, 8, digest), good)
                good.write_bytes(b"tampered")
                missing = root / "uncreated" / "blob"
                for path in (good, missing):
                    with self.assertRaisesRegex(ValueError, "offline cache missing or invalid"):
                        builder.fetch("https://deb.debian.org/debian/blob", path, 8, digest)
                network.assert_not_called()
            self.assertEqual(good.read_bytes(), b"tampered")
            self.assertFalse(missing.parent.exists())

    def test_offline_cannot_create_unreviewed_lock(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = subprocess.run([sys.executable, str(EXPERIMENT / "tools/debian_rootfs.py"),
                                     "lock", "--offline", "--cache", str(root / "cache"),
                                     "--lock", str(root / "lock.json")], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn("existing reviewed lock", result.stderr)
            self.assertEqual(list(root.iterdir()), [])

    def test_fresh_seed_normalization_preserves_locked_accounts_and_nonlog_data(self):
        epoch = 1789199741
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "seed"
            for name in ("etc", "var/log", "var/lib/dpkg", "usr/share/doc"):
                (root / name).mkdir(parents=True)
            shadow = "root:!*:22000:0:99999:7:::\nideck:!:23000:0:99999:7:::\ndaemon:*:20000:0:99999:7:::\n"
            for name in ("shadow", "shadow-"):
                (root / "etc" / name).write_text(shadow)
                (root / "etc" / name).chmod(0o640)
            log = root / "var/log/alternatives.log"
            log.write_text("variable installation timestamp\n")
            (root / "var/log/README").write_text("preserve package documentation")
            outside = Path(temporary) / "not-a-guest-log"
            outside.write_text("preserve external target")
            (root / "var/log/linked").symlink_to(outside)
            for name in ("var/lib/dpkg/status", "usr/share/doc/copyright"):
                (root / name).write_text("preserve package state/notices")
            builder.canonical_seed_content(root, epoch)
            self.assertEqual(log.read_bytes(), b"")
            self.assertEqual(outside.read_text(), "preserve external target")
            self.assertTrue((root / "var/log/linked").is_symlink())
            expected = shadow
            for day in (22000, 23000, 20000):
                expected = expected.replace(":" + str(day) + ":", ":" + str(epoch // 86400) + ":")
            for name in ("shadow", "shadow-"):
                p = root / "etc" / name
                self.assertEqual(p.read_text(), expected)
                self.assertEqual(p.stat().st_mode & 0o777, 0o640)
            for name in ("var/lib/dpkg/status", "usr/share/doc/copyright"):
                self.assertEqual((root / name).read_text(), "preserve package state/notices")
            builder.canonical_seed_content(root, epoch)
            self.assertEqual((root / "etc/shadow").read_text(), expected)
            self.assertEqual((root / "var/log/README").read_text(), "preserve package documentation")
            log.unlink()
            log.symlink_to(outside)
            builder.canonical_seed_content(root, epoch)
            self.assertTrue(log.is_symlink())
            self.assertEqual(outside.read_text(), "preserve external target")
            (root / "etc/shadow").write_text(shadow.replace("root:!*:", "root::"))
            with self.assertRaisesRegex(ValueError, "locked seed account"):
                builder.canonical_seed_content(root, epoch)

    def test_inode_publication_rejects_unsupported_extended_timestamp(self):
        for epoch in (-1, 0x80000000):
            with self.assertRaisesRegex(ValueError, "unsupported seed epoch"):
                builder.inode_publication_commands({".": [0, 0]}, epoch)

    def test_ownership_paths_and_debugfs_commands_reject_injection(self):
        self.assertEqual(builder.normalized_member("./lib/aarch64-linux-gnu/libc.so.6"), "usr/lib/aarch64-linux-gnu/libc.so.6")
        for name in ("../escape", "usr/../../escape", "etc/line\ncommand", 'etc/"command'):
            with self.assertRaises(ValueError):
                builder.normalized_member(name)
        with self.assertRaises(ValueError):
            builder.debugfs_quote('/etc/x"\nrm /data')

    def test_guest_modes_are_correct_under_private_host_umask(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            previous = os.umask(0o077)
            try:
                for name in ("dev", "proc", "sys", "run", "tmp", "data", "etc/apt"):
                    (root / name).mkdir(parents=True)
                for name in ("etc/hostname", "etc/hosts", "etc/machine-id", "etc/apt/sources.list", "etc/fstab"):
                    (root / name).write_text("public\n")
                builder.canonical_guest_modes(root)
            finally:
                os.umask(previous)
            self.assertEqual((root / "tmp").stat().st_mode & 0o7777, 0o1777)
            for name in ("dev", "proc", "sys", "run", "data"):
                self.assertEqual((root / name).stat().st_mode & 0o7777, 0o755)
            self.assertEqual((root / "etc/hosts").stat().st_mode & 0o7777, 0o644)

    def test_guest_absolute_symlinks_stay_inside_prepared_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "usr/lib").mkdir(parents=True)
            (root / "lib").symlink_to("/usr/lib")
            (root / "usr/lib/target").write_text("guest-only")
            self.assertEqual(builder.rooted_path(root, "/lib/target").read_text(), "guest-only")
            (root / "loop").symlink_to("/loop")
            with self.assertRaises(ValueError):
                builder.rooted_path(root, "/loop")

    def test_real_elf_layout_interpreter_needed_and_origin_search(self):
        def elf(needed=False, interpreter=False, machine=183):
            b = bytearray(1024)
            b[:6] = b"\x7fELF\x02\x01"
            struct.pack_into("<H", b, 18, machine)
            struct.pack_into("<Q", b, 32, 64)
            struct.pack_into("<HH", b, 54, 56, 3)
            struct.pack_into("<IIQQQQQQ", b, 64, 1, 0, 0, 0, 0, len(b), len(b), 4096)
            struct.pack_into("<IIQQQQQQ", b, 120, 2, 0, 256, 256, 0, 64, 64, 8)
            tags = [(5, 512), (1, 0), (29, 12), (0, 0)] if needed else [(5, 512), (0, 0)]
            for i, pair in enumerate(tags):
                struct.pack_into("<qQ", b, 256 + i * 16, *pair)
            strings = b"libfoo.so.1\x00$ORIGIN/lib\x00"
            b[512:512 + len(strings)] = strings
            if interpreter:
                text = b"/lib/ld-linux-aarch64.so.1\x00"
                b[600:600 + len(text)] = text
                struct.pack_into("<IIQQQQQQ", b, 176, 3, 0, 600, 600, 0, len(text), len(text), 1)
            return b
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "bin/lib").mkdir(parents=True)
            (root / "lib").mkdir()
            app = root / "bin/app"
            app.write_bytes(elf(needed=True, interpreter=True))
            with self.assertRaisesRegex(ValueError, "interpreter"):
                builder.check_elf_closure(root)
            (root / "lib/ld-linux-aarch64.so.1").write_bytes(elf())
            with self.assertRaisesRegex(ValueError, "DT_NEEDED"):
                builder.check_elf_closure(root)
            (root / "bin/lib/libfoo.so.1").write_bytes(elf())
            report = builder.check_elf_closure(root)
            self.assertEqual(report["dt_needed_edges"], 1)
            app.write_bytes(elf(machine=62))
            with self.assertRaisesRegex(ValueError, "non-ARM64"):
                builder.check_elf_closure(root)

    @unittest.skipUnless(platform.system() == "Linux" and platform.machine() == "x86_64" and shutil.which("cc"), "x86_64 Linux host compatibility helper")
    def test_child_syscall_restrictions_preserve_parent_and_ordinary_io(self):
        libc = ctypes.CDLL(None)
        parent_privs = libc.prctl(39, 0, 0, 0, 0)  # PR_GET_NO_NEW_PRIVS
        with tempfile.TemporaryDirectory() as temporary:
            binary = Path(temporary) / "compat"
            subprocess.run(["cc", "-Wall", "-Wextra", "-Werror", str(EXPERIMENT / "tools/debian_proot_compat.c"), "-o", str(binary)], check=True, capture_output=True)
            program = """import ctypes, errno, os, tempfile
c=ctypes.CDLL(None, use_errno=True)
assert c.prctl(39,0,0,0,0)==1
for number in (332,439):
 ctypes.set_errno(0)
 assert c.syscall(number,-1,0,0,0,0)==-1 and ctypes.get_errno()==errno.ENOSYS
for number in (92,93,94,260):
 ctypes.set_errno(0)
 assert c.syscall(number,-1,0,0,0,0)==-1 and ctypes.get_errno()==errno.EPERM
with tempfile.TemporaryFile() as f:
 f.write(b'ordinary io'); f.seek(0); assert f.read()==b'ordinary io'
assert os.getpid()>0
print('child-deny-only-pass')
"""
            r = subprocess.run([str(binary), sys.executable, "-c", program], text=True, capture_output=True, check=True)
            self.assertEqual(r.stdout.strip(), "child-deny-only-pass")
        self.assertEqual(libc.prctl(39, 0, 0, 0, 0), parent_privs)


if __name__ == "__main__":
    unittest.main()
