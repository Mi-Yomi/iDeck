import Foundation

/// Runs the app's actual Foundation renderer on the Apple host. These fixtures
/// test report export only; they do not execute QEMU, pair a device or prove JIT.
func runMarkdownReportChecks() throws {
    var assertions = 0
    func expect(_ condition: @autoclosure () -> Bool, _ message: String) {
        precondition(condition(), "Markdown report: " + message)
        assertions += 1
    }
    func cell(_ markdown: String, _ label: String) -> String {
        for line in markdown.split(separator: "\n") {
            let columns = line.split(separator: "|", omittingEmptySubsequences: false)
            if columns.count >= 3,
               columns[1].trimmingCharacters(in: .whitespaces) == label {
                return columns[2].trimmingCharacters(in: .whitespaces)
                    .replacingOccurrences(of: "**", with: "")
            }
        }
        preconditionFailure("Markdown report: missing row " + label)
    }
    let complete: [String: Any] = [
        "schema": 1, "status": "guest_frames_and_input_verified",
        "app_version": "2.0.0", "app_bundle_version": "119",
        "ideck_source_commit": String(repeating: "a", count: 40),
        "husk_commit": "0695248f491cda877f7969d1f0cc89aeede1482e",
        "device_class": "iPhone17,2", "os": "iOS 27.0", "started_utc": "2026-10-16T02:00:00Z",
        "jit_execution_check_passed": true, "jit_available_after_init": true,
        "qemu_init_returned": true, "linux_boot_observed": true, "guest_probe_completed": true,
        "guest_input_verified": true, "physical_screen_verified": false,
        "accelerated_guest_gpu_verified": false, "steam_executed": false,
        "profile_cpu": "cortex-a72", "profile_memory_mib": 1024, "profile_vcpus": 4,
        "profile_width": 800, "profile_height": 600,
        "prewarmed_region_mib": 512, "requested_tcg_mib": 256, "elapsed_seconds": 25.5,
        "matched_frame_phases": [0, 1], "frame_0_pixels_checked": 480000, "frame_1_pixels_checked": 480000,
        "frame_0_bgra_sha256": String(repeating: "1", count: 64),
        "frame_1_bgra_sha256": String(repeating: "2", count: 64),
        "serial_sha256": String(repeating: "3", count: 64),
        "app_executable_sha256": String(repeating: "4", count: 64)
    ]
    let full = LinuxProbeReport.render(report: complete)
    expect(cell(full, "QEMU owner thread retained until app exits") == "UNKNOWN", "older reports do not infer thread retention")
    var retained = complete
    retained["qemu_owner_thread_retained_until_process_exit"] = true
    expect(cell(LinuxProbeReport.render(report: retained), "QEMU owner thread retained until app exits") == "RETENTION ENTERED",
           "thread retention has a separate narrow receipt")
    retained["mode"] = "debian"
    expect(cell(LinuxProbeReport.render(report: retained), "Host log/socket close path returned") == "UNKNOWN", "missing tail is not inferred from clean status")
    retained["console_shutdown_tail_returned"] = true
    expect(cell(LinuxProbeReport.render(report: retained), "Host log/socket close path returned") == "RETURNED", "host close tail has a separate receipt")
    expect(full.hasPrefix("# iDeck Linux Probe Report"), "stable human-readable title")
    for (label, expected) in [("JIT execution before start", "PASS"), ("JIT available after QEMU init", "PASS"),
                              ("QEMU init returned", "RETURNED"), ("Linux init marker", "OBSERVED (Linux init started)"),
                              ("Guest completion marker", "OBSERVED (validation below)"),
                              ("Guest input", "PASS (keyboard and tablet evdev)")] {
        expect(cell(full, label) == expected, label + " explicit true preserves its specific meaning")
    }
    expect(cell(full, "Physical screen") == "NOT VERIFIED", "framebuffer pass is not physical-screen proof")
    expect(cell(full, "Accelerated guest GPU") == "NOT VERIFIED", "software probe is not accelerated GPU proof")
    expect(cell(full, "Steam") == "NOT RUN", "Linux/input success is not Steam execution")
    expect(full.contains("25.5"), "elapsed evidence preserved")
    expect(full.lowercased().contains("not pure boot"), "polling/interaction elapsed must not be called pure boot time")
    expect(full.contains(String(repeating: "a", count: 40)), "source identity included")
    expect(cell(full, "Device class") == "iPhone17&#44;2", "device class safely escaped without adding a personal identifier")
    for (label, expected) in [("Version", "2&#46;0&#46;0"), ("Build", "119"), ("Schema", "1"),
                              ("Frame A RGB validation", "PASS"), ("Frame B RGB validation", "PASS"),
                              ("Frame A pixels checked", "480000"), ("Frame B pixels checked", "480000"),
                              ("CPU", "cortex&#45;a72"), ("Guest memory MiB", "1024"), ("Guest vCPUs", "4"),
                              ("Guest width", "800"), ("Guest height", "600"),
                              ("Prewarmed region MiB", "512"), ("Requested TCG MiB", "256")] {
        expect(cell(full, label) == expected, label + " is present in the safe summary")
    }
    for (label, character) in [("Frame A BGRA SHA-256", "1"), ("Frame B BGRA SHA-256", "2"),
                               ("Serial SHA-256", "3"), ("Installed executable SHA-256", "4")] {
        expect(cell(full, label) == String(repeating: character, count: 64), label + " identity retained")
    }

    for label in ["Husk commit", "OS", "Status", "Started UTC", "Matched framebuffer phases", "Elapsed seconds"] {
        expect(cell(full, label) != "UNKNOWN", label + " approved metadata/evidence must not be dropped")
    }
    let unknownStatus = LinuxProbeReport.render(report: ["status": "UNRECOGNIZED_PRIVATE_STATUS_CANARY"])
    expect(cell(unknownStatus, "Status") == "UNKNOWN", "unknown status is not promoted to success")
    expect(!unknownStatus.contains("UNRECOGNIZED_PRIVATE_STATUS_CANARY"), "unknown status text excluded")

    let runtimeFields = [
        ("jit_execution_check_passed", "JIT execution before start", "NOT VERIFIED"),
        ("jit_available_after_init", "JIT available after QEMU init", "NOT VERIFIED"),
        ("qemu_init_returned", "QEMU init returned", "NOT OBSERVED"),
        ("linux_boot_observed", "Linux init marker", "NOT OBSERVED"),
        ("guest_probe_completed", "Guest completion marker", "NOT COMPLETED"),
        ("guest_input_verified", "Guest input", "NOT VERIFIED"),
        ("physical_screen_verified", "Physical screen", "NOT VERIFIED"),
        ("accelerated_guest_gpu_verified", "Accelerated guest GPU", "NOT VERIFIED"),
        ("steam_executed", "Steam", "NOT RUN")
    ]
    for (key, label, falseValue) in runtimeFields {
        expect(cell(LinuxProbeReport.render(report: [key: false]), label) == falseValue,
               key + " explicit false must remain distinct from unknown")
        let invalidBooleans: [Any] = [NSNull(), NSNumber(value: 1), "true", [true], ["value": true]]
        for invalid in invalidBooleans {
            expect(cell(LinuxProbeReport.render(report: [key: invalid]), label) == "UNKNOWN",
                   key + " must reject null, number, string and container booleans")
        }
        expect(cell(LinuxProbeReport.render(report: [:]), label) == "UNKNOWN", key + " absent is unknown")
    }
    for state in ["prepared", "booting", "prepare_failed", "guest_failed", "probe_timeout", "evidence_failed"] {
        let early = LinuxProbeReport.render(report: ["status": state])
        expect(!early.contains("| PASS |"), state + " must not synthesize runtime passes")
        expect(cell(early, "Guest input") == "UNKNOWN", state + " missing input evidence remains unknown")
    }

    let maliciousOS = "iOS 27 | `code` ```\r\n<script>alert(1)</script> [click](https://example.invalid) Привет 👋\u{202E}"
    let escaped = LinuxProbeReport.render(report: ["os": maliciousOS])
    expect(!escaped.contains(maliciousOS), "untrusted metadata not emitted verbatim")
    expect(!escaped.contains("<script>"), "HTML cannot become active markup")
    expect(!escaped.contains("[click](https://example.invalid)"), "Markdown link cannot become active markup")
    expect(!escaped.contains("```"), "metadata cannot inject a fenced code block")
    expect(escaped.contains("Привет 👋"), "UTF-8 metadata remains readable")
    expect(cell(escaped, "OS").contains("&#91;U+D&#93;") && cell(escaped, "OS").contains("&#91;U+A&#93;"), "CR/LF made visible without creating rows")
    expect(escaped.contains("&#91;U+202E&#93;"), "bidi formatting control made visible")
    let tail = "TRUNCATION_SECRET_CANARY"
    let bounded = LinuxProbeReport.render(report: ["os": String(repeating: "x", count: 200) + tail])
    expect(!bounded.contains(tail), "metadata is bounded before long-tail content")

    let secret = "DO_NOT_EXPORT_PAIRING_TOKEN_7D922"
    var sensitive = complete
    sensitive["argv"] = ["qemu", "-kernel", "/private/" + secret]
    sensitive["pairing"] = ["private_key": secret]
    sensitive["token"] = secret
    sensitive["future_unknown_field"] = ["nested": [secret]]
    sensitive["error"] = secret
    let before = try JSONSerialization.data(withJSONObject: sensitive, options: [.sortedKeys])
    let safe = LinuxProbeReport.render(report: sensitive, serial:
        "IDECK_FRAME_A\nIDECK_FRAME_A " + secret + "\n" + secret + "\nLinux version 6.18.35-0-virt " + secret + "\n")
    let after = try JSONSerialization.data(withJSONObject: sensitive, options: [.sortedKeys])
    expect(before == after, "renderer cannot mutate authoritative report/JSON values")
    expect(!safe.contains(secret), "unknown/nested fields, argv, errors and arbitrary serial text excluded")
    expect(safe.contains("IDECK_FRAME_A"), "whole allowlisted serial marker preserved")
    expect(safe.contains("6.18.35-0-virt"), "only safe kernel-version token retained")
    expect(safe == LinuxProbeReport.render(report: sensitive, serial:
        "IDECK_FRAME_A\nIDECK_FRAME_A " + secret + "\n" + secret + "\nLinux version 6.18.35-0-virt " + secret + "\n"),
        "same snapshot produces deterministic Markdown")
    expect(!LinuxProbeReport.render(report: [:], serial: "IDECK_FRAME_A " + secret).contains("IDECK_FRAME_A"),
           "serial marker with an unapproved suffix is not accepted")
    let invalidPhaseLists: [Any] = [[true, false], [0, 2], "0,1", NSNull()]
    for invalidPhases in invalidPhaseLists {
        let output = LinuxProbeReport.render(report: ["matched_frame_phases": invalidPhases])
        expect(!output.contains("| PASS |"), "invalid frame phase evidence cannot synthesize a pass")
    }
    let malformedNumbers: [Any] = [true, NSNumber(value: true), -1, Double.nan, Double.infinity, "25.5", NSNull()]
    for invalid in malformedNumbers {
        let output = LinuxProbeReport.render(report: ["elapsed_seconds": invalid, "profile_vcpus": invalid])
        expect(cell(output, "Elapsed seconds") == "UNKNOWN", "elapsed rejects boolean, nonfinite, negative or wrong-typed numbers")
        expect(cell(output, "Guest vCPUs") == "UNKNOWN", "integer count rejects malformed numbers")
    }
    expect(cell(LinuxProbeReport.render(report: ["profile_vcpus": 1.5]), "Guest vCPUs") == "UNKNOWN", "fractional integer rejected")
    expect(cell(LinuxProbeReport.render(report: ["elapsed_seconds": 0]), "Elapsed seconds") == "0.000", "valid zero duration retained")
    expect(LinuxProbeReport.filename == "iDeck-Linux-Probe-Report.md", "fixed .md filename")
    let debian = LinuxProbeReport.render(report: ["mode": "debian", "status": "terminal_prepare_failed",
        "storage_failure": "needsRecovery", "import_status": "existing_disk_preserved",
        "terminal_clean_stop": false, "qemu_block_layer_drained_verified": false])
    expect(debian.hasPrefix("# iDeck Debian Console Report"), "Debian report has its own title")
    expect(cell(debian, "Mode") == "DEBIAN ARM64 / EXT4", "Debian is not reported as framebuffer probe")
    expect(cell(debian, "Storage failure") == "needsRecovery", "recovery refusal remains visible")
    expect(cell(debian, "Orderly stop") == "NOT VERIFIED", "failed startup cannot claim clean stop")
    expect(cell(debian, "QEMU block layer drained") == "NOT VERIFIED", "loop return cannot imply backend cleanup")
    let rejected = LinuxProbeReport.render(report: ["mode": "debian", "storage_failure": secret, "import_status": secret])
    expect(!rejected.contains(secret), "Debian failure/import fields remain allowlisted")
    for failure in ["specification", "headerRead", "alreadyExists", "assetMetadata"] {
        expect(cell(LinuxProbeReport.render(report: ["mode": "desktop", "storage_failure": failure]), "Storage failure") == failure,
               "recognized storage failure is not reported as absent")
    }
    var ext4: [String: Any] = ["mode": "desktop", "status": "terminal_prepare_failed",
        "storage_failure": "needsRecovery", "ext4_recover_bit": true, "ext4_state": 2,
        "ext4_last_orphan": UInt32.max, "ext4_error_count": UInt32.max,
        "user_file_contents": secret]
    let ext4Rows = [("ext4_state", "Ext4 state (raw)", "2"),
                    ("ext4_last_orphan", "Ext4 last_orphan", "4294967295"),
                    ("ext4_error_count", "Ext4 error_count", "4294967295")]
    let ext4MD = LinuxProbeReport.render(report: ext4)
    expect(cell(ext4MD, "Ext4 RECOVER bit") == "SET", "recover bit is not inferred from a failed start")
    for (_, label, expected) in ext4Rows { expect(cell(ext4MD, label) == expected, "full unsigned ext4 value preserved") }
    expect(!ext4MD.contains(secret), "file contents excluded from desktop MD")
    expect(ext4MD.contains("do not diagnose why"), "ext4 cause is not guessed")
    ext4["ext4_recover_bit"] = false
    expect(cell(LinuxProbeReport.render(report: ext4), "Ext4 RECOVER bit") == "CLEAR", "explicit clear differs from missing")
    let invalidUnsigned: [Any] = [true, "1", -1, 1.5, Double.nan, UInt64(UInt32.max) + 1, NSNull()]
    for (key, label, _) in ext4Rows {
        for bad in invalidUnsigned {
            var invalid = ext4; invalid[key] = bad
            expect(cell(LinuxProbeReport.render(report: invalid), label) == "UNKNOWN", "invalid unsigned ext4 metadata rejected")
        }
    }
    ext4["ext4_state"] = 65536
    expect(cell(LinuxProbeReport.render(report: ext4), "Ext4 state (raw)") == "UNKNOWN", "16bit state bound preserved")
    expect(cell(debian, "Ext4 RECOVER bit") == "UNKNOWN", "old report does not synthesize ext4 observations")
    let recoveryMD = LinuxProbeReport.render(report: ["mode": "desktop", "recovery_phase": "prepared",
        "recovery_failure": "space", "recovery_assessment_exit": 4, "recovery_replay_exit": 0,
        "recovery_verification_exit": 0, "recovery_checked_image_sha256": String(repeating: "b", count: 64),
        "recovery_watchdog_timeout": "progress",
        "recovery_private_file_contents": secret])
    expect(cell(recoveryMD, "Recovery phase") == "prepared", "known phase is explicit")
    expect(cell(recoveryMD, "Recovery failure") == "space", "space refusal is retained")
    expect(cell(recoveryMD, "Recovery assessment exit") == "4", "nonmutating assessment can report an error")
    expect(cell(recoveryMD, "Guest checked image SHA-256") == String(repeating: "b", count: 64), "checked image is explicit")
    expect(cell(recoveryMD, "Recovery watchdog") == "progress", "recovery timeout is distinct from graphical readiness")
    expect(!recoveryMD.contains(secret), "recovery exports exclude contents")
    let unknownRecovery = LinuxProbeReport.render(report: ["mode": "desktop", "recovery_phase": secret, "recovery_failure": secret,
        "recovery_checked_image_sha256": secret, "recovery_watchdog_timeout": secret])
    expect(!unknownRecovery.contains(secret), "unknown recovery strings remain excluded")
    let failures = [("terminal_startup_timed_out", "Startup readiness timeout"),
                    ("terminal_stop_timed_out", "Orderly Stop timeout"),
                    ("terminal_control_channel_failed", "Control channel failure"),
                    ("terminal_serial_channel_failed", "Serial channel failure"),
                    ("serial_log_write_failed", "Serial log write failure")]
    let invalidFailureValues: [Any] = [NSNull(), NSNumber(value: 1), "true", secret]
    for mode in ["terminal", "debian", "desktop"] {
        for (key, label) in failures {
            expect(cell(LinuxProbeReport.render(report: ["mode": mode, key: true]), label) == "REPORTED", "known failure survives MD export")
            expect(cell(LinuxProbeReport.render(report: ["mode": mode, key: false]), label) == "NONE REPORTED", "explicit false remains separate")
            for bad in invalidFailureValues {
                expect(cell(LinuxProbeReport.render(report: ["mode": mode, key: bad]), label) == "UNKNOWN", "failure rejects non-boolean values")
            }
            expect(cell(LinuxProbeReport.render(report: ["mode": mode]), label) == "UNKNOWN", "legacy report never invents missing failure observations")
        }
    }
    for phase in LinuxStartupPreparation.Phase.allCases {
        let md = LinuxProbeReport.render(report: ["mode": "desktop", "preparation_phase": phase.rawValue])
        expect(cell(md, "Preparation phase") != "UNKNOWN", "production phase is allowlisted")
    }
    let cancelled = LinuxProbeReport.render(report: ["mode": "desktop", "status": "terminal_prepare_cancelled",
        "preparation_cancel_requested": true, "preparation_cancelled_before_qemu": true,
        "terminal_clean_stop": false, "preparation_phase": secret])
    expect(cancelled.contains("startup was cancelled before native entry"), "cancellation is distinct from an unclean VM exit")
    expect(cell(cancelled, "Startup cancellation requested") == "REQUESTED", "request alone is not completion")
    expect(cell(cancelled, "Startup cancelled before native entry") == "CANCELLED BEFORE NATIVE ENTRY", "completion has its own receipt")
    expect(cell(cancelled, "Orderly stop") != "PASS", "cancel is never a clean-stop receipt")
    expect(!cancelled.contains(secret), "preparation strings are allowlisted")
    print("LINUX_MARKDOWN_REPORT_CHECKS_PASS (\(assertions) assertions; actual Foundation renderer, no device/runtime execution)")
}
