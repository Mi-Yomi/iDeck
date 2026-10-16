import Foundation

/// Executes the production Stop decision, including reordered callbacks. The
/// QEMU engine itself is not simulated here; full app sources use the real SDK.
func runConsoleLifecycleChecks() {
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
        state.record(.hostSynced)
        precondition(state.clean && !state.canStart && state.mustRetainDisk)
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
