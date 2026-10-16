import Foundation
#if canImport(Darwin)
import Darwin
#else
import Glibc
#endif

/// Separate ext4 storage contract. Existing terminal FAT16 handling is untouched.
/// No QEMU entry, mounting, recovery, formatting or legacy-data mutation here.
final class LinuxDesktopDisk {
    enum Invalid: Error, Equatable {
        case specification, directory, inspection, open, locked, metadata, size
        case headerRead, checksum, filesystem, uuid, geometry, features, journal
        case needsRecovery, ownership, alreadyExists, insufficientSpace, io
    }
    struct Features: Codable, Equatable {
        let compat: UInt32
        let incompat: UInt32
        let roCompat: UInt32
        // Explicit mke2fs feature set, not whatever a host defaults to today.
        static let supported = Features(compat: 0x2c, incompat: 0xc2, roCompat: 0x443)
    }
    struct Specification: Codable, Equatable {
        let sizeBytes: Int64
        let uuid: String
        let blockSize: Int
        let features: Features

        func validate() throws {
            guard sizeBytes >= 64 * 1024 * 1024, sizeBytes <= 4 * 1024 * 1024 * 1024,
                  sizeBytes % 4096 == 0, blockSize == 4096, features == .supported, uuid.utf8.count == 36,
                  uuid.range(of: "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
                             options: .regularExpression) != nil,
                  uuid != "00000000-0000-0000-0000-000000000000" else { throw Invalid.specification }
        }
    }

    let url: URL
    let specification: Specification
    private var fd: Int32
    private init(url: URL, specification: Specification, fd: Int32) {
        self.url = url; self.specification = specification; self.fd = fd
    }
    deinit { if fd >= 0 { _ = Self.closeFD(fd) } }

    /// Only for an existing system-provided Documents/temporary prefix, before
    /// appending app-owned children. Resolve Apple's /var aliases explicitly.
    static func trustedDirectory(_ existing: URL) throws -> URL {
        guard existing.isFileURL, let resolved = realpath(existing.path, nil) else { throw Invalid.directory }
        defer { free(resolved) }
        let path = String(cString: resolved)
        let url = URL(fileURLWithPath: path, isDirectory: true)
        guard url.path == path else { throw Invalid.directory }
        try validateDirectory(url)
        return url
    }

    static func validateDirectory(_ directory: URL, allowingMissing: Bool = false) throws {
        guard directory.isFileURL, directory.baseURL == nil, directory.query == nil,
              directory.fragment == nil,
              directory.host == nil || directory.host == "" || directory.host == "localhost",
              let raw = URLComponents(url: directory, resolvingAgainstBaseURL: false)?.path,
              raw.hasPrefix("/"), directory.path.hasPrefix("/"), !raw.contains("\0") else { throw Invalid.directory }
        let pieces = raw.split(separator: "/")
        guard !pieces.contains("."), !pieces.contains(".."), !directory.path.contains("\0") else { throw Invalid.directory }
        var prefix = ""
        for piece in directory.path.split(separator: "/") {
            prefix += "/" + piece
            var state = stat()
            if lstat(prefix, &state) == 0 {
                guard state.st_mode & S_IFMT == S_IFDIR else { throw Invalid.directory }
            } else if !allowingMissing || errno != ENOENT { throw Invalid.directory }
        }
    }

    static func openExisting(directory: URL, specification: Specification) throws -> LinuxDesktopDisk {
        try specification.validate()
        try validateDirectory(directory)
        let url = directory.appendingPathComponent("rootfs-v1.raw")
        let descriptor = openFD(url.path, O_RDWR | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC)
        guard descriptor >= 0 else { throw Invalid.open }
        var accepted = false
        defer { if !accepted { _ = closeFD(descriptor) } }
        guard flock(descriptor, LOCK_EX | LOCK_NB) == 0 else { throw Invalid.locked }
        try validateIdentity(fd: descriptor, url: url, specification: specification)
        try validateSuperblock(fd: descriptor, specification: specification)
        accepted = true
        return LinuxDesktopDisk(url: url, specification: specification, fd: descriptor)
    }

