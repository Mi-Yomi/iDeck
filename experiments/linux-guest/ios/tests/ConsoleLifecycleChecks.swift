import Foundation
#if canImport(Darwin)
import Darwin
#else
import Glibc
#endif

/// A real Foundation worker with native pthread TLS. The destructor ends this
/// isolated test process if the worker exits. No QEMU registration is faked.
func runQEMUOwnerLifetimeChild(retain: Bool) -> Never {
    var key = pthread_key_t()
    precondition(pthread_key_create(&key, { _ in _exit(42) }) == 0)
    let tlsKey = key
    let entered = DispatchSemaphore(value: 0)
    let worker = Thread {
        precondition(pthread_setspecific(tlsKey, UnsafeMutableRawPointer(bitPattern: 1)) == 0)
        if retain {
            LinuxQEMUThreadLifetime.retainCurrentThread { entered.signal() }
        }
        entered.signal()
    }
    worker.start()
    precondition(entered.wait(timeout: .now() + 5) == .success)
    if !retain { dispatchMain() } // Negative control must reach the TLS destructor.
    worker.cancel() // A UI cancellation must not reclaim the native owner.
    let queue = DispatchQueue(label: "ideck.lifetime.regression")
    for _ in 0..<10000 {
        queue.sync { precondition(!worker.isFinished) }
    }
    // Process exit, not a release hook on the production lifetime helper.
    _exit(0)
}

func runQEMUOwnerLifetimeChecks() throws {
    let cases: [(String, Int32)] = [("exit-control", 42), ("retain", 0)]
    for (mode, expected) in cases {
        let child = Process()
        let ended = DispatchSemaphore(value: 0)
        child.executableURL = URL(fileURLWithPath: CommandLine.arguments[0])
        child.arguments = ["--qemu-owner-lifetime", mode]
        child.terminationHandler = { _ in ended.signal() }
        try child.run()
        guard ended.wait(timeout: .now() + 10) == .success else {
            child.terminate()
            preconditionFailure("QEMU owner lifetime regression timed out")
        }
        child.waitUntilExit()
        precondition(child.terminationReason == .exit && child.terminationStatus == expected)
    }
    print("LINUX_QEMU_OWNER_LIFETIME_PASS (production wait; real Foundation/pthread TLS; no QEMU/device run)")
}

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
    try runQEMUOwnerLifetimeChecks()
    try runStartupPreparationChecks()
    runLauncherNavigationChecks()
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

/// Exercise the production atomic gate, not a surrogate lifecycle model. The
/// concurrent race must have exactly one winner, including a late UI cancel.
func runStartupPreparationChecks() throws {
    for phase in LinuxStartupPreparation.Phase.allCases {
        let preparation = LinuxStartupPreparation()
        try preparation.advance(phase)
        precondition(preparation.snapshot.phase == phase && preparation.snapshot.canCancel)
        precondition(!preparation.snapshot.message.isEmpty)
        precondition(preparation.requestCancellation())
        precondition(!preparation.requestCancellation(), "duplicate tap must not enqueue another cancellation")
        precondition(preparation.snapshot.inProgress && !preparation.snapshot.canCancel)
        precondition(!preparation.enterNative(), "cancel won before native entry")
        do {
            try preparation.advance(.nativeEntry)
            preconditionFailure("cancelled startup advanced")
        } catch LinuxStartupPreparation.Cancelled.beforeNativeEntry { }
        preparation.finish()
        precondition(!preparation.snapshot.inProgress && !preparation.enterNative())
        precondition(!preparation.requestCancellation(), "finished preparation cannot reopen")
    }
    let native = LinuxStartupPreparation()
    precondition(native.enterNative())
    precondition(!native.requestCancellation(), "after entry only normal Stop may act")
    native.finish()
    precondition(native.snapshot.state == .entered && !native.enterNative())
    for _ in 0..<100 {
        let preparation = LinuxStartupPreparation()
        let resultLock = NSLock()
        var entered = false, cancelled = false
        DispatchQueue.concurrentPerform(iterations: 2) { index in
            let result = index == 0 ? preparation.enterNative() : preparation.requestCancellation()
            resultLock.lock(); defer { resultLock.unlock() }
            if index == 0 { entered = result } else { cancelled = result }
        }
        precondition(entered != cancelled, "entry and cancellation must never both succeed")
        precondition(!preparation.enterNative() && !preparation.requestCancellation())
        preparation.finish()
        precondition(preparation.snapshot.state == (entered ? .entered : .finished))
    }
    print("LINUX_STARTUP_PREPARATION_PASS (production lock/gate, repeated taps and concurrent entry/cancel; no QEMU/device run)")
}

func runLauncherNavigationChecks() {
    for environment in [LinuxLauncherNavigation.Destination.steam, .desktop, .terminal, .debian, .linux, .library] {
        var navigation = LinuxLauncherNavigation()
        precondition(navigation.open(environment))
        // Preparing, failed, recovery and stopped sessions keep the same owner.
        navigation.reserve(environment)
        for _ in 0..<20 {
            navigation.home()
            precondition(navigation.destination == .choose && navigation.owner == environment)
            precondition(navigation.open(.settings))
            precondition(navigation.open(.advanced))
            navigation.home(); navigation.resume()
            precondition(navigation.destination == environment)
            precondition(navigation.open(environment))
            for other in LinuxLauncherNavigation.Destination.allCases where other.isEnvironment && other != environment {
                precondition(!navigation.open(other))
                precondition(navigation.destination == environment)
            }
        }
        navigation.reserve(nil)
        precondition(navigation.owner == environment, "Stop/failure cannot grant a second native entry")
    }
    var beforeStart = LinuxLauncherNavigation()
    precondition(beforeStart.open(.steam))
    beforeStart.home()
    precondition(beforeStart.open(.desktop), "profile choice can change before any attempt")
    beforeStart.reserve(.desktop)
    beforeStart.home(); beforeStart.resume()
    precondition(beforeStart.destination == .desktop)
    print("LINUX_LAUNCHER_NAVIGATION_PASS (Home/resume, repeated taps, sticky attempted owner; no VM entry)")
}
