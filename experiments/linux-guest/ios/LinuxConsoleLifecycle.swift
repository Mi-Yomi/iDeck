import Foundation

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
