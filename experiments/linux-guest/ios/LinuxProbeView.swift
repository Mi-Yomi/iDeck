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
    private var currentSession: LinuxTerminalSession {
        switch route.current {
        case .some(.steam): return steam
        case .some(.desktop): return desktop
        case .some(.debian): return debian
        default: return terminal
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
            HStack {
                Button { route.home() } label: { Label("Домой", systemImage: "house.fill") }
                    .accessibilityIdentifier("ideck-home")
                Spacer()
                if route.current != nil {
                    Button { route.resume() } label: { Label("К сессии", systemImage: "play.rectangle") }
                        .accessibilityIdentifier("ideck-resume")
                }
            }.buttonStyle(.bordered).padding(.horizontal).padding(.vertical, 6).background(.ultraThinMaterial)
        }
        .onAppear { LinuxTerminalSession.shared.recoverDiagnostics(); steam.refreshSteamReadiness() }
        .sheet(isPresented: $showJIT) { JITSetupFlow() }
        .sheet(isPresented: $showDiagnostics) {
            if route.current == .linux {
                LinuxProbeDiagnosticsView(session: probe)
            } else {
                LinuxDesktopDiagnosticsView(session: currentSession)
            }
        }
        .onChange(of: scenePhase) { phase in
            if phase == .active { steam.refreshSteamReadiness() }
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
        case .steam: LinuxDesktopView(session: .steam)
        case .settings: settings
        case .advanced: advanced
        case .library: EmptyView()
        }
    }
    private var launcher: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                HStack {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("iDeck").font(.largeTitle.bold())
                        Text("Ваша Linux-консоль").foregroundStyle(Theme.textDim)
                    }
                    Spacer()
                    Image(systemName: "gamecontroller.fill").font(.largeTitle).foregroundStyle(Theme.accent)
                }
                if let current = route.current {
                    VStack(alignment: .leading, spacing: 12) {
                        Label("Текущая сессия · \(current.rawValue)", systemImage: "circle.fill").font(.headline)
                        Text(current == .linux ? probe.message : current == .library ? "Библиотека сохраняет текущий runtime." : currentSession.message).font(.callout)
                        if current == .steam { Text(steam.steamMessage).font(.footnote).foregroundStyle(Theme.textDim) }
                        Button("Вернуться к сессии") { route.resume() }.buttonStyle(.borderedProminent)
                        Text("Домой меняет только экран. Сессия и её диск остаются у текущего владельца.").font(.footnote).foregroundStyle(Theme.textDim)
                    }.padding().background(Theme.surface, in: RoundedRectangle(cornerRadius: Theme.cardCorner))
                }
                LazyVGrid(columns: [GridItem(.adaptive(minimum: 240), spacing: 16)], spacing: 16) {
                    launcherCard("Steam / Big Picture", icon: "gamecontroller", detail: "Настроить или открыть Steam в настоящей Linux-сессии. Установка клиента требует согласия на сеть.", target: .steam)
                    launcherCard("Рабочий стол", icon: "desktopcomputer", detail: route.runtimeOwner == .steam ? "Экран текущей Steam/Linux-сессии без смены диска или перезапуска VM." : "Открыть экран Linux. Отдельный GUI-диск сохраняет ваши файлы.", target: route.runtimeOwner == .steam ? .steam : .desktop)
                    launcherCard("Настройки", icon: "gearshape", detail: "JIT, подключение и параметры сессии", target: .settings)
                }
                if let check = steam.steamReadiness { Text("Steam · \(check.summary)").font(.footnote).foregroundStyle(Theme.textDim) }
                if route.runtimeOwner != nil {
                    Text("Смена среды заблокирована после попытки запуска, включая остановку и ошибку. Для другой VM нужен новый процесс iDeck.").font(.footnote).foregroundStyle(Theme.textDim)
                }
                if let notice = route.notice { Text(notice).foregroundStyle(.orange) }
                Button { route.choose(.advanced) } label: { Label("Диагностика и дополнительно", systemImage: "wrench.and.screwdriver") }
            }.padding(20).frame(maxWidth: 900).frame(maxWidth: .infinity)
        }
    }
    private func launcherCard(_ title: String, icon: String, detail: String, target: LinuxProbeRoute.Destination) -> some View {
        Button { route.choose(target) } label: {
            VStack(alignment: .leading, spacing: 14) {
                Image(systemName: icon).font(.title).foregroundStyle(Theme.accent)
                Text(title).font(.title2.bold()).foregroundStyle(Theme.text)
                Text(detail).font(.callout).foregroundStyle(Theme.textDim).fixedSize(horizontal: false, vertical: true)
                Label(route.canChoose(target) ? "Открыть" : "Другая среда занята", systemImage: route.canChoose(target) ? "arrow.right" : "lock.fill").font(.footnote)
            }.frame(maxWidth: .infinity, minHeight: 180, alignment: .leading).padding(20)
                .background(Theme.surface, in: RoundedRectangle(cornerRadius: Theme.cardCorner))
        }.buttonStyle(.plain).disabled(!route.canChoose(target))
    }
    private var settings: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                Text("Настройки").font(.largeTitle.bold())
                Text("JIT включается только вашим действием. Возврат домой не сбрасывает JIT и не запускает Linux.")
                Button("Настроить JIT") { jit.refreshPairingStatus(); showJIT = true }.buttonStyle(.borderedProminent)
                    .disabled(route.runtimeOwner != nil || jit.busy)
                if route.runtimeOwner != nil { Text("Настройки JIT заблокированы после попытки запуска. Текущая сессия сохраняет свой JIT.").font(.footnote) }
                Text("Steam: отдельный диск 12 GiB; RAM Auto с резервом или фиксированные 1536 MiB. Согласие на сеть и официальный installer доступны перед запуском Steam-сессии.").foregroundStyle(Theme.textDim)
                Button("Диагностика и сохранённые отчёты") { route.choose(.advanced) }
            }.padding(20).frame(maxWidth: 700)
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
                Text("Recovery GUI-диска доступен в диагностике перед запуском. Steam-диск 12 GiB не поддерживает GUI recovery.").font(.footnote)
                ForEach([LinuxProbeRoute.Destination.terminal, .debian, .linux], id: \.self) { target in
                    Button(target == .linux ? "Boot / display / input test" : target == .debian ? "Debian console" : "Linux terminal") { route.choose(target) }.disabled(!route.canChoose(target))
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
            Text("This checks Linux boot, display and input. Steam is not included yet.")
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
