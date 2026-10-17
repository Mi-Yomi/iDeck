func runDisplayPointerChecks() {
    var pointer = LinuxDisplayPointer()
    precondition(pointer.release() == nil)
    precondition(pointer.move(x: 40, y: 50) == nil) // Begin in letterbox was ignored.
    for _ in 0..<10_000 {
        precondition(pointer.press(x: 10, y: 20) == .init(x: 10, y: 20, down: true))
        precondition(pointer.press(x: 30, y: 40) == nil) // No second down owner.
        precondition(pointer.move(x: 799, y: 599) == .init(x: 799, y: 599, down: true))
        // End/cancel outside the view, focus loss, Stop and orientation change
        // all invoke this exact production transition without a hit test.
        precondition(pointer.release() == .init(x: 799, y: 599, down: false))
        precondition(!pointer.held)
        precondition(pointer.release() == nil) // Repeated focus/Stop is idempotent.
        precondition(pointer.move(x: 1, y: 1) == nil)
    }
    print("LINUX_DISPLAY_POINTER_PASS")
}
