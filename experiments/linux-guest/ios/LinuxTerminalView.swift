import SwiftUI

/// A local line console, without a claim of full VT terminal emulation.
struct LinuxTerminalView: View {
    @ObservedObject private var session = LinuxTerminalSession.shared
    @ObservedObject private var jit = JITCoordinator.shared
    @Environment(\.scenePhase) private var scenePhase
    @State private var command = ""
    @State private var showShare = false
    @State private var shareItems: [URL] = []

    var body: some View {
        ScrollView {
            VStack(spacing: 12) {
                Text("iDeck · Linux terminal").font(.headline)
                Text(session.message).font(.callout).multilineTextAlignment(.center)
                Text(session.jitExecutionMessage).font(.footnote)
                    .foregroundStyle(session.jitExecutionReady ? Color.green : Color.secondary)
                if jit.busy { ProgressView(jit.status ?? "Enabling JIT…") }
                else if let status = jit.status { Text(status == "JIT is on." ? "Debugger attached." : status).font(.footnote) }
                if let error = jit.error { Text(error).font(.footnote).foregroundStyle(.orange) }
                Button("JIT setup and method") { jit.refreshPairingStatus(); jit.showSetup = true }.disabled(jit.busy)
                HStack {
                    Button("Enable JIT") { enableJIT() }.disabled(session.attempted || jit.busy)
                    Button("Start terminal") { session.start() }.disabled(session.attempted || jit.busy)
                    Button("Stop Linux") { session.stop() }.disabled(!session.canStop || session.stopping)
                }.buttonStyle(.bordered)
                ScrollView([.vertical, .horizontal]) {
                    Text(session.transcript.isEmpty ? "Waiting for Linux serial output…" : session.transcript)
                        .font(.system(.caption, design: .monospaced))
                        .textSelection(.enabled)
                        .frame(maxWidth: .infinity, alignment: .topLeading)
                        .padding(8)
                }.frame(minHeight: 240, maxHeight: 420)
                    .background(Color.black.opacity(0.9)).foregroundStyle(.white)
                    .accessibilityIdentifier("ideck-linux-terminal-output")
                HStack {
                    TextField("Linux command", text: $command)
                        .textInputAutocapitalization(.never).autocorrectionDisabled()
                        .textFieldStyle(.roundedBorder).onSubmit { submit() }
                        .disabled(!session.ready || session.stopping)
                    Button("Send") { submit() }.disabled(!session.ready || session.stopping)
                }
                HStack {
                    Button("Ctrl-C") { session.sendControl(3) }
                    Button("Ctrl-D") { session.sendControl(4) }
                    Button("Tab") { session.sendControl(9) }
                    Button("Esc") { session.sendControl(27) }
                }.buttonStyle(.bordered).disabled(!session.ready || session.stopping)
                Menu("Save report") {
                    Button("Markdown report (.md)") {
                        guard let file = session.markdownFile else { return }
                        shareItems = [file]; showShare = true
                    }.disabled(session.markdownFile == nil)
                    Button("Raw JSON and serial log") { shareItems = session.shareFiles; showShare = true }
                        .disabled(session.shareFiles.isEmpty)
                }.disabled(session.markdownFile == nil && session.shareFiles.isEmpty)
                if let error = session.exportError { Text(error).font(.footnote).foregroundStyle(.orange) }
                Text("Local line console. Keep files in /data and use Stop Linux before closing the app. FAT16 does not preserve Unix permissions or symlinks. Full-screen terminal apps and Steam are not included.")
                    .font(.footnote).foregroundStyle(.secondary)
            }.padding()
        }
        .sheet(isPresented: $jit.showSetup) { JITSetupFlow() }
        .sheet(isPresented: $showShare) { ShareSheet(items: shareItems) }
        .onAppear { claimJIT() }
        .onChange(of: jit.attachGeneration) { _ in claimJIT() }
        .onChange(of: scenePhase) { if $0 == .active { claimJIT() } }
    }

    private func submit() {
        guard session.ready, !session.stopping else { return }
        session.sendLine(command)
        command = ""
    }

    private func claimJIT() { jit.refreshPairingStatus(); session.claimJIT() }

    private func enableJIT() {
        guard !session.attempted, !jit.busy else { return }
        jit.refreshPairingStatus()
        if jit.method == .automatic, HuskBuiltInJIT.isAvailable { jit.method = .builtIn }
        jit.enable()
    }
}
