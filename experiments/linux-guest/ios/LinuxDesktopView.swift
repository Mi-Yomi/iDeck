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
    @State private var command = ""
    init(session: LinuxTerminalSession = .desktop) {
        self.session = session
        input = session.desktopInput!
    }

    var body: some View {
        GeometryReader { geometry in
            VStack(spacing: 5) {
                HStack {
                    Text(session.isSteam ? "Steam · experimental" : "Debian desktop").font(.headline)
                    Spacer()
                    if session.attempted { Button("Stop Linux") { session.stop() }.disabled(!session.canStop || session.stopping) }
                }
                Text(session.message).font(.caption).frame(maxWidth: .infinity, alignment: .leading)
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
        .background(LinuxDesktopKeyboard(input: input, available: session.ready && !session.stopping && phase == .active && !recovery, show: keyboard).frame(width: 1,height: 1).opacity(0.01))
        .sheet(isPresented: $jit.showSetup) { JITSetupFlow() }
        .onAppear { session.recoverDiagnostics(); input.setFocused(session.ready && phase == .active && !recovery) }
        .onChange(of: recovery) { input.setFocused(!$0 && session.ready && phase == .active && !session.stopping) }
        .onDisappear { input.setFocused(false) }
        .onChange(of: phase) { input.setFocused($0 == .active && session.ready && !session.stopping && !recovery) }
        .onChange(of: session.ready) { input.setFocused($0 && phase == .active && !session.stopping && !recovery) }
        .onChange(of: jit.attachGeneration) { _ in jit.refreshPairingStatus(); session.claimJIT() }
    }
    private var display: some View {
        LinuxDesktopDisplay(input: input)
            .aspectRatio(4.0 / 3.0, contentMode: .fit)
            .allowsHitTesting(session.ready && !session.stopping && !recovery)
            .accessibilityIdentifier("ideck-debian-desktop-display")
            .background(Color.black)
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
                Button(session.isSteam ? "Start Steam environment" : "Start desktop") { session.start() }
                    .disabled(jit.busy || (session.isSteam && (!session.steamPayloadAvailable || !session.steamNetworkConsent)))
            }
            if session.isSteam, session.attempted {
                Text(session.steamMessage).font(.caption2)
                Button("Install / resume Steam") { session.steamAction("INSTALL") }.disabled(!session.ready || session.stopping || session.steamBusy)
                Button("Launch Big Picture") { session.steamAction("BIG_PICTURE") }.disabled(!session.ready || !session.steamInstalled || session.steamBusy || session.stopping)
                Button("Return to Desktop") { session.steamAction("DESKTOP") }.disabled(!session.ready || !session.steamInstalled || session.stopping)
            }
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
            Text(input.message).font(.caption2).foregroundStyle(.secondary)
            Button(recovery ? "Hide recovery" : "Serial recovery") { recovery.toggle() }
            if let file = session.markdownFile { ShareLink(item: file) { Text("Share report") } }
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
