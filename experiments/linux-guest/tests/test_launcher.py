"""Navigation/observation wiring checks. Swift state-machine execution is required
by the Apple gate; UIKit visuals and real Home/resume remain device gates."""
from pathlib import Path
import unittest
from test_terminal import swift_block

ROOT=Path(__file__).resolve().parents[1]

class Launcher(unittest.TestCase):
    def test_home_and_resume_never_touch_the_runtime_or_owner(self):
        source=(ROOT/'ios/LinuxProbeView.swift').read_text()
        for declaration in ('func home()', 'func resume()'):
            body=swift_block(source,declaration)
            for forbidden in ('qemu_', 'cancelPreparation', '.stop(', 'closeUnused', 'attempted =', 'JITBootstrap'):
                self.assertNotIn(forbidden,body)
        self.assertIn('navigation.reserve(runtimeOwner)',source)
        self.assertIn('guard navigation.open(target)',source)
        for name in ('steam','desktop','debian','shared'):
            self.assertIn(f'LinuxTerminalSession.{name}.attempted',source)
        self.assertIn('if LinuxProbeSession.shared.attempted',source)

    def test_disappear_releases_input_but_background_cancels_only_preparation(self):
        view=(ROOT/'ios/LinuxDesktopView.swift').read_text()
        disappear=swift_block(view,'.onDisappear')
        self.assertIn('input.setFocused(false)',disappear)
        self.assertNotIn('cancelPreparation',disappear)
        self.assertNotIn('stop()',disappear)
        root=(ROOT/'ios/LinuxProbeView.swift').read_text()
        phase=swift_block(root,'.onChange(of: scenePhase)')
        self.assertIn('phase == .background',phase)
        self.assertIn('session.cancelPreparation()',phase)
        self.assertNotIn('stop()',phase)
        self.assertIn('ContentView().opacity(route.destination == .library ? 1 : 0)',root)

    def test_nav_scenarios_are_in_mandatory_production_swift_checks(self):
        checks=(ROOT/'ios/tests/ConsoleLifecycleChecks.swift').read_text()
        self.assertIn('runLauncherNavigationChecks()',swift_block(checks,'func runConsoleLifecycleChecks()'))
        actual=swift_block(checks,'func runLauncherNavigationChecks()')
        for expression in ('navigation.home()', 'navigation.resume()', '0..<20',
                           '!navigation.open(other)', 'beforeStart.open(.desktop)', 'navigation.reserve(nil)'):
            self.assertIn(expression,actual)
        ci=(ROOT.parents[1]/'ci/check_linux_guest_profile.py').read_text()
        self.assertIn('"LINUX_LAUNCHER_NAVIGATION_PASS"',ci)

    def test_real_display_and_action_deadlines_never_claim_steam_success(self):
        source=(ROOT/'ios/LinuxTerminalSession.swift').read_text()
        poll=swift_block(source,'private func observeDisplay(')
        self.assertIn('husk_display_sequence() > 0',poll)
        self.assertIn('>= 60',poll)
        self.assertIn('!loopReturned, !stopRequested, !stopFailed, !startupAborted',poll)
        for forbidden in ('lock_frame', 'request_update', 'stop()', 'ready = true', 'steamInstalled = true'):
            self.assertNotIn(forbidden,poll)
        self.assertIn('self.owner.isDesktop && !self.isRecovery',source)
        worker=source[source.index('private final class LinuxTerminalWorker'):]
        action=swift_block(worker,'func steamAction(')
        self.assertIn('self.steamActionRevision == revision',action)
        self.assertIn('+ 180',action)
        self.assertNotIn('steamBusy = false',action)
        report=(ROOT/'ios/LinuxProbeReport.swift').read_text()
        for key in ('display_frame_observed','display_frame_timed_out','steam_action_wait_timed_out'):
            self.assertIn('"'+key+'"',report)

    def test_launcher_only_offers_real_actions_and_collapsed_controls(self):
        source=(ROOT/'ios/LinuxProbeView.swift').read_text()
        launcher=swift_block(source,'private var launcher:')
        for title in ('Steam / Big Picture','Рабочий стол','Настройки'):
            self.assertIn('"'+title+'"',launcher)
        for diagnostic in ('Send A','Start Linux','Boot / display / input test'):
            self.assertNotIn(diagnostic,launcher)
        for forbidden in ('session.start(', 'qemu_init', 'startRecovery', 'steamAction('):
            self.assertNotIn(forbidden,launcher)
        view=(ROOT/'ios/LinuxDesktopView.swift').read_text()
        self.assertIn('DisclosureGroup("Управление и клавиатура"',view)
        self.assertIn('if !session.ready || !session.displayHasFrame',view)
        self.assertIn('session.displayTimedOut',view)
        self.assertIn('LinuxDesktopDiagnosticsView(session: currentSession)',source)
        settings=swift_block(source,'private var settings:')
        self.assertIn('.disabled(route.runtimeOwner != nil || jit.busy)',settings)

if __name__=='__main__': unittest.main()
