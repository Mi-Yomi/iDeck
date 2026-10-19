import Foundation
import CryptoKit
import Darwin
import zlib

/// Steam-only contract. No accepted GUI/Debian disk or CPU/network policy is changed.
struct LinuxSteamProfile: Decodable {
    typealias Invalid = LinuxDesktopProfile.Invalid
    typealias Asset = LinuxDesktopProfile.Asset
    static let uuid = "c6a66b17-1b3e-4fe9-a07b-70c185fb2718"
    static let size: Int64 = 12 * 1024 * 1024 * 1024
    enum Blocker: Error { case payloadMissing, networkConsent, memoryBudget }
    static let memoryMib = 1536
    static let hostReserve: UInt64 = 1024 * 1024 * 1024
    let schema: Int
    let mode: String
    let controlPort: String
    let kernel: Asset
    let initramfs: Asset
    let rootfs: Asset
    let seedSha256: String
    let image: LinuxDesktopDisk.Specification

    enum Check: Equatable {
        case passed, unknown, blocked(String)
        var text: String {
            switch self {
            case .passed: return "Проверено"
            case .unknown: return "Не проверено / нет измерения"
            case .blocked(let reason): return reason
            }
        }
    }
    /// A read-only snapshot, not authorization to enter native code. JIT's cached
    /// observation is informational; Start must perform its real execution check.
    struct Readiness: Equatable {
        let manifest: Check
        let jit: Check
        let network: Check
        let memory: Check
        let selectedMemoryMib: Int?
        let availableMemory: UInt64?
        let memoryMode: LinuxSteamMemory.Mode
        var memoryExplanation: String { LinuxSteamMemory.explanation(available: availableMemory, mode: memoryMode) }
        var canCheckAndStart: Bool { manifest == .passed && network == .passed && memory == .passed }
        var summary: String {
            "Manifest: \(manifest.text) · JIT: \(jit.text) · Сеть (согласие): \(network.text) · Память: \(memory.text)"
        }
    }
    /// Apple's process-memory API returns a signed Int. Nonpositive readings
    /// mean unknown; use a failable conversion so no reading can trap or wrap.
    static func availableMemoryBytes(_ measurement: Int) -> UInt64? {
        guard measurement > 0 else { return nil }
        return UInt64(exactly: measurement)
    }
    static func readiness(assets: URL, jitVerified: Bool?, networkConsent: Bool,
                          availableMemory: UInt64?, memoryMode: LinuxSteamMemory.Mode = .fixed1536) -> Readiness {
        let manifest: Check
        do { _ = try load(from: assets); manifest = .passed }
        catch Blocker.payloadMissing { manifest = .blocked("Manifest отсутствует в IPA") }
        catch { manifest = .blocked("Manifest не прошёл проверку формата/контракта") }
        let memory: Check
        let plan = try? LinuxSteamMemory.plan(available: availableMemory, mode: memoryMode)
        if availableMemory == nil || availableMemory == 0 { memory = .unknown }
        else { memory = plan == nil ? .blocked("Недостаточно бюджета процесса с резервом; Auto не использует всю физическую RAM") : .passed }
        return Readiness(manifest: manifest,
            jit: jitVerified.map { $0 ? .passed : .blocked("Последняя проверка JIT не пройдена") } ?? .unknown,
            network: networkConsent ? .passed : .blocked("Требуется согласие на сеть"), memory: memory, selectedMemoryMib: plan?.guestMib,
            availableMemory: availableMemory, memoryMode: memoryMode)
    }

    func validate() throws {
        guard schema == 1, mode == "steam-experimental", controlPort == "org.ideck.control",
              kernel.file == "vmlinuz-virt", initramfs.file == "initramfs-steam.gz",
              rootfs.file == "steam-rootfs-v1.raw.gz", image.uuid == Self.uuid,
              image.sizeBytes == Self.size, rootfs.size > 0, rootfs.size <= 2 * 1024 * 1024 * 1024,
              seedSha256.range(of: "^[0-9a-f]{64}$", options: .regularExpression) != nil else { throw Invalid.configuration }
        try image.validate()
        for asset in [kernel, initramfs, rootfs] {
            guard asset.size > 0,
                  asset.sha256.range(of: "^[0-9a-f]{64}$", options: .regularExpression) != nil else { throw Invalid.configuration }
        }
        guard kernel.size <= 32 * 1024 * 1024, initramfs.size <= 128 * 1024 * 1024 else { throw Invalid.configuration }
    }

