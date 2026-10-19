import Foundation
import CryptoKit
import Darwin

func runSteamOfflineChecks(root: URL) throws {
    let mib = LinuxSteamMemory.mib
    let unknownBudgets: [UInt64?] = [nil, 0]
    for absent in unknownBudgets {
        do { _ = try LinuxSteamMemory.plan(available: absent, mode: .auto); preconditionFailure("unknown auto ready") }
        catch LinuxSteamMemory.Failure.unavailable { }
    }
    let autoMinimum = UInt64(1536 + 2048) * mib
    do { _ = try LinuxSteamMemory.plan(available: autoMinimum - 1, mode: .auto); preconditionFailure("under minimum") }
    catch LinuxSteamMemory.Failure.insufficient { }
    let floor = try LinuxSteamMemory.plan(available: autoMinimum, mode: .auto)
    precondition(floor.guestMib == 1536 && floor.overhead == 1024 * mib && floor.reserve == 1024 * mib)
    let stepped = try LinuxSteamMemory.plan(available: UInt64(2048 + 2048 + 255) * mib, mode: .auto)
    precondition(stepped.guestMib == 2048)
    let cap = try LinuxSteamMemory.plan(available: UInt64.max, mode: .auto)
    precondition(cap.guestMib == 4096)
    precondition(LinuxSteamMemory.minimumBudget(.auto) == 3584 * mib)
    precondition(LinuxSteamMemory.minimumBudget(.fixed1536) == 2560 * mib)
    // Owner screenshot: Auto refuses a measured process budget, not a touch/JIT failure.
    let measured = 3000 * mib
    do { _ = try LinuxSteamMemory.plan(available: measured, mode: .auto); preconditionFailure("unsafe Auto fallback") }
    catch LinuxSteamMemory.Failure.insufficient { }
    let smaller = try LinuxSteamMemory.plan(available: measured, mode: .fixed1536)
    precondition(smaller.guestMib == 1536 && smaller.reserve == 1024 * mib)
    precondition(LinuxSteamMemory.explanation(available: measured, mode: .auto).contains("3000 MiB"))
    precondition(LinuxSteamMemory.explanation(available: measured, mode: .auto).contains("3584 MiB"))
    precondition(LinuxSteamMemory.explanation(available: nil, mode: .fixed1536).contains("не измерен"))
    do { try smaller.recheck(2559 * mib); preconditionFailure("stale smaller-mode budget") }
    catch LinuxSteamMemory.Failure.insufficient { }
    let manual = try LinuxSteamMemory.plan(available: UInt64(1536 + 1024) * mib, mode: .fixed1536)
    precondition(manual.guestMib == 1536 && manual.overhead == 0)
    let overhead = try LinuxSteamMemory.plan(available: UInt64(8192) * mib, mode: .auto, hostOverhead: 4096 * mib)
    precondition(overhead.guestMib == 3072)
    for _ in 0..<20 {
        do { try floor.recheck(autoMinimum - 1); preconditionFailure("stale budget authorized entry") }
        catch LinuxSteamMemory.Failure.insufficient { }
    }
    do { try floor.recheck(nil); preconditionFailure("unknown final budget") }
    catch LinuxSteamMemory.Failure.unavailable { }
    do { _ = try LinuxSteamMemory.plan(available: UInt64.max, mode: .auto, hostOverhead: UInt64.max); preconditionFailure("overflow accepted") }
    catch LinuxSteamMemory.Failure.overflow { }
    do { _ = try LinuxSteamMemory.plan(available: UInt64.max, mode: .auto, safetyReserve: UInt64.max); preconditionFailure("reserve overflow") }
    catch LinuxSteamMemory.Failure.overflow { }
    let exported = LinuxProbeReport.render(report: ["mode": "steam-experimental", "profile_memory_mib": 2048,
        "steam_memory_mode": "auto", "steam_memory_effective_mib": 2048,
        "steam_memory_overhead_bytes": 1024 * mib, "steam_memory_reserve_bytes": 1024 * mib,
        "steam_memory_final_recheck": "BLOCKED", "steam_offline_cache_attached": true])
    precondition(exported.contains("Steam RAM mode") && exported.contains("BLOCKED") && exported.contains("CONFIGURED READONLY / PINNED"))
    try runFreshMemoryHandoffChecks(root: root, plan: floor)
    print("LINUX_STEAM_AUTO_MEMORY_PASS (unknown/bounds/step/overhead/overflow/final deterioration; synthetic budgets)")

    let folder = root.appendingPathComponent("offline-cache-checks")
    try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
    let source = folder.appendingPathComponent("fixture.tar")
    let bytes = Data("fixture".utf8)
    let digest = SHA256.hash(data: bytes).map { String(format: "%02x", $0) }.joined()
    let entry = LinuxSteamOfflineCache.Entry(header: "Y2xpZW50L2ZpeHR1cmUuemlwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADAwMDA2NDQAMDAwMDAwMAAwMDAwMDAwADAwMDAwMDAwMDA3ADAwMDAwMDAwMDAwADAxMTQzMgAgMAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAB1c3RhcgAwMAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=", size: 7, sha256: digest)
    var archive = Data(base64Encoded: entry.header)! + bytes
    archive.append(Data(repeating: 0, count: 10240 - archive.count))
    try archive.write(to: source)
    func verify(_ file: URL) throws {
        let fd = Darwin.open(file.path, O_RDONLY | O_NOFOLLOW)
        precondition(fd >= 0); defer { Darwin.close(fd) }
        try LinuxSteamOfflineCache.verify(fd, entries: [entry], archiveSize: 10240)
    }
    try verify(source)
    for offset in [0, 156, 345, 512, 519, 10239] {
        var corrupted = archive; corrupted[offset] ^= 1
        try corrupted.write(to: source)
        do { try verify(source); preconditionFailure("corrupt header/data/padding accepted") } catch { }
    }
    try (archive + Data([0])).write(to: source)
    do { try verify(source); preconditionFailure("extra bytes accepted") } catch { }
    try archive.write(to: source)
    let target = folder.appendingPathComponent("import")
    enum Interrupted: Error { case fixture }
    var checkpoints = 0
    do {
        try LinuxSteamOfflineCache.importArchive(source, into: target, entries: [entry], archiveSize: 10240) {
            checkpoints += 1
            if checkpoints == 2 { throw Interrupted.fixture }
        }
        preconditionFailure("interruption ignored")
    } catch Interrupted.fixture { }
    precondition(!FileManager.default.fileExists(atPath: target.appendingPathComponent("packages.tar").path))
    try LinuxSteamOfflineCache.importArchive(source, into: target, entries: [entry], archiveSize: 10240)
    let published = try Data(contentsOf: target.appendingPathComponent("packages.tar"))
    precondition(published == archive)
    do {
        try LinuxSteamOfflineCache.importArchive(source, into: target, entries: [entry], archiveSize: 10240)
        preconditionFailure("existing published archive replaced")
    } catch LinuxSteamOfflineCache.Invalid.exists { }
    let publishedInterruption = folder.appendingPathComponent("published-interruption")
    checkpoints = 0
    do {
        try LinuxSteamOfflineCache.importArchive(source, into: publishedInterruption, entries: [entry], archiveSize: 10240) {
            checkpoints += 1
            if checkpoints == 3 { throw Interrupted.fixture }
        }
        preconditionFailure("post-publication interruption ignored")
    } catch Interrupted.fixture { }
    try LinuxSteamOfflineCache.reconcilePublication(in: publishedInterruption, entries: [entry], archiveSize: 10240)
    precondition(!FileManager.default.fileExists(atPath: publishedInterruption.appendingPathComponent(".import.partial").path))
    let recovered = try Data(contentsOf: publishedInterruption.appendingPathComponent("packages.tar"))
    precondition(recovered == archive)
    let alias = folder.appendingPathComponent("alias.tar")
    try FileManager.default.createSymbolicLink(at: alias, withDestinationURL: source)
    do {
        try LinuxSteamOfflineCache.importArchive(alias, into: folder.appendingPathComponent("alias-import"), entries: [entry], archiveSize: 10240)
        preconditionFailure("symlink source accepted")
    } catch { }
    let blocked = folder.appendingPathComponent("contended")
    try FileManager.default.createDirectory(at: blocked, withIntermediateDirectories: true)
    let fd = Darwin.open(blocked.appendingPathComponent(".import.partial").path, O_RDWR | O_CREAT, 0o600)
    precondition(fd >= 0 && flock(fd, LOCK_EX | LOCK_NB) == 0)
    defer { Darwin.close(fd) }
    do {
        try LinuxSteamOfflineCache.importArchive(source, into: blocked, entries: [entry], archiveSize: 10240)
        preconditionFailure("competing importer accepted")
    } catch LinuxSteamOfflineCache.Invalid.busy { }
    try runSteamBundledChecks(root: folder, entry: entry, archive: archive)
    print("LINUX_STEAM_OFFLINE_CACHE_PASS (actual synthetic tar IO/digest/headers/links/corruption/interruption/no-replace/owner lock)")
}


