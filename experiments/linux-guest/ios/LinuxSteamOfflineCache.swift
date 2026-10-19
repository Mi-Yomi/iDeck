import Foundation
import CryptoKit
import Darwin

/// A fixed canonical USTAR stream, never a general-purpose archive extractor.
/// Expected headers and hashes come from app code, never the imported file.
enum LinuxSteamOfflineCache {
    enum Invalid: Error { case metadata, header, digest, padding, space, busy, exists, io }
    struct Entry {
        let header: String
        let size: Int64
        let sha256: String
    }
    static let filename = "packages.tar"
    static let reserve: UInt64 = 1024 * 1024 * 1024

    final class Handle {
        let fd: Int32
        let url: URL
        init(_ url: URL) throws {
            self.url = url
            let descriptor = Darwin.open(url.path, O_RDONLY | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC)
            guard descriptor >= 0 else { throw Invalid.io }
            do {
                try LinuxSteamOfflineCache.metadata(descriptor, size: LinuxSteamCacheContract.archiveSize, owned: true)
                guard flock(descriptor, LOCK_SH | LOCK_NB) == 0 else { throw Invalid.busy }
                try LinuxSteamOfflineCache.verify(descriptor)
            } catch { Darwin.close(descriptor); throw error }
            fd = descriptor
        }
        deinit { Darwin.close(fd) }
        func validateIdentity() throws {
            try LinuxSteamOfflineCache.metadata(fd, size: LinuxSteamCacheContract.archiveSize, owned: true)
            var opened = stat(), named = stat()
            guard fstat(fd, &opened) == 0, lstat(url.path, &named) == 0,
                  named.st_mode & S_IFMT == S_IFREG, named.st_nlink == 1,
                  opened.st_dev == named.st_dev, opened.st_ino == named.st_ino,
                  opened.st_size == LinuxSteamCacheContract.archiveSize else { throw Invalid.metadata }
        }
    }

    private static func metadata(_ fd: Int32, size: Int64, owned: Bool) throws {
        var s = stat()
        guard fstat(fd, &s) == 0, s.st_mode & S_IFMT == S_IFREG,
              s.st_nlink == 1, s.st_size == size,
              !owned || (s.st_uid == geteuid() && s.st_mode & 0o777 == 0o600) else { throw Invalid.metadata }
    }
    private static func read(_ fd: Int32, offset: Int64, count: Int) throws -> Data {
        var bytes = Data(count: count), done = 0
        while done < count {
            let amount = bytes.withUnsafeMutableBytes {
                pread(fd, $0.baseAddress!.advanced(by: done), count - done, off_t(offset) + off_t(done))
            }
            if amount < 0 && errno == EINTR { continue }
            guard amount > 0 else { throw Invalid.io }
            done += amount
        }
        return bytes
    }
    /// Header byte equality rejects traversal, links, duplicates, extra entries,
    /// PAX/GNU extensions and metadata corruption before using any member name.
    static func verify(_ fd: Int32, entries: [Entry] = LinuxSteamCacheContract.entries,
                       archiveSize: Int64 = LinuxSteamCacheContract.archiveSize) throws {
        guard !entries.isEmpty, entries.count <= 64, archiveSize > 0,
              archiveSize <= 512 * 1024 * 1024, archiveSize % 10240 == 0 else { throw Invalid.metadata }
        var offset: Int64 = 0
        for entry in entries {
            guard entry.size > 0, entry.size <= 512 * 1024 * 1024,
                  let header = Data(base64Encoded: entry.header), header.count == 512,
                  offset <= archiveSize - 512,
                  try read(fd, offset: offset, count: 512) == header else { throw Invalid.header }
            offset += 512
            guard entry.size <= archiveSize - offset else { throw Invalid.metadata }
            var hash = SHA256(), left = entry.size
            while left > 0 {
                let bytes = try read(fd, offset: offset, count: Int(min(left, 1024 * 1024)))
                hash.update(data: bytes); offset += Int64(bytes.count); left -= Int64(bytes.count)
            }
            let digest = hash.finalize().map { String(format: "%02x", $0) }.joined()
            guard digest == entry.sha256 else { throw Invalid.digest }
            let padding = Int((512 - entry.size % 512) % 512)
            guard Int64(padding) <= archiveSize - offset,
                  try read(fd, offset: offset, count: padding).allSatisfy({ $0 == 0 }) else { throw Invalid.padding }
            offset += Int64(padding)
        }
        guard archiveSize - offset >= 1024 else { throw Invalid.padding }
        while offset < archiveSize {
            let amount = Int(min(archiveSize - offset, 1024 * 1024))
            guard try read(fd, offset: offset, count: amount).allSatisfy({ $0 == 0 }) else { throw Invalid.padding }
            offset += Int64(amount)
        }
        var s = stat()
        guard fstat(fd, &s) == 0, s.st_size == archiveSize else { throw Invalid.metadata }
    }

