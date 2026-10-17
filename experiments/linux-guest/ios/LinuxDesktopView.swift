import SwiftUI
import UIKit

private final class LinuxDesktopKeyAccessory: UIInputView {
    override var intrinsicContentSize: CGSize { CGSize(width: UIView.noIntrinsicMetric, height: 100) }
}

private final class LinuxDesktopKeyView: UIView, UIKeyInput {
    var input: LinuxDesktopInput?
    var hideKeyboard: (() -> Void)?
    var available = false { didSet { refreshAccessory() } }
    private var accessoryButtons: [UIButton] = []
    private var modifierButtons: [String: UIButton] = [:]
    private lazy var keyAccessory = makeAccessory()
    private let emptyInput = UIView(frame: .zero)
    override var inputView: UIView? { softwareKeyboard ? nil : emptyInput }
    override var inputAccessoryView: UIView? { softwareKeyboard ? keyAccessory : nil }
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
    private func accessoryButton(_ title: String, code: String, label: String? = nil,
                                 action: @escaping (LinuxDesktopKeyView) -> Void) -> UIButton {
        let button = UIButton(type: .system)
        button.setTitle(title, for: .normal)
        button.titleLabel?.font = .preferredFont(forTextStyle: .caption1)
        button.titleLabel?.adjustsFontForContentSizeCategory = true
        button.titleLabel?.adjustsFontSizeToFitWidth = true
        button.titleLabel?.minimumScaleFactor = 0.75
        button.accessibilityLabel = label ?? title
        button.accessibilityIdentifier = "ideck-desktop-accessory-\(code)"
        button.layer.cornerRadius = 6
        button.addAction(UIAction { [weak self] _ in
            guard let self else { return }
            action(self); self.refreshAccessory()
        }, for: .touchUpInside)
        accessoryButtons.append(button)
        return button
    }
    private func makeAccessory() -> UIInputView {
        let bar = LinuxDesktopKeyAccessory(frame: CGRect(x: 0, y: 0, width: 320, height: 100), inputViewStyle: .keyboard)
        bar.autoresizingMask = [.flexibleWidth]
        let first = UIStackView()
        for key in [("Esc", "esc"), ("Tab", "tab")] {
            first.addArrangedSubview(accessoryButton(key.0, code: key.1) { $0.input?.key(key.1) })
        }
        for key in [("Ctrl", "ctrl"), ("Alt", "alt")] {
            let button = accessoryButton(key.0, code: key.1) { $0.input?.toggle(key.1) }
            modifierButtons[key.1] = button; first.addArrangedSubview(button)
        }
        first.addArrangedSubview(accessoryButton("Release", code: "release", label: "Release all keys and mouse buttons") { $0.input?.releaseHeld() })
        first.addArrangedSubview(accessoryButton("Hide", code: "hide", label: "Hide keyboard and release held input") {
            $0.input?.releaseHeld(); $0.hideKeyboard?()
        })
        let second = UIStackView()
        for key in [("←", "left", "Left arrow"), ("↑", "up", "Up arrow"), ("↓", "down", "Down arrow"),
                    ("→", "right", "Right arrow"), ("Enter", "ret", "Enter"), ("⌫", "backspace", "Backspace")] {
            second.addArrangedSubview(accessoryButton(key.0, code: key.1, label: key.2) { $0.input?.key(key.1) })
        }
        for row in [first, second] {
            row.axis = .horizontal; row.distribution = .fillEqually; row.spacing = 4
            row.heightAnchor.constraint(equalToConstant: 44).isActive = true
        }
        let stack = UIStackView(arrangedSubviews: [first, second])
        stack.axis = .vertical; stack.spacing = 4; stack.translatesAutoresizingMaskIntoConstraints = false
        bar.addSubview(stack)
        NSLayoutConstraint.activate([
            stack.leadingAnchor.constraint(equalTo: bar.leadingAnchor, constant: 8),
            stack.trailingAnchor.constraint(equalTo: bar.trailingAnchor, constant: -8),
            stack.topAnchor.constraint(equalTo: bar.topAnchor, constant: 4),
            stack.bottomAnchor.constraint(equalTo: bar.bottomAnchor, constant: -4)
        ])
        refreshAccessory()
        return bar
    }
    func refreshAccessory() {
        for button in accessoryButtons {
            button.isEnabled = available && input?.enabled == true
            button.backgroundColor = .secondarySystemBackground
        }
        for (code, button) in modifierButtons {
            let selected = input?.latched.contains(code) == true
            button.isSelected = selected
            button.accessibilityTraits = selected ? [.button, .selected] : [.button]
            button.backgroundColor = selected ? UIColor.systemOrange.withAlphaComponent(0.3) : .secondarySystemBackground
        }
    }
}

