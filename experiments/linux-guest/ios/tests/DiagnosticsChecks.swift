import Foundation
#if canImport(Darwin)
import Darwin
#else
import Glibc
#endif

/// Real file IO/process interruption tests of the same helper shipped in the
/// app. No JIT/QEMU/device implementation is substituted or executed.
func runDiagnosticInterruptionChild(_ documents: URL) throws -> Never {
    let store = try LinuxTerminalDiagnostics(documents: documents)
    let journal = try store.begin(source: String(repeating: "a", count: 40), build: "119")
    try journal.record(.startRequested)
    try journal.record(.qemuInitBegin)
    // Deliberately bypass Swift destructors, as a native exit would. The
    // journal must already be synchronized before record() returned.
    _exit(23)
}

func runDiagnosticFIFOChild(_ documents: URL, nativeLog: Bool) throws -> Never {
    let store = try LinuxTerminalDiagnostics(documents: documents)
    do {
        if nativeLog {
            guard let previous = try store.recover().first else { _exit(25) }
            try store.preservePreviousLogs(id: previous.id)
        } else { _ = try store.recover() }
    } catch LinuxTerminalDiagnostics.Problem.metadata { _exit(24) }
    _exit(25)
}

func runTerminalDiagnosticsChecks() throws {
    let manager = FileManager.default
    let suite = manager.temporaryDirectory.appendingPathComponent("ideck-diagnostic-checks-" + UUID().uuidString)
    try manager.createDirectory(at: suite, withIntermediateDirectories: true)
    defer { try? manager.removeItem(at: suite) }
    func check(_ condition: Bool, _ message: String) { precondition(condition, "Terminal diagnostics: " + message) }
    func documents(_ name: String) throws -> URL {
        let url = suite.appendingPathComponent(name)
        try manager.createDirectory(at: url, withIntermediateDirectories: true)
        return url
    }
    func expect(_ problem: LinuxTerminalDiagnostics.Problem, _ body: () throws -> Void) {
        do { try body(); preconditionFailure("unsafe diagnostic input accepted") }
        catch let found as LinuxTerminalDiagnostics.Problem {
            check(String(describing: found) == String(describing: problem), "expected exact diagnostic error")
        } catch { preconditionFailure("unexpected diagnostic error type") }
    }
    func rawURL(_ store: LinuxTerminalDiagnostics, _ id: String) -> URL {
        store.directory.appendingPathComponent("attempt-" + id + ".jsonl")
    }
    func append(_ bytes: Data, to file: URL) throws {
        let handle = try FileHandle(forWritingTo: file)
        defer { try? handle.close() }
        try handle.seekToEnd(); try handle.write(contentsOf: bytes); try handle.synchronize()
    }

    let docs = try documents("interruption")
    let empty = try LinuxTerminalDiagnostics(documents: docs)
    check(try empty.recover().isEmpty, "export/recovery before any start has no attempt or VM side effect")
    let process = Process()
    process.executableURL = URL(fileURLWithPath: CommandLine.arguments[0])
    process.arguments = ["--diagnostic-interruption", docs.path]
    try process.run(); process.waitUntilExit()
    check(process.terminationStatus == 23, "actual child native exit after synchronous checkpoint")
    let relaunched = try LinuxTerminalDiagnostics(documents: docs)
    let previous = try relaunched.recover()
    check(previous.count == 1, "recover previous process without starting anything")
    let interrupted = previous[0]
    check(interrupted.records.last?.stage == .qemuInitBegin && !interrupted.clean, "last checkpoint survives process exit")
    let exported = try relaunched.export(interrupted, previousProcess: true)
    let markdown = try String(contentsOf: exported, encoding: .utf8)
    check(markdown.contains("Previous process ended without a confirmed clean stop. Cause UNKNOWN."), "interruption is not a crash diagnosis")
    check(markdown.contains("qemuInitBegin"), "checkpoint is useful without native stack")
    check(markdown.contains("Jetsam/SIGKILL") && markdown.contains("not accessible"), "limits are explicit")
    let exportedBytes = try Data(contentsOf: exported)
    for _ in 0..<3 {
        let again = try LinuxTerminalDiagnostics(documents: docs)
        let recovered = try again.recover()
        check(recovered.count == 1, "repeated relaunch/export never creates or deletes attempts")
        _ = try again.export(recovered[0], previousProcess: true)
        check(try Data(contentsOf: exported) == exportedBytes, "repeated report remains stable")
    }
    let oldBytes = try Data(contentsOf: rawURL(relaunched, interrupted.id))
    let newAttempt = try relaunched.begin(source: String(repeating: "b", count: 40), build: "120")
    try newAttempt.record(.startRequested)
    check(newAttempt.id != interrupted.id, "new UUID preserves previous attempt")
    check(try Data(contentsOf: rawURL(relaunched, interrupted.id)) == oldBytes, "previous journal never overwritten")

    let torn = try LinuxTerminalDiagnostics(documents: documents("torn"))
    let tornJournal = try torn.begin(source: "UNKNOWN", build: "UNKNOWN")
    try tornJournal.record(.qemuInitBegin)
    try append(Data("{\"schema\":1,\"stage\":\"cleanStopped\"".utf8), to: rawURL(torn, tornJournal.id))
    let tornSnapshot = try torn.snapshot(id: tornJournal.id)
    check(tornSnapshot.tornTail && !tornSnapshot.clean && tornSnapshot.records.last?.stage == .qemuInitBegin,
          "torn final record preserves earlier complete checkpoints")

    let malformed = try LinuxTerminalDiagnostics(documents: documents("malformed"))
    let malformedJournal = try malformed.begin(source: "UNKNOWN", build: "UNKNOWN")
    try append(Data("{not-json}\n".utf8), to: rawURL(malformed, malformedJournal.id))
    check(try malformed.snapshot(id: malformedJournal.id).invalid, "malformed complete record cannot establish success")
    try Data(repeating: 120, count: LinuxTerminalDiagnostics.maximumBytes + 1).write(to: rawURL(malformed, malformedJournal.id))
    let oversized = try malformed.snapshot(id: malformedJournal.id)
    check(oversized.invalid && oversized.records.isEmpty && !oversized.clean, "oversized reads bounded and invalid")

    let cleanStore = try LinuxTerminalDiagnostics(documents: documents("clean"))
    let clean = try cleanStore.begin(source: "UNKNOWN", build: "1")
    for stage in [LinuxTerminalDiagnostics.Stage.startRequested, .guestCleanUnmount, .mainLoopReturned, .hostDiskSynced, .cleanStopped] {
        try clean.record(stage)
    }
    check(try clean.snapshot().clean, "clean result requires all three runtime conditions recorded")
    check(try clean.snapshot().markdown(previousProcess: true).contains("Confirmed orderly stop"), "clean receipt stays distinct on relaunch")
    let forged = try cleanStore.begin(source: "UNKNOWN", build: "1")
    try forged.record(.cleanStopped)
    check(try !forged.snapshot().clean, "a lone clean marker must never claim orderly stop")

    let rejected = try cleanStore.begin(source: "UNKNOWN", build: "1")
    try rejected.record(.startRequested); try rejected.record(.startRejected)
    check(try rejected.snapshot().markdown(previousProcess: true).contains("Start was rejected before VM entry"),
          "normal JIT rejection is not labeled an interrupted VM")
    let preflight = try cleanStore.begin(source: "UNKNOWN", build: "1")
    try preflight.record(.jitClaimBegin)
    check(try preflight.snapshot().markdown(previousProcess: true).contains("no VM start request was recorded"),
          "interrupted JIT claim before Start is distinct from VM interruption")

    let concurrent = try LinuxTerminalDiagnostics(documents: documents("concurrent"))
    let shared = try concurrent.begin(source: "UNKNOWN", build: "1")
    DispatchQueue.concurrentPerform(iterations: 32) { _ in
        do { try shared.record(.assetsBegin) } catch { preconditionFailure("concurrent diagnostic write failed") }
    }
    let ordered = try shared.snapshot()
    check(ordered.records.count == 33 && !ordered.invalid && !ordered.tornTail, "concurrent writes serialize complete records")
    check(ordered.records.map(\.sequence) == Array(0..<33), "sequence reflects synchronized append order")

    let broken = try LinuxTerminalDiagnostics(documents: documents("sync-failure"), synchronize: { _ in -1 })
    expect(.synchronize) { _ = try broken.begin(source: "UNKNOWN", build: "1") }
    let exportBroken = try LinuxTerminalDiagnostics(documents: docs, synchronize: { _ in -1 })
    expect(.synchronize) { _ = try exportBroken.export(interrupted, previousProcess: true) }
    check(try Data(contentsOf: exported) == exportedBytes, "failed export never publishes truncated Markdown")

    let linkedDocs = try documents("linked-root")
    let outside = try documents("outside")
    try manager.createSymbolicLink(at: linkedDocs.appendingPathComponent("iDeckDiagnostics"), withDestinationURL: outside)
    expect(.directory) { _ = try LinuxTerminalDiagnostics(documents: linkedDocs) }
    let links = try LinuxTerminalDiagnostics(documents: documents("linked-leaf"))
    let linkedJournal = try links.begin(source: "UNKNOWN", build: "1")
    let journalURL = rawURL(links, linkedJournal.id)
    try manager.removeItem(at: journalURL)
    let privateFile = outside.appendingPathComponent("private")
    let secret = "TOKEN-example /private/var/mobile/Containers/private ``` <script>"
    try Data(secret.utf8).write(to: privateFile)
    try manager.createSymbolicLink(at: journalURL, withDestinationURL: privateFile)
    expect(.open) { _ = try links.snapshot(id: linkedJournal.id) }
    expect(.invalid) { _ = try links.snapshot(id: "../private") }
    check(try String(contentsOf: privateFile, encoding: .utf8) == secret, "unsafe files never modified")

    let nativeDocs = try documents("native")
    let native = try LinuxTerminalDiagnostics(documents: nativeDocs)
    let nativeAttempt = try native.begin(source: secret, build: secret)
    try nativeAttempt.record(.qemuInitBegin)
    try Data(secret.utf8).write(to: nativeDocs.appendingPathComponent("husk-native-prev.log"))
    try Data("previous app log".utf8).write(to: nativeDocs.appendingPathComponent("husk-prev.log"))
    try native.preservePreviousLogs(id: nativeAttempt.id)
    let snapshot = try native.snapshot(id: nativeAttempt.id)
    check(snapshot.nativeBytes == secret.utf8.count && snapshot.appLogBytes != nil, "native stderr/app logs preserved locally")
    let privateMarkdown = snapshot.markdown(previousProcess: true)
    check(!privateMarkdown.contains(secret) && !privateMarkdown.contains("TOKEN-example") && !privateMarkdown.contains("/private/var"),
          "Markdown excludes arbitrary logs, metadata injection and personal paths")
    try Data("rotated later launch".utf8).write(to: nativeDocs.appendingPathComponent("husk-native-prev.log"))
    try native.preservePreviousLogs(id: nativeAttempt.id)
    check(try native.snapshot(id: nativeAttempt.id).nativeBytes == snapshot.nativeBytes, "relaunch cannot overwrite first captured evidence")

    let absentDocs = try documents("absent-native")
    let absent = try LinuxTerminalDiagnostics(documents: absentDocs)
    let absentAttempt = try absent.begin(source: "UNKNOWN", build: "1")
    try absent.preservePreviousLogs(id: absentAttempt.id)
    try Data("unrelated later launch".utf8).write(to: absentDocs.appendingPathComponent("husk-native-prev.log"))
    try absent.preservePreviousLogs(id: absentAttempt.id)
    check(try absent.snapshot(id: absentAttempt.id).nativeBytes == nil, "missing original logs never filled by a later unrelated launch")
    check(snapshot.markdown(previousProcess: true).contains("Native log association | UNKNOWN"), "rotating-log association is never claimed proven")

    // The explicit manual summary exports only fixed labels, never source
    // substrings/captures. Include paths, credentials and Markdown injection on
    // the SAME recognized line to guard against unsafe partial-line redaction.
    let summaryDocs = try documents("native-summary")
    let summaryStore = try LinuxTerminalDiagnostics(documents: summaryDocs)
    let summaryAttempt = try summaryStore.begin(source: String(repeating: "c", count: 40), build: "119")
    try summaryAttempt.record(.qemuInitBegin)
    let summaryID = summaryAttempt.id
    let nativeURL = summaryStore.directory.appendingPathComponent("attempt-" + summaryID + ".native.txt")
    let appURL = summaryStore.directory.appendingPathComponent("attempt-" + summaryID + ".app.txt")
    let leak = "PAIRING_TOKEN=do-not-share /private/var/mobile/secret /Users/Owner ``` <script>"
    var nativeRaw = Data(("[husk-jit] prewarm OK: 536870912 bytes " + leak + "\n" +
                          "Failed to create chardev: " + leak + "\n" +
                          "qemu-system-aarch64: userdata: Failed to lock byte 100. " + leak + "\n" +
                          "unknown raw line " + leak + "\n" + String(repeating: "x", count: 2049) + "\n").utf8)
    nativeRaw.append(contentsOf: [255, 254, 10])
    let appRaw = Data(("Assertion failed: " + leak + "\n").utf8)
    try nativeRaw.write(to: nativeURL); try appRaw.write(to: appURL)
    let summarySnapshot = try summaryStore.snapshot(id: summaryID)
    let unchangedJournal = try Data(contentsOf: rawURL(summaryStore, summaryID))
    let primary = try summaryStore.export(summarySnapshot, previousProcess: true)
    let primaryBytes = try Data(contentsOf: primary)
    var safeSummaryURL: URL?
    for _ in 0..<3 {
        let url = try summaryStore.exportNativeSummary(summarySnapshot, previousProcess: true)
        safeSummaryURL = url
        let text = try String(contentsOf: url, encoding: .utf8)
        check(text.contains("JIT prewarm OK text") && text.contains("QEMU chardev creation failure text") && text.contains("Native assertion text"),
              "recognized native text yields useful fixed labels")
        check(text.contains("KNOWN ERROR: QEMU block byte 100 lock conflict text (association UNKNOWN)"),
              "exact byte100 failure is recognized without source values or cause attribution")
        for forbidden in ["PAIRING_TOKEN", "do-not-share", "/private/var", "/Users/Owner", "<script>", "```", "536870912", "unknown raw line"] {
            check(!text.contains(forbidden), "arbitrary sensitive text never reaches native Markdown")
        }
        check(text.contains("Association UNKNOWN") && text.contains("does not identify the cause"), "native signature is not an attributed crash cause")
        check(text.contains("Omitted/unrecognized lines:"), "unknown/invalid UTF8/oversized lines are explicitly omitted")
        check(try Data(contentsOf: nativeURL) == nativeRaw && Data(contentsOf: appURL) == appRaw, "summary never changes raw snapshot bytes")
        check(try Data(contentsOf: rawURL(summaryStore, summaryID)) == unchangedJournal, "manual export never appends or replaces startup journal")
        check(try Data(contentsOf: primary) == primaryBytes, "native export never replaces original checkpoint Markdown")
    }
    let safeSummary = safeSummaryURL!
    let safeBytes = try Data(contentsOf: safeSummary)
    try manager.removeItem(at: nativeURL)
    try manager.createSymbolicLink(at: nativeURL, withDestinationURL: privateFile)
    expect(.open) { _ = try summaryStore.exportNativeSummary(summarySnapshot, previousProcess: true) }
    check(try Data(contentsOf: safeSummary) == safeBytes, "failed manual export never publishes partial or unsafe Markdown")
    try manager.removeItem(at: nativeURL)
    try Data(repeating: 120, count: 1024 * 1024 + 1).write(to: nativeURL)
    expect(.limit) { _ = try summaryStore.exportNativeSummary(summarySnapshot, previousProcess: true) }
    let absentSummary = try absent.exportNativeSummary(absent.snapshot(id: absentAttempt.id), previousProcess: true)
    let absentText = try String(contentsOf: absentSummary, encoding: .utf8)
    check(absentText.contains("Snapshot NOT AVAILABLE") && !absentText.contains("unrelated later launch"),
          "manual summary never substitutes rotating logs for absent snapshots")

    // Run FIFO regressions in bounded child processes: the old blocking open
    // would hang, and must fail this check instead of hanging the entire gate.
    for nativeLog in [false, true] {
        let fifoDocs = try documents(nativeLog ? "native-fifo" : "journal-fifo")
        let fifoStore = try LinuxTerminalDiagnostics(documents: fifoDocs)
        let fifoJournal = try fifoStore.begin(source: "UNKNOWN", build: "1")
        let fifoPath = nativeLog ? fifoDocs.appendingPathComponent("husk-native-prev.log") : rawURL(fifoStore, fifoJournal.id)
        if !nativeLog { try manager.removeItem(at: fifoPath) }
        check(mkfifo(fifoPath.path, mode_t(0o600)) == 0, "create actual FIFO fixture")
        let child = Process()
        child.executableURL = URL(fileURLWithPath: CommandLine.arguments[0])
        child.arguments = [nativeLog ? "--diagnostic-native-fifo" : "--diagnostic-fifo", fifoDocs.path]
        let finished = DispatchSemaphore(value: 0)
        child.terminationHandler = { _ in finished.signal() }
        try child.run()
        let timedOut = finished.wait(timeout: .now() + 5) == .timedOut
        if timedOut { child.terminate() }
        child.waitUntilExit()
        check(!timedOut && child.terminationStatus == 24, "FIFO rejected without blocking recovery/export")
    }

    let limited = try LinuxTerminalDiagnostics(documents: documents("limit"))
    let limitedJournal = try limited.begin(source: "UNKNOWN", build: "1")
    for _ in 1..<LinuxTerminalDiagnostics.maximumRecords { try limitedJournal.record(.jitClaimReturned) }
    expect(.limit) { try limitedJournal.record(.qemuInitBegin) }
    check(try limitedJournal.snapshot().records.count == LinuxTerminalDiagnostics.maximumRecords, "journal bound does not discard previous evidence")
    print("LINUX_TERMINAL_DIAGNOSTICS_CHECKS_PASS (actual journal/process interruption/export; no guest/device execution)")
}