    /// The profile supplies a streaming cryptographically checked copy. The
    /// temporary is never published unless both that copy and ext4 guards pass.
    /// An existing path always wins; provisioning never reseeds or replaces it.
    static func provision(directory: URL, specification: Specification,
                          validatedCopy: (Int32) throws -> Void) throws -> LinuxDesktopDisk {
        try specification.validate()
        try validateDirectory(directory, allowingMissing: true)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        try validateDirectory(directory)
        let target = directory.appendingPathComponent("rootfs-v1.raw")
        var state = stat()
        guard lstat(target.path, &state) != 0 else { throw Invalid.alreadyExists }
        guard errno == ENOENT else { throw Invalid.inspection }
        let capacity = try FileManager.default.attributesOfFileSystem(forPath: directory.path)
        guard let available = capacity[.systemFreeSize] as? NSNumber else { throw Invalid.io }
        guard available.uint64Value >= UInt64(specification.sizeBytes) + 32 * 1024 * 1024 else { throw Invalid.insufficientSpace }
        let directoryFD = openFD(directory.path, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC)
        guard directoryFD >= 0 else { throw Invalid.directory }
        defer { _ = closeFD(directoryFD) }
        func sameDirectory() throws {
            var opened = stat(), named = stat()
            guard fstat(directoryFD, &opened) == 0, lstat(directory.path, &named) == 0,
                  named.st_mode & S_IFMT == S_IFDIR,
                  opened.st_dev == named.st_dev, opened.st_ino == named.st_ino else { throw Invalid.directory }
        }
        try sameDirectory()
        let temporary = ".rootfs-import-" + UUID().uuidString
        let descriptor = openAt(directoryFD, temporary, O_RDWR | O_CREAT | O_EXCL | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC, mode_t(0o600))
        guard descriptor >= 0 else { throw Invalid.open }
        var accepted = false
        defer {
            // Never unlink a different inode supplied under our old temp name.
            var opened = stat(), named = stat()
            if fstat(descriptor, &opened) == 0,
               fstatat(directoryFD, temporary, &named, AT_SYMLINK_NOFOLLOW) == 0,
               opened.st_dev == named.st_dev, opened.st_ino == named.st_ino {
                _ = unlinkat(directoryFD, temporary, 0)
            }
            if !accepted { _ = closeFD(descriptor) }
        }
        guard flock(descriptor, LOCK_EX | LOCK_NB) == 0 else { throw Invalid.locked }
        try validatedCopy(descriptor)
        guard fstat(descriptor, &state) == 0, state.st_mode & S_IFMT == S_IFREG,
              state.st_nlink == 1, state.st_size == off_t(specification.sizeBytes) else { throw Invalid.size }
        try validateSuperblock(fd: descriptor, specification: specification)
        guard fsync(descriptor) == 0 else { throw Invalid.io }
        try validateDirectory(directory)
        try sameDirectory()
        var named = stat()
        guard fstatat(directoryFD, temporary, &named, AT_SYMLINK_NOFOLLOW) == 0,
              named.st_dev == state.st_dev, named.st_ino == state.st_ino,
              named.st_mode & S_IFMT == S_IFREG, named.st_nlink == 1 else { throw Invalid.ownership }
        // Anchor BOTH paths to the held directory, not a mutable absolute path.
        guard linkat(directoryFD, temporary, directoryFD, "rootfs-v1.raw", 0) == 0 else {
            if errno == EEXIST { throw Invalid.alreadyExists }
            throw Invalid.io
        }
        guard fstatat(directoryFD, "rootfs-v1.raw", &named, AT_SYMLINK_NOFOLLOW) == 0,
              named.st_dev == state.st_dev, named.st_ino == state.st_ino else { throw Invalid.ownership }
        guard unlinkat(directoryFD, temporary, 0) == 0 else { throw Invalid.io }
        try sameDirectory()
        try validateIdentity(fd: descriptor, url: target, specification: specification)
        accepted = true
        // Preserve the SAME exclusive owner through publication and handoff.
        return LinuxDesktopDisk(url: target, specification: specification, fd: descriptor)
    }

    /// Recheck before any future native handoff. Does not reread a superblock
    /// while a live guest may be changing it, or release the exclusive lock.
    func validateOwnership() throws {
        guard fd >= 0 else { throw Invalid.ownership }
        try Self.validateDirectory(url.deletingLastPathComponent())
        guard flock(fd, LOCK_EX | LOCK_NB) == 0 else { throw Invalid.ownership }
        try Self.validateIdentity(fd: fd, url: url, specification: specification)
    }

    private static func validateIdentity(fd: Int32, url: URL, specification: Specification) throws {
        var opened = stat(), named = stat()
        guard fstat(fd, &opened) == 0, lstat(url.path, &named) == 0,
              opened.st_mode & S_IFMT == S_IFREG, named.st_mode & S_IFMT == S_IFREG,
              opened.st_nlink == 1, named.st_nlink == 1,
              opened.st_dev == named.st_dev, opened.st_ino == named.st_ino else { throw Invalid.ownership }
        guard opened.st_size == off_t(specification.sizeBytes), named.st_size == opened.st_size else { throw Invalid.size }
    }

