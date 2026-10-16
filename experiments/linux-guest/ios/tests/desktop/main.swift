import Foundation

if CommandLine.arguments.count == 4, CommandLine.arguments[1] == "--desktop-interrupted-import" {
    try runDesktopInterruptedImport(directory: URL(fileURLWithPath: CommandLine.arguments[2]),
                                    fixture: URL(fileURLWithPath: CommandLine.arguments[3]))
}

if CommandLine.arguments.count == 5, CommandLine.arguments[1] == "--desktop-disk-contender" {
    try runDesktopDiskContender(directory: URL(fileURLWithPath: CommandLine.arguments[2]),
                                fixture: URL(fileURLWithPath: CommandLine.arguments[3]),
                                locked: CommandLine.arguments[4] == "locked")
}
if CommandLine.arguments.count == 4, CommandLine.arguments[1] == "--real-image" {
    struct Profile: Decodable { let image: LinuxDesktopDisk.Specification }
    let decoder = JSONDecoder(); decoder.keyDecodingStrategy = .convertFromSnakeCase
    let profile = try decoder.decode(Profile.self, from: Data(contentsOf: URL(fileURLWithPath: CommandLine.arguments[3])))
    let image = URL(fileURLWithPath: CommandLine.arguments[2])
    precondition(image.lastPathComponent == "rootfs-v1.raw")
    let disk = try LinuxDesktopDisk.openExisting(directory: image.deletingLastPathComponent(), specification: profile.image)
    try disk.validateOwnership(); disk.closeUnused()
    print("REAL_EXT4_IMAGE_SWIFT_CONTRACT_PASS (not fsck or guest mount)")
} else {
    try runDesktopDiskChecks(fixture: URL(fileURLWithPath: "experiments/linux-guest/ios/tests/fixtures/desktop-ext4-superblock.json"))
}
