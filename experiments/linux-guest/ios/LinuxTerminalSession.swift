import Foundation
import Combine
import UIKit
import Darwin
import CryptoKit

/// A real local serial console. One QEMU invocation is allowed per process.
final class LinuxTerminalSession: ObservableObject {
    static let shared = LinuxTerminalSession()
    static let debian = LinuxTerminalSession(isDebian: true)
    static let desktop = LinuxTerminalSession(isDesktop: true)
    static let steam = LinuxTerminalSession(isSteam: true)
    let isSteam: Bool
    @Published var steamNetworkConsent = false
    @Published fileprivate(set) var steamInstalled = false
    @Published fileprivate(set) var steamBusy = false
    @Published fileprivate(set) var steamMessage = "Install or resume after the desktop is ready. Login and agreements belong to you."
    var steamPayloadAvailable: Bool { FileManager.default.fileExists(atPath: Bundle.main.bundleURL.appendingPathComponent("iDeckLinuxSteam/steam-profile.json").path) }
    @Published fileprivate(set) var steamReadiness: LinuxSteamProfile.Readiness?
    private var jitObservation: Bool?
    /// No JITBootstrap.ready here: that getter can prewarm native JIT on older
    /// iOS. Preview reads only the bounded bundle manifest and OS memory counter.
    @discardableResult func refreshSteamReadiness() -> LinuxSteamProfile.Readiness? {
        precondition(Thread.isMainThread)
        guard isSteam, !attempted else { return steamReadiness }
        let available = os_proc_available_memory()
        let result = LinuxSteamProfile.readiness(assets: Bundle.main.bundleURL.appendingPathComponent("iDeckLinuxSteam"),
            jitVerified: jitObservation, networkConsent: steamNetworkConsent,
            availableMemory: available > 0 ? available : nil)
        steamReadiness = result
        return result
    }
    let isDebian: Bool
    let isDesktop: Bool
    @Published fileprivate(set) var recoveryMode = false
    private var recoveryRequested = false
    let desktopInput: LinuxDesktopInput?
    init(isDebian: Bool = false, isDesktop: Bool = false, isSteam: Bool = false) {
        self.isSteam = isSteam
        self.isDebian = isDebian || isDesktop || isSteam
        self.isDesktop = isDesktop || isSteam
        self.desktopInput = (isDesktop || isSteam) ? LinuxDesktopInput() : nil
        if isSteam { message = "Experimental Steam: separate 12 GiB disk, 1536 MiB guest RAM and 4 vCPUs. Device usability is unverified." }
        else if isDesktop { message = "Enable JIT, then start the local Debian desktop. Files in /home/ideck persist on its separate GUI disk." }
        else if isDebian { message = "Enable JIT, then start Debian with its separate persistent ext4 disk." }
    }
    @Published fileprivate(set) var message = "Enable JIT, then start the local Linux terminal."
    @Published fileprivate(set) var attempted = false
    @Published fileprivate(set) var running = false
    @Published fileprivate(set) var ready = false
    @Published fileprivate(set) var displayHasFrame = false
    @Published fileprivate(set) var displayTimedOut = false
    @Published fileprivate(set) var serialReady = false
    @Published fileprivate(set) var stopping = false
    @Published fileprivate(set) var canStop = false
    @Published fileprivate(set) var cleanStopped = false
    @Published fileprivate(set) var preparationState: LinuxStartupPreparation.Snapshot?
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

    /// Session MD when available; otherwise the CURRENT startup journal MD.
    /// Never silently substitute a previous attempt for the current report.
    func reportForSharing() -> URL? {
        precondition(Thread.isMainThread)
        recoverDiagnostics()
        if let markdownFile { return markdownFile }
        guard let id = diagnosticJournal?.id else { return nil }
        return diagnosticReports.first { diagnosticAttemptIDs[$0] == id }
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
        jitObservation = passed
        jitExecutionReady = passed
        jitExecutionMessage = passed ? "JIT execution check passed."
            : "JIT execution has not been verified. Open JIT setup."
    }

