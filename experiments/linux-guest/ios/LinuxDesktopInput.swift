import Foundation
import Combine
import UIKit

/// A monotonic VM-liveness gate. Never hold this lock while entering QEMU/BQL.
private final class LinuxInputGate {
    private let lock = NSLock()
    private var started = false
    private var ended = false
    private var textGeneration: UInt64 = 0
    func begin() { lock.lock(); if !ended { started = true }; lock.unlock() }
    func finish() { lock.lock(); ended = true; textGeneration &+= 1; lock.unlock() }
    func active() -> Bool { lock.lock(); defer { lock.unlock() }; return started && !ended }
    func cancelText() -> UInt64 { lock.lock(); defer { lock.unlock() }; textGeneration &+= 1; return textGeneration }
    func generation() -> UInt64 { lock.lock(); defer { lock.unlock() }; return textGeneration }
}

/// Graphical input always enters QEMU on a dedicated queue, never the main UI
/// thread. A late BQL wait cannot freeze iOS; VM lifetime/locks remain retained.
final class LinuxDesktopInput: ObservableObject {
    @Published private(set) var enabled = false
    @Published private(set) var latched: Set<String> = []
    @Published private(set) var message = "US keyboard layout; text, special keys and modifiers go to Linux."
    private var state = LinuxDesktopInputState()
    private var focused = false
    private let gate = LinuxInputGate()
    private let queue = DispatchQueue(label: "ideck.desktop.input", qos: .userInteractive)

    func guestReady() {
        precondition(Thread.isMainThread)
        gate.begin(); enabled = focused && gate.active()
    }
    /// Called on the QEMU owner thread immediately after loop return, before
    /// retention. It never waits for an in-flight BQL call or releases QEMU.
    func guestEnded() {
        gate.finish()
        DispatchQueue.main.async { self.enabled = false; _ = self.state.releaseAll(); self.latched = [] }
    }
    func setFocused(_ focused: Bool) {
        precondition(Thread.isMainThread)
        self.focused = focused
        if focused { enabled = gate.active() }
        else { releaseHeld(); enabled = false }
    }
    private func emit(_ events: [LinuxDesktopInputState.Event]) {
        guard !events.isEmpty else { return }
        queue.async { self.deliver(events) }
    }
    private func deliver(_ events: [LinuxDesktopInputState.Event]) {
        for event in events {
            guard gate.active() else { return }
            switch event {
            case .key(let name, let down):
                _ = name.withCString { husk_display_send_key($0, down) }
            case .pointer(let x, let y, let buttons, let wheel):
                _ = husk_display_send_pointer_buttons(x, y, buttons, wheel)
            }
        }
    }
    func releaseHeld() {
        precondition(Thread.isMainThread)
        _ = gate.cancelText()
        emit(state.releaseAll()); latched = []
    }
    func prepareStop(_ completion: @escaping () -> Void) {
        precondition(Thread.isMainThread)
        enabled = false; releaseHeld()
        // Normally releases precede Stop. The independent control channel must
        // still work if a QEMU/BQL call stalls; worker.stop() is idempotent.
        queue.async { completion() }
        DispatchQueue.global(qos: .userInitiated).asyncAfter(deadline: .now() + .milliseconds(250)) { completion() }
    }
    func toggle(_ name: String) {
        guard enabled else { return }
        _ = gate.cancelText()
        emit(state.toggle(name)); latched = state.latched
    }
    func key(_ name: String) {
        guard enabled else { return }
        _ = gate.cancelText()
        emit(state.stroke(name))
    }
    func text(_ text: String) {
        guard enabled else { return }
        guard let units = state.text(text) else {
            message = "Text was not sent: use the US layout, at most 4096 characters. No partial paste was sent."
            return
        }
        let generation = gate.generation()
        queue.async {
            for unit in units {
                guard self.gate.active(), self.gate.generation() == generation else { return }
                self.deliver(unit)
                // Separate virtual-device queues and bulk pastes need pacing.
                // Cancellation is checked between complete paired key units.
                Thread.sleep(forTimeInterval: 0.008)
            }
        }
    }
    func physical(_ usage: Int, down: Bool, flags: UIKeyModifierFlags) {
        guard enabled else { return }
        _ = gate.cancelText()
        var modifiers = Set<String>()
        if flags.contains(.shift) { modifiers.insert("shift") }
        if flags.contains(.control) { modifiers.insert("ctrl") }
        if flags.contains(.alternate) { modifiers.insert("alt") }
        if flags.contains(.command) { modifiers.insert("meta_l") }
        emit(state.physicalUsage(usage, down: down, modifiers: modifiers))
    }
    func point(x: Int32, y: Int32, begin: UInt32? = nil) {
        guard enabled else { return }
        if begin != nil { _ = gate.cancelText() }
        emit(state.point(x: x, y: y, begin: begin))
    }
    func pointerUp() { emit(state.releasePointer()) }
    func rightClick() { guard enabled else { return }; _ = gate.cancelText(); emit(state.clickRight()) }
    func scroll(_ steps: Int32) { guard enabled else { return }; emit(state.scroll(steps)) }
}
