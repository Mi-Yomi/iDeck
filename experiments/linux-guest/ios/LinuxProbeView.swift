import SwiftUI

/// A shared screen route; native ownership lives in the existing static sessions.
@MainActor
final class LinuxProbeRoute: ObservableObject {
    typealias Destination = LinuxLauncherNavigation.Destination
    static let shared = LinuxProbeRoute()
    @Published private(set) var navigation = LinuxLauncherNavigation()
    @Published private(set) var notice: String?
    var destination: Destination { navigation.destination }
    var runtimeOwner: Destination? {
        if LinuxTerminalSession.steam.attempted { return .steam }
        if LinuxTerminalSession.desktop.attempted { return .desktop }
        if LinuxTerminalSession.debian.attempted { return .debian }
        if LinuxTerminalSession.shared.attempted { return .terminal }
        if LinuxProbeSession.shared.attempted { return .linux }
        return navigation.owner
    }
    var current: Destination? { runtimeOwner ?? navigation.selected }
    func canChoose(_ target: Destination) -> Bool { runtimeOwner == nil || !target.isEnvironment || runtimeOwner == target }
    func home() {
        navigation.reserve(runtimeOwner)
        navigation.home()
        NotificationCenter.default.post(name: Notification.Name("iDeck.releaseDisplayInput"), object: nil)
    }
    func resume() { navigation.reserve(runtimeOwner); navigation.resume() }
    func selectPrimary() { navigation.reserve(runtimeOwner); navigation.selectPrimary() }
    func choose(_ target: Destination) {
        navigation.reserve(runtimeOwner)
        let initializeLibrary = target == .library && navigation.owner != .library
        guard navigation.open(target) else {
            notice = "Другая среда уже использовала runtime. Вернитесь к текущей сессии. Новый запуск Linux требует полного перезапуска iDeck."; return
        }
        notice = nil
        if initializeLibrary {
            _ = Downloads.shared
            let defaults = UserDefaults.standard
            if !defaults.bool(forKey: "husk.autoStart.offByDefault") {
                defaults.set(false, forKey: "husk.autoStart")
                defaults.set(true, forKey: "husk.autoStart.offByDefault")
            }
            IncomingFiles.clearLeftovers()
            HuskGamepads.shared.start()
        }
    }
}

