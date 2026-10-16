import SwiftUI

/// The route is shared by all windows and cannot be changed in this process.
/// QEMU and the translation runtimes own global state and a shared JIT region.
@MainActor
final class LinuxProbeRoute: ObservableObject {
    enum Destination { case choose, linux, library }
    static let shared = LinuxProbeRoute()
    @Published private(set) var destination: Destination = .choose

    func choose(_ route: Destination) {
        guard destination == .choose, route != .choose else { return }
        if route == .library {
            // Original Husk maintenance, deferred until its library is chosen.
            _ = Downloads.shared
            let defaults = UserDefaults.standard
            if !defaults.bool(forKey: "husk.autoStart.offByDefault") {
                defaults.set(false, forKey: "husk.autoStart")
                defaults.set(true, forKey: "husk.autoStart.offByDefault")
            }
            IncomingFiles.clearLeftovers()
            HuskGamepads.shared.start()
        }
        destination = route
    }
}

struct LinuxProbeRoot: View {
    @ObservedObject private var route = LinuxProbeRoute.shared

    var body: some View {
        #if IDECK_LINUX_PROBE_ONLY
        // The separately installed probe has no Android/PS4 library route.
        LinuxProbeView()
        #else
        Group {
            switch route.destination {
            case .choose:
                VStack(spacing: 24) {
                    Text("iDeck Linux experiment").font(.title)
                    Text("Choose the environment for this launch.")
                    Button("Linux boot and input probe") { route.choose(.linux) }
                        .buttonStyle(.borderedProminent)
                    Button("Open Husk library") { route.choose(.library) }
                        .buttonStyle(.bordered)
                    Text("To switch environments, close and reopen the app.")
                        .font(.footnote).foregroundStyle(.secondary)
                }.padding()
            case .linux:
                LinuxProbeView()
            case .library:
                ContentView()
            }
        }
        .onOpenURL { url in
            // APK deep links must not activate another runtime in a Linux run.
            guard route.destination == .library else { return }
            if !AppClip.handle(url) { IncomingFiles.shared.receive(url) }
        }
        #endif
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
