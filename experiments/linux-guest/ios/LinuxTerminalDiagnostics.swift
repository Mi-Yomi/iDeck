import Foundation
#if canImport(Darwin)
import Darwin
#else
import Glibc
#endif

/// Ordinary-thread diagnostics only. No signal handlers, runtime calls, user
/// disk access, arbitrary error text, argv, pairing data or automatic uploads.
final class LinuxTerminalDiagnostics {
    enum Failure: String, Codable {
        case unknown, configuration, asset, disk, diskLocked, io, unsafePath, sessionAlreadyExists
        case assetDescriptor, assetDirectory, assetInspection, assetType, assetSize
        case assetContainment, assetRead, assetContentSize, assetDigest, assetKernelMismatch
        case diskTrustedDirectory, diskDirectoryURL, diskDirectoryComponent, diskDirectoryType
        case diskDirectoryInspection, diskInspection, diskOpen, diskLinks, diskMetadata
        case diskSize, diskHeaderRead, diskFormat, diskSeedSize, diskOwnership
        case specification, directory, inspection, open, locked, metadata, size, headerRead
        case checksum, filesystem, uuid, geometry, features, journal, needsRecovery, ownership
        case alreadyExists, insufficientSpace, profile, assetMetadata, recoveryFailed
    }
    enum Stage: String, Codable, CaseIterable {
        case opened, jitEnableBegin, jitEnableDispatched, jitClaimBegin, jitClaimReturned, jitUnavailable
        case startRequested, jitReadyBegin, jitReadyReturned, jitExecutionBegin, jitExecutionReturned
        case runtimeOwnershipBegin, runtimeOwnershipReturned, startRejected, documentsBegin, documentsReturned, assetsBegin, assetsReturned
        case diskBegin, diskInspected, diskReturned, socketsBegin, socketsReturned, argumentsBegin, argumentsReturned
        case reportBegin, reportReturned, argvBegin, argvReturned, threadStarting
        case qemuInitBegin, qemuInitReturned, nativeJITCheckBegin, nativeJITCheckReturned
        case displayInitBegin, displayInitReturned, mainLoopBegin, mainLoopReturned
        case terminalReady, stopRequested, guestCleanUnmount, hostSyncBegin, hostDiskSynced
        case cleanStopped, stopFailed, uncleanStopped, preparationFailed, preparationCancelRequested, preparationCancelled, startupTimeout, stopTimeout
        case qemuOwnerThreadRetained, consoleLogCloseBegin, consoleLogCloseReturned
        case consolePeersCloseBegin, consolePeersCloseReturned
        case recoveryBackup, recoveryWorkCopy, recoveryPrepared, recoveryAssessment, recoveryReplay, recoveryVerified, recoveryRelaunch, recoveryTimeout
    }
    enum Problem: Error { case directory, open, metadata, read, write, synchronize, limit, invalid }
    struct Ext4State: Codable, Equatable {
        let recoverBit: Bool
        let state: UInt32
        let lastOrphan: UInt32
        let errorCount: UInt32
        var markdown: [String] {
            ["", "## Ext4 startup metadata", "", "| Field | Observed value |", "| --- | --- |",
             "| RECOVER bit | \(recoverBit ? "SET" : "CLEAR") |", "| state (raw) | \(state) |",
             "| last_orphan | \(lastOrphan) |", "| error_count | \(errorCount) |", "",
             "Observed during locked preboot superblock validation. These fields are not an fsck or a diagnosis of why the state arose. No user-file contents are included."]
        }
    }
    struct Record: Codable {
        let schema: Int
        let sequence: Int
        let stage: Stage
        let utc: String
        let elapsedMilliseconds: Int
        let source: String
        let build: String
        let failure: Failure?
        let ext4: Ext4State?
        init(schema: Int, sequence: Int, stage: Stage, utc: String, elapsedMilliseconds: Int,
             source: String, build: String, failure: Failure?, ext4: Ext4State? = nil) {
            self.schema = schema; self.sequence = sequence; self.stage = stage; self.utc = utc
            self.elapsedMilliseconds = elapsedMilliseconds; self.source = source; self.build = build
            self.failure = failure; self.ext4 = ext4
        }
    }
    struct Snapshot {
        let id: String
        let records: [Record]
        let tornTail: Bool
        let invalid: Bool
        let nativeBytes: Int?
        let appLogBytes: Int?

