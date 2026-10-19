import Foundation
#if canImport(Darwin)
import Darwin
#else
import Glibc
#endif

struct DesktopGolden: Decodable {
    let sizeBytes: Int64
    let uuid: String
    let blockSize: Int
    let features: LinuxDesktopDisk.Features
    let headerHex: String
    var specification: LinuxDesktopDisk.Specification {
        .init(sizeBytes: sizeBytes, uuid: uuid, blockSize: blockSize, features: features)
    }
    var header: [UInt8] {
        let bytes = Array(headerHex.utf8)
        return stride(from: 0, to: bytes.count, by: 2).map {
            UInt8(String(decoding: bytes[$0..<$0 + 2], as: UTF8.self), radix: 16)!
        }
    }
    static func load(_ url: URL) throws -> Self {
        let decoder = JSONDecoder(); decoder.keyDecodingStrategy = .convertFromSnakeCase
        return try decoder.decode(Self.self, from: Data(contentsOf: url))
    }
}

func runDesktopDiskContender(directory: URL, fixture: URL, locked: Bool) throws {
    let spec = try DesktopGolden.load(fixture).specification
    do {
        let disk = try LinuxDesktopDisk.openExisting(directory: directory, specification: spec)
        precondition(!locked, "another process acquired owned ext4 image")
        try disk.validateOwnership(); disk.closeUnused()
    } catch LinuxDesktopDisk.Invalid.locked { precondition(locked) }
    exit(0)
}

func runDesktopInterruptedImport(directory: URL, fixture: URL) throws {
    let spec = try DesktopGolden.load(fixture).specification
    _ = try LinuxDesktopDisk.provision(directory: directory, specification: spec) { fd in
        let partial = FileHandle(fileDescriptor: fd, closeOnDealloc: false)
        try partial.write(contentsOf: Data(repeating: 0x53, count: 4096))
        try partial.synchronize()
        _exit(77) // Real process exit bypasses all defer cleanup.
    }
    preconditionFailure("interrupted import child returned")
}

