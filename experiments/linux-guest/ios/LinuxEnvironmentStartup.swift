/// UI intent only; Start still rechecks actual JIT/RAM/ownership and disk safety.
struct LinuxEnvironmentLaunchIntent {
    enum Decision { case wait, resume, consent, jit, start }
    private(set) var pending = false
    mutating func begin() -> Bool {
        guard !pending else { return false }
        pending = true; return true
    }
    mutating func cancel() { pending = false }
    mutating func advance(owner: Bool, foreground: Bool, busy: Bool, network: Bool, jit: Bool) -> Decision {
        guard pending, foreground, !busy else { return .wait }
        if owner { pending = false; return .resume }
        guard network else { return .consent }
        guard jit else { return .jit }
        pending = false; return .start
    }
}

/// Queue-confined orchestration of existing guest verbs, never native ownership.
struct LinuxEnvironmentStartup {
    enum Command: String { case install = "INSTALL", openSteam = "BIG_PICTURE" }
    enum Stage: String {
        case idle, waitingDesktop, installingSteam, openingSteam, waitingConfirmation, desktop, blocked, stopped
        var message: String {
            switch self {
            case .idle: return "Среда готова к запуску."
            case .waitingDesktop: return "Запускаем рабочий стол…"
            case .installingSteam: return "Рабочий стол доступен. Подготавливаем Steam из встроенных пакетов…"
            case .openingSteam: return "Установка подтверждена. Запуск Steam внутри среды запрошен; вход и соглашения — ваши действия."
            case .waitingConfirmation: return "Среда работает. Ожидаем подтверждение Steam; повторная команда не отправлялась."
            case .desktop: return "Рабочий стол работает. Steam вернул управление; окно клиента не подтверждено."
            case .blocked: return "Подготовка Steam не завершена; подробности в расширенных настройках."
            case .stopped: return "Среда останавливается или завершена. Новый запуск требует перезапуска iDeck."
            }
        }
    }
    private(set) var stage = Stage.idle
    private(set) var pending: Command?
    private(set) var installed = false
    static func completes(command: String?, status: String) -> Bool {
        guard let command else { return false }
        if status.hasPrefix("IDECK_STEAM_BLOCKER:") { return true }
        return ["IDECK_STEAM_INSTALLED":"INSTALL", "IDECK_STEAM_CLIENT_RETURNED":"BIG_PICTURE",
                "IDECK_STEAM_DESKTOP_READY":"DESKTOP"][status] == command
    }
    static func acknowledgesLaunch(command: String?, status: String) -> Bool {
        command == "BIG_PICTURE" && status == "IDECK_STEAM_LAUNCH_REQUESTED"
    }
    mutating func begin() { if stage == .idle { stage = .waitingDesktop } }
    mutating func desktopReady() -> Command? {
        guard stage == .waitingDesktop else { return nil }
        stage = .installingSteam; pending = .install; return .install
    }
    mutating func observe(_ status: String) -> Command? {
        guard stage != .idle, stage != .stopped else { return nil }
        if status.hasPrefix("IDECK_STEAM_BLOCKER:") {
            pending = nil; stage = .blocked
        } else if status == "IDECK_STEAM_INSTALLED", pending == .install {
            installed = true; stage = .openingSteam; pending = .openSteam; return .openSteam
        } else if status == "IDECK_STEAM_CLIENT_RETURNED", pending == .openSteam {
            pending = nil; stage = .desktop
        } else if status == "IDECK_STEAM_DESKTOP_READY" {
            pending = nil; stage = .desktop
        }
        return nil
    }
    mutating func timedOut() { if pending != nil { stage = .waitingConfirmation } }
    mutating func retry() -> Command? {
        guard stage == .blocked, pending == nil else { return nil }
        stage = .installingSteam; pending = .install; return .install
    }
    mutating func stop() { pending = nil; stage = .stopped }
}
