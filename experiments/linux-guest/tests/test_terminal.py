"""Exercise real terminal bundle bytes and integration guards, never emulate Linux.

FAT/CPIO inspections below are build validation. The real two-boot acceptance
requires QEMU (absent locally) or an authorized device test.
"""
import hashlib
import gzip
import ast
import json
import struct
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

EXPERIMENT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXPERIMENT / "tools"))
sys.path.insert(0, str(EXPERIMENT / "ipa"))
import terminal_bundle
import package_probe

LOCK = EXPERIMENT / "ipa/terminal.lock.json"


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def cpio_entries(data):
    """Independent reader of newc records, including concatenated trailers."""
    entries = {}
    position = 0
    while position < len(data):
        if data[position:position + 6] not in (b"070701", b"070702"):
            if data[position] != 0:
                raise AssertionError("unexpected non-newc data")
            position += 1
            continue
        header = data[position:position + 110]
        size = int(header[54:62], 16)
        name_size = int(header[94:102], 16)
        name = data[position + 110:position + 110 + name_size - 1].decode()
        start = (position + 110 + name_size + 3) & ~3
        end = start + size
        if end > len(data):
            raise AssertionError("truncated newc record")
        entries[name] = (int(header[14:22], 16), data[start:end])
        position = (end + 3) & ~3
    return entries


def swift_block(source, declaration):
    start = source.index("{", source.index(declaration))
    depth, end = 1, start + 1
    while depth:
        if source[end] == "{":
            depth += 1
        elif source[end] == "}":
            depth -= 1
        end += 1
    return source[start + 1:end - 1]


class TerminalBundleChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary.name)
        cls.probe = cls.root / "probe"
        cls.probe.mkdir()
        probe_lock = json.loads((EXPERIMENT / "ipa/guest.lock.json").read_text())
        with tarfile.open(EXPERIMENT / probe_lock["archive"]) as archive:
            for name in probe_lock["files"]:
                (cls.probe / name).write_bytes(archive.extractfile(name).read())
        cls.source = cls.root / "terminal"
        terminal_bundle.prepare(cls.probe, cls.source)
        cls.lock = json.loads(LOCK.read_text())

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_actual_seed_has_consistent_fat16_geometry_and_two_identical_fats(self):
        seed = self.source / "userdata-seed.raw"
        self.assertEqual(seed.stat().st_size, 128 * 1024 * 1024)
        with seed.open("rb") as stream:
            boot = stream.read(512)
            self.assertEqual(boot[510:], b"\x55\xaa")
            self.assertEqual(boot[54:62], b"FAT16   ")
            sector = struct.unpack_from("<H", boot, 11)[0]
            cluster = boot[13]
            reserved = struct.unpack_from("<H", boot, 14)[0]
            fats = boot[16]
            roots = struct.unpack_from("<H", boot, 17)[0]
            total = struct.unpack_from("<I", boot, 32)[0]
            fat_sectors = struct.unpack_from("<H", boot, 22)[0]
            self.assertEqual((sector, cluster, reserved, fats, roots, total, fat_sectors),
                             (512, 8, 1, 2, 512, 262144, 128))
            root_sectors = (roots * 32 + sector - 1) // sector
            clusters = (total - reserved - fats * fat_sectors - root_sectors) // cluster
            self.assertTrue(4085 <= clusters < 65525)
            self.assertGreaterEqual(fat_sectors * sector // 2, clusters + 2)
            stream.seek(reserved * sector)
            first = stream.read(fat_sectors * sector)
            self.assertEqual(stream.read(fat_sectors * sector), first)
            self.assertEqual(struct.unpack_from("<HH", first), (0xFFF8, 0xFFFF))
            self.assertEqual(first[4:], bytes(len(first) - 4))
        self.assertEqual(sha(seed), self.lock["files"][seed.name]["sha256"])

    def test_real_prepare_is_deterministic_and_locked(self):
        other = self.root / "terminal-again"
        terminal_bundle.prepare(self.probe, other)
        self.assertEqual({p.name for p in other.iterdir()}, set(self.lock["files"]))
        for name, expected in self.lock["files"].items():
            self.assertEqual(other.joinpath(name).stat().st_size, expected["size"])
            self.assertEqual(sha(other / name), expected["sha256"])
            self.assertEqual(sha(other / name), sha(self.source / name))

    def test_terminal_cpio_preserves_original_guest_and_real_driver_closure(self):
        original = (self.probe / "initramfs-ideck.gz").read_bytes()
        terminal = (self.source / "initramfs-terminal.gz").read_bytes()
        self.assertTrue(terminal.startswith(original))
        suffix = cpio_entries(gzip.decompress(terminal[len(original):]))
        self.assertEqual(set(suffix), {"ideck-terminal-init", "ideck-terminal-login", "TRAILER!!!"})
        for name in ("ideck-terminal-init", "ideck-terminal-login"):
            mode, data = suffix[name]
            self.assertEqual(mode, 0o100755)
            self.assertEqual(data, (EXPERIMENT / "guest" / name).read_bytes())
        entries = cpio_entries(gzip.decompress(terminal))
        prefix = "usr/lib/modules/6.18.35-0-virt/"
        for name in ("kernel/drivers/block/virtio_blk.ko", "kernel/fs/fat/fat.ko", "kernel/fs/fat/vfat.ko",
                     "kernel/fs/nls/nls_cp437.ko", "kernel/fs/nls/nls_iso8859-1.ko"):
            self.assertIn(prefix + name, entries)
            self.assertTrue(entries[prefix + name][1].startswith(b"\x7fELF\x02\x01"))
        self.assertIn(b"kernel/drivers/char/virtio_console.ko\n", entries[prefix + "modules.builtin"][1])
        self.assertEqual((self.probe / "vmlinuz-virt").stat().st_size,
                         json.loads((self.source / "terminal-profile.json").read_text())["kernel"]["size"])

    def test_prepare_rejects_corrupt_probe_before_creating_output(self):
        path = self.probe / "vmlinuz-virt"
        original = path.read_bytes()
        destination = self.root / "bad-probe-output"
        try:
            path.write_bytes(b"corrupt")
            with self.assertRaises(ValueError):
                terminal_bundle.prepare(self.probe, destination)
            self.assertFalse(destination.exists())
        finally:
            path.write_bytes(original)

    def test_prepare_rejects_changed_script_and_symlink(self):
        scripts = self.root / "scripts"
        scripts.mkdir()
        for name in self.lock["inputs"]["scripts"]:
            (scripts / name).write_bytes((EXPERIMENT / "guest" / name).read_bytes())
        changed = scripts / "ideck-terminal-init"
        original = changed.read_bytes()
        changed.write_bytes(original + b"\necho unreviewed\n")
        destination = self.root / "bad-script-output"
        with self.assertRaises(ValueError):
            terminal_bundle.prepare(self.probe, destination, scripts=scripts)
        self.assertFalse(destination.exists())
        changed.unlink()
        changed.symlink_to(EXPERIMENT / "guest/ideck-terminal-init")
        with self.assertRaises(ValueError):
            terminal_bundle.prepare(self.probe, destination, scripts=scripts)
        self.assertFalse(destination.exists())

    def test_stage_is_idempotent_exact_and_excludes_unrelated_files(self):
        out = self.root / "staged"
        private = self.source / "unrelated-private-file"
        private.write_text("not a guest asset")
        try:
            terminal_bundle.stage(self.source, out, LOCK)
            before = {p.name: sha(p) for p in out.iterdir()}
            terminal_bundle.stage(self.source, out, LOCK)
            self.assertEqual(before, {p.name: sha(p) for p in out.iterdir()})
            self.assertEqual(set(before), set(self.lock["files"]))
            self.assertNotIn(private.name, before)
        finally:
            private.unlink()

    def test_real_ipa_resource_gate_requires_exact_complete_uncorrupted_bundle(self):
        app = self.root / "ResourceGate.app"
        resources = app / "iDeckLinuxTerminal"
        terminal_bundle.stage(self.source, resources, LOCK)
        package_probe.check_terminal_assets(app)
        asset = resources / "LICENSES-terminal.txt"
        original = asset.read_bytes()
        missing = self.root / "temporarily-missing-license"
        asset.rename(missing)
        try:
            with self.assertRaises(ValueError):
                package_probe.check_terminal_assets(app)
        finally:
            missing.rename(asset)
        asset.write_bytes(bytes([original[0] ^ 1]) + original[1:])
        try:
            with self.assertRaises(ValueError):
                package_probe.check_terminal_assets(app)
        finally:
            asset.write_bytes(original)
        extra = resources / "unreviewed-extra"
        extra.write_bytes(b"excluded")
        try:
            with self.assertRaises(ValueError):
                package_probe.check_terminal_assets(app)
        finally:
            extra.unlink()
        asset.rename(missing)
        asset.symlink_to(missing)
        try:
            with self.assertRaises(ValueError):
                package_probe.check_terminal_assets(app)
        finally:
            asset.unlink()
            missing.rename(asset)
        package_probe.check_terminal_assets(app)

    def test_corrupt_seed_and_symlink_rejected_without_destination_changes(self):
        seed = self.source / "userdata-seed.raw"
        saved = self.source / "saved-seed.raw"
        out = self.root / "rejected-stage"
        out.mkdir()
        sentinel = out / "keep"
        sentinel.write_bytes(b"existing destination")
        with seed.open("r+b") as stream:
            stream.seek(510)
            original = stream.read(2)
            stream.seek(510)
            stream.write(b"xx")
        try:
            with self.assertRaises(ValueError):
                terminal_bundle.stage(self.source, out, LOCK)
            self.assertEqual(list(out.iterdir()), [sentinel])
        finally:
            with seed.open("r+b") as stream:
                stream.seek(510)
                stream.write(original)
        seed.rename(saved)
        seed.symlink_to(saved)
        try:
            with self.assertRaises(ValueError):
                terminal_bundle.stage(self.source, out, LOCK)
            self.assertEqual(sentinel.read_bytes(), b"existing destination")
        finally:
            seed.unlink()
            saved.rename(seed)

    def test_unsafe_lock_output_paths_and_destination_symlinks_fail_closed(self):
        bad_lock = json.loads(LOCK.read_text())
        bad_lock["files"]["../escape"] = bad_lock["files"].pop("userdata-seed.raw")
        path = self.root / "unsafe.lock.json"
        path.write_text(json.dumps(bad_lock))
        output = self.root / "unsafe-lock-output"
        with self.assertRaises(ValueError):
            terminal_bundle.stage(self.source, output, path)
        self.assertFalse(output.exists())
        outside = self.root / "outside"
        outside.mkdir()
        link = self.root / "destination-link"
        link.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError):
            terminal_bundle.stage(self.source, link, LOCK)
        self.assertEqual(list(outside.iterdir()), [])
        with self.assertRaises(ValueError):
            terminal_bundle.stage(self.source, self.source / "nested", LOCK)
        self.assertFalse((self.source / "nested").exists())

    def test_guest_stop_uses_separate_control_and_unmounts_before_clean_ack(self):
        script = (EXPERIMENT / "guest/ideck-terminal-init").read_text()
        login = (EXPERIMENT / "guest/ideck-terminal-login").read_text()
        shutdown = script[script.index("shutdown() {"):script.index("trap shutdown")]
        self.assertLess(shutdown.index("kill -KILL -1"), shutdown.index("umount /data"))
        self.assertLess(shutdown.index("umount /data || fail unmount"),
                        shutdown.index("echo IDECK_TERMINAL_CLEAN_UNMOUNT >&3"))
        self.assertLess(shutdown.index("sync || fail sync_after_unmount"),
                        shutdown.index("echo IDECK_TERMINAL_CLEAN_UNMOUNT >&3"))
        self.assertLess(shutdown.index("echo IDECK_TERMINAL_CLEAN_UNMOUNT >&3"), shutdown.index("poweroff -f"))
        self.assertIn("trap shutdown USR2 TERM INT", script)
        self.assertIn("while IFS= read -r command <&3", script)
        self.assertIn('[ "$command" = IDECK_STOP_V1 ]', script)
        self.assertIn("kill -USR2 1", script)
        self.assertIn("org.ideck.control", script)
        self.assertNotIn("eval ", script)
        self.assertNotIn("mkfs", script)
        self.assertNotIn("mke2fs", script)
        self.assertIn("mount -t vfat", script)
        self.assertIn("cd /data || exit 1", login)
        self.assertIn("exec /usr/bin/busybox sh -i", login)
        getty = next(line for line in script.splitlines() if line.startswith("$BB getty "))
        self.assertTrue(getty.endswith("3>&- &"), "ordinary ash must not inherit the supervisor control fd")
        self.assertNotIn("/ideck-init", script)


