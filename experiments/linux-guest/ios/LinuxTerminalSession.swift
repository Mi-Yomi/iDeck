import Foundation
import Combine
import UIKit
import Darwin
import CryptoKit

/// A real local serial console. One QEMU invocation is allowed per process.
final class LinuxTerminalSession: ObservableObject {
    static let shared = LinuxTerminalSession()
    static let debian = LinuxTerminalSession(isDebian: true)
    let isDebian: Bool
    init(isDebian: Bool = false) {
        self.isDebian = isDebian
        if isDebian { message = "Enable JIT, then start Debian with its separate persistent ext4 disk." }
    }
    @Published fileprivate(set) var message = "Enable JIT, then start the local Linux terminal."
    @Published fileprivate(set) var attempted = false
    @Published fileprivate(set) var running = false
    @Published fileprivate(set) var ready = false
    @Published fileprivate(set) var stopping = false
    @Published fileprivate(set) var canStop = false
    @Published fileprivate(set) var cleanStopped = false
    @Published fileprivate(set) var transcript = ""
    @Published fileprivate(set) var shareFiles: [URL] = []
    @Published fileprivate(set) var markdownFile: URL?
    @Published fileprivate(set) var exportError: String?
    @Published fileprivate(set) var jitExecutionReady = false
    @Published fileprivate(set) var jitExecutionMessage = "JIT execution has not been verified."
    @Published fileprivate(set) var diagnosticReports: [URL] = []
    @Published fileprivate(set) var diagnosticsMessage = "Startup reports can be exported without starting Linux."
    @Published fileprivate(set) var diagnosticsError: String?
    private var diagnostics: LinuxTerminalDiagnostics?
    private var diagnosticJournal: LinuxTerminalDiagnostics.Journal?
    private var recoveredDiagnostics = false
    private var diagnosticAttemptIDs: [URL: String] = [:]
    private var worker: LinuxTerminalWorker?

    /// Recovery/export has no JIT, QEMU or userdata dependencies. Run before
    /// any automatic JIT check; reading reports never starts a new attempt.
    func recoverDiagnostics() {
        precondition(Thread.isMainThread)
        diagnosticReports = []
        diagnosticAttemptIDs = [:]
        do {
            let store = try diagnosticStore()
            var previous = try store.recover(excluding: diagnosticJournal?.id)
            if !recoveredDiagnostics {
                if let latest = previous.first { try store.preservePreviousLogs(id: latest.id) }
                recoveredDiagnostics = true
                previous = try store.recover(excluding: diagnosticJournal?.id)
            }
            var files = [URL]()
            var ids = [URL: String]()
            if let current = diagnosticJournal {
                let file = try store.export(current.snapshot(), previousProcess: false)
                files.append(file); ids[file] = current.id
            }
            for snapshot in previous {
                let file = try store.export(snapshot, previousProcess: true)
                files.append(file); ids[file] = snapshot.id
            }
            diagnosticAttemptIDs = ids
            diagnosticReports = files
            diagnosticsError = nil
            diagnosticsMessage = files.isEmpty ? "No saved startup attempt yet. Linux has not been started by this action."
                : "Saved startup reports are available. An interrupted previous process is not a diagnosed crash cause."
        } catch { diagnosticFailure() }
    }

    /// Owner selects one saved attempt explicitly. Never open rotating logs,
    /// run recovery capture, start JIT/VM, or replace the preserved snapshots.
    func exportNativeDiagnostics(for report: URL) -> URL? {
        precondition(Thread.isMainThread)
        do {
            guard let id = diagnosticAttemptIDs[report] else { throw LinuxTerminalDiagnostics.Problem.invalid }
            let store = try diagnosticStore()
            let current = diagnosticJournal?.id == id
            let snapshot: LinuxTerminalDiagnostics.Snapshot
            if current, let journal = diagnosticJournal { snapshot = try journal.snapshot() }
            else { snapshot = try store.snapshot(id: id) }
            let file = try store.exportNativeSummary(snapshot, previousProcess: !current)
            diagnosticsError = nil
            return file
        } catch {
            diagnosticFailure()
            return nil
        }
    }