private struct LinuxDesktopKeyboard: UIViewRepresentable {
    let input: LinuxDesktopInput
    let available: Bool
    let show: Bool
    let hide: () -> Void
    func makeUIView(context: Context) -> LinuxDesktopKeyView {
        let view = LinuxDesktopKeyView(); view.input = input
        return view
    }
    func updateUIView(_ view: LinuxDesktopKeyView, context: Context) {
        view.hideKeyboard = hide
        view.available = available; view.softwareKeyboard = show
        view.refreshAccessory()
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
    @State private var showDiagnostics = false
    @State private var showShare = false
    @State private var shareItems: [URL] = []
    init() { input = LinuxTerminalSession.desktop.desktopInput! }

    var body: some View {
        GeometryReader { geometry in
            VStack(spacing: 5) {
                Text("Debian desktop").font(.headline).frame(maxWidth: .infinity, alignment: .leading)
                Text(session.message).font(.caption).lineLimit(3).frame(maxWidth: .infinity, alignment: .leading)
                if let preparation = session.preparationState, preparation.inProgress {
                    ProgressView(preparation.message).font(.caption)
                    Text("Keep iDeck open. Leaving this screen cancels pending startup after the current file operation; completed copies are preserved.")
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
        .background(LinuxDesktopKeyboard(input: input, available: inputAvailable, show: keyboard, hide: { keyboard = false }).frame(width: 1,height: 1).opacity(0.01))
        .sheet(isPresented: $jit.showSetup) { JITSetupFlow() }
        .sheet(isPresented: $showDiagnostics) { LinuxDesktopDiagnosticsView(session: session) }
        .sheet(isPresented: $showShare) { ShareSheet(items: shareItems) }
        .onAppear { session.recoverDiagnostics(); refreshInputFocus() }
        .onChange(of: recovery) { _ in refreshInputFocus() }
        .onChange(of: showDiagnostics) { _ in refreshInputFocus() }
        .onChange(of: showShare) { _ in refreshInputFocus() }
        .onChange(of: jit.showSetup) { _ in refreshInputFocus() }
        .onDisappear { input.setFocused(false); session.cancelPreparation() }
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
            Button("Share report") {
                prepareDiagnostics()
                if let file = session.reportForSharing() { shareItems = [file]; showShare = true }
                else { showDiagnostics = true }
            }.accessibilityIdentifier("ideck-desktop-share-report")
            Button("Diagnostics") { prepareDiagnostics(); session.recoverDiagnostics(); showDiagnostics = true }
                .accessibilityLabel("Saved startup diagnostics, Markdown")
                .accessibilityIdentifier("ideck-desktop-startup-diagnostics")
            Spacer(minLength: 0)
            if let preparation = session.preparationState, preparation.inProgress {
                Button(preparation.canCancel ? "Cancel start" : "Cancelling…") { session.cancelPreparation() }
                    .disabled(!preparation.canCancel).accessibilityIdentifier("ideck-desktop-cancel-start")
            } else if session.attempted {
                Button("Stop Linux") { session.stop() }.disabled(!session.canStop || session.stopping)
            } else {
                Button("Recover disk") { session.startRecovery() }.disabled(jit.busy)
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
                Button("Start desktop") { session.startDesktop() }.disabled(jit.busy)
            }
            if session.recoveryMode {
                Text("Separate recovery VM. Creates verified backup/work copies; preserves the original. After completion, close/reopen iDeck before Start desktop.").font(.caption2)
            } else if !session.attempted {
                Text("After a blocked unclean disk: Recover disk first. Requires space for two full copies plus 512 MiB reserve.").font(.caption2)
            }
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 5) {
                Button("Keyboard") { if keyboard { input.releaseHeld() }; keyboard.toggle() }
                    .accessibilityIdentifier("ideck-desktop-keyboard")
                    .accessibilityValue(keyboard ? "Shown" : "Hidden")
                Button("Release keys") { input.releaseHeld() }.accessibilityIdentifier("ideck-desktop-release-input")
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
private struct LinuxDesktopDiagnosticsView: View {
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
