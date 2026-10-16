import Foundation
import CryptoKit
import Darwin

/// Validated local terminal assets and a separate, persistent user-data disk.
/// This helper has no UI, runtime, network or pairing dependencies.
struct LinuxTerminalProfile: Decodable {
    struct Asset: Decodable {
        let file: String
        let sha256: String
        let size: Int
    }
    enum Invalid: Error, Equatable {
        case configuration, asset, disk, diskLocked, io
        case assetDescriptor, assetDirectory, assetInspection, assetType, assetSize
        case assetContainment, assetRead, assetContentSize, assetDigest, assetKernelMismatch
        // Static stage names identify a failed guard without exposing paths.
        case diskTrustedDirectory, diskDirectoryURL, diskDirectoryComponent
        case diskDirectoryType, diskDirectoryInspection, diskInspection, diskOpen, diskLinks
        case diskMetadata, diskSize, diskHeaderRead, diskFormat, diskSeedSize, diskOwnership
    }
    static let diskSize = 128 * 1024 * 1024
    let schema: Int
    let mode: String
    let kernel: Asset
    let initramfs: Asset
    let seed: Asset
    let diskSizeBytes: Int
    let filesystem: String
    let controlPort: String
    let cpu: String
    let memoryMib: Int
    let vcpus: Int
    let tcgCacheMib: Int
    let width: Int
    let height: Int

    static func load(from assets: URL) throws -> Self {
        let file = assets.appendingPathComponent("terminal-profile.json")
        let values = try file.resourceValues(forKeys: [.isRegularFileKey, .isSymbolicLinkKey, .fileSizeKey])
        guard values.isRegularFile == true, values.isSymbolicLink != true,
              let count = values.fileSize, count > 0, count <= 65536 else { throw Invalid.asset }
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        let profile = try decoder.decode(Self.self, from: Data(contentsOf: file))
        guard profile.schema == 1, profile.mode == "terminal", profile.filesystem == "fat16",
              profile.controlPort == "org.ideck.control", profile.diskSizeBytes == diskSize,
              profile.seed.size == diskSize, profile.cpu == "cortex-a72", profile.memoryMib == 1024,
              profile.vcpus == 4, profile.tcgCacheMib == 256, profile.width == 800, profile.height == 600 else {
            throw Invalid.configuration
        }
        return profile
    }

    private func checked(_ asset: Asset, name: String, in assets: URL) throws -> URL {
        guard asset.file == name, asset.size > 0, asset.size <= Self.diskSize,
              asset.sha256.utf8.count == 64,
              asset.sha256.utf8.allSatisfy({ (48...57).contains($0) || (97...102).contains($0) }) else { throw Invalid.assetDescriptor }
        guard let root = LinuxGuestAssetPath.directory(assets) else { throw Invalid.assetDirectory }
        let file = root.appendingPathComponent(name)
        let values: URLResourceValues
        do { values = try file.resourceValues(forKeys: [.isRegularFileKey, .isSymbolicLinkKey, .fileSizeKey]) }
        catch { throw Invalid.assetInspection }
        guard values.isRegularFile == true, values.isSymbolicLink != true else { throw Invalid.assetType }
        guard values.fileSize == asset.size else { throw Invalid.assetSize }
        guard LinuxGuestAssetPath.canonical(file) == file.path else { throw Invalid.assetContainment }
        let handle: FileHandle
        do { handle = try FileHandle(forReadingFrom: file) }
        catch { throw Invalid.assetRead }
        defer { try? handle.close() }
        var hash = SHA256()
        var count = 0
        while true {
            let bytes: Data
            do { bytes = try handle.read(upToCount: 1024 * 1024) ?? Data() }
            catch { throw Invalid.assetRead }
            if bytes.isEmpty { break }
            count += bytes.count
            guard count <= asset.size else { throw Invalid.assetContentSize }
            hash.update(data: bytes)
        }
        let digest = hash.finalize().map { String(format: "%02x", $0) }.joined()
        guard count == asset.size else { throw Invalid.assetContentSize }
        guard digest == asset.sha256 else { throw Invalid.assetDigest }
        return file
    }

