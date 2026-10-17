import Foundation
import CryptoKit
import Darwin

/// GUI-only, clone-only transaction. No QEMU teardown or same-process promotion.
/// Every descriptor stays owned by the worker after native entry until app exit.
final class LinuxGUIRecovery: LinuxConsoleDisk {
    enum Invalid: Error { case metadata, busy, io, space, changed, receipt, manualReview, relaunch }
    enum Phase: String, Codable { case copying, prepared, running, verified, promoting, promoted, manualReview }
    struct Receipt: Codable {
        var schema = 1
        var id: String
        var phase: Phase
        var process: String
        var sourceSHA256: String
        var recoveredSHA256: String?
        var sourceInode: UInt64
        var sourceDevice: Int64
        var sourceMode: UInt32
        var sourceUID: UInt32
        var sourceGID: UInt32
        var size: Int64
        var uuid: String
        var assessment: Int?
        var replay: Int?
        var verification: Int?
        var toolSeedSHA256: String?
        var suffixSHA256: String?
        var failure: String?
        var scanClean: Bool?
        var summaryReconciled: Bool?
    }
    static let process = UUID().uuidString.lowercased()
    let directory: URL
    let specification: LinuxDesktopDisk.Specification
    private(set) var receipt: Receipt?
    private var parent: Int32 = -1
    private var root: Int32 = -1
    private var generation: Int32 = -1
    private var lease: Int32 = -1
    private var source: Int32 = -1
    private var backup: Int32 = -1
    private var work: Int32 = -1
    var url: URL { directory.appendingPathComponent(".recovery-v1/" + (receipt?.id ?? "INVALID") + "/work.raw") }
    private var rootURL: URL { directory.appendingPathComponent(".recovery-v1", isDirectory: true) }

