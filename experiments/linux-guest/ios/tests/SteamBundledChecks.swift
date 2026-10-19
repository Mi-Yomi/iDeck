import Foundation
import CryptoKit
import Darwin

func runSteamBundledChecks(root: URL, entry: LinuxSteamOfflineCache.Entry, archive: Data) throws {
    let assets = root.appendingPathComponent("synthetic-bundle")
    try FileManager.default.createDirectory(at: assets, withIntermediateDirectories: true)
    let source = assets.appendingPathComponent("owner-steam-cache.tar")
    try archive.write(to: source)
    let sha = SHA256.hash(data: archive).map { String(format:"%02x",$0) }.joined()
    func assertBytes(_ file: URL, _ expected: Data) throws {
        let actual = try Data(contentsOf: file); precondition(actual == expected)
    }
    let userdata = root.appendingPathComponent("existing-userdata-sentinel")
    let original = Data("synthetic existing userdata, never a real user disk".utf8)
    try original.write(to: userdata)
    func prepare(_ target: URL, checkpoint: (() throws -> Void)? = nil) throws -> LinuxSteamOfflineCache.Handle {
        try LinuxSteamOfflineCache.prepareBundled(from: assets, into: target, entries: [entry],
            archiveSize: 10240, expectedSHA256: sha, checkpoint: checkpoint)
    }
    let target = root.appendingPathComponent("auto-cache")
    let first = try prepare(target); try first.validateIdentity()
    var before = stat(); precondition(lstat(first.url.path, &before) == 0)
    let repeatHandle = try prepare(target); try repeatHandle.validateIdentity()
    var after = stat(); precondition(lstat(repeatHandle.url.path, &after) == 0)
    precondition(before.st_ino == after.st_ino && before.st_dev == after.st_dev)
    try assertBytes(userdata, original)
    let exported = LinuxProbeReport.render(report: ["mode":"steam-experimental",
        "steam_bundled_cache_status":"blocked: digest"])
    precondition(exported.contains("Bundled package cache stage") && exported.contains("blocked: digest"))
    // Always check bundle pin, including when a prior published cache exists.
    var corrupt = archive; corrupt[512] ^= 1; try corrupt.write(to: source)
    do { _ = try prepare(target); preconditionFailure("corrupt bundled input accepted") }
    catch LinuxSteamOfflineCache.Invalid.digest { }
    try assertBytes(first.url, archive)
    try FileManager.default.removeItem(at: source)
    do { _ = try prepare(target); preconditionFailure("missing bundle accepted") }
    catch LinuxSteamOfflineCache.Invalid.io { }
    try archive.write(to: source)
    enum Interrupt: Error { case fixture }
    for checkpoint in [2, 3, 5] {
        var count = 0
        let partial = root.appendingPathComponent("auto-interrupted-\(checkpoint)")
        do {
            _ = try prepare(partial) { count += 1; if count == checkpoint { throw Interrupt.fixture } }
            preconditionFailure("cancel checkpoint skipped")
        } catch Interrupt.fixture { }
        let resumed = try prepare(partial); try resumed.validateIdentity()
        try assertBytes(resumed.url, archive)
    }
    let broken = root.appendingPathComponent("auto-corrupt-existing")
    let cached = try prepare(broken)
    try corrupt.write(to: cached.url)
    do { _ = try prepare(broken); preconditionFailure("corrupt published cache replaced") }
    catch LinuxSteamOfflineCache.Invalid.digest { }
    try assertBytes(cached.url, corrupt)
    try assertBytes(userdata, original)
    print("LINUX_STEAM_BUNDLED_CACHE_PASS (actual synthetic bundle import/reuse/pins/cancel/retry/no-replace/userdata sentinel preservation)")
}
