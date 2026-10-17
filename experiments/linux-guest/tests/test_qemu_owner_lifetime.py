"""Wiring guards plus an opt-in OFFLINE native archive-pinned RCU regression.

Apple/Foundation execution is a separate mandatory gate, never a Python PASS.
"""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from check_qemu_rcu_lifetime import check
from test_terminal import swift_block


class QEMUOwnerLifetime(unittest.TestCase):
    def test_all_linux_native_workers_retain_same_thread_after_loop_return(self):
        for name in ("LinuxTerminalSession.swift", "LinuxProbeSession.swift"):
            source = (ROOT / "ios" / name).read_text()
            thread = swift_block(source, "let thread = Thread")
            loop = thread.index("qemu_main_loop()")
            retention = thread.index("LinuxQEMUThreadLifetime.retainCurrentThread")
            self.assertGreater(retention, loop)
            self.assertNotRegex(thread[loop:], r"\bThread\s*\{")
            retained = swift_block(thread, "LinuxQEMUThreadLifetime.retainCurrentThread")
            self.assertIn('report["qemu_owner_thread_retained_until_process_exit"] = true', retained)
        lifecycle = (ROOT / "ios/LinuxConsoleLifecycle.swift").read_text()
        helper = swift_block(lifecycle, "static func retainCurrentThread(")
        self.assertIn("static func retainCurrentThread(_ retained: () -> Void) -> Never", lifecycle)
        self.assertLess(helper.index("condition.lock()"), helper.index("retained()"))
        self.assertIn("while true { condition.wait() }", helper)
        for forbidden in ("sleep", "isCancelled", "qemu_cleanup", "rcu_unregister_thread", "return", "bql_unlock"):
            self.assertNotIn(forbidden, helper)

    def test_shutdown_tail_has_durable_boundaries_after_narrow_clean_receipt(self):
        source = (ROOT / "ios/LinuxTerminalSession.swift").read_text()
        finalize = swift_block(source, "private func finalizeIfClean()")
        tokens = ["checkpoint(.cleanStopped)", "checkpoint(.consoleLogCloseBegin)",
                  "logHandle?.close()", "checkpoint(.consoleLogCloseReturned)",
                  "checkpoint(.consolePeersCloseBegin)", "serial?.closePeer(); control?.closePeer()",
                  "checkpoint(.consolePeersCloseReturned)", 'report["console_shutdown_tail_returned"] = true']
        positions = [finalize.index(t) for t in tokens]
        self.assertEqual(positions, sorted(positions))
        snapshot = (ROOT / "ios/LinuxTerminalDiagnostics.swift").read_text()
        self.assertIn("tail == Array(Self.shutdownTail.prefix(tail.count))", snapshot)
        self.assertIn("sync < clean", snapshot)
        report = (ROOT / "ios/LinuxProbeReport.swift").read_text()
        self.assertIn('report["console_shutdown_tail_returned"]', report)

    def test_production_foundation_wait_and_native_tls_are_mandatory_in_apple_gate(self):
        source = (ROOT / "ios/tests/ConsoleLifecycleChecks.swift").read_text()
        self.assertIn("pthread_key_create(&key", source)
        self.assertIn("pthread_setspecific(tlsKey", source)
        self.assertIn("LinuxQEMUThreadLifetime.retainCurrentThread { entered.signal() }", source)
        self.assertIn("try runQEMUOwnerLifetimeChecks()", source)
        self.assertIn('("exit-control", 42), ("retain", 0)', source)
        gate = (ROOT.parents[1] / "ci/check_linux_guest_profile.py").read_text()
        self.assertIn('"LINUX_QEMU_OWNER_LIFETIME_PASS"', gate)
        main = (ROOT / "ios/tests/main.swift").read_text()
        self.assertIn("runQEMUOwnerLifetimeChild(retain:", main)

    @unittest.skipUnless(os.environ.get("IDECK_QEMU_RCU_ARCHIVE") and shutil.which("cc"),
                         "explicit existing pinned QEMU SOURCE archive and C compiler required")
    def test_native_pinned_registry_thread_exit_and_retention(self):
        with tempfile.TemporaryDirectory() as directory:
            result = check(Path(os.environ["IDECK_QEMU_RCU_ARCHIVE"]), Path(directory) / "native")
        self.assertEqual(result["status"], "PASS")
        self.assertEqual([r["exit_code"] for r in result["results"]], [0, 0, 0])
        self.assertIn("STALE_REGISTRY_AFTER_REAL_THREAD_EXIT", result["results"][0]["output"])
        self.assertIn("RETAINED_TLS_REGISTRY_PASS", result["results"][2]["output"])


if __name__ == "__main__":
    unittest.main()