    private func diagnosticStore() throws -> LinuxTerminalDiagnostics {
        if let diagnostics { return diagnostics }
        let store = try LinuxTerminalDiagnostics(documents:
            FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0])
        diagnostics = store
        return store
    }
    private func journal() throws -> LinuxTerminalDiagnostics.Journal {
        if let diagnosticJournal { return diagnosticJournal }
        // Capture previous logs before creating an attempt that could otherwise
        // be mistaken for the previous launch during subsequent UI refreshes.
        if !recoveredDiagnostics { recoverDiagnostics() }
        guard recoveredDiagnostics else { throw LinuxTerminalDiagnostics.Problem.read }
        let next = try diagnosticStore().begin(
            source: Bundle.main.object(forInfoDictionaryKey: "iDeckSourceCommit") as? String ?? "UNKNOWN",
            build: Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "UNKNOWN")
        diagnosticJournal = next
        return next
    }
    fileprivate func diagnosticFailure() {
        diagnosticsError = "Startup diagnostics could not be fully saved or recovered. No complete diagnostic record is promised; preserve existing files before another launch."
        HuskLog.log("ideck-terminal", "startup diagnostic IO failed; raw error text omitted")
    }


    func noteJITEnable(dispatched: Bool = false) -> Bool {
        precondition(Thread.isMainThread)
        do { try journal().record(dispatched ? .jitEnableDispatched : .jitEnableBegin); return true }
        catch { diagnosticFailure(); return false }
    }

    func claimJIT() {
        precondition(Thread.isMainThread)
        guard !attempted else { return }
        do {
            let journal = try journal()
            try journal.record(.jitClaimBegin)
            guard JITBootstrap.ready else {
                try journal.record(.jitUnavailable); recordJIT(false); return
            }
            let passed = JITBootstrap.prewarm() || JITBootstrap.isLive || JITBootstrap.mapJITResult == true
            try journal.record(.jitClaimReturned)
            recordJIT(passed)
        } catch { diagnosticFailure() }
    }

    private func recordJIT(_ passed: Bool) {
        jitExecutionReady = passed
        jitExecutionMessage = passed ? "JIT execution check passed."
            : "JIT execution has not been verified. Open JIT setup."
    }

    func start() {
        precondition(Thread.isMainThread)
        guard !attempted else { return }
        let diagnostic: LinuxTerminalDiagnostics.Journal
        do {
            diagnostic = try journal()
            try diagnostic.record(.startRequested)
            try diagnostic.record(.jitReadyBegin)
            let ready = JITBootstrap.ready
            try diagnostic.record(.jitReadyReturned)
            guard ready else {
                try diagnostic.record(.startRejected); recordJIT(false); message = "Enable JIT first."; return
            }
            try diagnostic.record(.jitExecutionBegin)
            let passed = JITBootstrap.prewarm() || JITBootstrap.isLive || JITBootstrap.mapJITWorks
            try diagnostic.record(.jitExecutionReturned)
            guard passed else {
                try diagnostic.record(.startRejected)
                recordJIT(false); message = "JIT did not pass its execution check. Open JIT setup."; return
            }
            recordJIT(true)
            try diagnostic.record(.runtimeOwnershipBegin)
            let runtimeFree = !LinuxProbeSession.shared.attempted && !LinuxTerminalSession.shared.attempted
                && !LinuxTerminalSession.debian.attempted && !QemuRunner.shared.isRunning && husk_console_loaded_game() == nil
            try diagnostic.record(.runtimeOwnershipReturned)
            guard runtimeFree else {
                try diagnostic.record(.startRejected)
                message = "Another runtime owns this process. Close and reopen the app."; return
            }
        } catch {
            diagnosticFailure(); message = "Startup journal is unavailable. Export existing diagnostics before trying again."; return
        }
        attempted = true
        let documents: URL
        do {
            // Resolve only the system-provided existing prefix. The userdata
            // directory is appended afterwards and must pass its own lstat walk.
            try diagnostic.record(.documentsBegin)
            documents = try LinuxTerminalDisk.trustedDirectory(
                FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0])
            try diagnostic.record(.documentsReturned)
        } catch {
            do { try diagnostic.record(.preparationFailed, failure: Self.failure(error)) } catch { diagnosticFailure() }
            HuskLog.log("ideck-terminal", "Documents validation or diagnostic write failed")
            message = "The app's Documents directory could not be validated. Close and reopen the app."
            return
        }
        let root = documents.appendingPathComponent(isDebian ? "iDeckDebian" : "iDeckLinux", isDirectory: true)
        let session = documents.appendingPathComponent("iDeckLinuxSessions", isDirectory: true)
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        let metadata: [String: Any] = [
            "app_version": Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "unknown",
            "app_bundle_version": Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "unknown",
            "ideck_source_commit": Bundle.main.object(forInfoDictionaryKey: "iDeckSourceCommit") as? String ?? "unknown",
            "device_class": UIDevice.current.model,
            "os": ProcessInfo.processInfo.operatingSystemVersionString,
            "jit_execution_check_passed": jitExecutionReady,
            "prewarmed_region_mib": JITBootstrap.prewarmed ? 512 : 0,
        ]
        let next = LinuxTerminalWorker(owner: self, bundle: Bundle.main.bundleURL, session: session,
                                       dataDirectory: root, metadata: metadata, diagnostic: diagnostic)
        worker = next
        message = isDebian ? "Checking Debian assets and importing or opening the separate ext4 disk…"
            : "Checking terminal assets and the persistent user-data disk…"
        next.start()
    }

    fileprivate static func failure(_ error: Error) -> LinuxTerminalDiagnostics.Failure {
        if let value = error as? LinuxTerminalProfile.Invalid {
            return LinuxTerminalDiagnostics.Failure(rawValue: String(describing: value)) ?? .unknown
        }
        if let value = error as? LinuxGuestProfile.Invalid {
            return LinuxTerminalDiagnostics.Failure(rawValue: String(describing: value)) ?? .unknown
        }
        return .unknown
    }

    func send(_ text: String) {
        precondition(Thread.isMainThread)
        guard ready, !stopping, text.utf8.count <= 16384 else { return }
        worker?.send(Data(text.utf8))
    }

    func sendLine(_ line: String) { send(line + "\r") }
    func sendControl(_ byte: UInt8) {
        precondition(Thread.isMainThread)
        guard ready, !stopping, byte == 3 || byte == 4 || byte == 9 || byte == 27 else { return }
        worker?.send(Data([byte]))
    }

    func stop() {
        precondition(Thread.isMainThread)
        guard canStop, !stopping else { return }
        NotificationCenter.default.post(name: Notification.Name("iDeck.releaseDisplayInput"), object: nil)
        stopping = true
        canStop = false
        ready = false
        message = "Stopping guest processes, syncing and unmounting user data…"
        worker?.stop()
    }

    fileprivate func publish(_ update: @escaping (LinuxTerminalSession) -> Void) {
        DispatchQueue.main.async { update(self) }
    }
}

