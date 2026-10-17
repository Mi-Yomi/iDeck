import Foundation
import CryptoKit
import Darwin

/// A versioned GUI contract, isolated from the accepted Debian console seed.
struct LinuxGUIProfile: Decodable {
    typealias Invalid = LinuxDesktopProfile.Invalid
    typealias Asset = LinuxDesktopProfile.Asset
    static let uuid = "b66e1c8d-9cbf-45a7-b97b-dcc8f68efca7"
    static let size: Int64 = 1_342_177_280
    let schema: Int
    let mode: String
    let controlPort: String
    let kernel: Asset
    let initramfs: Asset
    let rootfs: Asset
    let image: LinuxDesktopDisk.Specification

    func validate() throws {
        guard schema == 1, mode == "desktop", controlPort == "org.ideck.control",
              kernel.file == "vmlinuz-virt", initramfs.file == "initramfs-desktop.gz",
              rootfs.file == "gui-rootfs-v1.raw", image.uuid == Self.uuid,
              image.sizeBytes == Self.size, rootfs.size == Self.size else { throw Invalid.configuration }
        try image.validate()
        for asset in [kernel, initramfs, rootfs] {
            guard asset.size > 0,
                  asset.sha256.range(of: "^[0-9a-f]{64}$", options: .regularExpression) != nil else { throw Invalid.configuration }
        }
        guard kernel.size <= 32 * 1024 * 1024, initramfs.size <= 128 * 1024 * 1024 else { throw Invalid.configuration }
    }

    static func load(from assets: URL) throws -> Self {
        let root = try LinuxDesktopDisk.trustedDirectory(assets)
        let fd = Darwin.open(root.appendingPathComponent("desktop-profile.json").path,
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
            if let destination { try chunk.withUnsafeBytes { try LinuxDesktopDisk.writeAll(destination, bytes: $0) } }
        }
        guard count == asset.size else { throw Invalid.assetSize }
        let sum = hash.finalize().map { String(format: "%02x", $0) }.joined()
        guard sum == asset.sha256 else { throw Invalid.assetDigest }
    }

    func openExisting(in directory: URL) throws -> LinuxDesktopDisk {
        try validate()
        return try LinuxDesktopDisk.openExisting(directory: directory, specification: image)
    }

    func provision(in directory: URL, assets: URL) throws -> LinuxDesktopDisk {
        try validate()
        // The verified raw is already materialized in the app bundle. Keep a
        // separate 512MiB import reserve; never count sparse allocation savings.
        return try LinuxDesktopDisk.provision(directory: directory, specification: image,
            availableBytes: { url in
                let values = try FileManager.default.attributesOfFileSystem(forPath: url.path)
                guard let free = values[.systemFreeSize] as? NSNumber,
                      free.uint64Value >= UInt64(Self.size) + 512 * 1024 * 1024 else {
                    throw LinuxDesktopDisk.Invalid.insufficientSpace
                }
                return free.uint64Value
            }) { fd in try checked(rootfs, assets: assets, copyTo: fd) }
    }

    func arguments(probeAssets: URL, assets: URL, session: URL, disk: LinuxDesktopDisk,
                   serialFD: Int32, controlFD: Int32) throws -> [String] {
        try validate()
        guard serialFD >= 0, controlFD >= 0, serialFD != controlFD else { throw LinuxTerminalProfile.Invalid.io }
        try disk.validateOwnership()
        guard disk.specification == image else { throw Invalid.configuration }
        let original = try LinuxGuestProfile.load(from: probeAssets)
        guard kernel.sha256 == original.kernel.sha256, kernel.size == Int64(original.kernel.size) else { throw Invalid.configuration }
        try checked(kernel, assets: assets); try checked(initramfs, assets: assets)
        let root = try LinuxDesktopDisk.trustedDirectory(assets)
        var args = try original.arguments(assets: probeAssets, session: session)
        for (option, value) in [("-kernel", root.appendingPathComponent(kernel.file).path),
                                ("-initrd", root.appendingPathComponent(initramfs.file).path)] {
            guard let index = args.firstIndex(of: option), index + 1 < args.count else { throw Invalid.configuration }
            args[index + 1] = value
        }
        guard let append = args.firstIndex(of: "-append"), let serial = args.firstIndex(of: "-chardev") else { throw Invalid.configuration }
        args[append + 1] = "console=ttyAMA0 earlycon=pl011,0x09000000 rdinit=/ideck-desktop-init panic=0 loglevel=6"
        args[serial + 1] = "socket,id=linuxserial,fd=\(serialFD)"
        let path = disk.url.path.replacingOccurrences(of: ",", with: ",,")
        args += ["-chardev", "socket,id=control0,fd=\(controlFD)", "-device", "virtio-serial-pci",
                 "-device", "virtserialport,chardev=control0,name=\(controlPort)",
                 "-drive", "if=none,id=desktop,format=raw,cache=writethrough,file.locking=off,file=\(path)",
                 "-device", "virtio-blk-device,drive=desktop"]
        return args
    }
}
