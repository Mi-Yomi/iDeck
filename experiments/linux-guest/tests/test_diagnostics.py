"""Startup instrumentation wiring; actual IO/relaunch checks are Swift helpers.

These Python tests deliberately do not emulate durability, Foundation, or QEMU.
"""
import ast
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EXPERIMENT = ROOT / "experiments/linux-guest"
sys.path.insert(0, str(EXPERIMENT / "tools"))
from test_terminal import swift_block
import stage_husk
import typecheck_source


class StartupDiagnosticsWiring(unittest.TestCase):
    def test_native_boundaries_are_recorded_directly_before_async_publication(self):
        session = (EXPERIMENT / "ios/LinuxTerminalSession.swift").read_text()
        thread = swift_block(session, "let thread = Thread")
        ordered = ['guard self.prepareNativeEntry(serial: serial, control: control)', 'qemu_init(', 'checkpoint(.qemuInitReturned)',
                   'checkpoint(.nativeJITCheckBegin)', 'husk_ios_jit_is_available()',
                   'checkpoint(.nativeJITCheckReturned)', 'checkpoint(.displayInitBegin)',
                   'husk_display_init()', 'checkpoint(.displayInitReturned)',
                   'checkpoint(.mainLoopBegin)', 'qemu_main_loop()', 'checkpoint(.mainLoopReturned)']
        positions = [thread.index(token) for token in ordered]
        self.assertEqual(positions, sorted(positions))
        entry = swift_block(session, "private func prepareNativeEntry(")
        self.assertIn("try diagnostic.record(.qemuInitBegin)", entry)
        self.assertLess(entry.index("try diagnostic.record(.qemuInitBegin)"), entry.index("handToQEMU()"))
        self.assertIn("return false", entry)
        self.assertIn("self.disk?.closeUnused()", entry)
        checkpoint = swift_block(session, "private func checkpoint(")
        self.assertIn("try diagnostic.record(stage", checkpoint)
        self.assertNotIn("queue.async", checkpoint)
        start = swift_block(session, "func start()")
        self.assertLess(start.index("diagnostic.record(.startRequested)"), start.index("JITBootstrap.ready"))
        claim = swift_block(session, "func claimJIT()")
        self.assertLess(claim.index("journal.record(.jitClaimBegin)"), claim.index("JITBootstrap.ready"))

    def test_recovery_export_needs_no_vm_jit_or_new_attempt(self):
        session = (EXPERIMENT / "ios/LinuxTerminalSession.swift").read_text()
        recovery = swift_block(session, "func recoverDiagnostics()")
        for forbidden in ("JITBootstrap", "qemu_init", "openDisk", ".begin(", "worker.start"):
            self.assertNotIn(forbidden, recovery)
        view = (EXPERIMENT / "ios/LinuxTerminalView.swift").read_text()
        self.assertIn('.onAppear { session.recoverDiagnostics() }', view)
        self.assertNotIn('.onAppear { claimJIT()', view)
        self.assertIn('Menu("Startup diagnostics (.md)")', view)
        self.assertIn('shareItems = [file]', view)
        chooser = (EXPERIMENT / "ios/LinuxProbeView.swift").read_text()
        self.assertIn('.onAppear { LinuxTerminalSession.shared.recoverDiagnostics() }', chooser)

    def test_real_io_helper_has_no_signal_runtime_or_secret_collection(self):
        helper = (EXPERIMENT / "ios/LinuxTerminalDiagnostics.swift").read_text()
        for forbidden in ("signal(", "sigaction(", "JITBootstrap", "qemu_init(", "URLSession",
                          "localizedDescription", "pairingRecord", 'report["argv"]'):
            self.assertNotIn(forbidden, helper)
        record = swift_block(helper, "func record(")
        self.assertLess(record.index("lock.lock()"), record.index("store.writeAll"))
        write = swift_block(helper, "private func writeAll(")
        self.assertIn("synchronize(fd) == 0", write)
        self.assertIn("O_NOFOLLOW", helper)
        self.assertIn("state.st_nlink == 1", helper)
        self.assertIn("lines.dropLast()", helper)
        markdown = swift_block(helper, "func markdown(")
        self.assertNotIn("Data(contentsOf", markdown)
        self.assertNotIn("read(", markdown)
        self.assertIn("Cause UNKNOWN", markdown)
        self.assertIn("Jetsam/SIGKILL", markdown)

    def test_new_runtime_helper_is_exactly_staged_and_actual_swift_tests_are_wired(self):
        lock = stage_husk.load_overlay()
        name = "ios/LinuxTerminalDiagnostics.swift"
        self.assertEqual(lock["copies"][name], "src/app/Husk/LinuxTerminalDiagnostics.swift")
        self.assertEqual(hashlib.sha256((EXPERIMENT / name).read_bytes()).hexdigest(), lock["inputs"][name])
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "source"
            typecheck_source.restore(out)
            typecheck_source.overlay(out)
            self.assertEqual((out / lock["copies"][name]).read_bytes(), (EXPERIMENT / name).read_bytes())
        tree = ast.parse((ROOT / "ci/check_linux_guest_profile.py").read_text())
        calls = {node.args[0].value: node for node in ast.walk(tree)
                 if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "run"
                 and node.args and isinstance(node.args[0], ast.Constant)}
        mac_names = {node.id for node in ast.walk(calls["mac-compile"].args[1]) if isinstance(node, ast.Name)}
        ios_names = {node.id for node in ast.walk(calls["ios-typecheck"].args[1]) if isinstance(node, ast.Name)}
        self.assertTrue({"diagnostics", "diagnostics_tests"}.issubset(mac_names))
        self.assertIn("diagnostics", ios_names)
        main = (EXPERIMENT / "ios/tests/main.swift").read_text()
        self.assertIn("try runTerminalDiagnosticsChecks()", main)
        self.assertIn("try runDiagnosticInterruptionChild(", main)


if __name__ == "__main__":
    unittest.main()
