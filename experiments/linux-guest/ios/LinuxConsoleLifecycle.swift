import Foundation

/// Cancellation belongs only to preparation, before the native runtime owns
/// anything. The UI and QEMU thread compete through this same lock; a queued
/// cancellation can never tear down a runtime whose entry already won.
final class LinuxStartupPreparation {
    enum Phase: String, CaseIterable {
        case assets, disk, importingSeed = "importing_seed", recoveryCopies = "recovery_copies"
        case arguments, report, nativeEntry = "native_entry"
        var message: String {
            switch self {
            case .assets: return "Verifying app assets and their hashes…"
            case .disk: return "Validating the persistent disk and any checked recovery copy…"
            case .importingSeed: return "Copying and verifying the initial disk…"
            case .recoveryCopies: return "Preparing and verifying separate recovery copies…"
            case .arguments: return "Preparing the console and Linux startup…"
            case .report: return "Saving startup evidence and verifying the executable…"
            case .nativeEntry: return "Finishing safety checks before starting Linux…"
            }
        }
    }
    enum State: Equatable { case preparing, cancellationRequested, entered, finished }
    enum Cancelled: Error { case beforeNativeEntry }
    struct Snapshot {
        let phase: Phase
        let state: State
        var inProgress: Bool { state == .preparing || state == .cancellationRequested }
        var canCancel: Bool { state == .preparing }
        var message: String {
            state == .cancellationRequested
                ? "Cancelling startup after the current file check or copy finishes…" : phase.message
        }
    }
    private let lock = NSLock()
    private var state = State.preparing
    private var phase = Phase.assets
    var snapshot: Snapshot {
        lock.lock(); defer { lock.unlock() }
        return Snapshot(phase: phase, state: state)
    }
    func advance(_ next: Phase) throws {
        lock.lock(); defer { lock.unlock() }
        guard state == .preparing else { throw Cancelled.beforeNativeEntry }
        phase = next
    }
    @discardableResult func requestCancellation() -> Bool {
        lock.lock(); defer { lock.unlock() }
        guard state == .preparing else { return false }
        state = .cancellationRequested
        return true
    }
    /// The one atomic commit point. Once entered, cancellation/finish cannot
    /// reopen preparation or release the native owner; normal Stop takes over.
    func enterNative() -> Bool {
        lock.lock(); defer { lock.unlock() }
        guard state == .preparing else { return false }
        state = .entered
        return true
    }
    func finish() {
        lock.lock(); defer { lock.unlock() }
        if state != .entered { state = .finished }
    }
}

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

/// Screen navigation only. An attempted native environment stays reserved even
/// after Stop/failure; returning Home never grants a second QEMU invocation.
struct LinuxLauncherNavigation {
    enum Destination: String, CaseIterable {
        case choose, linux, terminal, debian, desktop, steam, library, settings, advanced
        var isEnvironment: Bool { ![Self.choose, .settings, .advanced].contains(self) }
    }
    private(set) var destination = Destination.choose
    private(set) var selected: Destination?
    private(set) var owner: Destination?
    mutating func reserve(_ environment: Destination?) {
        if owner == nil, let environment, environment.isEnvironment { owner = environment }
    }
    func allows(_ target: Destination) -> Bool {
        !target.isEnvironment || owner == nil || owner == target
    }
    @discardableResult mutating func open(_ target: Destination) -> Bool {
        guard allows(target) else { return false }
        if target.isEnvironment { selected = target }
        if target == .library { reserve(target) }
        destination = target
        return true
    }
    mutating func home() { destination = .choose }
    mutating func resume() { if let target = owner ?? selected { _ = open(target) } }
}