    func openDisk(in directory: URL, assets: URL) throws -> LinuxTerminalDisk {
        let seedURL = try checked(seed, name: "userdata-seed.raw", in: assets)
        return try LinuxTerminalDisk.open(directory: directory, seed: seedURL, size: diskSizeBytes)
    }

    func arguments(probeAssets: URL, terminalAssets: URL, session: URL, disk: LinuxTerminalDisk,
                   serialFD: Int32, controlFD: Int32) throws -> [String] {
        guard serialFD >= 0, controlFD >= 0, serialFD != controlFD else { throw Invalid.configuration }
        // Disabling QEMU's duplicate byte locks requires the live host owner,
        // never an arbitrary path. Recheck again immediately before native entry.
        try disk.validateOwnership()
        let diskURL = disk.url
        let original = try LinuxGuestProfile.load(from: probeAssets)
        guard kernel.file == original.kernel.file, kernel.sha256 == original.kernel.sha256,
              kernel.size == original.kernel.size else { throw Invalid.assetKernelMismatch }
        let ramdisk = try checked(initramfs, name: "initramfs-terminal.gz", in: terminalAssets)
        // The original validator still checks the kernel AND probe initramfs,
        // exact CPU/memory/display contract, and a new isolated session path.
        var args = try original.arguments(assets: probeAssets, session: session)
        guard let initrd = args.firstIndex(of: "-initrd"), initrd + 1 < args.count,
              let append = args.firstIndex(of: "-append"), append + 1 < args.count,
              let chardev = args.firstIndex(of: "-chardev"), chardev + 1 < args.count,
              let serial = args.firstIndex(of: "-serial"), serial + 1 < args.count else { throw Invalid.configuration }
        func optionPath(_ url: URL) throws -> String {
            guard url.isFileURL, !url.path.contains("\0"), !url.path.contains("\n"), !url.path.contains("\r") else { throw Invalid.configuration }
            return url.path.replacingOccurrences(of: ",", with: ",,")
        }
        args[initrd + 1] = ramdisk.path
        args[append + 1] = "console=ttyAMA0 loglevel=6 rdinit=/ideck-terminal-init fbcon=nodefer vt.global_cursor_default=0"
        args[chardev + 1] = "socket,id=linuxterm,fd=\(serialFD),server=off"
        args[serial + 1] = "chardev:linuxterm"
        args += ["-chardev", "socket,id=linuxcontrol,fd=\(controlFD),server=off",
                 "-device", "virtio-serial-pci", "-device", "virtserialport,chardev=linuxcontrol,name=org.ideck.control",
                 "-drive", "if=none,id=userdata,format=raw,cache=writethrough,file.locking=off,file=\(try optionPath(diskURL))",
                 "-device", "virtio-blk-pci,drive=userdata"]
        return args
    }
}

/// Owns the whole-file exclusive flock on userdata itself. Darwin flock and
/// OFD byte locks conflict across separate opens, so this profile alone uses
/// file.locking=off for QEMU's duplicate lock. All app writers acquire this lock.
/// The runtime worker retains it until process exit, including after an orderly
/// guest stop. QEMU's block-layer drain is not established by main-loop return.
final class LinuxTerminalDisk {
    let url: URL
    private var fd: Int32
    private init(url: URL, fd: Int32) { self.url = url; self.fd = fd }
    deinit { if fd >= 0 { Darwin.close(fd) } }

    /// Resolve only an existing system-provided Documents/temporary prefix,
    /// before appending app-owned/untrusted children. Foundation URL path
    /// standardization may shorten /private aliases, so use POSIX realpath.
    static func trustedDirectory(_ existing: URL) throws -> URL {
        guard existing.isFileURL, let resolved = realpath(existing.path, nil) else {
            throw LinuxTerminalProfile.Invalid.diskTrustedDirectory
        }
        defer { free(resolved) }
        let resolvedPath = String(cString: resolved)
        let directory = URL(fileURLWithPath: resolvedPath, isDirectory: true)
        guard directory.path == resolvedPath else { throw LinuxTerminalProfile.Invalid.diskTrustedDirectory }
        try validateDirectory(directory, allowingMissing: false)
        return directory
    }

