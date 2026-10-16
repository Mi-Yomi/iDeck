import Foundation
import Combine
import CryptoKit
import UIKit

/// One QEMU invocation per process. All published state is changed on main;
/// file IO and pixel validation run on the worker's serial queue.
final class LinuxProbeSession: ObservableObject {
    static let shared = LinuxProbeSession()
    @Published private(set) var message = "Enable JIT, then start the Linux probe."
    @Published private(set) var attempted = false
    @Published private(set) var displayReady = false
    @Published private(set) var inputReady = false
    @Published private(set) var shareFiles: [URL] = []
    @Published private(set) var markdownFile: URL?
    @Published private(set) var exportError: String?
    @Published private(set) var jitExecutionReady = false
    @Published private(set) var jitExecutionMessage = "JIT execution has not been verified."
    private var worker: LinuxProbeWorker?

    func claimJIT() {
        precondition(Thread.isMainThread)
        guard !attempted else { return }
        guard JITBootstrap.ready else {
            jitExecutionReady = false
            jitExecutionMessage = "JIT execution has not been verified. Set up and enable JIT."
            return
        }
        // Claim while the debugger is attached. Views read this result without
        // triggering the MAP_JIT execution probe during rendering.
        recordJITExecution(JITBootstrap.prewarm() || JITBootstrap.isLive || JITBootstrap.mapJITResult == true)
    }

    private func recordJITExecution(_ passed: Bool) {
        jitExecutionReady = passed
        jitExecutionMessage = passed ? "JIT execution check passed."
            : (JITBootstrap.lastFailure ?? "JIT execution check did not pass. Open JIT setup.")
    }

    func start() {
        precondition(Thread.isMainThread)
        guard !attempted else { return }
        guard JITBootstrap.ready else {
            jitExecutionReady = false
            jitExecutionMessage = "JIT execution has not been verified. Set up and enable JIT."
            message = "Enable JIT first."; return
        }
        guard JITBootstrap.prewarm() || JITBootstrap.isLive || JITBootstrap.mapJITWorks else {
            recordJITExecution(false)
            message = "JIT did not pass its execution check. Open JIT setup."; return
        }
        recordJITExecution(true)
        guard !LinuxTerminalSession.shared.attempted, !LinuxTerminalSession.debian.attempted else {
            message = "The terminal owns this process. Close and reopen the app."; return
        }
        // The root chooser never creates ContentView/native-runtime screens in
        // this route. These additional guards defend against future routing edits.
        guard !QemuRunner.shared.isRunning, husk_console_loaded_game() == nil else {
            message = "Another runtime owns this process. Close and reopen the app."; return
        }
        attempted = true
        message = "Checking the bundled Linux guest…"
        let documents = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        let session = documents.appendingPathComponent("iDeckLinuxSessions", isDirectory: true)
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        let next = LinuxProbeWorker(owner: self, assets: Bundle.main.bundleURL.appendingPathComponent("iDeckLinuxProbe"),
                                    session: session, prewarmed: JITBootstrap.prewarmed,
                                    metadata: ["app_version": Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "unknown",
                                               "ideck_source_commit": Bundle.main.object(forInfoDictionaryKey: "iDeckSourceCommit") as? String ?? "unknown",
                                               "device_class": UIDevice.current.model,
                                               "jit_execution_check_passed": jitExecutionReady])
        worker = next
        next.start()
    }

    func sendA() {
        precondition(Thread.isMainThread)
        guard inputReady, displayReady else { return }
        guard husk_display_send_key("a", true) else { message = "The keyboard bridge rejected A."; return }
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.05) {
            // Always release the accepted press, even if capture ends meanwhile.
            _ = husk_display_send_key("a", false)
        }
    }

    fileprivate func publish(_ text: String, display: Bool? = nil, input: Bool? = nil) {
        DispatchQueue.main.async {
            self.message = text
            if let display { self.displayReady = display }
            if let input { self.inputReady = input }
        }
    }

    fileprivate func publishExports(files: [URL], markdown: URL?, error: String?) {
        DispatchQueue.main.async {
            self.shareFiles = files
            self.markdownFile = markdown
            self.exportError = error
        }
    }
}

private final class LinuxProbeWorker {
    let owner: LinuxProbeSession
    let assets: URL
    let session: URL
    let prewarmed: Bool
    let metadata: [String: Any]
    let queue = DispatchQueue(label: "ideck.linux.evidence", qos: .utility)
    var timer: DispatchSourceTimer?
    // QEMU retains argv. Both the strings AND pointer array must outlive init.
    // This worker is retained for the entire process, including after loop exit.
    var argv: UnsafeMutablePointer<UnsafeMutablePointer<CChar>?>?
    var report: [String: Any] = [:] // used only on queue, after prepare()
    var frames = Set<Int>()
    var began = Date()
    var terminal = false
    var latestSerial: String?
    var markdownAvailable = false
    var markdownError: String?
    var serialPublished = false

    init(owner: LinuxProbeSession, assets: URL, session: URL, prewarmed: Bool, metadata: [String: Any]) {
        self.owner = owner; self.assets = assets; self.session = session; self.prewarmed = prewarmed
        self.metadata = metadata
    }

