func runDesktopInputChecks() {
    var input = LinuxDesktopInputState()
    precondition(input.releaseAll().isEmpty)
    // Every printable US character is represented by a named, paired stroke.
    for ascii in UInt32(32)...126 {
        let text = String(UnicodeScalar(ascii)!)
        precondition(input.text(text)?.count == 1)
        let keys = input.text(text)![0]
        precondition(keys.first != nil && keys.last != nil)
        if keys.count == 4 { precondition(keys.first == .key("shift",true) && keys.last == .key("shift",false)) }
        else { precondition(keys.count == 2) }
    }
    precondition(input.text("echo café\n") == nil) // Whole unsupported paste, no partial command.
    precondition(input.text(String(repeating:"a",count:4097)) == nil)
    precondition(input.toggle("ctrl") == [.key("ctrl",true)])
    // Modifier ownership survives physical key-up while the UI modifier is latched.
    precondition(input.physical("a",down:true,modifiers:["ctrl"]) == [.key("a",true)])
    precondition(input.physical("a",down:false,modifiers:[]) == [.key("a",false)])
    precondition(input.toggle("ctrl") == [.key("ctrl",false)])
    precondition(input.physical("c",down:true,modifiers:["ctrl"]) == [.key("ctrl",true),.key("c",true)])
    precondition(input.releaseAll() == [.key("c",false),.key("ctrl",false)])
    precondition(input.physicalUsage(225,down:true,modifiers:[]) == [.key("shift",true)])
    precondition(input.physicalUsage(229,down:true,modifiers:["shift"]).isEmpty)
    precondition(input.physicalUsage(225,down:false,modifiers:["shift"]).isEmpty)
    precondition(input.physicalUsage(229,down:false,modifiers:["shift"]) == [.key("shift",false)])
    for _ in 0..<10000 {
        precondition(input.point(x:799,y:599,begin:1) == [.pointer(799,599,1,0)])
        precondition(input.releasePointer() == [.pointer(799,599,0,0)])
        precondition(input.releasePointer().isEmpty)
        precondition(input.clickRight() == [.pointer(799,599,2,0),.pointer(799,599,0,0)])
        precondition(input.scroll(99) == [.pointer(799,599,0,8)])
        precondition(input.toggle("shift") == [.key("shift",true)])
        precondition(input.text("A") == [[.key("a",true),.key("a",false)]])
        precondition(input.releaseAll() == [.key("shift",false)])
    }
    precondition(LinuxDesktopInputState.hid(4) == "a")
    precondition(LinuxDesktopInputState.hid(40) == "ret")
    precondition(LinuxDesktopInputState.hid(69) == "f12")
    precondition(LinuxDesktopInputState.hid(79) == "right")
    precondition(LinuxDesktopInputState.hid(224) == nil) // Modifiers use the paired HID/flag state.
    print("LINUX_DESKTOP_INPUT_PASS")
}
