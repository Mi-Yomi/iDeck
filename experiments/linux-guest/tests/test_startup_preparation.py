"""Native wiring guards. Production lock/race/journal/renderer execution is
mandatory in the Apple Swift gate; these checks do not emulate that execution.
"""
import unittest
from pathlib import Path
from test_terminal import swift_block

ROOT = Path(__file__).resolve().parents[1]


class StartupPreparationWiring(unittest.TestCase):
    def test_cancel_and_native_entry_compete_on_one_production_lock(self):
        source = (ROOT / 'ios/LinuxConsoleLifecycle.swift').read_text()
        helper = swift_block(source, 'final class LinuxStartupPreparation')
        self.assertIn('private let lock = NSLock()', helper)
        for method in ('func requestCancellation()', 'func enterNative()', 'func advance(', 'func finish()'):
            body = swift_block(helper, method)
            self.assertIn('lock.lock(); defer { lock.unlock() }', body)
        enter = swift_block(helper, 'func enterNative()')
        self.assertIn('guard state == .preparing else { return false }', enter)
        self.assertIn('state = .entered', enter)
        self.assertIn('if state != .entered', swift_block(helper, 'func finish()'))
        self.assertNotIn('state = .preparing', helper)
        for forbidden in ('qemu_', 'closeUnused', 'Thread.cancel', 'Darwin.kill', 'JITBootstrap', 'removeItem'):
            self.assertNotIn(forbidden, helper)

    def test_gate_is_after_existing_checks_and_before_any_native_handoff(self):
        source = (ROOT / 'ios/LinuxTerminalSession.swift').read_text()
        entry = swift_block(source, 'private func prepareNativeEntry(')
        checks = ['try disk.validateOwnership()', 'try diagnostic.record(.qemuInitBegin)',
                  'guard preparation.enterNative()', 'self.enteredQEMU = true', 'serial.handToQEMU()']
        self.assertEqual([entry.index(s) for s in checks], sorted(entry.index(s) for s in checks))
        self.assertIn('Cancelled.beforeNativeEntry', entry)
        self.assertIn('serial.closeUnused(); control.closeUnused()', entry)
        worker_start = swift_block(source[source.index('private final class LinuxTerminalWorker'):], 'func start()')
        self.assertIn('guard self.prepareNativeEntry(serial: serial, control: control) else { return }', worker_start)
        self.assertLess(worker_start.index('guard self.prepareNativeEntry('), worker_start.index('qemu_init('))
        self.assertIn('if !self.enteredQEMU { self.disk?.closeUnused() }', worker_start)
        self.assertIn('if let recovery = self.recovery, let gui { try recovery.markRunning(', worker_start)
        self.assertIn('LinuxQEMUThreadLifetime.retainCurrentThread', worker_start)

    def test_cancellation_never_stops_live_vm_or_reopens_one_use_attempt(self):
        source = (ROOT / 'ios/LinuxTerminalSession.swift').read_text()
        cancel = swift_block(source, 'func cancelPreparation()')
        self.assertIn('worker.requestPreparationCancellation()', cancel)
        self.assertIn('diagnosticJournal?.record(.preparationCancelRequested)', cancel)
        request = swift_block(source, 'func requestPreparationCancellation()')
        self.assertIn('guard preparation.requestCancellation() else { return false }', request)
        self.assertIn('queue.async', request)
        for body in (cancel, request):
            for forbidden in ('stop()', 'closeUnused', 'attempted = false', 'qemu_', 'Thread.cancel', 'removeItem'):
                self.assertNotIn(forbidden, body)
        start = swift_block(source, 'func start()')
        self.assertIn('guard !attempted else { return }', start)
        self.assertEqual(source.count('attempted = false'), 1)  # initialization only
        self.assertEqual(source.count('"preparation_cancelled_before_qemu"] = true'), 2)
        self.assertNotIn('cleanStopped = true', cancel)

    def test_progress_covers_slow_phases_and_route_background_requests_cancel(self):
        source = (ROOT / 'ios/LinuxTerminalSession.swift').read_text()
        for phase in ('assets', 'disk', 'importingSeed', 'recoveryCopies', 'arguments', 'report', 'nativeEntry'):
            self.assertIn(f'preparationCheckpoint(.{phase})', source)
        progress = swift_block(source, 'private func preparationCheckpoint(')
        self.assertIn('try preparation.advance(phase)', progress)
        self.assertIn('if state.inProgress', progress)
        for name, scene in [('LinuxDesktopView.swift', 'phase'), ('LinuxTerminalView.swift', 'scenePhase')]:
            view = (ROOT / 'ios' / name).read_text()
            self.assertIn('preparation.inProgress', view)
            self.assertIn('ProgressView(preparation.message)', view)
            self.assertIn('.disabled(!preparation.canCancel)', view)
            if '.onDisappear' in view:
                self.assertNotIn('session.cancelPreparation()', swift_block(view, '.onDisappear'))
            change = swift_block(view, f'.onChange(of: {scene})')
            self.assertIn('.background { session.cancelPreparation() }', change)
            self.assertNotIn('session.stop()', change)
        root = (ROOT / 'ios/LinuxProbeView.swift').read_text()
        self.assertIn('for session in [terminal, debian, desktop, steam] { session.cancelPreparation() }', root)

    def test_actual_swift_races_and_cancelled_journal_are_mandatory(self):
        checks = (ROOT / 'ios/tests/ConsoleLifecycleChecks.swift').read_text()
        self.assertIn('try runStartupPreparationChecks()', swift_block(checks, 'func runConsoleLifecycleChecks()'))
        self.assertIn('DispatchQueue.concurrentPerform(iterations: 2)', checks)
        self.assertIn('precondition(entered != cancelled', checks)
        self.assertIn('!preparation.requestCancellation()', checks)
        ci = (ROOT.parents[1] / 'ci/check_linux_guest_profile.py').read_text()
        self.assertIn('"LINUX_STARTUP_PREPARATION_PASS"', ci)
        diagnostics = (ROOT / 'ios/tests/DiagnosticsChecks.swift').read_text()
        self.assertIn('try cancelled.record(.preparationCancelled)', diagnostics)
        self.assertIn('try cancelled.record(.preparationCancelRequested)', diagnostics)
        self.assertIn('contradictory native-entry evidence', diagnostics)

    def test_preparation_failure_latches_before_cleanup_and_all_late_callbacks(self):
        source = (ROOT / 'ios/LinuxTerminalSession.swift').read_text()
        worker = source[source.index('private final class LinuxTerminalWorker'):]
        start = swift_block(worker, 'func start()')
        # The failure may occur after a watchdog has already been armed.
        self.assertLess(start.index('self.scheduleStartupTimeout()'), start.index('try recovery.markRunning('))
        catch = start[start.index('} catch {\n                // A timer'):]
        self.assertLess(catch.index('self.startupAborted = true'), catch.index('self.preparation.finish()'))
        self.assertLess(catch.index('self.startupAborted = true'), catch.index('self.serial?.closeUnused()'))
        self.assertLess(catch.index('self.startupAborted = true'), catch.index('self.persist()'))
        for name in ('private func scheduleStartupTimeout()', 'private func armRecoveryTimeout()',
                     'private func recoveryTimeout(', 'private func receiveSerial(',
                     'private func receiveControl(', 'private func channelDisconnected('):
            self.assertIn('!startupAborted' if 'Timeout' not in name else 'startupAborted', swift_block(worker, name))
        # A queued cancel note only adds the request fact; it cannot overwrite
        # failure status, restart preparation, clear dirty state or close a VM.
        request = swift_block(source, 'func requestPreparationCancellation()')
        for forbidden in ('["status"]', 'stopFailed =', 'startupAborted =', 'cleanStopped =', 'attempted ='):
            self.assertNotIn(forbidden, request)
        diagnostics = (ROOT / 'ios/tests/DiagnosticsChecks.swift').read_text()
        self.assertIn('late cancellation does not mask fsync/preparation failure', diagnostics)
        self.assertIn('original typed IO failure remains', diagnostics)

    def test_markdown_keeps_known_failures_without_arbitrary_error_text(self):
        renderer = (ROOT / 'ios/LinuxProbeReport.swift').read_text()
        checks = (ROOT / 'ios/tests/MarkdownReportChecks.swift').read_text()
        for key in ('terminal_startup_timed_out', 'terminal_stop_timed_out', 'terminal_control_channel_failed',
                    'terminal_serial_channel_failed', 'serial_log_write_failed'):
            self.assertIn(f'"{key}"', renderer)
            self.assertIn(f'"{key}"', checks)
        self.assertIn('invalidFailureValues', checks)
        self.assertIn('legacy report never invents', checks)
        self.assertNotIn('localizedDescription', renderer)
        self.assertNotIn('report.keys', renderer)


if __name__ == '__main__':
    unittest.main()