    func start() {
        queue.async {
            do {
                let profile = try LinuxGuestProfile.load(from: self.assets)
                let args = try profile.arguments(assets: self.assets, session: self.session)
                // Persist exactly what will be run before entering a C function
                // that can terminate the process on a fatal QEMU startup error.
                try Data(contentsOf: self.assets.appendingPathComponent("profile.json"))
                    .write(to: self.session.appendingPathComponent("profile.json"), options: .atomic)
                self.report = ["schema": 1, "status": "prepared", "argv": args,
                    "husk_commit": "0695248f491cda877f7969d1f0cc89aeede1482e",
                    "os": ProcessInfo.processInfo.operatingSystemVersionString,
                    "started_utc": ISO8601DateFormatter().string(from: Date()),
                    "prewarmed_region_mib": self.prewarmed ? 512 : 0,
                    "requested_tcg_mib": profile.tcgCacheMib,
                    "profile_cpu": profile.cpu, "profile_memory_mib": profile.memoryMib,
                    "profile_vcpus": profile.vcpus, "profile_width": profile.width, "profile_height": profile.height,
                    "linux_boot_observed": false, "guest_probe_completed": false,
                    "steam_executed": false, "physical_screen_verified": false,
                    "accelerated_guest_gpu_verified": false]
                self.report.merge(self.metadata) { _, captured in captured }
                if let executable = Bundle.main.executableURL {
                    let handle = try FileHandle(forReadingFrom: executable)
                    defer { try? handle.close() }
                    var hash = SHA256()
                    while let chunk = try handle.read(upToCount: 1024 * 1024), !chunk.isEmpty { hash.update(data: chunk) }
                    self.report["app_executable_sha256"] = hash.finalize().map { String(format: "%02x", $0) }.joined()
                }
                self.report["app_bundle_version"] = Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "unknown"
                try self.saveReport()
                self.owner.publish("Starting the Linux kernel…")
                let pointers = UnsafeMutablePointer<UnsafeMutablePointer<CChar>?>.allocate(capacity: args.count + 1)
                pointers.initialize(repeating: nil, count: args.count + 1)
                for (index, argument) in args.enumerated() {
                    guard let copy = strdup(argument) else {
                        for offset in 0..<index { free(pointers[offset]) }
                        pointers.deinitialize(count: args.count + 1); pointers.deallocate()
                        throw NSError(domain: "iDeckLinux", code: 1, userInfo: [NSLocalizedDescriptionKey: "Could not allocate QEMU arguments"])
                    }
                    pointers[index] = copy
                }
                self.argv = pointers
                let thread = Thread {
                    HuskLog.log("ideck-linux", "qemu_init; isolated software Linux guest")
                    qemu_init(Int32(args.count), pointers)
                    // qemu_init completed the allocator path; the self-test is
                    // part of Husk's allocator. Kernel execution is checked below.
                    let jitLive = husk_ios_jit_is_available()
                    husk_display_init()
                    self.queue.async {
                        self.report["qemu_init_returned"] = true
                        self.report["jit_available_after_init"] = jitLive
                        self.began = Date()
                        self.beginPolling()
                    }
                    self.owner.publish("Linux is booting…", display: true)
                    qemu_main_loop()
                    self.queue.async {
                        self.finish("guest_stopped", "Linux stopped. Close and reopen the app for another session.")
                        self.owner.publish("Linux stopped. Close and reopen the app.", display: false, input: false)
                    }
                    // No in-process restart or qemu_cleanup: the shared display
                    // listener has no detach API. Tearing it down while MTKView
                    // holds a surface would introduce a use-after-free. The OS
                    // reclaims this single-use runtime on application exit.
                }
                thread.name = "ideck.linux.qemu"
                thread.qualityOfService = .userInteractive
                thread.stackSize = 16 * 1024 * 1024
                thread.start()
            } catch {
                self.finish("prepare_failed", "Linux preparation failed: \(error.localizedDescription)")
            }
        }
    }

    var serialURL: URL { session.appendingPathComponent("linux-serial.log") }
    var resultURL: URL { session.appendingPathComponent("result.json") }
    var markdownURL: URL { session.appendingPathComponent(LinuxProbeReport.filename) }

    func refreshExportFiles() {
        let files = [resultURL, serialURL].filter { FileManager.default.fileExists(atPath: $0.path) }
        serialPublished = files.contains(serialURL)
        let markdown = markdownAvailable && FileManager.default.fileExists(atPath: markdownURL.path) ? markdownURL : nil
        owner.publishExports(files: files, markdown: markdown, error: markdownError)
    }

    func invalidateMarkdown() {
        markdownAvailable = false
        markdownError = "Markdown export failed. You can still save the available raw JSON and serial log."
        try? FileManager.default.removeItem(at: markdownURL)
        refreshExportFiles()
    }

