"""Actual generated shell/strict parser and wiring; no claimed repair or VM run."""
import hashlib
import json
import os
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

    def test_actual_binding_shell_accepts_only_one_complete_canonical_identity(self):
        generation='11111111-1111-4111-8111-111111111111'
        nonce='22222222-2222-4222-8222-222222222222'
        digest='a'*64
        fields=[f'ideck.recovery_id={generation}',f'ideck.recovery_nonce={nonce}',f'ideck.recovery_source_sha256={digest}']
        prelude=steam_recovery_guest.binding_prelude().decode()
        self.assertEqual(prelude.count('$(cat /proc/cmdline)'),1)
        script='exec 3>&1\nfail() { echo "FAIL:$1"; exit 7; }\n'+prelude.replace('$(cat /proc/cmdline)', "$(printf '%s' \"$CASE_CMDLINE\")")
        def execute(arguments):
            return subprocess.run(['sh','-c',script],env={**os.environ,'CASE_CMDLINE':' '.join(arguments)},capture_output=True,text=True)
        good=execute(['console=ttyAMA0',*fields])
        self.assertEqual(good.returncode,0,good.stderr)
        self.assertEqual(good.stdout,f'IDECK_RECOVERY_BIND:{generation}:{nonce}:{digest}\n')
        cases=[fields[:2],fields[1:],fields+[fields[0]],fields+['ideck.recovery_nonce='],
               ['ideck.recovery_id=',*fields],fields[:1]+['ideck.recovery_nonce=bad']+fields[2:],
               fields[:2]+['ideck.recovery_source_sha256='+'A'*64],
               [fields[0].replace('-','',1),*fields[1:]]]
        for arguments in cases:
            with self.subTest(arguments=arguments):
                result=execute(arguments)
                self.assertEqual(result.returncode,7,result.stdout+result.stderr)
                self.assertNotIn('IDECK_RECOVERY_BIND:',result.stdout)

    def test_full_input_hash_precedes_assessment_and_any_work_writes(self):
        script=steam_recovery_guest.steam_script().decode()
        self.assertLess(script.index('IDECK_RECOVERY_BIND:'),script.index('IDECK_DESKTOP_RECOVERY_READY'))
        self.assertLess(script.index('set_target_mode ro 1\ninput_hash='),script.index('check -f -n\n'))
        self.assertLess(script.index('[ "$1" = "$binding_source" ]'),script.index('check -f -n\n'))
        self.assertLess(script.index('IDECK_RECOVERY_SOURCE_SHA256:'),script.index('set_target_mode rw 0'))
        self.assertIn("awk '$1==12884901888 && $2==\"bytes\" {ok++} END {exit(ok!=1)}' /run/source-hash.log",script)
        profile=(ROOT/'ios/LinuxGUIProfile.swift').read_text()
        self.assertIn('args[append + 1] += " " + binding.arguments',swift_block(profile,'func recoveryArguments('))

    def test_failed_or_timed_out_recovery_cannot_be_resurrected_by_late_ready(self):
        source=(ROOT/'ios/LinuxTerminalSession.swift').read_text()
        ready=swift_block(source,'if owner.isDesktop, line == Data("IDECK_DESKTOP_RECOVERY_READY".utf8)')
        self.assertLess(ready.index('guard acceptRecoveryActivity()'),ready.index('checkpoint(.terminalReady)'))
        self.assertLess(ready.index('guard recoveryProgress.bindingReady'),ready.index('checkpoint(.terminalReady)'))
        self.assertIn('report["terminal_clean_stop"] = false; report["status"] = "terminal_stop_failed"',ready)
        recovery=(ROOT/'ios/LinuxGUIRecovery.swift').read_text()
        self.assertIn('receipt?.failure == nil',swift_block(recovery,'func recordResult('))
        promote=swift_block(recovery,'static func promotePending(')
        self.assertLess(promote.index('receipt.failure == nil, scope.resultBound(receipt)'),promote.index('transaction.backup ='))

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
        for text in ('LinuxSteamRecoveryGuest.swift','SteamRecoveryChecks.swift','"LINUX_STEAM_RECOVERY_SCOPE_PASS"','"LINUX_STEAM_RECOVERY_BINDING_PASS"'):
            self.assertIn(text,ci)
        self.assertIn('try runSteamRecoveryChecks(', (ROOT/'ios/tests/SteamProfileChecks.swift').read_text())
        checks=(ROOT/'ios/tests/SteamRecoveryChecks.swift').read_text()
        for text in ('scope: .steam','availableBytes: { _ in 0 }','observed == eligible','current == header',
                     'Steam recovery accepted insufficient real-copy budget','scope.permits(nil)','watchdog.timeout(at: 1800) == .deadline','try runSteamRecoveryBindingChecks(', 'try rejectPromotion(bad', 'try progress.observe(line)'):
            self.assertIn(text,checks)
