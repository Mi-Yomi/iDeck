import Foundation

/// Run against both real disk owners, before their independent-process lock
/// contenders. Only the first sync error is injected; the next sync is real.
func runConsoleHostSyncFailureCheck(disk: LinuxConsoleDisk) throws {
    enum Injected: Error { case hostSync }
    for order: [LinuxConsoleLifecycle.Event] in [[.unmounted, .loopReturned], [.loopReturned, .unmounted]] {
        var state = LinuxConsoleLifecycle()
        state.record(.entered); state.record(.ready); state.record(.stop)
        for event in order { state.record(event) }
        var attempts = 0
        func synchronize() throws {
            attempts += 1
            if attempts == 1 { throw Injected.hostSync }
            try disk.synchronize()
        }
        do {
            _ = try state.synchronizeForCleanStop(synchronize)
            preconditionFailure("first host sync must fail")
        } catch Injected.hostSync { }
        precondition(state.failed && !state.clean && state.mustRetainDisk && !state.canStart)
        try disk.validateOwnership()

        // An already queued finalize cannot retry the failed sync.
        let retried = try state.synchronizeForCleanStop(synchronize)
        precondition(!retried && attempts == 1)
        // Even an independently successful later fsync/stale success callback
        // cannot promote this failed session to clean.
        try synchronize()
        precondition(attempts == 2)
        state.record(.hostSynced)
        let finalized = try state.synchronizeForCleanStop(synchronize)
        precondition(!finalized && attempts == 2 && state.failed && !state.clean)
        precondition(!state.maySyncForCleanStop && state.mustRetainDisk && !state.canStart)
        try disk.validateOwnership()
    }
}

/// Executes the production Stop decision, including reordered callbacks. The
/// QEMU engine itself is not simulated here; full app sources use the real SDK.
func runConsoleLifecycleChecks() throws {
    func prepared() -> LinuxConsoleLifecycle {
        var state = LinuxConsoleLifecycle()
        precondition(state.canStart && !state.mustRetainDisk)
        state.record(.entered); state.record(.ready)
        precondition(!state.canStart && state.mustRetainDisk)
        return state
    }
    for order: [LinuxConsoleLifecycle.Event] in [[.stop, .unmounted, .loopReturned], [.stop, .loopReturned, .unmounted]] {
        var state = prepared()
        for event in order { state.record(event); precondition(!state.clean && state.mustRetainDisk) }
        precondition(state.maySyncForCleanStop)
        var attempts = 0
        let finalized = try state.synchronizeForCleanStop { attempts += 1 }
        precondition(finalized && state.clean && !state.canStart && state.mustRetainDisk)
        let repeated = try state.synchronizeForCleanStop { attempts += 1 }
        precondition(!repeated && attempts == 1 && state.clean && state.mustRetainDisk)
    }
    for failure: LinuxConsoleLifecycle.Event in [.failed, .timedOut] {
        for position in 0...3 {
            var state = prepared()
            let events: [LinuxConsoleLifecycle.Event] = [.stop, .unmounted, .loopReturned]
            for index in 0...3 {
                if index == position { state.record(failure) }
                if index < 3 { state.record(events[index]) }
            }
            state.record(.hostSynced)
            precondition(!state.clean && !state.maySyncForCleanStop && state.mustRetainDisk && !state.canStart)
        }
    }
    var returnedOnly = prepared()
    returnedOnly.record(.loopReturned); returnedOnly.record(.hostSynced)
    precondition(!returnedOnly.clean && returnedOnly.mustRetainDisk)
    var unmountedOnly = prepared()
    unmountedOnly.record(.unmounted); unmountedOnly.record(.hostSynced)
    precondition(!unmountedOnly.clean && unmountedOnly.mustRetainDisk)
    var beforeReady = LinuxConsoleLifecycle()
    beforeReady.record(.entered); beforeReady.record(.unmounted); beforeReady.record(.loopReturned)
    beforeReady.record(.hostSynced)
    precondition(!beforeReady.clean && beforeReady.mustRetainDisk)
    print("LINUX_CONSOLE_RUNTIME_REGRESSION_PASS (production lifecycle; backend cleanup NOT assumed)")
}
