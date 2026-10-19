func runSteamControlsChecks() {
    var pad = LinuxSteamControlsState()
    var input = LinuxDesktopInputState()
    func apply() -> [LinuxDesktopInputState.Event] { input.screen(keys: pad.keys, buttons: pad.buttons) }
    pad.set(.leftStick, down: true, x: -1, y: -1)
    precondition(apply() == [.key("a", true), .key("w", true)])
    pad.set(.a, down: true); pad.set(.r2, down: true)
    precondition(apply() == [.key("ret", true), .pointer(0,0,1,0)])
    // Independent touches and overlapping keyboard sources must not release peers.
    pad.set(.start, down: true); pad.set(.a, down: false)
    precondition(apply().isEmpty)
    precondition(input.physical("w", down: true, modifiers: []).isEmpty)
    pad.set(.leftStick, down: false)
    precondition(apply() == [.key("a", false)])
    precondition(input.physical("w", down: false, modifiers: []) == [.key("w", false)])
    pad.set(.up, down: true); pad.set(.rightStick, down: true, x: 0, y: -1)
    precondition(apply() == [.key("up", true)])
    pad.set(.up, down: false); precondition(apply().isEmpty)
    pad.set(.rightStick, down: true, x: 0.1, y: -0.1)
    precondition(apply() == [.key("up", false)])
    pad.set(.leftStick, down: true, x: .infinity, y: .nan); precondition(apply().isEmpty)
    // Touch mouse release does not release the held trigger (and vice versa).
    precondition(input.point(x:300,y:200,begin:2) == [.pointer(300,200,3,0)])
    pad.set(.r2, down: false); precondition(apply() == [.pointer(300,200,2,0)])
    precondition(input.releasePointer() == [.pointer(300,200,0,0)])
    pad.set(.l1, down: true); pad.set(.r1, down: true); pad.set(.l2, down: true)
    _ = apply()
    let released = input.releaseAll()
    precondition(released.contains(.key("shift",false)) && released.contains(.key("ctrl",false)))
    precondition(released.contains(.key("ret",false)) && released.contains(.pointer(300,200,0,0)))
    pad.releaseAll(); precondition(apply().isEmpty && input.releaseAll().isEmpty)
    for control in LinuxSteamControlsState.Control.allCases {
        pad.set(control, down: true, x: 1, y: 1); _ = apply()
        pad.releaseAll(); _ = apply()
        precondition(input.releaseAll().isEmpty)
    }
    print("LINUX_STEAM_SCREEN_CONTROLS_PASS (digital sticks/keyboard/mouse, chords, independent ownership, neutral/nonfinite, release-all)")
}