    private init(directory: URL, specification: LinuxDesktopDisk.Specification) throws {
        self.directory = directory; self.specification = specification
        do {
        try specification.validate()
        guard specification.uuid == LinuxGUIProfile.uuid, specification.sizeBytes == LinuxGUIProfile.size else { throw Invalid.metadata }
        try LinuxDesktopDisk.validateDirectory(directory)
        parent = Darwin.open(directory.path, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC)
        guard parent >= 0 else { throw Invalid.io }
        if mkdirat(parent, ".recovery-v1", 0o700) != 0, errno != EEXIST { throw Invalid.io }
        root = openat(parent, ".recovery-v1", O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC)
        guard root >= 0 else { throw Invalid.metadata }
        lease = openat(root, "lease", O_RDWR | O_CREAT | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC, 0o600)
        try regular(lease, size: nil)
        guard flock(lease, LOCK_EX | LOCK_NB) == 0 else { throw Invalid.busy }
        source = openat(parent, "rootfs-v1.raw", O_RDONLY | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC)
        try regular(source, size: specification.sizeBytes)
        guard flock(source, LOCK_EX | LOCK_NB) == 0 else { throw Invalid.busy }
        try sourceIdentity()
        receipt = try readReceipt()
        if let receipt {
            guard receipt.schema == 1, UUID(uuidString: receipt.id)?.uuidString.lowercased() == receipt.id,
                  UUID(uuidString: receipt.process) != nil, receipt.size == specification.sizeBytes,
                  receipt.uuid == specification.uuid, Self.digest(receipt.sourceSHA256),
                  receipt.sourceMode <= 0o777, receipt.sourceUID == geteuid(),
                  receipt.recoveredSHA256 == nil || Self.digest(receipt.recoveredSHA256!) else { throw Invalid.receipt }
            generation = openat(root, receipt.id, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC)
            guard generation >= 0 else { throw Invalid.metadata }
        }
        } catch { closeUnused(); throw error }
    }
    deinit { closeUnused() }
    func closeUnused() {
        for fd in [work, backup, source, lease, generation, root, parent] where fd >= 0 { _ = Darwin.close(fd) }
        work = -1; backup = -1; source = -1; lease = -1; generation = -1; root = -1; parent = -1
    }
    fileprivate static func digest(_ value: String) -> Bool {
        value.utf8.count == 64 && value.utf8.allSatisfy { "0123456789abcdef".utf8.contains($0) }
    }
    private func regular(_ fd: Int32, size: Int64?) throws {
        var state = stat()
        guard fd >= 0, fstat(fd, &state) == 0, state.st_mode & S_IFMT == S_IFREG,
              state.st_nlink == 1, state.st_uid == geteuid(), size == nil || state.st_size == size! else { throw Invalid.metadata }
    }
    private func matches(_ fd: Int32, directory: Int32, name: String) throws {
        var opened = stat(), named = stat()
        guard fstat(fd, &opened) == 0, fstatat(directory, name, &named, AT_SYMLINK_NOFOLLOW) == 0,
              opened.st_dev == named.st_dev, opened.st_ino == named.st_ino,
              named.st_mode & S_IFMT == S_IFREG, named.st_nlink == 1 else { throw Invalid.changed }
    }
    private func sourceIdentity() throws {
        try regular(source, size: specification.sizeBytes)
        try matches(source, directory: parent, name: "rootfs-v1.raw")
        var pinned = stat(), named = stat()
        guard fstat(parent, &pinned) == 0, lstat(directory.path, &named) == 0,
              pinned.st_dev == named.st_dev, pinned.st_ino == named.st_ino else { throw Invalid.changed }
        guard flock(source, LOCK_EX | LOCK_NB) == 0 else { throw Invalid.busy }
    }
    func validateOwnership() throws {
        try sourceIdentity()
        try regular(work, size: specification.sizeBytes)
        try matches(work, directory: generation, name: "work.raw")
        var named = stat(), pinned = stat()
        guard lstat(url.path, &named) == 0, fstat(work, &pinned) == 0,
              named.st_dev == pinned.st_dev, named.st_ino == pinned.st_ino,
              flock(work, LOCK_EX | LOCK_NB) == 0 else { throw Invalid.changed }
    }
    func synchronize() throws { try validateOwnership(); guard fsync(work) == 0 else { throw Invalid.io } }
    private func hash(_ fd: Int32) throws -> String {
        try regular(fd, size: specification.sizeBytes)
        var hash = SHA256(), offset: Int64 = 0
        var buffer = [UInt8](repeating: 0, count: 1024 * 1024)
        while offset < specification.sizeBytes {
            let amount = min(buffer.count, Int(specification.sizeBytes - offset))
            let count = buffer.withUnsafeMutableBytes { pread(fd, $0.baseAddress!, amount, off_t(offset)) }
            if count < 0, errno == EINTR { continue }
            guard count > 0 else { throw Invalid.io }
            hash.update(data: Data(buffer.prefix(count))); offset += Int64(count)
        }
        return hash.finalize().map { String(format: "%02x", $0) }.joined()
    }
    private func readReceipt() throws -> Receipt? {
        let fd = openat(root, "current.json", O_RDONLY | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC)
        if fd < 0, errno == ENOENT { return nil }
        defer { if fd >= 0 { close(fd) } }
        try regular(fd, size: nil)
        var state = stat(); guard fstat(fd, &state) == 0, state.st_size > 0, state.st_size <= 16384 else { throw Invalid.receipt }
        let data = try FileHandle(fileDescriptor: fd, closeOnDealloc: false).read(upToCount: 16385) ?? Data()
        guard data.count == Int(state.st_size) else { throw Invalid.receipt }
        return try JSONDecoder().decode(Receipt.self, from: data)
    }
    private func write(_ data: Data, directory: Int32, name: String) throws {
        let temporary = ".state-" + UUID().uuidString
        let fd = openat(directory, temporary, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0o600)
        guard fd >= 0 else { throw Invalid.io }
        defer { close(fd) }
        try data.withUnsafeBytes { try LinuxDesktopDisk.writeAll(fd, bytes: $0) }
        guard fsync(fd) == 0, renameat(directory, temporary, directory, name) == 0,
              fsync(directory) == 0 else { throw Invalid.io }
    }
    private func save() throws {
        guard let receipt else { throw Invalid.receipt }
        let data = try JSONEncoder().encode(receipt)
        guard data.count <= 16384 else { throw Invalid.receipt }
        try write(data, directory: generation, name: "receipt.json")
        try write(data, directory: root, name: "current.json")
    }
    private func file(_ name: String, create: Bool) throws -> Int32 {
        let fd = openat(generation, name, O_RDWR | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC | (create ? O_CREAT : 0), 0o600)
        do { try regular(fd, size: nil); guard flock(fd, LOCK_EX | LOCK_NB) == 0 else { throw Invalid.busy }; return fd }
        catch { if fd >= 0 { close(fd) }; throw error }
    }
    private func copy(_ input: Int32, _ output: Int32) throws {
        guard ftruncate(output, 0) == 0, lseek(output, 0, SEEK_SET) == 0 else { throw Invalid.io }
        var offset: Int64 = 0, buffer = [UInt8](repeating: 0, count: 1024 * 1024)
        while offset < specification.sizeBytes {
            let count = buffer.withUnsafeMutableBytes { pread(input, $0.baseAddress!, min($0.count, Int(specification.sizeBytes-offset)), off_t(offset)) }
            if count < 0, errno == EINTR { continue }
            guard count > 0 else { throw Invalid.io }
            try buffer.withUnsafeBytes { try LinuxDesktopDisk.writeAll(output, bytes: UnsafeRawBufferPointer(rebasing: $0.prefix(count))) }
            offset += Int64(count)
        }
        guard fsync(output) == 0 else { throw Invalid.io }
    }

