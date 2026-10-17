import Foundation

func runGUIProfileChecks(root: URL) throws {
    let assets = root.appendingPathComponent("gui-profile-fixture", isDirectory: true)
    try FileManager.default.createDirectory(at: assets, withIntermediateDirectories: true)
    let asset: (String, Int64) -> [String: Any] = { name,size in ["file":name,"size":size,"sha256":String(repeating:"a",count:64)] }
    let valid: [String: Any] = ["schema":1,"mode":"desktop","control_port":"org.ideck.control",
        "kernel":asset("vmlinuz-virt",10_351_104),"initramfs":asset("initramfs-desktop.gz",12_000_000),
        "rootfs":asset("gui-rootfs-v1.raw",LinuxGUIProfile.size),
        "image":["size_bytes":LinuxGUIProfile.size,"uuid":LinuxGUIProfile.uuid,"block_size":4096,
                 "features":["compat":44,"incompat":194,"ro_compat":1091]]]
    let file = assets.appendingPathComponent("desktop-profile.json")
    try JSONSerialization.data(withJSONObject:valid).write(to:file)
    let profile = try LinuxGUIProfile.load(from:assets)
    precondition(profile.mode == "desktop" && profile.image.uuid == LinuxGUIProfile.uuid)
    for field in ["mode","control_port","rootfs","image"] {
        var bad = valid
        switch field {
        case "mode": bad[field] = "debian"
        case "control_port": bad[field] = "shell"
        case "rootfs": bad[field] = asset("rootfs-v1.raw",LinuxGUIProfile.size)
        default:
            var image = valid["image"] as! [String: Any]
            image["uuid"] = "29c758bc-0416-4d87-b1ba-a922238a07f5"; bad[field] = image
        }
        try JSONSerialization.data(withJSONObject:bad).write(to:file)
        do { _ = try LinuxGUIProfile.load(from:assets); preconditionFailure("invalid GUI profile accepted") }
        catch { }
    }
    try Data(repeating:32,count:65537).write(to:file)
    do { _ = try LinuxGUIProfile.load(from:assets); preconditionFailure("oversized GUI profile accepted") }
    catch { }
    print("LINUX_GUI_PROFILE_PASS")
}