    static func open(directory: URL, seed: URL, size: Int = LinuxTerminalProfile.diskSize) throws -> LinuxTerminalDisk {
        guard size == LinuxTerminalProfile.diskSize else { throw LinuxTerminalProfile.Invalid.diskSize }
        let manager = FileManager.default
        try validateDirectory(directory, allowingMissing: true)
        if !manager.fileExists(atPath: directory.path) {
            try manager.createDirectory(at: directory, withIntermediateDirectories: true)
        }
        try validateDirectory(directory, allowingMissing: false)
        let url = directory.appendingPathComponent("userdata.raw")
        var state = stat()
        if lstat(url.path, &state) != 0 {
            guard errno == ENOENT else { throw LinuxTerminalProfile.Invalid.diskInspection }
            try provision(seed: seed, destination: url, size: size)
        }
        let fd = Darwin.open(url.path, O_RDWR | O_NOFOLLOW)
        guard fd >= 0 else { throw LinuxTerminalProfile.Invalid.diskOpen }
        var accepted = false
        defer { if !accepted { Darwin.close(fd) } }
        guard flock(fd, LOCK_EX | LOCK_NB) == 0 else { throw LinuxTerminalProfile.Invalid.diskLocked }
        guard fstat(fd, &state) == 0 else { throw LinuxTerminalProfile.Invalid.diskMetadata }
        guard state.st_nlink == 1 else { throw LinuxTerminalProfile.Invalid.diskLinks }
        try validateFormat(fd: fd, size: size)
        accepted = true
        return LinuxTerminalDisk(url: url, fd: fd)
    }

    private static func validateFormat(fd: Int32, size: Int) throws {
        var state = stat()
        guard fstat(fd, &state) == 0, (state.st_mode & S_IFMT) == S_IFREG else { throw LinuxTerminalProfile.Invalid.diskMetadata }
        guard state.st_size == off_t(size) else { throw LinuxTerminalProfile.Invalid.diskSize }
        var boot = [UInt8](repeating: 0, count: 512)
        guard pread(fd, &boot, 512, 0) == 512 else { throw LinuxTerminalProfile.Invalid.diskHeaderRead }
        func le16(_ offset: Int) -> Int { Int(boot[offset]) | Int(boot[offset + 1]) << 8 }
        func le32(_ offset: Int) -> Int { le16(offset) | le16(offset + 2) << 16 }
        let sectors = le16(19) == 0 ? le32(32) : le16(19)
        guard boot[510] == 0x55, boot[511] == 0xaa, le16(11) == 512,
              sectors * 512 == size, String(bytes: boot[54..<62], encoding: .ascii) == "FAT16   " else {
            throw LinuxTerminalProfile.Invalid.diskFormat
        }
    }

    static func validateDirectory(_ directory: URL, allowingMissing: Bool) throws {
        guard directory.isFileURL, directory.baseURL == nil, directory.query == nil, directory.fragment == nil,
              directory.host == nil || directory.host == "" || directory.host == "localhost",
              let rawPath = URLComponents(url: directory, resolvingAgainstBaseURL: false)?.path,
              rawPath.hasPrefix("/"), directory.path.hasPrefix("/") else {
            throw LinuxTerminalProfile.Invalid.diskDirectoryURL
        }
        let path = directory.path
        let components = path.split(separator: "/", omittingEmptySubsequences: true)
        let rawComponents = rawPath.split(separator: "/", omittingEmptySubsequences: true)
        guard !rawPath.contains("\0"), !path.contains("\0"),
              !rawComponents.contains("."), !rawComponents.contains(".."),
              !components.contains("."), !components.contains("..") else {
            throw LinuxTerminalProfile.Invalid.diskDirectoryComponent
        }
        // Inspect each ORIGINAL pathname prefix. Do not standardize or resolve
        // this caller-supplied path: doing so could hide a symlink ancestor.
        var current = ""
        for component in components {
            current += "/" + String(component)
            var state = stat()
            if lstat(current, &state) == 0 {
                guard (state.st_mode & S_IFMT) == S_IFDIR else { throw LinuxTerminalProfile.Invalid.diskDirectoryType }
            } else {
                guard allowingMissing, errno == ENOENT else { throw LinuxTerminalProfile.Invalid.diskDirectoryInspection }
            }
        }
    }

