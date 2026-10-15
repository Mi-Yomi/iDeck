import Foundation
import CryptoKit

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
} catch LinuxGuestProfile.Invalid.asset { }
precondition(!FileManager.default.fileExists(atPath: root.appendingPathComponent("new-session").path))
print("LINUX_PROFILE_HOST_CHECKS_PASS (synthetic assets; no QEMU/device execution)")
