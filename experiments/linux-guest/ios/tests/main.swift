import Foundation
import CryptoKit

if CommandLine.arguments.count == 3, ["--diagnostic-fifo", "--diagnostic-native-fifo"].contains(CommandLine.arguments[1]) {
    try runDiagnosticFIFOChild(URL(fileURLWithPath: CommandLine.arguments[2], isDirectory: true),
                               nativeLog: CommandLine.arguments[1] == "--diagnostic-native-fifo")
}
if CommandLine.arguments.count == 3, CommandLine.arguments[1] == "--diagnostic-interruption" {
    try runDiagnosticInterruptionChild(URL(fileURLWithPath: CommandLine.arguments[2], isDirectory: true))
}

// Host-only validation; synthetic bytes are not a Linux boot test.
let root = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)
try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
let data = Data("profile validator test input".utf8)
let sum = SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
for name in ["vmlinuz-virt", "initramfs-ideck.gz"] {
    try data.write(to: root.appendingPathComponent(name))
}
let description: [String: Any] = [
    "schema": 1, "width": 800, "height": 600, "cpu": "cortex-a72",
    "memory_mib": 1024, "vcpus": 4, "tcg_cache_mib": 256,
    "kernel": ["file": "vmlinuz-virt", "sha256": sum, "size": data.count],
    "initramfs": ["file": "initramfs-ideck.gz", "sha256": sum, "size": data.count]
]
try JSONSerialization.data(withJSONObject: description).write(to: root.appendingPathComponent("profile.json"))
let profile = try LinuxGuestProfile.load(from: root)
let session = root.appendingPathComponent("session,one")
let args = try profile.arguments(assets: root, session: session)
precondition(args.contains("tcg,thread=multi,tb-size=256,split-wx=on"))
precondition(args.contains(where: { $0.contains("session,,one/linux-serial.log") }))
do {
    _ = try profile.arguments(assets: root, session: session)
    fatalError("existing session was accepted")
} catch LinuxGuestProfile.Invalid.sessionAlreadyExists { }
try Data("corrupt".utf8).write(to: root.appendingPathComponent("vmlinuz-virt"))
do {
    _ = try profile.arguments(assets: root, session: root.appendingPathComponent("new-session"))
    fatalError("corrupt asset was accepted")
} catch LinuxGuestProfile.Invalid.assetSize { }
precondition(!FileManager.default.fileExists(atPath: root.appendingPathComponent("new-session").path))
print("LINUX_PROFILE_HOST_CHECKS_PASS (synthetic assets; no QEMU/device execution)")

// The input fixture is the captured serial log from the real ARM64 Linux run.
// Parsing it on a Mac is a validator test, not a second kernel/device run.
let serialFixture = try String(contentsOfFile: CommandLine.arguments[2], encoding: .utf8)
try LinuxProbeEvidence.validate(serial: serialFixture)
for bad in [serialFixture.replacingOccurrences(of: "IDECK_EVENTS_BEGIN:keyboard", with: "missing"),
            "IDECK_PROBE_DONE\nQEMU Virtio Keyboard\nQEMU Virtio Tablet\n"] {
    do {
        try LinuxProbeEvidence.validate(serial: bad)
        fatalError("non-evidence was accepted")
    } catch { }
}
func record(type: UInt16, code: UInt16, value: Int32) -> String {
    var bytes = [UInt8](repeating: 0, count: 16)
    bytes += [UInt8(type & 255), UInt8(type >> 8), UInt8(code & 255), UInt8(code >> 8)]
    let unsigned = UInt32(bitPattern: value)
    bytes += (0..<4).map { UInt8((unsigned >> ($0 * 8)) & 255) }
    return bytes.map { String(format: "%02x", $0) }.joined(separator: " ") + "\n"
}
let reverseKey = "IDECK_EVENTS_BEGIN:keyboard\n" + record(type: 1, code: 30, value: 0)
    + record(type: 1, code: 30, value: 1) + "IDECK_EVENTS_END:keyboard\n"
let tablet = "IDECK_EVENTS_BEGIN:tablet\n" + record(type: 1, code: 272, value: 1)
    + record(type: 3, code: 0, value: 8192) + record(type: 3, code: 1, value: 24575)
    + record(type: 1, code: 272, value: 0) + "IDECK_EVENTS_END:tablet\n"
do {
    try LinuxProbeEvidence.validate(serial: reverseKey + tablet)
    fatalError("release-before-press accepted")
} catch LinuxProbeEvidence.Invalid.key { }

// Check strict row-stride/channel/last-pixel handling, including unused alpha.
let colors: [[UInt8]] = [[34, 51, 204], [51, 204, 68], [204, 85, 34], [204, 204, 204]]
var pixels = Data(repeating: 0, count: 3216 * 600)
for y in 0..<600 {
    for x in 0..<800 {
        let color = colors[(y / 300) * 2 + x / 400]
        for channel in 0..<3 { pixels[y * 3216 + x * 4 + channel] = color[channel] }
    }
}
precondition(LinuxProbeEvidence.matchesFrame(pixels, stride: 3216, phase: 0))
precondition(!LinuxProbeEvidence.matchesFrame(pixels, stride: 3216, phase: 1))
pixels[599 * 3216 + 799 * 4] ^= 1
precondition(!LinuxProbeEvidence.matchesFrame(pixels, stride: 3216, phase: 0))
precondition(!LinuxProbeEvidence.matchesFrame(Data(), stride: 0, phase: 0))
print("LINUX_EVIDENCE_HOST_CHECKS_PASS (recorded guest events + synthetic pixel guards)")

// Exercise the same pure Foundation Markdown renderer shipped in the app.
try runMarkdownReportChecks()

// Real disk/configuration helpers; not a Linux boot or persistence claim.
try runTerminalChecks()

// Durable journal recovery/export with a real native-exit child process.
try runTerminalDiagnosticsChecks()
