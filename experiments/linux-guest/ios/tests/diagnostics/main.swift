import Foundation

if CommandLine.arguments.count == 3, ["--diagnostic-fifo", "--diagnostic-native-fifo"].contains(CommandLine.arguments[1]) {
    try runDiagnosticFIFOChild(URL(fileURLWithPath: CommandLine.arguments[2], isDirectory: true),
                               nativeLog: CommandLine.arguments[1] == "--diagnostic-native-fifo")
}
if CommandLine.arguments.count == 3, CommandLine.arguments[1] == "--diagnostic-interruption" {
    try runDiagnosticInterruptionChild(URL(fileURLWithPath: CommandLine.arguments[2], isDirectory: true))
}
try runTerminalDiagnosticsChecks()