        var clean: Bool {
            let stages = records.map(\.stage)
            guard let clean = stages.firstIndex(of: .cleanStopped),
                  let unmount = stages.firstIndex(of: .guestCleanUnmount),
                  let loop = stages.firstIndex(of: .mainLoopReturned),
                  let sync = stages.firstIndex(of: .hostDiskSynced) else { return false }
            // Older receipts end at cleanStopped. New ones append bounded tail
            // checkpoints; neither receipt proves backend teardown or survival.
            let tail = Array(stages.dropFirst(clean + 1))
            return unmount < sync && loop < sync && sync < clean
                && tail == Array(Self.shutdownTail.prefix(tail.count)) && tail.count <= Self.shutdownTail.count
                && !stages.contains(.stopFailed) && !invalid && !tornTail
        }
        private static let shutdownTail: [Stage] = [.consoleLogCloseBegin, .consoleLogCloseReturned,
                                                   .consolePeersCloseBegin, .consolePeersCloseReturned]
        var shutdownTailReturned: Bool {
            guard clean, let cleanIndex = records.firstIndex(where: { $0.stage == .cleanStopped }) else { return false }
            return Array(records.dropFirst(cleanIndex + 1).map(\.stage)) == Self.shutdownTail
        }
        func markdown(previousProcess: Bool) -> String {
            let last = records.last
            let attempted = records.contains { $0.stage == .startRequested }
            let nativeObserved = records.contains { [Stage.qemuInitReturned, .mainLoopBegin, .terminalReady].contains($0.stage) }
            let outcome: String
            if clean { outcome = "Confirmed orderly stop: guest unmount, QEMU loop return and host sync were recorded." }
            else if !invalid && !tornTail && last?.stage == .startRejected {
                outcome = "Start was rejected before VM entry; no successful terminal run was recorded."
            } else if !invalid && !tornTail && !nativeObserved && records.contains(where: { $0.stage == .preparationFailed }) {
                outcome = "Preparation failed before QEMU entry; no successful terminal run was recorded."
            } else if !invalid && !tornTail && records.contains(where: { $0.stage == .preparationCancelled })
                        && !nativeObserved {
                outcome = "Startup was cancelled before native entry. Completed copies were preserved; reopen the app before another attempt."
            } else if previousProcess && attempted { outcome = "Previous process ended without a confirmed clean stop. Cause UNKNOWN." }
            else if previousProcess { outcome = "Previous diagnostic session ended; no VM start request was recorded. Cause UNKNOWN." }
            else { outcome = "Current diagnostic session; orderly stop is not established." }
            var lines = ["# iDeck Terminal Startup Diagnostics", "", outcome, "",
                "| Field | Value |", "| --- | --- |", "| Attempt | \(id) |",
                "| Source commit | \(last?.source ?? "UNKNOWN") |", "| App build | \(last?.build ?? "UNKNOWN") |",
                "| Last saved checkpoint | \(last?.stage.rawValue ?? "UNKNOWN") |",
                "| Host log/socket close path returned | \(shutdownTailReturned ? "RECORDED" : "NOT ESTABLISHED") |",
                "| Incomplete final record | \(tornTail ? "YES" : "NO") |",
                "| Invalid or oversized journal | \(invalid ? "YES" : "NO") |",
                "| Native stderr snapshot bytes | \(nativeBytes.map(String.init) ?? "NOT AVAILABLE") |",
                "| Native log association | UNKNOWN: rotating previous-launch candidate, not independently matched |",
                "| App log snapshot bytes | \(appLogBytes.map(String.init) ?? "NOT AVAILABLE") |", "",
                "## Saved checkpoints", "", "| Sequence | UTC | Elapsed ms | Checkpoint | Known failure |",
                "| --- | --- | --- | --- | --- |"]
            for record in records {
                lines.append("| \(record.sequence) | \(record.utc) | \(record.elapsedMilliseconds) | \(record.stage.rawValue) | \(record.failure?.rawValue ?? "none recorded") |")
            }
            if let ext4 = records.compactMap(\.ext4).last { lines += ext4.markdown }
            lines += ["", "A checkpoint identifies code reached, not the cause of termination. Missing checkpoints do not prove which instruction failed.",
                "Native exit, crash, manual close and Jetsam/SIGKILL cannot be distinguished by this journal alone. System IPS/Jetsam reports are not accessible through this app sandbox.",
                "Native stderr/app log snapshots are preserved locally when available, separately from this Markdown. Their arbitrary text, paths, commands and possible private data are excluded from this export.",
                "No pairing records, tokens, argv, console transcript or personal filesystem paths are included. Nothing is uploaded automatically.",
                "An orderly-stop receipt does not verify QEMU block-layer teardown or file persistence after a second guest boot.", ""]
            lines += ["Owner-thread retention records entry to a process-lifetime wait on the same QEMU thread. It does not record RCU unregister or backend drain.",
                "Log/socket tail checkpoints record code reached and return from close attempts, not IO success or continued process health.", ""]
            return lines.joined(separator: "\n")
        }
    }

