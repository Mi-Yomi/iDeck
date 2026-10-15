import json
import sys
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
            build_linux_probe_ipa.restore_guest(out)
            self.assertEqual((out / "vmlinuz-virt").stat().st_size, 10351104)
            self.assertEqual(build_linux_probe_ipa.sha(out / "initramfs-ideck.gz"),
                             "5f64312eeef340991c6b0d97bd9d1fb01649c1763e14d7fb8231ad16551e9343")
            with self.assertRaisesRegex(ValueError, "must be new"):
                build_linux_probe_ipa.restore_guest(out)

    def test_probe_project_excludes_unused_embedded_runtimes(self):
        project = json.loads((ROOT / "experiments/linux-guest/ipa/project.json").read_text())
        target = project["targets"]["Husk"]
        dependencies = str(target["dependencies"])
        self.assertNotIn("MoltenVK", dependencies)
        self.assertNotIn("libhuskps4", dependencies)
        self.assertIn("libqemu-aarch64-softmmu.dylib", dependencies)
        self.assertIn("libANGLE-shared.dylib", dependencies)
        self.assertIn("HuskJITHelper", dependencies)
        self.assertEqual(len(target["preBuildScripts"]), 1)
        self.assertIn("ideck-stage-linux-guest.py", target["preBuildScripts"][0]["script"])
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


if __name__ == "__main__":
    unittest.main()
