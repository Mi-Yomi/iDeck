"""Offline hashing/staging regressions with hashlib.file_digest unavailable."""
import contextlib
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

EXPERIMENT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXPERIMENT / "tools"))
sys.path.insert(0, str(EXPERIMENT / "ipa"))
sys.path.insert(0, str(EXPERIMENT.parents[1] / "ci"))
import debian_bundle as bundle
import build_linux_probe_ipa as builder
import package_probe
import stage_husk
import steam_bundle

MIB = 1024 * 1024
CASES = (b"", b"abc", bytes(range(256)) * (2 * MIB // 256) + b"tail")


def expected(data):
    # Independent in-memory oracle for small synthetic fixtures only.
    return {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}


@contextlib.contextmanager
def without_file_digest():
    original = getattr(hashlib, "file_digest", None)
    if original is not None:
        del hashlib.file_digest
    try:
        yield
    finally:
        if original is not None:
            hashlib.file_digest = original


@contextlib.contextmanager
def bounded_reads(test):
    """Use real files, rejecting unbounded reads and recording every request."""
    original = Path.open
    reads = []

    class Reader:
        def __init__(self, stream):
            self.stream = stream

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return self.stream.__exit__(*args)

        def read(self, size=-1):
            test.assertEqual(size, MIB)
            reads.append(size)
            return self.stream.read(size)

    def guarded_open(path, mode="r", *args, **kwargs):
        stream = original(path, mode, *args, **kwargs)
        return Reader(stream) if mode == "rb" else stream

    with patch.object(Path, "open", guarded_open):
        yield reads
    test.assertTrue(reads, "must exercise real bounded reads")


class StreamingHashChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        missing_api = without_file_digest()
        missing_api.__enter__()
        self.addCleanup(missing_api.__exit__, None, None, None)

    def test_metadata_empty_small_and_multiblock_bounded(self):
        path = self.root / "data"
        for data in CASES:
            with self.subTest(size=len(data)):
                path.write_bytes(data)
                with bounded_reads(self) as reads:
                    self.assertEqual(bundle.metadata(path), expected(data))
                self.assertEqual(len(reads), (len(data) + MIB - 1) // MIB + 1)

    def test_ci_sha_empty_small_and_multiblock_bounded(self):
        path = self.root / "data"
        for data in CASES:
            with self.subTest(size=len(data)):
                path.write_bytes(data)
                with bounded_reads(self) as reads:
                    self.assertEqual(builder.sha(path), expected(data)["sha256"])
                self.assertEqual(len(reads), (len(data) + MIB - 1) // MIB + 1)

    def test_steam_metadata_empty_small_and_multiblock_bounded(self):
        path = self.root / "data"
        for data in CASES:
            with self.subTest(size=len(data)):
                path.write_bytes(data)
                with bounded_reads(self) as reads:
                    self.assertEqual(steam_bundle.metadata(path), expected(data))
                self.assertEqual(len(reads), (len(data) + MIB - 1) // MIB + 1)

    def test_standalone_steam_overlay_stage_repeat_and_corruption_without_api(self):
        mapping = stage_husk.load_overlay()["copies"]
        self.assertEqual(mapping["tools/steam_bundle.py"], "scripts/ideck-stage-steam.py")
        script = self.root / mapping["tools/steam_bundle.py"]
        script.parent.mkdir()
        shutil.copyfile(EXPERIMENT / "tools/steam_bundle.py", script)
        lock = json.loads((EXPERIMENT / "ipa/steam.lock.json").read_text())
        source = self.root / "guests/ideck-steam"
        source.mkdir(parents=True)
        builder.restore_guest(self.root / "probe")
        shutil.copyfile(self.root / "probe/vmlinuz-virt", source / "vmlinuz-virt")
        # Synthetic initramfs/rootfs bytes exercise staging, not guest boot.
        for name, data in (("initramfs-steam.gz", CASES[2]),
                           ("steam-rootfs-v1.raw.gz", b"root fixture"),
                           ("LICENSES-steam.txt", b"notice fixture")):
            (source / name).write_bytes(data)
            lock["files"][name] = expected(data)
        profile = {"schema": 1, "mode": "steam-experimental", "control_port": "org.ideck.control",
                   "image": {"size_bytes": steam_bundle.SIZE, "uuid": steam_bundle.UUID,
                             "block_size": 4096, "features": {"compat": 44, "incompat": 194, "ro_compat": 1091}},
                   "seed_sha256": lock["seed_sha256"]}
        for key, name in (("kernel", "vmlinuz-virt"), ("initramfs", "initramfs-steam.gz"),
                          ("rootfs", "steam-rootfs-v1.raw.gz")):
            profile[key] = {"file": name, **lock["files"][name]}
        data = json.dumps(profile).encode()
        (source / "steam-profile.json").write_bytes(data)
        lock["files"]["steam-profile.json"] = expected(data)
        lockpath = self.root / mapping["ipa/steam.lock.json"]
        lockpath.write_text(json.dumps(lock))
        destination = self.root / "Husk.app/iDeckLinuxSteam"
        wrapper = ("import hashlib, runpy, sys; hashlib.__dict__.pop('file_digest', None); "
                   "assert not hasattr(hashlib, 'file_digest'); sys.argv = sys.argv[1:]; "
                   "runpy.run_path(sys.argv[0], run_name='__main__')")
        for command, path in (("verify", source), ("stage", source),
                              ("stage", source), ("verify", destination)):
            args = [command, str(path), str(lockpath)]
            if command == "stage":
                args += ["--destination", str(destination)]
            result = subprocess.run([sys.executable, "-I", "-B", "-c", wrapper, str(script), *args],
                                    cwd=self.root, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout), lock["files"])
        (source / "initramfs-steam.gz").write_bytes(b"X" * len(CASES[2]))
        result = subprocess.run([sys.executable, "-I", "-B", "-c", wrapper, str(script),
                                 "stage", str(source), str(lockpath), "--destination", str(destination)],
                                cwd=self.root, capture_output=True, text=True, timeout=30)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Steam asset integrity mismatch", result.stderr)
        self.assertEqual((destination / "initramfs-steam.gz").read_bytes(), CASES[2])

    def test_large_ipa_hash_empty_small_and_multiblock_bounded(self):
        path = self.root / "fixture.ipa"
        for data in CASES:
            path.write_bytes(data)
            with bounded_reads(self):
                self.assertEqual(package_probe.sha256_file(path), expected(data)["sha256"])

    def test_terminal_package_gate_empty_small_and_multiblock_bounded(self):
        names = ("terminal-profile.json", "initramfs-terminal.gz",
                 "userdata-seed.raw", "LICENSES-terminal.txt")
        directory = self.root / "App.app/iDeckLinuxTerminal"
        directory.mkdir(parents=True)
        files = dict(zip(names, (*CASES, b"notice")))
        for name, data in files.items():
            (directory / name).write_bytes(data)
        (self.root / "terminal.lock.json").write_text(json.dumps(
            {"files": {name: expected(data) for name, data in files.items()}}))
        with patch.object(package_probe, "__file__", str(self.root / "package_probe.py")):
            with bounded_reads(self):
                package_probe.check_terminal_assets(directory.parent)
            asset = directory / "userdata-seed.raw"
            for data in (b"X" * len(files[asset.name]), files[asset.name] + b"extra"):
                asset.write_bytes(data)
                with self.assertRaises(ValueError):
                    package_probe.check_terminal_assets(directory.parent)


class DebianStagingWithoutFileDigest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        missing_api = without_file_digest()
        missing_api.__enter__()
        self.addCleanup(missing_api.__exit__, None, None, None)
        self.source = self.root / "source"
        self.source.mkdir()
        self.files = {name: (name + " fixture\n").encode() for name in bundle.NAMES}
        self.files.update({"LICENSES-debian.txt": CASES[0],
                           "debian-profile.json": CASES[1], "rootfs-v1.raw": CASES[2]})
        for name, data in self.files.items():
            (self.source / name).write_bytes(data)
        self.lock = {"schema": 1, "files": {name: expected(data) for name, data in self.files.items()}}
        self.lockpath = self.root / "lock.json"
        self.lockpath.write_text(json.dumps(self.lock))
        self.destination = self.root / "App.app/iDeckDebian"

    def test_verify_stage_and_repeat_are_exact_bounded_and_synced(self):
        with bounded_reads(self), patch.object(bundle.os, "fsync", wraps=os.fsync) as sync:
            self.assertEqual(bundle.verify(self.source, self.lock), self.lock["files"])
            for _ in range(2):
                self.assertEqual(bundle.stage(self.source, self.destination, self.lockpath), self.lock["files"])
                self.assertEqual(bundle.verify(self.destination, self.lock), self.lock["files"])
            self.assertEqual(sync.call_count, 2 * len(bundle.NAMES))
        self.assertEqual({p.name: p.read_bytes() for p in self.destination.iterdir()}, self.files)

    def test_stage_independently_rejects_corrupted_written_file(self):
        for same_size in (False, True):
            with self.subTest(same_size=same_size):
                destination = self.root / str(same_size) / "iDeckDebian"

                def corrupt(origin, target, length):
                    self.assertEqual(length, MIB)
                    if same_size:
                        while chunk := origin.read(length):
                            target.write(b"X" * len(chunk))
                    else:
                        target.write(b"corrupt")

                with patch.object(bundle.shutil, "copyfileobj", side_effect=corrupt):
                    with self.assertRaisesRegex(ValueError, "integrity"):
                        bundle.stage(self.source, destination, self.lockpath)
                # An empty file may have been published before the same-size fault.
                self.assertEqual({p.name: p.read_bytes() for p in destination.iterdir()},
                                 {"LICENSES-debian.txt": b""} if same_size else {})

    def test_fsync_failure_prevents_publication(self):
        with patch.object(bundle.os, "fsync", side_effect=OSError("synthetic fsync failure")):
            with self.assertRaises(OSError):
                bundle.stage(self.source, self.destination, self.lockpath)
        self.assertEqual(list(self.destination.iterdir()), [])

    def test_verify_and_stage_reject_hash_size_missing_extra_and_symlink(self):
        asset = self.source / "rootfs-v1.raw"
        original = self.files[asset.name]
        for data in (b"X" * len(original), original + b"extra"):
            with self.subTest(size=len(data)):
                asset.write_bytes(data)
                self.assert_invalid_source()
        asset.unlink()
        self.assert_invalid_source()
        asset.symlink_to(self.source / "vmlinuz-virt")
        self.assert_invalid_source()
        asset.unlink()
        asset.write_bytes(original)
        (self.source / "extra").write_bytes(b"extra")
        self.assert_invalid_source()

    def assert_invalid_source(self):
        with self.assertRaises(ValueError):
            bundle.verify(self.source, self.lock)
        with self.assertRaises(ValueError):
            bundle.stage(self.source, self.destination, self.lockpath)
        self.assertFalse(self.destination.exists())

    def test_unsafe_destination_and_ancestors_rejected_without_writes(self):
        external = self.root / "external"
        external.mkdir()
        alias = self.root / "alias"
        alias.symlink_to(external, target_is_directory=True)
        for destination in (self.source, self.source / "child", alias, alias / "child"):
            with self.subTest(destination=destination):
                with self.assertRaises(ValueError):
                    bundle.stage(self.source, destination, self.lockpath)
        self.assertEqual(list(external.iterdir()), [])
        self.assertEqual({p.name: p.read_bytes() for p in self.source.iterdir()}, self.files)

    def test_extra_and_symlink_destination_contents_rejected(self):
        self.destination.mkdir(parents=True)
        extra = self.destination / "extra"
        extra.write_bytes(b"keep")
        with self.assertRaises(ValueError):
            bundle.stage(self.source, self.destination, self.lockpath)
        self.assertEqual(extra.read_bytes(), b"keep")
        extra.unlink()
        alias = self.destination / "rootfs-v1.raw"
        alias.symlink_to(self.source / alias.name)
        with self.assertRaises(ValueError):
            bundle.stage(self.source, self.destination, self.lockpath)
        self.assertTrue(alias.is_symlink())
        self.assertEqual(list(self.destination.iterdir()), [alias])

    def test_standalone_overlay_cli_verify_stage_and_repeat_without_api(self):
        # Same byte-for-byte copy mapping and CLI arguments as the Xcode phase.
        overlay = stage_husk.load_overlay()
        relative = overlay["copies"]["tools/debian_bundle.py"]
        self.assertEqual(relative, "scripts/ideck-stage-debian.py")
        isolated = self.root / "standalone"
        script = isolated / relative
        script.parent.mkdir(parents=True)
        shutil.copyfile(EXPERIMENT / "tools/debian_bundle.py", script)
        self.assertEqual(script.read_bytes(), (EXPERIMENT / "tools/debian_bundle.py").read_bytes())
        lockpath = script.parent / "ideck-debian.lock.json"
        lockpath.write_text(json.dumps(self.lock))
        source = isolated / "guests/ideck-debian"
        shutil.copytree(self.source, source)
        self.assertEqual({p.name for p in script.parent.iterdir()}, {script.name, lockpath.name})
        wrapper = ("import hashlib, runpy, sys; "
                   "hashlib.__dict__.pop('file_digest', None); "
                   "assert not hasattr(hashlib, 'file_digest'); "
                   "sys.argv = sys.argv[1:]; runpy.run_path(sys.argv[0], run_name='__main__')")
        interpreters = [sys.executable]
        python39 = shutil.which("python3.9")
        if python39 and python39 != sys.executable:
            interpreters.append(python39)
        for index, interpreter in enumerate(interpreters):
            destination = isolated / f"build-{index}/Husk.app/iDeckDebian"
            for command, path in (("verify", source), ("stage", source),
                                  ("stage", source), ("verify", destination)):
                args = [command, str(path), str(lockpath)]
                if command == "stage":
                    args += ["--destination", str(destination)]
                result = subprocess.run([interpreter, "-I", "-B", "-c", wrapper, str(script), *args],
                                        cwd=isolated, text=True, capture_output=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout), self.lock["files"])
            self.assertEqual({p.name: p.read_bytes() for p in destination.iterdir()}, self.files)


if __name__ == "__main__":
    unittest.main()