/// A bounded, nonblocking peer of QEMU's already-connected Unix socket.
private final class LinuxTerminalSocket {
    let queue: DispatchQueue
    private(set) var peer: Int32 = -1
    private(set) var qemu: Int32 = -1
    private var handedToQEMU = false
    private var reader: DispatchSourceRead?
    private var writer: DispatchSourceWrite?
    private var pending = Data()
    var received: ((Data) -> Void)?
    var disconnected: (() -> Void)?

    init(queue: DispatchQueue) throws {
        self.queue = queue
        var sockets: [Int32] = [-1, -1]
        guard socketpair(AF_UNIX, SOCK_STREAM, 0, &sockets) == 0 else { throw LinuxTerminalProfile.Invalid.io }
        peer = sockets[0]; qemu = sockets[1]
        var enabled: Int32 = 1
        guard setsockopt(peer, SOL_SOCKET, SO_NOSIGPIPE, &enabled, socklen_t(MemoryLayout<Int32>.size)) == 0,
              setsockopt(qemu, SOL_SOCKET, SO_NOSIGPIPE, &enabled, socklen_t(MemoryLayout<Int32>.size)) == 0,
              fcntl(peer, F_SETFL, fcntl(peer, F_GETFL) | O_NONBLOCK) == 0 else {
            Darwin.close(peer); Darwin.close(qemu); peer = -1; qemu = -1
            throw LinuxTerminalProfile.Invalid.io
        }
    }

    func beginReading() {
        let source = DispatchSource.makeReadSource(fileDescriptor: peer, queue: queue)
        source.setEventHandler { [weak self] in self?.readAvailable() }
        reader = source
        source.resume()
    }

    func handToQEMU() { handedToQEMU = true }

    func enqueue(_ data: Data) throws {
        guard peer >= 0, data.count <= 16384, pending.count + data.count <= 65536 else { throw LinuxTerminalProfile.Invalid.io }
        pending.append(data)
        try flush()
    }

    private func flush() throws {
        while peer >= 0, !pending.isEmpty {
            let count = pending.withUnsafeBytes { Darwin.write(peer, $0.baseAddress, $0.count) }
            if count < 0, errno == EINTR { continue }
            if count < 0, errno == EAGAIN || errno == EWOULDBLOCK {
                if writer == nil {
                    let source = DispatchSource.makeWriteSource(fileDescriptor: peer, queue: queue)
                    source.setEventHandler { [weak self] in
                        guard let self else { return }
                        do { try self.flush() } catch { self.closePeer(); self.disconnected?() }
                    }
                    writer = source; source.resume()
                }
                return
            }
            guard count > 0 else { throw LinuxTerminalProfile.Invalid.io }
            pending.removeFirst(count)
        }
        writer?.cancel(); writer = nil
    }

    private func readAvailable() {
        guard peer >= 0 else { return }
        var bytes = [UInt8](repeating: 0, count: 4096)
        var total = 0
        while peer >= 0, total < 65536 {
            let count = Darwin.read(peer, &bytes, 4096)
            if count < 0, errno == EINTR { continue }
            if count < 0, errno == EAGAIN || errno == EWOULDBLOCK { return }
            guard count > 0 else { closePeer(); disconnected?(); return }
            total += count
            received?(Data(bytes.prefix(count)))
        }
    }

    func drainAvailable() { readAvailable() }

    func closePeer() {
        reader?.cancel(); reader = nil
        writer?.cancel(); writer = nil
        pending.removeAll()
        if peer >= 0 { Darwin.close(peer); peer = -1 }
    }

    func closeUnused() {
        closePeer()
        if !handedToQEMU, qemu >= 0 { Darwin.close(qemu); qemu = -1 }
    }
}

