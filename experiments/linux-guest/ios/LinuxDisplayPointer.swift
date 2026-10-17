/// Pure transition state used by the real Metal view; no QEMU or UIKit dependency.
/// A release does not depend on hit testing the final touch location.
struct LinuxDisplayPointer {
    struct Event: Equatable {
        let x: Int32
        let y: Int32
        let down: Bool
    }
    private(set) var held = false
    private var x: Int32 = 0
    private var y: Int32 = 0

    mutating func press(x: Int32, y: Int32) -> Event? {
        guard !held else { return nil }
        held = true
        self.x = x; self.y = y
        return Event(x: x, y: y, down: true)
    }
    mutating func move(x: Int32, y: Int32) -> Event? {
        guard held else { return nil }
        self.x = x; self.y = y
        return Event(x: x, y: y, down: true)
    }
    mutating func release() -> Event? {
        guard held else { return nil }
        held = false
        return Event(x: x, y: y, down: false)
    }
}
