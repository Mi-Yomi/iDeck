import SwiftUI
import UIKit

private final class LinuxDesktopKeyView: UIView, UIKeyInput {
    var input: LinuxDesktopInput?
    var available = false
    private let emptyInput = UIView(frame: .zero)
    override var inputView: UIView? { softwareKeyboard ? nil : emptyInput }
    var softwareKeyboard = false {
        didSet { if oldValue != softwareKeyboard { reloadInputViews() } }
    }
    override var canBecomeFirstResponder: Bool { available }
    var hasText: Bool { true }
    var autocapitalizationType: UITextAutocapitalizationType = .none
    var autocorrectionType: UITextAutocorrectionType = .no
    var spellCheckingType: UITextSpellCheckingType = .no
    var smartQuotesType: UITextSmartQuotesType = .no
    var smartDashesType: UITextSmartDashesType = .no
    var smartInsertDeleteType: UITextSmartInsertDeleteType = .no
    var keyboardType: UIKeyboardType = .asciiCapable
    func insertText(_ text: String) { input?.text(text) }
    func deleteBackward() { input?.key("backspace") }
    override func resignFirstResponder() -> Bool { input?.releaseHeld(); return super.resignFirstResponder() }
    override func pressesBegan(_ presses: Set<UIPress>, with event: UIPressesEvent?) { hardware(presses, down: true) }
    override func pressesEnded(_ presses: Set<UIPress>, with event: UIPressesEvent?) { hardware(presses, down: false) }
    override func pressesCancelled(_ presses: Set<UIPress>, with event: UIPressesEvent?) { input?.releaseHeld() }
    private func hardware(_ presses: Set<UIPress>, down: Bool) {
        for press in presses { if let key = press.key { input?.physical(Int(key.keyCode.rawValue), down: down, flags: key.modifierFlags) } }
    }
}

private struct LinuxDesktopKeyboard: UIViewRepresentable {
    let input: LinuxDesktopInput
    let available: Bool
    let show: Bool
    func makeUIView(context: Context) -> LinuxDesktopKeyView {
        let view = LinuxDesktopKeyView(); view.input = input
        return view
    }
    func updateUIView(_ view: LinuxDesktopKeyView, context: Context) {
        view.available = available; view.softwareKeyboard = show
        if available {
            DispatchQueue.main.async { if view.available, view.window != nil, !view.isFirstResponder { _ = view.becomeFirstResponder() } }
        } else if view.isFirstResponder { _ = view.resignFirstResponder() }
    }
    static func dismantleUIView(_ view: LinuxDesktopKeyView, coordinator: ()) { view.input?.releaseHeld(); _ = view.resignFirstResponder() }
}

private struct LinuxDesktopDisplay: UIViewRepresentable {
    let input: LinuxDesktopInput
    func makeUIView(context: Context) -> HuskMetalView {
        let view = HuskMetalView(); view.desktopInput = input; return view
    }
    func updateUIView(_ view: HuskMetalView, context: Context) { view.desktopInput = input }
    static func dismantleUIView(_ view: HuskMetalView, coordinator: ()) { view.desktopInput?.releaseHeld() }
}

struct LinuxDesktopView: View {
    @ObservedObject private var session = LinuxTerminalSession.desktop
    @ObservedObject private var jit = JITCoordinator.shared
    @ObservedObject private var input: LinuxDesktopInput
    @Environment(\.scenePhase) private var phase
    @State private var keyboard = false
    @State private var recovery = false
    @State private var controlsExpanded = false
    @State private var command = ""
    @State private var showDiagnostics = false
    @State private var showShare = false
    @State private var shareItems: [URL] = []
    init(session: LinuxTerminalSession = .desktop) {
        self.session = session
        input = session.desktopInput!
    }

