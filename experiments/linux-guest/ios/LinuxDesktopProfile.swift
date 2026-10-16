import Foundation
import CryptoKit
#if canImport(Darwin)
import Darwin
#else
import Glibc
#endif

/// Storage-only G1 profile. This does not enable a desktop route or construct
/// QEMU argv before the bootstrap/module/GUI gates have passed.
struct LinuxDesktopProfile: Decodable {
    enum Invalid: Error, Equatable {
        case configuration, profile, asset, assetMetadata, assetRead, assetSize, assetDigest
    }
    struct Asset: Decodable {
        let file: String
        let size: Int64
        let sha256: String
    }
    let schema: Int
    let mode: String
    let filesystem: String
    let rootfs: Asset
    let image: LinuxDesktopDisk.Specification

    func validate() throws {
        guard schema == 1, mode == "desktop-rootfs", filesystem == "ext4",
              rootfs.file == "rootfs-v1.raw", rootfs.size == image.sizeBytes, rootfs.sha256.utf8.count == 64,
              rootfs.sha256.range(of: "^[0-9a-f]{64}$", options: .regularExpression) != nil else {
            throw Invalid.configuration
        }
        try image.validate()
    }

    /// Use a reviewed app-bundled profile; an imported image cannot supply its
    /// own expected hash. Bundle aliases are resolved before appending leaves.
    static func load(from assets: URL) throws -> Self {
        let root = try assetDirectory(assets)
        let url = root.appendingPathComponent("desktop-rootfs-profile.json")
        let fd = openRead(url)
        guard fd >= 0 else { throw Invalid.profile }
        defer { closeRead(fd) }
        var state = stat()
        guard fstat(fd, &state) == 0, state.st_mode & S_IFMT == S_IFREG,
              state.st_nlink == 1, state.st_size > 0, state.st_size <= 65536 else { throw Invalid.profile }
        let handle = FileHandle(fileDescriptor: fd, closeOnDealloc: false)
        let data = try handle.read(upToCount: 65537) ?? Data()
        guard data.count == Int(state.st_size) else { throw Invalid.profile }
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        let result = try decoder.decode(Self.self, from: data)
        try result.validate()
        return result
    }

    func openExisting(in directory: URL) throws -> LinuxDesktopDisk {
        try validate()
        // Mutable disk identity/FS contract, not original seed hash. Reopen
        // therefore preserves legitimate package/home/free-count changes.
        return try LinuxDesktopDisk.openExisting(directory: directory, specification: image)
    }

    func provision(in directory: URL, assets: URL) throws -> LinuxDesktopDisk {
        try validate()
        let root = try Self.assetDirectory(assets)
        let seedURL = root.appendingPathComponent(rootfs.file)
        let fd = Self.openRead(seedURL)
        guard fd >= 0 else { throw Invalid.assetRead }
        defer { Self.closeRead(fd) }
        var state = stat()
        guard fstat(fd, &state) == 0, state.st_mode & S_IFMT == S_IFREG,
              state.st_nlink == 1 else { throw Invalid.assetMetadata }
        guard state.st_size == off_t(rootfs.size) else { throw Invalid.assetSize }
        return try LinuxDesktopDisk.provision(directory: directory, specification: image) { destination in
            let source = FileHandle(fileDescriptor: fd, closeOnDealloc: false)
            var hash = SHA256()
            var count: Int64 = 0
            while let bytes = try source.read(upToCount: 1024 * 1024), !bytes.isEmpty {
                count += Int64(bytes.count)
                guard count <= rootfs.size else { throw Invalid.assetSize }
                hash.update(data: bytes)
                try bytes.withUnsafeBytes { try LinuxDesktopDisk.writeAll(destination, bytes: $0) }
            }
            guard count == rootfs.size else { throw Invalid.assetSize }
            let digest = hash.finalize().map { String(format: "%02x", $0) }.joined()
            guard digest == rootfs.sha256 else { throw Invalid.assetDigest }
        }
    }

    private static func assetDirectory(_ assets: URL) throws -> URL {
        guard assets.isFileURL, !assets.path.contains("\0"),
              let path = realpath(assets.path, nil) else { throw Invalid.asset }
        defer { free(path) }
        let canonical = String(cString: path)
        let root = URL(fileURLWithPath: canonical, isDirectory: true)
        guard root.path == canonical else { throw Invalid.asset }
        try LinuxDesktopDisk.validateDirectory(root)
        return root
    }
    private static func openRead(_ url: URL) -> Int32 {
        #if canImport(Darwin)
        return Darwin.open(url.path, O_RDONLY | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC)
        #else
        return Glibc.open(url.path, O_RDONLY | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC)
        #endif
    }
    private static func closeRead(_ fd: Int32) {
        #if canImport(Darwin)
        _ = Darwin.close(fd)
        #else
        _ = Glibc.close(fd)
        #endif
    }
}
