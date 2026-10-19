/// Screen controls map to the existing QEMU keyboard/mouse, not a Linux HID pad.
struct LinuxSteamControlsState {
    enum Control: String, CaseIterable {
        case leftStick, rightStick, up, down, left, right, a, b, x, y, l1, r1, l2, r2, start, select
    }
    private var held: [Control: Set<String>] = [:]
    private var mouse: [Control: UInt32] = [:]
    var keys: Set<String> { held.values.reduce(into: []) { $0.formUnion($1) } }
    var buttons: UInt32 { mouse.values.reduce(0, |) }

    mutating func set(_ control: Control, down: Bool, x: Double = 0, y: Double = 0) {
        held[control] = nil; mouse[control] = nil
        guard down else { return }
        if control == .leftStick || control == .rightStick {
            guard x.isFinite, y.isFinite else { return }
            var keys = Set<String>()
            let codes = control == .leftStick ? ["a", "d", "w", "s"] : ["left", "right", "up", "down"]
            if x < -0.22 { keys.insert(codes[0]) }; if x > 0.22 { keys.insert(codes[1]) }
            if y < -0.22 { keys.insert(codes[2]) }; if y > 0.22 { keys.insert(codes[3]) }
            held[control] = keys
        } else if control == .l2 || control == .r2 {
            mouse[control] = control == .l2 ? 2 : 1
        } else {
            let codes: [Control: String] = [.up:"up", .down:"down", .left:"left", .right:"right",
                .a:"ret", .b:"esc", .x:"spc", .y:"tab", .l1:"shift", .r1:"ctrl", .start:"ret", .select:"esc"]
            if let key = codes[control] { held[control] = [key] }
        }
    }
    mutating func releaseAll() { held = [:]; mouse = [:] }
}
