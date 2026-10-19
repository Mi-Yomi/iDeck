"""Read-only readiness/native-entry wiring regressions. Production Swift fixture
execution is mandatory in Apple CI; this is not a phone compatibility pass."""
from pathlib import Path
import unittest
from test_terminal import swift_block

ROOT=Path(__file__).resolve().parents[1]

class SteamReadiness(unittest.TestCase):
    def test_signed_apple_memory_api_uses_failable_conversion_and_typed_fixtures(self):
        profile=(ROOT/'ios/LinuxSteamProfile.swift').read_text()
        conversion=swift_block(profile,'static func availableMemoryBytes(')
        self.assertIn('static func availableMemoryBytes(_ measurement: Int) -> UInt64?',profile)
        self.assertIn('guard measurement > 0 else { return nil }',conversion)
        self.assertIn('UInt64(exactly: measurement)',conversion)
        self.assertNotIn('UInt64(measurement)',conversion)
        self.assertNotIn('truncatingIfNeeded',conversion)
        refresh=swift_block((ROOT/'ios/LinuxTerminalSession.swift').read_text(),'func refreshSteamReadiness()')
        self.assertIn('availableMemory: LinuxSteamProfile.availableMemoryBytes(available)',refresh)
        self.assertNotIn('available > 0 ? available : nil',refresh)
        fixtures=(ROOT/'ios/tests/SteamProfileChecks.swift').read_text()
        for expression in ('unknownMeasurements: [Int]', 'positiveMeasurements: [Int]', 'let converted: UInt64?', '[Int.min, -1, 0]',
                           'Int(budget) - 1, Int(budget), Int(budget) + 1, Int.max',
                           'readiness(LinuxSteamProfile.availableMemoryBytes(Int.min)).memory == .unknown'):
            self.assertIn(expression,fixtures)

    def test_snapshot_reuses_manifest_validator_and_has_no_userdata_or_native_inputs(self):
        source=(ROOT/'ios/LinuxSteamProfile.swift').read_text()
        preview=swift_block(source,'static func readiness(')
        self.assertIn('try load(from: assets)',preview)
        self.assertIn('availableMemory == nil || availableMemory == 0',preview)
        self.assertIn('LinuxSteamMemory.plan',preview)
        self.assertIn('memoryMode',preview)
        self.assertIn('memory = .unknown',preview)
        for forbidden in ('JITBootstrap','qemu_', 'provision(', 'openExisting(', 'flock(', 'systemFreeSize', 'URLSession', 'steam_root'):
            self.assertNotIn(forbidden,preview)
        # No disk path is accepted: free-space/dirty/owner checks remain in Start.
        signature=source[source.index('static func readiness('):source.index('-> Readiness {',source.index('static func readiness('))]
        self.assertNotIn('directory',signature)
        self.assertNotIn('disk',signature)

    def test_start_rechecks_before_jit_side_effects_and_never_clears_attempt(self):
        source=(ROOT/'ios/LinuxTerminalSession.swift').read_text()
        start=swift_block(source,'func start()')
        order=['guard !attempted','refreshSteamReadiness()', 'JITBootstrap.ready', 'JITBootstrap.prewarm()', 'attempted = true', 'next.start()']
        self.assertEqual([start.index(x) for x in order],sorted(start.index(x) for x in order))
        self.assertIn('preflight.canCheckAndStart',start)
        self.assertEqual(source.count('attempted = false'),1)
        refresh=swift_block(source,'func refreshSteamReadiness()')
        self.assertIn('guard isSteam, !attempted',refresh)
        self.assertIn('os_proc_available_memory()',refresh)
        for forbidden in ('JITBootstrap.', 'qemu_', 'worker', 'openExisting', 'provision(', 'attempted ='):
            self.assertNotIn(forbidden,refresh)
        worker=source[source.index('private final class LinuxTerminalWorker'):]
        self.assertIn('try LinuxSteamProfile.load(from: assets)',worker)
        self.assertIn('LinuxSteamMemory.plan(available:',worker)
        self.assertIn('plan.recheck',worker)
        self.assertIn('guard preparation.enterNative()',worker)

    def test_unknown_jit_is_not_a_preview_execution_or_compatibility_claim(self):
        source=(ROOT/'ios/LinuxSteamProfile.swift').read_text()
        self.assertIn('jitVerified.map',source)
        self.assertIn('?? .unknown',source)
        view=(ROOT/'ios/LinuxDesktopView.swift').read_text()
        self.assertIn('session.steamReadiness?.canCheckAndStart != true',view)
        self.assertIn('LSE, GUI и Steam ещё не проверены',view)
        self.assertIn('Hash ресурсов проверяется при подготовке',view)
        self.assertIn('Only first import needs 13 GiB free',view)
        # Cached preview state cannot replace the actual launch gate.
        start=swift_block((ROOT/'ios/LinuxTerminalSession.swift').read_text(),'func start()')
        self.assertIn('let ready = JITBootstrap.ready',start)
        self.assertIn('guard passed else',start)

    def test_actual_swift_faults_boundaries_repetition_and_changes_are_mandatory(self):
        tests=(ROOT/'ios/tests/SteamProfileChecks.swift').read_text()
        for expression in ('readiness(nil).memory == .unknown','readiness(0).memory == .unknown',
                           'readiness(budget - 1)', 'readiness(budget + 1)', 'for _ in 0..<20',
                           'preserved == header', 'fresh Start check must reject a changed manifest',
                           'preview pass cannot authorize a later low-memory Start'):
            self.assertIn(expression,tests)
        ci=(ROOT.parents[1]/'ci/check_linux_guest_profile.py').read_text()
        self.assertIn('"LINUX_STEAM_READINESS_PASS"',ci)
        profile=(ROOT/'ios/LinuxSteamProfile.swift').read_text()
        self.assertIn('free.uint64Value >= UInt64(Self.size) + 1024 * 1024 * 1024',swift_block(profile,'func provision('))

if __name__=='__main__': unittest.main()
