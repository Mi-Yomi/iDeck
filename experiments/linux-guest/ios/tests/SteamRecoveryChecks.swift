import Foundation
import Darwin

/// Sparse negative fixture only; no fsck, repaired header or positive replay claim.
func runSteamRecoveryChecks(directory: URL, header: [UInt8], specification: LinuxDesktopDisk.Specification) throws {
    let scope = LinuxGUIRecovery.Scope.steam
    precondition(scope.accepts(specification) && !LinuxGUIRecovery.Scope.gui.accepts(specification))
    precondition(scope.suffixSHA256 == LinuxSteamRecoveryGuest.sha256)
    precondition(scope.suffixSHA256 != LinuxGUIRecovery.Scope.gui.suffixSHA256)
    let eligible = LinuxDesktopDisk.RecoveryObservation(recoverBit: true, state: 1, lastOrphan: 0, errorCount: 0)
    precondition(scope.permits(eligible) && !scope.permits(nil))
    for bad in [LinuxDesktopDisk.RecoveryObservation(recoverBit: false, state: 1, lastOrphan: 0, errorCount: 0),
                .init(recoverBit: true, state: 0, lastOrphan: 0, errorCount: 0),
                .init(recoverBit: true, state: 1, lastOrphan: 1, errorCount: 0),
                .init(recoverBit: true, state: 1, lastOrphan: 0, errorCount: 1)] {
        precondition(!scope.permits(bad))
    }
    do {
        _ = try LinuxGUIRecovery.prepare(directory: directory, specification: specification, availableBytes: { _ in 0 })
        preconditionFailure("default GUI scope accepted Steam")
    } catch LinuxGUIRecovery.Invalid.metadata { }
    var observed: LinuxDesktopDisk.RecoveryObservation?
    do {
        _ = try LinuxGUIRecovery.prepare(directory: directory, specification: specification,
            availableBytes: { _ in 0 }, observe: { observed = $0 }, scope: .steam)
        preconditionFailure("Steam recovery accepted insufficient real-copy budget")
    } catch LinuxGUIRecovery.Invalid.space { }
    precondition(observed == eligible)
    var watchdog = LinuxRecoveryWatchdog(started: 0, scope: .steam)
    precondition(watchdog.timeout(at: 60) == .supervisor)
    watchdog.advanced(at: 1, supervisor: true)
    precondition(watchdog.timeout(at: 900) == nil && watchdog.timeout(at: 901) == .progress)
    watchdog.advanced(at: 1799)
    precondition(watchdog.timeout(at: 1800) == .deadline)
    let source = directory.appendingPathComponent("rootfs-v1.raw")
    let fd = Darwin.open(source.path, O_RDONLY | O_NOFOLLOW)
    precondition(fd >= 0); defer { Darwin.close(fd) }
    var current = [UInt8](repeating: 0, count: 1024)
    let read = current.withUnsafeMutableBytes { pread(fd, $0.baseAddress, $0.count, 1024) }
    precondition(read == 1024 && current == header)
    var state = stat(); precondition(fstat(fd, &state) == 0 && state.st_size == specification.sizeBytes)
    precondition(!FileManager.default.fileExists(atPath: directory.appendingPathComponent(".recovery-v1/current.json").path))
    do {
        _ = try LinuxDesktopDisk.openExisting(directory: directory, specification: specification)
        preconditionFailure("space refusal cleared ext4 guard")
    } catch LinuxDesktopDisk.Invalid.needsRecovery { }
    try runSteamRecoveryBindingChecks(directory: directory, specification: specification, state: state)
    let unchanged = current.withUnsafeMutableBytes { pread(fd, $0.baseAddress, $0.count, 1024) }
    precondition(unchanged == 1024 && current == header)
    precondition(!FileManager.default.fileExists(atPath: directory.appendingPathComponent(".recovery-v1/current.json").path))
    print("LINUX_STEAM_RECOVERY_SCOPE_PASS (scope isolation, RECOVER-only eligibility, low-space before hash/copies, original header/guard retained; replay NOT RUN)")
}