struct LinuxProbeRoot: View {
    @ObservedObject private var route = LinuxProbeRoute.shared
    @ObservedObject private var desktop = LinuxTerminalSession.desktop
    @ObservedObject private var steam = LinuxTerminalSession.steam
    @ObservedObject private var terminal = LinuxTerminalSession.shared
    @ObservedObject private var debian = LinuxTerminalSession.debian
    @ObservedObject private var probe = LinuxProbeSession.shared
    @ObservedObject private var jit = JITCoordinator.shared
    @Environment(\.scenePhase) private var scenePhase
    @State private var showJIT = false
    @State private var showDiagnostics = false
    @State private var showNetworkConsent = false
    @State private var launchIntent = LinuxEnvironmentLaunchIntent()
    private var pendingLaunch: Bool { launchIntent.pending }
    @State private var launchNotice: String?
    private var currentSession: LinuxTerminalSession {
        switch route.current {
        case .some(.steam): return steam
        case .some(.desktop): return desktop
        case .some(.debian): return debian
        case .some(.terminal): return terminal
        default: return steam
        }
    }
    var body: some View {
        ZStack {
            Theme.bg.ignoresSafeArea()
            // Keep the original library mounted if opened in a full Husk build.
            // Its own view lifecycle must not stop a runtime when Home is shown.
            #if !IDECK_LINUX_PROBE_ONLY
            if route.navigation.owner == .library {
                ContentView().opacity(route.destination == .library ? 1 : 0)
                    .allowsHitTesting(route.destination == .library)
                    .accessibilityHidden(route.destination != .library)
            }
            #endif
            if route.destination != .library { screen }
        }
        .tint(Theme.accent)
        .safeAreaInset(edge: .top, spacing: 0) {
            if route.destination != .choose {
                HStack {
                    Button { route.home() } label: { Label("Домой", systemImage: "house.fill") }
                        .accessibilityIdentifier("ideck-home")
                    Spacer()
                    if route.runtimeOwner != nil, route.destination == .settings || route.destination == .advanced {
                        Button { route.resume() } label: { Label("К среде", systemImage: "play.rectangle") }
                            .accessibilityIdentifier("ideck-resume")
                    }
                    if route.destination != .settings {
                        Button { route.choose(.settings) } label: { Image(systemName: "gearshape") }
                            .accessibilityLabel("Настройки")
                    }
                }.buttonStyle(.bordered).padding(.horizontal).padding(.vertical, 6).background(.ultraThinMaterial)
            }
        }
        .onAppear { steam.refreshSteamReadiness() }
        .sheet(isPresented: $showJIT, onDismiss: {
            if pendingLaunch, steam.jitExecutionReady { advanceLaunch() }
            else { launchIntent.cancel() }
        }) { JITSetupFlow() }
        .confirmationDialog("Разрешить сеть для среды?", isPresented: $showNetworkConsent, titleVisibility: .visible) {
            Button("Разрешить и продолжить") { steam.steamNetworkConsent = true; advanceLaunch() }
            Button("Не сейчас", role: .cancel) { launchIntent.cancel(); launchNotice = "Запуск отменён до создания сессии." }
        } message: {
            Text("Установка использует встроенные пакеты. Steam может обращаться к сети для обновления и входа. Логин и соглашения остаются вашими действиями.")
        }
        .onChange(of: jit.attachGeneration) { _ in
            if pendingLaunch, route.runtimeOwner == nil, scenePhase == .active { steam.claimJIT(); advanceLaunch() }
        }
        .onChange(of: jit.busy) { busy in if !busy, pendingLaunch { advanceLaunch() } }
        .onChange(of: steam.jitExecutionReady) { ready in
            if ready, pendingLaunch { showJIT = false; advanceLaunch() }
        }
        .sheet(isPresented: $showDiagnostics) {
            if route.current == .linux {
                LinuxProbeDiagnosticsView(session: probe)
            } else {
                LinuxDesktopDiagnosticsView(session: currentSession)
            }
        }
        .onChange(of: scenePhase) { phase in
            if phase == .active {
                steam.refreshSteamReadiness()
                if pendingLaunch, route.runtimeOwner == nil { steam.claimJIT(); advanceLaunch() }
            }
            if phase == .background {
                for session in [terminal, debian, desktop, steam] { session.cancelPreparation() }
            }
        }
        #if !IDECK_LINUX_PROBE_ONLY
        .onOpenURL { url in
            guard route.destination == .library else { return }
            if !AppClip.handle(url) { IncomingFiles.shared.receive(url) }
        }
        #endif
    }
    @ViewBuilder private var screen: some View {
        switch route.destination {
        case .choose: launcher
        case .linux: LinuxProbeView()
        case .terminal: LinuxTerminalView()
        case .debian: LinuxTerminalView(session: .debian)
        case .desktop: LinuxDesktopView()
        case .steam: LinuxDesktopView(session: .steam, unified: true)
        case .settings: settings
        case .advanced: advanced
        case .library: EmptyView()
        }
    }
    private var launcher: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                HStack {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("iDeck").font(.largeTitle.bold())
                        Text("Ваша игровая среда").foregroundStyle(Theme.textDim)
                    }
                    Spacer()
                    Button { route.choose(.settings) } label: { Image(systemName: "gearshape") }
                        .accessibilityLabel("Настройки").buttonStyle(.bordered)
                }
                Image(systemName: "gamecontroller.fill").font(.system(size: 72)).foregroundStyle(Theme.accent)
                    .frame(maxWidth: .infinity).padding(.vertical, 24)
                Text(route.runtimeOwner == .steam ? steam.environmentSummary
                    : route.runtimeOwner != nil ? currentSession.message
                    : launchNotice ?? "Рабочий стол и Steam в одной среде. Подготовка начнётся после нажатия.")
                    .font(.callout).frame(maxWidth: .infinity, alignment: .leading)
                if let preparation = steam.preparationState, preparation.inProgress {
                    ProgressView().accessibilityLabel(steam.environmentSummary)
                } else if pendingLaunch || jit.busy { ProgressView(jit.status ?? "Подготовка запуска…") }
                else if route.runtimeOwner == .steam, steam.environmentStage == .installingSteam { ProgressView("Подготовка Steam…") }
                Button { launchPrimary() } label: {
                    Label(route.runtimeOwner == nil ? "Запустить среду" : "Продолжить среду", systemImage: "play.fill")
                        .font(.title3.bold()).frame(maxWidth: .infinity, minHeight: 64)
                }.buttonStyle(.borderedProminent).disabled(jit.busy || pendingLaunch)
                    .accessibilityIdentifier("ideck-launch-environment")
                if let notice = route.notice { Text(notice).font(.footnote).foregroundStyle(.orange) }
            }.padding(24).frame(maxWidth: 650).frame(maxWidth: .infinity)
        }
    }
    private func launchPrimary() {
        if route.runtimeOwner != nil { route.resume(); return }
        guard !pendingLaunch, !jit.busy else { return }
        route.selectPrimary()
        launchNotice = nil
        guard launchIntent.begin() else { return }
        steam.claimJIT() // Explicit Start only; preview never performs JIT work.
        advanceLaunch()
    }
    private func advanceLaunch() {
        switch launchIntent.advance(owner: route.runtimeOwner != nil, foreground: scenePhase == .active,
                                    busy: jit.busy, network: steam.steamNetworkConsent, jit: steam.jitExecutionReady) {
        case .wait: return
        case .resume: route.resume()
        case .consent: showNetworkConsent = true
        case .jit: showJIT = true
        case .start:
            showJIT = false
            steam.startEnvironment()
            if steam.attempted { route.choose(.steam) }
            else { launchNotice = steam.message }
        }
    }
    private var settings: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                Text("Настройки").font(.largeTitle.bold())
                Text("JIT включается только вашим действием. Домой и продолжение не перезапускают среду.")
                Button("Настроить JIT") { jit.refreshPairingStatus(); showJIT = true }
                    .buttonStyle(.bordered).disabled(route.runtimeOwner != nil || jit.busy)
                Text(steam.jitExecutionMessage).font(.footnote).foregroundStyle(Theme.textDim)
                Picker("Память среды", selection: $steam.steamMemoryMode) {
                    Text("Auto · до 4096 MiB (эксперимент)").tag(LinuxSteamMemory.Mode.auto)
                    Text("1536 MiB").tag(LinuxSteamMemory.Mode.fixed1536)
                }.disabled(route.runtimeOwner != nil || pendingLaunch)
                Toggle("Разрешить сеть Steam в этой сессии", isOn: $steam.steamNetworkConsent)
                    .disabled(route.runtimeOwner != nil || pendingLaunch)
                Text("Используется прежний диск среды 12 GiB. Существующие данные сохраняются. Для первого создания диска нужны 12 GiB и 1 GiB резерва; встроенный кэш проверяется отдельно.")
                    .font(.footnote).foregroundStyle(Theme.textDim)
                Button("Расширенные настройки") { route.choose(.advanced) }.buttonStyle(.bordered)
            }.padding(24).frame(maxWidth: 700)
        }
    }
    private var advanced: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                Text("Дополнительно").font(.largeTitle.bold())
                Button("Диагностика / Share report") {
                    if route.current != .linux { currentSession.recoverDiagnostics() }
                    showDiagnostics = true
                }
                Text("Экранная панель отправляет клавиши и мышь; Linux HID-геймпад она не создаёт.").font(.footnote)
                Text("Recovery GUI-диска доступен в диагностике перед запуском. Steam-диск 12 GiB не поддерживает GUI recovery.").font(.footnote)
                ForEach([LinuxProbeRoute.Destination.desktop, .terminal, .debian, .linux], id: \.self) { target in
                    Button(target == .desktop ? "Прежний GUI-диск (без миграции)" : target == .linux ? "Boot / display / input test" : target == .debian ? "Debian console" : "Linux terminal") { route.choose(target) }.disabled(!route.canChoose(target))
                }
                if route.runtimeOwner == .steam {
                    Text(steam.steamCacheStatus).font(.footnote)
                    Text(steam.steamMessage).font(.footnote).textSelection(.enabled)
                    Button("Повторить подготовку Steam") { steam.retryEnvironmentSteam() }
                        .disabled(!steam.ready || steam.steamBusy || steam.stopping || steam.environmentStage != .blocked)
                    Button("Открыть Steam внутри среды") { steam.steamAction("BIG_PICTURE") }
                        .disabled(!steam.ready || !steam.steamInstalled || steam.steamBusy || steam.stopping)
                    Button("Завершить Steam, оставить рабочий стол") { steam.steamAction("DESKTOP") }
                        .disabled(!steam.ready || !steam.steamInstalled || steam.stopping)
                }
                #if !IDECK_LINUX_PROBE_ONLY
                Button("Husk library") { route.choose(.library) }.disabled(!route.canChoose(.library))
                #endif
            }.buttonStyle(.bordered).padding(20).frame(maxWidth: 700)
        }
    }
}