    func saveReport() throws {
        report["matched_frame_phases"] = frames.sorted()
        report["elapsed_seconds"] = Date().timeIntervalSince(began)
        do {
            // Preserve every raw field; Markdown is an additional presentation
            // of this same snapshot, never a replacement for the evidence JSON.
            try JSONSerialization.data(withJSONObject: report, options: [.prettyPrinted, .sortedKeys])
                .write(to: resultURL, options: .atomic)
        } catch {
            invalidateMarkdown()
            throw error
        }
        do {
            try LinuxProbeReport.render(report: report, serial: latestSerial)
                .write(to: markdownURL, atomically: true, encoding: .utf8)
            markdownAvailable = true
            markdownError = nil
            refreshExportFiles()
        } catch {
            // A presentation export failure must not change the guest outcome.
            invalidateMarkdown()
        }
    }

    func finish(_ status: String, _ text: String) {
        guard !terminal else { return }
        terminal = true
        timer?.cancel(); timer = nil
        report["status"] = status
        do { try saveReport() } catch { HuskLog.log("ideck-linux", "could not save result: \(error)") }
        owner.publish(text, input: false)
    }

    func beginPolling() {
        report["status"] = "booting"
        do { try saveReport() } catch {
            finish("report_write_failed", "Could not save the probe report. Close the app."); return
        }
        let source = DispatchSource.makeTimerSource(queue: queue)
        source.schedule(deadline: .now(), repeating: .milliseconds(250))
        source.setEventHandler { [weak self] in self?.poll() }
        timer = source
        source.resume()
    }

    func poll() {
        guard !terminal else { return }
        do {
            if Date().timeIntervalSince(began) > 120 {
                finish("probe_timeout", "The probe timed out. Save the report, then close the app."); return
            }
            guard FileManager.default.fileExists(atPath: serialURL.path) else { return }
            if !serialPublished { refreshExportFiles() }
            let handle = try FileHandle(forReadingFrom: serialURL)
            defer { try? handle.close() }
            let data = try handle.read(upToCount: 2 * 1024 * 1024 + 1) ?? Data()
            guard data.count <= 2 * 1024 * 1024 else {
                finish("serial_limit", "The serial log exceeded the probe limit. Save the report."); return
            }
            let serial = String(decoding: data, as: UTF8.self).replacingOccurrences(of: "\r\n", with: "\n")
            latestSerial = serial
            let serialLines = serial.components(separatedBy: "\n")
            let bootObserved = report["linux_boot_observed"] as? Bool == true || serialLines.contains("IDECK_BOOT_BEGIN")
            let probeCompleted = report["guest_probe_completed"] as? Bool == true || serialLines.contains("IDECK_PROBE_DONE")
            if report["linux_boot_observed"] as? Bool != bootObserved || report["guest_probe_completed"] as? Bool != probeCompleted {
                report["linux_boot_observed"] = bootObserved
                report["guest_probe_completed"] = probeCompleted
                try saveReport()
            }
            if serial.contains("IDECK_PROBE_FAILED:") || serial.contains("Kernel panic") {
                finish("guest_failed", "The Linux guest reported a failure. Save the report."); return
            }
            let phase = serial.contains("IDECK_FRAME_B") ? 1 : 0
            if !frames.contains(phase), serial.contains(phase == 0 ? "IDECK_FRAME_A" : "IDECK_FRAME_B") {
                var info = HuskFrameInfo()
                if husk_display_lock_frame(&info) {
                    var pixels: Data?
                    if info.width == 800, info.height == 600, info.bpp == 32,
                       info.stride >= 3200, info.stride <= 8192, let pointer = info.pixels {
                        pixels = Data(bytes: pointer, count: Int(info.stride) * 600)
                    }
                    husk_display_unlock_frame()
                    if let pixels, LinuxProbeEvidence.matchesFrame(pixels, stride: Int(info.stride), phase: phase) {
                        frames.insert(phase)
                        report["frame_\(phase)_bgra_sha256"] = SHA256.hash(data: pixels).map { String(format: "%02x", $0) }.joined()
                        report["frame_\(phase)_pixels_checked"] = 480000
                        try saveReport()
                    }
                }
            }
            if serial.contains("IDECK_INPUT_READY:keyboard"), serial.contains("IDECK_INPUT_READY:tablet"),
               !serial.contains("IDECK_EVENTS_BEGIN:") {
                owner.publish("Tap the coloured image and press Send A within 20 seconds.", input: true)
            }
            if serial.contains("IDECK_EVENTS_BEGIN:"), !serial.contains("IDECK_PROBE_DONE") {
                owner.publish("Checking captured Linux input…", input: false)
            }
            if serial.contains("IDECK_PROBE_DONE") {
                try LinuxProbeEvidence.validate(serial: serial)
                report["guest_input_verified"] = true
                report["serial_sha256"] = SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
                if frames == Set([0, 1]) {
                    finish("guest_frames_and_input_verified", "Both frame buffers and Linux input verified. Save the report and a screen recording.")
                } else if !frames.contains(0) {
                    finish("first_frame_not_observed", "Input arrived, but the first frame was not verified. Save the report.")
                }
                // A final frame can reach the display bridge after its serial
                // marker. Continue polling until it matches or the deadline.
            }
        } catch {
            finish("evidence_failed", "Probe evidence failed validation: \(error.localizedDescription)")
        }
    }
}