    static func prepare(directory: URL, specification: LinuxDesktopDisk.Specification,
                        availableBytes: ((URL) throws -> Int64)? = nil,
                        observe: ((LinuxDesktopDisk.RecoveryObservation) -> Void)? = nil,
                        progress: ((String) -> Void)? = nil) throws -> LinuxGUIRecovery {
        let transaction = try Self(directory: directory, specification: specification)
        // This method is called only before native entry under the process guard.
        try LinuxDesktopDisk.validateForJournalRecovery(fd: transaction.source, specification: specification, observe: observe)
        let sourceHash = try transaction.hash(transaction.source)
        var state = stat(); guard fstat(transaction.source, &state) == 0 else { throw Invalid.io }
        if transaction.receipt?.phase == .verified || transaction.receipt?.phase == .promoting { throw Invalid.relaunch }
        if transaction.receipt?.phase == .manualReview { throw Invalid.manualReview }
        if transaction.receipt == nil || transaction.receipt?.phase == .promoted {
            let id = UUID().uuidString.lowercased()
            guard mkdirat(transaction.root, id, 0o700) == 0 else { throw Invalid.io }
            if transaction.generation >= 0 { close(transaction.generation) }
            transaction.generation = openat(transaction.root, id, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC)
            guard transaction.generation >= 0, fsync(transaction.root) == 0 else { throw Invalid.io }
            transaction.receipt = Receipt(id: id, phase: .copying, process: process, sourceSHA256: sourceHash,
                sourceInode: UInt64(state.st_ino), sourceDevice: Int64(state.st_dev), sourceMode: UInt32(state.st_mode & 0o777),
                sourceUID: state.st_uid, sourceGID: state.st_gid, size: specification.sizeBytes, uuid: specification.uuid)
            try transaction.save()
        }
        guard var receipt = transaction.receipt, receipt.sourceSHA256 == sourceHash,
              receipt.sourceInode == UInt64(state.st_ino), receipt.sourceDevice == Int64(state.st_dev),
              receipt.sourceUID == state.st_uid, receipt.sourceGID == state.st_gid,
              receipt.sourceMode == UInt32(state.st_mode & 0o777) else { throw Invalid.changed }
        transaction.backup = try transaction.file("original.raw", create: true)
        var backupState = stat()
        guard fstat(transaction.backup, &backupState) == 0 else { throw Invalid.io }
        var backupVerified = false
        if backupState.st_size == specification.sizeBytes { backupVerified = try transaction.hash(transaction.backup) == sourceHash }
        guard backupVerified || receipt.phase == .copying else { throw Invalid.changed }
        transaction.work = try transaction.file("work.raw", create: true)
        // A fresh exclusive lock proves the previous native owner has exited.
        // Discard only this transaction's uncommitted work, never its source or
        // a verified backup. Recheck actual free space AFTER reclaim, not an
        // estimate based on sparse files/APFS clones.
        guard ftruncate(transaction.work, 0) == 0, fsync(transaction.work) == 0 else { throw Invalid.io }
        if !backupVerified {
            guard ftruncate(transaction.backup, 0) == 0, fsync(transaction.backup) == 0 else { throw Invalid.io }
        }
        let free: Int64
        if let availableBytes { free = try availableBytes(directory) }
        else {
            let attributes = try FileManager.default.attributesOfFileSystem(forPath: directory.path)
            guard let bytes = attributes[.systemFreeSize] as? NSNumber else { throw Invalid.space }; free = bytes.int64Value
        }
        let neededCopies: Int64 = backupVerified ? 1 : 2
        guard free >= specification.sizeBytes * neededCopies + 512 * 1024 * 1024 else { throw Invalid.space }
        progress?("backup")
        if !backupVerified {
            try transaction.copy(transaction.source, transaction.backup)
        }
        guard try transaction.hash(transaction.backup) == sourceHash else { throw Invalid.changed }
        progress?("work_copy")
        // Only the disposable work copy may be restarted after an interrupted VM.
        try transaction.copy(transaction.backup, transaction.work)
        guard try transaction.hash(transaction.work) == sourceHash,
              try transaction.hash(transaction.source) == sourceHash else { throw Invalid.changed }
        receipt.phase = .prepared; receipt.process = process; receipt.assessment = nil; receipt.replay = nil; receipt.verification = nil; receipt.failure = nil
        receipt.recoveredSHA256 = nil; receipt.scanClean = nil; receipt.summaryReconciled = nil
        transaction.receipt = receipt; try transaction.save(); try transaction.validateOwnership()
        progress?("prepared")
        return transaction
    }
    func markRunning(toolSeedSHA256: String) throws {
        guard receipt?.phase == .prepared, Self.digest(toolSeedSHA256) else { throw Invalid.receipt }
        receipt?.toolSeedSHA256 = toolSeedSHA256; receipt?.suffixSHA256 = LinuxRecoveryGuest.sha256
        receipt?.phase = .running; try save()
    }
    func recordResult(assessment: Int, replay: Int, verification: Int, scanClean: Bool, imageSHA256: String, summaryReconciled: Bool = false) throws {
        guard receipt?.phase == .running, [0,4].contains(assessment), [0,1].contains(replay), verification == 0,
              scanClean, Self.digest(imageSHA256) else { throw Invalid.manualReview }
        // Receipt only. NEVER inspect/hash/promote a native-owned work image here.
        receipt?.assessment = assessment; receipt?.replay = replay; receipt?.verification = verification
        receipt?.scanClean = true
        receipt?.recoveredSHA256 = imageSHA256
        receipt?.summaryReconciled = summaryReconciled
        receipt?.phase = .verified; try save()
    }
    func recordFailure(_ reason: String) throws {
        guard LinuxRecoveryProgress.failures.contains(reason) else { throw Invalid.receipt }
        receipt?.failure = reason
        receipt?.phase = ["assessment", "replay", "manual_review", "verification_output", "control_receipt", "counter_scope", "counter_eligibility"].contains(reason) ? .manualReview : .running
        try save()
    }

