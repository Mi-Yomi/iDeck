"""Mode/overlay wiring regressions. Actual Swift disk and relaunch IO is mandatory
in the Apple gate; these source checks do not establish device recovery."""
import json
from pathlib import Path
import unittest
from test_terminal import swift_block

ROOT = Path(__file__).resolve().parents[1]


class SteamRecoveryIntegration(unittest.TestCase):
    def test_steam_profile_report_uses_its_manifest_before_desktop_fallback(self):
        source = (ROOT / 'ios/LinuxTerminalSession.swift').read_text()
        line = next(line for line in source.splitlines() if 'self.report["terminal_profile_sha256"] =' in line)
        self.assertIn('self.owner.isSteam ? "steam-profile.json" : self.owner.isDesktop ? "desktop-profile.json"', line)
        for filename in ('debian-profile.json', 'terminal-profile.json'):
            self.assertIn(filename, line)
        self.assertIn('self.owner.isDesktop && !self.owner.isSteam ? (try LinuxGUIProfile.load', source)
        self.assertIn('isSteam ? "iDeckSteam-v1" : isDesktop ? "iDeckDebianGUI-v1"', source)

    def test_explicit_and_automatic_gui_recovery_exclude_steam_and_native_entry(self):
        source = (ROOT / 'ios/LinuxTerminalSession.swift').read_text()
        recovery = swift_block(source, 'func startRecovery()')
        self.assertIn('guard isDesktop, !isSteam else', recovery)
        self.assertIn('guard !attempted else', recovery)
        prepare = swift_block(source, 'private func prepareRecovery(')
        self.assertIn('guard owner.isDesktop, !owner.isSteam, !enteredQEMU', prepare)
        self.assertIn('recoveryRequested = false; start()', swift_block(source, 'func startDesktop()'))
        view = (ROOT / 'ios/LinuxDesktopView.swift').read_text()
        self.assertIn('else if !session.isSteam {\n                Button("Recover disk")', view)
        self.assertIn('"Start desktop") { session.startDesktop() }', view)
        self.assertIn('GUI recovery does not support this separate 12 GiB disk', source)
        self.assertIn('!LinuxTerminalSession.steam.attempted', source)

    def test_dirty_steam_observation_and_repeated_refusal_are_in_actual_apple_checks(self):
        profile = (ROOT / 'ios/LinuxSteamProfile.swift').read_text()
        self.assertIn('specification: image, observe: observe)', swift_block(profile, 'func openExisting('))
        checks = (ROOT / 'ios/tests/SteamProfileChecks.swift').read_text()
        for expression in ('for _ in 0..<2', 'catch LinuxDesktopDisk.Invalid.needsRecovery',
                           'observed?.recoverBit == true', 'catch LinuxGUIRecovery.Invalid.metadata',
                           'preserved == header'):
            self.assertIn(expression, checks)
        main = (ROOT / 'ios/tests/main.swift').read_text()
        self.assertIn('runGUIRecoveryChecks', main)
        self.assertIn('runSteamProfileChecks', main)
        ci = (ROOT.parents[1] / 'ci/check_linux_guest_profile.py').read_text()
        for marker in ('LINUX_STEAM_PROFILE_PASS', 'LINUX_GUI_RECOVERY_PASS', 'LINUX_EXT4_DIAGNOSTICS_PASS'):
            self.assertIn('"' + marker + '"', ci)

    def test_all_modes_keep_fixed_failure_screen_exports_and_separate_assets(self):
        view = (ROOT / 'ios/LinuxDesktopView.swift').read_text()
        self.assertIn('init(session: LinuxTerminalSession = .desktop)', view)
        actions = swift_block(view, 'private var persistentActions:')
        self.assertIn('Button("Share report")', actions)
        self.assertIn('Button("Diagnostics")', actions)
        for label in ('Share report', 'Diagnostics'):
            self.assertNotIn('session.ready', swift_block(actions, 'Button("' + label + '")'))
        renderer = (ROOT / 'ios/LinuxProbeReport.swift').read_text()
        self.assertIn('let steam = report["mode"] as? String == "steam-experimental"', renderer)
        self.assertIn('# iDeck Steam Experiment Report', renderer)
        self.assertIn('existing_steam_disk_preserved', renderer)
        lock = json.loads((ROOT / 'husk/overlay.lock.json').read_text())
        for name in ('LinuxGUIRecovery.swift', 'LinuxRecoveryGuest.swift', 'LinuxStartupFailure.swift', 'LinuxSteamProfile.swift'):
            self.assertEqual(lock['copies']['ios/' + name], 'src/app/Husk/' + name)


if __name__ == '__main__':
    unittest.main()