    static let maximumBytes = 128 * 1024
    static let maximumRecords = 256
    let directory: URL
    private let rootFD: Int32
    private let documentsFD: Int32
    private let synchronize: (Int32) -> Int32

    init(documents: URL, synchronize: @escaping (Int32) -> Int32 = { fsync($0) }) throws {
        guard documents.isFileURL, !documents.path.contains("\0"),
              let resolved = realpath(documents.path, nil) else { throw Problem.directory }
        defer { free(resolved) }
        let root = URL(fileURLWithPath: String(cString: resolved), isDirectory: true)
        let docFD = open(root.path, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC)
        guard docFD >= 0 else { throw Problem.directory }
        var accepted = false
        defer { if !accepted { close(docFD) } }
        if mkdirat(docFD, "iDeckDiagnostics", mode_t(0o700)) != 0, errno != EEXIST { throw Problem.directory }
        let fd = openat(docFD, "iDeckDiagnostics", O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC)
        guard fd >= 0 else { throw Problem.directory }
        self.documentsFD = docFD; self.rootFD = fd
        self.directory = root.appendingPathComponent("iDeckDiagnostics", isDirectory: true)
        self.synchronize = synchronize
        accepted = true
    }
    deinit { close(rootFD); close(documentsFD) }

    private static func validID(_ id: String) -> Bool {
        let bytes = Array(id.utf8)
        guard bytes.count == 50, bytes[13] == 45,
              bytes.prefix(13).allSatisfy({ (48...57).contains($0) }) else { return false }
        let uuid = String(id.dropFirst(14))
        return UUID(uuidString: uuid)?.uuidString == uuid
    }
    private static func basename(_ id: String, _ suffix: String) throws -> String {
        guard validID(id), ["jsonl", "md", "native.md", "native.txt", "app.txt", "capture.txt"].contains(suffix) else { throw Problem.invalid }
        return "attempt-" + id + "." + suffix
    }
    private static func stamp() -> String {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return formatter.string(from: Date())
    }
    private func checkedOpen(_ name: String, flags: Int32) throws -> Int32 {
        let fd = openat(rootFD, name, flags | O_NOFOLLOW | O_CLOEXEC | O_NONBLOCK, mode_t(0o600))
        guard fd >= 0 else { throw Problem.open }
        var state = stat()
        guard fstat(fd, &state) == 0, (state.st_mode & S_IFMT) == S_IFREG, state.st_nlink == 1 else {
            close(fd); throw Problem.metadata
        }
        return fd
    }
    private func writeAll(_ data: Data, fd: Int32) throws {
        try data.withUnsafeBytes { bytes in
            var offset = 0
            while offset < bytes.count {
                let count = write(fd, bytes.baseAddress!.advanced(by: offset), bytes.count - offset)
                if count < 0, errno == EINTR { continue }
                guard count > 0 else { throw Problem.write }
                offset += count
            }
        }
        guard synchronize(fd) == 0 else { throw Problem.synchronize }
    }
    private func read(_ name: String, maximum: Int) throws -> Data {
        let fd = try checkedOpen(name, flags: O_RDONLY)
        defer { close(fd) }
        var result = Data()
        var buffer = [UInt8](repeating: 0, count: 4096)
        while result.count <= maximum {
            let count = buffer.withUnsafeMutableBytes { bytes in
                FoundationRead(fd, bytes.baseAddress!, min(bytes.count, maximum + 1 - result.count))
            }
            if count < 0, errno == EINTR { continue }
            guard count >= 0 else { throw Problem.read }
            if count == 0 { break }
            result.append(contentsOf: buffer.prefix(count))
        }
        guard result.count <= maximum else { throw Problem.limit }
        return result
    }
    private func snapshotSize(_ id: String, suffix: String) -> Int? {
        guard let name = try? Self.basename(id, suffix), let fd = try? checkedOpen(name, flags: O_RDONLY) else { return nil }
        defer { close(fd) }
        var state = stat()
        guard fstat(fd, &state) == 0, state.st_size <= 1024 * 1024 else { return nil }
        return Int(state.st_size)
    }
    func snapshot(id: String) throws -> Snapshot {
        let name = try Self.basename(id, "jsonl")
        let data: Data
        do { data = try read(name, maximum: Self.maximumBytes) }
        catch Problem.limit { return Snapshot(id: id, records: [], tornTail: false, invalid: true,
                                             nativeBytes: snapshotSize(id, suffix: "native.txt"), appLogBytes: snapshotSize(id, suffix: "app.txt")) }
        var records = [Record]()
        var invalid = false
        let lines = data.split(separator: 10, omittingEmptySubsequences: false)
        for line in lines.dropLast() {
            guard line.count <= 1024, records.count < Self.maximumRecords,
                  let record = try? JSONDecoder().decode(Record.self, from: Data(line)),
                  record.schema == 1, record.sequence == records.count,
                  record.elapsedMilliseconds >= 0, record.utc.utf8.count == 24,
                  record.utc.utf8.allSatisfy({ (48...57).contains($0) || "-T:.Z".utf8.contains($0) }),
                  (record.source == "UNKNOWN" || (record.source.utf8.count == 40 && record.source.utf8.allSatisfy({ "0123456789abcdef".utf8.contains($0) }))),
                  record.build == "UNKNOWN" || (record.build.utf8.count <= 16 && !record.build.isEmpty && record.build.utf8.allSatisfy({ (48...57).contains($0) })),
                  !records.isEmpty || record.stage == .opened,
                  record.ext4 == nil || (record.stage == .diskInspected && record.ext4!.state <= UInt32(UInt16.max)) else { invalid = true; break }
            records.append(record)
        }
        return Snapshot(id: id, records: records, tornTail: data.last != 10, invalid: invalid,
                        nativeBytes: snapshotSize(id, suffix: "native.txt"), appLogBytes: snapshotSize(id, suffix: "app.txt"))
    }
    func recover(excluding: String? = nil) throws -> [Snapshot] {
        let names = try FileManager.default.contentsOfDirectory(atPath: directory.path)
        guard names.count <= 4096 else { throw Problem.limit }
        let ids = names.compactMap { name -> String? in
            guard name.hasPrefix("attempt-"), name.hasSuffix(".jsonl") else { return nil }
            let id = String(name.dropFirst(8).dropLast(6))
            return Self.validID(id) && id != excluding ? id : nil
        }.sorted(by: >)
        // A bad/symlink file must never supply report content. Report its read
        // failure to the caller rather than silently treating it as success.
        return try ids.prefix(8).map { try snapshot(id: $0) }
    }
    func begin(source: String, build: String) throws -> Journal {
        let id = String(format: "%013lld", Int64(Date().timeIntervalSince1970 * 1000)) + "-" + UUID().uuidString
        let fd = try checkedOpen(Self.basename(id, "jsonl"), flags: O_WRONLY | O_CREAT | O_EXCL | O_APPEND)
        let safeSource = source.utf8.count == 40 && source.utf8.allSatisfy({ "0123456789abcdef".utf8.contains($0) }) ? source : "UNKNOWN"
        let safeBuild = !build.isEmpty && build.utf8.count <= 16 && build.utf8.allSatisfy({ (48...57).contains($0) }) ? build : "UNKNOWN"
        let journal = Journal(store: self, id: id, fd: fd, source: safeSource, build: safeBuild)
        try journal.record(.opened)
        return journal
    }
    func export(_ snapshot: Snapshot, previousProcess: Bool) throws -> URL {
        try publishMarkdown(snapshot.markdown(previousProcess: previousProcess), id: snapshot.id, suffix: "md")
    }