/// Actual production gate + journal fsync barrier; no QEMU or device execution.
private func runFreshMemoryHandoffChecks(root: URL, plan: LinuxSteamMemory.Plan) throws {
    final class Budget {
        private let lock = NSLock()
        private var bytes: UInt64?
        init(_ value: UInt64) { bytes = value }
        func set(_ value: UInt64?) { lock.lock(); bytes = value; lock.unlock() }
        func get() -> UInt64? { lock.lock(); defer { lock.unlock() }; return bytes }
    }
    let budget = Budget(plan.required)
    let inIO = DispatchSemaphore(value: 0), resumeIO = DispatchSemaphore(value: 0)
    var armed = false, syncFailed = false
    let documents = root.appendingPathComponent("fresh-handoff-journal")
    try FileManager.default.createDirectory(at: documents, withIntermediateDirectories: true)
    let store = try LinuxTerminalDiagnostics(documents: documents, synchronize: { fd in
        if syncFailed { return -1 }
        if armed {
            inIO.signal()
            guard resumeIO.wait(timeout: .now() + 5) == .success else { return -1 }
        }
        return fsync(fd)
    })
    let journal = try store.begin(source: String(repeating: "a", count: 40), build: "handoff-fixture")
    // SteamProfileChecks leaves this sparse synthetic ext4 header dirty. Keep
    // its real exclusive fd lock throughout refusal; never rewrite its bytes.
    let raw = root.appendingPathComponent("steam-data/rootfs-v1.raw")
    let held = Darwin.open(raw.path, O_RDWR | O_NOFOLLOW)
    precondition(held >= 0 && flock(held, LOCK_EX | LOCK_NB) == 0)
    defer { Darwin.close(held) }
    var before = Data(count: 1024)
    let beforeCount = before.withUnsafeMutableBytes { pread(held, $0.baseAddress!, $0.count, 1024) }
    precondition(beforeCount == 1024 && before[0x60] & 4 != 0)
    let preparation = LinuxStartupPreparation()
    let changer = Thread {
        precondition(inIO.wait(timeout: .now() + 5) == .success)
        budget.set(plan.required - 1)
        resumeIO.signal()
    }
    armed = true; changer.start()
    var samples = 0
    do {
        _ = try LinuxSteamMemory.enterAfterIO(plan: plan, preparation: preparation,
            prepare: { try journal.record(.qemuInitBegin) },
            sample: { samples += 1; return budget.get() })
        preconditionFailure("budget during blocked fsync was not resampled")
    } catch LinuxSteamMemory.Failure.insufficient { }
    armed = false
    precondition(samples == 1 && preparation.snapshot.state == .finished)
    precondition(!preparation.enterNative(), "a refused preparation cannot start another VM")
    let contender = Darwin.open(raw.path, O_RDWR | O_NOFOLLOW)
    precondition(contender >= 0)
    precondition(flock(contender, LOCK_EX | LOCK_NB) != 0, "memory refusal released the disk owner")
    Darwin.close(contender)
    var after = Data(count: 1024)
    let afterCount = after.withUnsafeMutableBytes { pread(held, $0.baseAddress!, $0.count, 1024) }
    precondition(afterCount == 1024 && after == before, "memory refusal cleared dirty ext4 metadata")
    let snapshot = try store.snapshot(id: journal.id)
    precondition(snapshot.records.contains { $0.stage == .qemuInitBegin }, "mandatory journal was not durable before sampling")
    // Even after budget recovers, the same one-use preparation cannot re-enter.
    budget.set(plan.required)
    do {
        _ = try LinuxSteamMemory.enterAfterIO(plan: plan, preparation: preparation,
            prepare: {}, sample: { budget.get() })
        preconditionFailure("refused preparation was reopened")
    } catch LinuxStartupPreparation.Cancelled.beforeNativeEntry { }
    // Journal failure must prevent the sample/native boundary altogether.
    syncFailed = true
    let failed = LinuxStartupPreparation()
    do {
        _ = try LinuxSteamMemory.enterAfterIO(plan: plan, preparation: failed,
            prepare: { try journal.record(.qemuInitBegin) },
            sample: { preconditionFailure("sample ran after failed fsync") })
        preconditionFailure("failed mandatory journal allowed native entry")
    } catch LinuxTerminalDiagnostics.Problem.synchronize { }
    precondition(failed.snapshot.state == .finished && !failed.enterNative())
    // The successful route is still exactly one atomic commit.
    let success = LinuxStartupPreparation()
    let sampled = try LinuxSteamMemory.enterAfterIO(plan: plan, preparation: success, prepare: {}, sample: { budget.get() })
    precondition(sampled == plan.required && success.snapshot.state == .entered && !success.enterNative())
    let nonSteam = LinuxStartupPreparation()
    let noBudget = try LinuxSteamMemory.enterAfterIO(plan: nil, preparation: nonSteam, prepare: {},
        sample: { preconditionFailure("non-Steam route sampled Steam budget") })
    precondition(noBudget == nil && nonSteam.snapshot.state == .entered)
    print("LINUX_STEAM_FRESH_HANDOFF_PASS (blocked journal IO, fresh budget, durable journal, dirty bytes/lock retained, refusal one-use, sync failure)")
}