    /// Same bounded newc append contract as recovery, with a Steam-only suffix.
    /// Keep the historically verified recovery generator/source unchanged.
    static func appendRuntime(to original: URL, expectedSHA256: String, expectedSize: Int64, output: URL) throws {
        let input = Darwin.open(original.path, O_RDONLY | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC)
        guard input >= 0 else { throw Invalid.io }
        defer { Darwin.close(input) }
        try metadata(input, size: expectedSize, owned: false)
        guard expectedSize > 0, expectedSize <= 32 * 1024 * 1024 else { throw Invalid.metadata }
        let target = Darwin.open(output.path, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0o600)
        guard target >= 0 else { throw Invalid.io }
        defer { Darwin.close(target) }
        var offset: Int64 = 0, hash = SHA256()
        while offset < expectedSize {
            let bytes = try read(input, offset: offset, count: Int(min(expectedSize - offset, 1024 * 1024)))
            hash.update(data: bytes)
            try bytes.withUnsafeBytes { try LinuxDesktopDisk.writeAll(target, bytes: $0) }
            offset += Int64(bytes.count)
        }
        guard hash.finalize().map({ String(format: "%02x", $0) }).joined() == expectedSHA256 else { throw Invalid.digest }
        let suffix = Data(repeating: 0, count: Int((4 - offset % 4) % 4)) + LinuxSteamCacheContract.suffix
        try suffix.withUnsafeBytes { try LinuxDesktopDisk.writeAll(target, bytes: $0) }
        guard fsync(target) == 0 else { throw Invalid.io }
    }

    /// Recover only the exact two-name publication interruption, never an
    /// arbitrary hard link. The verified published inode already contains pins.
    static func reconcilePublication(in directory: URL,
                                     entries: [Entry] = LinuxSteamCacheContract.entries,
                                     archiveSize: Int64 = LinuxSteamCacheContract.archiveSize) throws {
        try LinuxDesktopDisk.validateDirectory(directory, allowingMissing: true)
        let parent = Darwin.open(directory.path, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC)
        if parent < 0 { if errno == ENOENT { return }; throw Invalid.metadata }
        defer { Darwin.close(parent) }
        let fd = openat(parent, filename, O_RDONLY | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC)
        if fd < 0 { if errno == ENOENT { return }; throw Invalid.metadata }
        defer { Darwin.close(fd) }
        var state = stat(), partial = stat(), published = stat()
        guard fstat(fd, &state) == 0 else { throw Invalid.metadata }
        if state.st_nlink == 1 { return }
        guard state.st_nlink == 2, state.st_mode & S_IFMT == S_IFREG,
              state.st_uid == geteuid(), state.st_mode & 0o777 == 0o600,
              state.st_size == archiveSize, flock(fd, LOCK_EX | LOCK_NB) == 0 else { throw Invalid.metadata }
        guard fstatat(parent, ".import.partial", &partial, AT_SYMLINK_NOFOLLOW) == 0,
              fstatat(parent, filename, &published, AT_SYMLINK_NOFOLLOW) == 0,
              partial.st_mode & S_IFMT == S_IFREG, published.st_mode & S_IFMT == S_IFREG,
              state.st_dev == partial.st_dev, state.st_ino == partial.st_ino,
              state.st_dev == published.st_dev, state.st_ino == published.st_ino else { throw Invalid.metadata }
        try verify(fd, entries: entries, archiveSize: archiveSize)
        guard unlinkat(parent, ".import.partial", 0) == 0, fsync(parent) == 0 else { throw Invalid.io }
    }