private final class LinuxTerminalWorker {
    let owner: LinuxTerminalSession
    let bundle: URL
    let session: URL
    let dataDirectory: URL
    let metadata: [String: Any]
    let queue = DispatchQueue(label: "ideck.linux.terminal", qos: .userInitiated)
    let diagnostic: LinuxTerminalDiagnostics.Journal
    var disk: LinuxConsoleDisk?
    var lifecycle = LinuxConsoleLifecycle()
    var serial: LinuxTerminalSocket?
    var control: LinuxTerminalSocket?
    var argv: UnsafeMutablePointer<UnsafeMutablePointer<CChar>?>?
    var report: [String: Any] = [:]
    var transcript = Data()
    var controlLines = Data()
    var enteredQEMU = false
    var startupAborted = false
    var ready = false
    var guestWasReady = false
    var stopRequested = false
    var cleanUnmount = false
    var loopReturned = false
    var finalized = false
    var stopFailed = false
    var began = Date()
    var markdownAvailable = false
    var exportError: String?
    var logHandle: FileHandle?
    var loggedBytes = 0
    var logTruncated = false
    var transcriptPublishScheduled = false
    var transcriptRevision: UInt64 = 0

    init(owner: LinuxTerminalSession, bundle: URL, session: URL, dataDirectory: URL, metadata: [String: Any],
         diagnostic: LinuxTerminalDiagnostics.Journal) {
        self.owner = owner; self.bundle = bundle; self.session = session
        self.dataDirectory = dataDirectory; self.metadata = metadata; self.diagnostic = diagnostic
    }

    /// Called synchronously on the thread reaching the boundary, including the
    /// QEMU thread. A post-entry diagnostic IO error must not tear down QEMU or
    /// release the userdata lock; it is made visible on the UI instead.
    private func checkpoint(_ stage: LinuxTerminalDiagnostics.Stage, failure: LinuxTerminalDiagnostics.Failure? = nil) {
        do { try diagnostic.record(stage, failure: failure) }
        catch { owner.publish { $0.diagnosticFailure() } }
    }

    /// Before C has adopted either socket or touched the disk, a journal
    /// synchronization failure can safely prevent entry. After entry the
    /// checkpoint helper preserves runtime ownership even if diagnostics fail.
    private func prepareNativeEntry(serial: LinuxTerminalSocket, control: LinuxTerminalSocket) -> Bool {
        do {
            try queue.sync {
                guard let disk = self.disk else { throw LinuxTerminalProfile.Invalid.diskOwnership }
                try disk.validateOwnership()
            }
            try diagnostic.record(.qemuInitBegin)
        }
        catch {
            let failure = LinuxTerminalSession.failure(error)
            let journalFailed = error is LinuxTerminalDiagnostics.Problem
            queue.async {
                self.checkpoint(.preparationFailed, failure: failure)
                self.startupAborted = true
                serial.closeUnused(); control.closeUnused()
                try? self.logHandle?.close(); self.logHandle = nil
                self.disk?.closeUnused()
                self.report["status"] = "terminal_prepare_failed"
                self.persist()
                self.owner.publish {
                    if journalFailed { $0.diagnosticFailure() }
                    $0.message = "Startup disk ownership or journal check failed. Linux was not started. Existing user data was preserved; close and reopen the app."
                }
            }
            return false
        }
        queue.sync {
            self.enteredQEMU = true
            self.lifecycle.record(.entered)
            self.report["userdata_lock_retained_until_process_exit"] = true
            self.persist()
            serial.handToQEMU(); control.handToQEMU()
        }
        return true
    }

