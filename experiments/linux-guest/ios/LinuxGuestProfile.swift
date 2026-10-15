import Foundation
import CryptoKit

/// The first direct-Linux experiment only. Construct this off the UI thread.
/// This does not grant JIT, load QEMU, provide Metal rendering or start Steam.
struct LinuxGuestProfile: Decodable {
    struct Asset: Decodable {
        let file: String
        let sha256: String
        let size: Int
    }
    enum Invalid: Error { case configuration, asset, unsafePath, sessionAlreadyExists }
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
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return try decoder.decode(Self.self, from: Data(contentsOf: directory.appendingPathComponent("profile.json")))
    }

    private func checkedAsset(_ asset: Asset, named name: String, in directory: URL) throws -> URL {
        guard asset.file == name, asset.size > 0, asset.size <= 64 * 1024 * 1024,
              asset.sha256.count == 64,
              asset.sha256.allSatisfy({ "0123456789abcdef".contains($0) }) else { throw Invalid.asset }
        let root = directory.standardizedFileURL.resolvingSymlinksInPath()
        let url = root.appendingPathComponent(name).resolvingSymlinksInPath()
        guard url.deletingLastPathComponent() == root else { throw Invalid.unsafePath }
        let data = try Data(contentsOf: url, options: .mappedIfSafe)
        let hash = SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
        guard data.count == asset.size, hash == asset.sha256 else { throw Invalid.asset }
        return url
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
