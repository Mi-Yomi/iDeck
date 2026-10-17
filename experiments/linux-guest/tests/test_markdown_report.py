"""Real package helpers and source/staging guards; no Python renderer surrogate.

The real renderer assertions are Swift code executed by the existing Apple
host gate. These local tests do not execute Swift, JIT or a device runtime.
"""
import ast
import copy
import hashlib
import plistlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "experiments/linux-guest/ipa"))
sys.path.insert(0, str(ROOT / "experiments/linux-guest/tools"))
import package_probe
import stage_husk
import typecheck_source


def block(source, declaration):
    start = source.index("{", source.index(declaration))
    depth = 1
    end = start + 1
    while depth:
        if source[end] == "{":
            depth += 1
        elif source[end] == "}":
            depth -= 1
        end += 1
    return source[start + 1:end - 1]


class MarkdownPackageTypes(unittest.TestCase):
    def test_real_helper_registers_only_markdown_utf8_mime_and_extension(self):
        info = {"CFBundleIdentifier": "dev.ideck.linuxprobe", "CFBundleURLTypes": [{"CFBundleURLSchemes": ["ideck-linux-probe"]}]}
        package_probe.configure_markdown_type(info)
        declaration = info["UTImportedTypeDeclarations"][0]
        self.assertEqual(declaration["UTTypeIdentifier"], "net.daringfireball.markdown")
        self.assertEqual(declaration["UTTypeConformsTo"], ["public.utf8-plain-text"])
        self.assertEqual(declaration["UTTypeTagSpecification"],
                         {"public.filename-extension": ["md"], "public.mime-type": ["text/markdown"]})
        self.assertEqual(info["CFBundleURLTypes"][0]["CFBundleURLSchemes"], ["ideck-linux-probe"])
        self.assertEqual(plistlib.loads(plistlib.dumps(info)), info)
        self.assertNotIn("CFBundleDocumentTypes", info)

    def test_existing_foreign_types_preserved_and_target_declaration_idempotent(self):
        foreign = {"UTTypeIdentifier": "example.foreign", "UTTypeTagSpecification": {"public.filename-extension": ["bin"]}}
        info = {"OtherSetting": True, "UTImportedTypeDeclarations": [copy.deepcopy(foreign),
                {"UTTypeIdentifier": "net.daringfireball.markdown", "UTTypeDescription": "old"}]}
        package_probe.configure_markdown_type(info)
        once = copy.deepcopy(info)
        package_probe.configure_markdown_type(info)
        self.assertEqual(info, once)
        self.assertEqual(info["UTImportedTypeDeclarations"][0], foreign)
        self.assertTrue(info["OtherSetting"])
        self.assertEqual(sum(item["UTTypeIdentifier"] == "net.daringfireball.markdown"
                             for item in info["UTImportedTypeDeclarations"]), 1)