    static func load(from assets: URL) throws -> Self {
        guard FileManager.default.fileExists(atPath: assets.appendingPathComponent("steam-profile.json").path) else { throw Blocker.payloadMissing }
        let root = try LinuxDesktopDisk.trustedDirectory(assets)
        let fd = Darwin.open(root.appendingPathComponent("steam-profile.json").path,
                             O_RDONLY | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC)
        guard fd >= 0 else { throw Invalid.profile }
        defer { Darwin.close(fd) }
        var state = stat()
        guard fstat(fd, &state) == 0, state.st_mode & S_IFMT == S_IFREG,
              state.st_nlink == 1, state.st_size > 0, state.st_size <= 65536 else { throw Invalid.profile }
        let handle = FileHandle(fileDescriptor: fd, closeOnDealloc: false)
        let bytes = try handle.read(upToCount: 65537) ?? Data()
        guard bytes.count == Int(state.st_size) else { throw Invalid.profile }
        let decoder = JSONDecoder(); decoder.keyDecodingStrategy = .convertFromSnakeCase
        let result = try decoder.decode(Self.self, from: bytes)
        try result.validate()
        return result
    }

    private func open(_ asset: Asset, in assets: URL) throws -> Int32 {
        let root = try LinuxDesktopDisk.trustedDirectory(assets)
        let fd = Darwin.open(root.appendingPathComponent(asset.file).path,
                             O_RDONLY | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC)
        guard fd >= 0 else { throw Invalid.assetRead }
        var state = stat()
        guard fstat(fd, &state) == 0, state.st_mode & S_IFMT == S_IFREG, state.st_nlink == 1 else {
            Darwin.close(fd); throw Invalid.assetMetadata
        }
        guard state.st_size == asset.size else { Darwin.close(fd); throw Invalid.assetSize }
        return fd
    }

    private func checked(_ asset: Asset, assets: URL, copyTo destination: Int32? = nil) throws {
        let fd = try open(asset, in: assets)
        defer { Darwin.close(fd) }
        let source = FileHandle(fileDescriptor: fd, closeOnDealloc: false)
        var hash = SHA256(); var count: Int64 = 0
        while let chunk = try source.read(upToCount: 1024 * 1024), !chunk.isEmpty {
            count += Int64(chunk.count)
            guard count <= asset.size else { throw Invalid.assetSize }
            hash.update(data: chunk)
        }
        guard count == asset.size else { throw Invalid.assetSize }
        let sum = hash.finalize().map { String(format: "%02x", $0) }.joined()
        guard sum == asset.sha256 else { throw Invalid.assetDigest }
        if let destination { try Self.copyGzip(fd, to: destination, size: image.sizeBytes, digest: seedSha256) }
    }

    static func copyGzip(_ fd: Int32, to destination: Int32, size: Int64, digest: String) throws {
        guard lseek(fd, 0, SEEK_SET) == 0 else { throw Invalid.assetRead }
        let compressed = dup(fd)
        guard compressed >= 0 else { throw Invalid.assetRead }
        guard let stream = gzdopen(compressed, "rb") else { Darwin.close(compressed); throw Invalid.assetRead }
        defer { gzclose(stream) }
        var buffer = [UInt8](repeating: 0, count: 1024 * 1024)
        var expanded: Int64 = 0
        var rawHash = SHA256()
        while true {
            let capacity = UInt32(buffer.count)
            let n = gzread(stream, &buffer, capacity)
            guard n >= 0 else { throw Invalid.assetRead }
            if n == 0 { guard gzeof(stream) != 0 else { throw Invalid.assetRead }; break }
            expanded += Int64(n)
            guard expanded <= size else { throw Invalid.assetSize }
            let bytes = Data(buffer.prefix(Int(n)))
            rawHash.update(data: bytes)
            try bytes.withUnsafeBytes { try LinuxDesktopDisk.writeAll(destination, bytes: $0) }
        }
        guard expanded == size else { throw Invalid.assetSize }
        guard rawHash.finalize().map({ String(format: "%02x", $0) }).joined() == digest else { throw Invalid.assetDigest }
    }

    func openExisting(in directory: URL, observe: ((LinuxDesktopDisk.RecoveryObservation) -> Void)? = nil) throws -> LinuxDesktopDisk {
        try validate()
        return try LinuxDesktopDisk.openExisting(directory: directory, specification: image, observe: observe)
    }