    /// Explicit manual export only. Arbitrary native/app log lines cannot be
    /// made secret-free with general regex redaction, so map recognized text to
    /// fixed diagnostic labels and omit everything else. Preserve raw files.
    func exportNativeSummary(_ snapshot: Snapshot, previousProcess: Bool) throws -> URL {
        _ = try Self.basename(snapshot.id, "native.md")
        var lines = [snapshot.markdown(previousProcess: previousProcess), "## Native log signatures (manual export)", "",
            "Association UNKNOWN: these are rotating previous-launch candidates, not independently matched to this attempt.",
            "Signature presence describes log text only; it does not identify the cause of termination.",
            "Only fixed recognized labels are exported. Unknown lines, paths, addresses, commands and possible credentials remain local.", ""]
        for (label, suffix) in [("Native stderr", "native.txt"), ("App log", "app.txt")] {
            let name = try Self.basename(snapshot.id, suffix)
            var state = stat()
            lines += ["### " + label, ""]
            if fstatat(rootFD, name, &state, AT_SYMLINK_NOFOLLOW) != 0 {
                guard errno == ENOENT else { throw Problem.metadata }
                lines += ["Snapshot NOT AVAILABLE. No current/rotated log was substituted.", ""]
                continue
            }
            let data = try read(name, maximum: 1024 * 1024)
            let summary = Self.nativeSignatures(data)
            lines += ["Snapshot bytes: \(data.count).", "", "| Recognized text signature |", "| --- |"]
            lines += summary.labels.isEmpty ? ["| NONE RECOGNIZED |"] : summary.labels.map { "| \($0) |" }
            lines += ["", "Omitted/unrecognized lines: \(summary.omitted).", ""]
        }
        return try publishMarkdown(lines.joined(separator: "\n"), id: snapshot.id, suffix: "native.md")
    }

