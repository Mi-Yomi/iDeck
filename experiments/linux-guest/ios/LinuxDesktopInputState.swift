import Foundation

/// Monotonic VM liveness plus independent text and focus cancellation. Never
/// hold this lock while entering QEMU/BQL. Only queued batches are filtered;
/// an already started batch completes its paired releases on the serial queue.
final class LinuxInputGate {
    private let lock = NSLock()
    private var started = false
    private var ended = false
    private var textGeneration: UInt64 = 0
    private var inputEpoch: UInt64 = 0
    func begin() { lock.lock(); if !ended { started = true }; lock.unlock() }
    func finish() {
        lock.lock(); ended = true; textGeneration &+= 1; inputEpoch &+= 1; lock.unlock()
    }
    func active() -> Bool { lock.lock(); defer { lock.unlock() }; return started && !ended }
    func cancelText() -> UInt64 { lock.lock(); defer { lock.unlock() }; textGeneration &+= 1; return textGeneration }
    func generation() -> UInt64 { lock.lock(); defer { lock.unlock() }; return textGeneration }
    func inputGeneration() -> UInt64 { lock.lock(); defer { lock.unlock() }; return inputEpoch }
    func invalidateInput() {
        lock.lock(); textGeneration &+= 1; inputEpoch &+= 1; lock.unlock()
    }
    func eventsForDelivery(_ events: [LinuxDesktopInputState.Event], generation: UInt64) -> [LinuxDesktopInputState.Event] {
        lock.lock()
        let live = started && !ended
        let current = generation == inputEpoch
        lock.unlock()
        guard live else { return [] }
        if current { return events }
        // A queued key-up may be the only release for an earlier delivered
        // key-down: UI ownership can already have ended before focus is lost.
        return events.filter {
            switch $0 {
            case .key(_, false), .pointerRelease: return true
            default: return false
            }
        }
    }
}

/// Named QKeyCode transitions. UIKit text is converted to the guest's US layout;
/// serial recovery is deliberately not involved in graphical input.
struct LinuxDesktopInputState {
    enum Event: Equatable {
        case key(String, Bool)
        case pointer(Int32, Int32, UInt32, Int32)
        case pointerRelease(Int32, Int32)
    }
    static let modifiers: Set<String> = ["ctrl", "alt", "shift", "meta_l"]
    private(set) var latched: Set<String> = []
    private var hardware: Set<String> = []
    private var hardwareModifiers: Set<String> = []
    private var modifierUsages: Set<Int> = []
    private(set) var buttons: UInt32 = 0
    private var x: Int32 = 0
    private var y: Int32 = 0
    private var held: Set<String> { latched.union(hardware).union(hardwareModifiers) }

