import Foundation

/// Conservative process-budget policy, not a claim about physical device RAM.
enum LinuxSteamMemory {
    enum Mode: String, CaseIterable, Hashable { case auto, fixed1536 }
    enum Failure: Error { case unavailable, insufficient, overflow }
    static let mib: UInt64 = 1024 * 1024
    static let minimum = 1536
    static let ceiling = 4096 // Experimental capped ceiling; device acceptance pending.
    struct Plan: Equatable {
        let guestMib: Int
        let overhead: UInt64
        let reserve: UInt64
        let sampledBudget: UInt64
        var required: UInt64 { UInt64(guestMib) * LinuxSteamMemory.mib + overhead + reserve }
        func recheck(_ available: UInt64?) throws {
            guard let available, available > 0 else { throw Failure.unavailable }
            guard available >= required else { throw Failure.insufficient }
        }
    }
    /// available is ADDITIONAL process budget; never subtract current RSS again.
    /// H includes future JIT/TCG commitment and display/QEMU/IO growth. Keeping
    /// the full conservative H avoids inferring resident bytes from prewarmed VA.
    static func plan(available: UInt64?, mode: Mode,
                     hostOverhead: UInt64 = 1024 * LinuxSteamMemory.mib,
                     safetyReserve: UInt64 = 1024 * LinuxSteamMemory.mib) throws -> Plan {
        guard let available, available > 0 else { throw Failure.unavailable }
        let overhead = mode == .auto ? hostOverhead : 0
        let (retained, overflow) = overhead.addingReportingOverflow(safetyReserve)
        guard !overflow, retained <= UInt64.max - UInt64(ceiling) * mib else { throw Failure.overflow }
        guard available >= retained else { throw Failure.insufficient }
        let room = (available - retained) / mib
        let guest = mode == .auto ? Int(min(room, UInt64(ceiling)) / 256) * 256 : minimum
        guard guest >= minimum, UInt64(guest) <= room else { throw Failure.insufficient }
        return Plan(guestMib: guest, overhead: overhead, reserve: safetyReserve, sampledBudget: available)
    }
}
