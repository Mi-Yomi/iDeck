import contextlib
import hashlib
import io
import json
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "ci"))
sys.path.insert(0, str(ROOT / "experiments/linux-guest/ipa"))
import check_build_request
import build_linux_probe_ipa
import package_probe


class RequestGuards(unittest.TestCase):
    def setUp(self):
        self.head = "1" * 40
        self.env = dict(IDECK_WORKFLOW_ID="ideck-linux-guest-profile-check",
                        CM_BRANCH=check_build_request.LINUX_BRANCH, CM_REPO_SLUG="Mi-Yomi/iDeck",
                        CM_COMMIT=self.head, EXPECTED_COMMIT=self.head,
                        FREE_QUOTA_VERIFIED="true", PRIVATE_SOURCE_VERIFIED="true")

    def test_exact_request_accepted(self):
        self.assertEqual(check_build_request.validate(self.env, self.head, False), [])

    def test_wrong_branch_even_at_same_commit_rejected(self):
        self.env["CM_BRANCH"] = "main"
        self.assertIn("Select branch", " ".join(check_build_request.validate(self.env, self.head, False)))

    def test_steam_branch_is_allowed_only_for_exact_manual_ipa_workflow(self):
        env = dict(self.env, CM_BRANCH=check_build_request.STEAM_BRANCH,
                   IDECK_WORKFLOW_ID="ideck-linux-probe-ipa")
        self.assertEqual(check_build_request.validate(env, self.head, False), [])
        for workflow in ("ideck-linux-guest-profile-check", "ideck-linux-probe-ipa-other"):
            with self.subTest(workflow=workflow):
                self.assertTrue(check_build_request.validate(dict(env, IDECK_WORKFLOW_ID=workflow), self.head, False))
        for branch in ("main", check_build_request.STEAM_BRANCH + "-other"):
            with self.subTest(branch=branch):
                self.assertTrue(check_build_request.validate(dict(env, CM_BRANCH=branch), self.head, False))

    def test_steam_ipa_still_rejects_wrong_sha_dirty_checkout_and_missing_attestations(self):
        env = dict(self.env, CM_BRANCH=check_build_request.STEAM_BRANCH,
                   IDECK_WORKFLOW_ID="ideck-linux-probe-ipa")
        self.assertTrue(check_build_request.validate(env, self.head, True))
        for key, value in (("EXPECTED_COMMIT", "a" * 40), ("CM_COMMIT", "a" * 40),
                           ("FREE_QUOTA_VERIFIED", "false"), ("PRIVATE_SOURCE_VERIFIED", "false"),
                           ("CM_REPO_SLUG", "other/iDeck")):
            with self.subTest(key=key):
                self.assertTrue(check_build_request.validate(dict(env, **{key: value}), self.head, False))

    def test_old_checkout_and_provider_mismatch_rejected(self):
        for key in ("EXPECTED_COMMIT", "CM_COMMIT"):
            changed = dict(self.env, **{key: "a" * 40})
            self.assertTrue(check_build_request.validate(changed, self.head, False))
        self.assertTrue(check_build_request.validate(self.env, self.head, True))

    def test_missing_input_and_default_sentinel_do_not_authorize_run(self):
        for value in ("", "REQUIRED", "a77ab50", "A" * 40):
            self.env["EXPECTED_COMMIT"] = value
            self.assertTrue(check_build_request.validate(self.env, self.head, False))

    def test_quota_and_private_verification_still_required(self):
        for key in ("FREE_QUOTA_VERIFIED", "PRIVATE_SOURCE_VERIFIED", "CM_REPO_SLUG"):
            changed = dict(self.env, **{key: "false"})
            self.assertTrue(check_build_request.validate(changed, self.head, False))

    def test_legacy_expected_source_commit_remains_distinct_from_transport_commit(self):
        env = dict(IDECK_WORKFLOW_ID="ideck-main-apple-source-check", EXPECTED_SOURCE_COMMIT="b" * 40,
                   FREE_QUOTA_VERIFIED="true", PRIVATE_SOURCE_VERIFIED="true")
        self.assertFalse(check_build_request.validate(env, self.head, False))
        env["EXPECTED_SOURCE_COMMIT"] = "REQUIRED"
        self.assertTrue(check_build_request.validate(env, self.head, False))


