"""Source wiring guards; real UIKit layout/share-sheet acceptance stays on device.

The Foundation regressions run the real disk validator/journal/MD renderer in
the Apple gate. These checks do not emulate a successful GUI or filesystem.
"""
import ast
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from test_terminal import swift_block


class DesktopDiagnosticsUI(unittest.TestCase):
    def test_exports_are_fixed_above_scroll_and_independent_of_vm_readiness(self):
        view = (ROOT / "ios/LinuxDesktopView.swift").read_text()
        actions = swift_block(view, "private var persistentActions:")
        controls = swift_block(view, "private var controls:")
        self.assertIn('.safeAreaInset(edge: .top, spacing: 0) { persistentActions }', view)
        self.assertIn('.ignoresSafeArea(.keyboard, edges: .bottom)', view)
        self.assertIn('Text(session.message).font(.caption).lineLimit(3)', view)
        self.assertNotIn('ShareLink', controls)
        self.assertNotIn('Share report', controls)
        for label in ('Share report', 'Diagnostics'):
            button = swift_block(actions, f'Button("{label}")')
            self.assertIn('prepareDiagnostics()', button)
            self.assertNotIn('session.ready', button)
            self.assertNotIn('disabled', button)
        # VM actions have their own guards; MD actions are outside input grids.
        self.assertEqual(actions.count('.disabled('), 2)
        self.assertIn('.disabled(!preparation.canCancel)', actions)
        self.assertIn('Button("Stop Linux") { session.stop() }.disabled(', actions)
        self.assertIn('session.attempted && !session.ready', actions)
        self.assertIn('ideck-desktop-startup-diagnostics', actions)

    def test_preboot_report_falls_back_to_current_journal_and_saved_md_is_explicit(self):
        session = (ROOT / "ios/LinuxTerminalSession.swift").read_text()
        share = swift_block(session, 'func reportForSharing()')
        self.assertIn('recoverDiagnostics()', share)
        self.assertIn('if let markdownFile', share)
        self.assertIn('diagnosticJournal?.id', share)
        self.assertIn('diagnosticAttemptIDs[$0] == id', share)
        self.assertNotIn('shareFiles', share)
        view = (ROOT / "ios/LinuxDesktopView.swift").read_text()
        diagnostics = swift_block(view, 'struct LinuxDesktopDiagnosticsView:')
        for token in ('session.diagnosticReports.enumerated()', 'ShareLink("Startup report',
                      'session.exportError', 'session.diagnosticsError',
                      'session.exportNativeDiagnostics(for: file)', '.navigationViewStyle(.stack)'):
            self.assertIn(token, diagnostics)
        self.assertNotIn('.disabled(', diagnostics)
        for forbidden in ('session.start(', 'session.stop(', 'session.claimJIT(', 'readToEnd(', 'rootfs-v1.raw'):
            self.assertNotIn(forbidden, diagnostics)

    def test_opening_reports_releases_input_and_resigns_keyboard(self):
        view = (ROOT / "ios/LinuxDesktopView.swift").read_text()
        prepare = swift_block(view, 'private func prepareDiagnostics()')
        self.assertIn('keyboard = false', prepare)
        self.assertIn('input.setFocused(false)', prepare)
        self.assertIn('UIResponder.resignFirstResponder', prepare)
        available = swift_block(view, 'private var inputAvailable:')
        for condition in ('!showDiagnostics', '!showShare', '!jit.showSetup', '!session.stopping'):
            self.assertIn(condition, available)
        for state in ('showDiagnostics', 'showShare', 'session.stopping'):
            self.assertIn(f'.onChange(of: {state})', view)

    def test_exact_metadata_is_observed_from_original_locked_read_before_refusal(self):
        source = (ROOT / 'ios/LinuxDesktopDisk.swift').read_text()
        validate = swift_block(source, 'static func validateHeader(')
        self.assertLess(validate.index('throw Invalid.checksum'), validate.index('observe?('))
        self.assertLess(validate.index('throw Invalid.features'), validate.index('observe?('))
        self.assertLess(validate.index('observe?('), validate.index('throw Invalid.needsRecovery'))
        for expression in ('incompat & 4 == 0', 'u16(0x3a) == 1', 'u32(0xe8) == 0', 'u32(0x194) == 0'):
            self.assertIn(expression, validate)
        session = (ROOT / 'ios/LinuxTerminalSession.swift').read_text()
        observe = swift_block(session, 'private func observeSuperblock(')
        for key in ('ext4_recover_bit', 'ext4_state', 'ext4_last_orphan', 'ext4_error_count'):
            self.assertIn(f'report["{key}"]', observe)
        self.assertIn('diagnostic.record(.diskInspected, ext4: state)', observe)
        for forbidden in ('open(', 'read(', 'removeItem', 'writeAll(', 'mount', 'repair('):
            self.assertNotIn(forbidden, observe)
        self.assertNotIn('after an unclean shutdown', session)
        mapper = (ROOT / 'ios/LinuxStartupFailure.swift').read_text()
        self.assertIn('error as? LinuxDesktopDisk.Invalid', mapper)
        self.assertIn('error as? LinuxTerminalProfile.Invalid', mapper)
        self.assertNotIn('localizedDescription', mapper)

    def test_new_classifier_is_locked_staged_and_actual_swift_tests_are_mandatory(self):
        lock = json.loads((ROOT / 'husk/overlay.lock.json').read_text())
        path = 'ios/LinuxStartupFailure.swift'
        self.assertEqual(lock['inputs'][path], hashlib.sha256((ROOT / path).read_bytes()).hexdigest())
        self.assertEqual(lock['copies'][path], 'src/app/Husk/LinuxStartupFailure.swift')
        ci = (ROOT.parents[1] / 'ci/check_linux_guest_profile.py').read_text()
        tree = ast.parse(ci)
        calls = {call.args[0].value: call.args[1] for call in ast.walk(tree)
                 if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == 'run'
                 and len(call.args) > 1 and isinstance(call.args[0], ast.Constant)}
        for gate in ('ios-typecheck', 'mac-compile'):
            self.assertIn('startup_failure', {node.id for node in ast.walk(calls[gate]) if isinstance(node, ast.Name)})
        for marker in ('LINUX_STARTUP_FAILURE_PASS', 'LINUX_EXT4_DIAGNOSTICS_PASS'):
            self.assertIn(f'"{marker}"', ci)


if __name__ == '__main__':
    unittest.main()
