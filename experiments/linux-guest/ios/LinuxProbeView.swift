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
        .sheet(isPresented: $showJIT, onDismiss: { recheckLauncherJIT() }) { JITSetupFlow() }
        .confirmationDialog("Разрешить сеть для среды?", isPresented: $showNetworkConsent, titleVisibility: .visible) {
            Button("Разрешить и продолжить") { steam.steamNetworkConsent = true; advanceLaunch() }
            Button("Не сейчас", role: .cancel) { launchIntent.cancel(); launchNotice = "Запуск отменён до создания сессии." }
        } message: {
            Text("Установка использует встроенные пакеты. Steam может обращаться к сети для обновления и входа. Логин и соглашения остаются вашими действиями.")
        }
        .onChange(of: jit.attachGeneration) { _ in recheckLauncherJIT() }
        .onChange(of: jit.busy) { busy in
            if !busy, launchIntent.jitPrompt { recheckLauncherJIT() }
        }
        .onChange(of: steam.steamMemoryMode) { _ in steam.refreshSteamReadiness() }
        .onChange(of: steam.steamNetworkConsent) { _ in steam.refreshSteamReadiness() }
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
                if launchIntent.jitPrompt { recheckLauncherJIT() }
            }
            if phase == .background {
                if pendingLaunch { launchIntent.cancel(); launchNotice = "Запуск отложен. Вернитесь и нажмите «Запустить среду»." }
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
                } else if pendingLaunch { ProgressView("Проверяем условия запуска…") }
                else if route.runtimeOwner == .steam, steam.environmentStage == .installingSteam { ProgressView("Подготовка Steam…") }
                Button { launchPrimary() } label: {
                    Label(route.runtimeOwner == nil ? "Запустить среду" : "Продолжить среду", systemImage: "play.fill")
                        .font(.title3.bold()).frame(maxWidth: .infinity, minHeight: 64)
                }.buttonStyle(.borderedProminent)
                    .accessibilityIdentifier("ideck-launch-environment")
                if route.runtimeOwner == nil {
                    if launchIntent.jitPrompt {
                        Text("Для запуска нужен JIT. Откройте настройку ниже; после возврата iDeck проверит выполнение кода. Само открытие другого приложения JIT не подтверждает.")
                            .font(.callout).foregroundStyle(.orange)
                        Text(steam.jitExecutionMessage).font(.footnote)
                        if let error = jit.error { Text(error).font(.footnote).textSelection(.enabled) }
                        if jit.busy { Text(jit.status ?? "JIT helper выполняет запрос. Если ожидание затянулось, откройте настройку и проверьте результат.").font(.footnote) }
                        Button("Открыть настройку JIT") { openLauncherJIT() }.buttonStyle(.bordered)
                            .accessibilityIdentifier("ideck-launcher-jit-setup")
                    }
                    if let readiness = steam.steamReadiness, readiness.memory != .passed {
                        Text("Запуск остановлен проверкой памяти. " + readiness.memoryExplanation)
                            .font(.callout).foregroundStyle(.orange)
                            .accessibilityIdentifier("ideck-launcher-memory-blocker")
                        if steam.steamMemoryMode == .auto {
                            Text("Режим 1536 MiB требует меньше бюджета, но может быть тесен для Steam и игр. Резерв и повторная проверка сохраняются.").font(.footnote)
                            Button("Проверить запуск с 1536 MiB") {
                                steam.steamMemoryMode = .fixed1536
                                launchPrimary()
                            }.buttonStyle(.bordered).accessibilityIdentifier("ideck-launcher-fixed-memory")
                        }
                        Button("Обновить замер памяти") {
                            steam.refreshSteamReadiness()
                            launchNotice = "Замер обновлён. Если бюджета недостаточно, закройте другие приложения или перезапустите iDeck. Запуск остаётся заблокированным до свежей успешной проверки."
                        }.buttonStyle(.bordered)
                    }
                }
                if let notice = route.notice { Text(notice).font(.footnote).foregroundStyle(.orange) }
            }.padding(24).frame(maxWidth: 650).frame(maxWidth: .infinity)
        }
    }
    private func launchPrimary() {
        if route.runtimeOwner != nil { route.resume(); return }
        guard !pendingLaunch else {
            launchNotice = "Проверка запуска уже выполняется. Вторая сессия не создаётся."; return
        }
        route.selectPrimary()
        guard launchIntent.begin() else { return }
        launchNotice = "Проверяем JIT и свежий бюджет памяти…"
        // Give SwiftUI a frame to show feedback before the existing native check.
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.05) {
            guard pendingLaunch else { return }
            guard scenePhase == .active else { launchIntent.cancel(); launchNotice = "Вернитесь в iDeck и повторите запуск."; return }
            guard route.runtimeOwner == nil else { launchIntent.cancel(); route.resume(); return }
            guard !jit.busy else {
                launchIntent.checkedJIT(false)
                launchNotice = "JIT helper занят. Откройте настройку JIT и проверьте результат; VM не запущена."; return
            }
            steam.claimJIT()
            steam.refreshSteamReadiness()
            advanceLaunch()
        }
    }
    private func advanceLaunch() {
        switch launchIntent.advance(owner: route.runtimeOwner != nil, foreground: scenePhase == .active,
                                    busy: jit.busy, network: steam.steamNetworkConsent, jit: steam.jitExecutionReady) {
        case .wait:
            launchIntent.cancel()
            launchNotice = "Запуск ожидает активного iDeck и завершения JIT helper. Повторите проверку или откройте настройку JIT."
        case .resume: route.resume()
        case .consent:
            launchNotice = "Для продолжения нужно согласие на сеть."
            showNetworkConsent = true
        case .jit:
            launchNotice = "JIT не прошёл проверку. Включите его через настройку прямо ниже; VM не запущена."
        case .start:
            showJIT = false
            steam.startEnvironment()
            if steam.attempted { route.choose(.steam) }
            else { launchNotice = steam.message }
        }
    }
    private func openLauncherJIT() {
        guard route.runtimeOwner == nil else { route.resume(); return }
        launchIntent.checkedJIT(false)
        launchNotice = "Настройте JIT, затем вернитесь для проверки и продолжения запуска."
        jit.refreshPairingStatus()
        if jit.method == .automatic, HuskBuiltInJIT.isAvailable { jit.method = .builtIn }
        showJIT = true
    }
    private func recheckLauncherJIT() {
        guard launchIntent.jitPrompt, route.runtimeOwner == nil, scenePhase == .active, !jit.busy else { return }
        steam.claimJIT()
        steam.refreshSteamReadiness()
        let verified = steam.jitExecutionReady
        launchIntent.checkedJIT(verified)
        launchNotice = verified ? "JIT проверен. Нажмите «Запустить среду» для продолжения со свежей проверкой памяти."
            : "JIT пока не прошёл проверку. Откройте настройку JIT и проверьте pairing и подключение; VM не запущена."
        if verified { showJIT = false }
    }
    private var settings: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                Text("Настройки").font(.largeTitle.bold())
                Text("JIT включается только вашим действием. Домой и продолжение не перезапускают среду.")
                Button("Настроить JIT") { openLauncherJIT() }
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
                Text("Восстановление GUI или отдельного Steam-диска доступно в диагностике до запуска VM. Для Steam: только eligible journal replay на копиях, без сброса; после неудачного запуска нужен перезапуск iDeck.").font(.footnote)
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