    func start() {
        queue.async {
            do {
                try LinuxDesktopDisk.validateDirectory(self.session, allowingMissing: true)
                try FileManager.default.createDirectory(at: self.session, withIntermediateDirectories: true)
                self.report = self.metadata
                self.report["mode"] = self.owner.isDebian ? "debian" : "terminal"
                self.report["status"] = "terminal_prepared"
                self.report["terminal_clean_stop"] = false
                self.report["qemu_block_layer_drained_verified"] = false
                self.report["import_status"] = "not_started"
                self.persist()
                let assets = self.bundle.appendingPathComponent(self.owner.isDebian ? "iDeckDebian" : "iDeckLinuxTerminal")
                let probe = self.bundle.appendingPathComponent("iDeckLinuxProbe")
                try self.diagnostic.record(.assetsBegin)
                let terminal = self.owner.isDebian ? nil : (try LinuxTerminalProfile.load(from: assets))
                let debian = self.owner.isDebian ? (try LinuxDebianProfile.load(from: assets)) : nil
                let desktop = self.owner.isDebian ? (try LinuxDesktopProfile.load(from: assets)) : nil
                try self.diagnostic.record(.assetsReturned)
                try self.diagnostic.record(.diskBegin)
                var preparedMetadata: [String: Any]
                if let desktop, let debian {
                    self.report["debian_seed_sha256"] = desktop.rootfs.sha256
                    self.report["terminal_initramfs_sha256"] = debian.initramfs.sha256
                    let path = self.dataDirectory.appendingPathComponent("rootfs-v1.raw")
                    var state = stat()
                    // lstat distinguishes absent from a dangling link or IO error.
                    if lstat(path.path, &state) == 0 {
                        self.report["import_status"] = "existing_disk_preserved"; self.persist()
                        self.disk = try desktop.openExisting(in: self.dataDirectory)
                    } else {
                        guard errno == ENOENT else { throw LinuxDesktopDisk.Invalid.inspection }
                        self.report["import_status"] = "copying_seed"; self.persist()
                        self.disk = try desktop.provision(in: self.dataDirectory, assets: assets)
                        self.report["import_status"] = "seed_hash_verified_and_published"; self.persist()
                    }
                    preparedMetadata = ["profile_cpu": "cortex-a72", "profile_memory_mib": 1024, "profile_vcpus": 4,
                        "profile_width": 800, "profile_height": 600, "requested_tcg_mib": 256,
                        "userdata_size_bytes": desktop.image.sizeBytes, "userdata_filesystem": "ext4",
                        "debian_seed_sha256": desktop.rootfs.sha256, "terminal_initramfs_sha256": debian.initramfs.sha256]
                } else if let profile = terminal {
                    self.disk = try profile.openDisk(in: self.dataDirectory, assets: assets)
                    preparedMetadata = ["profile_cpu": profile.cpu, "profile_memory_mib": profile.memoryMib, "profile_vcpus": profile.vcpus,
                        "profile_width": profile.width, "profile_height": profile.height, "requested_tcg_mib": profile.tcgCacheMib,
                        "userdata_size_bytes": profile.diskSizeBytes, "userdata_filesystem": profile.filesystem,
                        "terminal_initramfs_sha256": profile.initramfs.sha256]
                } else { throw LinuxTerminalProfile.Invalid.configuration }
                try self.diagnostic.record(.diskReturned)
                try self.diagnostic.record(.socketsBegin)
                self.serial = try LinuxTerminalSocket(queue: self.queue)
                self.control = try LinuxTerminalSocket(queue: self.queue)
                guard let disk = self.disk, let serial = self.serial, let control = self.control else { throw LinuxTerminalProfile.Invalid.io }
                try self.diagnostic.record(.socketsReturned)
                try self.diagnostic.record(.argumentsBegin)
                let args: [String]
                let bootSession = self.session.appendingPathComponent("qemu")
                if let profile = terminal, let terminalDisk = disk as? LinuxTerminalDisk {
                    args = try profile.arguments(probeAssets: probe, terminalAssets: assets, session: bootSession,
                        disk: terminalDisk, serialFD: serial.qemu, controlFD: control.qemu)
                } else if let profile = debian, let desktopDisk = disk as? LinuxDesktopDisk {
                    args = try profile.arguments(probeAssets: probe, assets: assets, session: bootSession,
                        disk: desktopDisk, serialFD: serial.qemu, controlFD: control.qemu)
                } else { throw LinuxTerminalProfile.Invalid.configuration }
                try self.diagnostic.record(.argumentsReturned)
                try self.diagnostic.record(.reportBegin)
                guard FileManager.default.createFile(atPath: self.serialURL.path, contents: Data()) else { throw LinuxTerminalProfile.Invalid.io }
                self.logHandle = try FileHandle(forWritingTo: self.serialURL)
                self.report.merge(preparedMetadata) { _, next in next }
                self.report.merge(["schema": 1, "status": "terminal_prepared", "argv": args,
                    "husk_commit": "0695248f491cda877f7969d1f0cc89aeede1482e",
                    "started_utc": ISO8601DateFormatter().string(from: Date()),
                    "log_truncated": false,
                    "elapsed_scope": "terminal_session_including_preparation",
                    "qemu_block_layer_drained_verified": false,
                    "steam_executed": false, "physical_screen_verified": false, "accelerated_guest_gpu_verified": false]) { _, next in next }
                self.report["terminal_profile_sha256"] = try self.digest(assets.appendingPathComponent(self.owner.isDebian ? "debian-profile.json" : "terminal-profile.json"))
                if let executable = Bundle.main.executableURL { self.report["app_executable_sha256"] = try self.digest(executable) }
                try self.saveReport()
                try self.diagnostic.record(.reportReturned)
                serial.received = { [weak self] bytes in self?.receiveSerial(bytes) }
                control.received = { [weak self] bytes in self?.receiveControl(bytes) }
                serial.disconnected = { [weak self] in self?.channelDisconnected(control: false) }
                control.disconnected = { [weak self] in self?.channelDisconnected(control: true) }
                serial.beginReading(); control.beginReading()
                try self.diagnostic.record(.argvBegin)
                let pointers = UnsafeMutablePointer<UnsafeMutablePointer<CChar>?>.allocate(capacity: args.count + 1)
                pointers.initialize(repeating: nil, count: args.count + 1)
                for (index, argument) in args.enumerated() {
                    guard let value = strdup(argument) else {
                        for offset in 0..<index { free(pointers[offset]) }
                        pointers.deinitialize(count: args.count + 1); pointers.deallocate()
                        throw LinuxTerminalProfile.Invalid.io
                    }
                    pointers[index] = value
                }
                self.argv = pointers
                try self.diagnostic.record(.argvReturned)
                try self.diagnostic.record(.threadStarting)
                self.scheduleStartupTimeout()
                let thread = Thread {
                    guard self.prepareNativeEntry(serial: serial, control: control) else { return }
                    qemu_init(Int32(args.count), pointers)
                    self.checkpoint(.qemuInitReturned)
                    self.checkpoint(.nativeJITCheckBegin)
                    let jitAvailable = husk_ios_jit_is_available()
                    self.checkpoint(.nativeJITCheckReturned)
                    // Keep the established software display lifecycle. No cleanup
                    // or second initialization is safe with its live listener.
                    self.checkpoint(.displayInitBegin)
                    husk_display_init()
                    self.checkpoint(.displayInitReturned)
                    self.queue.async {
                        self.report["qemu_init_returned"] = true
                        self.report["jit_available_after_init"] = jitAvailable
                        self.report["status"] = "terminal_running"
                        self.persist()
                        let alreadyReady = self.ready
                        self.owner.publish {
                            $0.running = true
                            if !alreadyReady { $0.message = "Linux is starting the local terminal…" }
                        }
                    }
                    self.checkpoint(.mainLoopBegin)
                    qemu_main_loop()
                    self.checkpoint(.mainLoopReturned)
                    LinuxQEMUThreadLifetime.retainCurrentThread {
                        self.checkpoint(.qemuOwnerThreadRetained)
                        self.queue.async {
                            self.report["qemu_owner_thread_retained_until_process_exit"] = true
                            self.didReturnFromQEMU()
                        }
                    }
                }
                thread.name = "ideck.linux.terminal.qemu"
                thread.qualityOfService = .userInteractive
                thread.stackSize = 16 * 1024 * 1024
                thread.start()
            } catch {
                self.checkpoint(.preparationFailed, failure: LinuxTerminalSession.failure(error))
                HuskLog.log("ideck-terminal", "terminal preparation failed: \(LinuxTerminalSession.failure(error).rawValue)")
                if error is LinuxTerminalDiagnostics.Problem { self.owner.publish { $0.diagnosticFailure() } }
                self.serial?.closeUnused(); self.control?.closeUnused()
                try? self.logHandle?.close(); self.logHandle = nil
                if !self.enteredQEMU { self.disk?.closeUnused() }
                self.report["status"] = "terminal_prepare_failed"
                if let failure = error as? LinuxDesktopDisk.Invalid { self.report["storage_failure"] = String(describing: failure) }
                if let failure = error as? LinuxDesktopProfile.Invalid { self.report["storage_failure"] = String(describing: failure) }
                self.persist()
                let needsRecovery = (error as? LinuxDesktopDisk.Invalid) == .needsRecovery
                let noSpace = (error as? LinuxDesktopDisk.Invalid) == .insufficientSpace
                let busy = (error as? LinuxDesktopDisk.Invalid) == .locked
                let badSeed = (error as? LinuxDesktopProfile.Invalid) == .assetDigest
                self.owner.publish {
                    $0.message = needsRecovery ? "The Debian disk needs offline ext4 recovery after an unclean shutdown. It was not recreated or mounted. Export the report and preserve the disk before repair."
                        : noSpace ? "Not enough free space to import Debian (512 MiB plus 32 MiB reserve). Existing disks were preserved. Free space and reopen the app to retry."
                        : busy ? "The Debian disk or import is busy. It was not replaced. Close the owning session before retrying."
                        : badSeed ? "The Debian seed failed its SHA-256 check. No disk was published. Restore the correct app payload before retrying; existing disks were preserved."
                        : "Console preparation failed. The existing disk was not replaced. Export the report; close and reopen the app to retry."
                }
            }
        }
    }

