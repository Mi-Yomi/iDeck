"""Native boundary source wiring; actual gate/journal/barrier runs in Apple CI."""
from pathlib import Path
import unittest
from test_terminal import swift_block
ROOT = Path(__file__).resolve().parents[1]

class FreshHandoff(unittest.TestCase):
    def test_blocking_io_is_before_final_sample_and_handoff_has_no_sync_io(self):
        memory = (ROOT/'ios/LinuxSteamMemory.swift').read_text()
        gate = swift_block(memory, 'static func enterAfterIO(')
        steps = ['try prepare()', 'sample()', 'try plan?.recheck(available)',
                 'guard preparation.enterNative()', 'return available']
        self.assertEqual([gate.index(s) for s in steps], sorted(gate.index(s) for s in steps))
        self.assertIn('preparation.finish()', gate)
        session = (ROOT/'ios/LinuxTerminalSession.swift').read_text()
        entry = swift_block(session, 'private func prepareNativeEntry(')
        prepare = swift_block(entry, 'prepare:')
        for required in ('disk.validateOwnership()', 'steamOfflineCache?.validateIdentity()',
                         'try self.saveReport()', 'diagnostic.record(.qemuInitBegin)'):
            self.assertIn(required, prepare)
        sample = swift_block(entry, 'sample:')
        self.assertIn('os_proc_available_memory()', sample)
        for forbidden in ('saveReport', 'persist()', 'diagnostic.record', 'queue.sync'):
            self.assertNotIn(forbidden, sample)
        handoff = entry[entry.index('self.enteredQEMU = true'):entry.index('} catch {')]
        self.assertIn('serial.handToQEMU(); control.handToQEMU()', handoff)
        self.assertIn('self.queue.async { self.persist() }', handoff)
        synchronous = handoff.replace('self.queue.async { self.persist() }', '')
        for forbidden in ('saveReport', 'persist()', 'diagnostic.record', 'queue.sync'):
            self.assertNotIn(forbidden, synchronous)

    def test_refusal_preserves_owner_dirty_bytes_and_one_use_tests_are_required(self):
        source = (ROOT/'ios/LinuxTerminalSession.swift').read_text()
        entry = swift_block(source, 'private func prepareNativeEntry(')
        self.assertIn('if !memoryFailed { self.disk?.closeUnused() }', entry)
        self.assertIn('self.startupAborted = true\n                    throw error', entry)
        self.assertEqual(source.count('attempted = false'), 1)
        self.assertNotIn('removeItem', entry)
        tests = (ROOT/'ios/tests/SteamOfflineChecks.swift').read_text()
        for required in ('inIO.wait', 'resumeIO.wait', 'budget.set(plan.required - 1)',
                         'try journal.record(.qemuInitBegin)', 'after == before',
                         'flock(contender, LOCK_EX | LOCK_NB) != 0',
                         '!preparation.enterNative()', 'LinuxTerminalDiagnostics.Problem.synchronize'):
            self.assertIn(required, tests)
        ci = (ROOT.parents[1]/'ci/check_linux_guest_profile.py').read_text()
        self.assertIn('"LINUX_STEAM_FRESH_HANDOFF_PASS"', ci)

if __name__ == '__main__': unittest.main()