    mutating func toggle(_ name: String) -> [Event] {
        guard Self.modifiers.contains(name) else { return [] }
        let before = held
        if latched.contains(name) { latched.remove(name) } else { latched.insert(name) }
        return changes(from: before)
    }
    mutating func physical(_ name: String?, down: Bool, modifiers: Set<String>) -> [Event] {
        let before = held
        hardwareModifiers = modifiers.intersection(Self.modifiers)
        if let name {
            if down { hardware.insert(name) } else { hardware.remove(name) }
        }
        return changes(from: before)
    }
    mutating func physicalUsage(_ usage: Int, down: Bool, modifiers: Set<String>) -> [Event] {
        var normalized = modifiers
        if let name = Self.modifier(usage) {
            if down { modifierUsages.insert(usage) } else { modifierUsages.remove(usage) }
            // UIKit may include the released modifier in pressesEnded flags.
            // Keep the other left/right key's ownership until it too releases.
            if !down && !modifierUsages.contains(where: { Self.modifier($0) == name }) { normalized.remove(name) }
        }
        for usage in modifierUsages { if let name = Self.modifier(usage) { normalized.insert(name) } }
        return physical(Self.hid(usage), down: down, modifiers: normalized)
    }
    private func changes(from before: Set<String>) -> [Event] {
        let up = before.subtracting(held)
        let down = held.subtracting(before)
        let releases = up.filter { !Self.modifiers.contains($0) }.sorted() + up.filter { Self.modifiers.contains($0) }.sorted()
        let presses = down.filter { Self.modifiers.contains($0) }.sorted() + down.filter { !Self.modifiers.contains($0) }.sorted()
        return releases.map { .key($0, false) } + presses.map { .key($0, true) }
    }
    func stroke(_ name: String, shift: Bool = false) -> [Event] {
        var events: [Event] = []
        let temporaryShift = shift && !held.contains("shift")
        if temporaryShift { events.append(.key("shift", true)) }
        events.append(.key(name, true))
        if !held.contains(name) { events.append(.key(name, false)) }
        if temporaryShift { events.append(.key("shift", false)) }
        return events
    }
    /// One indivisible transition unit per character permits cancellation
    /// between characters without leaving temporary Shift or a key down.
    func text(_ text: String) -> [[Event]]? {
        guard text.utf8.count <= 4096 else { return nil }
        var units: [[Event]] = []
        for scalar in text.unicodeScalars {
            guard let code = Self.ascii(scalar.value) else { return nil }
            units.append(stroke(code.0, shift: code.1))
        }
        return units
    }
    static func ascii(_ value: UInt32) -> (String, Bool)? {
        if (97...122).contains(value) { return (String(UnicodeScalar(value)!), false) }
        if (65...90).contains(value) { return (String(UnicodeScalar(value + 32)!), true) }
        if (48...57).contains(value) { return (String(UnicodeScalar(value)!), false) }
        let plain: [UInt32: String] = [9:"tab",10:"ret",13:"ret",32:"spc",45:"minus",61:"equal",
            91:"bracket_left",93:"bracket_right",92:"backslash",59:"semicolon",39:"apostrophe",
            96:"grave_accent",44:"comma",46:"dot",47:"slash"]
        if let key = plain[value] { return (key, false) }
        let shifted: [UInt32: String] = [33:"1",64:"2",35:"3",36:"4",37:"5",94:"6",38:"7",42:"8",
            40:"9",41:"0",95:"minus",43:"equal",123:"bracket_left",125:"bracket_right",
            124:"backslash",58:"semicolon",34:"apostrophe",126:"grave_accent",60:"comma",62:"dot",63:"slash"]
        return shifted[value].map { ($0, true) }
    }
    static func modifier(_ usage: Int) -> String? {
        return [224:"ctrl",225:"shift",226:"alt",227:"meta_l",228:"ctrl",229:"shift",230:"alt",231:"meta_l"][usage]
    }
    /// USB HID usages are stable device codes; QEMU enum numbers never cross ABI.
    static func hid(_ usage: Int) -> String? {
        if (4...29).contains(usage) { return String(UnicodeScalar(usage - 4 + 97)!) }
        if (30...38).contains(usage) { return String(usage - 29) }
        if usage == 39 { return "0" }
        if (58...69).contains(usage) { return "f\(usage - 57)" }
        if (89...97).contains(usage) { return "kp_\(usage - 88)" }
        return [40:"ret",41:"esc",42:"backspace",43:"tab",44:"spc",45:"minus",46:"equal",
                47:"bracket_left",48:"bracket_right",49:"backslash",50:"less",51:"semicolon",
                52:"apostrophe",53:"grave_accent",54:"comma",55:"dot",56:"slash",57:"caps_lock",
                70:"sysrq",71:"scroll_lock",72:"pause",73:"insert",74:"home",75:"pgup",
                76:"delete",77:"end",78:"pgdn",79:"right",80:"left",81:"down",82:"up",
                83:"num_lock",84:"kp_divide",85:"kp_multiply",86:"kp_subtract",87:"kp_add",
                88:"kp_enter",98:"kp_0",99:"kp_decimal"][usage]
    }
    mutating func point(x: Int32, y: Int32, begin: UInt32? = nil) -> [Event] {
        self.x = max(0, min(799, x)); self.y = max(0, min(599, y))
        if let begin { guard buttons == 0 else { return [] }; buttons = begin & 7 }
        return [.pointer(self.x, self.y, buttons, 0)]
    }
    mutating func releasePointer() -> [Event] {
        guard buttons != 0 else { return [] }
        buttons = 0
        return [.pointerRelease(x, y)]
    }
    mutating func clickRight() -> [Event] {
        let release = releasePointer()
        return release + [.pointer(x, y, 2, 0), .pointerRelease(x, y)]
    }
    func scroll(_ steps: Int32) -> [Event] {
        guard steps != 0 else { return [] }
        return [.pointer(x, y, buttons, max(-8, min(8, steps)))]
    }
    mutating func releaseAll() -> [Event] {
        let releases = held.filter { !Self.modifiers.contains($0) }.sorted() + held.filter { Self.modifiers.contains($0) }.sorted()
        let events = releases.map { Event.key($0, false) } + releasePointer()
        latched = []; hardware = []; hardwareModifiers = []; modifierUsages = []
        return events
    }
}