/// The probe owns a separate report; never substitute a terminal journal for it.
private struct LinuxProbeDiagnosticsView: View {
    @ObservedObject var session: LinuxProbeSession
    @Environment(\.dismiss) private var dismiss
    @State private var showShare = false
    @State private var shareItems: [URL] = []
    var body: some View {
        NavigationView {
            List {
                Section("Linux probe") {
                    Text(session.message).textSelection(.enabled)
                    if let error = session.exportError { Text(error).foregroundStyle(.orange) }
                }
                Section("Probe report") {
                    if let file = session.markdownFile {
                        ShareLink("Share probe report (.md)", item: file)
                    } else {
                        Text("Probe Markdown report is not available yet. No terminal report is substituted.")
                    }
                    Button("Raw probe JSON and serial log") {
                        shareItems = session.shareFiles; showShare = true
                    }.disabled(session.shareFiles.isEmpty)
                }
            }
            .navigationTitle("Probe diagnostics").navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Done") { dismiss() } } }
        }
        .navigationViewStyle(.stack)
        .sheet(isPresented: $showShare) { ShareSheet(items: shareItems) }
    }
}

struct LinuxProbeView: View {
    @ObservedObject private var session = LinuxProbeSession.shared
    @ObservedObject private var jit = JITCoordinator.shared
    @Environment(\.scenePhase) private var scenePhase
    @State private var showShare = false
    @State private var shareItems: [URL] = []

