"""Actual generated shell/strict parser and wiring; no claimed repair or VM run."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import recovery_guest
import steam_recovery_guest
from test_terminal import swift_block


class SteamSafeRecovery(unittest.TestCase):
    def test_generated_steam_guest_is_exact_syntax_valid_and_gui_stays_receipt_bound(self):
        script=steam_recovery_guest.steam_script()
        self.assertEqual((ROOT/'ios/LinuxSteamRecoveryGuest.swift').read_text(),steam_recovery_guest.steam_swift())
        self.assertEqual(subprocess.run(['sh','-n'],input=script,capture_output=True).returncode,0)
        receipt=json.loads((ROOT/'evidence/gui-recovery-20261017/digest-receipt.json').read_text())
        for name,digest in receipt['source_inputs'].items():
            self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),digest)
        self.assertEqual((ROOT/'ios/LinuxRecoveryGuest.swift').read_text(),recovery_guest.swift(recovery_guest.SCRIPT.read_bytes()))

    def test_guest_has_only_work_journal_replay_and_two_readonly_full_checks(self):
        script=steam_recovery_guest.steam_script().decode()
        for text in ('ideck-recovery-tools','ideck-recovery-work','25165824','12884901888',
                     'c6a66b17-1b3e-4fe9-a07b-70c185fb2718','readonly','ro,noload','E2FSCK_CONFIG=/dev/null'):
            self.assertIn(text,script)
        self.assertEqual(script.count('check -p -E journal_only'),1)
        self.assertEqual(script.count('check -p'),1)
        self.assertEqual(script.count('check -f -n -E fixes_only'),2)
        self.assertIn('awk -f /ideck-fsck-clean.awk /run/eligibility.log 3>&- || fail manual_review',script)
        for forbidden in ('/counter-sync','allow_counters=1','check -y','mkfs','debugfs','tune2fs','rootfs-v1.raw','/home/ideck'):
            self.assertNotIn(forbidden,script)
        self.assertLess(script.index('set_target_mode ro 1',script.index('check -p')),script.index('IDECK_RECOVERY_SCAN_CLEAN'))
        self.assertLess(script.index('IDECK_RECOVERY_SCAN_CLEAN'),script.index('checked_hash=$(image_hash'))

    def test_scope_eligibility_copies_and_fresh_process_activation_keep_guards(self):
        source=(ROOT/'ios/LinuxGUIRecovery.swift').read_text()
        scope=swift_block(source,'enum Scope:')
        for check in ('specification.uuid == LinuxSteamProfile.uuid','specification.sizeBytes == LinuxSteamProfile.size',
                      'value.recoverBit && value.state == 1 && value.lastOrphan == 0 && value.errorCount == 0'):
            self.assertIn(check,scope)
        prepare=swift_block(source,'static func prepare(')
        self.assertLess(prepare.index('guard scope.permits(observation)'),prepare.index('transaction.hash(transaction.source)'))
        self.assertLess(prepare.index('specification.sizeBytes * 2 + 512'),prepare.index('transaction.hash(transaction.source)'))
        for guard in ('transaction.copy(transaction.source, transaction.backup)','transaction.copy(transaction.backup, transaction.work)',
                      'transaction.hash(transaction.source) == sourceHash','try progress?("backup")'):
            self.assertIn(guard,prepare)
        promote=swift_block(source,'static func promotePending(')
        for guard in ('receipt.process != process','receipt.suffixSHA256 == scope.suffixSHA256','receipt.toolSeedSHA256 == toolSeedSHA256',
                      'receipt.scanClean == true','recoveredHash == checkedSHA256','validateSuperblock(fd: transaction.work'):
            self.assertIn(guard,promote)
        self.assertLess(promote.index('guard recoveredHash == checkedSHA256'),promote.index('renameat('))

    def test_ui_failure_latch_stops_waiting_and_exposes_report_without_vm_actions(self):
        source=(ROOT/'ios/LinuxTerminalSession.swift').read_text()
        self.assertEqual(source.count('startupEndedBeforeNative = true'),3)
        self.assertEqual(source.count('startupEndedBeforeNative = false'),1)
        self.assertIn('Причина состояния пока не установлена',source)
        view=(ROOT/'ios/LinuxDesktopView.swift').read_text()
        display=swift_block(view,'private var display:')
        self.assertLess(display.index('if session.startupEndedBeforeNative'),display.index('else if session.displayTimedOut'))
        self.assertIn('if unified && !session.startupEndedBeforeNative',display)
        self.assertIn('Button("Диагностика / отчёт")',display)
        actions=swift_block(view,'private var persistentActions:')
        self.assertIn('session.attempted && !session.startupEndedBeforeNative',actions)
        self.assertIn('session.isSteam && !session.attempted',view)
        self.assertIn('confirmSteamRecovery = true',view)
        confirmed=swift_block(view,'Button("Создать копии и проверить журнал")')
        self.assertIn('session.startRecovery()',confirmed)
        self.assertIn('if session.attempted { dismiss(); LinuxProbeRoute.shared.choose(.steam) }',confirmed)
        self.assertEqual(source.count('attempted = false'),1)

    def test_actual_apple_negative_scope_fixtures_are_mandatory(self):
        ci=(ROOT.parents[1]/'ci/check_linux_guest_profile.py').read_text()
        for text in ('LinuxSteamRecoveryGuest.swift','SteamRecoveryChecks.swift','"LINUX_STEAM_RECOVERY_SCOPE_PASS"'):
            self.assertIn(text,ci)
        self.assertIn('try runSteamRecoveryChecks(', (ROOT/'ios/tests/SteamProfileChecks.swift').read_text())
        checks=(ROOT/'ios/tests/SteamRecoveryChecks.swift').read_text()
        for text in ('scope: .steam','availableBytes: { _ in 0 }','observed == eligible','current == header',
                     'Steam recovery accepted insufficient real-copy budget','scope.permits(nil)','watchdog.timeout(at: 1800) == .deadline'):
            self.assertIn(text,checks)
