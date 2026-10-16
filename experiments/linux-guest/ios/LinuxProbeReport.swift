import Foundation
import CoreFoundation

/// A bounded, allowlisted companion to the unchanged JSON and raw serial files.
/// Rendering never accesses files, the device, pairing records or the runtime.
enum LinuxProbeReport {
    static let filename = "iDeck-Linux-Probe-Report.md"

    static func render(report: [String: Any], serial: String? = nil) -> String {
        let debian = report["mode"] as? String == "debian"
        let console = debian || report["mode"] as? String == "terminal"
        let statuses: Set<String> = ["prepared", "booting", "guest_stopped", "prepare_failed", "report_write_failed",
                                     "probe_timeout", "serial_limit", "guest_failed", "evidence_failed",
                                     "guest_frames_and_input_verified", "first_frame_not_observed",
                                     "terminal_prepared", "terminal_running", "terminal_stopping", "terminal_clean_stopped",
                                     "terminal_unclean_stopped", "terminal_prepare_failed", "terminal_stop_failed",
                                     "terminal_startup_timeout", "terminal_stop_timeout"]
        let status = (report["status"] as? String).flatMap { statuses.contains($0) ? $0 : nil }
        let summary: String
        switch status {
        case .some("guest_frames_and_input_verified"):
            summary = "Reported outcome: Linux framebuffer and input probe completed; stage evidence follows."
        case .some("terminal_clean_stopped"):
            summary = "Reported outcome: terminal stopped after guest unmount, QEMU loop return and host disk sync. Close and reopen the app before the next session."
        case .some("terminal_prepared"), .some("terminal_running"), .some("terminal_stopping"):
            summary = "Reported outcome: terminal session is active or stopping; the disk is not yet declared safe to close."
        case .some(let value) where value.hasPrefix("terminal_"):
            summary = "Reported outcome: terminal startup or shutdown is incomplete or failed; orderly stop is not established."
        case .some("prepared"), .some("booting"):
            summary = "Reported outcome: probe in progress; completed checks and pending observations follow."
        case .some(_):
            summary = "Reported outcome: probe incomplete or failed; stage evidence follows."
        case .none:
            summary = "Reported outcome: UNKNOWN; individual evidence fields follow."
        }
        var lines = [debian ? "# iDeck Debian Console Report" : "# iDeck Linux Probe Report", "", summary, "", "## Snapshot", "", "| Field | Value |", "| --- | --- |"]
        func row(_ label: String, _ value: String) { lines.append("| \(label) | \(value) |") }
        row("Version", text(report["app_version"]))
        row("Build", text(report["app_bundle_version"]))
        row("Source commit", hex(report["ideck_source_commit"], count: 40))
        row("Husk commit", hex(report["husk_commit"], count: 40))
        row("Device class", text(report["device_class"]))
        row("OS", text(report["os"]))
        row("Schema", integer(report["schema"]))
        row("Mode", debian ? "DEBIAN ARM64 / EXT4" : (console ? "TERMINAL" : "DIAGNOSTIC PROBE"))
        row("Status", status.map(escape) ?? "UNKNOWN")
        row("Started UTC", text(report["started_utc"]))
        row("Installed executable SHA-256", hex(report["app_executable_sha256"], count: 64))
        row("Serial SHA-256", hex(report["serial_sha256"], count: 64))

        lines += ["", "## Runtime checks", "", "| Check | Result |", "| --- | --- |"]
        row("JIT execution before start", flag(report["jit_execution_check_passed"]))
        row("JIT available after QEMU init", flag(report["jit_available_after_init"]))
        row("QEMU init returned", flag(report["qemu_init_returned"], yes: "RETURNED", no: "NOT OBSERVED"))
        row("Linux init marker", flag(report["linux_boot_observed"], yes: "OBSERVED (Linux init started)", no: "NOT OBSERVED"))
        row("Guest completion marker", flag(report["guest_probe_completed"], yes: "OBSERVED (validation below)", no: "NOT COMPLETED"))
        row("Guest input", flag(report["guest_input_verified"], yes: "PASS (keyboard and tablet evdev)"))
        row("Physical screen", flag(report["physical_screen_verified"], yes: "VERIFIED (reported)"))
        row("Accelerated guest GPU", flag(report["accelerated_guest_gpu_verified"], yes: "VERIFIED (reported)"))
        row("Steam", flag(report["steam_executed"], yes: "REPORTED EXECUTED", no: "NOT RUN"))
        row("Elapsed seconds", decimal(report["elapsed_seconds"]))
        row("Elapsed scope", console
            ? "Session time including asset and disk preparation, terminal use and shutdown; not kernel boot time"
            : (bool(report["qemu_init_returned"]) == true
                ? "Polling after QEMU init, including input interaction; not pure boot time or whole launch time"
                : "UNKNOWN: preparation or early runtime; not an established boot duration"))

        if console {
            lines += ["", "## Persistent terminal", "", "| Check | Result |", "| --- | --- |"]
            row("Terminal ready", flag(report["terminal_ready"]))
            row("Guest disk unmounted", flag(report["terminal_clean_unmount"]))
            row("QEMU loop returned", flag(report["qemu_main_loop_returned"]))
            row("Host disk sync", flag(report["host_disk_fsync_passed"]))
            row("Orderly stop", flag(report["terminal_clean_stop"]))
            row("Disk lock retained until app exits", flag(report["userdata_lock_retained_until_process_exit"], yes: "RETAINED", no: "NOT RETAINED"))
            row("QEMU block layer drained", flag(report["qemu_block_layer_drained_verified"], yes: "VERIFIED (reported)", no: "NOT VERIFIED"))
            row("Serial log truncated", flag(report["log_truncated"], yes: "YES (bounded capture)", no: "NO"))
            if debian {
                let imports: Set<String> = ["not_started", "existing_disk_preserved", "copying_seed", "seed_hash_verified_and_published"]
                let failures: Set<String> = ["needsRecovery", "insufficientSpace", "locked", "assetDigest", "assetSize", "checksum", "filesystem", "ownership", "metadata", "size", "directory", "open", "io", "inspection", "configuration", "uuid", "geometry", "features", "journal", "profile", "assetRead", "assetMetadata"]
                row("Import", (report["import_status"] as? String).flatMap { imports.contains($0) ? $0 : nil } ?? "UNKNOWN")
                row("Storage failure", (report["storage_failure"] as? String).flatMap { failures.contains($0) ? $0 : nil } ?? "NONE RECORDED")
                row("Seed SHA-256", hex(report["debian_seed_sha256"], count: 64))
                row("Production initramfs SHA-256", hex(report["terminal_initramfs_sha256"], count: 64))
            }
            lines += ["", debian ? "Debian runs through chroot from Alpine initramfs. Its ext4 root is persistent; /run is temporary. This is a line console."
                      : "Files in /data use the persistent VFAT volume. The initramfs root is temporary.",
                      "Orderly stop records guest unmount, QEMU loop return and host sync. It does not establish QEMU block-layer teardown; the disk lock stays held until this app exits.",
                      "The framebuffer/input diagnostic checks below are not run in terminal mode.",
                      "This report does not itself verify a file after a second guest boot."]
        }

        lines += ["", "## Framebuffer evidence", "", "| Check | Result |", "| --- | --- |"]
        let phases = framePhases(report["matched_frame_phases"])
        row("Matched framebuffer phases", phases.map { $0.sorted().map { String($0) }.joined(separator: ", ") }.map { $0.isEmpty ? "NONE OBSERVED" : $0 } ?? "UNKNOWN")
        for phase in 0...1 {
            let label = phase == 0 ? "A" : "B"
            row("Frame \(label) RGB validation", phases.map { $0.contains(phase) ? "PASS" : "NOT VERIFIED" } ?? "UNKNOWN")
            row("Frame \(label) pixels checked", integer(report["frame_\(phase)_pixels_checked"]))
            row("Frame \(label) BGRA SHA-256", hex(report["frame_\(phase)_bgra_sha256"], count: 64))
        }
        lines += ["", "Framebuffer validation does not prove physical screen presentation.",
                  "", "## Configuration", "", "| Field | Value |", "| --- | --- |"]
        row("CPU", text(report["profile_cpu"]))
        for (label, key) in [("Guest memory MiB", "profile_memory_mib"), ("Guest vCPUs", "profile_vcpus"),
                             ("Guest width", "profile_width"), ("Guest height", "profile_height"),
                             ("Prewarmed region MiB", "prewarmed_region_mib"), ("Requested TCG MiB", "requested_tcg_mib")] {
            row(label, integer(report[key]))
        }
        lines += ["", "## Safe probe markers", ""]
        lines += markerSummary(serial)
        lines += ["", "## Scope", "", "UNKNOWN means the field was missing, null or had an unexpected type/value.",
                  "Debugger attachment, executable-memory checks, Linux init, framebuffer validation and guest input are separate results.",
                  "An observed completion marker alone is not a validated probe pass.",
                  "The executable hash identifies this installed copy; owner re-signing can change it.",
                  "`result.json` and `linux-serial.log` remain separate evidence files. This summary excludes raw arguments, paths, pairing records and arbitrary serial text.", ""]
        return lines.joined(separator: "\n")
    }