class IPAInputs(unittest.TestCase):
    def test_failed_build_command_is_not_a_successful_step(self):
        with tempfile.TemporaryDirectory() as tmp:
            worker = build_linux_probe_ipa.Worker(Path(tmp))
            with self.assertRaisesRegex(RuntimeError, "compiler failed"):
                worker.run("compiler", [sys.executable, "-c", "print('real child failure'); raise SystemExit(3)"])
            self.assertEqual(worker.steps[-1]["exit_code"], 3)
            self.assertIn("real child failure", (Path(tmp) / "compiler.log").read_text())

    def test_real_committed_guest_restores_with_original_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "guest"
            assets = build_linux_probe_ipa.restore_guest(out)
            self.assertEqual((out / "vmlinuz-virt").stat().st_size, 10351104)
            self.assertEqual(build_linux_probe_ipa.sha(out / "initramfs-ideck.gz"),
                             "5f64312eeef340991c6b0d97bd9d1fb01649c1763e14d7fb8231ad16551e9343")
            with self.assertRaisesRegex(ValueError, "must be new"):
                build_linux_probe_ipa.restore_guest(out)
            lock = json.loads((ROOT / "experiments/linux-guest/ipa/guest.lock.json").read_text())
            self.assertEqual(assets, lock["files"])
            report = dict(status="failed", ipa_created=False, guest_assets=assets)
            link = tarfile.TarInfo("unused-link")
            link.type, link.linkname = tarfile.SYMTYPE, "/opt/X11/include"
            log = io.StringIO()
            with contextlib.redirect_stdout(log), self.assertRaises(tarfile.AbsoluteLinkError):
                try:
                    raise tarfile.AbsoluteLinkError(link)
                except tarfile.AbsoluteLinkError as error:
                    report["failure"] = str(error)
                    raise
                finally:
                    build_linux_probe_ipa.write_result(Path(tmp), report)
            self.assertEqual(json.loads((Path(tmp) / "result.json").read_text()), report)
            self.assertEqual(json.loads(log.getvalue().split("=", 1)[1]), report)

    def test_probe_project_excludes_unused_embedded_runtimes(self):
        project = json.loads((ROOT / "experiments/linux-guest/ipa/project.json").read_text())
        target = project["targets"]["Husk"]
        dependencies = str(target["dependencies"])
        self.assertNotIn("MoltenVK", dependencies)
        self.assertNotIn("libhuskps4", dependencies)
        self.assertIn("libqemu-aarch64-softmmu.dylib", dependencies)
        self.assertIn("libANGLE-shared.dylib", dependencies)
        self.assertIn("HuskJITHelper", dependencies)
        self.assertEqual(len(target["preBuildScripts"]), 4)
        self.assertIn("ideck-stage-linux-guest.py", target["preBuildScripts"][0]["script"])
        self.assertIn("ideck-stage-linux-terminal.py", target["preBuildScripts"][1]["script"])
        self.assertIn("iDeckLinuxTerminal", target["preBuildScripts"][1]["script"])
        self.assertIn("ideck-stage-debian.py", target["preBuildScripts"][2]["script"])
        self.assertIn("iDeckDebian", target["preBuildScripts"][2]["script"])
        self.assertIn("ideck-stage-desktop.py", target["preBuildScripts"][3]["script"])
        self.assertIn("iDeckLinuxDesktop", target["preBuildScripts"][3]["script"])
        self.assertIn("IDECK_LINUX_PROBE_ONLY", project["settings"]["base"]["SWIFT_ACTIVE_COMPILATION_CONDITIONS"])

    def test_package_rejects_husk_identity_and_simulator(self):
        valid = dict(CFBundleIdentifier="dev.ideck.linuxprobe", CFBundleExecutable="Husk", CFBundlePackageType="APPL",
                     CFBundleVersion="119", CFBundleShortVersionString="2.0.0", MinimumOSVersion="16.0", UIDeviceFamily=[1, 2])
        package_probe.check_plist(valid)
        with self.assertRaises(ValueError):
            package_probe.check_plist(dict(valid, CFBundleIdentifier="com.husk.app"))
        package_probe.check_ios_build_output("platform IOS\n")
        package_probe.check_ios_build_output("cmd LC_VERSION_MIN_IPHONEOS\n")
        for text in ("platform IOSSIMULATOR\n", "platform MACOS\n", "platform MACCATALYST\n", ""):
            with self.assertRaises(ValueError):
                package_probe.check_ios_build_output(text)