    private static func nativeSignatures(_ data: Data) -> (labels: [String], omitted: Int) {
        // No matched source substring, regex capture or arbitrary value is ever
        // copied to the export. Even a forged line can only select a fixed label.
        let catalog: [(String, String)] = [
            ("husk: could not obtain", "QEMU JIT allocation error text"),
            ("prewarm OK:", "JIT prewarm OK text"),
            ("prewarm FAILED:", "JIT prewarm FAILED text"),
            ("using the prewarmed region", "QEMU using prewarmed JIT region text"),
            ("'wait' option is incompatible", "Socket wait option incompatibility text"),
            ("'reconnect' option is incompatible", "Socket reconnect option incompatibility text"),
            ("is not a socket", "File descriptor is not a socket text"),
            ("Unable to parse FD number", "Socket descriptor parse error text"),
            ("Unable to query remote socket address", "Remote socket address query error text"),
            ("Unable to query local socket address", "Local socket address query error text"),
            ("Failed to create chardev", "QEMU chardev creation failure text"),
            ("Failed to get", "Resource acquisition failure text (generic)"),
            ("Could not open", "File/resource open failure text (generic)"),
            ("Failed to lock byte", "QEMU block byte-lock failure text"),
            ("Failed to lock byte 100.", "KNOWN ERROR: QEMU block byte 100 lock conflict text (association UNKNOWN)"),
            ("Cannot allocate memory", "Memory allocation failure text"),
            ("Assertion failed:", "Native assertion text"),
            ("assertion failed:", "Native assertion text"),
            ("ERROR:", "Native error marker text (generic)"),
            ("init: registering DisplayChangeListener", "Display listener registration begin text"),
            ("init: listener registered", "Display listener registration completed text"),
            ("qemu_console_lookup_by_index(0) returned NULL", "No QEMU graphics console text"),
            ("*** FATAL SIGNAL", "Fatal signal marker text (signal/cause not inferred)")
        ]
        var found = Set<String>()
        var omitted = 0
        for (index, line) in String(decoding: data, as: UTF8.self).split(separator: "\n").enumerated() {
            guard index < 4096, line.utf8.count <= 2048 else { omitted += 1; continue }
            var recognized = false
            for (pattern, label) in catalog where line.contains(pattern) { found.insert(label); recognized = true }
            if !recognized { omitted += 1 }
        }
        return (found.sorted(), omitted)
    }