class TerminalSourceContracts(unittest.TestCase):
    """Source-level safety contracts, explicitly not Swift/runtime execution."""
    def test_asset_containment_uses_posix_paths_and_apple_regressions_are_wired(self):
        guest = (EXPERIMENT / "ios/LinuxGuestProfile.swift").read_text()
        terminal = (EXPERIMENT / "ios/LinuxTerminalProfile.swift").read_text()
        canonical = swift_block(guest, "static func canonical(")
        self.assertIn("realpath(", canonical)
        self.assertIn("free(resolved)", canonical)
        self.assertIn("url.isFileURL", canonical)
        for source, function, leaf in ((guest, "private func checkedAsset(", "candidate"),
                                       (terminal, "private func checked(", "file")):
            checked = swift_block(source, function)
            self.assertIn("LinuxGuestAssetPath.directory(", checked)
            self.assertIn(f"LinuxGuestAssetPath.canonical({leaf}) == {leaf}.path", checked)
            for forbidden in ("standardizedFileURL", "resolvingSymlinksInPath", "== root"):
                self.assertNotIn(forbidden, checked)
            for guard in ("asset.file == name", "isRegularFile == true", "isSymbolicLink != true",
                          "values.fileSize == asset.size", "asset.sha256", "assetDigest",
                          "assetType", "assetSize", "assetContainment", "assetContentSize"):
                self.assertIn(guard, checked)
        checks = (EXPERIMENT / "ios/tests/TerminalChecks.swift").read_text()
        for required in ('for hint in [false, true]', '"apple-alias"',
                         'rawVar.appendingPathComponent("tmp")', 'isDirectory: hint',
                         'expectTerminalFailure(.assetDigest)', 'expectProbeFailure(.assetDigest)',
                         'expectTerminalFailure(.assetType)', 'expectProbeFailure(.assetType)',
                         'expectTerminalFailure(.assetDescriptor)', '!manager.fileExists(atPath: rejectedSession.path)',
                         'sourceSeedDescription["sha256"]', 'bundledSeedDescription["sha256"]'):
            self.assertIn(required, checks)

    def test_trusted_system_prefix_uses_posix_realpath_before_untrusted_leaf_checks(self):
        # Darwin rewrites system aliases in Foundation URL normalization. The
        # real Swift host cases exercise /var and /private; these are wiring
        # and safety guards, not a Python reproduction of Darwin/Foundation.
        profile = (EXPERIMENT / "ios/LinuxTerminalProfile.swift").read_text()
        trusted = swift_block(profile, "static func trustedDirectory(")
        validate = swift_block(profile, "static func validateDirectory(")
        self.assertIn("realpath(", trusted)
        for operation in ("standardizedFileURL", "resolvingSymlinksInPath"):
            self.assertNotIn(operation, validate)
        self.assertIn('"."', validate)
        self.assertIn('".."', validate)
        self.assertIn("lstat(", validate)
        self.assertIn("S_IFDIR", validate)
        session = (EXPERIMENT / "ios/LinuxTerminalSession.swift").read_text()
        self.assertLess(session.index("LinuxTerminalDisk.trustedDirectory("),
                        session.index('appendingPathComponent("iDeckLinux"'))
        checks = (EXPERIMENT / "ios/tests/TerminalChecks.swift").read_text()
        self.assertLess(checks.index("LinuxTerminalDisk.trustedDirectory(manager.temporaryDirectory)"),
                        checks.index('appendingPathComponent("ideck-terminal-checks-'))
        self.assertIn('URL(fileURLWithPath: "/var", isDirectory: true)', checks)
        self.assertIn("LinuxTerminalDisk.trustedDirectory(rawVar)", checks)
        self.assertIn("LinuxTerminalDisk.validateDirectory(trustedVar, allowingMissing: false)", checks)
        self.assertIn('"/%2E/child"', checks)
        self.assertIn('"/%2E%2E/child"', checks)
        self.assertIn("catch LinuxTerminalProfile.Invalid.diskDirectoryComponent", checks)
        self.assertIn("catch LinuxTerminalProfile.Invalid.diskDirectoryType", checks)
        self.assertIn('linkedDirectory.appendingPathComponent("child")', checks)
        self.assertIn('linkedDirectory.absoluteString + "/%2E%2E/hidden-data"', checks)
        self.assertLess(checks.index("LinuxTerminalDisk.validateDirectory(rejected, allowingMissing: true)"),
                        checks.index("LinuxTerminalDisk.open(directory: rejected, seed: appended)"))
        # Static enum cases and checkpoint labels expose the failed guard, not
        # the owner's directory names. No surrogate path-validator runs here.
        errors = swift_block(profile, "enum Invalid: Error")
        self.assertIn("diskDirectoryComponent", errors)
        self.assertIn("diskSeedSize", errors)
        self.assertNotIn("String", errors)
        checkpoint = swift_block(checks, "func checkpoint(")
        self.assertNotIn(".path", checkpoint)
        self.assertNotIn(".absoluteString", checkpoint)

    def test_actual_swift_seed_fixture_rewinds_after_truncate_before_writing_header(self):
        # Guards the exact regression that reached Apple's mac-tests: FileHandle
        # truncate moves its cursor. This inspects the real Swift fixture, and
        # does not claim to execute FileHandle or reproduce it in Python.
        checks = (EXPERIMENT / "ios/tests/TerminalChecks.swift").read_text()
        fixture = swift_block(checks, "func makeSeed(")
        truncate = fixture.index("file.truncate(atOffset:")
        rewind = fixture.index("file.seek(toOffset: 0)")
        write = fixture.index("file.write(contentsOf: boot)")
        self.assertLess(truncate, rewind)
        self.assertLess(rewind, write)
        self.assertGreater(fixture.rindex("fileSize(url) == LinuxTerminalProfile.diskSize"), write)
        self.assertIn("reader.read(upToCount: 512) == boot", fixture)
        self.assertIn("catch LinuxTerminalProfile.Invalid.diskSeedSize", checks)
        self.assertLess(checks.index("try makeSeed(seed)"), checks.index('checkpoint("disk-first-open")'))

    def test_clean_claim_requires_independent_unmount_loop_return_and_host_fsync(self):
        session = (EXPERIMENT / "ios/LinuxTerminalSession.swift").read_text()
        serial = swift_block(session, "private func receiveSerial(")
        control = swift_block(session, "private func receiveControl(")
        finalize = swift_block(session, "private func finalizeIfClean()")
        disconnected = swift_block(session, "private func channelDisconnected(")
        self.assertNotIn("cleanUnmount = true", serial)
        self.assertIn('line == Data("IDECK_TERMINAL_CLEAN_UNMOUNT".utf8)', control)
        self.assertIn("cleanUnmount = true", control)
        self.assertIn("guard cleanUnmount, loopReturned, !finalized, !stopFailed, let disk", finalize)
        self.assertLess(finalize.index("control?.drainAvailable()"),
                        finalize.index("guard !stopFailed, controlLines.isEmpty"))
        self.assertLess(finalize.index("guard !stopFailed, controlLines.isEmpty"), finalize.index("try disk.synchronize()"))
        self.assertLess(finalize.index("try disk.synchronize()"), finalize.index('report["terminal_clean_stop"] = true'))
        self.assertNotIn("synchronizeAndClose", finalize)
        self.assertNotIn("closeUnused", finalize)
        self.assertNotIn("cleanUnmount = true", disconnected)
        self.assertNotIn("loopReturned = true", disconnected)
        self.assertNotIn('report["terminal_clean_stop"] = true', disconnected)
        self.assertIn("guard !finalized", disconnected)
        self.assertNotIn("qemu_cleanup()", session)
        self.assertNotIn('command("quit")', session)
        self.assertIn('Data("IDECK_STOP_V1\\n".utf8)', session)
        self.assertIn("socketpair(AF_UNIX, SOCK_STREAM", session)

    def test_control_failure_and_timeouts_do_not_confirm_clean_or_release_the_disk(self):
        session = (EXPERIMENT / "ios/LinuxTerminalSession.swift").read_text()
        control = swift_block(session, "private func receiveControl(")
        failure = control[control.index('line == Data("IDECK_TERMINAL_STOP_FAILED".utf8)'):]
        self.assertIn("stopFailed = true", failure)
        self.assertIn('report["terminal_clean_stop"] = false', failure)
        self.assertNotIn('report["terminal_clean_stop"] = true', failure)
        for function, status in (("scheduleStartupTimeout", "terminal_startup_timeout"),
                                 ("scheduleStopTimeout", "terminal_stop_timeout")):
            timeout = swift_block(session, "private func " + function + "()")
            self.assertIn('report["status"] = "' + status + '"', timeout)
            self.assertIn("queue.asyncAfter", timeout)
            for forbidden in ('report["terminal_clean_stop"] = true', "cleanUnmount = true", "closeUnused",
                              "synchronizeAndClose", "qemu_cleanup", "Darwin.kill", "exit("):
                self.assertNotIn(forbidden, timeout)
        self.assertIn('"qemu_block_layer_drained_verified": false', session)
        self.assertIn('report["userdata_lock_retained_until_process_exit"] = true', session)

    def test_qemu_duplicate_lock_requires_live_host_disk_owner(self):
        profile = (EXPERIMENT / "ios/LinuxTerminalProfile.swift").read_text()
        arguments = swift_block(profile, "func arguments(")
        self.assertIn("disk: LinuxTerminalDisk", profile)
        self.assertNotIn("diskURL: URL", profile)
        self.assertLess(arguments.index("try disk.validateOwnership()"), arguments.index("original.arguments("))
        self.assertEqual(arguments.count("file.locking=off"), 1)
        self.assertIn("format=raw,cache=writethrough,file.locking=off,file=", arguments)
        ownership = swift_block(profile, "func validateOwnership()")
        for guard in ["fd >= 0", "flock(fd, LOCK_EX | LOCK_NB)", "fstat(fd", "lstat(url.path",
                      "opened.st_dev == named.st_dev", "opened.st_ino == named.st_ino",
                      "opened.st_nlink == 1", "named.st_nlink == 1", "opened.st_size", "S_IFREG"]:
            self.assertIn(guard, ownership)
        for forbidden in ["LOCK_UN", "close(", "unlink(", "provision(", "truncate("]:
            self.assertNotIn(forbidden, ownership)
        session = (EXPERIMENT / "ios/LinuxTerminalSession.swift").read_text()
        entry = swift_block(session, "private func prepareNativeEntry(")
        self.assertLess(entry.index("try disk.validateOwnership()"), entry.index("try diagnostic.record(.qemuInitBegin)"))
        self.assertLess(entry.index("try disk.validateOwnership()"), entry.index("handToQEMU()"))
        probe = (EXPERIMENT / "ios/LinuxGuestProfile.swift").read_text()
        self.assertNotIn("locking=off", probe)
        diagnostics = (EXPERIMENT / "ios/LinuxTerminalDiagnostics.swift").read_text()
        self.assertIn("diskOwnership", diagnostics)

    def test_apple_disk_checks_exercise_conflict_and_independent_processes(self):
        checks = (EXPERIMENT / "ios/tests/TerminalChecks.swift").read_text()
        self.assertIn("F_OFD_SETLK", checks)
        self.assertIn("l_start: 100, l_len: 1", checks)
        self.assertIn("errno == EAGAIN || errno == EACCES", checks)
        self.assertEqual(checks.count("try contenders(directory, seed: seed, locked: true)"), 2)
        self.assertIn("try contenders(directory, seed: seed, locked: false)", checks)
        self.assertIn("replacement inode never reseeded or modified", checks)
        self.assertIn("closed-disk-token-argv", checks)
        main = (EXPERIMENT / "ios/tests/main.swift").read_text()
        self.assertIn("try runTerminalDiskContender(", main)

    def test_console_log_and_ui_publication_are_bounded_without_qemu_logfile(self):
        session = (EXPERIMENT / "ios/LinuxTerminalSession.swift").read_text()
        serial = swift_block(session, "private func receiveSerial(")
        publication = swift_block(session, "private func scheduleTranscriptPublication()")
        profile = (EXPERIMENT / "ios/LinuxTerminalProfile.swift").read_text()
        self.assertIn("2 * 1024 * 1024 - loggedBytes", serial)
        self.assertIn("Data(bytes.prefix(remaining))", serial)
        self.assertIn('report["log_truncated"] = true', serial)
        self.assertIn("256 * 1024", serial)
        self.assertIn("if !transcriptPublishScheduled", publication)
        self.assertIn("self.owner.publish", publication)
        self.assertIn("self.queue.async", publication)
        self.assertNotIn("logfile=", profile)
        self.assertIn("cache=writethrough", profile)

    def test_apple_gate_runs_actual_helpers_and_one_shot_jit_exclusion_is_retained(self):
        script = (EXPERIMENT.parents[1] / "ci/check_linux_guest_profile.py").read_text()
        tree = ast.parse(script)
        calls = {node.args[0].value: node for node in ast.walk(tree)
                 if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "run"
                 and node.args and isinstance(node.args[0], ast.Constant)}
        compile_names = {node.id for node in ast.walk(calls["mac-compile"].args[1]) if isinstance(node, ast.Name)}
        self.assertTrue({"terminal", "terminal_tests"}.issubset(compile_names))
        self.assertIn("try runTerminalChecks()", (EXPERIMENT / "ios/tests/main.swift").read_text())
        terminal = (EXPERIMENT / "ios/LinuxTerminalSession.swift").read_text()
        start = swift_block(terminal, "func start()")
        self.assertLess(start.index("JITBootstrap.mapJITWorks"), start.index("attempted = true"))
        self.assertIn("!LinuxProbeSession.shared.attempted", start)
        self.assertIn("!QemuRunner.shared.isRunning", start)
        self.assertIn("husk_console_loaded_game() == nil", start)
        self.assertIn("guard !attempted", start)
        probe = (EXPERIMENT / "ios/LinuxProbeSession.swift").read_text()
        self.assertIn("!LinuxTerminalSession.shared.attempted", probe)
        self.assertNotIn("Process(", terminal)


if __name__ == "__main__":
    unittest.main()
