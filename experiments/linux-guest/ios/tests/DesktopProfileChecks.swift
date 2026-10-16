import Foundation
import CryptoKit

/// Apple CryptoKit/profile guard checks; fixture contents are synthetic except
/// for the captured real-mke2fs superblock. No QEMU or legacy userdata access.
func runDesktopProfileChecks(fixture: URL) throws {
    let golden = try DesktopGolden.load(fixture)
    let manager = FileManager.default
    let root = try LinuxDesktopDisk.trustedDirectory(manager.temporaryDirectory)
        .appendingPathComponent("ideck-desktop-profile-" + UUID().uuidString)
    let assets = root.appendingPathComponent("assets")
    try manager.createDirectory(at: assets, withIntermediateDirectories: true)
    defer { try? manager.removeItem(at: root) }
    let seed = assets.appendingPathComponent("rootfs-v1.raw")
    precondition(manager.createFile(atPath: seed.path, contents: nil))
    let file = try FileHandle(forWritingTo: seed)
    try file.truncate(atOffset: UInt64(golden.sizeBytes))
    try file.seek(toOffset: 1024); try file.write(contentsOf: Data(golden.header)); try file.close()
    func digest() throws -> String {
        let reader = try FileHandle(forReadingFrom: seed)
        defer { try? reader.close() }
        var hash = SHA256()
        while let bytes = try reader.read(upToCount: 1024 * 1024), !bytes.isEmpty { hash.update(data: bytes) }
        return hash.finalize().map { String(format: "%02x", $0) }.joined()
    }
    var description: [String: Any] = [
        "schema": 1, "mode": "desktop-rootfs", "filesystem": "ext4",
        "rootfs": ["file": "rootfs-v1.raw", "size": golden.sizeBytes, "sha256": try digest()],
        "image": ["size_bytes": golden.sizeBytes, "uuid": golden.uuid, "block_size": 4096,
                  "features": ["compat": 44, "incompat": 194, "ro_compat": 1091]]
    ]
    let profileURL = assets.appendingPathComponent("desktop-rootfs-profile.json")
    func load() throws -> LinuxDesktopProfile {
        try JSONSerialization.data(withJSONObject: description).write(to: profileURL)
        return try LinuxDesktopProfile.load(from: assets)
    }
    let profile = try load()
    let directory = root.appendingPathComponent("persistent")
    let disk = try profile.provision(in: directory, assets: assets)
    try disk.validateOwnership(); disk.closeUnused()
    let changed = try FileHandle(forWritingTo: directory.appendingPathComponent("rootfs-v1.raw"))
    try changed.seek(toOffset: 2 * 1024 * 1024); try changed.write(contentsOf: Data([0x6b])); try changed.close()
    let reopened = try profile.openExisting(in: directory)
    reopened.closeUnused() // changed body accepted, original seed hash is not a reopen checksum
    do {
        _ = try profile.provision(in: directory, assets: assets)
        preconditionFailure("existing desktop disk was replaced")
    } catch LinuxDesktopDisk.Invalid.alreadyExists { }
    let seedWriter = try FileHandle(forWritingTo: seed)
    try seedWriter.seek(toOffset: 2 * 1024 * 1024)
    try seedWriter.write(contentsOf: Data([0x70])); try seedWriter.close()
    let failed = root.appendingPathComponent("corrupt-seed")
    do {
        _ = try profile.provision(in: failed, assets: assets)
        preconditionFailure("same-size corrupt rootfs seed accepted")
    } catch LinuxDesktopProfile.Invalid.assetDigest { }
    let contents = try manager.contentsOfDirectory(atPath: failed.path)
    precondition(contents.isEmpty, "failed digest published partial disk")
    let held = root.appendingPathComponent("held-seed")
    try manager.moveItem(at: seed, to: held)
    try manager.createSymbolicLink(at: seed, withDestinationURL: held)
    do {
        _ = try profile.provision(in: root.appendingPathComponent("linked-seed"), assets: assets)
        preconditionFailure("symlink seed accepted")
    } catch LinuxDesktopProfile.Invalid.assetRead { }
    description["rootfs"] = ["file": "../rootfs-v1.raw", "size": golden.sizeBytes, "sha256": String(repeating: "0", count: 64)]
    do { _ = try load(); preconditionFailure("traversal asset descriptor accepted") }
    catch LinuxDesktopProfile.Invalid.configuration { }
    print("LINUX_DESKTOP_PROFILE_CHECKS_PASS (actual CryptoKit/IO guards; no guest boot)")
}
