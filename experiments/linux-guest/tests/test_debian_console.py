"""Transport rejection and real overlay contracts; guest evidence is separate."""
import gzip
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

EXPERIMENT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXPERIMENT / "tools"))
import debian_bundle as bundle
from test_terminal import cpio_entries, swift_block


class DebianTransportChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"; self.source.mkdir()
        self.files = {name: (name + " fixture\n").encode() for name in bundle.NAMES}
        for name, data in self.files.items(): (self.source / name).write_bytes(data)
        self.lock = {"schema": 1, "files": {n: bundle.metadata(self.source / n) for n in bundle.NAMES}}
        self.transport = dict(self.files)
        self.transport["rootfs-v1.raw.gz"] = gzip.compress(self.transport.pop("rootfs-v1.raw"), mtime=0)
        self.archive = self.root / "payload.tar"
        self.lockpath = self.root / "lock.json"
        self.make_archive()

    def make_archive(self, special=None):
        with tarfile.open(self.archive, "w", format=tarfile.USTAR_FORMAT) as tar:
            for name, data in self.transport.items():
                member = tarfile.TarInfo(name); member.size = len(data)
                if special is not None and name == "vmlinuz-virt": special(member)
                tar.addfile(member, io.BytesIO(data) if member.isfile() else None)
        self.lock["transport_files"] = {n: {"size": len(b), "sha256": hashlib.sha256(b).hexdigest()} for n, b in self.transport.items()}
        self.lock["payload"] = {"filename": self.archive.name, **bundle.metadata(self.archive)}
        self.lockpath.write_text(json.dumps(self.lock))

    def test_restore_stage_exact_and_repeat(self):
        restored = self.root / "restore"
        bundle.restore(self.archive, restored, self.lockpath)
        target = self.root / "App.app/iDeckDebian"
        for _ in range(2): bundle.stage(restored, target, self.lockpath)
        self.assertEqual({p.name: p.read_bytes() for p in target.iterdir()}, self.files)
        with self.assertRaises(ValueError): bundle.restore(self.archive, restored, self.lockpath)

    def test_wrong_payload_hash_creates_no_bundle(self):
        self.archive.write_bytes(self.archive.read_bytes() + b"changed")
        target = self.root / "out"
        with self.assertRaises(ValueError): bundle.restore(self.archive, target, self.lockpath)
        self.assertFalse(target.exists())

    def test_archive_link_and_traversal_refused_before_writes(self):
        for special in [lambda m: setattr(m, "type", tarfile.SYMTYPE), lambda m: setattr(m, "name", "../escape")]:
            self.make_archive(special)
            target = self.root / "unsafe"
            with self.assertRaises(ValueError): bundle.restore(self.archive, target, self.lockpath)
            self.assertFalse(target.exists()); self.assertFalse((self.root / "escape").exists())

    def test_decompressed_hash_and_size_required(self):
        for data in [b"X" * len(self.files["rootfs-v1.raw"]), b"X" * 1000]:
            self.transport["rootfs-v1.raw.gz"] = gzip.compress(data)
            self.make_archive()
            target = self.root / ("out-" + str(len(data)))
            with self.assertRaises(ValueError): bundle.restore(self.archive, target, self.lockpath)

    def test_missing_corrupt_extra_and_symlink_assets(self):
        target = self.source / "rootfs-v1.raw"
        original = target.read_bytes()
        target.write_bytes(b"x" * len(original))
        with self.assertRaises(ValueError): bundle.verify(self.source, self.lock)
        target.unlink()
        with self.assertRaises(ValueError): bundle.verify(self.source, self.lock)
        target.symlink_to(self.source / "vmlinuz-virt")
        with self.assertRaises(ValueError): bundle.verify(self.source, self.lock)
        target.unlink(); target.write_bytes(original)
        (self.source / "extra").write_bytes(b"x")
        with self.assertRaises(ValueError): bundle.verify(self.source, self.lock)

    def test_low_space_and_symlink_parent_fail_closed(self):
        with patch.object(bundle.shutil, "disk_usage", return_value=type("Usage", (), {"free": 0})()):
            with self.assertRaisesRegex(ValueError, "space"):
                bundle.restore(self.archive, self.root / "full", self.lockpath)
        self.assertEqual(list((self.root / "full").iterdir()), [])
        alias = self.root / "alias"; alias.symlink_to(self.source, target_is_directory=True)
        with self.assertRaises(ValueError): bundle.restore(self.archive, alias / "new", self.lockpath)
        self.assertFalse((self.source / "new").exists())

    def test_missing_private_transport_is_an_explicit_blocker(self):
        with patch.dict(bundle.os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "IDECK_DEBIAN_PAYLOAD_URL"):
                bundle.fetch(self.root / "download", self.lockpath)
        self.assertFalse((self.root / "download").exists())

    def test_github_token_only_reaches_asset_api_and_is_stripped_on_redirect(self):
        environment = {"IDECK_DEBIAN_PAYLOAD_URL": "https://api.github.com/repos/Mi-Yomi/iDeck/releases/assets/123",
                       "IDECK_DEBIAN_PAYLOAD_TOKEN": "test-private-token"}
        with patch.dict(bundle.os.environ, environment), patch.object(bundle.urllib.request, "build_opener") as factory:
            factory.return_value.open.return_value = io.BytesIO(self.archive.read_bytes())
            bundle.fetch(self.root / "download", self.lockpath)
            request = factory.return_value.open.call_args.args[0]
            self.assertEqual(request.get_header("Authorization"), "Bearer test-private-token")
            handler = factory.call_args.args[0]()
            redirected = handler.redirect_request(request, None, 302, "Found", {}, "https://release-assets.githubusercontent.com/fixture")
            self.assertIsNone(redirected.get_header("Authorization"))
            with self.assertRaises(ValueError): handler.redirect_request(request, None, 302, "Found", {}, "http://example.com/fixture")

    def test_token_cannot_be_sent_to_other_hosts_or_repositories(self):
        for url in ["https://example.com/asset", "https://api.github.com/repos/other/project/releases/assets/123"]:
            with patch.dict(bundle.os.environ, {"IDECK_DEBIAN_PAYLOAD_URL": url, "IDECK_DEBIAN_PAYLOAD_TOKEN": "secret"}):
                with self.assertRaisesRegex(ValueError, "restricted"):
                    bundle.fetch(self.root / "download", self.lockpath)
        self.assertFalse((self.root / "download").exists())

    def test_download_errors_do_not_expose_credentials_or_publish_partial(self):
        with patch.dict(bundle.os.environ, {"IDECK_DEBIAN_PAYLOAD_URL": "https://example.com/asset?secret=example",
                                          "IDECK_DEBIAN_PAYLOAD_TOKEN": ""}), patch.object(bundle.urllib.request, "build_opener") as factory:
            factory.return_value.open.side_effect = RuntimeError("https://example.com/asset?secret=example")
            with self.assertRaises(RuntimeError) as failure: bundle.fetch(self.root / "download", self.lockpath)
            self.assertNotIn("secret=", str(failure.exception))
            self.assertFalse((self.root / "download").exists())
            self.assertFalse(list(self.root.glob(".debian-download-*")))