    private func publishMarkdown(_ text: String, id: String, suffix: String) throws -> URL {
        let name = try Self.basename(id, suffix)
        let temporary = ".export-" + UUID().uuidString
        let fd = try checkedOpen(temporary, flags: O_WRONLY | O_CREAT | O_EXCL)
        defer { close(fd); unlinkat(rootFD, temporary, 0) }
        try writeAll(Data(text.utf8), fd: fd)
        guard renameat(rootFD, temporary, rootFD, name) == 0 else { throw Problem.write }
        return directory.appendingPathComponent(name)
    }
    /// Capture prior launch logs once, before Husk rotates them again. Preserve
    /// raw originals locally, never include their arbitrary text in Markdown.
    func preservePreviousLogs(id: String) throws {
        // Reserve the association attempt BEFORE reading any rotating files.
        // Even absent logs must not be filled by unrelated later launches.
        let receipt = try Self.basename(id, "capture.txt")
        var receiptState = stat()
        if fstatat(rootFD, receipt, &receiptState, AT_SYMLINK_NOFOLLOW) == 0 {
            guard (receiptState.st_mode & S_IFMT) == S_IFREG, receiptState.st_nlink == 1 else { throw Problem.metadata }
            return
        }
        guard errno == ENOENT else { throw Problem.metadata }
        let receiptFD = try checkedOpen(receipt, flags: O_WRONLY | O_CREAT | O_EXCL)
        defer { close(receiptFD) }
        try writeAll(Data("Rotating previous-launch log capture attempted; association UNKNOWN.\n".utf8), fd: receiptFD)
        for (input, suffix) in [("husk-native-prev.log", "native.txt"), ("husk-prev.log", "app.txt")] {
            let output = try Self.basename(id, suffix)
            var state = stat()
            if fstatat(rootFD, output, &state, AT_SYMLINK_NOFOLLOW) == 0 {
                guard (state.st_mode & S_IFMT) == S_IFREG, state.st_nlink == 1 else { throw Problem.metadata }
                continue
            }
            guard errno == ENOENT else { throw Problem.metadata }
            let source = openat(documentsFD, input, O_RDONLY | O_NOFOLLOW | O_CLOEXEC | O_NONBLOCK)
            if source < 0 { if errno == ENOENT { continue }; throw Problem.open }
            defer { close(source) }
            guard fstat(source, &state) == 0, (state.st_mode & S_IFMT) == S_IFREG, state.st_nlink == 1 else { throw Problem.metadata }
            let offset = max(0, state.st_size - 1024 * 1024)
            guard lseek(source, offset, SEEK_SET) >= 0 else { throw Problem.read }
            var bytes = Data()
            var buffer = [UInt8](repeating: 0, count: 4096)
            while bytes.count < 1024 * 1024 {
                let count = buffer.withUnsafeMutableBytes { FoundationRead(source, $0.baseAddress!, min($0.count, 1024 * 1024 - bytes.count)) }
                if count < 0, errno == EINTR { continue }
                guard count >= 0 else { throw Problem.read }
                if count == 0 { break }
                bytes.append(contentsOf: buffer.prefix(count))
            }
            // Publish only a fully copied/synchronized snapshot. A partial copy
            // never becomes the permanent first snapshot on the next relaunch.
            let temporary = ".capture-" + UUID().uuidString
            let target = try checkedOpen(temporary, flags: O_WRONLY | O_CREAT | O_EXCL)
            defer { close(target); unlinkat(rootFD, temporary, 0) }
            try writeAll(bytes, fd: target)
            guard linkat(rootFD, temporary, rootFD, output, 0) == 0 else { throw Problem.write }
        }
    }

