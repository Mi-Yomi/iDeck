import Foundation
import CryptoKit
import Darwin

func recoveryUnitSpecification() -> LinuxDesktopDisk.Specification {
    .init(sizeBytes: LinuxGUIProfile.size, uuid: LinuxGUIProfile.uuid, blockSize: 4096,
          features: .init(compat: 44, incompat: 194, roCompat: 1091))
}

func runRecoveryPromotionChild(directory: URL, interruption: String) throws -> Never {
    let promoted = try LinuxGUIRecovery.promotePending(directory: directory, specification: recoveryUnitSpecification(),
        toolSeedSHA256: String(repeating: "a", count: 64), fault: { phase in
            if phase == interruption { _exit(phase == "before_rename" ? 85 : 86) }
        })
    precondition(promoted); _exit(0)
}

/// Actual bounded IO/locking/atomic-rename checks with sparse synthetic bodies.
/// Setting a golden unit header clean below is NOT a filesystem repair or VM gate.
/// Real fsck/GUI recovery is separately exercised by check_gui_recovery.py.
func runGUIRecoveryChecks(root: URL, fixture: URL) throws {
    func check(_ condition: Bool, _ message: String = "recovery IO check") { precondition(condition, message) }
    let manager = FileManager.default
    let directory = root.appendingPathComponent("gui-recovery-unit-" + UUID().uuidString)
    try manager.createDirectory(at: directory, withIntermediateDirectories: true)
    defer { try? manager.removeItem(at: directory) }
    let spec = recoveryUnitSpecification()
    var header = try DesktopGolden.load(fixture).header
    func u32(_ n: Int) -> UInt32 { UInt32(header[n]) | UInt32(header[n+1]) << 8 | UInt32(header[n+2]) << 16 | UInt32(header[n+3]) << 24 }
    func set32(_ n: Int, _ value: UInt32) { for i in 0..<4 { header[n+i] = UInt8((value >> (i*8)) & 255) } }
    let hex = Array(spec.uuid.replacingOccurrences(of: "-", with: "").utf8)
    for i in 0..<16 { header[0x68+i] = UInt8(String(decoding: hex[i*2..<i*2+2], as: UTF8.self), radix: 16)! }
    let blocks = UInt32(spec.sizeBytes / 4096)
    set32(4, blocks); set32(0x150, 0); set32(0, ((blocks+32767)/32768) * u32(0x28))
    set32(0x60, 198); set32(1020, LinuxDesktopDisk.crc32c(header[0..<1020]))
    let original = directory.appendingPathComponent("rootfs-v1.raw")
    let fd = Darwin.open(original.path, O_RDWR | O_CREAT | O_EXCL, 0o600)
    precondition(fd >= 0)
    let handle = FileHandle(fileDescriptor: fd, closeOnDealloc: true)
    try handle.truncate(atOffset: UInt64(spec.sizeBytes)); try handle.seek(toOffset: 1024)
    try handle.write(contentsOf: Data(header)); try handle.seek(toOffset: 2 * 1024 * 1024)
    try handle.write(contentsOf: Data("SYNTHETIC_RECOVERY_UNIT_CANARY".utf8)); try handle.synchronize(); try handle.close()
    do { _ = try LinuxGUIRecovery.prepare(directory: directory, specification: spec, availableBytes: { _ in 0 }); preconditionFailure("low-space accepted") }
    catch LinuxGUIRecovery.Invalid.space { }
    // Receipt is genuinely in copying phase. Exercise partial backup/work bytes
    // as an interrupted producer would leave them; the source is never changed.
    let stateURL = directory.appendingPathComponent(".recovery-v1/current.json")
    let partialState = try JSONDecoder().decode(LinuxGUIRecovery.Receipt.self, from: Data(contentsOf: stateURL))
    for leaf in ["original.raw", "work.raw"] {
        let file = directory.appendingPathComponent(".recovery-v1/" + partialState.id + "/" + leaf)
        try Data(repeating: 0x71, count: 137).write(to: file)
    }
    var transaction: LinuxGUIRecovery? = try LinuxGUIRecovery.prepare(directory: directory, specification: spec)
    let backup = directory.appendingPathComponent(".recovery-v1/" + transaction!.receipt!.id + "/original.raw")
    func readHeader(_ path: URL) throws -> Data {
        let file = try FileHandle(forReadingFrom: path); defer { try? file.close() }
        try file.seek(toOffset: 1024); return try file.read(upToCount: 1024) ?? Data()
    }
    check(try readHeader(original) == Data(header))
    check(try readHeader(backup) == Data(header))
    try transaction!.markRunning(toolSeedSHA256: String(repeating: "a", count: 64))
    do {
        try transaction!.recordResult(assessment: 0, replay: 0, verification: 0, scanClean: false)
        preconditionFailure("exit0 without clean output accepted")
    } catch LinuxGUIRecovery.Invalid.manualReview { }
    let workURL = transaction!.url
    let writer = try FileHandle(forWritingTo: workURL)
    set32(0x60, 194); set32(1020, LinuxDesktopDisk.crc32c(header[0..<1020]))
    try writer.seek(toOffset: 1024); try writer.write(contentsOf: Data(header)); try writer.synchronize(); try writer.close()
    try transaction!.recordResult(assessment: 0, replay: 0, verification: 0, scanClean: true)
    do {
        _ = try LinuxGUIRecovery.promotePending(directory: directory, specification: spec, toolSeedSHA256: String(repeating: "a", count: 64))
        preconditionFailure("same-process or owned disk promotion accepted")
    } catch LinuxGUIRecovery.Invalid.busy { } catch LinuxGUIRecovery.Invalid.relaunch { }
    // No native VM was entered in this unit fixture. Real workers never close
    // after entry; the retained owner holds these descriptors through app exit.
    transaction!.closeUnused(); transaction = nil
    for (interruption, expected) in [("before_rename", Int32(85)), ("after_rename", Int32(86)), ("none", Int32(0))] {
        let child = Process(), finished = DispatchSemaphore(value: 0)
        child.executableURL = URL(fileURLWithPath: CommandLine.arguments[0])
        child.arguments = ["--gui-recovery-promote", directory.path, interruption]
        child.terminationHandler = { _ in finished.signal() }; try child.run()
        if finished.wait(timeout: .now()+60) == .timedOut { child.terminate(); preconditionFailure("promotion child timed out") }
        precondition(child.terminationStatus == expected)
    }
    let opened = try LinuxDesktopDisk.openExisting(directory: directory, specification: spec)
    try opened.validateOwnership()
    // Execute the real normal argv path, including creating its fresh session
    // BEFORE appending the suffix. Tiny kernel/initrd bytes are only unit data.
    let assets = directory.appendingPathComponent("argv-assets")
    try manager.createDirectory(at: assets, withIntermediateDirectories: true)
    let bytes = Data("GUI runtime argv unit".utf8)
    let sum = SHA256.hash(data: bytes).map { String(format: "%02x", $0) }.joined()
    for name in ["vmlinuz-virt", "initramfs-ideck.gz", "initramfs-desktop.gz"] { try bytes.write(to: assets.appendingPathComponent(name)) }
    func asset(_ name: String) -> [String: Any] { ["file": name, "size": bytes.count, "sha256": sum] }
    let probe: [String: Any] = ["schema": 1, "width": 800, "height": 600, "cpu": "cortex-a72",
        "memory_mib": 1024, "vcpus": 4, "tcg_cache_mib": 256, "kernel": asset("vmlinuz-virt"), "initramfs": asset("initramfs-ideck.gz")]
    try JSONSerialization.data(withJSONObject: probe).write(to: assets.appendingPathComponent("profile.json"))
    let profile = LinuxGUIProfile(schema: 1, mode: "desktop", controlPort: "org.ideck.control",
        kernel: .init(file: "vmlinuz-virt", size: Int64(bytes.count), sha256: sum),
        initramfs: .init(file: "initramfs-desktop.gz", size: Int64(bytes.count), sha256: sum),
        rootfs: .init(file: "gui-rootfs-v1.raw", size: spec.sizeBytes, sha256: String(repeating: "a", count: 64)), image: spec)
    let boot = directory.appendingPathComponent("argv-session")
    let args = try profile.arguments(probeAssets: assets, assets: assets, session: boot, disk: opened, serialFD: 40, controlFD: 41)
    precondition(args.contains(boot.appendingPathComponent("desktop-runtime-initramfs").path))
    let combined = try Data(contentsOf: boot.appendingPathComponent("desktop-runtime-initramfs"))
    precondition(combined.prefix(bytes.count) == bytes && combined.suffix(LinuxRecoveryGuest.suffix.count) == LinuxRecoveryGuest.suffix)
    do {
        try LinuxRecoveryGuest.append(to: assets.appendingPathComponent("initramfs-desktop.gz"), expectedSHA256: sum,
                                      expectedSize: Int64(bytes.count), output: boot.appendingPathComponent("desktop-runtime-initramfs"))
        preconditionFailure("existing runtime initramfs overwritten")
    } catch LinuxDesktopDisk.Invalid.io { }
    check(try Data(contentsOf: boot.appendingPathComponent("desktop-runtime-initramfs")) == combined)
    opened.closeUnused()
    check(try readHeader(original) == Data(header))
    check(try readHeader(backup) != Data(header), "original snapshot was overwritten")
    let reader = try FileHandle(forReadingFrom: original); try reader.seek(toOffset: 2 * 1024 * 1024)
    let marker = try reader.read(upToCount: Data("SYNTHETIC_RECOVERY_UNIT_CANARY".utf8).count); try reader.close()
    precondition(marker == Data("SYNTHETIC_RECOVERY_UNIT_CANARY".utf8))

    var progress = LinuxRecoveryProgress()
    for line in ["IDECK_RECOVERY_ASSESS:4", "IDECK_RECOVERY_REPLAY:1", "IDECK_RECOVERY_VERIFY:0", "IDECK_RECOVERY_SCAN_CLEAN", "IDECK_RECOVERY_DONE"] { try progress.observe(line) }
    precondition(progress.done)
    var scoped = LinuxRecoveryProgress()
    for line in ["IDECK_RECOVERY_ASSESS:0", "IDECK_RECOVERY_REPLAY:0", "IDECK_RECOVERY_SUMMARY_ELIGIBLE"] { try scoped.observe(line) }
    do { try scoped.observe("IDECK_RECOVERY_VERIFY:0"); preconditionFailure("unfinished scope accepted") }
    catch { }
    try scoped.observe("IDECK_RECOVERY_SUMMARY_RECONCILED")
    for line in ["IDECK_RECOVERY_VERIFY:0", "IDECK_RECOVERY_SCAN_CLEAN", "IDECK_RECOVERY_DONE"] { try scoped.observe(line) }
    precondition(scoped.done && scoped.summaryReconciled)
    var legacyProgress = LinuxRecoveryProgress()
    for line in ["IDECK_RECOVERY_ASSESS:0", "IDECK_RECOVERY_REPLAY:0", "IDECK_RECOVERY_VERIFY:0"] { try legacyProgress.observe(line) }
    do { try legacyProgress.observe("IDECK_RECOVERY_DONE"); preconditionFailure("legacy receipt without SCAN_CLEAN accepted") }
    catch { }
    precondition(!legacyProgress.done)
    for line in ["IDECK_RECOVERY_DONE", "IDECK_RECOVERY_REPLAY:0", "IDECK_RECOVERY_ASSESS:8", "IDECK_RECOVERY_FAILED:manual_review"] {
        var invalid = LinuxRecoveryProgress()
        do { try invalid.observe(line); preconditionFailure("invalid recovery receipt accepted") } catch { }
    }
    let digest = SHA256.hash(data: LinuxRecoveryGuest.suffix).map { String(format: "%02x", $0) }.joined()
    precondition(digest == LinuxRecoveryGuest.sha256 && LinuxRecoveryGuest.suffix.count < 32768)
    print("LINUX_GUI_RECOVERY_PASS (actual IO/process locks/interrupted rename; synthetic bodies, no native teardown)")
}