    /// Fresh process only, BEFORE its one native invocation. Old QEMU ownership
    /// must have ended: exclusive source/work locks are required in addition to ID.
    static func promotePending(directory: URL, specification: LinuxDesktopDisk.Specification, toolSeedSHA256: String,
                               fault: ((String) -> Void)? = nil) throws -> Bool {
        guard FileManager.default.fileExists(atPath: directory.appendingPathComponent(".recovery-v1/current.json").path) else { return false }
        let transaction = try Self(directory: directory, specification: specification)
        guard var receipt = transaction.receipt else { return false }
        guard receipt.phase == .verified || receipt.phase == .promoting else { return false }
        guard receipt.process != process else { throw Invalid.relaunch }
        guard [0,4].contains(receipt.assessment ?? -1), [0,1].contains(receipt.replay ?? -1), receipt.verification == 0,
              receipt.scanClean == true, receipt.toolSeedSHA256 == toolSeedSHA256,
              receipt.suffixSHA256 == LinuxRecoveryGuest.sha256,
              let checkedSHA256 = receipt.recoveredSHA256, Self.digest(checkedSHA256) else { throw Invalid.receipt }
        transaction.backup = try transaction.file("original.raw", create: false)
        guard try transaction.hash(transaction.backup) == receipt.sourceSHA256 else { throw Invalid.changed }
        let activeHash = try transaction.hash(transaction.source)
        if receipt.phase == .promoting, activeHash == checkedSHA256 {
            do { try LinuxDesktopDisk.validateSuperblock(fd: transaction.source, specification: specification) }
            catch { receipt.phase = .manualReview; transaction.receipt = receipt; try transaction.save(); throw Invalid.manualReview }
            guard fsync(transaction.parent) == 0, fsync(transaction.generation) == 0 else { throw Invalid.io }
            receipt.phase = .promoted; transaction.receipt = receipt; try transaction.save(); return true
        }
        guard activeHash == receipt.sourceSHA256 else { throw Invalid.changed }
        var state = stat(); guard fstat(transaction.source, &state) == 0,
            UInt64(state.st_ino) == receipt.sourceInode, Int64(state.st_dev) == receipt.sourceDevice,
            state.st_uid == receipt.sourceUID, state.st_gid == receipt.sourceGID,
            UInt32(state.st_mode & 0o777) == receipt.sourceMode else { throw Invalid.changed }
        transaction.work = try transaction.file("work.raw", create: false)
        try transaction.validateOwnership()
        do { try LinuxDesktopDisk.validateSuperblock(fd: transaction.work, specification: specification) }
        catch { receipt.phase = .manualReview; transaction.receipt = receipt; try transaction.save(); throw Invalid.manualReview }
        let recoveredHash = try transaction.hash(transaction.work)
        guard recoveredHash == checkedSHA256 else { throw Invalid.changed }
        var workState = stat(); guard fstat(transaction.work, &workState) == 0 else { throw Invalid.io }
        if workState.st_gid != receipt.sourceGID {
            guard fchown(transaction.work, receipt.sourceUID, receipt.sourceGID) == 0 else { throw Invalid.metadata }
        }
        guard fchmod(transaction.work, mode_t(receipt.sourceMode)) == 0, fsync(transaction.work) == 0 else { throw Invalid.io }
        receipt.phase = .promoting
        transaction.receipt = receipt; try transaction.save(); try transaction.validateOwnership()
        fault?("before_rename")
        guard renameat(transaction.generation, "work.raw", transaction.parent, "rootfs-v1.raw") == 0,
              fsync(transaction.parent) == 0, fsync(transaction.generation) == 0 else { throw Invalid.io }
        fault?("after_rename")
        receipt.phase = .promoted; transaction.receipt = receipt; try transaction.save()
        return true
    }
}