/// Executes the production protocol/receipt guards; deliberately no positive disk-repair claim.
private func runSteamRecoveryBindingChecks(directory: URL, specification: LinuxDesktopDisk.Specification, state: stat) throws {
    typealias Binding = LinuxGUIRecovery.SteamBinding
    let id = "11111111-1111-4111-8111-111111111111"
    let nonce = "22222222-2222-4222-8222-222222222222"
    let sourceHash = String(repeating: "a", count: 64)
    let repairedHash = String(repeating: "b", count: 64)
    let binding = Binding(generation: id, nonce: nonce, sourceSHA256: sourceHash)!
    precondition(Binding(generation: "bad", nonce: nonce, sourceSHA256: sourceHash) == nil)
    precondition(Binding(generation: id, nonce: nonce + " ", sourceSHA256: sourceHash) == nil)
    precondition(Binding(generation: id, nonce: nonce, sourceSHA256: String(repeating: "A", count: 64)) == nil)
    let events = [binding.marker, "IDECK_RECOVERY_SOURCE_SHA256:" + sourceHash,
        "IDECK_RECOVERY_ASSESS:4", "IDECK_RECOVERY_REPLAY:1", "IDECK_RECOVERY_VERIFY:0",
        "IDECK_RECOVERY_SCAN_CLEAN", "IDECK_RECOVERY_IMAGE_SHA256:" + repairedHash, "IDECK_RECOVERY_DONE"]
    func rejects(_ lines: [String]) throws {
        var progress = LinuxRecoveryProgress(expectedBinding: binding)
        do {
            for line in lines { try progress.observe(line) }
            preconditionFailure("Steam recovery accepted unbound/out-of-order control receipt")
        } catch LinuxGUIRecovery.Invalid.receipt { }
          catch LinuxGUIRecovery.Invalid.manualReview { }
    }
    var progress = LinuxRecoveryProgress(expectedBinding: binding)
    precondition(!progress.bindingReady && progress.phase == "checking_source")
    try progress.observe(events[0]); precondition(progress.bindingReady && progress.verifiedBinding == nil)
    for line in events.dropFirst() { try progress.observe(line) }
    precondition(progress.done && progress.verifiedBinding == binding && progress.imageSHA256 == repairedHash)
    try rejects([events[1]])
    try rejects([Binding(generation: nonce, nonce: id, sourceSHA256: sourceHash)!.marker])
    try rejects([Binding(generation: id, nonce: id, sourceSHA256: sourceHash)!.marker])
    try rejects([events[0], "IDECK_RECOVERY_SOURCE_SHA256:" + repairedHash])
    try rejects([events[0], events[0]])
    try rejects([events[0], events[2]])
    try rejects([events[0], events[1], events[1]])
    try rejects(Array(events.prefix(4)) + ["IDECK_RECOVERY_SUMMARY_ELIGIBLE"])
    try rejects(events + [events[7]])
    var gui = LinuxRecoveryProgress()
    precondition(gui.bindingReady)
    for line in events.dropFirst(2) { try gui.observe(line) }
    precondition(gui.done && gui.verifiedBinding == nil)

    var receipt = LinuxGUIRecovery.Receipt(id: id, phase: .verified,
        process: "33333333-3333-4333-8333-333333333333", sourceSHA256: sourceHash,
        sourceInode: UInt64(state.st_ino), sourceDevice: Int64(state.st_dev), sourceMode: UInt32(state.st_mode & 0o777),
        sourceUID: state.st_uid, sourceGID: state.st_gid, size: specification.sizeBytes, uuid: specification.uuid)
    receipt.schema = 2; receipt.scopeName = "steam"; receipt.runNonce = nonce
    receipt.verifiedRunNonce = nonce; receipt.verifiedSourceSHA256 = sourceHash
    receipt.assessment = 4; receipt.replay = 1; receipt.verification = 0; receipt.scanClean = true
    receipt.recoveredSHA256 = repairedHash; receipt.toolSeedSHA256 = sourceHash
    receipt.suffixSHA256 = LinuxSteamRecoveryGuest.sha256
    precondition(LinuxGUIRecovery.Scope.steam.accepts(receipt) && LinuxGUIRecovery.Scope.steam.resultBound(receipt))
    precondition(!LinuxGUIRecovery.Scope.gui.accepts(receipt))
    let root = directory.appendingPathComponent(".recovery-v1")
    let generation = root.appendingPathComponent(id)
    let current = root.appendingPathComponent("current.json")
    try FileManager.default.createDirectory(at: generation, withIntermediateDirectories: false)
    defer { try? FileManager.default.removeItem(at: current); try? FileManager.default.removeItem(at: generation) }
    // No backup/work exists: expected rejection MUST precede any full disk hash/copy.
    func rejectPromotion(_ value: LinuxGUIRecovery.Receipt, relaunch: Bool = false) throws {
        try JSONEncoder().encode(value).write(to: current)
        do {
            _ = try LinuxGUIRecovery.promotePending(directory: directory, specification: specification,
                toolSeedSHA256: sourceHash, scope: .steam)
            preconditionFailure("Steam activated a stale/mixed/failed receipt")
        } catch LinuxGUIRecovery.Invalid.receipt { precondition(!relaunch) }
          catch LinuxGUIRecovery.Invalid.relaunch { precondition(relaunch) }
    }
    var bad = receipt; bad.verifiedRunNonce = nil; try rejectPromotion(bad)
    bad = receipt; bad.verifiedRunNonce = id; try rejectPromotion(bad)
    bad = receipt; bad.verifiedSourceSHA256 = repairedHash; try rejectPromotion(bad)
    bad = receipt; bad.failure = "watchdog_deadline"; try rejectPromotion(bad)
    bad = receipt; bad.summaryReconciled = true; try rejectPromotion(bad)
    bad = receipt; bad.schema = 1; bad.scopeName = nil; bad.runNonce = nil; try rejectPromotion(bad)
    bad = receipt; bad.scopeName = "gui"; try rejectPromotion(bad)
    bad = receipt; bad.uuid = LinuxGUIProfile.uuid; try rejectPromotion(bad)
    bad = receipt; bad.size = LinuxGUIProfile.size; try rejectPromotion(bad)
    bad = receipt; bad.process = LinuxGUIRecovery.process; try rejectPromotion(bad, relaunch: true)
    try JSONEncoder().encode(receipt).write(to: current)
    let lockedSource = Darwin.open(directory.appendingPathComponent("rootfs-v1.raw").path, O_RDONLY | O_NOFOLLOW)
    precondition(lockedSource >= 0 && flock(lockedSource, LOCK_EX | LOCK_NB) == 0)
    do {
        _ = try LinuxGUIRecovery.promotePending(directory: directory, specification: specification,
            toolSeedSHA256: sourceHash, scope: .steam)
        preconditionFailure("Steam promotion ignored source ownership lock")
    } catch LinuxGUIRecovery.Invalid.busy { }
    precondition(Darwin.close(lockedSource) == 0)
    bad = receipt; bad.schema = 1; bad.scopeName = nil; bad.runNonce = nil
    bad.uuid = LinuxGUIProfile.uuid; bad.size = LinuxGUIProfile.size
    precondition(LinuxGUIRecovery.Scope.gui.accepts(bad))

    let report = LinuxProbeReport.render(report: ["mode": "steam-experimental", "recovery_phase": "checking_source",
        "recovery_generation": id, "recovery_run_nonce": nonce, "recovery_source_sha256": sourceHash,
        "recovery_binding_accepted": true, "recovery_source_verified": true])
    for text in ["| Recovery generation | " + id, "| Recovery run nonce | " + nonce,
                 "| Recovery source SHA-256 | " + sourceHash, "| Recovery source verified | PASS", "checking_source"] {
        precondition(report.contains(text))
    }
    let unsafe = "PRIVATE_NONCE_CANARY"
    let redacted = LinuxProbeReport.render(report: ["mode": "steam-experimental", "recovery_generation": unsafe,
        "recovery_run_nonce": unsafe, "recovery_source_sha256": unsafe])
    precondition(!redacted.contains(unsafe))
    print("LINUX_STEAM_RECOVERY_BINDING_PASS (production protocol, nonce/source replay rejection, stale/mixed/failed receipts and same-process promotion refused before disk IO, report redaction; positive repair NOT RUN)")
}