    static func validateSuperblock(fd: Int32, specification: Specification) throws {
        try specification.validate()
        var header = [UInt8](repeating: 0, count: 1024)
        var count = 0
        while count < header.count {
            let remaining = 1024 - count
            let result = header.withUnsafeMutableBytes {
                pread(fd, $0.baseAddress!.advanced(by: count), remaining, off_t(1024 + count))
            }
            if result < 0, errno == EINTR { continue }
            guard result > 0 else { throw Invalid.headerRead }
            count += result
        }
        try validateHeader(header, specification: specification)
    }

    /// Only superblock contract validation, not an fsck/inode-tree integrity claim.
    static func validateHeader(_ h: [UInt8], specification s: Specification) throws {
        try s.validate()
        guard h.count == 1024 else { throw Invalid.headerRead }
        func u16(_ n: Int) -> UInt32 { UInt32(h[n]) | UInt32(h[n + 1]) << 8 }
        func u32(_ n: Int) -> UInt32 { u16(n) | u16(n + 2) << 16 }
        guard u16(0x38) == 0xef53, u32(0x4c) == 1 else { throw Invalid.filesystem }
        guard h[0x175] == 1, crc32c(h[0..<1020]) == u32(1020) else { throw Invalid.checksum }
        let hex = h[0x68..<0x78].map { String(format: "%02x", $0) }.joined()
        guard hex == s.uuid.replacingOccurrences(of: "-", with: "") else { throw Invalid.uuid }
        let incompat = u32(0x60)
        guard u32(0x5c) == s.features.compat, incompat & ~UInt32(4) == s.features.incompat,
              u32(0x64) == s.features.roCompat else { throw Invalid.features }
        guard incompat & 4 == 0, u16(0x3a) == 1, u32(0xe8) == 0,
              u32(0x194) == 0 else { throw Invalid.needsRecovery }
        let blocks = UInt64(u32(4)) | UInt64(u32(0x150)) << 32
        guard blocks == UInt64(s.sizeBytes / 4096) else { throw Invalid.geometry }
        let groups = (blocks + 32767) / 32768
        let inodesPerGroup = UInt64(u32(0x28))
        guard u32(0x14) == 0, u32(0x18) == 2, u32(0x1c) == 2,
              blocks == UInt64(s.sizeBytes / 4096), u32(0x20) == 32768, u32(0x24) == 32768,
              inodesPerGroup > 0, inodesPerGroup <= 32768,
              UInt64(u32(0)) == groups * inodesPerGroup,
              u16(0x58) == 256, u16(0xfe) == 64 else { throw Invalid.geometry }
        guard u32(0xe0) == 8, u32(0xe4) == 0, h[0xd0..<0xe0].allSatisfy({ $0 == 0 }) else { throw Invalid.journal }
    }

    /// ext4 stores raw CRC32C(~0, superblock[0..<1020]), without a final XOR.
    static func crc32c<C: Collection>(_ bytes: C) -> UInt32 where C.Element == UInt8 {
        var value: UInt32 = 0xffffffff
        for byte in bytes {
            value ^= UInt32(byte)
            for _ in 0..<8 { value = (value >> 1) ^ ((value & 1) == 1 ? 0x82f63b78 : 0) }
        }
        return value
    }

    func synchronize() throws {
        guard fd >= 0, fsync(fd) == 0 else { throw Invalid.io }
    }
    /// Only for a disk that has NEVER been handed to QEMU. A future runtime
    /// retains this owner through process exit, including after orderly Stop.
    func closeUnused() { if fd >= 0 { _ = Self.closeFD(fd); fd = -1 } }

    static func writeAll(_ fd: Int32, bytes: UnsafeRawBufferPointer) throws {
        var written = 0
        while written < bytes.count {
            #if canImport(Darwin)
            let count = Darwin.write(fd, bytes.baseAddress!.advanced(by: written), bytes.count - written)
            #else
            let count = Glibc.write(fd, bytes.baseAddress!.advanced(by: written), bytes.count - written)
            #endif
            if count < 0, errno == EINTR { continue }
            guard count > 0 else { throw Invalid.io }
            written += count
        }
    }
    private static func openFD(_ path: String, _ flags: Int32, _ mode: mode_t = 0) -> Int32 {
        #if canImport(Darwin)
        return Darwin.open(path, flags, mode)
        #else
        return Glibc.open(path, flags, mode)
        #endif
    }
    private static func openAt(_ directory: Int32, _ name: String, _ flags: Int32, _ mode: mode_t) -> Int32 {
        #if canImport(Darwin)
        return Darwin.openat(directory, name, flags, mode)
        #else
        return Glibc.openat(directory, name, flags, mode)
        #endif
    }
    private static func closeFD(_ fd: Int32) -> Int32 {
        #if canImport(Darwin)
        return Darwin.close(fd)
        #else
        return Glibc.close(fd)
        #endif
    }
}