    func startDesktop() {
        guard !attempted else { return }
        recoveryRequested = false; start()
    }
    func startRecovery() {
        guard isDesktop, !isSteam else {
            message = "This recovery supports only the separate Debian GUI disk. Share diagnostics and preserve this disk for offline review."; return
        }
        guard !attempted else {
            message = "Close and reopen the app, then choose Recover disk before starting a VM. Recovery uses a separate one-use VM."; return
        }
        recoveryRequested = true; start()
    }
    func start() {
        precondition(Thread.isMainThread)
        guard !attempted else { return }
        if isSteam {
            // Fresh reads on every click; a successful preview is never reused
            // as authority. No attempt/native operation is consumed by refusal.
            guard let preflight = refreshSteamReadiness(), preflight.canCheckAndStart else {
                message = "Steam preflight: \(steamReadiness?.summary ?? "Не проверено"). Исправьте условия и повторите. Native запуск не начат."; return
            }
        }
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
                && !LinuxTerminalSession.debian.attempted && !LinuxTerminalSession.desktop.attempted && !LinuxTerminalSession.steam.attempted && !QemuRunner.shared.isRunning && husk_console_loaded_game() == nil
            try diagnostic.record(.runtimeOwnershipReturned)
            guard runtimeFree else {
                try diagnostic.record(.startRejected)
                message = "Another runtime owns this process. Close and reopen the app."; return
            }
        } catch {
            diagnosticFailure(); message = "Startup journal is unavailable. Export existing diagnostics before trying again."; return
        }
        attempted = true
        recoveryMode = isDesktop && !isSteam && recoveryRequested
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
        let root = documents.appendingPathComponent(isSteam ? "iDeckSteam-v1" : isDesktop ? "iDeckDebianGUI-v1" : (isDebian ? "iDeckDebian" : "iDeckLinux"), isDirectory: true)
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
        preparationState = next.preparation.snapshot
        message = isDebian ? "Checking Debian assets and importing or opening the separate ext4 disk…"
            : "Checking terminal assets and the persistent user-data disk…"
        next.start()
    }

    /// Safe on repeated taps, leaving the route or moving to the background.
    /// It never sends Stop, closes a disk or resets the one-use attempt guard.
    func cancelPreparation() {
        precondition(Thread.isMainThread)
        guard let worker, worker.requestPreparationCancellation() else { return }
        let state = worker.preparation.snapshot
        preparationState = state
        message = state.message + " Keep iDeck open. Completed copies are preserved; reopen the app before retrying."
        do { try diagnosticJournal?.record(.preparationCancelRequested) }
        catch { diagnosticFailure() }
    }

    fileprivate static func failure(_ error: Error) -> LinuxTerminalDiagnostics.Failure {
        LinuxStartupFailure.classify(error)
    }

    func send(_ text: String) {
        precondition(Thread.isMainThread)
        guard (isDesktop ? serialReady : ready), !stopping, text.utf8.count <= 16384 else { return }
        worker?.send(Data(text.utf8))
    }

    func steamAction(_ action: String) {
        precondition(Thread.isMainThread)
        guard isSteam, ready, !stopping, ["INSTALL", "BIG_PICTURE", "DESKTOP"].contains(action),
              (action == "INSTALL" || steamInstalled), (!steamBusy || action == "DESKTOP") else { return }
        steamBusy = true
        worker?.steamAction(action)
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
        serialReady = false
        message = "Stopping guest processes, syncing and unmounting user data…"
        if let desktopInput { desktopInput.prepareStop { [weak self] in self?.worker?.stop() } }
        else { worker?.stop() }
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
    let preparation = LinuxStartupPreparation()
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
    var recovery: LinuxGUIRecovery?
    var recoveryProgress = LinuxRecoveryProgress()
    var recoveryWatchdog: LinuxRecoveryWatchdog?
    var recoveryWatchdogRevision: UInt64 = 0
    var recoveryTimedOut = false
    var isRecovery: Bool

    init(owner: LinuxTerminalSession, bundle: URL, session: URL, dataDirectory: URL, metadata: [String: Any],
         diagnostic: LinuxTerminalDiagnostics.Journal) {
        self.owner = owner; self.bundle = bundle; self.session = session
        self.dataDirectory = dataDirectory; self.metadata = metadata; self.diagnostic = diagnostic
        self.isRecovery = owner.recoveryMode
    }

    /// Called synchronously on the thread reaching the boundary, including the
    /// QEMU thread. A post-entry diagnostic IO error must not tear down QEMU or
    /// release the userdata lock; it is made visible on the UI instead.
    private func checkpoint(_ stage: LinuxTerminalDiagnostics.Stage, failure: LinuxTerminalDiagnostics.Failure? = nil) {
        do { try diagnostic.record(stage, failure: failure) }
        catch { owner.publish { $0.diagnosticFailure() } }
    }

    func requestPreparationCancellation() -> Bool {
        guard preparation.requestCancellation() else { return false }
        queue.async {
            self.report["preparation_cancel_requested"] = true
            self.persist()
        }
        return true
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
            guard preparation.enterNative() else { throw LinuxStartupPreparation.Cancelled.beforeNativeEntry }
        }
        catch {
            let failure = LinuxTerminalSession.failure(error)
            let journalFailed = error is LinuxTerminalDiagnostics.Problem
            let cancelled = error is LinuxStartupPreparation.Cancelled
            queue.async {
                self.checkpoint(cancelled ? .preparationCancelled : .preparationFailed, failure: cancelled ? nil : failure)
                self.startupAborted = true
                self.preparation.finish()
                serial.closeUnused(); control.closeUnused()
                try? self.logHandle?.close(); self.logHandle = nil
                self.disk?.closeUnused()
                self.report["status"] = cancelled ? "terminal_prepare_cancelled" : "terminal_prepare_failed"
                if cancelled { self.report["preparation_cancelled_before_qemu"] = true }
                self.persist()
                self.owner.publish {
                    if journalFailed { $0.diagnosticFailure() }
                    $0.preparationState = self.preparation.snapshot
                    $0.message = cancelled ? "Startup cancelled before Linux started. Completed copies were preserved. Close and reopen iDeck before another attempt."
                        : "Startup disk ownership or journal check failed. Linux was not started. Existing user data was preserved; close and reopen the app."
                }
            }
            return false
        }
        queue.sync {
            self.enteredQEMU = true
            self.owner.publish {
                $0.preparationState = self.preparation.snapshot
                $0.message = "Starting Linux. Keep iDeck open; Stop becomes available when the guest supervisor is ready."
            }
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
                self.report["mode"] = self.owner.isSteam ? "steam-experimental" : self.owner.isDesktop ? "desktop" : (self.owner.isDebian ? "debian" : "terminal")
                self.report["status"] = "terminal_prepared"
                self.report["terminal_clean_stop"] = false
                self.report["qemu_block_layer_drained_verified"] = false
                self.report["import_status"] = "not_started"
                self.persist()
                let assets = self.bundle.appendingPathComponent(self.owner.isSteam ? "iDeckLinuxSteam" : self.owner.isDesktop ? "iDeckLinuxDesktop" : (self.owner.isDebian ? "iDeckDebian" : "iDeckLinuxTerminal"))
                let probe = self.bundle.appendingPathComponent("iDeckLinuxProbe")
                try self.preparationCheckpoint(.assets)
                try self.diagnostic.record(.assetsBegin)
                let terminal = self.owner.isDebian ? nil : (try LinuxTerminalProfile.load(from: assets))
                let steam = self.owner.isSteam ? (try LinuxSteamProfile.load(from: assets)) : nil
                if steam != nil {
                    let available = os_proc_available_memory()
                    self.report["process_available_memory_bytes"] = available
                    guard available >= UInt64(LinuxSteamProfile.memoryMib) * 1024 * 1024 + LinuxSteamProfile.hostReserve else { throw LinuxSteamProfile.Blocker.memoryBudget }
                }
                let gui = self.owner.isDesktop && !self.owner.isSteam ? (try LinuxGUIProfile.load(from: assets)) : nil
                let debian = self.owner.isDebian && !self.owner.isDesktop ? (try LinuxDebianProfile.load(from: assets)) : nil
                let desktop = self.owner.isDebian && !self.owner.isDesktop ? (try LinuxDesktopProfile.load(from: assets)) : nil
                try self.diagnostic.record(.assetsReturned)
                try self.preparationCheckpoint(.disk)
                try self.diagnostic.record(.diskBegin)
                let preparedMetadata: [String: Any]
                if let steam {
                    let path = self.dataDirectory.appendingPathComponent("rootfs-v1.raw")
                    var state = stat()
                    if lstat(path.path, &state) == 0 {
                        self.report["import_status"] = "existing_steam_disk_preserved"; self.persist()
                        self.disk = try steam.openExisting(in: self.dataDirectory, observe: self.observeSuperblock)
                    } else {
                        guard errno == ENOENT else { throw LinuxDesktopDisk.Invalid.inspection }
                        self.report["import_status"] = "copying_steam_seed"; self.persist()
                        try self.preparationCheckpoint(.importingSeed)
                        self.disk = try steam.provision(in: self.dataDirectory, assets: assets)
                        self.report["import_status"] = "steam_seed_hash_verified_and_published"; self.persist()
                    }
                    preparedMetadata = ["profile_cpu": "cortex-a76", "profile_memory_mib": LinuxSteamProfile.memoryMib,
                        "profile_vcpus": 4, "profile_width": 800, "profile_height": 600, "requested_tcg_mib": 256,
                        "userdata_size_bytes": steam.image.sizeBytes, "userdata_filesystem": "ext4",
                        "steam_seed_sha256": steam.seedSha256, "steam_seed_gzip_sha256": steam.rootfs.sha256, "terminal_initramfs_sha256": steam.initramfs.sha256,
                        "steam_network_consent": self.owner.steamNetworkConsent, "steam_device_verified": false]
                } else if let gui {
                    self.report["debian_seed_sha256"] = gui.rootfs.sha256
                    self.report["terminal_initramfs_sha256"] = gui.initramfs.sha256
                    if self.isRecovery {
                        try self.prepareRecovery(gui)
                    } else {
                        if try LinuxGUIRecovery.promotePending(directory: self.dataDirectory, specification: gui.image, toolSeedSHA256: gui.rootfs.sha256) {
                            self.report["recovery_phase"] = "promoted"
                        }
                        let path = self.dataDirectory.appendingPathComponent("rootfs-v1.raw")
                        var state = stat()
                        if lstat(path.path, &state) == 0 {
                            self.report["import_status"] = "existing_disk_preserved"; self.persist()
                            do { self.disk = try gui.openExisting(in: self.dataDirectory, observe: self.observeSuperblock) }
                            catch LinuxDesktopDisk.Invalid.needsRecovery {
                                // Original boot gate refused BEFORE native entry.
                                // Use this process's ONE VM for a clone-only repair;
                                // desktop activation is deferred to a fresh process.
                                self.report["storage_failure"] = "needsRecovery"
                                try self.prepareRecovery(gui)
                            }
                        } else {
                            guard errno == ENOENT else { throw LinuxDesktopDisk.Invalid.inspection }
                            self.report["import_status"] = "copying_seed"; self.persist()
                            try self.preparationCheckpoint(.importingSeed)
                            self.disk = try gui.provision(in: self.dataDirectory, assets: assets)
                            self.report["import_status"] = "seed_hash_verified_and_published"; self.persist()
                        }
                    }
                    preparedMetadata = ["profile_cpu": "cortex-a72", "profile_memory_mib": 1024, "profile_vcpus": 4,
                        "profile_width": 800, "profile_height": 600, "requested_tcg_mib": 256,
                        "userdata_size_bytes": gui.image.sizeBytes, "userdata_filesystem": "ext4",
                        "debian_seed_sha256": gui.rootfs.sha256, "terminal_initramfs_sha256": gui.initramfs.sha256,
                        "desktop_software_rendering": true]
                } else if let desktop, let debian {
                    self.report["debian_seed_sha256"] = desktop.rootfs.sha256
                    self.report["terminal_initramfs_sha256"] = debian.initramfs.sha256
                    let path = self.dataDirectory.appendingPathComponent("rootfs-v1.raw")
                    var state = stat()
                    // lstat distinguishes absent from a dangling link or IO error.
                    if lstat(path.path, &state) == 0 {
                        self.report["import_status"] = "existing_disk_preserved"; self.persist()
                        self.disk = try desktop.openExisting(in: self.dataDirectory, observe: self.observeSuperblock)
                    } else {
                        guard errno == ENOENT else { throw LinuxDesktopDisk.Invalid.inspection }
                        self.report["import_status"] = "copying_seed"; self.persist()
                        try self.preparationCheckpoint(.importingSeed)
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
                try self.preparationCheckpoint(.arguments)
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
                } else if let profile = steam, let desktopDisk = disk as? LinuxDesktopDisk {
                    args = try profile.arguments(probeAssets: probe, assets: assets, session: bootSession,
                        disk: desktopDisk, serialFD: serial.qemu, controlFD: control.qemu, networkConsent: self.owner.steamNetworkConsent)
                } else if let profile = gui, let recovery = self.recovery {
                    args = try profile.recoveryArguments(probeAssets: probe, assets: assets, session: bootSession,
                        transaction: recovery, serialFD: serial.qemu, controlFD: control.qemu)
                    self.report["recovery_suffix_sha256"] = LinuxRecoveryGuest.sha256
                } else if let profile = gui, let desktopDisk = disk as? LinuxDesktopDisk {
                    args = try profile.arguments(probeAssets: probe, assets: assets, session: bootSession,
                        disk: desktopDisk, serialFD: serial.qemu, controlFD: control.qemu)
                } else if let profile = debian, let desktopDisk = disk as? LinuxDesktopDisk {
                    args = try profile.arguments(probeAssets: probe, assets: assets, session: bootSession,
                        disk: desktopDisk, serialFD: serial.qemu, controlFD: control.qemu)
                } else { throw LinuxTerminalProfile.Invalid.configuration }
                if gui != nil, let index = args.firstIndex(of: "-initrd"), index + 1 < args.count {
                    self.report["desktop_runtime_initramfs_sha256"] = try self.digest(URL(fileURLWithPath: args[index + 1]))
                    self.report["desktop_runtime_suffix_sha256"] = LinuxRecoveryGuest.sha256
                }
                try self.diagnostic.record(.argumentsReturned)
                try self.preparationCheckpoint(.report)
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
                self.report["terminal_profile_sha256"] = try self.digest(assets.appendingPathComponent(self.owner.isSteam ? "steam-profile.json" : self.owner.isDesktop ? "desktop-profile.json" : (self.owner.isDebian ? "debian-profile.json" : "terminal-profile.json")))
                if let executable = Bundle.main.executableURL { self.report["app_executable_sha256"] = try self.digest(executable) }
                try self.saveReport()
                try self.diagnostic.record(.reportReturned)
                serial.received = { [weak self] bytes in self?.receiveSerial(bytes) }
                control.received = { [weak self] bytes in self?.receiveControl(bytes) }
                serial.disconnected = { [weak self] in self?.channelDisconnected(control: false) }
                control.disconnected = { [weak self] in self?.channelDisconnected(control: true) }
                serial.beginReading(); control.beginReading()
                try self.preparationCheckpoint(.nativeEntry)
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
                        if self.owner.isDesktop && !self.isRecovery {
                            self.observeDisplay(started: ProcessInfo.processInfo.systemUptime)
                        }
                        self.report["qemu_init_returned"] = true
                        self.report["jit_available_after_init"] = jitAvailable
                        self.report["status"] = "terminal_running"
                        self.persist()
                        let alreadyReady = self.ready
                        self.owner.publish {
                            $0.running = true
                            if !alreadyReady { $0.message = $0.isDesktop ? "Linux is starting the local Debian desktop…" : "Linux is starting the local terminal…" }
                        }
                    }
                    self.checkpoint(.mainLoopBegin)
                    qemu_main_loop()
                    self.owner.desktopInput?.guestEnded()
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
                if let recovery = self.recovery, let gui { try recovery.markRunning(toolSeedSHA256: gui.rootfs.sha256) }
                thread.start()
            } catch {
                // A timer may already be queued while receipt/file fsync was
                // blocking this queue. Preserve the original preparation error
                // before releasing unused resources or running that callback.
                self.startupAborted = true
                let cancelled = error is LinuxStartupPreparation.Cancelled
                self.checkpoint(cancelled ? .preparationCancelled : .preparationFailed,
                                failure: cancelled ? nil : LinuxTerminalSession.failure(error))
                self.preparation.finish()
                if !cancelled { HuskLog.log("ideck-terminal", "terminal preparation failed: \(LinuxTerminalSession.failure(error).rawValue)") }
                if error is LinuxTerminalDiagnostics.Problem { self.owner.publish { $0.diagnosticFailure() } }
                self.serial?.closeUnused(); self.control?.closeUnused()
                try? self.logHandle?.close(); self.logHandle = nil
                if !self.enteredQEMU { self.disk?.closeUnused() }
                self.report["status"] = cancelled ? "terminal_prepare_cancelled" : "terminal_prepare_failed"
                if cancelled { self.report["preparation_cancelled_before_qemu"] = true }
                if let failure = error as? LinuxDesktopDisk.Invalid { self.report["storage_failure"] = String(describing: failure) }
                if let failure = error as? LinuxDesktopProfile.Invalid { self.report["storage_failure"] = String(describing: failure) }
                if let failure = error as? LinuxGUIRecovery.Invalid { self.report["recovery_failure"] = String(describing: failure) }
                self.persist()
                if let blocker = error as? LinuxSteamProfile.Blocker {
                    self.report["steam_blocker"] = String(describing: blocker); self.persist()
                    self.owner.publish { $0.message = "Steam preparation blocked: \(blocker). Missing payload requires a separately sealed Steam asset; memoryBudget requires 1536 MiB guest plus 1 GiB available host reserve. Existing disks were preserved." }
                    return
                }
                let needsRecovery = (error as? LinuxDesktopDisk.Invalid) == .needsRecovery
                let noSpace = (error as? LinuxDesktopDisk.Invalid) == .insufficientSpace
                let busy = (error as? LinuxDesktopDisk.Invalid) == .locked
                let badSeed = (error as? LinuxDesktopProfile.Invalid) == .assetDigest
                self.owner.publish {
                    $0.preparationState = self.preparation.snapshot
                    $0.message = cancelled ? "Startup cancelled before Linux started. Completed copies were preserved. Close and reopen iDeck before another attempt."
                        : error is LinuxGUIRecovery.Invalid ? "Recovery could not proceed safely (\(String(describing: error))). Original data was preserved. Share diagnostics; manual repair is not automatic. A new app process is required after any recovery VM."
                        : needsRecovery ? (self.owner.isSteam
                            ? "Steam ext4 safety checks blocked startup. The disk was not mounted or replaced. GUI recovery does not support this separate 12 GiB disk. Share diagnostics and preserve it for offline review."
                            : self.owner.isDesktop
                            ? "Ext4 safety checks blocked startup. The disk was not mounted or replaced. Share diagnostics before further recovery."
                            : "Ext4 safety checks blocked startup. The disk was not mounted or replaced. Share the recorded metadata and preserve the disk before offline review.")
                        : noSpace ? (self.owner.isSteam ? "Not enough space for the separate 12 GiB Steam disk and 1 GiB reserve. Existing disks were preserved." : self.owner.isDesktop ? "Not enough space for the GUI disk and 512 MiB reserve. Existing disks were preserved." : "Not enough free space to import Debian (512 MiB plus 32 MiB reserve). Existing disks were preserved. Free space and reopen the app to retry.")
                        : busy ? "The Debian disk or import is busy. It was not replaced. Close the owning session before retrying."
                        : badSeed ? "The Debian seed failed its SHA-256 check. No disk was published. Restore the correct app payload before retrying; existing disks were preserved."
                        : "Console preparation failed. The existing disk was not replaced. Export the report; close and reopen the app to retry."
                }
            }
        }
    }

    func send(_ bytes: Data) {
        queue.async {
            guard (self.owner.isDesktop ? self.guestWasReady : self.ready), !self.stopRequested, !self.loopReturned else { return }
            do { try self.serial?.enqueue(bytes) } catch { self.channelDisconnected(control: false) }
        }
    }

    private var steamActionRevision: UInt64 = 0

    func steamAction(_ action: String) {
        queue.async {
            guard self.owner.isSteam, self.ready, !self.stopRequested, !self.loopReturned else { return }
            do {
                try self.control?.enqueue(Data(("IDECK_STEAM_" + action + "\n").utf8))
                self.steamActionRevision &+= 1
                self.report["steam_action_wait_timed_out"] = false; self.persist()
                let revision = self.steamActionRevision
                self.queue.asyncAfter(deadline: .now() + 180) {
                    guard self.steamActionRevision == revision, !self.stopRequested, !self.loopReturned, !self.stopFailed else { return }
                    self.report["steam_action_wait_timed_out"] = true; self.persist()
                    self.owner.publish { $0.steamMessage = "Steam has not confirmed completion after 180 seconds. It may still be running. Open Diagnostics and share the report; no duplicate operation was started." }
                }
            }
            catch { self.channelDisconnected(control: true) }
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
        guard !startupAborted else { return }
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
        guard !finalized, !startupAborted else { return }
        guard controlLines.count + bytes.count <= 4096 else { control?.closePeer(); channelDisconnected(control: true); return }
        controlLines.append(bytes)
        while let newline = controlLines.firstIndex(of: 10) {
            guard !finalized else { return }
            var line = controlLines.subdata(in: controlLines.startIndex..<newline)
            controlLines.removeSubrange(controlLines.startIndex...newline)
            if line.last == 13 { line.removeLast() }
            if owner.isSteam, let status = String(data: line, encoding: .utf8), status.hasPrefix("IDECK_STEAM_") {
                report["steam_guest_status"] = status
                if ["IDECK_STEAM_INSTALLED", "IDECK_STEAM_CLIENT_RETURNED", "IDECK_STEAM_DESKTOP_READY"].contains(status) || status.hasPrefix("IDECK_STEAM_BLOCKER:") {
                    steamActionRevision &+= 1
                }
                if status == "IDECK_STEAM_CPU_LSE_PASS" { report["steam_cpu_lse_passed"] = true }
                if status == "IDECK_STEAM_INSTALLED" {
                    owner.publish { $0.steamInstalled = true; $0.steamBusy = false; $0.steamMessage = "Pinned client installed. Big Picture starts the real client; sign in and accept any terms yourself." }
                } else if status.hasPrefix("IDECK_STEAM_BLOCKER:") {
                    owner.publish { $0.steamBusy = false; $0.steamMessage = status }
                } else if status == "IDECK_STEAM_CLIENT_RETURNED" {
                    owner.publish { $0.steamBusy = false; $0.steamMessage = "Steam launcher returned. This does not confirm a rendered client window." }
                } else if status == "IDECK_STEAM_DESKTOP_READY" {
                    owner.publish { $0.steamBusy = false; $0.steamMessage = "Steam and its private namespace writers exited. Linux Desktop stays open." }
                } else if status == "IDECK_STEAM_LAUNCH_REQUESTED" || status == "IDECK_STEAM_DESKTOP_REQUESTED" {
                    owner.publish { $0.steamMessage = status == "IDECK_STEAM_LAUNCH_REQUESTED" ? "Real Big Picture launch requested. Rendering on this device is unverified." : "Steam shutdown requested. Waiting for client, namespace writers and launch owner to exit…" }
                }
                persist()
                continue
            }
            // Only this independent guest supervisor port can acknowledge
            // readiness/unmount. A shell echo in the serial transcript cannot.
            let prefix = owner.isDesktop ? "IDECK_DESKTOP_" : (owner.isDebian ? "IDECK_DEBIAN_" : "IDECK_TERMINAL_")
            if isRecovery, let text = String(data: line, encoding: .utf8), text.hasPrefix("IDECK_RECOVERY_") {
                guard acceptRecoveryActivity() else { continue }
                do {
                    try recoveryProgress.observe(text)
                    recoveryWatchdog?.advanced(at: ProcessInfo.processInfo.systemUptime)
                    armRecoveryTimeout()
                    report["recovery_assessment_exit"] = recoveryProgress.assessment
                    report["recovery_replay_exit"] = recoveryProgress.replay
                    report["recovery_verification_exit"] = recoveryProgress.verification
                    report["recovery_output_clean"] = recoveryProgress.scanClean
                    report["recovery_checked_image_sha256"] = recoveryProgress.imageSHA256
                    report["recovery_summary_reconciled"] = recoveryProgress.summaryReconciled
                    let stage = recoveryProgress.phase
                    report["recovery_phase"] = stage
                    checkpoint(recoveryProgress.done ? .recoveryRelaunch : (recoveryProgress.imageSHA256 != nil ? .recoveryVerified : (recoveryProgress.replay != nil ? .recoveryReplay : .recoveryAssessment)))
                    if recoveryProgress.done { lifecycle.record(.stop); stopRequested = true; scheduleStopTimeout() }
                    let message = recoveryProgress.message
                    owner.publish { $0.message = message }
                } catch {
                    let reason = LinuxRecoveryProgress.failure(text) ?? "control_receipt"
                    stopFailed = true; ready = false; report["recovery_phase"] = "manual_review"
                    report["recovery_guest_failure"] = reason
                    report["terminal_clean_stop"] = false; report["status"] = "terminal_stop_failed"
                    checkpoint(.stopFailed, failure: .recoveryFailed)
                    do { try recovery?.recordFailure(reason) } catch { owner.publish { $0.diagnosticFailure() } }
                    owner.publish { $0.ready = false; $0.canStop = false; $0.message = "Recovery stopped (\(reason)). Original and backup are preserved; no replacement was activated. Share diagnostics. General or destructive repair requires a separate decision." }
                }
                persist(); continue
            }
            if owner.isDesktop, line == Data("IDECK_DESKTOP_RECOVERY_READY".utf8), !guestWasReady, !loopReturned, !stopRequested {
                if isRecovery, acceptRecoveryActivity() {
                    recoveryWatchdog?.advanced(at: ProcessInfo.processInfo.systemUptime, supervisor: true)
                    armRecoveryTimeout()
                }
                checkpoint(.terminalReady)
                lifecycle.record(.ready)
                guestWasReady = true
                report["terminal_ready"] = true
                report["desktop_gui_ready"] = false
                persist()
                let timedOut = recoveryTimedOut
                owner.publish {
                    $0.serialReady = !$0.recoveryMode; $0.canStop = true
                    $0.message = timedOut ? "Recovery timed out; no copy can be activated. Stop is available now. Original data remains preserved."
                        : $0.recoveryMode ? "Offline recovery is checking the unmounted work copy. Keep iDeck open until completion. Original data is preserved."
                        : "Recovery console is ready. Starting Xorg and the desktop…"
                }
                continue
            }
            if owner.isDesktop, line == Data("IDECK_DESKTOP_GUI_FAILED".utf8), !stopRequested, !loopReturned {
                ready = false
                report["desktop_gui_failed"] = true; report["desktop_gui_ready"] = false
                persist()
                owner.publish { $0.ready = false; $0.desktopInput?.setFocused(false); $0.message = "Graphical startup failed. Serial recovery and Stop remain available; save the report." }
                continue
            }
            if !isRecovery, line == Data((prefix + "READY").utf8), !ready, !loopReturned, !stopRequested {
                if !guestWasReady { checkpoint(.terminalReady) }
                lifecycle.record(.ready)
                guestWasReady = true
                ready = (serial?.peer ?? -1) >= 0
                let consoleReady = ready
                report["terminal_ready"] = true
                if owner.isDesktop { report["desktop_gui_ready"] = true }
                report["status"] = "terminal_running"
                persist()
                owner.publish {
                    $0.ready = consoleReady; $0.serialReady = consoleReady; $0.canStop = true
                    if consoleReady { $0.desktopInput?.guestReady() }
                    $0.message = consoleReady ? ($0.isDesktop ? "Debian desktop ready. Files in /home/ideck persist; use Stop Linux before closing iDeck." : ($0.isDebian ? "Debian console ready. Files in /root persist on ext4; use Stop Linux before closing the app."
                        : "Local Linux console ready. User files are stored in /data; use Stop Linux before closing the app."))
                        : "The console channel is unavailable. Use Stop Linux to stop the guest through its separate control channel."
                }
            } else if line == Data((prefix + "CLEAN_UNMOUNT").utf8) {
                lifecycle.record(.unmounted)
                ready = false
                stopRequested = true
                cleanUnmount = true
                checkpoint(.guestCleanUnmount)
                report["terminal_clean_unmount"] = true
                let timedOut = recoveryTimedOut
                owner.publish {
                    $0.ready = false; $0.serialReady = false; $0.canStop = false
                    $0.message = timedOut ? "The recovery guest unmounted after timeout. Recovery is not accepted; original data remains preserved. Save diagnostics."
                        : "User data was unmounted. Waiting for Linux to stop…"
                }
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
        guard !finalized, !stopFailed, !startupAborted else { return }
        ready = false
        let canStop = !controlClosed && guestWasReady && !stopRequested && !loopReturned && (control?.peer ?? -1) >= 0
        report[controlClosed ? "terminal_control_channel_failed" : "terminal_serial_channel_failed"] = true
        persist()
        owner.publish {
            $0.ready = false
            $0.serialReady = false
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
        report["status"] = recoveryTimedOut ? "terminal_recovery_timeout" : (stopFailed ? "terminal_stop_failed" : "terminal_unclean_stopped")
        if !cleanUnmount { checkpoint(.uncleanStopped) }
        persist()
        owner.publish { $0.running = false; $0.ready = false; $0.serialReady = false; $0.stopping = false; $0.canStop = false }
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
            if let recovery {
                guard recoveryProgress.done, let assessment = recoveryProgress.assessment,
                      let replay = recoveryProgress.replay, let verification = recoveryProgress.verification,
                      let imageSHA256 = recoveryProgress.imageSHA256 else { throw LinuxGUIRecovery.Invalid.receipt }
                try recovery.recordResult(assessment: assessment, replay: replay, verification: verification,
                                          scanClean: recoveryProgress.scanClean, imageSHA256: imageSHA256,
                                          summaryReconciled: recoveryProgress.summaryReconciled)
                report["recovery_phase"] = "relaunch_required"
            }
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
                $0.cleanStopped = true; $0.running = false; $0.ready = false; $0.serialReady = false; $0.stopping = false; $0.canStop = false
                $0.message = $0.recoveryMode ? "The recovery VM finished checking its copy. Fully close and reopen iDeck, then choose Start desktop to validate and activate it. Original backup is preserved; no disk is promoted in this process."
                    : "Guest unmount and data sync were confirmed. Close and reopen the app for the next session; the disk stays locked until this app exits."
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
                $0.cleanStopped = false; $0.running = false; $0.ready = false; $0.serialReady = false; $0.stopping = false; $0.canStop = false
                $0.message = "Guest unmount completed, but host disk sync failed. Clean stop is not confirmed; the disk remains locked until the app exits. Save the report before closing the app."
            }
        }
    }

    private func scheduleStartupTimeout() {
        if isRecovery {
            recoveryWatchdog = LinuxRecoveryWatchdog(started: ProcessInfo.processInfo.systemUptime)
            armRecoveryTimeout()
            return
        }
        queue.asyncAfter(deadline: .now() + 60) {
            guard !self.isRecovery, !self.ready, !self.stopRequested, !self.loopReturned, !self.finalized, !self.startupAborted else { return }
            self.checkpoint(.startupTimeout)
            self.report["terminal_startup_timed_out"] = true
            self.report["status"] = "terminal_startup_timeout"
            self.persist()
            self.owner.publish {
                $0.message = $0.isDesktop ? "Desktop readiness was not confirmed within 60 seconds. Serial recovery and Stop remain available once the supervisor is ready. Save the report; the disk remains locked until app exit." : "Linux terminal readiness was not confirmed within 60 seconds. No forced stop was attempted. Save the report; the disk remains locked until app exit."
            }
        }
    }

    /// The bridge sequence is an existing atomic counter, not proof of Steam UI
    /// or non-black pixels. Never lock/copy a frame or touch BQL from this poll.
    private func observeDisplay(started: TimeInterval) {
        guard !loopReturned, !stopRequested, !stopFailed, !startupAborted else { return }
        if husk_display_sequence() > 0 {
            report["display_frame_observed"] = true; persist()
            owner.publish { $0.displayHasFrame = true }
            return
        }
        if ProcessInfo.processInfo.systemUptime - started >= 60, report["display_frame_timed_out"] as? Bool != true {
            report["display_frame_timed_out"] = true; persist()
            owner.publish { $0.displayTimedOut = true }
            // Continue observing: a late real frame can replace the waiting UI.
        }
        queue.asyncAfter(deadline: .now() + 1) { self.observeDisplay(started: started) }
    }

    private func acceptRecoveryActivity() -> Bool {
        guard !recoveryTimedOut, !stopFailed else { return false }
        if !stopRequested, let reason = recoveryWatchdog?.timeout(at: ProcessInfo.processInfo.systemUptime) {
            recoveryTimeout(reason); return false
        }
        return true
    }

    private func armRecoveryTimeout() {
        guard isRecovery, !recoveryProgress.done, !recoveryTimedOut, !stopFailed, !stopRequested,
              !loopReturned, !finalized, !startupAborted, let watchdog = recoveryWatchdog else { return }
        recoveryWatchdogRevision &+= 1
        let revision = recoveryWatchdogRevision
        let delay = max(0, watchdog.nextDeadline - ProcessInfo.processInfo.systemUptime)
        queue.asyncAfter(deadline: .now() + delay) {
            guard revision == self.recoveryWatchdogRevision, !self.recoveryProgress.done, !self.recoveryTimedOut,
                  !self.stopFailed, !self.stopRequested, !self.loopReturned, !self.finalized, !self.startupAborted else { return }
            if let reason = self.recoveryWatchdog?.timeout(at: ProcessInfo.processInfo.systemUptime) { self.recoveryTimeout(reason) }
            else { self.armRecoveryTimeout() }
        }
    }

    private func recoveryTimeout(_ reason: LinuxRecoveryWatchdog.Timeout) {
        guard !recoveryTimedOut, !stopFailed, !stopRequested, !loopReturned, !finalized, !startupAborted else { return }
        recoveryTimedOut = true; stopFailed = true; ready = false
        recoveryWatchdogRevision &+= 1
        lifecycle.record(.failed)
        checkpoint(.recoveryTimeout, failure: .recoveryFailed)
        report["recovery_watchdog_timeout"] = reason.rawValue
        report["terminal_clean_stop"] = false; report["status"] = "terminal_recovery_timeout"
        do { try recovery?.recordFailure("watchdog_" + reason.rawValue) } catch { owner.publish { $0.diagnosticFailure() } }
        persist()
        let canStop = guestWasReady && (control?.peer ?? -1) >= 0
        owner.publish {
            $0.ready = false; $0.serialReady = false; $0.desktopInput?.setFocused(false)
            $0.canStop = canStop
            $0.message = "Recovery exceeded its \(reason.rawValue) time limit. No copy can be activated from this attempt. Original and backup remain preserved; save diagnostics and use Stop when available. The disk stays locked until app exit."
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

    private func prepareRecovery(_ profile: LinuxGUIProfile) throws {
        guard owner.isDesktop, !owner.isSteam, !enteredQEMU else { throw LinuxGUIRecovery.Invalid.relaunch }
        try preparationCheckpoint(.recoveryCopies)
        isRecovery = true; report["recovery_requested"] = true
        owner.publish { $0.recoveryMode = true }
        let transaction = try LinuxGUIRecovery.prepare(directory: dataDirectory, specification: profile.image, observe: observeSuperblock) { stage in
            self.checkpoint(stage == "backup" ? .recoveryBackup : (stage == "work_copy" ? .recoveryWorkCopy : .recoveryPrepared))
            self.report["recovery_phase"] = stage; self.persist()
            self.owner.publish {
                $0.preparationState = self.preparation.snapshot
                if self.preparation.snapshot.canCancel { $0.message = "Recovery: \(stage). Preserving the original and verifying a separate work copy…" }
            }
        }
        recovery = transaction; disk = transaction
    }

    private func preparationCheckpoint(_ phase: LinuxStartupPreparation.Phase) throws {
        try preparation.advance(phase)
        report["preparation_phase"] = phase.rawValue
        persist()
        owner.publish {
            let state = self.preparation.snapshot
            $0.preparationState = state
            if state.inProgress { $0.message = state.message + " Keep iDeck open; cancellation waits for the current file operation." }
        }
    }

    /// Called synchronously by the existing locked preboot header validator.
    /// No second disk open, file-content read, mount or repair is performed.
    private func observeSuperblock(_ value: LinuxDesktopDisk.RecoveryObservation) {
        report["ext4_recover_bit"] = value.recoverBit
        report["ext4_state"] = value.state
        report["ext4_last_orphan"] = value.lastOrphan
        report["ext4_error_count"] = value.errorCount
        let state = LinuxTerminalDiagnostics.Ext4State(recoverBit: value.recoverBit, state: value.state,
                                                      lastOrphan: value.lastOrphan, errorCount: value.errorCount)
        do { try diagnostic.record(.diskInspected, ext4: state) }
        catch { owner.publish { $0.diagnosticFailure() } }
        persist()
    }

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
