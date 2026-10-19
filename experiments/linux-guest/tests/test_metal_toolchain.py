"""Verify Metal component preparation without running Apple tools or downloads."""
import contextlib
import hashlib
import io
import json
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "ci"))
import build_linux_probe_ipa as build


class MetalToolchainTests(unittest.TestCase):
    missing_component = ("error: cannot execute tool 'metal' due to missing Metal Toolchain; "
                         "use xcodebuild -downloadComponent MetalToolchain to download it\n")
    air = b"real-compiler-output-simulation-for-subprocess-test\n"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name)
        self.worker = build.Worker(self.output)
        self.worker.env["DEVELOPER_DIR"] = "/Applications/Override Xcode.app/Contents/Developer"
        self.worker.env["TOOLCHAINS"] = "unwanted.override.toolchain"
        self.report = {}
        self.calls = []
        self.responses = []
        self.popen_patch = mock.patch.object(build.subprocess, "Popen", side_effect=self.popen)
        self.popen_patch.start()
        self.addCleanup(self.popen_patch.stop)
        self.stdout = contextlib.redirect_stdout(io.StringIO())
        self.stdout.__enter__()
        self.addCleanup(self.stdout.__exit__, None, None, None)

    def popen(self, command, **kwargs):
        self.assertTrue(self.responses, "Unexpected additional process: " + repr(command))
        response = self.responses.pop(0)
        call = dict(command=command, **kwargs)
        self.calls.append(call)
        kwargs["stdout"].write(response.get("log", "").encode())
        if "-c" in command and response.get("output", True) and response.get("code", 0) == 0:
            Path(command[command.index("-o") + 1]).write_bytes(response.get("bytes", self.air))
        process = mock.Mock(pid=123456789)

        def wait(timeout=None):
            call.setdefault("wait_timeouts", []).append(timeout)
            if response.get("timeout") and timeout is not None:
                raise subprocess.TimeoutExpired(command, timeout)
            return response.get("code", 0)

        process.wait.side_effect = wait
        return process

    def ensure(self, *responses):
        self.responses = [*responses, dict(log="Apple metal version fixture\n")]
        build.ensure_metal_toolchain(self.worker, self.report)
        self.assertEqual(self.responses, [])

    def downloads(self):
        return [call for call in self.calls if "-downloadComponent" in call["command"]]

    def assert_probe(self, call):
        command = call["command"]
        compiler = command[command.index("xcrun"):]
        self.assertEqual(compiler[:4], ["xcrun", "--sdk", "iphoneos", "metal"])
        self.assertIn("-c", command)
        source = Path(command[command.index("-c") + 1])
        self.assertTrue(source.is_file())
        self.assertIn("kernel", source.read_text())
        self.assertIn("-o", command)

    def test_present_compiler_executes_probe_without_component_download(self):
        self.ensure(dict(log="Metal compile passed\n"))
        self.assertEqual(len(self.calls), 2)
        self.assert_probe(self.calls[0])
        self.assertEqual(self.downloads(), [])
        self.assertFalse(self.report["metal_toolchain"]["download_requested"])
        self.assertEqual(self.report["metal_toolchain"]["status"], "ready")
        self.assertEqual(self.report["metal_toolchain"]["initial_probe"], "passed")
        self.assertEqual(self.report["metal_toolchain"]["probe_artifact"]["size"], len(self.air))
        self.assertEqual(self.report["metal_toolchain"]["probe_artifact"]["sha256"], hashlib.sha256(self.air).hexdigest())
        self.assertEqual(self.worker.steps[0]["exit_code"], 0)
        self.assertIn("Metal compile passed", (self.output / "metal-probe-before.log").read_text())
        json.dumps(self.report)

    def test_explicit_missing_component_downloads_once_then_recompiles(self):
        self.ensure(dict(code=1, log=self.missing_component), dict(log="component download passed\n"),
                    dict(log="Metal compile after download passed\n"))
        self.assertEqual(len(self.calls), 4)
        self.assert_probe(self.calls[0])
        download = self.downloads()[0]["command"]
        self.assertEqual(download[download.index("xcodebuild"):], ["xcodebuild", "-downloadComponent", "metalToolchain"])
        self.assertEqual(len(self.downloads()), 1)
        self.assert_probe(self.calls[2])
        self.assertNotEqual(self.calls[0]["command"][-1], self.calls[2]["command"][-1])
        self.assertTrue(self.report["metal_toolchain"]["download_requested"])
        self.assertEqual(self.report["metal_toolchain"]["status"], "ready")
        self.assertEqual(self.report["metal_toolchain"]["initial_probe"], "missing_component")
        self.assertEqual(self.report["metal_toolchain"]["probe_artifact"]["sha256"], hashlib.sha256(self.air).hexdigest())
        self.assertEqual([step["exit_code"] for step in self.worker.steps], [1, 0, 0, 0])
        self.assertIn(self.missing_component, (self.output / "metal-probe-before.log").read_text())
        self.assertIn("component download passed", (self.output / "metal-toolchain-download.log").read_text())
        json.dumps(self.report)

    def test_permission_license_and_unrelated_compile_errors_do_not_download(self):
        for message in ("permission denied", "You have not agreed to the Xcode license agreements",
                        "input.metal:1: syntax error", "missing Metal Toolchain without official recovery command",
                        "xcodebuild -downloadComponent MetalToolchain unrelated message"):
            with self.subTest(message=message):
                # Use a fresh probe directory for each independent call.
                with tempfile.TemporaryDirectory() as tmp:
                    self.worker = build.Worker(Path(tmp))
                    self.report = {}
                    self.calls = []
                    self.responses = [dict(code=69, log=message)]
                    with self.assertRaises(RuntimeError):
                        build.ensure_metal_toolchain(self.worker, self.report)
                    self.assertEqual(len(self.calls), 1)
                    self.assertEqual(self.downloads(), [])
                    self.assertFalse(self.report["metal_toolchain"]["download_requested"])
                    self.assertEqual(self.worker.steps[0]["exit_code"], 69)
                    json.dumps(self.report)

    def test_component_download_failure_stops_without_reprobe_or_retry(self):
        self.responses = [dict(code=1, log=self.missing_component),
                          dict(code=1, log="component download network failure")]
        with self.assertRaises(RuntimeError):
            build.ensure_metal_toolchain(self.worker, self.report)
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(len(self.downloads()), 1)
        self.assertEqual(self.worker.steps[-1]["exit_code"], 1)
        self.assertIn("component download network failure", (self.output / "metal-toolchain-download.log").read_text())
        json.dumps(self.report)

    def test_download_license_or_permission_failure_is_not_bypassed(self):
        for message in ("permission denied", "Xcode license not accepted"):
            with self.subTest(message=message), tempfile.TemporaryDirectory() as tmp:
                self.worker = build.Worker(Path(tmp))
                self.report = {}
                self.calls = []
                self.responses = [dict(code=1, log=self.missing_component), dict(code=69, log=message)]
                with self.assertRaises(RuntimeError):
                    build.ensure_metal_toolchain(self.worker, self.report)
                self.assertEqual(len(self.calls), 2)
                self.assertEqual(len(self.downloads()), 1)
                self.assertFalse(any("sudo" in call["command"] or "-license" in call["command"]
                                     for call in self.calls))

    def test_failed_reprobe_stops_after_single_download(self):
        self.responses = [dict(code=1, log=self.missing_component), dict(log="download passed"),
                          dict(code=1, log=self.missing_component)]
        with self.assertRaises(RuntimeError):
            build.ensure_metal_toolchain(self.worker, self.report)
        self.assertEqual(len(self.calls), 3)
        self.assertEqual(len(self.downloads()), 1)
        self.assertEqual(self.worker.steps[-1]["exit_code"], 1)
        json.dumps(self.report)

    def test_zero_exit_without_compiled_air_is_not_success_or_missing_component(self):
        self.responses = [dict(code=0, output=False)]
        with self.assertRaises((ValueError, RuntimeError)):
            build.ensure_metal_toolchain(self.worker, self.report)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.downloads(), [])

    def test_zero_exit_with_empty_air_is_rejected(self):
        self.responses = [dict(code=0, bytes=b"")]
        with self.assertRaises((ValueError, RuntimeError)):
            build.ensure_metal_toolchain(self.worker, self.report)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.downloads(), [])

    def test_successful_download_without_real_reprobe_air_remains_failure(self):
        for result in (dict(output=False), dict(bytes=b"")):
            with self.subTest(result=result), tempfile.TemporaryDirectory() as tmp:
                self.worker = build.Worker(Path(tmp))
                self.report = {}
                self.calls = []
                self.responses = [dict(code=1, log=self.missing_component), dict(log="download passed"), result]
                with self.assertRaises(ValueError):
                    build.ensure_metal_toolchain(self.worker, self.report)
                self.assertEqual(len(self.calls), 3)
                self.assertEqual(len(self.downloads()), 1)
                self.assertEqual(self.report["metal_toolchain"]["status"], "failed")
                self.assertNotIn("probe_artifact", self.report["metal_toolchain"])
                json.dumps(self.report)

    def test_angle_environment_isolation_and_remaining_budget_reach_every_child(self):
        self.worker.started = time.monotonic() - (build.NATIVE_BUILD_BUDGET_SECONDS - 100)
        self.ensure(dict(code=1, log=self.missing_component), dict(log="download passed"), dict())
        for call in self.calls:
            self.assertEqual(call["command"][:4], ["/usr/bin/env", "-i",
                "PATH=" + self.worker.env["PATH"], "HOME=" + self.worker.env["HOME"]])
            self.assertIn(call["command"][4], ("xcrun", "xcodebuild"))
            self.assertFalse(any(argument.startswith(("DEVELOPER_DIR=", "TOOLCHAINS="))
                                 for argument in call["command"]))
            self.assertIs(call["env"], self.worker.env)
            self.assertTrue(call["start_new_session"])
            self.assertGreater(call["wait_timeouts"][0], 0)
            self.assertLessEqual(call["wait_timeouts"][0], 100)
            self.assertNotIn("shell", call)
        self.assertEqual(self.worker.env["DEVELOPER_DIR"], "/Applications/Override Xcode.app/Contents/Developer")
        self.assertEqual(self.worker.env["TOOLCHAINS"], "unwanted.override.toolchain")
        self.assertEqual(self.report["metal_toolchain"]["selection_mode"], "angle_env_i_path_home")
        self.assertTrue(self.report["metal_toolchain"]["ignored_developer_dir_override"])
        self.assertTrue(self.report["metal_toolchain"]["ignored_toolchains_override"])

    def test_probe_timeout_propagates_without_component_download(self):
        self.responses = [dict(timeout=True)]
        with mock.patch.object(build.os, "killpg") as kill, self.assertRaises(subprocess.TimeoutExpired):
            build.ensure_metal_toolchain(self.worker, self.report)
        kill.assert_called_once_with(123456789, signal.SIGKILL)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.downloads(), [])

    def test_download_timeout_stops_without_retry_or_reprobe(self):
        self.responses = [dict(code=1, log=self.missing_component), dict(timeout=True)]
        with mock.patch.object(build.os, "killpg") as kill, self.assertRaises(subprocess.TimeoutExpired):
            build.ensure_metal_toolchain(self.worker, self.report)
        kill.assert_called_once_with(123456789, signal.SIGKILL)
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(len(self.downloads()), 1)


if __name__ == "__main__":
    unittest.main()