/// Only the dedicated trusted control socket can advance these ordered receipts.
struct LinuxRecoveryProgress {
    static let failures: Set<String> = ["proc", "sys", "dev", "applets", "module", "ext4", "control", "control_open",
        "duplicate_tools", "duplicate_work", "disk_identity", "extra_disk", "readonly", "size", "uuid", "tools_mount",
        "bind_dev", "bind_proc", "target_mode", "assessment", "replay", "manual_review", "sync", "unmount_proc",
        "unmount_dev", "unmount_tools", "final_sync", "cancelled", "poweroff_returned", "control_receipt", "verification_output",
        "scope_head", "scope_hash", "image_hash", "counter_scope", "counter_eligibility", "counter_directory", "counter_mount", "counter_sync", "counter_unmount",
        "watchdog_supervisor", "watchdog_progress", "watchdog_deadline"]
    static func failure(_ line: String) -> String? {
        let prefix = "IDECK_RECOVERY_FAILED:"
        guard line.hasPrefix(prefix) else { return nil }
        let reason = String(line.dropFirst(prefix.count))
        return failures.contains(reason) ? reason : nil
    }
    private(set) var assessment: Int?
    private(set) var replay: Int?
    private(set) var verification: Int?
    private(set) var scanClean = false
    private(set) var imageSHA256: String?
    private(set) var summaryEligible = false
    private(set) var summaryReconciled = false
    private(set) var done = false
    var phase: String {
        if done { return "awaiting_exit" }
        if imageSHA256 != nil { return "verified" }
        if verification != nil { return "checking_image" }
        if summaryEligible { return summaryReconciled ? "summary_reconciled" : "summary_reconciling" }
        return replay != nil ? "replayed" : "assessed"
    }
    var message: String {
        if done { return "Recovery checks finished. Waiting for Linux shutdown and host sync. Keep iDeck open." }
        if imageSHA256 != nil { return "Recovery image hash recorded. Finishing checks; keep iDeck open. The original remains preserved." }
        if scanClean { return "Recovery: hashing the checked work copy. This can take some time; keep iDeck open. The original remains preserved." }
        return "Recovery: checking the separate work copy (\(phase)). Keep iDeck open until completion. The original remains preserved."
    }
    mutating func observe(_ line: String) throws {
        guard !done else { throw LinuxGUIRecovery.Invalid.receipt }
        if line == "IDECK_RECOVERY_ASSESS:0" || line == "IDECK_RECOVERY_ASSESS:4" {
            guard assessment == nil else { throw LinuxGUIRecovery.Invalid.receipt }
            assessment = line.hasSuffix(":0") ? 0 : 4
        } else if line == "IDECK_RECOVERY_REPLAY:0" || line == "IDECK_RECOVERY_REPLAY:1" {
            guard assessment != nil, replay == nil else { throw LinuxGUIRecovery.Invalid.receipt }
            replay = line.hasSuffix(":0") ? 0 : 1
        } else if line == "IDECK_RECOVERY_VERIFY:0" {
            guard replay != nil, verification == nil, !summaryEligible || summaryReconciled else { throw LinuxGUIRecovery.Invalid.receipt }
            verification = 0
        } else if line == "IDECK_RECOVERY_SUMMARY_ELIGIBLE" {
            guard replay != nil, verification == nil, !summaryEligible else { throw LinuxGUIRecovery.Invalid.receipt }
            summaryEligible = true
        } else if line == "IDECK_RECOVERY_SUMMARY_RECONCILED" {
            guard summaryEligible, !summaryReconciled, verification == nil else { throw LinuxGUIRecovery.Invalid.receipt }
            summaryReconciled = true
        } else if line == "IDECK_RECOVERY_SCAN_CLEAN" {
            guard verification == 0, !scanClean else { throw LinuxGUIRecovery.Invalid.receipt }; scanClean = true
        } else if line.hasPrefix("IDECK_RECOVERY_IMAGE_SHA256:") {
            let value = String(line.dropFirst("IDECK_RECOVERY_IMAGE_SHA256:".count))
            guard scanClean, imageSHA256 == nil, LinuxGUIRecovery.digest(value) else { throw LinuxGUIRecovery.Invalid.receipt }
            imageSHA256 = value
        } else if line == "IDECK_RECOVERY_DONE" {
            guard verification == 0, scanClean, imageSHA256 != nil else { throw LinuxGUIRecovery.Invalid.receipt }; done = true
        } else { throw LinuxGUIRecovery.Invalid.manualReview }
    }
}

