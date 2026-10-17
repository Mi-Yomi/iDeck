import Foundation

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
        precondition(input.releasePointer() == [.pointerRelease(799,599)])
        precondition(input.releasePointer().isEmpty)
        precondition(input.clickRight() == [.pointer(799,599,2,0),.pointerRelease(799,599)])
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

    let gate = LinuxInputGate()
    let initial = gate.inputGeneration()
    precondition(gate.eventsForDelivery([.key("a",true)],generation:initial).isEmpty)
    gate.begin()
    var queued = LinuxDesktopInputState()
    // Ctrl-down already delivered; Ctrl-up is queued and UI ownership has
    // ended. A later focus loss must retain that sole release.
    precondition(gate.eventsForDelivery(queued.toggle("ctrl"),generation:initial) == [.key("ctrl",true)])
    let keyUp = queued.toggle("ctrl")
    precondition(queued.releaseAll().isEmpty)
    gate.invalidateInput()
    precondition(gate.eventsForDelivery(keyUp,generation:initial) == [.key("ctrl",false)])

    let beforeBlur = gate.inputGeneration()
    precondition(gate.eventsForDelivery(queued.point(x:10,y:20,begin:1),generation:beforeBlur) == [.pointer(10,20,1,0)])
    let pointerUp = queued.releasePointer()
    let move = queued.point(x:30,y:40)
    precondition(queued.releaseAll().isEmpty)
    gate.invalidateInput()
    precondition(gate.eventsForDelivery(pointerUp,generation:beforeBlur) == [.pointerRelease(10,20)])
    precondition(gate.eventsForDelivery(move,generation:beforeBlur).isEmpty)
    precondition(gate.eventsForDelivery([.pointer(10,20,1,0),.pointer(10,20,0,3)],generation:beforeBlur).isEmpty)
    // Entire old strokes lose presses, never releases. Temporary Shift does
    // not survive a cancelled paste/stroke, and manual Release is idempotent.
    precondition(gate.eventsForDelivery(queued.stroke("a",shift:true),generation:beforeBlur)
        == [.key("a",false),.key("shift",false)])
    precondition(gate.eventsForDelivery(queued.clickRight(),generation:beforeBlur) == [.pointerRelease(30,40)])
    precondition(queued.releaseAll().isEmpty)

    // Ordinary rapid key events cancel text, not each other. Refocused input
    // is accepted at the new epoch after queued releases, in FIFO order.
    let resumed = gate.inputGeneration()
    let oldText = gate.generation()
    for key in ["esc","tab","left","up","down","right"] {
        _ = gate.cancelText()
        let stroke = queued.stroke(key)
        precondition(gate.eventsForDelivery(stroke,generation:resumed) == stroke)
    }
    precondition(gate.generation() != oldText && gate.inputGeneration() == resumed)
    precondition(gate.eventsForDelivery(queued.physical("c",down:true,modifiers:["alt"]),generation:resumed)
        == [.key("alt",true),.key("c",true)])
    let blurRelease = queued.releaseAll()
    gate.invalidateInput()
    gate.invalidateInput()
    precondition(gate.eventsForDelivery(blurRelease,generation:resumed) == [.key("c",false),.key("alt",false)])

    // Real concurrent gate readers/cancellations: a whole pending pair or its
    // release is possible, never a press without its matching release.
    let group = DispatchGroup()
    for _ in 0..<100 {
        group.enter()
        DispatchQueue.global().async {
            let token = gate.inputGeneration()
            let stroke: [LinuxDesktopInputState.Event] = [.key("a",true),.key("a",false)]
            let accepted = gate.eventsForDelivery(stroke,generation:token)
            precondition(accepted == stroke || accepted == [.key("a",false)])
            gate.invalidateInput()
            group.leave()
        }
    }
    precondition(group.wait(timeout:.now()+5) == .success)
    gate.finish(); gate.begin()
    precondition(!gate.active())
    precondition(gate.eventsForDelivery(blurRelease,generation:gate.inputGeneration()).isEmpty)
    print("LINUX_DESKTOP_INPUT_PASS")
}
