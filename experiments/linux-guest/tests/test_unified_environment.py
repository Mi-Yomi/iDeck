"""Guest receipt lock ordering and unified routing; no Steam/native execution."""
import contextlib
import fcntl
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from test_terminal import swift_block

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import steam_offline_cache as tool


class UnifiedEnvironment(unittest.TestCase):
    def test_generated_guest_releases_real_action_lock_before_install_receipt(self):
        for fail in (False, True):
            with self.subTest(installer_fails=fail), tempfile.TemporaryDirectory() as temp:
                root=Path(temp); action=root/'device-action.py';action.write_bytes(tool.runtime_device_action())
                spec=importlib.util.spec_from_file_location('generated_environment_action',action)
                module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
                module.OPT=root;module.LOG=root/'log';module.ACTION_LOCK=root/'action.lock';module.PROC=root/'proc'
                module.PROC.mkdir();(module.PROC/'cmdline').write_text('ideck.steam_experiment=1 ideck.steam_persistent=1 ideck.steam_network=1')
                sentinel=root/'existing-userdata';sentinel.write_bytes(b'preserve userdata')
                (root/'steam-offline-cache.py').write_text('import contextlib\n@contextlib.contextmanager\ndef source(installer):\n    yield\n')
                (root/'install-official.py').write_text("def install():\n    "+("raise RuntimeError('fixture')" if fail else "return")+'\n')
                observed=[]
                class Receipt(io.StringIO):
                    def write(self,text):
                        if 'IDECK_STEAM_INSTALLED' in text:
                            with module.ACTION_LOCK.open('r+') as contender:
                                fcntl.flock(contender,fcntl.LOCK_EX|fcntl.LOCK_NB)
                                observed.append('lock free before INSTALLED')
                        return super().write(text)
                output=Receipt()
                with patch.object(module.os,'geteuid',return_value=0),contextlib.redirect_stdout(output):
                    if fail:
                        with self.assertRaisesRegex(RuntimeError,'fixture'):module.main('install')
                    else:module.main('install')
                self.assertEqual(observed,[] if fail else ['lock free before INSTALLED'])
                self.assertEqual('IDECK_STEAM_INSTALLED' in output.getvalue(),not fail)
                self.assertEqual(sentinel.read_bytes(),b'preserve userdata')
                with module.ACTION_LOCK.open('r+') as contender:fcntl.flock(contender,fcntl.LOCK_EX|fcntl.LOCK_NB)

    def test_main_launcher_has_one_primary_entry_and_legacy_disks_only_in_advanced(self):
        source=(ROOT/'ios/LinuxProbeView.swift').read_text()
        launcher=swift_block(source,'private var launcher:')
        self.assertIn('"Запустить среду"',launcher);self.assertIn('"Продолжить среду"',launcher)
        for forbidden in ('launcherCard(','.choose(.steam)', '.choose(.desktop)', '.choose(.linux)', 'Boot / display / input test', 'Check Boot'):
            self.assertNotIn(forbidden,launcher)
        advanced=swift_block(source,'private var advanced:')
        self.assertIn('LinuxProbeRoute.Destination.desktop, .terminal, .debian, .linux',advanced)
        self.assertIn('без миграции',advanced)
        start=swift_block(source,'private func advanceLaunch()')
        self.assertIn('launchIntent.advance(',start);self.assertIn('foreground: scenePhase == .active',start)
        self.assertIn('steam.startEnvironment()',start)

    def test_automatic_actions_use_real_ready_receipts_and_existing_serialized_verb_path(self):
        source=(ROOT/'ios/LinuxTerminalSession.swift').read_text()
        ready=source.index('let command = environment.desktopReady()')
        self.assertIn('consoleReady, steamOfflineCache != nil',source[ready-150:ready])
        self.assertIn('environment.observe(status)',source)
        automatic=swift_block(source,'private func automaticSteam(')
        self.assertIn('enqueueSteamAction(command.rawValue)',automatic)
        queue=swift_block(source,'private func enqueueSteamAction(')
        for guard in ('!self.stopRequested','!self.loopReturned','!self.steamCommandInFlight','self.ready'):
            self.assertIn(guard,queue)
        self.assertIn('environment.timedOut()',queue)
        self.assertNotIn('steamBusy = false',queue)
        start=swift_block(source,'func startEnvironment()')
        self.assertIn('!attempted',start);self.assertIn('start()',start)
        self.assertEqual(source.count('attempted = false'),1)
        self.assertIn('"iDeckSteam-v1"',source)

    def test_new_production_state_and_mandatory_apple_checks_are_staged(self):
        lock=json.loads((ROOT/'husk/overlay.lock.json').read_text())
        self.assertEqual(lock['copies']['ios/LinuxEnvironmentStartup.swift'],'src/app/Husk/LinuxEnvironmentStartup.swift')
        ci=(ROOT.parents[1]/'ci/check_linux_guest_profile.py').read_text()
        for item in ('LinuxEnvironmentStartup.swift','EnvironmentStartupChecks.swift','"LINUX_UNIFIED_ENVIRONMENT_PASS"'):
            self.assertIn(item,ci)
        self.assertIn('runEnvironmentStartupChecks()', (ROOT/'ios/tests/main.swift').read_text())

    def test_launcher_click_gives_feedback_before_checks_and_is_not_silently_disabled(self):
        source=(ROOT/'ios/LinuxProbeView.swift').read_text()
        launcher=swift_block(source,'private var launcher:')
        self.assertNotIn('.disabled(jit.busy || pendingLaunch)',launcher)
        click=swift_block(source,'private func launchPrimary()')
        self.assertLess(click.index('launchNotice = "Проверяем'),click.index('DispatchQueue.main.asyncAfter'))
        self.assertLess(click.index('steam.claimJIT()'),click.index('steam.refreshSteamReadiness()'))
        self.assertLess(click.index('steam.refreshSteamReadiness()'),click.index('advanceLaunch()'))
        self.assertIn('Проверка запуска уже выполняется',click)
        self.assertIn('route.runtimeOwner != nil { route.resume(); return }',click)
        for guard in ('guard pendingLaunch','scenePhase == .active','guard route.runtimeOwner == nil','guard !jit.busy'):
            self.assertIn(guard,click)

    def test_inline_jit_prompt_uses_existing_flow_and_rechecks_without_auto_start(self):
        source=(ROOT/'ios/LinuxProbeView.swift').read_text()
        self.assertIn('ideck-launcher-jit-setup',source)
        self.assertIn('JITSetupFlow()',source)
        setup=swift_block(source,'private func openLauncherJIT()')
        for text in ('jit.refreshPairingStatus()', 'HuskBuiltInJIT.isAvailable', 'jit.method = .builtIn', 'showJIT = true'):
            self.assertIn(text,setup)
        recheck=swift_block(source,'private func recheckLauncherJIT()')
        self.assertLess(recheck.index('steam.claimJIT()'),recheck.index('let verified = steam.jitExecutionReady'))
        self.assertIn('launchIntent.checkedJIT(verified)',recheck)
        for forbidden in ('startEnvironment()', 'advanceLaunch()', 'requestTrollStoreAttach', 'apple-magnifier'):
            self.assertNotIn(forbidden,recheck)
        model=(ROOT/'ios/LinuxEnvironmentStartup.swift').read_text()
        self.assertIn('guard jit else { checkedJIT(false); return .jit }',model)
        self.assertIn('pending = false; jitPrompt = !verified',model)
        session=(ROOT/'ios/LinuxTerminalSession.swift').read_text()
        claim=swift_block(session,'func claimJIT()')
        self.assertIn('recordJIT(false)',claim[claim.index('catch {'):])

    def test_owner_memory_refusal_has_measured_budget_and_smaller_mode_action(self):
        source=(ROOT/'ios/LinuxProbeView.swift').read_text()
        launcher=swift_block(source,'private var launcher:')
        for text in ('readiness.memory != .passed','readiness.memoryExplanation','steam.steamMemoryMode = .fixed1536','Обновить замер памяти'):
            self.assertIn(text,launcher)
        profile=(ROOT/'ios/LinuxSteamProfile.swift').read_text()
        self.assertIn('Недостаточно бюджета процесса с резервом; Auto не использует всю физическую RAM',profile)
        fixture=(ROOT/'ios/tests/SteamProfileChecks.swift').read_text()
        for text in ('autoRefusal.memory == .blocked(', 'autoRefusal.jit == .passed','stale readiness cannot authorize fixed1536'):
            self.assertIn(text,fixture)
        memory=(ROOT/'ios/LinuxSteamMemory.swift').read_text()
        policy=swift_block(memory,'static func plan(')
        self.assertIn('let room = (available - retained) / mib',policy)
        for forbidden in ('physicalMemory','resident','RSS'):
            self.assertNotIn(forbidden,policy)

    def test_fresh_worker_budget_checks_remain_after_cache_and_disk_io(self):
        source=(ROOT/'ios/LinuxTerminalSession.swift').read_text()
        worker=source[source.index('private final class LinuxTerminalWorker'):]
        prepare=worker.index('LinuxSteamOfflineCache.prepareBundled(')
        args=worker.index('let plan = try LinuxSteamMemory.plan(',prepare)
        self.assertLess(prepare,args)
        gate=swift_block(worker,'private func prepareNativeEntry(')
        for text in ('LinuxSteamMemory.enterAfterIO', 'disk.validateOwnership()', 'os_proc_available_memory()'):
            self.assertIn(text,gate)


if __name__=='__main__':unittest.main()