class NativeExtraction(unittest.TestCase):
    rule = {"path": "source/unused-X11-link", "target": "/opt/X11/include", "reason": "unused fixture"}

    def archive(self, root, members, omissions=None):
        archive = root / "source.tar.gz"
        with tarfile.open(archive, "w:gz") as target:
            for name, kind, value in members:
                member = tarfile.TarInfo(name)
                member.type = kind
                if kind == tarfile.REGTYPE:
                    member.size = len(value)
                    target.addfile(member, io.BytesIO(value))
                else:
                    member.linkname = value
                    target.addfile(member)
        item = dict(filename=archive.name, size=archive.stat().st_size,
                    sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
                    omit_symlinks=[] if omissions is None else omissions)
        return archive, item

    def test_reviewed_link_omitted_and_real_files_extracted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive, item = self.archive(root, [("source/input.c", tarfile.REGTYPE, b"original source\n"),
                (self.rule["path"], tarfile.SYMTYPE, self.rule["target"])], [self.rule])
            out = root / "unpacked"
            result = build_linux_probe_ipa.unpack_source(archive, out, item)
            self.assertEqual((out / "source/input.c").read_bytes(), b"original source\n")
            self.assertFalse((out / self.rule["path"]).is_symlink())
            self.assertFalse((out / self.rule["path"]).exists())
            self.assertEqual(result["omitted_symlinks"], [self.rule])

    def test_other_unsafe_members_remain_rejected(self):
        for member in [("source/other-link", tarfile.SYMTYPE, "/opt/X11/include"),
                       ("source/escape-link", tarfile.SYMTYPE, "../../outside.txt"),
                       ("../outside.txt", tarfile.REGTYPE, b"must not overwrite")]:
            with self.subTest(member=member), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                outside = root / "outside.txt"
                outside.write_bytes(b"unchanged")
                archive, item = self.archive(root, [member], [self.rule])
                with self.assertRaises(tarfile.FilterError):
                    build_linux_probe_ipa.unpack_source(archive, root / "unpacked", item)
                self.assertEqual(outside.read_bytes(), b"unchanged")

    def test_omission_requires_exact_link_type_and_target(self):
        for kind, value in [(tarfile.REGTYPE, b"must not silently omit a regular file"),
                            (tarfile.SYMTYPE, "/unreviewed/path")]:
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                archive, item = self.archive(root, [(self.rule["path"], kind, value)], [self.rule])
                with self.assertRaisesRegex(ValueError, "differs from reviewed symlink"):
                    build_linux_probe_ipa.unpack_source(archive, root / "unpacked", item)

    def test_source_hash_mismatch_rejected_before_extraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive, item = self.archive(root, [("source/input.c", tarfile.REGTYPE, b"source")])
            item["sha256"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "differs from lock"):
                build_linux_probe_ipa.unpack_source(archive, root / "unpacked", item)
            self.assertFalse((root / "unpacked").exists())

    def test_missing_reviewed_link_is_not_silently_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive, item = self.archive(root, [("source/input.c", tarfile.REGTYPE, b"source")], [self.rule])
            with self.assertRaisesRegex(ValueError, "symlink is absent"):
                build_linux_probe_ipa.unpack_source(archive, root / "unpacked", item)


if __name__ == "__main__":
    unittest.main()