    func send(_ bytes: Data) {
        queue.async {
            guard self.ready, !self.stopRequested, !self.loopReturned else { return }
            do { try self.serial?.enqueue(bytes) } catch { self.channelDisconnected(control: false) }
        }
    }

    func stop() {
        queue.async {
            guard self.guestWasReady, !self.stopRequested, !self.loopReturned,
                  let control = self.control, control.peer >= 0 else { return }
            self.checkpoint(.stopRequested)
            self.stopRequested = true
            self.lifecycle.record(.stop)
            self.report["status"] = "terminal_stopping"
            self.persist()
            do { try control.enqueue(Data("IDECK_STOP_V1\n".utf8)) }
            catch { self.channelDisconnected(control: true) }
            self.scheduleStopTimeout()
        }
    }

    private func receiveSerial(_ bytes: Data) {
        if let logHandle {
            let remaining = max(0, 2 * 1024 * 1024 - loggedBytes)
            do {
                let kept = Data(bytes.prefix(remaining))
                try logHandle.write(contentsOf: kept)
                loggedBytes += kept.count
                if bytes.count > remaining, !logTruncated {
                    logTruncated = true
                    report["log_truncated"] = true
                    persist()
                }
            } catch {
                report["serial_log_write_failed"] = true
                try? logHandle.close(); self.logHandle = nil
                persist()
            }
        }
        transcript.append(bytes)
        if transcript.count > 256 * 1024 { transcript.removeFirst(transcript.count - 256 * 1024) }
        transcriptRevision &+= 1
        scheduleTranscriptPublication()
    }

