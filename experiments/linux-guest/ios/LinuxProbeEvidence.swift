import Foundation

/// Interprets real Linux evdev captures, not a device-name/byte-presence test.
/// This proves guest input only. Physical screen presentation needs a device run.
enum LinuxProbeEvidence {
    struct Event {
        let type: UInt16
        let code: UInt16
        let value: Int32
    }
    enum Invalid: Error { case capture, key, pointer, axes }

    static func events(in serial: String, label: String) throws -> [Event] {
        guard let start = serial.range(of: "IDECK_EVENTS_BEGIN:\(label)\n"),
              let end = serial.range(of: "IDECK_EVENTS_END:\(label)", range: start.upperBound..<serial.endIndex)
        else { throw Invalid.capture }
        let tokens = serial[start.upperBound..<end.lowerBound].split(whereSeparator: { $0.isWhitespace })
        guard !tokens.isEmpty, tokens.count <= 262144, tokens.count % 24 == 0 else { throw Invalid.capture }
        let bytes = try tokens.map { token -> UInt8 in
            guard token.count == 2, let byte = UInt8(token, radix: 16) else { throw Invalid.capture }
            return byte
        }
        func u16(_ offset: Int) -> UInt16 { UInt16(bytes[offset]) | UInt16(bytes[offset + 1]) << 8 }
        func i32(_ offset: Int) -> Int32 {
            let value = UInt32(bytes[offset]) | UInt32(bytes[offset + 1]) << 8
                | UInt32(bytes[offset + 2]) << 16 | UInt32(bytes[offset + 3]) << 24
            return Int32(bitPattern: value)
        }
        return stride(from: 0, to: bytes.count, by: 24).map {
            Event(type: u16($0 + 16), code: u16($0 + 18), value: i32($0 + 20))
        }
    }

    static func validate(serial: String) throws {
        let normalized = serial.replacingOccurrences(of: "\r\n", with: "\n")
        let keys = try events(in: normalized, label: "keyboard")
        let pointer = try events(in: normalized, label: "tablet")
        func pressAndRelease(_ events: [Event], code: UInt16) -> Bool {
            guard let down = events.firstIndex(where: { $0.type == 1 && $0.code == code && $0.value == 1 }) else { return false }
            return events.dropFirst(down + 1).contains { $0.type == 1 && $0.code == code && $0.value == 0 }
        }
        guard pressAndRelease(keys, code: 30) else { throw Invalid.key }
        guard pressAndRelease(pointer, code: 272) else { throw Invalid.pointer }
        // A physical tap may be anywhere in the image. QEMU's absolute tablet
        // uses 0...32767; the host QMP test separately checks exact coordinates.
        for axis in [UInt16(0), UInt16(1)] {
            guard pointer.contains(where: { $0.type == 3 && $0.code == axis && (0...32767).contains($0.value) })
            else { throw Invalid.axes }
        }
    }

    static func matchesFrame(_ bytes: Data, stride rowBytes: Int, phase: Int) -> Bool {
        guard (0...1).contains(phase), rowBytes >= 3200, rowBytes <= 8192,
              bytes.count == rowBytes * 600 else { return false }
        let colors: [[UInt8]] = [[34, 51, 204], [51, 204, 68], [204, 85, 34], [204, 204, 204]]
        // QEMU's x8r8g8b8 alpha byte is unspecified. Check every RGB channel;
        // row padding is deliberately excluded from pixel acceptance.
        return bytes.withUnsafeBytes { raw in
            let p = raw.bindMemory(to: UInt8.self)
            for y in 0..<600 {
                for x in 0..<800 {
                    let color = colors[((y / 300) * 2 + x / 400 + phase) % 4]
                    let offset = y * rowBytes + x * 4
                    if p[offset] != color[0] || p[offset + 1] != color[1] || p[offset + 2] != color[2] { return false }
                }
            }
            return true
        }
    }
}