class DebianIntegrationChecks(unittest.TestCase):
    def test_runtime_uses_real_husk_and_retains_owner_after_stop(self):
        source = (EXPERIMENT / "ios/LinuxTerminalSession.swift").read_text()
        final = swift_block(source, "private func finalizeIfClean()")
        self.assertIn("lifecycle.maySyncForCleanStop", final)
        self.assertIn("try disk.synchronize()", final)
        for forbidden in ("closeUnused", "disk = nil", "qemu_cleanup"):
            self.assertNotIn(forbidden, final)
        self.assertIn("qemu_init(Int32(args.count), pointers)", source)
        self.assertIn("qemu_main_loop()", source)
        self.assertIn("LinuxTerminalSession.debian.attempted", source)
        self.assertIn('isDebian ? "iDeckDebian" : "iDeckLinux"', source)
        self.assertIn(".needsRecovery", source)
        timeout = swift_block(source, "private func scheduleStopTimeout()")
        self.assertIn("lifecycle.record(.timedOut)", timeout)

    def test_production_init_and_login_contract(self):
        init = (EXPERIMENT / "guest/ideck-debian-init").read_text()
        login = (EXPERIMENT / "guest/ideck-debian-login").read_text()
        self.assertLess(init.index("modprobe virtio_mmio"), init.index("modprobe virtio_blk"))
        self.assertIn("/lib/modules/6.18.35-0-virt/$module", init)
        self.assertIn("getty -n -l /ideck-debian-login -L 115200 ttyAMA0 dumb 3>&- &", init)
        self.assertIn("chroot /sysroot /usr/bin/env -i", login)
        self.assertIn("--default-signal=INT,QUIT", login)
        self.assertIn("exec /bin/sh -i", login)
        shutdown = init[init.index("shutdown() {"):init.index("trap shutdown")]
        self.assertLess(shutdown.index("kill -KILL -1"), shutdown.index("umount /sysroot"))
        self.assertLess(shutdown.index("umount /sysroot"), shutdown.index("echo IDECK_DEBIAN_CLEAN_UNMOUNT"))
        self.assertEqual(init.count("poweroff -f"), 1)
        for bad in ("mkfs", "e2fsck", "ideck.phase", "posix-check"):
            self.assertNotIn(bad, init)

    def test_actual_payload_lock_and_ci_mandatory_gates(self):
        lock = bundle.load_lock(EXPERIMENT / "ipa/debian.lock.json")
        self.assertEqual(lock["files"]["rootfs-v1.raw"]["sha256"], "a081d86594a0c59e585541ae26fa586468f267767dc081796f51186ea9c01217")
        for name, expected in lock["inputs"]["guest"].items(): bundle.checked(EXPERIMENT / "guest" / name, expected)
        ci = (EXPERIMENT.parents[1] / "ci/check_linux_guest_profile.py").read_text()
        self.assertIn('"LINUX_CONSOLE_RUNTIME_REGRESSION_PASS"', ci)
        self.assertIn('raise RuntimeError("Mandatory Swift runtime/storage regression', ci)
        builder = (EXPERIMENT.parents[1] / "ci/build_linux_probe_ipa.py").read_text()
        self.assertLess(builder.index('worker.run("swift-source-check"'), builder.index('worker.run("build-tools"'))
        self.assertLess(builder.index('fetch_debian(debian_archive'), builder.index('worker.run("build-tools"'))
        project = json.loads((EXPERIMENT / "ipa/project.json").read_text())
        self.assertIn("Stage verified iDeck Debian console", [s["name"] for s in project["targets"]["Husk"]["preBuildScripts"]])


if __name__ == "__main__": unittest.main()