    private static func provision(seed: URL, destination: URL, size: Int) throws {
        let temporary = destination.deletingLastPathComponent().appendingPathComponent(".userdata-\(UUID().uuidString).tmp")
        let fd = Darwin.open(temporary.path, O_RDWR | O_CREAT | O_EXCL | O_NOFOLLOW, mode_t(0o600))
        guard fd >= 0 else { throw LinuxTerminalProfile.Invalid.io }
        defer { Darwin.close(fd); try? FileManager.default.removeItem(at: temporary) }
        let source = try FileHandle(forReadingFrom: seed)
        defer { try? source.close() }
        var count = 0
        while let bytes = try source.read(upToCount: 1024 * 1024), !bytes.isEmpty {
            count += bytes.count
            guard count <= size else { throw LinuxTerminalProfile.Invalid.diskSeedSize }
            try bytes.withUnsafeBytes { buffer in
                var offset = 0
                while offset < buffer.count {
                    let sent = Darwin.write(fd, buffer.baseAddress!.advanced(by: offset), buffer.count - offset)
                    if sent < 0, errno == EINTR { continue }
                    guard sent > 0 else { throw LinuxTerminalProfile.Invalid.io }
                    offset += sent
                }
            }
        }
        guard count == size else { throw LinuxTerminalProfile.Invalid.diskSeedSize }
        guard fsync(fd) == 0 else { throw LinuxTerminalProfile.Invalid.io }
        try validateFormat(fd: fd, size: size)
        // link is an atomic, same-directory, no-clobber publish. A racing first
        // creator may win; its existing disk is validated and locked below.
        if link(temporary.path, destination.path) != 0, errno != EEXIST { throw LinuxTerminalProfile.Invalid.io }
    }

    /// Fail closed if the owner was closed, the pathname was replaced/unlinked,
    /// a hard link appeared or the directory contract changed. This never
    /// releases the host lock and never repairs/reseeds an existing disk.
    func validateOwnership() throws {
        guard fd >= 0 else { throw LinuxTerminalProfile.Invalid.diskOwnership }
        try Self.validateDirectory(url.deletingLastPathComponent(), allowingMissing: false)
        var opened = stat()
        var named = stat()
        guard flock(fd, LOCK_EX | LOCK_NB) == 0,
              fstat(fd, &opened) == 0, lstat(url.path, &named) == 0,
              (opened.st_mode & S_IFMT) == S_IFREG, (named.st_mode & S_IFMT) == S_IFREG,
              opened.st_dev == named.st_dev, opened.st_ino == named.st_ino,
              opened.st_nlink == 1, named.st_nlink == 1,
              opened.st_size == off_t(LinuxTerminalProfile.diskSize),
              named.st_size == opened.st_size else { throw LinuxTerminalProfile.Invalid.diskOwnership }
    }

    func synchronize() throws {
        guard fd >= 0, fsync(fd) == 0 else { throw LinuxTerminalProfile.Invalid.io }
    }

    /// For helpers/tests that never handed this disk to QEMU. The runtime uses
    /// synchronize() and retains its descriptor/lock until the app process exits.
    func synchronizeAndClose() throws {
        try synchronize()
        let descriptor = fd
        fd = -1
        guard Darwin.close(descriptor) == 0 else { throw LinuxTerminalProfile.Invalid.io }
    }

    func closeUnused() {
        if fd >= 0 { Darwin.close(fd); fd = -1 }
    }
}