    var body: some View {
        GeometryReader { geometry in
            VStack(spacing: 5) {
                Text(session.isSteam ? "Steam · experimental" : "Debian desktop").font(.headline).frame(maxWidth: .infinity, alignment: .leading)
                Text(session.message).font(.caption).lineLimit(3).frame(maxWidth: .infinity, alignment: .leading)
                if let preparation = session.preparationState, preparation.inProgress {
                    ProgressView(preparation.message).font(.caption)
                    Text("Keep iDeck open. Home preserves this preparation; Cancel start explicitly cancels before native entry.")
                        .font(.caption2).fixedSize(horizontal: false, vertical: true)
                }
                if jit.busy { ProgressView(jit.status ?? "Enabling JIT…") }
                if let error = jit.error { Text(error).font(.caption).foregroundStyle(.orange) }
                if geometry.size.width > geometry.size.height {
                    HStack(alignment: .top, spacing: 8) {
                        display.frame(maxWidth: .infinity, maxHeight: .infinity)
                        ScrollView { controls }.frame(width: 190)
                    }
                } else {
                    display.frame(maxWidth: .infinity, maxHeight: .infinity)
                    ScrollView { controls }.frame(maxHeight: 210)
                }
                if recovery { recoveryConsole }
            }
            .buttonStyle(.bordered).font(.caption).padding(8)
        }
        // Keep export actions outside the geometry/scroll/input subtree. The
        // keyboard may cover guest controls, never this fixed top safe-area bar.
        .safeAreaInset(edge: .top, spacing: 0) { persistentActions }
        .ignoresSafeArea(.keyboard, edges: .bottom)
        .background(LinuxDesktopKeyboard(input: input, available: inputAvailable, show: keyboard).frame(width: 1,height: 1).opacity(0.01))
        .sheet(isPresented: $jit.showSetup) { JITSetupFlow() }
        .sheet(isPresented: $showDiagnostics) { LinuxDesktopDiagnosticsView(session: session) }
        .sheet(isPresented: $showShare) { ShareSheet(items: shareItems) }
        .onAppear { session.recoverDiagnostics(); refreshInputFocus() }
        .onChange(of: recovery) { _ in refreshInputFocus() }
        .onChange(of: showDiagnostics) { _ in refreshInputFocus() }
        .onChange(of: showShare) { _ in refreshInputFocus() }
        .onChange(of: jit.showSetup) { _ in refreshInputFocus() }
        .onDisappear { keyboard = false; input.setFocused(false) }
        .onChange(of: phase) { value in
            if value == .active { session.recoverDiagnostics() }
            if value == .background { session.cancelPreparation() }
            refreshInputFocus()
        }
        .onChange(of: session.ready) { _ in refreshInputFocus() }
        .onChange(of: session.stopping) { _ in refreshInputFocus() }
        .onChange(of: jit.attachGeneration) { _ in jit.refreshPairingStatus(); session.claimJIT() }
    }
    private var inputAvailable: Bool {
        session.ready && !session.stopping && phase == .active && !recovery
            && !showDiagnostics && !showShare && !jit.showSetup
    }
    private var persistentActions: some View {
        HStack(spacing: 8) {
            if session.attempted && !session.ready {
                Button("Share report") {
                    prepareDiagnostics()
                    if let file = session.reportForSharing() { shareItems = [file]; showShare = true }
                    else { showDiagnostics = true }
                }.accessibilityIdentifier("ideck-desktop-share-report")
            }
            Button("Diagnostics") { prepareDiagnostics(); session.recoverDiagnostics(); showDiagnostics = true }
                .accessibilityLabel("Saved startup diagnostics, Markdown")
                .accessibilityIdentifier("ideck-desktop-startup-diagnostics")
            Spacer(minLength: 0)
            if let preparation = session.preparationState, preparation.inProgress {
                Button(preparation.canCancel ? "Cancel start" : "Cancelling…") { session.cancelPreparation() }
                    .disabled(!preparation.canCancel).accessibilityIdentifier("ideck-desktop-cancel-start")
            } else if session.attempted {
                Button("Stop Linux") { session.stop() }.disabled(!session.canStop || session.stopping)
            }
        }
        .buttonStyle(.bordered).font(.caption).lineLimit(1).minimumScaleFactor(0.8)
        .frame(minHeight: 44).padding(.horizontal, 8).padding(.vertical, 4)
        .fixedSize(horizontal: false, vertical: true).background(.ultraThinMaterial)
    }
    private func refreshInputFocus() { input.setFocused(inputAvailable) }
    private func prepareDiagnostics() {
        keyboard = false; input.setFocused(false)
        UIApplication.shared.sendAction(#selector(UIResponder.resignFirstResponder), to: nil, from: nil, for: nil)
    }
    private var display: some View {
        ZStack {
            LinuxDesktopDisplay(input: input)
                .allowsHitTesting(session.ready && !session.stopping && !recovery)
                .accessibilityIdentifier("ideck-debian-desktop-display")
            if !session.ready || !session.displayHasFrame {
                VStack(spacing: 10) {
                    Image(systemName: session.displayTimedOut ? "exclamationmark.display" : "desktopcomputer").font(.largeTitle)
                    if let preparation = session.preparationState, preparation.inProgress {
                        ProgressView(preparation.message)
                    } else {
                        Text(session.message).multilineTextAlignment(.center)
                    }
                    if session.displayTimedOut {
                        Text("Кадр гостя не получен за 60 секунд. Причина не установлена. Сохраните отчёт в Диагностике; Stop остаётся доступен после готовности supervisor.")
                    } else {
                        Text(session.recoveryMode ? "Recovery работает без графического дисплея. Оригинал и резервная копия сохраняются." : session.attempted ? "Ожидаем готовность Linux и кадр гостевого дисплея…" : "Экран настоящей сессии появится после запуска Linux.")
                    }
                    Button("Диагностика / отчёт") { prepareDiagnostics(); session.recoverDiagnostics(); showDiagnostics = true }
                }.font(.callout).padding(20).frame(maxWidth: .infinity, maxHeight: .infinity)
                    .background(Theme.surface.opacity(0.96))
            }
        }.aspectRatio(4.0 / 3.0, contentMode: .fit).background(Color.black)
    }
    private var controls: some View {
        VStack(spacing: 6) {
            if !session.attempted {
                Button("JIT setup") { jit.refreshPairingStatus(); jit.showSetup = true }.disabled(jit.busy)
                Button("Enable JIT") { enableJIT() }.disabled(jit.busy)
                if session.isSteam {
                    Text("Separate 12 GiB disk + 1 GiB free import reserve. Guest: 1536 MiB RAM, 4 vCPUs. Games and iPhone performance are unverified.").font(.caption2)
                    Toggle("Allow Steam network this session", isOn: $session.steamNetworkConsent)
                    Text("Downloads use pinned official Valve/Debian HTTPS. Steam later contacts its services and may update. You handle login and agreements.").font(.caption2)
                    if !session.steamPayloadAvailable {
                        Text("Blocker: sealed Steam seed/bootstrap/profile is missing from this IPA.").foregroundStyle(.orange)
                    }
                }
                Button(session.isSteam ? "Start Steam environment" : "Start desktop") { session.startDesktop() }
                    .disabled(jit.busy || (session.isSteam && (!session.steamPayloadAvailable || !session.steamNetworkConsent)))
            }
            if session.isSteam, session.attempted {
                Text(session.steamMessage).font(.caption2)
                Button("Install / resume Steam") { session.steamAction("INSTALL") }.disabled(!session.ready || session.stopping || session.steamBusy)
                Button("Launch Big Picture") { session.steamAction("BIG_PICTURE") }.disabled(!session.ready || !session.steamInstalled || session.steamBusy || session.stopping)
                Button("Return to Desktop") { session.steamAction("DESKTOP") }.disabled(!session.ready || !session.steamInstalled || session.stopping)
            }
            if session.recoveryMode {
                Text("Separate recovery VM. Creates verified backup/work copies; preserves the original. After completion, close/reopen iDeck before Start desktop.").font(.caption2)
            } else if !session.attempted && !session.isSteam {
                Text("After a blocked unclean disk: Recover disk first. Requires space for two full copies plus 512 MiB reserve.").font(.caption2)
            }
            DisclosureGroup("Управление и клавиатура", isExpanded: $controlsExpanded) {
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 5) {
                Button("Keyboard") { keyboard.toggle() }
                Button("Release keys") { input.releaseHeld() }
                Button("Right click") { input.rightClick() }
                Button("Scroll ↑") { input.scroll(3) }
                Button("Scroll ↓") { input.scroll(-3) }
                ForEach([("Ctrl","ctrl"),("Alt","alt"),("Shift","shift"),("Super","meta_l")], id: \.1) { label, code in
                    Button(label) { input.toggle(code) }.tint(input.latched.contains(code) ? .orange : .accentColor)
                }
            }.disabled(!session.ready || session.stopping || recovery)
            LazyVGrid(columns: Array(repeating: GridItem(.flexible()), count: 3), spacing: 5) {
                ForEach([("Esc","esc"),("Tab","tab"),("Enter","ret"),("←","left"),("↑","up"),("→","right"),
                         ("⌫","backspace"),("↓","down"),("Del","delete"),("Home","home"),("End","end"),
                         ("PgUp","pgup"),("PgDn","pgdn")], id: \.1) { label, code in Button(label) { input.key(code) } }
                ForEach(1...12, id: \.self) { n in Button("F\(n)") { input.key("f\(n)") } }
            }.disabled(!session.ready || session.stopping || recovery)
            }
            Text(input.message).font(.caption2).foregroundStyle(.secondary)
            DisclosureGroup("Дополнительно") {
                Button(recovery ? "Hide recovery" : "Serial recovery") { recovery.toggle() }
            }
        }
    }
    private var recoveryConsole: some View {
        VStack {
            ScrollView([.horizontal,.vertical]) { Text(session.transcript).font(.system(.caption2, design: .monospaced)).textSelection(.enabled) }
                .frame(maxHeight: 100)
            HStack {
                TextField("Recovery console command", text: $command).textInputAutocapitalization(.never).autocorrectionDisabled()
                Button("Send to serial") { session.sendLine(command); command = "" }.disabled(!session.serialReady || session.stopping)
            }
        }
    }
    private func enableJIT() {
        guard !session.attempted, !jit.busy, session.noteJITEnable() else { return }
        jit.refreshPairingStatus()
        if jit.method == .automatic, HuskBuiltInJIT.isAvailable { jit.method = .builtIn }
        jit.enable(); _ = session.noteJITEnable(dispatched: true)
    }
}