    func provision(in directory: URL, assets: URL) throws -> LinuxDesktopDisk {
        try validate()
        // The verified gzip seed is bundled in the app bundle. Keep a
        // separate 1GiB import reserve; never count sparse allocation savings.
        return try LinuxDesktopDisk.provision(directory: directory, specification: image,
            availableBytes: { url in
                let values = try FileManager.default.attributesOfFileSystem(forPath: url.path)
                guard let free = values[.systemFreeSize] as? NSNumber,
                      free.uint64Value >= UInt64(Self.size) + 1024 * 1024 * 1024 else {
                    throw LinuxDesktopDisk.Invalid.insufficientSpace
                }
                return free.uint64Value
            }) { fd in try checked(rootfs, assets: assets, copyTo: fd) }
    }

    func arguments(probeAssets: URL, assets: URL, session: URL, disk: LinuxDesktopDisk,
                   serialFD: Int32, controlFD: Int32, networkConsent: Bool,
                   memoryMib: Int = LinuxSteamProfile.memoryMib, offlineCache: LinuxSteamOfflineCache.Handle? = nil) throws -> [String] {
        guard networkConsent else { throw Blocker.networkConsent }
        guard memoryMib >= LinuxSteamMemory.minimum, memoryMib <= LinuxSteamMemory.ceiling, memoryMib % 256 == 0 else { throw Invalid.configuration }
        try validate()
        guard serialFD >= 0, controlFD >= 0, serialFD != controlFD else { throw LinuxTerminalProfile.Invalid.io }
        try disk.validateOwnership()
        guard disk.specification == image else { throw Invalid.configuration }
        let original = try LinuxGuestProfile.load(from: probeAssets)
        guard kernel.sha256 == original.kernel.sha256, kernel.size == Int64(original.kernel.size) else { throw Invalid.configuration }
        try checked(kernel, assets: assets); try checked(initramfs, assets: assets)
        let root = try LinuxDesktopDisk.trustedDirectory(assets)
        var args = try original.arguments(assets: probeAssets, session: session)
        let runtimeInit = session.appendingPathComponent("steam-runtime-initramfs")
        try LinuxSteamOfflineCache.appendRuntime(to: root.appendingPathComponent(initramfs.file), expectedSHA256: initramfs.sha256,
            expectedSize: initramfs.size, output: runtimeInit)
        for (option, value) in [("-kernel", root.appendingPathComponent(kernel.file).path),
                                ("-initrd", runtimeInit.path)] {
            guard let index = args.firstIndex(of: option), index + 1 < args.count else { throw Invalid.configuration }
            args[index + 1] = value
        }
        guard let append = args.firstIndex(of: "-append"), let serial = args.firstIndex(of: "-chardev") else { throw Invalid.configuration }
        args[append + 1] = "console=ttyAMA0 earlycon=pl011,0x09000000 rdinit=/ideck-steam-init panic=0 loglevel=6 ideck.steam_experiment=1 ideck.steam_persistent=1 ideck.steam_network=1"
        for (option, expected, replacement) in [("-cpu", "cortex-a72", "cortex-a76"), ("-m", "1024", String(memoryMib)), ("-nic", "none", "none")] {
            guard let index = args.firstIndex(of: option), args[index + 1] == expected else { throw Invalid.configuration }
            args[index + 1] = replacement
        }
        args[serial + 1] = "socket,id=linuxserial,fd=\(serialFD)"
        guard let nic = args.firstIndex(of: "-nic") else { throw Invalid.configuration }
        args.removeSubrange(nic...nic + 1)
        args += ["-netdev", "user,id=steamnet,net=10.0.2.0/24,dhcpstart=10.0.2.15,ipv6=off", "-device", "virtio-net-device,netdev=steamnet"]
        let path = disk.url.path.replacingOccurrences(of: ",", with: ",,")
        args += ["-chardev", "socket,id=control0,fd=\(controlFD)", "-device", "virtio-serial-pci",
                 "-device", "virtserialport,chardev=control0,name=\(controlPort)",
                 "-drive", "if=none,id=desktop,format=raw,cache=writethrough,file.locking=off,file=\(path)",
                 "-device", "virtio-blk-device,drive=desktop"]
        if let offlineCache {
            try offlineCache.validateIdentity()
            args[append + 1] += " ideck.steam_offline_cache=1"
            let cache = offlineCache.url.path.replacingOccurrences(of: ",", with: ",,")
            args += ["-drive", "if=none,id=steamcache,format=raw,readonly=on,file.locking=off,file=\(cache)",
                     "-device", "virtio-blk-device,drive=steamcache"]
        }
        return args
    }
}