    var body: some View {
        ScrollView { content }
            .sheet(isPresented: $jit.showSetup) { JITSetupFlow() }
            .sheet(isPresented: $showShare) { ShareSheet(items: shareItems) }
            .onChange(of: jit.attachGeneration) { _ in claimJIT() }
            .onChange(of: scenePhase) { if $0 == .active { claimJIT() } }
            .onAppear { claimJIT() }
    }

    private var coordinatorStatus: String? {
        // The coordinator observes debugger attachment; the session separately
        // verifies executable memory before displaying an execution pass.
        jit.status == "JIT is on." ? "Debugger attached." : jit.status
    }

    private var content: some View {
        VStack(spacing: 12) {
            Text("iDeck · Linux probe").font(.headline)
            Text(session.message).font(.callout).multilineTextAlignment(.center)
                .accessibilityIdentifier("ideck-linux-status")
            Text(session.jitExecutionMessage).font(.footnote)
                .foregroundStyle(session.jitExecutionReady ? Color.green : Color.secondary)
                .multilineTextAlignment(.center)
                .accessibilityIdentifier("ideck-jit-execution-status")
            if jit.busy {
                ProgressView(coordinatorStatus ?? "Enabling JIT…")
            } else if let status = coordinatorStatus {
                Text(status).font(.footnote).foregroundStyle(.secondary)
            }
            if let error = jit.error {
                Text(error).font(.footnote).foregroundStyle(.orange)
                    .multilineTextAlignment(.center)
            }
            if !jit.hasPairing, jit.method == .automatic || jit.method == .builtIn {
                Text("First time: open JIT setup to pair this iPhone or import its pairing file, then connect LocalDevVPN.")
                    .font(.footnote).foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
            }
            Button("JIT setup and method") {
                jit.refreshPairingStatus()
                jit.showSetup = true
            }.disabled(jit.busy)
            if session.displayReady {
                HuskDisplay().aspectRatio(4.0 / 3.0, contentMode: .fit)
                    .allowsHitTesting(session.inputReady)
                    .accessibilityIdentifier("ideck-linux-display")
            } else {
                Rectangle().fill(.black).aspectRatio(4.0 / 3.0, contentMode: .fit)
            }
            HStack {
                Button("Enable JIT") { enableJIT() }.disabled(session.attempted || jit.busy)
                Button("Start Linux") { session.start() }.disabled(session.attempted || jit.busy)
                Button("Send A") { session.sendA() }.disabled(!session.inputReady)
            }.buttonStyle(.bordered)
            Menu("Save report") {
                Button("Markdown report (.md)") {
                    guard let file = session.markdownFile else { return }
                    shareItems = [file]
                    showShare = true
                }.disabled(session.markdownFile == nil)
                Button("Raw JSON and serial log") {
                    shareItems = session.shareFiles
                    showShare = true
                }.disabled(session.shareFiles.isEmpty)
            }.disabled(session.markdownFile == nil && session.shareFiles.isEmpty)
            if let error = session.exportError {
                Text(error).font(.footnote).foregroundStyle(.orange)
                    .multilineTextAlignment(.center)
            }
            Text("Это отдельный boot/display/input тест. Основная среда запускается из лаунчера; её диск этот тест не использует.")
                .font(.footnote).foregroundStyle(.secondary)
        }
        .padding()
    }

    private func claimJIT() {
        // Claim while the debugger is attached; do not auto-start a guest.
        jit.refreshPairingStatus()
        session.claimJIT()
    }

    private func enableJIT() {
        guard !session.attempted, !jit.busy else { return }
        jit.refreshPairingStatus()
        // Automatic must not infer TrollStore from the system Magnifier URL.
        // Keep methods the user explicitly chose in the original walkthrough.
        if jit.method == .automatic, HuskBuiltInJIT.isAvailable {
            jit.method = .builtIn
        }
        jit.enable()
    }
}
