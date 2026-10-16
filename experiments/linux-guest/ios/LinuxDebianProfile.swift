import Foundation
import CryptoKit
import Darwin

/// Debian boot contract; persistent ext4 geometry/import stays in DesktopProfile.
struct LinuxDebianProfile: Decodable {
    let schema: Int
    let mode: String
    let controlPort: String
    let kernel: LinuxTerminalProfile.Asset
    let initramfs: LinuxTerminalProfile.Asset

    static func load(from assets: URL) throws -> LinuxDebianProfile {
        let profileURL = assets.appendingPathComponent("debian-profile.json")
        let decoder = JSONDecoder(); decoder.keyDecodingStrategy = .convertFromSnakeCase
        let data = try read(profileURL, maximum: 65536)
        let value = try decoder.decode(Self.self, from: data)
        guard value.schema == 1, value.mode == "debian", value.controlPort == "org.ideck.control",
              value.kernel.file == "vmlinuz-virt", value.initramfs.file == "initramfs-debian.gz" else {
            throw LinuxTerminalProfile.Invalid.configuration
        }
        return value
    }

    private static func read(_ url: URL, maximum: Int64) throws -> Data {
        let parent = url.deletingLastPathComponent()
        let canonical = try LinuxDesktopDisk.trustedDirectory(parent)
        // Resolve the trusted bundle prefix (iOS /var may be an OS alias),
        // then open only the fixed leaf without following a leaf symlink.
        try LinuxDesktopDisk.validateDirectory(canonical)
        let leaf = canonical.appendingPathComponent(url.lastPathComponent)
        let fd = Darwin.open(leaf.path, O_RDONLY | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC)
        guard fd >= 0 else { throw LinuxTerminalProfile.Invalid.assetRead }
        let handle = FileHandle(fileDescriptor: fd, closeOnDealloc: true)
        defer { try? handle.close() }
        var state = stat()
        guard fstat(fd, &state) == 0, state.st_mode & S_IFMT == S_IFREG,
              state.st_nlink == 1, state.st_size > 0, state.st_size <= maximum else {
            throw LinuxTerminalProfile.Invalid.assetType
        }
        guard let data = try handle.readToEnd(), data.count == Int(state.st_size) else {
            throw LinuxTerminalProfile.Invalid.assetRead
        }
        return data
    }

    private func asset(_ descriptor: LinuxTerminalProfile.Asset, in root: URL) throws -> URL {
        let url = root.appendingPathComponent(descriptor.file)
        let data = try Self.read(url, maximum: 128 * 1024 * 1024)
        guard descriptor.size == data.count else { throw LinuxTerminalProfile.Invalid.assetSize }
        guard SHA256.hash(data: data).map({ String(format: "%02x", $0) }).joined() == descriptor.sha256 else {
            throw LinuxTerminalProfile.Invalid.assetDigest
        }
        return url
    }

    func arguments(probeAssets: URL, assets: URL, session: URL, disk: LinuxDesktopDisk,
                   serialFD: Int32, controlFD: Int32) throws -> [String] {
        guard serialFD >= 0, controlFD >= 0, serialFD != controlFD else { throw LinuxTerminalProfile.Invalid.io }
        try disk.validateOwnership()
        let original = try LinuxGuestProfile.load(from: probeAssets)
        guard kernel.sha256 == original.kernel.sha256, kernel.size == original.kernel.size else {
            throw LinuxTerminalProfile.Invalid.configuration
        }
        let kernelURL = try asset(kernel, in: assets)
        let initrdURL = try asset(initramfs, in: assets)
        var args = try original.arguments(assets: probeAssets, session: session)
        for (option, value) in [("-kernel", kernelURL.path), ("-initrd", initrdURL.path)] {
            guard let index = args.firstIndex(of: option), index + 1 < args.count else { throw LinuxTerminalProfile.Invalid.configuration }
            args[index + 1] = value
        }
        guard let append = args.firstIndex(of: "-append"), let serial = args.firstIndex(of: "-chardev") else {
            throw LinuxTerminalProfile.Invalid.configuration
        }
        args[append + 1] = "console=ttyAMA0 earlycon=pl011,0x09000000 rdinit=/ideck-debian-init panic=0 loglevel=6"
        args[serial + 1] = "socket,id=linuxserial,fd=\(serialFD)"
        let path = disk.url.path.replacingOccurrences(of: ",", with: ",,")
        args += ["-chardev", "socket,id=control0,fd=\(controlFD)", "-device", "virtio-serial-pci",
                 "-device", "virtserialport,chardev=control0,name=\(controlPort)",
                 "-drive", "if=none,id=debian,format=raw,cache=writethrough,file.locking=off,file=\(path)",
                 "-device", "virtio-blk-device,drive=debian"]
        return args
    }
}