/// Monotonic, finite recovery deadlines, separate from graphical readiness.
/// Real trusted milestones may renew inactivity, never the absolute limit.
struct LinuxRecoveryWatchdog {
    enum Timeout: String, Equatable { case supervisor, progress, deadline }
    static let supervisorSeconds: TimeInterval = 60
    static let progressSeconds: TimeInterval = 90
    static let totalSeconds: TimeInterval = 180
    let started: TimeInterval
    private(set) var lastProgress: TimeInterval
    private(set) var supervisorReady = false
    init(started: TimeInterval) { self.started = started; self.lastProgress = started }
    mutating func advanced(at now: TimeInterval, supervisor: Bool = false) {
        lastProgress = max(lastProgress, now)
        supervisorReady = supervisorReady || supervisor
    }
    var nextDeadline: TimeInterval {
        min(started + Self.totalSeconds, supervisorReady ? lastProgress + Self.progressSeconds : started + Self.supervisorSeconds)
    }
    func timeout(at now: TimeInterval) -> Timeout? {
        if now >= started + Self.totalSeconds { return .deadline }
        if !supervisorReady, now >= started + Self.supervisorSeconds { return .supervisor }
        if supervisorReady, now >= lastProgress + Self.progressSeconds { return .progress }
        return nil
    }
}
