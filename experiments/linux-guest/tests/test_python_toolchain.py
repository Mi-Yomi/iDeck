"""Exercise worker-local Python setup with mocked processes, never pip/network."""
import ast
import contextlib
import hashlib
import io
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "ci"))
import build_linux_probe_ipa as build


class NativePythonTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name)
        fake_sys = types.SimpleNamespace(executable=sys.executable, version_info=(3, 12, 11),
                                         version="3.12.11 (mock interpreter)",
                                         implementation=types.SimpleNamespace(name="cpython"))
        for patcher in (mock.patch.object(build, "sys", fake_sys),
                        mock.patch.object(build.platform, "system", return_value="Darwin"),
                        mock.patch.object(build.platform, "machine", return_value="arm64")):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.worker = build.Worker(self.output)
        self.old_environment = dict(os.environ)
        self.old_worker_environment = dict(self.worker.env)
        self.report = {}
        self.calls = []
        self.responses = []
        patcher = mock.patch.object(build.subprocess, "Popen", side_effect=self.popen)
        patcher.start()
        self.addCleanup(patcher.stop)
        log = contextlib.redirect_stdout(io.StringIO())
        log.__enter__()
        self.addCleanup(log.__exit__, None, None, None)

    @property
    def python(self):
        return self.output / "native-python/bin/python3"

    def probe(self, **changes):
        result = dict(pyyaml_version="6.0.2", python_version="3.12.11", executable=str(self.python),
                      prefix=str(self.output / "native-python"),
                      pyyaml_module=str(self.output / "native-python/lib/python3.12/site-packages/yaml/__init__.py"))
        result.update(changes)
        return result

    def popen(self, command, **kwargs):
        self.assertTrue(self.responses, "Unexpected external command: " + repr(command))
        response = self.responses.pop(0)
        call = dict(command=command, environment=dict(kwargs["env"]), **kwargs)
        self.calls.append(call)
        if "venv" in command and response.get("code", 0) == 0:
            self.python.parent.mkdir(parents=True)
            self.python.write_text("mock executable; never run\n")
        output = response.get("log")
        if output is None:
            output = json.dumps(response.get("probe", self.probe())) if "-c" in command else "ok\n"
        kwargs["stdout"].write(output.encode())
        process = mock.Mock(pid=123456789)

        def wait(timeout=None):
            call.setdefault("wait_timeouts", []).append(timeout)
            if response.get("timeout") and timeout is not None:
                raise subprocess.TimeoutExpired(command, timeout)
            return response.get("code", 0)

        process.wait.side_effect = wait
        return process

    def ensure(self, *responses):
        self.responses = list(responses or (dict(), dict(), dict()))
        build.ensure_native_python(self.worker, self.report)
        self.assertEqual(self.responses, [])

    def assert_environment_unchanged(self):
        self.assertEqual(self.worker.env, self.old_worker_environment)
        self.assertEqual(dict(os.environ), self.old_environment)

    def test_isolated_venv_and_locked_install_use_same_absolute_interpreter(self):
        self.ensure()
        self.assertEqual(len(self.calls), 3)
        creation, install, probe = [call["command"] for call in self.calls]
        self.assertEqual(creation, [sys.executable, "-I", "-m", "venv", str(self.output / "native-python")])
        self.assertEqual(install[:5], [str(self.python), "-I", "-m", "pip", "--isolated"])
        for flag in ("--disable-pip-version-check", "--no-input", "--no-cache-dir", "--no-index",
                     "--no-deps", "--only-binary=:all:", "--require-hashes"):
            self.assertIn(flag, install)
        self.assertEqual(Path(install[install.index("--requirement") + 1]), build.NATIVE_PYTHON_REQUIREMENTS)
        self.assertEqual(probe[:3], [str(self.python), "-I", "-c"])
        self.assertIn("yaml", probe[3])
        self.assertNotIn("--system-site-packages", creation)
        for command in (creation, install, probe):
            for forbidden in ("--trusted-host", "--break-system-packages", "--user", "sudo"):
                self.assertNotIn(forbidden, command)
        receipt = self.report["native_python"]
        self.assertEqual(receipt["status"], "ready")
        json.dumps(receipt)

    def test_requirement_locks_one_official_wheel_and_content_hash(self):
        requirement = build.NATIVE_PYTHON_REQUIREMENTS.read_text()
        self.assertIn("PyYAML-6.0.2-cp312-cp312-macosx_11_0_arm64.whl", requirement)
        self.assertIn("https://files.pythonhosted.org/", requirement)
        self.assertIn("--hash=sha256:ce826d6ef20b1bc864f0a68340c8b3287705cae2f8b4b1d932177dcc76721725", requirement)
        active = [line for line in requirement.splitlines() if line.strip() and not line.startswith("#")]
        self.assertEqual(len(active), 1)
        self.assertTrue(active[0].startswith("PyYAML @ https://files.pythonhosted.org/"))
        self.assertNotIn("--trusted-host", requirement)
        self.assertEqual(build.NATIVE_PYYAML_VERSION, "6.0.2")

    def test_path_commit_is_worker_local_and_after_successful_probe(self):
        self.ensure()
        self.assertEqual(self.worker.env["PATH"], str(self.python.parent) + os.pathsep + self.old_worker_environment["PATH"])
        self.assertEqual(self.worker.env["VIRTUAL_ENV"], str(self.output / "native-python"))
        self.assertEqual(dict(os.environ), self.old_environment)
        for call in self.calls:
            self.assertEqual(call["environment"], self.old_worker_environment)
            self.assertNotIn("shell", call)
            self.assertTrue(call["start_new_session"])

    def test_unsupported_host_or_base_python_fails_before_install(self):
        invalid = (mock.patch.object(build.platform, "system", return_value="Linux"),
                   mock.patch.object(build.platform, "machine", return_value="x86_64"),
                   mock.patch.object(build.sys, "version_info", (3, 13, 0)),
                   mock.patch.object(build.sys, "implementation", types.SimpleNamespace(name="pypy")))
        for patcher in invalid:
            with self.subTest(patcher=patcher), patcher, self.assertRaisesRegex(RuntimeError, "CPython 3.12"):
                build.ensure_native_python(self.worker, self.report)
            self.assertEqual(self.calls, [])
            self.assert_environment_unchanged()
            self.assertEqual(self.report["native_python"]["status"], "failed")

    def test_preexisting_or_dangling_venv_path_is_not_overwritten(self):
        destination = self.output / "native-python"
        for symlink in (False, True):
            with self.subTest(symlink=symlink):
                if symlink:
                    destination.symlink_to(self.output / "uncreated")
                else:
                    destination.write_bytes(b"existing unrelated artifact")
                with self.assertRaises(FileExistsError):
                    build.ensure_native_python(self.worker, self.report)
                self.assertEqual(self.calls, [])
                if symlink:
                    self.assertTrue(destination.is_symlink())
                else:
                    self.assertEqual(destination.read_bytes(), b"existing unrelated artifact")
                self.assert_environment_unchanged()
                destination.unlink()

    def test_venv_creation_failure_stops_before_install_and_preserves_environment(self):
        self.responses = [dict(code=1, log="venv creation failed")]
        with self.assertRaises(RuntimeError):
            build.ensure_native_python(self.worker, self.report)
        self.assertEqual(len(self.calls), 1)
        self.assert_environment_unchanged()
        self.assertEqual(self.worker.steps[0]["exit_code"], 1)
        self.assertEqual(self.report["native_python"]["status"], "failed")

    def test_install_failure_stops_before_import_and_preserves_error_log(self):
        self.responses = [dict(), dict(code=1, log="locked wheel integrity check failed")]
        with self.assertRaises(RuntimeError):
            build.ensure_native_python(self.worker, self.report)
        self.assertEqual(len(self.calls), 2)
        self.assert_environment_unchanged()
        self.assertIn("locked wheel integrity check failed", (self.output / "python-install.log").read_text())
        self.assertEqual(self.worker.steps[-1]["exit_code"], 1)

    def test_import_failure_stops_without_path_change(self):
        self.responses = [dict(), dict(), dict(code=1, log="ModuleNotFoundError: No module named yaml")]
        with self.assertRaises(RuntimeError):
            build.ensure_native_python(self.worker, self.report)
        self.assertEqual(len(self.calls), 3)
        self.assert_environment_unchanged()
        self.assertEqual(self.report["native_python"]["status"], "failed")
        self.assertIn("ModuleNotFoundError", (self.output / "python-probe.log").read_text())

    def test_wrong_version_prefix_or_outside_module_are_rejected(self):
        for changed in (dict(pyyaml_version="6.0.1"), dict(python_version="3.13.0"),
                        dict(executable="/unrelated/system/python3"), dict(prefix="/unrelated/system/python"),
                        dict(pyyaml_module="/unrelated/system/yaml/__init__.py")):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory() as temp:
                self.output = Path(temp)
                self.worker = build.Worker(self.output)
                self.old_worker_environment = dict(self.worker.env)
                self.report = {}
                self.calls = []
                self.responses = [dict(), dict(), dict(probe=self.probe(**changed))]
                with self.assertRaises((ValueError, RuntimeError)):
                    build.ensure_native_python(self.worker, self.report)
                self.assertEqual(len(self.calls), 3)
                self.assert_environment_unchanged()
                self.assertEqual(self.report["native_python"]["status"], "failed")

    def test_invalid_probe_json_is_fatal(self):
        self.responses = [dict(), dict(), dict(log="not an import receipt")]
        with self.assertRaises(ValueError):
            build.ensure_native_python(self.worker, self.report)
        self.assert_environment_unchanged()
        self.assertEqual(self.report["native_python"]["status"], "failed")

    def test_malformed_identity_cannot_override_failed_status(self):
        identities = ([], {}, dict(self.probe(), status="ready"), dict(self.probe(), pyyaml_version=602))
        for identity in identities:
            with self.subTest(identity=identity), tempfile.TemporaryDirectory() as temp:
                self.output = Path(temp)
                self.worker = build.Worker(self.output)
                self.old_worker_environment = dict(self.worker.env)
                self.report = {}
                self.calls = []
                self.responses = [dict(), dict(), dict(probe=identity)]
                with self.assertRaises(ValueError):
                    build.ensure_native_python(self.worker, self.report)
                self.assert_environment_unchanged()
                self.assertEqual(self.report["native_python"]["status"], "failed")

    def cross_files(self):
        cross = self.output / "cross"
        cross.mkdir()
        for filename in ("cross-ios.meson", "cross-darwin.meson"):
            (cross / filename).write_text("[binaries]\npython = " + repr([str(self.python)]) + "\n")
        return cross

    def test_both_generated_cross_files_bind_and_hash_verified_interpreter(self):
        self.ensure()
        cross = self.cross_files()
        build.verify_native_python_cross_files(self.report, cross)
        receipt = self.report["native_python"]
        self.assertEqual(receipt["status"], "ready")
        self.assertEqual(set(receipt["cross_files"]), {"cross-ios.meson", "cross-darwin.meson"})
        for filename, identity in receipt["cross_files"].items():
            self.assertEqual(identity["python"], str(self.python))
            self.assertEqual(identity["sha256"], hashlib.sha256((cross / filename).read_bytes()).hexdigest())
        json.dumps(self.report)

    def test_wrong_relative_or_malformed_cross_binding_fails_closed(self):
        self.ensure()
        cross = self.cross_files()
        invalid = (repr(["/system/python3"]), repr([os.path.relpath(self.python)]),
                   repr(str(self.python)), repr([str(self.python), "-I"]), repr([123]))
        for expression in invalid:
            with self.subTest(expression=expression):
                (cross / "cross-darwin.meson").write_text("[binaries]\npython = " + expression + "\n")
                with self.assertRaises(ValueError):
                    build.verify_native_python_cross_files(self.report, cross)
                self.assertEqual(self.report["native_python"]["status"], "failed")

    def test_cross_binding_is_not_resolved_to_underlying_system_python(self):
        self.ensure()
        self.python.unlink()
        self.python.symlink_to(sys.executable)
        cross = self.cross_files()
        (cross / "cross-darwin.meson").write_text("[binaries]\npython = " + repr([sys.executable]) + "\n")
        with self.assertRaises(ValueError):
            build.verify_native_python_cross_files(self.report, cross)
        self.assertEqual(self.report["native_python"]["status"], "failed")

    def test_missing_cross_file_or_python_binding_stays_failed(self):
        self.ensure()
        cross = self.cross_files()
        (cross / "cross-darwin.meson").unlink()
        with self.assertRaises(FileNotFoundError):
            build.verify_native_python_cross_files(self.report, cross)
        self.assertEqual(self.report["native_python"]["status"], "failed")
        (cross / "cross-darwin.meson").write_text("[binaries]\nc = 'clang'\n")
        with self.assertRaises(KeyError):
            build.verify_native_python_cross_files(self.report, cross)
        self.assertEqual(self.report["native_python"]["status"], "failed")

    def test_cross_binding_expression_is_never_executed(self):
        self.ensure()
        cross = self.cross_files()
        marker = self.output / "must-not-exist"
        expression = "__import__('pathlib').Path(" + repr(str(marker)) + ").write_text('unsafe')"
        (cross / "cross-darwin.meson").write_text("[binaries]\npython = " + expression + "\n")
        with self.assertRaises(ValueError):
            build.verify_native_python_cross_files(self.report, cross)
        self.assertFalse(marker.exists())
        self.assertEqual(self.report["native_python"]["status"], "failed")

    def test_every_process_retains_logs_and_aggregate_timeout(self):
        self.worker.started = time.monotonic() - (build.NATIVE_BUILD_BUDGET_SECONDS - 100)
        self.ensure()
        self.assertEqual([step["exit_code"] for step in self.worker.steps], [0, 0, 0])
        for name, call in zip(("python-venv", "python-install", "python-probe"), self.calls):
            self.assertTrue((self.output / (name + ".log")).is_file())
            self.assertGreater(call["wait_timeouts"][0], 0)
            self.assertLessEqual(call["wait_timeouts"][0], 100)

    def test_install_timeout_kills_process_group_and_does_not_probe_or_retry(self):
        self.responses = [dict(), dict(timeout=True)]
        with mock.patch.object(build.os, "killpg") as kill, self.assertRaises(subprocess.TimeoutExpired):
            build.ensure_native_python(self.worker, self.report)
        kill.assert_called_once_with(123456789, signal.SIGKILL)
        self.assertEqual(len(self.calls), 2)
        self.assert_environment_unchanged()

    def test_bootstrap_precedes_native_base_that_generates_cross_python(self):
        tree = ast.parse(Path(build.__file__).read_text())
        main = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main")
        helpers = [node for node in ast.walk(main) if isinstance(node, ast.Call)
                   and isinstance(node.func, ast.Name) and node.func.id == "ensure_native_python"]
        native_base = [node for node in ast.walk(main) if isinstance(node, ast.Call)
                       and isinstance(node.func, ast.Attribute) and node.func.attr == "run" and node.args
                       and isinstance(node.args[0], ast.Constant) and node.args[0].value == "native-base"]
        self.assertEqual(len(helpers), 1)
        self.assertEqual(len(native_base), 1)
        self.assertLess(helpers[0].lineno, native_base[0].lineno)
        cross_check = [node for node in ast.walk(main) if isinstance(node, ast.Call)
                       and isinstance(node.func, ast.Name) and node.func.id == "verify_native_python_cross_files"]
        gpu = [node for node in ast.walk(main) if isinstance(node, ast.Call)
               and isinstance(node.func, ast.Attribute) and node.func.attr == "run" and node.args
               and isinstance(node.args[0], ast.Constant) and node.args[0].value == "native-gpu"]
        self.assertEqual(len(cross_check), 1)
        self.assertEqual(len(gpu), 1)
        self.assertLess(native_base[0].lineno, cross_check[0].lineno)
        self.assertLess(cross_check[0].lineno, gpu[0].lineno)


if __name__ == "__main__":
    unittest.main()
