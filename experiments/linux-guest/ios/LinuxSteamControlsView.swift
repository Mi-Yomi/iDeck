import SwiftUI
import UIKit

private final class LinuxScreenControlAccessibility: UIAccessibilityElement {
    var activate: (() -> Bool)?
    override func accessibilityActivate() -> Bool { activate?() ?? false }
}

/// Original UIKit overlay: each touch retains its own control, blank areas pass
/// through to HuskMetalView. No DroidDeck code/assets or Android HID calls.
private final class LinuxScreenControlsView: UIView {
    typealias Control = LinuxSteamControlsState.Control
    var input: LinuxDesktopInput?
    var enabled = false { didSet { if !enabled { reset() } } }
    private var frames: [Control: CGRect] = [:]
    private var touches: [ObjectIdentifier: (control: Control, point: CGPoint)] = [:]
    private var previousSize = CGSize.zero

    override init(frame: CGRect) {
        super.init(frame: frame)
        isMultipleTouchEnabled = true; isOpaque = false; backgroundColor = .clear
    }
    required init?(coder: NSCoder) { fatalError("init(coder:) has not been implemented") }
    func reset() { touches = [:]; input?.releaseScreenControls(); setNeedsDisplay() }
    override func layoutSubviews() {
        super.layoutSubviews()
        if bounds.size != previousSize { reset(); previousSize = bounds.size }
        let w = bounds.width, h = bounds.height
        let size: CGFloat = min(48, max(36, min(w / 8, h / 6)))
        let step = size, radius = h < 300 ? max(22, h * 0.08) : min(48, h * 0.14)
        func box(_ c: Control, _ x: CGFloat, _ y: CGFloat, _ width: CGFloat = 0, _ height: CGFloat = 0) {
            frames[c] = CGRect(x: x - (width == 0 ? size : width)/2, y: y - (height == 0 ? size : height)/2,
                               width: width == 0 ? size : width, height: height == 0 ? size : height)
        }
        let left = step * 1.5, right = w - left
        box(.leftStick, left, h * 0.35, radius * 2, radius * 2)
        box(.rightStick, right, h - step * 1.4, radius * 2, radius * 2)
        for (control, dx, dy) in [(Control.up,0,-1),(.down,0,1),(.left,-1,0),(.right,1,0)] {
            box(control, left + CGFloat(dx)*step, h - step*1.5 + CGFloat(dy)*step)
        }
        for (control, dx, dy) in [(Control.y,0,-1),(.a,0,1),(.x,-1,0),(.b,1,0)] {
            box(control, right + CGFloat(dx)*step, step * 2.5 + CGFloat(dy)*step)
        }
        box(.l1, step, size/2 + 3, size*1.5, size*0.65)
        box(.l2, step*2.7, size/2 + 3, size*1.5, size*0.65)
        box(.r1, w-step, size/2 + 3, size*1.5, size*0.65)
        box(.r2, w-step*2.7, size/2 + 3, size*1.5, size*0.65)
        box(.select, w*0.4, h-size/2-3, size*1.2, size*0.65)
        box(.start, w*0.6, h-size/2-3, size*1.2, size*0.65)
        accessibilityElements = Control.allCases.compactMap { control -> UIAccessibilityElement? in
            guard let rect = frames[control] else { return nil }
            let element = LinuxScreenControlAccessibility(accessibilityContainer: self)
            element.accessibilityLabel = label(control)
            element.accessibilityFrameInContainerSpace = rect
            element.accessibilityTraits = .button
            if control == .leftStick || control == .rightStick {
                element.accessibilityCustomActions = [("Up",0.0,-1.0),("Down",0.0,1.0),("Left",-1.0,0.0),("Right",1.0,0.0)].map { name, x, y in
                    UIAccessibilityCustomAction(name: name) { [weak self] _ in
                        guard let self, self.enabled else { return false }
                        self.input?.screenControl(control, down: true, x: x, y: y)
                        self.input?.screenControl(control, down: false)
                        return true
                    }
                }
            } else {
                element.activate = { [weak self] in
                    guard let self, self.enabled else { return false }
                    self.input?.screenControl(control, down: true); self.input?.screenControl(control, down: false)
                    return true
                }
            }
            return element
        }
        setNeedsDisplay()
    }
    override func point(inside point: CGPoint, with event: UIEvent?) -> Bool {
        enabled && frames.values.contains { $0.contains(point) }
    }
    override func touchesBegan(_ incoming: Set<UITouch>, with event: UIEvent?) {
        guard enabled else { return }
        for touch in incoming {
            let point = touch.location(in: self)
            if let control = Control.allCases.first(where: { frames[$0]?.contains(point) == true }) {
                if (control == .leftStick || control == .rightStick) && touches.values.contains(where: { $0.control == control }) { continue }
                touches[ObjectIdentifier(touch)] = (control, point); update(control)
            }
        }
        setNeedsDisplay()
    }
    override func touchesMoved(_ incoming: Set<UITouch>, with event: UIEvent?) {
        guard enabled else { return }
        for touch in incoming {
            let id = ObjectIdentifier(touch)
            guard let value = touches[id] else { continue }
            touches[id] = (value.control, touch.location(in: self)); update(value.control)
        }
        setNeedsDisplay()
    }
    override func touchesEnded(_ incoming: Set<UITouch>, with event: UIEvent?) { finish(incoming) }
    override func touchesCancelled(_ incoming: Set<UITouch>, with event: UIEvent?) { finish(incoming) }
    private func finish(_ incoming: Set<UITouch>) {
        for touch in incoming { if let value = touches.removeValue(forKey: ObjectIdentifier(touch)) { update(value.control) } }
        setNeedsDisplay()
    }
    private func update(_ control: Control) {
        guard let rect = frames[control] else { return }
        let active = touches.values.filter { $0.control == control }
        if control == .leftStick || control == .rightStick, let point = active.first?.point {
            input?.screenControl(control, down: true, x: Double((point.x-rect.midX)/(rect.width/2)), y: Double((point.y-rect.midY)/(rect.height/2)))
        } else {
            input?.screenControl(control, down: active.contains { rect.insetBy(dx: -8, dy: -8).contains($0.point) })
        }
    }
    private func label(_ control: Control) -> String {
        switch control {
        case .leftStick: return "Left stick · WASD"
        case .rightStick: return "Right stick · arrows"
        case .a: return "A · Enter"
        case .b: return "B · Escape"
        case .x: return "X · Space"
        case .y: return "Y · Tab"
        case .l1: return "L1 · Shift"
        case .r1: return "R1 · Control"
        case .l2: return "L2 · right mouse"
        case .r2: return "R2 · left mouse"
        default: return control.rawValue.capitalized
        }
    }
    override func draw(_ rect: CGRect) {
        for control in Control.allCases {
            guard let frame = frames[control] else { continue }
            let active = touches.values.contains { $0.control == control }
            let path = UIBezierPath(roundedRect: frame.insetBy(dx: 2, dy: 2), cornerRadius: min(frame.width,frame.height)/2)
            (active ? UIColor.systemTeal.withAlphaComponent(0.8) : UIColor.black.withAlphaComponent(0.5)).setFill(); path.fill()
            UIColor.white.withAlphaComponent(0.8).setStroke(); path.lineWidth = 1; path.stroke()
            let text = control == .leftStick ? "WASD" : control == .rightStick ? "↑↓←→" : control.rawValue.uppercased()
            let attrs: [NSAttributedString.Key: Any] = [.font:UIFont.boldSystemFont(ofSize: 11), .foregroundColor:UIColor.white]
            let measured = (text as NSString).size(withAttributes: attrs)
            (text as NSString).draw(at: CGPoint(x: frame.midX-measured.width/2, y: frame.midY-measured.height/2), withAttributes: attrs)
            if control == .leftStick || control == .rightStick, let point = touches.values.first(where: { $0.control == control })?.point {
                let x = min(frame.maxX-8, max(frame.minX+8, point.x)), y = min(frame.maxY-8, max(frame.minY+8, point.y))
                UIColor.systemTeal.setFill(); UIBezierPath(ovalIn: CGRect(x:x-8,y:y-8,width:16,height:16)).fill()
            }
        }
    }
}

struct LinuxSteamControlsView: UIViewRepresentable {
    let input: LinuxDesktopInput
    let enabled: Bool
    func makeUIView(context: Context) -> UIView {
        let view = LinuxScreenControlsView(); view.input = input; view.enabled = enabled; return view
    }
    func updateUIView(_ view: UIView, context: Context) {
        guard let view = view as? LinuxScreenControlsView else { return }
        view.input = input; view.enabled = enabled
    }
    static func dismantleUIView(_ view: UIView, coordinator: ()) { (view as? LinuxScreenControlsView)?.reset() }
}