    private static func bool(_ value: Any?) -> Bool? {
        guard let value else { return nil }
        if type(of: value) == Bool.self { return value as? Bool }
        guard let number = value as? NSNumber, CFGetTypeID(number) == CFBooleanGetTypeID() else { return nil }
        return number.boolValue
    }

    private static func flag(_ value: Any?, yes: String = "PASS", no: String = "NOT VERIFIED") -> String {
        guard let result = bool(value) else { return "UNKNOWN" }
        return result ? yes : no
    }

    private static func number(_ value: Any?) -> Double? {
        guard let value, type(of: value) != Bool.self, let number = value as? NSNumber,
              CFGetTypeID(number) != CFBooleanGetTypeID() else { return nil }
        let result = number.doubleValue
        return result.isFinite && result >= 0 && result <= 1_000_000_000 ? result : nil
    }

    private static func integer(_ value: Any?) -> String {
        guard let result = number(value), result.rounded() == result else { return "UNKNOWN" }
        return String(Int64(result))
    }

    private static func decimal(_ value: Any?) -> String {
        guard let result = number(value) else { return "UNKNOWN" }
        return String(format: "%.3f", locale: Locale(identifier: "en_US_POSIX"), result)
    }

    private static func framePhases(_ value: Any?) -> Set<Int>? {
        guard let values = value as? [Any], values.count <= 2 else { return nil }
        var result = Set<Int>()
        for value in values {
            guard let phase = number(value), phase == 0 || phase == 1,
                  result.insert(Int(phase)).inserted else { return nil }
        }
        return result
    }