/// Independent of guest readiness/JIT and the clipped display/input layout.
/// Only allowlisted MD exports are offered; raw disk/user files are not read.
struct LinuxDesktopDiagnosticsView: View {
    @ObservedObject var session: LinuxTerminalSession
    @Environment(\.dismiss) private var dismiss
    @State private var shareItems: [URL] = []
    @State private var showShare = false
    var body: some View {
        NavigationView {
            List {
                Section("Startup status") {
                    Text(session.message).textSelection(.enabled)
                    if let error = session.exportError { Text(error).foregroundStyle(.orange) }
                    if let error = session.diagnosticsError { Text(error).foregroundStyle(.orange) }
                }
                if session.isDesktop && !session.isSteam && !session.attempted {
                    Section("GUI recovery") {
                        Text("Preserves the original with verified backup/work copies. Requires two full copies plus 512 MiB reserve and a new process before activation.")
                        Button("Recover GUI disk") { session.startRecovery() }
                    }
                }
                Section("Session report (.md)") {
                    if let file = session.markdownFile { ShareLink("Share session report (.md)", item: file) }
                    else { Text("No session report yet. Saved startup reports below can cover a blocked start.") }
                }
                Section("Saved startup diagnostics (.md)") {
                    Button("Refresh saved reports") { session.recoverDiagnostics() }
                    Text(session.diagnosticsMessage)
                    ForEach(Array(session.diagnosticReports.enumerated()), id: \.element) { index, file in
                        ShareLink("Startup report \(index + 1) (.md)", item: file)
                        Button("Native log summary \(index + 1) (.md)") {
                            guard let file = session.exportNativeDiagnostics(for: file) else { return }
                            shareItems = [file]; showShare = true
                        }
                    }
                }
                Text("Reports contain known startup metadata and recognized log signatures. User-file contents and arbitrary log text are excluded.").font(.footnote)
            }
            .navigationTitle("Diagnostics").navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Done") { dismiss() } } }
        }
        .navigationViewStyle(.stack)
        .sheet(isPresented: $showShare) { ShareSheet(items: shareItems) }
        .onAppear { session.recoverDiagnostics() }
    }
}
