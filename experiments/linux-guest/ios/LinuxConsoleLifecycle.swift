import Foundation

/// qemu_init registers the calling thread's TLS reader in pinned QEMU's RCU
/// registry. Main-loop return does not tear down that registration, BQL, vCPUs
/// or display callbacks. Keep the SAME native thread alive for this single-use
/// runtime, just as we retain its disk owner. See docs/qemu-owner-lifetime.md.
enum LinuxQEMUThreadLifetime {
    static func retainCurrentThread(_ retained: () -> Void) -> Never {
        let condition = NSCondition()
        condition.lock()
        retained()
        // No release/cancel API: only process exit may reclaim this runtime.
        // A condition wait blocks without polling and tolerates spurious wakes.
        // It releases only this private mutex; QEMU's BQL ownership is intact.
        while true { condition.wait() }
    }
}

/// Shared Stop decision used by the real console worker and mandatory Apple
/// executable regression. A loop return never grants permission to close disk.
struct LinuxConsoleLifecycle {
    enum Event { case entered, ready, stop, unmounted, loopReturned, failed, timedOut, hostSynced }
    private(set) var entered = false
    private(set) var ready = false
    private(set) var requested = false
    private(set) var unmounted = false
    private(set) var returned = false
    private(set) var failed = false
    private(set) var timedOut = false
    private(set) var clean = false
    var mustRetainDisk: Bool { entered }
    var canStart: Bool { !entered }
    var maySyncForCleanStop: Bool { entered && ready && requested && unmounted && returned && !failed && !timedOut }

    /// A failed host sync is terminal for this session, even if the disk could
    /// be synced later. Queued finalizers must not retry and erase that failure.
    mutating func synchronizeForCleanStop(_ synchronize: () throws -> Void) throws -> Bool {
        guard maySyncForCleanStop, !clean else { return false }
        do {
            try synchronize()
            record(.hostSynced)
            return clean
        } catch {
            record(.failed)
            throw error
        }
    }

    mutating func record(_ event: Event) {
        switch event {
        case .entered: entered = true
        case .ready: if entered && !requested && !returned { ready = true }
        case .stop: requested = true
        case .unmounted: if entered && ready { requested = true; unmounted = true }
        case .loopReturned: returned = true
        case .failed: failed = true; clean = false
        case .timedOut: timedOut = true; clean = false
        case .hostSynced: if maySyncForCleanStop { clean = true }
        }
    }
}

protocol LinuxConsoleDisk: AnyObject {
    var url: URL { get }
    func validateOwnership() throws
    func synchronize() throws
    func closeUnused()
}
extension LinuxTerminalDisk: LinuxConsoleDisk { }
extension LinuxDesktopDisk: LinuxConsoleDisk { }