    private func scheduleTranscriptPublication() {
        // Coalesce fast guest output: a command such as `yes` must not enqueue
        // an unbounded number of large strings on the UI's main queue.
        if !transcriptPublishScheduled {
            transcriptPublishScheduled = true
            queue.asyncAfter(deadline: .now() + .milliseconds(100)) {
                let text = String(decoding: self.transcript, as: UTF8.self)
                let revision = self.transcriptRevision
                self.owner.publish {
                    $0.transcript = text
                    self.queue.async {
                        self.transcriptPublishScheduled = false
                        if self.transcriptRevision != revision { self.scheduleTranscriptPublication() }
                    }
                }
            }
        }
    }

    private func receiveControl(_ bytes: Data) {
        guard !finalized else { return }
        guard controlLines.count + bytes.count <= 4096 else { control?.closePeer(); channelDisconnected(control: true); return }
        controlLines.append(bytes)
        while let newline = controlLines.firstIndex(of: 10) {
            guard !finalized else { return }
            var line = controlLines.subdata(in: controlLines.startIndex..<newline)
            controlLines.removeSubrange(controlLines.startIndex...newline)
            if line.last == 13 { line.removeLast() }
            // Only this independent guest supervisor port can acknowledge
            // readiness/unmount. A shell echo in the serial transcript cannot.
            let prefix = owner.isDebian ? "IDECK_DEBIAN_" : "IDECK_TERMINAL_"
            if line == Data((prefix + "READY").utf8), !ready, !loopReturned, !stopRequested {
                checkpoint(.terminalReady)
                lifecycle.record(.ready)
                guestWasReady = true
                ready = (serial?.peer ?? -1) >= 0
                let consoleReady = ready
                report["terminal_ready"] = true
                report["status"] = "terminal_running"
                persist()
                owner.publish {
                    $0.ready = consoleReady; $0.canStop = true
                    $0.message = consoleReady ? ($0.isDebian ? "Debian console ready. Files in /root persist on ext4; use Stop Linux before closing the app."
                        : "Local Linux console ready. User files are stored in /data; use Stop Linux before closing the app.")
                        : "The console channel is unavailable. Use Stop Linux to stop the guest through its separate control channel."
                }
            } else if line == Data((prefix + "CLEAN_UNMOUNT").utf8) {
                lifecycle.record(.unmounted)
                ready = false
                stopRequested = true
                cleanUnmount = true
                checkpoint(.guestCleanUnmount)
                report["terminal_clean_unmount"] = true
                owner.publish { $0.ready = false; $0.canStop = false; $0.message = "User data was unmounted. Waiting for Linux to stop…" }
                persist()
                // Parse the rest of this control batch before considering a
                // pass: poweroff may have returned and emitted STOP_FAILED.
                queue.async { self.finalizeIfClean() }
            } else if line == Data((prefix + "STOP_FAILED").utf8) {
                lifecycle.record(.failed)
                checkpoint(.stopFailed)
                stopFailed = true
                stopRequested = true
                ready = false
                report["terminal_stop_failed"] = true
                report["terminal_clean_stop"] = false
                report["status"] = "terminal_stop_failed"
                persist()
                owner.publish {
                    $0.ready = false; $0.stopping = false; $0.canStop = false
                    $0.message = "Linux could not confirm a clean stop. User data was not replaced and remains locked until the app exits. Save the report before closing the app."
                }
            }
        }
    }

    private func channelDisconnected(control controlClosed: Bool) {
        guard !finalized, !stopFailed else { return }
        ready = false
        let canStop = !controlClosed && guestWasReady && !stopRequested && !loopReturned && (control?.peer ?? -1) >= 0
        report[controlClosed ? "terminal_control_channel_failed" : "terminal_serial_channel_failed"] = true
        persist()
        owner.publish {
            $0.ready = false
            $0.canStop = canStop
            if controlClosed { $0.stopping = false }
            $0.message = canStop ? "The console channel closed. You can still use Stop Linux through its separate control channel."
                : "The local console/control channel closed. Clean shutdown is not confirmed; the disk remains locked until this app exits."
        }
    }

    private func didReturnFromQEMU() {
        guard !loopReturned else { return }
        loopReturned = true
        lifecycle.record(.loopReturned)
        ready = false
        report["qemu_main_loop_returned"] = true
        report["status"] = stopFailed ? "terminal_stop_failed" : "terminal_unclean_stopped"
        if !cleanUnmount { checkpoint(.uncleanStopped) }
        persist()
        owner.publish { $0.running = false; $0.ready = false; $0.stopping = false; $0.canStop = false }
        finalizeIfClean()
        queue.asyncAfter(deadline: .now() + 2) {
            guard !self.finalized, !self.stopFailed else { return }
            self.owner.publish { $0.message = "Linux stopped without a confirmed clean unmount and disk sync. Close and reopen the app; user data may need recovery." }
        }
    }

