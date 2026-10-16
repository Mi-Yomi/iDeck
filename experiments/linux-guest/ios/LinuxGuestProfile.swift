import Foundation
import CryptoKit
import Darwin

/// Bundle roots may use Apple's system aliases or either URL directory hint.
/// Compare POSIX canonical filenames, never URL object identity/trailing slashes.
enum LinuxGuestAssetPath {
    static func canonical(_ url: URL) -> String? {
        guard url.isFileURL, !url.path.contains("\0"),
              let resolved = realpath(url.path, nil) else { return nil }
        defer { free(resolved) }
        return String(cString: resolved)
    }

    static func directory(_ url: URL) -> URL? {
        guard let path = canonical(url) else { return nil }
        var state = stat()
        guard lstat(path, &state) == 0, (state.st_mode & S_IFMT) == S_IFDIR else { return nil }
        return URL(fileURLWithPath: path, isDirectory: true)
    }
}

/// The first direct-Linux experiment only. Construct this off the UI thread.
/// This does not grant JIT, load QEMU, provide Metal rendering or start Steam.
struct LinuxGuestProfile: Decodable {
    struct Asset: Decodable {
        let file: String
        let sha256: String
        let size: Int
    }
    enum Invalid: Error, Equatable {
        case configuration, asset, unsafePath, sessionAlreadyExists
        case assetDescriptor, assetDirectory, assetInspection, assetType, assetSize
        case assetContainment, assetRead, assetContentSize, assetDigest
    }
    let schema: Int
    let width: Int
    let height: Int
    let cpu: String
    let memoryMib: Int
    let vcpus: Int
    let tcgCacheMib: Int
    let kernel: Asset
    let initramfs: Asset

    static func load(from directory: URL) throws -> LinuxGuestProfile {
        guard let root = LinuxGuestAssetPath.directory(directory) else { throw Invalid.assetDirectory }
        let file = root.appendingPathComponent("profile.json")
        let values = try file.resourceValues(forKeys: [.isRegularFileKey, .isSymbolicLinkKey, .fileSizeKey])
        guard values.isRegularFile == true, values.isSymbolicLink != true,
              let size = values.fileSize, size > 0, size <= 65536 else { throw Invalid.asset }
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return try decoder.decode(Self.self, from: Data(contentsOf: file))
    }

    private func checkedAsset(_ asset: Asset, named name: String, in directory: URL) throws -> URL {
        guard asset.file == name, asset.size > 0, asset.size <= 64 * 1024 * 1024,
              asset.sha256.count == 64,
              asset.sha256.allSatisfy({ "0123456789abcdef".contains($0) }) else { throw Invalid.assetDescriptor }
        guard let root = LinuxGuestAssetPath.directory(directory) else { throw Invalid.assetDirectory }
        let candidate = root.appendingPathComponent(name)
        let values: URLResourceValues
        do { values = try candidate.resourceValues(forKeys: [.isRegularFileKey, .isSymbolicLinkKey, .fileSizeKey]) }
        catch { throw Invalid.assetInspection }
        guard values.isRegularFile == true, values.isSymbolicLink != true else { throw Invalid.assetType }
        guard values.fileSize == asset.size else { throw Invalid.assetSize }
        // The exact allowed basename was checked above. realpath must leave
        // this canonical root + leaf unchanged; a link/escape is never accepted.
        guard LinuxGuestAssetPath.canonical(candidate) == candidate.path else { throw Invalid.assetContainment }
        let data: Data
        do { data = try Data(contentsOf: candidate, options: .mappedIfSafe) }
        catch { throw Invalid.assetRead }
        let hash = SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
        guard data.count == asset.size else { throw Invalid.assetContentSize }
        guard hash == asset.sha256 else { throw Invalid.assetDigest }
        return candidate
    }

    /// Creates an argv array for in-process qemu_init. A native session owner
    /// must first pass its existing JIT self-test, retain argv for QEMU's lifetime,
    /// and use the software Husk display/input bridge after qemu_init returns.
    /// Never send this profile through Android snapshot/GL/autosave handling.
    func arguments(assets: URL, session: URL) throws -> [String] {
        guard schema == 1, width == 800, height == 600, cpu == "cortex-a72",
              memoryMib == 1024, vcpus == 4, tcgCacheMib == 256 else { throw Invalid.configuration }
        let image = try checkedAsset(kernel, named: "vmlinuz-virt", in: assets)
        let ramdisk = try checkedAsset(initramfs, named: "initramfs-ideck.gz", in: assets)
        let sessionPath = session.standardizedFileURL.resolvingSymlinksInPath()
        // Each probe uses a new directory; it cannot reuse Android's disk/logs.
        guard !FileManager.default.fileExists(atPath: sessionPath.path) else { throw Invalid.sessionAlreadyExists }
        for path in [image.path, ramdisk.path, sessionPath.path] {
            guard !path.contains("\0"), !path.contains("\n"), !path.contains("\r") else { throw Invalid.unsafePath }
        }
        try FileManager.default.createDirectory(at: sessionPath, withIntermediateDirectories: true)
        let serial = sessionPath.appendingPathComponent("linux-serial.log").path
            .replacingOccurrences(of: ",", with: ",,")
        return ["qemu-system-aarch64", "-M", "virt", "-cpu", cpu,
                "-smp", String(vcpus), "-m", String(memoryMib),
                "-accel", "tcg,thread=multi,tb-size=256,split-wx=on",
                "-kernel", image.path, "-initrd", ramdisk.path,
                "-append", "console=ttyAMA0 loglevel=6 rdinit=/ideck-init fbcon=nodefer vt.global_cursor_default=0",
                "-nic", "none", "-device", "virtio-gpu-pci,xres=800,yres=600",
                "-device", "virtio-tablet-pci", "-device", "virtio-keyboard-pci",
                "-chardev", "file,id=linuxserial,path=\(serial)", "-serial", "chardev:linuxserial",
                "-display", "none", "-monitor", "none", "-no-reboot"]
    }
}
