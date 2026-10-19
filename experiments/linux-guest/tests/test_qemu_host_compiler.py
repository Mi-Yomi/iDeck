"""Mock Apple subprocesses to verify a distinct, genuinely executable host gate."""
import ast
import contextlib
import hashlib
import io
import os
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

PATCH = ROOT / "experiments/linux-guest/ipa/0003-qemu-macos-build-compiler.patch"
# Synthetic recipe slice with the pinned Husk stage_qemu context. It is not a
# substitute for the separate full pinned-source patch-application control.
RECIPE = r'''#!/bin/sh
set -eu
stage_qemu() {
    ( cd "$dir/_husk_build" \
      && ../configure \
            --prefix="$PREFIX" \
            --cross-prefix="" \
            --target-list=aarch64-softmmu \
            --enable-shared-lib \
            --extra-cflags="$CFLAGS" --extra-ldflags="$LDFLAGS"
    )
}
'''



class QemuHostCompilerTests(unittest.TestCase):
    marker = "IDECK_QEMU_HOST_COMPILER_OK"
    executable = b"mock compiler product: no actual Apple compilation\n"
    triple = "arm64-apple-darwin25.0.0"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name)
        fixture_root = self.output
        if sys.platform == "linux" and " " in str(fixture_root):
            # Model valid (space-free) Apple SDK paths even when Linux TMPDIR
            # lives on a Windows volume named "Freddy Fazbear". The actual
            # files remain in that caller-selected directory; no guard changes.
            descriptor = os.open(fixture_root, os.O_RDONLY | os.O_DIRECTORY)
            self.addCleanup(os.close, descriptor)
            fixture_root = Path(f"/proc/{os.getpid()}/fd/{descriptor}")
        self.clang = fixture_root / "Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin/clang"
        self.clang.parent.mkdir(parents=True)
        self.clang.write_text("mock compiler path, never executed\n")
        self.sdk = fixture_root / "Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX27.sdk"
        self.sdk.mkdir(parents=True)
        self.worker = build.Worker(self.output)
        self.worker.env.update(SDKROOT="/SDKs/iPhoneOS27.sdk", CC="clang -target arm64-apple-ios15.5",
                               CFLAGS="-target arm64-apple-ios15.5", LDFLAGS="-isysroot /SDKs/iPhoneOS27.sdk")
        self.original_environment = dict(os.environ)
        self.original_worker_environment = dict(self.worker.env)
        self.calls = []
        self.responses = []
        self.report = {}
        patcher = mock.patch.object(build.subprocess, "Popen", side_effect=self.popen)
        patcher.start()
        self.addCleanup(patcher.stop)
        redirect = contextlib.redirect_stdout(io.StringIO())
        redirect.__enter__()
        self.addCleanup(redirect.__exit__, None, None, None)

    def popen(self, command, **kwargs):
        self.assertTrue(self.responses, "Unexpected extra command: " + repr(command))
        response = self.responses.pop(0)
        call = dict(command=command, environment=dict(kwargs["env"]), **kwargs)
        self.calls.append(call)
        if "--find" in command:
            default_output = str(self.clang)
        elif "--show-sdk-path" in command:
            default_output = str(self.sdk)
        elif "-dumpmachine" in command:
            default_output = self.triple
        elif "-o" in command:
            default_output = ""
            if response.get("code", 0) == 0 and response.get("product", True):
                Path(command[command.index("-o") + 1]).write_bytes(response.get("bytes", self.executable))
        else:
            default_output = self.marker
        kwargs["stdout"].write((response.get("log", default_output) + "\n").encode())
        process = mock.Mock(pid=123456789)

        def wait(timeout=None):
            call.setdefault("wait_timeouts", []).append(timeout)
            if response.get("timeout") and timeout is not None:
                raise subprocess.TimeoutExpired(command, timeout)
            return response.get("code", 0)

        process.wait.side_effect = wait
        return process

    def ensure(self, *responses):
        self.responses = list(responses or (dict(), dict(), dict(), dict(), dict()))
        build.ensure_qemu_build_compiler(self.worker, self.report)
        self.assertEqual(self.responses, [])

    def assert_not_published(self):
        self.assertEqual(self.worker.env, self.original_worker_environment)
        self.assertEqual(dict(os.environ), self.original_environment)
        self.assertEqual(self.report["qemu_host_compiler"]["status"], "failed")

    def test_real_host_compile_link_then_execution_gate_before_publication(self):
        self.ensure()
        commands = [call["command"] for call in self.calls]
        self.assertEqual(commands[0], ["xcrun", "--sdk", "macosx", "--find", "clang"])
        self.assertEqual(commands[1], ["xcrun", "--sdk", "macosx", "--show-sdk-path"])
        self.assertEqual(commands[2], [str(self.clang), "-isysroot", str(self.sdk), "-dumpmachine"])
        compile_command = commands[3]
        self.assertEqual(compile_command[:5], [str(self.clang), "-target", self.triple, "-isysroot", str(self.sdk)])
        self.assertNotIn("-c", compile_command, "Host probe must link an executable")
        source = Path(compile_command[5])
        self.assertIn("TargetConditionals.h", source.read_text())
        self.assertIn("TARGET_OS_OSX", source.read_text())
        self.assertIn("TARGET_OS_IPHONE", source.read_text())
        self.assertIn(self.marker, source.read_text())
        binary = compile_command[compile_command.index("-o") + 1]
        self.assertEqual(commands[4], [binary], "Execute the new compiler product, not a stand-in")
        receipt = self.report["qemu_host_compiler"]
        self.assertEqual(receipt["status"], "ready")
        self.assertEqual(receipt["probe"]["size"], len(self.executable))
        self.assertEqual(receipt["probe"]["sha256"], hashlib.sha256(self.executable).hexdigest())
        self.assertEqual(receipt["probe"]["stdout"], self.marker)
        self.assertEqual(self.worker.env["IDECK_QEMU_HOST_CC"], " ".join(compile_command[:5]))

    def test_ios_target_environment_remains_unchanged_through_host_probe(self):
        self.ensure()
        self.assertEqual(dict(os.environ), self.original_environment)
        expected = dict(self.worker.env)
        expected.pop("IDECK_QEMU_HOST_CC")
        self.assertEqual(expected, self.original_worker_environment)
        for call in self.calls:
            self.assertEqual(call["environment"], self.original_worker_environment)
            self.assertNotIn("shell", call)
            self.assertTrue(call["start_new_session"])

    def test_discovery_failure_stops_without_compiler_publication(self):
        for count in (0, 1, 2):
            with self.subTest(stage=count):
                self.calls = []
                self.responses = [dict() for _ in range(count)] + [dict(code=1, log="real discovery failure")]
                with self.assertRaises(RuntimeError):
                    build.ensure_qemu_build_compiler(self.worker, self.report)
                self.assertEqual(len(self.calls), count + 1)
                self.assert_not_published()
                # A new attempt gets a fresh output directory; the failed helper
                # must not be made idempotent by reusing any partial probe.
                probe_dir = self.output / "qemu-host-compiler"
                if probe_dir.exists():
                    for child in probe_dir.iterdir():
                        child.unlink()
                    probe_dir.rmdir()

    def test_compile_failure_is_fatal_and_does_not_execute(self):
        self.responses = [dict(), dict(), dict(), dict(code=1, log="host linker failed")]
        with self.assertRaises(RuntimeError):
            build.ensure_qemu_build_compiler(self.worker, self.report)
        self.assertEqual(len(self.calls), 4)
        self.assert_not_published()
        self.assertEqual(self.worker.steps[-1]["exit_code"], 1)

    def test_nonzero_execution_fails_even_after_successful_compile_and_link(self):
        self.responses = [dict(), dict(), dict(), dict(), dict(code=1, log="not runnable")]
        with self.assertRaises(RuntimeError):
            build.ensure_qemu_build_compiler(self.worker, self.report)
        self.assertEqual(len(self.calls), 5)
        self.assert_not_published()

    def test_wrong_execution_marker_never_publishes_host_compiler(self):
        self.responses = [dict(), dict(), dict(), dict(), dict(log="wrong result")]
        with self.assertRaises(ValueError):
            build.ensure_qemu_build_compiler(self.worker, self.report)
        self.assert_not_published()

    def test_missing_or_empty_executable_is_not_a_passing_compile(self):
        for product in (dict(product=False), dict(bytes=b"")):
            with self.subTest(product=product), tempfile.TemporaryDirectory() as temp:
                self.worker = build.Worker(Path(temp))
                self.original_worker_environment = dict(self.worker.env)
                self.calls = []
                self.responses = [dict(), dict(), dict(), product]
                with self.assertRaises(ValueError):
                    build.ensure_qemu_build_compiler(self.worker, self.report)
                self.assertEqual(len(self.calls), 4)
                self.assert_not_published()

    def test_ios_or_other_unreviewed_triples_are_rejected(self):
        for triple in ("arm64-apple-ios15.5", "x86_64-unknown-linux-gnu", "arm64-apple-darwin25;false"):
            with self.subTest(triple=triple), tempfile.TemporaryDirectory() as temp:
                self.worker = build.Worker(Path(temp))
                self.original_worker_environment = dict(self.worker.env)
                self.calls = []
                self.responses = [dict(), dict(), dict(log=triple)]
                with self.assertRaises(ValueError):
                    build.ensure_qemu_build_compiler(self.worker, self.report)
                self.assertEqual(len(self.calls), 3)
                self.assert_not_published()

    def test_unsafe_or_relative_discovery_paths_are_rejected(self):
        unsafe_clang = self.output / "toolchain with spaces/clang"
        unsafe_clang.parent.mkdir()
        unsafe_clang.write_text("mock compiler path")
        quoted_clang = self.output / "quoted'clang"
        quoted_clang.write_text("mock compiler path")
        unsafe_sdk = self.output / "SDK with spaces/MacOSX27.sdk"
        unsafe_sdk.mkdir(parents=True)
        ios_sdk = self.output / "iPhoneOS27.sdk"
        ios_sdk.mkdir()
        for stage, path in ((0, "relative/clang"), (0, str(unsafe_clang)), (0, str(quoted_clang)),
                            (1, str(ios_sdk)), (1, str(unsafe_sdk)), (1, "relative/MacOSX27.sdk")):
            with self.subTest(stage=stage, path=path), tempfile.TemporaryDirectory() as temp:
                self.worker = build.Worker(Path(temp))
                self.original_worker_environment = dict(self.worker.env)
                self.calls = []
                self.responses = [dict(), dict()]
                self.responses[stage] = dict(log=path)
                with self.assertRaises(ValueError):
                    build.ensure_qemu_build_compiler(self.worker, self.report)
                self.assertEqual(len(self.calls), 2)
                self.assert_not_published()

    def test_host_probe_uses_existing_aggregate_budget_and_retains_logs(self):
        self.worker.started = time.monotonic() - (build.NATIVE_BUILD_BUDGET_SECONDS - 100)
        self.ensure()
        names = ("qemu-host-clang", "qemu-host-sdk", "qemu-host-triple", "qemu-host-compile", "qemu-host-execute")
        for name, call in zip(names, self.calls):
            self.assertTrue((self.output / (name + ".log")).is_file())
            self.assertGreater(call["wait_timeouts"][0], 0)
            self.assertLessEqual(call["wait_timeouts"][0], 100)

    def test_probe_timeout_kills_process_group_without_publishing(self):
        self.responses = [dict(), dict(), dict(), dict(timeout=True)]
        with mock.patch.object(build.os, "killpg") as kill, self.assertRaises(subprocess.TimeoutExpired):
            build.ensure_qemu_build_compiler(self.worker, self.report)
        kill.assert_called_once_with(123456789, signal.SIGKILL)
        self.assert_not_published()

    def test_host_compiler_gate_and_recipe_patch_precede_qemu(self):
        tree = ast.parse(Path(build.__file__).read_text())
        main = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main")
        helper = [node for node in ast.walk(main) if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Name) and node.func.id == "ensure_qemu_build_compiler"]
        calls = {node.args[0].value: node for node in ast.walk(main)
                 if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "run"
                 and node.args and isinstance(node.args[0], ast.Constant)}
        self.assertEqual(len(helper), 1)
        ordered = ("native-gpu", "qemu-host-patch-check", "qemu-host-patch-apply",
                   "qemu-cross-patch-check", "qemu-cross-patch-apply", "native-qemu")
        self.assertEqual([calls[name].lineno for name in ordered], sorted(calls[name].lineno for name in ordered))
        self.assertLess(calls["native-gpu"].lineno, helper[0].lineno)
        self.assertLess(helper[0].lineno, calls["qemu-host-patch-check"].lineno)
        checked = calls["qemu-host-patch-check"].args[1]
        applied = calls["qemu-host-patch-apply"].args[1]
        self.assertIn("--check", [node.value for node in checked.elts if isinstance(node, ast.Constant)])
        self.assertNotIn("--check", [node.value for node in applied.elts if isinstance(node, ast.Constant)])


class HostCompilerRecipePatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        initialized = subprocess.run(["git", "init", "--quiet", str(self.root)], capture_output=True, text=True)
        self.assertEqual(initialized.returncode, 0, initialized.stderr)
        self.recipe = self.root / "scripts/build_ios.sh"
        self.recipe.parent.mkdir()
        self.recipe.write_text(RECIPE)

    def apply(self, check=False):
        return subprocess.run(["git", "apply", *(["--check"] if check else []), str(PATCH)],
                              cwd=self.root, capture_output=True, text=True)

    def test_recipe_adds_only_required_host_cc_leaving_ios_flags_intact(self):
        checked = self.apply(check=True)
        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assertEqual(self.recipe.read_text(), RECIPE)
        applied = self.apply()
        self.assertEqual(applied.returncode, 0, applied.stderr)
        updated = self.recipe.read_text()
        added_lines = [line for line in updated.splitlines(keepends=True) if "--host-cc=" in line]
        self.assertEqual(len(added_lines), 1)
        self.assertIn("${IDECK_QEMU_HOST_CC:?", added_lines[0])
        self.assertEqual(updated.replace(added_lines[0], "", 1), RECIPE)
        self.assertIn('--cross-prefix=""', updated)
        self.assertIn('--target-list=aarch64-softmmu', updated)
        self.assertIn('--extra-cflags="$CFLAGS" --extra-ldflags="$LDFLAGS"', updated)

    def test_recipe_patch_rejects_changed_context_and_preserves_source(self):
        changed = RECIPE.replace('--cross-prefix=""', '--cross-prefix="unreviewed"')
        self.recipe.write_text(changed)
        checked = self.apply(check=True)
        self.assertNotEqual(checked.returncode, 0)
        self.assertEqual(self.recipe.read_text(), changed)

    def test_recipe_patch_does_not_accept_already_patched_sources(self):
        first = self.apply()
        self.assertEqual(first.returncode, 0, first.stderr)
        original = self.recipe.read_bytes()
        checked = self.apply(check=True)
        self.assertNotEqual(checked.returncode, 0)
        self.assertEqual(self.recipe.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