    private static func text(_ value: Any?) -> String {
        guard let string = value as? String, !string.isEmpty else { return "UNKNOWN" }
        return escape(string)
    }

    private static func hex(_ value: Any?, count: Int) -> String {
        guard let string = value as? String, string.utf8.count == count,
              string.utf8.allSatisfy({ (48...57).contains($0) || (65...70).contains($0) || (97...102).contains($0) })
        else { return "UNKNOWN" }
        return string.lowercased()
    }

    private static func escape(_ value: String) -> String {
        let scalars = value.unicodeScalars.prefix(160)
        var result = ""
        for scalar in scalars {
            switch scalar.properties.generalCategory {
            case .control, .format, .lineSeparator, .paragraphSeparator:
                result += "&#91;U+\(String(scalar.value, radix: 16, uppercase: true))&#93;"
            default:
                if scalar.value < 128 && scalar.value != 32
                    && !(48...57).contains(scalar.value) && !(65...90).contains(scalar.value) && !(97...122).contains(scalar.value) {
                    result += "&#\(scalar.value);"
                } else {
                    result.unicodeScalars.append(scalar)
                }
            }
        }
        if value.unicodeScalars.dropFirst(160).first != nil { result += " (truncated)" }
        return result
    }

    private static func markerSummary(_ serial: String?) -> [String] {
        guard let serial else { return ["Serial snapshot: NOT PROVIDED."] }
        let allowed = ["IDECK_BOOT_BEGIN", "IDECK_FB_MMAP_WRITE_OK", "IDECK_FRAME_A", "IDECK_FRAME_B",
                       "IDECK_INPUT_READY:keyboard", "IDECK_INPUT_READY:tablet", "IDECK_EVENTS_BEGIN:keyboard",
                       "IDECK_EVENTS_END:keyboard", "IDECK_EVENTS_BEGIN:tablet", "IDECK_EVENTS_END:tablet", "IDECK_PROBE_DONE",
                       "IDECK_PROBE_FAILED:no_framebuffer", "IDECK_PROBE_FAILED:framebuffer_dimensions",
                       "IDECK_PROBE_FAILED:framebuffer_depth", "IDECK_PROBE_FAILED:no_keyboard", "IDECK_PROBE_FAILED:no_tablet",
                       "IDECK_PROBE_FAILED:empty_keyboard", "IDECK_PROBE_FAILED:empty_tablet",
                       "IDECK_MODULE_LOAD_FAILED:virtio_pci", "IDECK_MODULE_LOAD_FAILED:virtio_gpu",
                       "IDECK_MODULE_LOAD_FAILED:virtio_input", "IDECK_MODULE_LOAD_FAILED:evdev"]
        let allowedSet = Set(allowed)
        let bounded = String(decoding: serial.utf8.prefix(2 * 1024 * 1024), as: UTF8.self)
        let kernelPattern = #"^(?:\[ {0,16}[0-9]{1,12}(?:\.[0-9]{1,9})?\] {0,16})?Linux version ([0-9]{1,6}\.[0-9]{1,6}(?:\.[0-9]{1,6})?(?:[-+._][A-Za-z0-9._+-]{1,48})?)(?: |$)"#
        let kernel = try? NSRegularExpression(pattern: kernelPattern)
        var observed = Set<String>()
        var version: String?
        for line in bounded.split(whereSeparator: { $0 == "\n" || $0 == "\r" }) {
            // Match whole lines only: a marker prefix followed by a secret is
            // not safe to share. Never append the rest of a kernel log line.
            if line.utf8.count <= 64 {
                let string = String(line)
                if allowedSet.contains(string) { observed.insert(string) }
            }
            let prefix = String(decoding: line.utf8.prefix(256), as: UTF8.self)
            if version == nil, let match = kernel?.firstMatch(in: prefix, range: NSRange(prefix.startIndex..., in: prefix)),
               let range = Range(match.range(at: 1), in: prefix), prefix[range].utf8.count <= 80 {
                version = String(prefix[range])
            }
        }
        var result = allowed.filter(observed.contains).map { "- `\($0)`" }
        if let version { result.append("- Kernel version token: `\(version)`") }
        if result.isEmpty { result = ["No allowlisted probe markers or kernel version token observed."] }
        return result
    }
}
