import Foundation

/// Conservative process-budget policy, not a claim about physical device RAM.
enum LinuxSteamMemory {
    enum Mode: String, CaseIterable, Hashable { case auto, fixed1536 }
    enum Failure: Error { case unavailable, insufficient, overflow }
    static let mib: UInt64 = 1024 * 1024
    static let minimum = 1536
    static let ceiling = 4096 // Experimental capped ceiling; device acceptance pending.
    static let hostOverheadBytes: UInt64 = 1024 * mib
    static let safetyReserveBytes: UInt64 = 1024 * mib
    static func minimumBudget(_ mode: Mode) -> UInt64 {
        UInt64(minimum) * mib + safetyReserveBytes + (mode == .auto ? hostOverheadBytes : 0)
    }
    static func explanation(available: UInt64?, mode: Mode) -> String {
        let measured = available.map { "\($0 / mib) MiB" } ?? "не измерен"
        let selected = mode == .auto ? "Auto" : "1536 MiB"
        return "Дополнительный бюджет процесса: \(measured). Для \(selected) нужно не менее \(minimumBudget(mode) / mib) MiB с резервом. Это не общий объём RAM телефона."
    }
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
    /// Finish blocking ownership/journal IO before sampling. A refusal closes
    /// this preparation permanently; the caller retains its one-use VM owner.
    static func enterAfterIO(plan: Plan?, preparation: LinuxStartupPreparation,
                             prepare: () throws -> Void, sample: () -> UInt64?) throws -> UInt64? {
        do {
            try prepare()
            let available = plan == nil ? nil : sample()
            try plan?.recheck(available)
            guard preparation.enterNative() else { throw LinuxStartupPreparation.Cancelled.beforeNativeEntry }
            return available
        } catch {
            preparation.finish()
            throw error
        }
    }

    /// available is ADDITIONAL process budget; never subtract current RSS again.
    /// H includes future JIT/TCG commitment and display/QEMU/IO growth. Keeping
    /// the full conservative H avoids inferring resident bytes from prewarmed VA.
    static func plan(available: UInt64?, mode: Mode,
                     hostOverhead: UInt64 = LinuxSteamMemory.hostOverheadBytes,
                     safetyReserve: UInt64 = LinuxSteamMemory.safetyReserveBytes) throws -> Plan {
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
