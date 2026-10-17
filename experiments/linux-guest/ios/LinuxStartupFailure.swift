import Foundation

/// Fixed failure names only. Never export an Error's arbitrary text or paths.
enum LinuxStartupFailure {
    static func classify(_ error: Error) -> LinuxTerminalDiagnostics.Failure {
        let name: String
        if let value = error as? LinuxDesktopDisk.Invalid { name = String(describing: value) }
        else if let value = error as? LinuxDesktopProfile.Invalid { name = String(describing: value) }
        else if let value = error as? LinuxTerminalProfile.Invalid { name = String(describing: value) }
        else if let value = error as? LinuxGuestProfile.Invalid { name = String(describing: value) }
        else { return .unknown }
        return LinuxTerminalDiagnostics.Failure(rawValue: name) ?? .unknown
    }
}