    private func finalizeIfClean() {
        guard cleanUnmount, loopReturned, !finalized, !stopFailed, let disk else { return }
        control?.drainAvailable()
        guard !stopFailed, controlLines.isEmpty else { return }
        guard lifecycle.maySyncForCleanStop else { return }
        do {
            // Main-loop return is not QEMU block-layer cleanup. Sync the host
            // file, but keep its descriptor and exclusive lock until app exit.
            checkpoint(.hostSyncBegin)
            guard try lifecycle.synchronizeForCleanStop({ try disk.synchronize() }) else { return }
            checkpoint(.hostDiskSynced)
            finalized = true
            report["host_disk_fsync_passed"] = true
            report["terminal_clean_stop"] = true
            report["status"] = "terminal_clean_stopped"
            checkpoint(.cleanStopped)
            persist()
            checkpoint(.consoleLogCloseBegin)
            try? logHandle?.synchronize()
            try? logHandle?.close(); logHandle = nil
            checkpoint(.consoleLogCloseReturned)
            checkpoint(.consolePeersCloseBegin)
            serial?.closePeer(); control?.closePeer()
            checkpoint(.consolePeersCloseReturned)
            report["console_shutdown_tail_returned"] = true
            persist()
            owner.publish {
                $0.cleanStopped = true; $0.running = false; $0.ready = false; $0.stopping = false; $0.canStop = false
                $0.message = "Guest unmount and data sync were confirmed. Close and reopen the app for the next session; the disk stays locked until this app exits."
            }
        } catch {
            // The lifecycle already latched failure before rethrowing. Keep
            // the worker/report failed too, before any queued finalize runs.
            stopFailed = true
            checkpoint(.stopFailed)
            report["host_disk_fsync_passed"] = false
            report["terminal_stop_failed"] = true
            report["terminal_clean_stop"] = false
            report["status"] = "terminal_stop_failed"
            persist()
            owner.publish {
                $0.cleanStopped = false; $0.running = false; $0.ready = false; $0.stopping = false; $0.canStop = false
                $0.message = "Guest unmount completed, but host disk sync failed. Clean stop is not confirmed; the disk remains locked until the app exits. Save the report before closing the app."
            }
        }
    }

    private func scheduleStartupTimeout() {
        queue.asyncAfter(deadline: .now() + 60) {
            guard !self.ready, !self.stopRequested, !self.loopReturned, !self.finalized, !self.startupAborted else { return }
            self.checkpoint(.startupTimeout)
            self.report["terminal_startup_timed_out"] = true
            self.report["status"] = "terminal_startup_timeout"
            self.persist()
            self.owner.publish {
                $0.message = "Linux terminal readiness was not confirmed within 60 seconds. No forced stop was attempted. Save the report; the disk remains locked until app exit."
            }
        }
    }

    private func scheduleStopTimeout() {
        queue.asyncAfter(deadline: .now() + 30) {
            guard !self.finalized, !self.stopFailed, !self.loopReturned else { return }
            self.checkpoint(.stopTimeout)
            self.lifecycle.record(.timedOut)
            self.report["terminal_stop_timed_out"] = true
            self.report["status"] = "terminal_stop_timeout"
            self.persist()
            self.owner.publish {
                $0.stopping = false; $0.ready = false
                $0.message = "Orderly shutdown was not confirmed within 30 seconds. No forced stop was attempted. Save the report before closing the app; the disk remains locked."
            }
        }
    }

    private func digest(_ url: URL) throws -> String {
        let handle = try FileHandle(forReadingFrom: url)
        defer { try? handle.close() }
        var hash = SHA256()
        while let chunk = try handle.read(upToCount: 1024 * 1024), !chunk.isEmpty { hash.update(data: chunk) }
        return hash.finalize().map { String(format: "%02x", $0) }.joined()
    }

    private var resultURL: URL { session.appendingPathComponent("result.json") }
    private var serialURL: URL { session.appendingPathComponent("linux-serial.log") }
    private var markdownURL: URL { session.appendingPathComponent(owner.isDebian ? "result.md" : LinuxProbeReport.filename) }

    private func refreshExports() {
        let files = [resultURL, serialURL].filter { FileManager.default.fileExists(atPath: $0.path) }
        let markdown = markdownAvailable && FileManager.default.fileExists(atPath: markdownURL.path) ? markdownURL : nil
        let error = exportError
        owner.publish { $0.shareFiles = files; $0.markdownFile = markdown; $0.exportError = error }
    }

    private func saveReport() throws {
        report["elapsed_seconds"] = Date().timeIntervalSince(began)
        do {
            try JSONSerialization.data(withJSONObject: report, options: [.prettyPrinted, .sortedKeys]).write(to: resultURL, options: .atomic)
        } catch {
            markdownAvailable = false
            try? FileManager.default.removeItem(at: markdownURL)
            exportError = "Could not update the report. Available raw files are preserved."
            refreshExports()
            throw error
        }
        do {
            try LinuxProbeReport.render(report: report).write(to: markdownURL, atomically: true, encoding: .utf8)
            markdownAvailable = true
            exportError = nil
            refreshExports()
        } catch {
            markdownAvailable = false
            try? FileManager.default.removeItem(at: markdownURL)
            exportError = "Markdown export failed. You can still save the available raw JSON and serial log."
            refreshExports()
        }
    }

    private func persist() { do { try saveReport() } catch { HuskLog.log("ideck-terminal", "could not update terminal report") } }
}
