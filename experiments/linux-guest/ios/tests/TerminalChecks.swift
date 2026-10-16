import Foundation
import CryptoKit

/// Actual Foundation/Darwin helper checks. Synthetic sparse FAT headers and
/// kernel bytes validate host file handling; they do not execute a Linux guest.
func runTerminalChecks() throws {
    let manager = FileManager.default
    let trustedTemporary = try LinuxTerminalDisk.trustedDirectory(manager.temporaryDirectory)
    let root = trustedTemporary
        .appendingPathComponent("ideck-terminal-checks-\(UUID().uuidString)")
    try manager.createDirectory(at: root, withIntermediateDirectories: true)
    defer { try? manager.removeItem(at: root) }

    func check(_ condition: Bool, _ message: String = "assertion failed") {
        precondition(condition, "Linux terminal host check: " + message)
    }
    func checkpoint(_ label: String) {
        // stderr is written directly, so a later uncaught throw still leaves
        // the last reached substep in a captured Apple host-test log.
        FileHandle.standardError.write(Data("LINUX_TERMINAL_CHECKPOINT \(label)\n".utf8))
    }
    func fileSize(_ url: URL) throws -> Int {
        guard let count = try manager.attributesOfItem(atPath: url.path)[.size] as? NSNumber else {
            preconditionFailure("Linux terminal host check: missing fixture file size")
        }
        return count.intValue
    }
    func expectFailure(_ body: () throws -> Void) {
        do { try body(); fatalError("unsafe terminal input accepted") } catch { }
    }
    func expectTerminalFailure(_ expected: LinuxTerminalProfile.Invalid, _ body: () throws -> Void) {
        do { try body(); preconditionFailure("unsafe terminal asset accepted") }
        catch let error as LinuxTerminalProfile.Invalid { check(error == expected, "expected \(expected), received \(error)") }
        catch { preconditionFailure("unexpected terminal asset error type") }
    }
    func expectProbeFailure(_ expected: LinuxGuestProfile.Invalid, _ body: () throws -> Void) {
        do { try body(); preconditionFailure("unsafe probe asset accepted") }
        catch let error as LinuxGuestProfile.Invalid { check(error == expected, "expected \(expected), received \(error)") }
        catch { preconditionFailure("unexpected probe asset error type") }
    }
    func bootSector() -> Data {
        var boot = Data(repeating: 0, count: 512)
        boot[11] = 0; boot[12] = 2 // 512-byte sectors
        boot[13] = 8; boot[14] = 1; boot[16] = 2
        boot[17] = 0; boot[18] = 2 // 512 root entries
        boot[21] = 0xf8; boot[22] = 128
        boot[32] = 0; boot[33] = 0; boot[34] = 4 // 262144 sectors
        boot.replaceSubrange(54..<62, with: Data("FAT16   ".utf8))
        boot[510] = 0x55; boot[511] = 0xaa
        return boot
    }
    func makeSeed(_ url: URL) throws {
        check(manager.createFile(atPath: url.path, contents: nil), "create synthetic seed")
        let file = try FileHandle(forWritingTo: url)
        defer { try? file.close() }
        check(try file.offset() == 0, "new seed handle starts at zero")
        check(try fileSize(url) == 0, "new seed is empty")
        try file.truncate(atOffset: UInt64(LinuxTerminalProfile.diskSize))
        check(try file.offset() == UInt64(LinuxTerminalProfile.diskSize), "truncate moves the file pointer to EOF")
        check(try fileSize(url) == LinuxTerminalProfile.diskSize, "truncate creates exactly 128 MiB")
        // FileHandle.truncate moves the pointer; reset it before writing BPB.
        // Without this seek the fixture grows by 512 bytes and sector zero is
        // empty, which the production size/format guards correctly reject.
        try file.seek(toOffset: 0)
        check(try file.offset() == 0, "explicit seek positions the BPB at sector zero")
        let boot = bootSector()
        try file.write(contentsOf: boot)
        check(try file.offset() == 512, "boot write ends at byte 512")
        try file.synchronize()
        check(try fileSize(url) == LinuxTerminalProfile.diskSize, "boot write must not grow the seed")
        let reader = try FileHandle(forReadingFrom: url)
        defer { try? reader.close() }
        check(try reader.read(upToCount: 512) == boot, "sector zero contains the complete expected BPB and signature")
        try reader.seek(toOffset: UInt64(LinuxTerminalProfile.diskSize - 1))
        check(try reader.read(upToCount: 2) == Data([0]), "last sparse byte is zero and no appended sector exists")
    }
    func byte(_ url: URL, at offset: UInt64) throws -> Data {
        let file = try FileHandle(forReadingFrom: url)
        defer { try? file.close() }
        try file.seek(toOffset: offset)
        return try file.read(upToCount: 1) ?? Data()
    }
    func asset(_ url: URL) throws -> [String: Any] {
        let file = try FileHandle(forReadingFrom: url)
        defer { try? file.close() }
        var hash = SHA256()
        var count = 0
        while let data = try file.read(upToCount: 1024 * 1024), !data.isEmpty {
            hash.update(data: data); count += data.count
        }
        return ["file": url.lastPathComponent, "size": count,
                "sha256": hash.finalize().map { String(format: "%02x", $0) }.joined()]
    }

    checkpoint("trusted-directory-positive")
    try LinuxTerminalDisk.validateDirectory(trustedTemporary, allowingMissing: false)
    try LinuxTerminalDisk.validateDirectory(root, allowingMissing: false)
    // Exercise the actual Darwin system alias independently of CI's TMPDIR,
    // which may point inside the checkout rather than under /var.
    let rawVar = URL(fileURLWithPath: "/var", isDirectory: true)
    let trustedVar = try LinuxTerminalDisk.trustedDirectory(rawVar)
    try LinuxTerminalDisk.validateDirectory(trustedVar, allowingMissing: false)
    if (try? manager.destinationOfSymbolicLink(atPath: rawVar.path)) != nil {
        do {
            try LinuxTerminalDisk.validateDirectory(rawVar, allowingMissing: false)
            preconditionFailure("Linux terminal host check: original system symlink alias was accepted")
        } catch LinuxTerminalProfile.Invalid.diskDirectoryType { }
    }
    checkpoint("directory-lexical-rejections")
    let relative = URL(string: "linked-directory/../persistent", relativeTo: root)!
    check(relative.baseURL != nil, "relative fixture retains its base URL")
    do {
        try LinuxTerminalDisk.validateDirectory(relative, allowingMissing: true)
        preconditionFailure("Linux terminal host check: unresolved relative directory URL was accepted")
    } catch LinuxTerminalProfile.Invalid.diskDirectoryURL { }
    for suffix in ["/%2E/child", "/%2E%2E/child"] {
        let untrusted = URL(string: root.absoluteString + suffix)!
        do {
            try LinuxTerminalDisk.validateDirectory(untrusted, allowingMissing: true)
            preconditionFailure("Linux terminal host check: raw dot path component was accepted")
        } catch LinuxTerminalProfile.Invalid.diskDirectoryComponent { }
    }

    let seed = root.appendingPathComponent("userdata-seed.raw")
    checkpoint("seed-layout")
    try makeSeed(seed)
    // Reproduce the old missing-seek mistake with the real Foundation API.
    // This synthetic malformed seed must fail before any disk is published.
    checkpoint("appended-header-regression")
    let appended = root.appendingPathComponent("appended-header.raw")
    check(manager.createFile(atPath: appended.path, contents: nil))
    let appendedWriter = try FileHandle(forWritingTo: appended)
    try appendedWriter.truncate(atOffset: UInt64(LinuxTerminalProfile.diskSize))
    check(try appendedWriter.offset() == UInt64(LinuxTerminalProfile.diskSize), "regression starts at EOF after truncate")
    try appendedWriter.write(contentsOf: bootSector())
    check(try appendedWriter.offset() == UInt64(LinuxTerminalProfile.diskSize + 512), "missing seek appends the header")
    try appendedWriter.synchronize(); try appendedWriter.close()
    check(try fileSize(appended) == LinuxTerminalProfile.diskSize + 512, "malformed seed is exactly one sector oversized")
    let appendedReader = try FileHandle(forReadingFrom: appended)
    check(try appendedReader.read(upToCount: 512) == Data(repeating: 0, count: 512), "malformed seed has an empty first sector")
    try appendedReader.seek(toOffset: UInt64(LinuxTerminalProfile.diskSize))
    check(try appendedReader.read(upToCount: 512) == bootSector(), "malformed seed BPB is at EOF instead of zero")
    try appendedReader.close()
    let rejected = root.appendingPathComponent("appended-header-data")
    // Prove directory validation accepts this target before a typed size
    // rejection; an unrelated directory failure must not satisfy this test.
    try LinuxTerminalDisk.validateDirectory(rejected, allowingMissing: true)
    do {
        _ = try LinuxTerminalDisk.open(directory: rejected, seed: appended)
        preconditionFailure("Linux terminal host check: oversized seed was accepted")
    } catch LinuxTerminalProfile.Invalid.diskSeedSize { }
    check(!manager.fileExists(atPath: rejected.appendingPathComponent("userdata.raw").path), "oversized seed must not publish a persistent disk")
    let directory = root.appendingPathComponent("persistent")
    checkpoint("disk-first-open")
    try LinuxTerminalDisk.validateDirectory(directory, allowingMissing: true)
    let disk = try LinuxTerminalDisk.open(directory: directory, seed: seed)
    check(disk.url.lastPathComponent == "userdata.raw")
    check(try byte(disk.url, at: 2 * 1024 * 1024) == Data([0]))
    expectFailure { _ = try LinuxTerminalDisk.open(directory: directory, seed: seed) }
    let writer = try FileHandle(forWritingTo: disk.url)
    try writer.seek(toOffset: 2 * 1024 * 1024)
    try writer.write(contentsOf: Data([0x7b]))
    try writer.close()
    try disk.synchronize()
    // Runtime sync must retain the lock: main_loop returning is not proof
    // that QEMU has released/drained all block-layer file descriptions.
    expectFailure { _ = try LinuxTerminalDisk.open(directory: directory, seed: seed) }
    try disk.synchronizeAndClose()
    expectFailure { try disk.synchronize() }
    checkpoint("disk-reopen")
    let reopened = try LinuxTerminalDisk.open(directory: directory, seed: seed)
    check(try byte(reopened.url, at: 2 * 1024 * 1024) == Data([0x7b]))
    check(try byte(seed, at: 2 * 1024 * 1024) == Data([0]))
    try reopened.synchronizeAndClose()

    // Rejection preserves existing bytes; no retry replaces a user's disk.
    checkpoint("disk-rejection-guards")
    let wrong = root.appendingPathComponent("wrong-size")
    try manager.createDirectory(at: wrong, withIntermediateDirectories: true)
    let wrongDisk = wrong.appendingPathComponent("userdata.raw")
    let sentinel = Data("preserve existing wrong-sized disk".utf8)
    try sentinel.write(to: wrongDisk)
    expectFailure { _ = try LinuxTerminalDisk.open(directory: wrong, seed: seed) }
    check(try Data(contentsOf: wrongDisk) == sentinel)
    let linked = root.appendingPathComponent("linked-disk")
    try manager.createDirectory(at: linked, withIntermediateDirectories: true)
    try manager.createSymbolicLink(at: linked.appendingPathComponent("userdata.raw"), withDestinationURL: seed)
    expectFailure { _ = try LinuxTerminalDisk.open(directory: linked, seed: seed) }
    let linkedDirectory = root.appendingPathComponent("linked-directory")
    try manager.createSymbolicLink(at: linkedDirectory, withDestinationURL: directory)
    do {
        try LinuxTerminalDisk.validateDirectory(linkedDirectory.appendingPathComponent("child"), allowingMissing: true)
        preconditionFailure("Linux terminal host check: original symlink ancestor was accepted")
    } catch LinuxTerminalProfile.Invalid.diskDirectoryType { }
    do {
        _ = try LinuxTerminalDisk.open(directory: linkedDirectory, seed: seed)
        preconditionFailure("Linux terminal host check: symlink disk directory was accepted")
    } catch LinuxTerminalProfile.Invalid.diskDirectoryType { }
    let hiddenLink = URL(string: linkedDirectory.absoluteString + "/%2E%2E/hidden-data")!
    do {
        try LinuxTerminalDisk.validateDirectory(hiddenLink, allowingMissing: true)
        preconditionFailure("Linux terminal host check: dotdot hid a symlink ancestor")
    } catch LinuxTerminalProfile.Invalid.diskDirectoryComponent { }
    let corrupt = try FileHandle(forWritingTo: directory.appendingPathComponent("userdata.raw"))
    try corrupt.seek(toOffset: 510); try corrupt.write(contentsOf: Data([0, 0])); try corrupt.close()
    expectFailure { _ = try LinuxTerminalDisk.open(directory: directory, seed: seed) }
    check(try byte(directory.appendingPathComponent("userdata.raw"), at: 510) == Data([0]))
    expectFailure { _ = try LinuxTerminalDisk.open(directory: root.appendingPathComponent("bad-size-option"), seed: seed, size: 512) }

    let probeAssets = root.appendingPathComponent("probe")
    checkpoint("profile-fixtures")
    let terminalAssets = root.appendingPathComponent("terminal")
    try manager.createDirectory(at: probeAssets, withIntermediateDirectories: true)
    try manager.createDirectory(at: terminalAssets, withIntermediateDirectories: true)
    for name in ["vmlinuz-virt", "initramfs-ideck.gz"] {
        try Data("synthetic host validator bytes".utf8).write(to: probeAssets.appendingPathComponent(name))
    }
    let terminalInit = terminalAssets.appendingPathComponent("initramfs-terminal.gz")
    try Data("synthetic terminal initramfs validator bytes".utf8).write(to: terminalInit)
    let bundledSeed = terminalAssets.appendingPathComponent("userdata-seed.raw")
    try manager.copyItem(at: seed, to: bundledSeed)
    let kernel = try asset(probeAssets.appendingPathComponent("vmlinuz-virt"))
    var probe: [String: Any] = ["schema": 1, "width": 800, "height": 600, "cpu": "cortex-a72",
        "memory_mib": 1024, "vcpus": 4, "tcg_cache_mib": 256, "kernel": kernel,
        "initramfs": try asset(probeAssets.appendingPathComponent("initramfs-ideck.gz"))]
    try JSONSerialization.data(withJSONObject: probe).write(to: probeAssets.appendingPathComponent("profile.json"))
    var description = probe
    description["mode"] = "terminal"; description["filesystem"] = "fat16"
    description["disk_size_bytes"] = LinuxTerminalProfile.diskSize
    description["control_port"] = "org.ideck.control"
    description["initramfs"] = try asset(terminalInit)
    let sourceSeedDescription = try asset(seed)
    let bundledSeedDescription = try asset(bundledSeed)
    description["seed"] = bundledSeedDescription
    check(sourceSeedDescription["sha256"] as? String == bundledSeedDescription["sha256"] as? String,
          "bundled seed matches the independently checked source fixture")
    let profileURL = terminalAssets.appendingPathComponent("terminal-profile.json")
    try JSONSerialization.data(withJSONObject: description).write(to: profileURL)
    let profile = try LinuxTerminalProfile.load(from: terminalAssets)
    checkpoint("profile-disk-open")
    let profileDisk = try profile.openDisk(in: root.appendingPathComponent("profile-data,one"), assets: terminalAssets)
    defer { profileDisk.closeUnused() }
    let session = root.appendingPathComponent("session,one")
    checkpoint("terminal-argv")
    let args = try profile.arguments(probeAssets: probeAssets, terminalAssets: terminalAssets,
        session: session, diskURL: profileDisk.url, serialFD: 51, controlFD: 52)
    check(args.contains("tcg,thread=multi,tb-size=256,split-wx=on"))
    check(args[args.firstIndex(of: "-nic")! + 1] == "none" && !args.contains("-netdev"))
    check(args.contains("virtserialport,chardev=linuxcontrol,name=org.ideck.control"))
    check(args.contains("socket,id=linuxcontrol,fd=52,server=off"))
    check(args.contains("socket,id=linuxterm,fd=51,server=off"))
    check(args.contains(where: { $0.contains("format=raw,cache=writethrough,file=") && $0.contains("profile-data,,one/userdata.raw") }))
    check(args.contains(where: { $0.contains("rdinit=/ideck-terminal-init") }))
    check(!args.contains(where: { $0.contains("tcp:") || $0.contains("hostfwd") || $0.contains("snapshot=on") }))

    // Regress the failing fixture representation AND the real Apple system
    // alias independently of TMPDIR. Root links are permitted bundle aliases;
    // asset leaf links remain forbidden below. No extra 128 MiB fixture copies.
    checkpoint("asset-directory-representations")
    let aliasName = "ideck-asset-checks-\(UUID().uuidString)"
    let canonicalAlias = trustedVar.appendingPathComponent("tmp").appendingPathComponent(aliasName)
    try manager.createDirectory(at: canonicalAlias, withIntermediateDirectories: false)
    defer { try? manager.removeItem(at: canonicalAlias) }
    try manager.createSymbolicLink(at: canonicalAlias.appendingPathComponent("probe"), withDestinationURL: probeAssets)
    try manager.createSymbolicLink(at: canonicalAlias.appendingPathComponent("terminal"), withDestinationURL: terminalAssets)
    let systemAlias = rawVar.appendingPathComponent("tmp").appendingPathComponent(aliasName)
    for (label, probeRoot, terminalRoot) in [
        ("local", probeAssets, terminalAssets),
        ("apple-alias", systemAlias.appendingPathComponent("probe"), systemAlias.appendingPathComponent("terminal"))
    ] {
        for hint in [false, true] {
            let probeRoot = URL(fileURLWithPath: probeRoot.path, isDirectory: hint)
            let terminalRoot = URL(fileURLWithPath: terminalRoot.path, isDirectory: hint)
            let suffix = "\(label)-\(hint)"
            checkpoint("asset-path-" + suffix)
            let alternate = try LinuxTerminalProfile.load(from: terminalRoot)
            let alternateDisk = try alternate.openDisk(in: root.appendingPathComponent("asset-data-" + suffix), assets: terminalRoot)
            defer { alternateDisk.closeUnused() }
            let alternateSession = root.appendingPathComponent("asset-session-" + suffix)
            let alternateArgs = try alternate.arguments(probeAssets: probeRoot, terminalAssets: terminalRoot,
                session: alternateSession, diskURL: alternateDisk.url, serialFD: 51, controlFD: 52)
            check(alternateArgs[alternateArgs.firstIndex(of: "-kernel")! + 1] == probeAssets.appendingPathComponent("vmlinuz-virt").path,
                  "probe uses the exact canonical kernel path")
            check(alternateArgs[alternateArgs.firstIndex(of: "-initrd")! + 1] == terminalInit.path,
                  "terminal uses the exact canonical initramfs path")
        }
    }

    checkpoint("asset-rejection-guards")
    let rejectedSession = root.appendingPathComponent("rejected-asset-session")
    func terminalArguments() throws {
        _ = try profile.arguments(probeAssets: probeAssets, terminalAssets: terminalAssets,
            session: rejectedSession, diskURL: profileDisk.url, serialFD: 51, controlFD: 52)
    }
    // Same size corruption must reach the digest check, before session creation.
    let savedInit = try Data(contentsOf: terminalInit)
    var changedInit = savedInit; changedInit[0] ^= 1
    try changedInit.write(to: terminalInit)
    expectTerminalFailure(.assetDigest) { try terminalArguments() }
    check(!manager.fileExists(atPath: rejectedSession.path))
    try savedInit.write(to: terminalInit)
    let probeInit = probeAssets.appendingPathComponent("initramfs-ideck.gz")
    let savedProbeInit = try Data(contentsOf: probeInit)
    var changedProbeInit = savedProbeInit; changedProbeInit[0] ^= 1
    try changedProbeInit.write(to: probeInit)
    expectProbeFailure(.assetDigest) { try terminalArguments() }
    check(!manager.fileExists(atPath: rejectedSession.path))
    try savedProbeInit.write(to: probeInit)
    // Reject leaf links even to correct bytes inside the same asset directory,
    // and to a sibling outside it. Neither case may be hidden by canonicalizing.
    for (leaf, expected, contents) in [(terminalInit, "terminal", savedInit), (probeInit, "probe", savedProbeInit)] {
        for parent in [leaf.deletingLastPathComponent(), root] {
            let target = parent.appendingPathComponent("saved-" + expected)
            try contents.write(to: target)
            try manager.removeItem(at: leaf)
            try manager.createSymbolicLink(at: leaf, withDestinationURL: target)
            if expected == "terminal" { expectTerminalFailure(.assetType) { try terminalArguments() } }
            else { expectProbeFailure(.assetType) { try terminalArguments() } }
            check(!manager.fileExists(atPath: rejectedSession.path))
            try manager.removeItem(at: leaf)
            try contents.write(to: leaf)
            try manager.removeItem(at: target)
        }
    }
    expectFailure { _ = try profile.arguments(probeAssets: probeAssets, terminalAssets: terminalAssets,
        session: session, diskURL: profileDisk.url, serialFD: 51, controlFD: 52) }
    expectFailure { _ = try profile.arguments(probeAssets: probeAssets, terminalAssets: terminalAssets,
        session: root.appendingPathComponent("invalid-fd"), diskURL: profileDisk.url, serialFD: 51, controlFD: 51) }
    var badSeed = try asset(bundledSeed)
    badSeed["sha256"] = String(repeating: "0", count: 64)
    description["seed"] = badSeed
    try JSONSerialization.data(withJSONObject: description).write(to: profileURL)
    let badSeedProfile = try LinuxTerminalProfile.load(from: terminalAssets)
    let absentData = root.appendingPathComponent("bad-seed-data")
    expectTerminalFailure(.assetDigest) { _ = try badSeedProfile.openDisk(in: absentData, assets: terminalAssets) }
    check(!manager.fileExists(atPath: absentData.path))
    badSeed["file"] = "../userdata-seed.raw"
    description["seed"] = badSeed
    try JSONSerialization.data(withJSONObject: description).write(to: profileURL)
    let wrongNameProfile = try LinuxTerminalProfile.load(from: terminalAssets)
    expectTerminalFailure(.assetDescriptor) { _ = try wrongNameProfile.openDisk(in: absentData, assets: terminalAssets) }
    check(!manager.fileExists(atPath: absentData.path))
    description["control_port"] = "unexpected.port"
    try JSONSerialization.data(withJSONObject: description).write(to: profileURL)
    expectFailure { _ = try LinuxTerminalProfile.load(from: terminalAssets) }
    probe["cpu"] = "host"
    try JSONSerialization.data(withJSONObject: probe).write(to: probeAssets.appendingPathComponent("profile.json"))
    expectFailure { _ = try profile.arguments(probeAssets: probeAssets, terminalAssets: terminalAssets,
        session: root.appendingPathComponent("wrong-probe"), diskURL: profileDisk.url, serialFD: 51, controlFD: 52) }

    // The shipped renderer must separate a clean-stop receipt from block-layer
    // teardown, diagnostic probe success and real second-boot verification.
    checkpoint("terminal-report-renderer")
    let cleanReport = LinuxProbeReport.render(report: ["mode": "terminal", "status": "terminal_clean_stopped",
        "terminal_ready": true, "terminal_clean_unmount": true, "qemu_main_loop_returned": true,
        "host_disk_fsync_passed": true, "terminal_clean_stop": true,
        "userdata_lock_retained_until_process_exit": true, "qemu_block_layer_drained_verified": false,
        "steam_executed": false, "physical_screen_verified": false, "accelerated_guest_gpu_verified": false])
    check(cleanReport.contains("| Orderly stop | PASS |"))
    check(cleanReport.contains("| Disk lock retained until app exits | RETAINED |"))
    check(cleanReport.contains("| QEMU block layer drained | NOT VERIFIED |"))
    check(cleanReport.contains("| Frame A RGB validation | UNKNOWN |"))
    check(cleanReport.contains("| Guest input | UNKNOWN |"))
    check(cleanReport.contains("| Physical screen | NOT VERIFIED |"))
    check(cleanReport.contains("| Accelerated guest GPU | NOT VERIFIED |"))
    check(cleanReport.contains("| Steam | NOT RUN |"))
    check(cleanReport.contains("does not itself verify a file after a second guest boot"))
    for status in ["terminal_startup_timeout", "terminal_stop_timeout", "terminal_stop_failed"] {
        let failedReport = LinuxProbeReport.render(report: ["mode": "terminal", "status": status,
            "host_disk_fsync_passed": NSNumber(value: 1)])
        check(failedReport.contains("orderly stop is not established"))
        check(failedReport.contains("| Host disk sync | UNKNOWN |"))
        check(failedReport.contains("| Orderly stop | UNKNOWN |"))
        check(failedReport.contains("| QEMU block layer drained | UNKNOWN |"))
    }
    print("LINUX_TERMINAL_HOST_CHECKS_PASS (actual disk/config helpers; synthetic assets; no guest/device execution)")
}