    static func existing(in directory: URL) throws -> Handle? {
        try reconcilePublication(in: directory)
        try LinuxDesktopDisk.validateDirectory(directory, allowingMissing: true)
        let file = directory.appendingPathComponent(filename)
        var s = stat()
        if lstat(file.path, &s) != 0 {
            guard errno == ENOENT else { throw Invalid.metadata }
            return nil
        }
        return try Handle(file)
    }

    /// Explicit owner import. Only the reserved partial can be restarted; an
    /// existing published cache is never replaced, and userdata is not an input.
    static func importArchive(_ source: URL, into directory: URL,
                              entries: [Entry] = LinuxSteamCacheContract.entries,
                              archiveSize: Int64 = LinuxSteamCacheContract.archiveSize,
                              checkpoint: (() throws -> Void)? = nil) throws {
        guard archiveSize > 0, archiveSize <= 512 * 1024 * 1024, archiveSize % 10240 == 0 else { throw Invalid.metadata }
        let canonical = try LinuxDesktopDisk.trustedDirectory(source.deletingLastPathComponent())
        let original = canonical.appendingPathComponent(source.lastPathComponent)
        let input = Darwin.open(original.path, O_RDONLY | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC)
        guard input >= 0 else { throw Invalid.io }
        defer { Darwin.close(input) }
        try metadata(input, size: archiveSize, owned: false)
        try LinuxDesktopDisk.validateDirectory(directory, allowingMissing: true)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
        try LinuxDesktopDisk.validateDirectory(directory)
        try reconcilePublication(in: directory, entries: entries, archiveSize: archiveSize)
        let parent = Darwin.open(directory.path, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC)
        guard parent >= 0 else { throw Invalid.io }
        defer { Darwin.close(parent) }
        var parentStat = stat(), namedParent = stat()
        guard fstat(parent, &parentStat) == 0, parentStat.st_uid == geteuid() else { throw Invalid.metadata }
        var published = stat()
        guard fstatat(parent, filename, &published, AT_SYMLINK_NOFOLLOW) != 0 else { throw Invalid.exists }
        guard errno == ENOENT else { throw Invalid.metadata }
        let output = openat(parent, ".import.partial", O_RDWR | O_CREAT | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC, 0o600)
        guard output >= 0 else { throw Invalid.io }
        defer { Darwin.close(output) }
        guard flock(output, LOCK_EX | LOCK_NB) == 0 else { throw Invalid.busy }
        var before = stat()
        guard fstat(output, &before) == 0, before.st_mode & S_IFMT == S_IFREG,
              before.st_nlink == 1, before.st_uid == geteuid(), before.st_mode & 0o777 == 0o600,
              before.st_size >= 0, before.st_size <= archiveSize else { throw Invalid.metadata }
        let capacity = try FileManager.default.attributesOfFileSystem(forPath: directory.path)
        guard let free = capacity[.systemFreeSize] as? NSNumber,
              free.uint64Value >= UInt64(archiveSize) + reserve else { throw Invalid.space }
        guard ftruncate(output, 0) == 0 else { throw Invalid.io }
        var offset: Int64 = 0
        while offset < archiveSize {
            try checkpoint?()
            let data = try read(input, offset: offset, count: Int(min(archiveSize - offset, 1024 * 1024)))
            try data.withUnsafeBytes { try LinuxDesktopDisk.writeAll(output, bytes: $0) }
            offset += Int64(data.count)
        }
        try metadata(input, size: archiveSize, owned: false)
        try verify(output, entries: entries, archiveSize: archiveSize)
        guard fsync(output) == 0 else { throw Invalid.io }
        try checkpoint?()
        var named = stat()
        guard lstat(directory.path, &namedParent) == 0, parentStat.st_dev == namedParent.st_dev,
              parentStat.st_ino == namedParent.st_ino,
              fstatat(parent, ".import.partial", &named, AT_SYMLINK_NOFOLLOW) == 0,
              before.st_dev == named.st_dev, before.st_ino == named.st_ino else { throw Invalid.metadata }
        guard linkat(parent, ".import.partial", parent, filename, 0) == 0 else { throw Invalid.exists }
        try checkpoint?()
        guard unlinkat(parent, ".import.partial", 0) == 0, fsync(parent) == 0 else { throw Invalid.io }
    }
}
