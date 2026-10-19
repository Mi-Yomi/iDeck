import Foundation
import CryptoKit
import Darwin
import zlib

func runSteamProfileChecks(root: URL) throws {
    let assets = root.appendingPathComponent("steam-assets", isDirectory: true)
    let probe = root.appendingPathComponent("steam-probe", isDirectory: true)
    let data = root.appendingPathComponent("steam-data", isDirectory: true)
    for path in [assets, probe, data] { try FileManager.default.createDirectory(at: path, withIntermediateDirectories: true) }
    let bytes = Data("synthetic checked asset; no client".utf8)
    let hash = SHA256.hash(data: bytes).map { String(format: "%02x", $0) }.joined()
    let asset: (String) -> [String: Any] = { ["file": $0, "size": bytes.count, "sha256": hash] }
    var valid: [String: Any] = ["schema": 1, "mode": "steam-experimental", "control_port": "org.ideck.control",
        "kernel": asset("vmlinuz-virt"), "initramfs": asset("initramfs-steam.gz"), "rootfs": asset("steam-rootfs-v1.raw.gz"),
        "seed_sha256": hash, "image": ["size_bytes": LinuxSteamProfile.size, "uuid": LinuxSteamProfile.uuid,
        "block_size": 4096, "features": ["compat": 44, "incompat": 194, "ro_compat": 1091]]]
    let profileFile = assets.appendingPathComponent("steam-profile.json")
    try JSONSerialization.data(withJSONObject: valid).write(to: profileFile)
    let profile = try LinuxSteamProfile.load(from: assets)
    try profile.validate()
    for name in ["vmlinuz-virt", "initramfs-steam.gz"] { try bytes.write(to: assets.appendingPathComponent(name)) }
    for name in ["vmlinuz-virt", "initramfs-ideck.gz"] { try bytes.write(to: probe.appendingPathComponent(name)) }
    // Execute the actual bounded gzip decoder with small real IO fixtures.
    let gzipFile = assets.appendingPathComponent("decoder-fixture.gz")
    guard let zipped = gzopen(gzipFile.path, "wb") else { preconditionFailure("gzip fixture open") }
    precondition(Int(bytes.withUnsafeBytes { gzwrite(zipped, $0.baseAddress, UInt32($0.count)) }) == bytes.count)
    precondition(gzclose(zipped) == Z_OK)
    let source = Darwin.open(gzipFile.path, O_RDONLY)
    let outputFile = assets.appendingPathComponent("decoder-output")
    let output = Darwin.open(outputFile.path, O_RDWR | O_CREAT | O_EXCL, 0o600)
    precondition(source >= 0 && output >= 0)
    defer { Darwin.close(source); Darwin.close(output) }
    try LinuxSteamProfile.copyGzip(source, to: output, size: Int64(bytes.count), digest: hash)
    let decoded = try Data(contentsOf: outputFile)
    precondition(decoded == bytes)
    do {
        try LinuxSteamProfile.copyGzip(source, to: output, size: Int64(bytes.count - 1), digest: hash)
        preconditionFailure("unbounded gzip accepted")
    } catch LinuxDesktopProfile.Invalid.assetSize { }
    do {
        try LinuxSteamProfile.copyGzip(source, to: output, size: Int64(bytes.count), digest: String(repeating: "a", count: 64))
        preconditionFailure("wrong expanded hash accepted")
    } catch LinuxDesktopProfile.Invalid.assetDigest { }
    let original: [String: Any] = ["schema": 1, "width": 800, "height": 600, "cpu": "cortex-a72",
        "memory_mib": 1024, "vcpus": 4, "tcg_cache_mib": 256,
        "kernel": asset("vmlinuz-virt"), "initramfs": asset("initramfs-ideck.gz")]
    try JSONSerialization.data(withJSONObject: original).write(to: probe.appendingPathComponent("profile.json"))
    // Synthetic sparse IO fixture only; never a real seed or physical-space claim.
    let golden = try JSONSerialization.jsonObject(with: Data(contentsOf: URL(fileURLWithPath:
        "experiments/linux-guest/ios/tests/fixtures/desktop-ext4-superblock.json"))) as! [String: Any]
    let hex = golden["header_hex"] as! String
    var header = stride(from: 0, to: hex.count, by: 2).map { index -> UInt8 in
        let a = hex.index(hex.startIndex, offsetBy: index)
        return UInt8(hex[a..<hex.index(a, offsetBy: 2)], radix: 16)!
    }
    func u32(_ offset: Int, _ value: UInt32) { for n in 0..<4 { header[offset + n] = UInt8(truncatingIfNeeded: value >> (8 * n)) } }
    let uuid = LinuxSteamProfile.uuid.replacingOccurrences(of: "-", with: "")
    for n in 0..<16 {
        let a = uuid.index(uuid.startIndex, offsetBy: 2 * n)
        header[0x68 + n] = UInt8(uuid[a..<uuid.index(a, offsetBy: 2)], radix: 16)!
    }
    let blocks = UInt32(LinuxSteamProfile.size / 4096)
    u32(4, blocks)
    let inodes = UInt32(header[0x28]) | UInt32(header[0x29]) << 8 | UInt32(header[0x2a]) << 16 | UInt32(header[0x2b]) << 24
    u32(0, ((blocks + 32767) / 32768) * inodes)
    u32(1020, LinuxDesktopDisk.crc32c(header[0..<1020]))
    try LinuxDesktopDisk.validateHeader(header, specification: profile.image)
    let raw = data.appendingPathComponent("rootfs-v1.raw")
    let fd = Darwin.open(raw.path, O_RDWR | O_CREAT | O_EXCL, 0o600)
    precondition(fd >= 0)
    defer { Darwin.close(fd) }
    precondition(ftruncate(fd, off_t(LinuxSteamProfile.size)) == 0)
    precondition(pwrite(fd, header, header.count, 1024) == header.count)
    let disk = try profile.openExisting(in: data)
    defer { disk.closeUnused() }
    do {
        _ = try profile.arguments(probeAssets: probe, assets: assets, session: root.appendingPathComponent("steam-denied"),
            disk: disk, serialFD: 10, controlFD: 11, networkConsent: false)
        preconditionFailure("network without consent")
    } catch LinuxSteamProfile.Blocker.networkConsent { }
    let args = try profile.arguments(probeAssets: probe, assets: assets, session: root.appendingPathComponent("steam-argv"),
        disk: disk, serialFD: 10, controlFD: 11, networkConsent: true)
    precondition(args[args.firstIndex(of: "-cpu")! + 1] == "cortex-a76")
    precondition(args[args.firstIndex(of: "-m")! + 1] == "1536")
    precondition(!args.contains("-nic") && args.contains("virtio-net-device,netdev=steamnet"))
    precondition(!args.joined().contains("hostfwd") && !args.joined().contains("steam_disk_grow"))
    precondition(args.contains("socket,id=linuxserial,fd=10"))
    // One synthetic canonical member tests the actual optional argv branch.
    let cacheFile = root.appendingPathComponent("cache-identity-fixture.tar")
    let cacheBody = Data("fixture".utf8)
    let cacheDigest = SHA256.hash(data: cacheBody).map { String(format: "%02x", $0) }.joined()
    let cacheEntry = LinuxSteamOfflineCache.Entry(header: "Y2xpZW50L2ZpeHR1cmUuemlwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADAwMDA2NDQAMDAwMDAwMAAwMDAwMDAwADAwMDAwMDAwMDA3ADAwMDAwMDAwMDAwADAxMTQzMgAgMAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAB1c3RhcgAwMAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=", size: 7, sha256: cacheDigest)
    var cacheArchive = Data(base64Encoded: cacheEntry.header)!
    cacheArchive.append(cacheBody)
    cacheArchive.append(Data(repeating: 0, count: 10240 - cacheArchive.count))
    try cacheArchive.write(to: cacheFile)
    try FileManager.default.setAttributes([.posixPermissions: 0o600], ofItemAtPath: cacheFile.path)
    let cacheHandle = try LinuxSteamOfflineCache.Handle(cacheFile, entries: [cacheEntry], archiveSize: 10240)
    let cacheArgs = try profile.arguments(probeAssets: probe, assets: assets, session: root.appendingPathComponent("steam-cache-argv"),
        disk: disk, serialFD: 10, controlFD: 11, networkConsent: true, offlineCache: cacheHandle)
    precondition(LinuxSteamCacheContract.deviceSerial == "ideck-steam-cache-v1")
    precondition(LinuxSteamCacheContract.deviceSerial.utf8.count <= 20)
    precondition(cacheArgs.contains("virtio-blk-device,drive=steamcache,serial=\(LinuxSteamCacheContract.deviceSerial)"))
    precondition(cacheArgs.contains("if=none,id=steamcache,format=raw,readonly=on,file.locking=off,file=\(cacheFile.path)"))
    precondition(cacheArgs.contains("virtio-blk-device,drive=desktop"))
    let ordinary = LinuxDesktopDisk.Specification(sizeBytes: LinuxSteamProfile.size, uuid: LinuxGUIProfile.uuid,
        blockSize: 4096, features: .supported)
    do { try ordinary.validate(); preconditionFailure("global disk limit raised") }
    catch LinuxDesktopDisk.Invalid.specification { }
    // Force-quit-shaped metadata on an existing Steam disk must be observable
    // and refused on every reopen, never routed to the GUI-only recovery engine.
    disk.closeUnused()
    u32(0x60, 198)
    u32(1020, LinuxDesktopDisk.crc32c(header[0..<1020]))
    precondition(pwrite(fd, header, header.count, 1024) == header.count)
    for _ in 0..<2 {
        var observed: LinuxDesktopDisk.RecoveryObservation?
        do {
            _ = try profile.openExisting(in: data, observe: { observed = $0 })
            preconditionFailure("dirty Steam disk mounted or recreated")
        } catch LinuxDesktopDisk.Invalid.needsRecovery { }
        precondition(observed?.recoverBit == true)
    }
    do {
        _ = try LinuxGUIRecovery.prepare(directory: data, specification: profile.image)
        preconditionFailure("Steam disk entered GUI recovery")
    } catch LinuxGUIRecovery.Invalid.metadata { }
    precondition(!FileManager.default.fileExists(atPath: data.appendingPathComponent(".recovery-v1").path))
    var preserved = [UInt8](repeating: 0, count: 1024)
    let read = preserved.withUnsafeMutableBytes { pread(fd, $0.baseAddress!, $0.count, 1024) }
    precondition(read == preserved.count)
    precondition(preserved == header, "dirty Steam metadata must remain byte-for-byte intact")
    // Preview inspects only the bundle manifest. Even this existing dirty disk
    // is left alone: its ownership/recovery check belongs to the real Start path.
    let manifestBytes = try Data(contentsOf: profileFile)
    let budget = UInt64(LinuxSteamProfile.memoryMib) * 1024 * 1024 + LinuxSteamProfile.hostReserve
    // Exercise the actual signed SDK boundary, not an inferred UInt64 fixture.
    let unknownMeasurements: [Int] = [Int.min, -1, 0]
    for signedMeasurement in unknownMeasurements {
        let converted: UInt64? = LinuxSteamProfile.availableMemoryBytes(signedMeasurement)
        precondition(converted == nil)
    }
    let positiveMeasurements: [Int] = [1, Int(budget) - 1, Int(budget), Int(budget) + 1, Int.max]
    for signedMeasurement in positiveMeasurements {
        let converted: UInt64? = LinuxSteamProfile.availableMemoryBytes(signedMeasurement)
        precondition(converted == UInt64(exactly: signedMeasurement))
    }
    func readiness(_ memory: UInt64?, jit: Bool? = nil, consent: Bool = true) -> LinuxSteamProfile.Readiness {
        LinuxSteamProfile.readiness(assets: assets, jitVerified: jit, networkConsent: consent, availableMemory: memory)
    }
    precondition(readiness(LinuxSteamProfile.availableMemoryBytes(Int.min)).memory == .unknown)
    precondition(!readiness(LinuxSteamProfile.availableMemoryBytes(Int(budget) - 1)).canCheckAndStart)
    precondition(readiness(LinuxSteamProfile.availableMemoryBytes(Int(budget))).canCheckAndStart)
    precondition(readiness(nil).memory == .unknown && !readiness(nil).canCheckAndStart)
    precondition(readiness(0).memory == .unknown)
    precondition(!readiness(budget - 1).canCheckAndStart)
    precondition(readiness(budget).memory == .passed)
    precondition(readiness(budget + 1).canCheckAndStart)
    precondition(readiness(budget).jit == .unknown)
    precondition(readiness(budget, jit: false).jit != .passed)
    precondition(readiness(budget, jit: true).jit == .passed)
    precondition(!readiness(budget, consent: false).canCheckAndStart)
    let processBudget = UInt64(3000) * LinuxSteamMemory.mib
    let autoRefusal = LinuxSteamProfile.readiness(assets: assets, jitVerified: true, networkConsent: true,
        availableMemory: processBudget, memoryMode: .auto)
    precondition(autoRefusal.manifest == .passed && autoRefusal.jit == .passed && autoRefusal.network == .passed)
    precondition(autoRefusal.memory == .blocked("Недостаточно бюджета процесса с резервом; Auto не использует всю физическую RAM"))
    precondition(!autoRefusal.canCheckAndStart && autoRefusal.memoryExplanation.contains("3000 MiB"))
    let fixedReady = LinuxSteamProfile.readiness(assets: assets, jitVerified: true, networkConsent: true,
        availableMemory: processBudget, memoryMode: .fixed1536)
    precondition(fixedReady.canCheckAndStart && fixedReady.selectedMemoryMib == 1536)
    let freshRefusal = LinuxSteamProfile.readiness(assets: assets, jitVerified: true, networkConsent: true,
        availableMemory: 2559 * LinuxSteamMemory.mib, memoryMode: .fixed1536)
    precondition(!freshRefusal.canCheckAndStart, "stale readiness cannot authorize fixed1536")
    let before = try FileManager.default.contentsOfDirectory(atPath: data.path)
    for _ in 0..<20 { precondition(readiness(budget).canCheckAndStart) }
    let after = try FileManager.default.contentsOfDirectory(atPath: data.path)
    precondition(after == before)
    preserved.withUnsafeMutableBytes { precondition(pread(fd, $0.baseAddress!, $0.count, 1024) == $0.count) }
    precondition(preserved == header)
    try Data("{ malformed".utf8).write(to: profileFile)
    precondition(!readiness(budget).canCheckAndStart, "fresh Start check must reject a changed manifest")
    try FileManager.default.removeItem(at: profileFile)
    precondition(!readiness(budget).canCheckAndStart)
    try manifestBytes.write(to: profileFile)
    precondition(readiness(budget).canCheckAndStart)
    precondition(!readiness(budget - 1).canCheckAndStart, "preview pass cannot authorize a later low-memory Start")
    print("LINUX_STEAM_READINESS_PASS (bounded manifest read, memory boundaries, unknowns, repeated preview, existing disk preserved)")
    valid["mode"] = "desktop"
    try JSONSerialization.data(withJSONObject: valid).write(to: profileFile)
    do { _ = try LinuxSteamProfile.load(from: assets); preconditionFailure("wrong Steam contract accepted") } catch { }
    print("LINUX_STEAM_PROFILE_PASS")
}