class MarkdownIntegration(unittest.TestCase):
    def test_same_renderer_is_locked_and_staged_into_real_swift_source(self):
        lock = stage_husk.load_overlay()
        renderer = "ios/LinuxProbeReport.swift"
        self.assertEqual(lock["copies"][renderer], "src/app/Husk/LinuxProbeReport.swift")
        self.assertEqual(hashlib.sha256((stage_husk.ROOT / renderer).read_bytes()).hexdigest(), lock["inputs"][renderer])
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "source"
            restored = typecheck_source.restore(output)
            self.assertEqual(len(restored["files"]), 81)
            typecheck_source.overlay(output)
            staged = output / lock["copies"][renderer]
            self.assertEqual(staged.read_bytes(), (stage_husk.ROOT / renderer).read_bytes())
            self.assertIn(staged, typecheck_source.swift_sources(output))

    def test_apple_gate_wires_actual_swift_renderer_and_test_executable(self):
        script = ROOT / "ci/check_linux_guest_profile.py"
        tree = ast.parse(script.read_text())
        calls = {node.args[0].value: node for node in ast.walk(tree)
                 if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "run"
                 and node.args and isinstance(node.args[0], ast.Constant)}
        compile_command = calls["mac-compile"].args[1]
        self.assertEqual([node.value for node in compile_command.elts[:2]], ["xcrun", "swiftc"])
        names = {node.id for node in ast.walk(compile_command) if isinstance(node, ast.Name)}
        self.assertIn("markdown", names)
        self.assertIn("markdown_tests", names)
        self.assertLess(calls["mac-compile"].lineno, calls["mac-tests"].lineno)
        main = (stage_husk.ROOT / "ios/tests/main.swift").read_text()
        self.assertIn("try runMarkdownReportChecks()", main)
        checks = (stage_husk.ROOT / "ios/tests/MarkdownReportChecks.swift").read_text()
        self.assertIn("LinuxProbeReport.render(report:", checks)
        self.assertIn("NSNumber(value: 1)", checks)
        self.assertIn("LINUX_MARKDOWN_REPORT_CHECKS_PASS", checks)
        self.assertNotIn("import UIKit", checks)

    def test_renderer_is_pure_allowlisted_presentation_not_private_data_collection(self):
        renderer = (stage_husk.ROOT / "ios/LinuxProbeReport.swift").read_text()
        self.assertIn("import Foundation", renderer)
        self.assertIn("import CoreFoundation", renderer)
        for forbidden in ("FileManager", "Bundle.main", "UserDefaults", "ProcessInfo", "String(contentsOf",
                          "Data(contentsOf", "URLSession", "JSONSerialization", "JITPairingFileStore"):
            self.assertNotIn(forbidden, renderer)
        self.assertNotIn('report["argv"]', renderer)
        self.assertNotIn("report.keys", renderer)
        self.assertIn("CFGetTypeID(number) == CFBooleanGetTypeID()", renderer)
        self.assertIn("allowedSet.contains(string)", renderer)
        self.assertIn('static let filename = "iDeck-Linux-Probe-Report.md"', renderer)

    def test_raw_json_saved_first_and_markdown_failure_cannot_change_probe_outcome(self):
        session = (stage_husk.ROOT / "ios/LinuxProbeSession.swift").read_text()
        save = block(session, "func saveReport() throws")
        raw = "JSONSerialization.data(withJSONObject: report, options: [.prettyPrinted, .sortedKeys])"
        self.assertIn(raw, save)
        self.assertLess(save.index(raw), save.index("LinuxProbeReport.render(report: report, serial: latestSerial)"))
        self.assertIn(".write(to: resultURL, options: .atomic)", save)
        self.assertIn(".write(to: markdownURL, atomically: true, encoding: .utf8)", save)
        optional_failure = save.rsplit("catch {", 1)[1]
        self.assertIn("invalidateMarkdown()", optional_failure)
        self.assertNotIn("throw", optional_failure)
        self.assertNotIn("finish(", optional_failure)
        self.assertNotIn('report["status"]', optional_failure)
        invalidation = block(session, "func invalidateMarkdown()")
        self.assertIn("markdownAvailable = false", invalidation)
        self.assertIn("removeItem(at: markdownURL)", invalidation)
        self.assertNotIn("removeItem(at: resultURL)", invalidation)
        exports = block(session, "func refreshExportFiles()")
        self.assertIn("fileExists(atPath:", exports)
        self.assertIn("markdownAvailable &&", exports)

    def test_share_menu_keeps_markdown_and_raw_evidence_separate(self):
        view = (stage_husk.ROOT / "ios/LinuxProbeView.swift").read_text()
        markdown = block(view, 'Button("Markdown report (.md)")')
        raw = block(view, 'Button("Raw JSON and serial log")')
        self.assertIn("shareItems = [file]", markdown)
        self.assertIn("session.markdownFile", markdown)
        self.assertIn("shareItems = session.shareFiles", raw)
        self.assertIn("session.exportError", view)
        self.assertIn("ShareSheet(items: shareItems)", view)
        package = (stage_husk.ROOT / "ipa/package_probe.py").read_text()
        self.assertLess(package.index("    configure_markdown_type(info)"), package.index("    plist_path.write_bytes"))

    def test_boot_markers_are_observed_from_full_lines_not_elapsed_or_substrings(self):
        session = (stage_husk.ROOT / "ios/LinuxProbeSession.swift").read_text()
        self.assertIn('serialLines = serial.components(separatedBy: "\\n")', session)
        self.assertIn('serialLines.contains("IDECK_BOOT_BEGIN")', session)
        self.assertIn('serialLines.contains("IDECK_PROBE_DONE")', session)
        self.assertNotIn('serial.contains("IDECK_BOOT_BEGIN")', session)
        self.assertIn('report["elapsed_seconds"] = Date().timeIntervalSince(began)', session)
        renderer = (stage_husk.ROOT / "ios/LinuxProbeReport.swift").read_text()
        self.assertIn("not pure boot time", renderer)
        self.assertIn("including input interaction", renderer)


if __name__ == "__main__":
    unittest.main()
