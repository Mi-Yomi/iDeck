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
    print("LINUX_STEAM_OFFLINE_CACHE_PASS (actual synthetic tar IO/digest/headers/links/corruption/interruption/no-replace/owner lock)")
}