    final class Journal: @unchecked Sendable {
        let id: String
        private let store: LinuxTerminalDiagnostics
        private let fd: Int32
        private let source: String
        private let build: String
        private let began = ProcessInfo.processInfo.systemUptime
        private let lock = NSLock()
        private var sequence = 0
        private var count = 0
        private var failed = false
        fileprivate init(store: LinuxTerminalDiagnostics, id: String, fd: Int32, source: String, build: String) {
            self.store = store; self.id = id; self.fd = fd; self.source = source; self.build = build
        }
        deinit { close(fd) }
        func record(_ stage: Stage, failure: Failure? = nil, ext4: Ext4State? = nil) throws {
            lock.lock(); defer { lock.unlock() }
            guard !failed else { throw Problem.write }
            guard ext4 == nil || (stage == .diskInspected && ext4!.state <= UInt32(UInt16.max)) else { throw Problem.invalid }
            guard sequence < LinuxTerminalDiagnostics.maximumRecords else { throw Problem.limit }
            let record = Record(schema: 1, sequence: sequence, stage: stage, utc: LinuxTerminalDiagnostics.stamp(),
                elapsedMilliseconds: max(0, Int((ProcessInfo.processInfo.systemUptime - began) * 1000)), source: source, build: build, failure: failure, ext4: ext4)
            var bytes = try JSONEncoder().encode(record); bytes.append(10)
            guard bytes.count <= 1024, count + bytes.count <= LinuxTerminalDiagnostics.maximumBytes else { throw Problem.limit }
            do { try store.writeAll(bytes, fd: fd) }
            catch { failed = true; throw error }
            sequence += 1; count += bytes.count
        }
        func snapshot() throws -> Snapshot {
            lock.lock(); defer { lock.unlock() }
            let value = try store.snapshot(id: id)
            return Snapshot(id: value.id, records: value.records, tornTail: value.tornTail,
                            invalid: value.invalid || failed, nativeBytes: value.nativeBytes, appLogBytes: value.appLogBytes)
        }
    }
}

// Avoid colliding with this type's bounded read helper, while executing the
// real platform syscall in both Apple and Linux helper checks.
private func FoundationRead(_ fd: Int32, _ buffer: UnsafeMutableRawPointer, _ count: Int) -> Int {
#if canImport(Darwin)
    return Darwin.read(fd, buffer, count)
#else
    return Glibc.read(fd, buffer, count)
#endif
}
