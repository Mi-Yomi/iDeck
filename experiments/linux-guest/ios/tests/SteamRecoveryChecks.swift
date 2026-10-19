import Foundation
import Darwin

/// Sparse negative fixture only; no fsck, repaired header or positive replay claim.
func runSteamRecoveryChecks(directory: URL, header: [UInt8], specification: LinuxDesktopDisk.Specification) throws {
    let scope = LinuxGUIRecovery.Scope.steam
    precondition(scope.accepts(specification) && !LinuxGUIRecovery.Scope.gui.accepts(specification))
    precondition(scope.suffixSHA256 == LinuxSteamRecoveryGuest.sha256)
    precondition(scope.suffixSHA256 != LinuxGUIRecovery.Scope.gui.suffixSHA256)
    let eligible = LinuxDesktopDisk.RecoveryObservation(recoverBit: true, state: 1, lastOrphan: 0, errorCount: 0)
    precondition(scope.permits(eligible) && !scope.permits(nil))
    for bad in [LinuxDesktopDisk.RecoveryObservation(recoverBit: false, state: 1, lastOrphan: 0, errorCount: 0),
                .init(recoverBit: true, state: 0, lastOrphan: 0, errorCount: 0),
                .init(recoverBit: true, state: 1, lastOrphan: 1, errorCount: 0),
                .init(recoverBit: true, state: 1, lastOrphan: 0, errorCount: 1)] {
        precondition(!scope.permits(bad))
    }
    do {
        _ = try LinuxGUIRecovery.prepare(directory: directory, specification: specification, availableBytes: { _ in 0 })
        preconditionFailure("default GUI scope accepted Steam")
    } catch LinuxGUIRecovery.Invalid.metadata { }
    var observed: LinuxDesktopDisk.RecoveryObservation?
    do {
        _ = try LinuxGUIRecovery.prepare(directory: directory, specification: specification,
            availableBytes: { _ in 0 }, observe: { observed = $0 }, scope: .steam)
        preconditionFailure("Steam recovery accepted insufficient real-copy budget")
    } catch LinuxGUIRecovery.Invalid.space { }
    precondition(observed == eligible)
    var watchdog = LinuxRecoveryWatchdog(started: 0, scope: .steam)
    precondition(watchdog.timeout(at: 60) == .supervisor)
    watchdog.advanced(at: 1, supervisor: true)
    precondition(watchdog.timeout(at: 900) == nil && watchdog.timeout(at: 901) == .progress)
    watchdog.advanced(at: 1799)
    precondition(watchdog.timeout(at: 1800) == .deadline)
    let source = directory.appendingPathComponent("rootfs-v1.raw")
    let fd = Darwin.open(source.path, O_RDONLY | O_NOFOLLOW)
    precondition(fd >= 0); defer { Darwin.close(fd) }
    var current = [UInt8](repeating: 0, count: 1024)
    let read = current.withUnsafeMutableBytes { pread(fd, $0.baseAddress, $0.count, 1024) }
    precondition(read == 1024 && current == header)
    var state = stat(); precondition(fstat(fd, &state) == 0 && state.st_size == specification.sizeBytes)
    precondition(!FileManager.default.fileExists(atPath: directory.appendingPathComponent(".recovery-v1/current.json").path))
    do {
        _ = try LinuxDesktopDisk.openExisting(directory: directory, specification: specification)
        preconditionFailure("space refusal cleared ext4 guard")
    } catch LinuxDesktopDisk.Invalid.needsRecovery { }
    print("LINUX_STEAM_RECOVERY_SCOPE_PASS (scope isolation, RECOVER-only eligibility, low-space before hash/copies, original header/guard retained; replay NOT RUN)")
}
