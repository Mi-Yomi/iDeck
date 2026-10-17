"""Regression guards on real restored/patched Swift source and its locked flow.

These are source/staging checks, not Swift execution, UIKit interaction, JIT,
pairing or device proof. No runtime types or native implementation are stubbed.
"""
import hashlib
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "experiments/linux-guest/tools"))
import stage_husk
import typecheck_source


def body(source, declaration):
    """Extract the balanced block of one named declaration in reviewed sources."""
    begin = source.index("{", source.index(declaration))
    depth = 1
    cursor = begin + 1
    while depth:
        if source[cursor] == "{":
            depth += 1
        elif source[cursor] == "}":
            depth -= 1
        cursor += 1
    return source[begin + 1:cursor - 1]


class JITSetupSourceGuards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.output = Path(cls.temporary.name) / "source"
        cls.source_lock = typecheck_source.restore(cls.output)
        cls.original = {name: (cls.output / "src/app/Husk" / name).read_text()
                        for name in ("JITBootstrap.swift", "JITSetup.swift", "JITSetupView.swift")}
        typecheck_source.overlay(cls.output)
        cls.lock = stage_husk.load_overlay()
        cls.files = {name: (cls.output / "src/app/Husk" / name).read_text()
                     for name in ("JITBootstrap.swift", "JITSetup.swift", "JITSetupView.swift",
                                  "JITPairing.swift", "LinuxProbeView.swift", "LinuxProbeSession.swift", "HuskApp.swift")}

    def test_real_pinned_slice_and_all_new_patch_bytes_are_review_locked(self):
        self.assertEqual(self.source_lock["commit"], stage_husk.PIN)
        self.assertEqual(len(self.source_lock["files"]), 81)
        patch = "husk/patches/0002-jit-setup-routing.patch"
        self.assertIn(patch, self.lock["inputs"])
        series = (stage_husk.ROOT / "husk/patches/series").read_text().splitlines()
        self.assertEqual(series, ["0001-isolated-linux-probe-route.patch", "0002-jit-setup-routing.patch",
                                  "0003-paired-display-pointer-release.patch", "0004-desktop-input-bridge.patch"])
        self.assertEqual(hashlib.sha256((stage_husk.ROOT / patch).read_bytes()).hexdigest(), self.lock["inputs"][patch])
        for name in self.original:
            relative = "src/app/Husk/" + name
            self.assertEqual(hashlib.sha256(self.files[name].encode()).hexdigest(), self.lock["patched_files"][relative])
        for name in ("LinuxProbeView.swift", "LinuxProbeSession.swift"):
            relative = "ios/" + name
            self.assertEqual(self.files[name], (stage_husk.ROOT / relative).read_text())
            self.assertEqual(hashlib.sha256(self.files[name].encode()).hexdigest(), self.lock["inputs"][relative])

    def test_stock_magnifier_cannot_satisfy_trollstore_detector_without_marker(self):
        old = body(self.original["JITBootstrap.swift"], "static var isTrollStoreInstalled")
        self.assertIn("canOpenURL", old)
        self.assertNotIn("isInstalledWithTrollStore", old)
        detector = body(self.files["JITBootstrap.swift"], "static var isTrollStoreInstalled")
        self.assertRegex(detector, r"guard\s+isInstalledWithTrollStore\s+else\s*\{\s*return false\s*\}")
        self.assertLess(detector.index("guard isInstalledWithTrollStore"), detector.index("canOpenURL"))
        marker = body(self.files["JITBootstrap.swift"], "static var isInstalledWithTrollStore")
        self.assertIn("_TrollStore", marker)
        self.assertIn("_TrollStoreLite", marker)
        self.assertIn("FileManager.default.fileExists", marker)

        attach = body(self.files["JITBootstrap.swift"], "static func requestTrollStoreAttach()")
        guard = body(attach, "guard isInstalledWithTrollStore else")
        self.assertIn("return false", guard)
        self.assertNotIn("UIApplication.shared.open", guard)
        self.assertLess(attach.index("guard isInstalledWithTrollStore"), attach.index("UIApplication.shared.canOpenURL"))
        self.assertLess(attach.index("guard isInstalledWithTrollStore"), attach.index("UIApplication.shared.open"))
        resolver = body(self.files["JITSetup.swift"], "var resolvedMethod")
        self.assertRegex(resolver, r"if JITBootstrap\.isTrollStoreInstalled\s*\{\s*return \.trollStore\s*\}")
        self.assertIn("guard method == .automatic else { return method }", resolver)

    def test_linux_enable_prefers_builtin_only_for_automatic_and_preserves_choices(self):
        enable = body(self.files["LinuxProbeView.swift"], "private func enableJIT()")
        self.assertIn("guard !session.attempted, !jit.busy else { return }", enable)
        selection = body(enable, "if jit.method == .automatic, HuskBuiltInJIT.isAvailable")
        self.assertIn("jit.method = .builtIn", selection)
        self.assertEqual(enable.count("jit.method = .builtIn"), 1)
        self.assertLess(enable.index("jit.refreshPairingStatus()"), enable.index("jit.enable()"))
        self.assertIn('Button("Enable JIT") { enableJIT() }', self.files["LinuxProbeView.swift"])
        self.assertNotIn('Button("Enable JIT") { jit.enable() }', self.files["LinuxProbeView.swift"])

        source = self.files["LinuxProbeView.swift"]
        setup = body(source, 'Button("JIT setup and method")')
        self.assertIn("jit.refreshPairingStatus()", setup)
        self.assertIn("jit.showSetup = true", setup)
        self.assertIn('.sheet(isPresented: $jit.showSetup) { JITSetupFlow() }', source)
        self.assertIn("if jit.busy", source)
        self.assertIn("ProgressView", source)
        self.assertIn("if let error = jit.error", source)
        self.assertIn("Text(error)", source)
        self.assertIn("if !jit.hasPairing", source)
        self.assertIn("import its pairing file", source)
        self.assertRegex(source, r'Button\("Enable JIT"\).*?\.disabled\(session\.attempted \|\| jit\.busy\)')
        self.assertRegex(source, r'Button\("Start Linux"\).*?\.disabled\(session\.attempted \|\| jit\.busy\)')

    def test_missing_pairing_still_opens_original_walkthrough_before_helper_enable(self):
        enable = body(self.files["JITSetup.swift"], "func enable()")
        builtin = enable[enable.index("case .builtIn:"):]
        self.assertRegex(builtin, r"guard HuskBuiltInJIT\.isAvailable, hasPairing else\s*\{")
        rejected = body(builtin, "guard HuskBuiltInJIT.isAvailable, hasPairing else")
        self.assertIn("showSetup = true", rejected)
        self.assertIn("return", rejected)
        self.assertLess(builtin.index("showSetup = true"), builtin.index("enableBuiltIn()"))

        setup = self.files["JITSetupView.swift"]
        for route in ("case .pairOnDevice:", "case .importFile:", "case .connect:", "case .enable:",
                      "case .stikDebug:", "case .trollStore:", "case .jailbreak:"):
            self.assertIn(route, setup)
        for evidence in ("pairing.start()", "jit.importPairingFile(url)", "Developer Mode",
                         "UIApplication.openSettingsURLString", "LocalDevVPN.open()",
                         "jit.prepareBuiltIn()", "jit.enableBuiltIn()", "jit.resetDDI()"):
            self.assertIn(evidence, setup)
        self.assertIn('"StikJIT"', self.files["JITSetup.swift"])
        self.assertIn('"pairingFile.plist"', self.files["JITSetup.swift"])
        self.assertIn("majorVersion: 27", self.files["JITPairing.swift"])

    def test_vpn_callback_uses_registered_packaged_probe_scheme(self):
        connect = body(self.files["JITSetup.swift"], "static var connect: URL")
        self.assertIn('Bundle.main.object(forInfoDictionaryKey: "CFBundleURLTypes")', connect)
        self.assertIn('$0["CFBundleURLSchemes"]', connect)
        self.assertIn('schemes.first(where: { !$0.isEmpty }) ?? "husk"', connect)
        self.assertIn('URLComponents(string: "localdevvpn://enable")', connect)
        self.assertIn('URLQueryItem(name: "scheme", value: callback)', connect)
        self.assertNotIn("localdevvpn://enable?scheme=husk", connect)
        packager = (stage_husk.ROOT / "ipa/package_probe.py").read_text()
        self.assertIn('"CFBundleURLSchemes": ["ideck-linux-probe"]', packager)

    def test_debugger_attachment_is_not_presented_as_execution_success(self):
        setup = self.files["JITSetup.swift"]
        walkthrough = self.files["JITSetupView.swift"]
        self.assertNotIn('status = "JIT is on."', setup)
        self.assertNotIn('outcome("JIT is on. Android can start."', walkthrough)
        self.assertIn("verify executable memory", setup)
        self.assertIn("verify executable memory", walkthrough)
        view = self.files["LinuxProbeView.swift"]
        self.assertIn("Text(session.jitExecutionMessage)", view)
        self.assertIn("session.jitExecutionReady", view)
        # A defensive UI mapping also handles a future/original coordinator's
        # old wording without treating its debugger flag as executable memory.
        self.assertIn("coordinatorStatus", view)
        self.assertIn('"Debugger attached."', view)
        self.assertNotIn("else if let status = jit.status", view)
        self.assertIn("else if let status = coordinatorStatus", view)
        mapping = body(view, "private var coordinatorStatus")
        self.assertIn('jit.status == "JIT is on." ? "Debugger attached." : jit.status', mapping)

        session = self.files["LinuxProbeSession.swift"]
        claim = body(session, "func claimJIT()")
        self.assertIn("guard !attempted else { return }", claim)
        self.assertIn("guard JITBootstrap.ready else", claim)
        self.assertIn("jitExecutionReady = false", claim)
        self.assertIn("JITBootstrap.prewarm() || JITBootstrap.isLive || JITBootstrap.mapJITResult == true", claim)
        self.assertNotIn("JITBootstrap.mapJITWorks", claim)
        record = body(session, "private func recordJITExecution(_ passed: Bool)")
        self.assertIn("jitExecutionReady = passed", record)
        self.assertNotIn("JITBootstrap.ready", record)
        self.assertNotIn("debuggedFlag", record)
        view_body = body(self.files["LinuxProbeView.swift"].split("struct LinuxProbeView: View", 1)[1], "var body")
        self.assertNotIn("JITBootstrap.mapJITWorks", view_body)
        self.assertNotIn("JITBootstrap.prewarm()", view_body)
        content = body(self.files["LinuxProbeView.swift"], "private var content")
        self.assertNotIn("JITBootstrap.mapJITWorks", content)
        self.assertNotIn("JITBootstrap.prewarm()", content)

    def test_start_retains_execution_guard_before_one_shot_runtime_attempt(self):
        start = body(self.files["LinuxProbeSession.swift"], "func start()")
        self.assertIn("guard JITBootstrap.ready else", start)
        execution_guard = "guard JITBootstrap.prewarm() || JITBootstrap.isLive || JITBootstrap.mapJITWorks else"
        rejected = body(start, execution_guard)
        self.assertIn("recordJITExecution(false)", rejected)
        self.assertIn("return", rejected)
        self.assertLess(start.index(execution_guard), start.index("recordJITExecution(true)"))
        self.assertLess(start.index("recordJITExecution(true)"), start.index("attempted = true"))
        self.assertIn("guard !QemuRunner.shared.isRunning, husk_console_loaded_game() == nil", start)
        self.assertIn('appendingPathComponent("iDeckLinuxSessions"', start)
        self.assertIn("UUID().uuidString", start)

    def test_foreground_or_helper_attachment_only_claims_and_never_autostarts_guest(self):
        view = self.files["LinuxProbeView.swift"]
        claim = body(view, "private func claimJIT()")
        self.assertIn("session.claimJIT()", claim)
        self.assertNotIn("session.start()", claim)
        self.assertIn(".onChange(of: jit.attachGeneration) { _ in claimJIT() }", view)
        self.assertIn(".onChange(of: scenePhase) { if $0 == .active { claimJIT() } }", view)
        self.assertIn(".onAppear { claimJIT() }", view)
        self.assertEqual(view.count("session.start()"), 1)
        isolated_root = view.split("#if IDECK_LINUX_PROBE_ONLY", 1)[1].split("#else", 1)[0]
        self.assertIn("LinuxProbeView()", isolated_root)
        self.assertNotIn("ContentView()", isolated_root)
        self.assertNotIn("QemuRunner.shared.start()", view)
        self.assertIn("LinuxProbeRoot()", self.files["HuskApp.swift"])


if __name__ == "__main__":
    unittest.main()