/// Actual storage helper checks. Golden header came from real mke2fs; sparse
/// unit-test bodies do not claim a complete filesystem or Linux mount/boot.
func runDesktopDiskChecks(fixture: URL, afterSync: ((LinuxDesktopDisk) throws -> Void)? = nil) throws {
    let golden = try DesktopGolden.load(fixture)
    let spec = golden.specification
    let header = golden.header
    precondition(header.count == 1024)
    try LinuxDesktopDisk.validateHeader(header, specification: spec)
    precondition(LinuxDesktopDisk.crc32c(Array("123456789".utf8)) == 0x1cf96d7c)
    func expect(_ failure: LinuxDesktopDisk.Invalid, _ body: () throws -> Void) {
        do { try body(); preconditionFailure("unsafe desktop disk accepted") }
        catch let received as LinuxDesktopDisk.Invalid { precondition(received == failure, "wrong desktop disk guard: \(received), expected \(failure)") }
        catch { preconditionFailure("unexpected desktop disk error") }
    }
    func checksum(_ data: inout [UInt8]) {
        let value = LinuxDesktopDisk.crc32c(data[0..<1020])
        for byte in 0..<4 { data[1020 + byte] = UInt8((value >> (8 * byte)) & 255) }
    }
    // Repair checksum after semantic mutations so each test reaches its guard.
    for (offset, value, error) in [
        (0x38, UInt8(0), LinuxDesktopDisk.Invalid.filesystem),
        (0x68, UInt8(header[0x68] ^ 1), .uuid),
        (0x5c, UInt8(header[0x5c] | 0x80), .features),
        (0x64, UInt8(header[0x64] | 0x20), .features),
        (0x60, UInt8(header[0x60] | 4), .needsRecovery),
        (0x3a, UInt8(0), .needsRecovery),
        (0xe8, UInt8(1), .needsRecovery),
        (0x194, UInt8(1), .needsRecovery),
        (0x18, UInt8(3), .geometry),
        (0xe0, UInt8(9), .journal),
        (0xe4, UInt8(1), .journal)
    ] {
        var changed = header; changed[offset] = value; checksum(&changed)
        expect(error) { try LinuxDesktopDisk.validateHeader(changed, specification: spec) }
    }
    var corrupt = header; corrupt[0x80] ^= 1
    expect(.checksum) {
        try LinuxDesktopDisk.validateHeader(corrupt, specification: spec) { _ in
            preconditionFailure("unvalidated metadata was observed")
        }
    }
    var huge = header
    for i in 4..<8 { huge[i] = 255 }
    for i in 0x150..<0x154 { huge[i] = 255 }
    checksum(&huge)
    expect(.geometry) { try LinuxDesktopDisk.validateHeader(huge, specification: spec) }
    // Mutable times/free counts are not the seed's immutable contract.
    var mutable = header; mutable[0x0c] ^= 1; mutable[0x30] ^= 1; checksum(&mutable)
    try LinuxDesktopDisk.validateHeader(mutable, specification: spec)

    let manager = FileManager.default
    let path = realpath(manager.temporaryDirectory.path, nil)!
    let root = URL(fileURLWithPath: String(cString: path)).appendingPathComponent("ideck-ext4-checks-" + UUID().uuidString)
    free(path)
    try manager.createDirectory(at: root, withIntermediateDirectories: true)
    defer { try? manager.removeItem(at: root) }
    func copyFixture(_ fd: Int32) throws {
        let handle = FileHandle(fileDescriptor: fd, closeOnDealloc: false)
        try handle.truncate(atOffset: UInt64(spec.sizeBytes))
        try handle.seek(toOffset: 1024)
        try handle.write(contentsOf: Data(header))
    }
    func children(_ directory: URL, locked: Bool) throws {
        var all: [(Process, DispatchSemaphore)] = []
        for _ in 0..<(locked ? 3 : 1) {
            let child = Process(), done = DispatchSemaphore(value: 0)
            child.executableURL = URL(fileURLWithPath: CommandLine.arguments[0])
            child.arguments = ["--desktop-disk-contender", directory.path, fixture.path, locked ? "locked" : "free"]
            child.terminationHandler = { _ in done.signal() }
            try child.run(); all.append((child, done))
        }
        for (child, done) in all {
            if done.wait(timeout: .now() + 10) != .success {
                child.terminate(); preconditionFailure("ext4 contender blocked")
            }
            precondition(child.terminationReason == .exit && child.terminationStatus == 0)
        }
    }
    let directory = root.appendingPathComponent("persistent")
    let disk = try LinuxDesktopDisk.provision(directory: directory, specification: spec, validatedCopy: copyFixture)
    defer { disk.closeUnused() }
    try disk.validateOwnership()
    expect(.locked) { _ = try LinuxDesktopDisk.openExisting(directory: directory, specification: spec) }
    try children(directory, locked: true)
    expect(.alreadyExists) {
        _ = try LinuxDesktopDisk.provision(directory: directory, specification: spec) { _ in preconditionFailure("existing disk reseeded") }
    }
    let file = try FileHandle(forWritingTo: disk.url)
    try file.seek(toOffset: 2 * 1024 * 1024); try file.write(contentsOf: Data([0x7b])); try file.close()
    try disk.synchronize(); try disk.validateOwnership()
    try afterSync?(disk)
    try children(directory, locked: true)
    disk.closeUnused()
    expect(.ownership) { try disk.validateOwnership() }
    try children(directory, locked: false)
    let reopened = try LinuxDesktopDisk.openExisting(directory: directory, specification: spec)
    let reader = try FileHandle(forReadingFrom: reopened.url)
    try reader.seek(toOffset: 2 * 1024 * 1024)
    let sentinel = try reader.read(upToCount: 1)
    precondition(sentinel == Data([0x7b]))
    try reader.close(); reopened.closeUnused()

    // Actual pathname/inode guards, with no writes to existing rejected data.
    let owner = try LinuxDesktopDisk.openExisting(directory: directory, specification: spec)
    defer { owner.closeUnused() }
    let held = directory.appendingPathComponent("held.raw")
    try manager.moveItem(at: owner.url, to: held)
    expect(.ownership) { try owner.validateOwnership() }
    try manager.copyItem(at: held, to: owner.url)
    expect(.ownership) { try owner.validateOwnership() }
    try manager.removeItem(at: owner.url)
    try manager.createSymbolicLink(at: owner.url, withDestinationURL: held)
    expect(.ownership) { try owner.validateOwnership() }
    try manager.removeItem(at: owner.url); try manager.moveItem(at: held, to: owner.url)
    precondition(link(owner.url.path, held.path) == 0)
    expect(.ownership) { try owner.validateOwnership() }
    try manager.removeItem(at: held); try owner.validateOwnership()
    let ancestor = root.appendingPathComponent("ancestor-link")
    try manager.createSymbolicLink(at: ancestor, withDestinationURL: directory)
    expect(.directory) { _ = try LinuxDesktopDisk.openExisting(directory: ancestor, specification: spec) }
    let short = try FileHandle(forWritingTo: owner.url)
    try short.truncate(atOffset: UInt64(spec.sizeBytes - 1)); try short.close()
    expect(.size) { try owner.validateOwnership() }
    owner.closeUnused()
    let before = try manager.attributesOfItem(atPath: owner.url.path)[.size] as! NSNumber
    expect(.size) { _ = try LinuxDesktopDisk.openExisting(directory: directory, specification: spec) }
    let after = try manager.attributesOfItem(atPath: owner.url.path)[.size] as! NSNumber
    precondition(after == before)

    let interrupted = root.appendingPathComponent("failed-import")
    expect(.io) {
        _ = try LinuxDesktopDisk.provision(directory: interrupted, specification: spec) { fd in
            try copyFixture(fd); throw LinuxDesktopDisk.Invalid.io
        }
    }
    let interruptedContents = try manager.contentsOfDirectory(atPath: interrupted.path)
    precondition(interruptedContents.isEmpty)
    let killed = root.appendingPathComponent("killed-import")
    let child = Process(), completed = DispatchSemaphore(value: 0)
    child.executableURL = URL(fileURLWithPath: CommandLine.arguments[0])
    child.arguments = ["--desktop-interrupted-import", killed.path, fixture.path]
    child.terminationHandler = { _ in completed.signal() }
    try child.run()
    if completed.wait(timeout: .now() + 10) != .success { child.terminate(); preconditionFailure("import child blocked") }
    precondition(child.terminationStatus == 77)
    precondition(manager.fileExists(atPath: killed.appendingPathComponent(".rootfs-import-v1.partial").path))
    let retried = try LinuxDesktopDisk.provision(directory: killed, specification: spec, validatedCopy: copyFixture)
    try retried.validateOwnership(); retried.closeUnused()
    let killedContents = try manager.contentsOfDirectory(atPath: killed.path)
    precondition(killedContents == ["rootfs-v1.raw"])
    // Interrupted atomic publication leaves a second alias, not a second copy.
    let alias = killed.appendingPathComponent(".rootfs-import-v1.partial")
    precondition(link(retried.url.path, alias.path) == 0)
    let published = try LinuxDesktopDisk.openExisting(directory: killed, specification: spec)
    try published.validateOwnership(); published.closeUnused()
    precondition(!manager.fileExists(atPath: alias.path))
    let full = root.appendingPathComponent("space-exhausted")
    expect(.insufficientSpace) {
        _ = try LinuxDesktopDisk.provision(directory: full, specification: spec, availableBytes: { _ in 0 }) { _ in
            preconditionFailure("seed copied without available space")
        }
    }
    let fullContents = try manager.contentsOfDirectory(atPath: full.path)
    precondition(fullContents.isEmpty)
    let busy = root.appendingPathComponent("busy-import")
    try manager.createDirectory(at: busy, withIntermediateDirectories: true)
    let busyPartial = busy.appendingPathComponent(".rootfs-import-v1.partial")
    let busyFD = open(busyPartial.path, O_RDWR | O_CREAT | O_EXCL, mode_t(0o600))
    precondition(busyFD >= 0 && flock(busyFD, LOCK_EX | LOCK_NB) == 0)
    expect(.locked) { _ = try LinuxDesktopDisk.provision(directory: busy, specification: spec, validatedCopy: copyFixture) }
    precondition(manager.fileExists(atPath: busyPartial.path), "contender removed active import")
    _ = close(busyFD)
    let dirtyDirectory = root.appendingPathComponent("needs-recovery")
    let dirtyDisk = try LinuxDesktopDisk.provision(directory: dirtyDirectory, specification: spec, validatedCopy: copyFixture)
    dirtyDisk.closeUnused()
    var dirty = header; dirty[0x60] |= 4; dirty[0x3a] = 2
    for byte in 0..<4 { dirty[0xe8 + byte] = 255; dirty[0x194 + byte] = 255 }
    checksum(&dirty)
    let dirtyWriter = try FileHandle(forWritingTo: dirtyDisk.url)
    try dirtyWriter.seek(toOffset: 1024); try dirtyWriter.write(contentsOf: Data(dirty)); try dirtyWriter.close()
    var observed: [LinuxDesktopDisk.RecoveryObservation] = []
    expect(.needsRecovery) {
        _ = try LinuxDesktopDisk.openExisting(directory: dirtyDirectory, specification: spec) { observed.append($0) }
    }
    precondition(observed == [.init(recoverBit: true, state: 2, lastOrphan: UInt32.max, errorCount: UInt32.max)],
                 "the refused locked header supplies all four exact fields")
    expect(.alreadyExists) { _ = try LinuxDesktopDisk.provision(directory: dirtyDirectory, specification: spec, validatedCopy: copyFixture) }
    let dirtyReader = try FileHandle(forReadingFrom: dirtyDisk.url)
    try dirtyReader.seek(toOffset: 1024)
    let preservedHeader = try dirtyReader.read(upToCount: 1024); try dirtyReader.close()
    precondition(preservedHeader == Data(dirty), "recovery refusal mutated the disk")
    // A trusted copy callback can expose a concurrent directory replacement.
    // Pinning openat/linkat/unlinkat must not publish or delete its substitute.
    let swapped = root.appendingPathComponent("swapped-import")
    let renamed = root.appendingPathComponent("original-import")
    var replacement: URL?
    expect(.directory) {
        _ = try LinuxDesktopDisk.provision(directory: swapped, specification: spec) { fd in
            try copyFixture(fd)
            let name = try manager.contentsOfDirectory(atPath: swapped.path).first!
            try manager.moveItem(at: swapped, to: renamed)
            try manager.createDirectory(at: swapped, withIntermediateDirectories: false)
            let substitute = swapped.appendingPathComponent(name)
            precondition(manager.createFile(atPath: substitute.path, contents: nil))
            let alternate = try FileHandle(forWritingTo: substitute)
            try copyFixture(alternate.fileDescriptor)
            try alternate.seek(toOffset: 2 * 1024 * 1024)
            try alternate.write(contentsOf: Data([0x5e])); try alternate.close()
            replacement = substitute
        }
    }
    let kept = try FileHandle(forReadingFrom: replacement!)
    try kept.seek(toOffset: 2 * 1024 * 1024)
    let keptMarker = try kept.read(upToCount: 1); try kept.close()
    precondition(keptMarker == Data([0x5e]))
    precondition(!manager.fileExists(atPath: swapped.appendingPathComponent("rootfs-v1.raw").path))
    let originalTemps = try manager.contentsOfDirectory(atPath: renamed.path)
    precondition(originalTemps.isEmpty)

    let tempSwap = root.appendingPathComponent("swapped-temp-entry")
    var unknown: URL?
    expect(.ownership) {
        _ = try LinuxDesktopDisk.provision(directory: tempSwap, specification: spec) { fd in
            try copyFixture(fd)
            let name = try manager.contentsOfDirectory(atPath: tempSwap.path).first!
            let source = tempSwap.appendingPathComponent(name)
            try manager.moveItem(at: source, to: tempSwap.appendingPathComponent("held-original"))
            precondition(manager.createFile(atPath: source.path, contents: nil))
            let alternate = try FileHandle(forWritingTo: source)
            try copyFixture(alternate.fileDescriptor); try alternate.close()
            unknown = source
        }
    }
    precondition(manager.fileExists(atPath: unknown!.path), "cleanup removed an unknown replacement")
    precondition(!manager.fileExists(atPath: tempSwap.appendingPathComponent("rootfs-v1.raw").path))

    let invalid = root.appendingPathComponent("invalid-header")
    expect(.filesystem) {
        _ = try LinuxDesktopDisk.provision(directory: invalid, specification: spec) { fd in
            let handle = FileHandle(fileDescriptor: fd, closeOnDealloc: false)
            try handle.truncate(atOffset: UInt64(spec.sizeBytes))
        }
    }
    let invalidContents = try manager.contentsOfDirectory(atPath: invalid.path)
    precondition(invalidContents.isEmpty)
    print("LINUX_DESKTOP_DISK_CHECKS_PASS (actual owner/IO; real mke2fs header; sparse unit bodies, no guest boot)")
}
