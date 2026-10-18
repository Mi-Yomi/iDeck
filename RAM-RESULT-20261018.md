Latest verified native game-tool run29, 2026-10-18: official ARM64 Runtime4 container (UID1000/64-bit/aarch64) and GE Wine11.0 Staging versions passed all6 probes. Managed dbus-run-session repeat passed with no new namespace holders; initial autolaunch/cleanup-race failures are preserved. Client4ELFs/package versions unchanged, OOM0, clean original Stop/QEMU0/noRecovery/full offline-copy fsck/source preservation PASS, input mount closed normally. Clean private source29 SHA c450673a940e0cefb1b27dc5a21697c7335e6fa8663e51c356da8d5a5e4dc03e. This is tool execution, NOT Steam/game/GPU/iPhone acceptance. Last accepted UI remains27; interrupted28 never reused. Bin-arm64 preflight/containment4Linux tests passed; GE also has a working legacy bin alias, so no Steam-stall causation claimed. iPhone16ProMax/iOS27 user-reported, hardware untested. No default/iOS route activated. Read [native runtime result](GAME-RUNTIME-RESULT-20261018.md).

Latest verified local run27, 2026-10-18: actual Store-Library-Store-Library navigation, Big Picture Home/game details rendered, 4GiB/native500ms/sandbox, zero OOM. Ordinary application shutdown, clean original VM Stop/QEMU0, full post-fsck/source preservation PASS. Pinned zero V5 + stock CEF watchdog flag; later owned CPU-affinity phase is separate/confounded. One bounded run only; full BP menu/return, Steam games, repeat launch and iPhone unverified. Run26 interrupted/inconclusive, preserved and not reused. Render-only pinned profile + 4 tests and actual CLI hash/overwrite checks PASS. No default/iOS launch profile activated. Read [current UI result](STEAM-UI-RESULT-20261018.md).

# iDeck: проверка с 4 ГиБ RAM, 18 октября 2026

Позднее в прогоне25 устранён рост SHM в одном запуске; рабочая навигация Steam
ещё не получена. Актуальные измерения и ограничения: [исправление общей памяти](SHM-RESULT-20261018.md).
Описанный ниже прогон24 остаётся историческим сравнением RAM.

По новому разрешению пользователя ВМ действительно запущена с 4096 МиБ вместо
2560 МиБ. Режим сохранён как явная опция `--experimental-memory-mib 4096`;
стандартный профиль 1536 МиБ и профили iOS не изменены. 25 тестов управления ВМ
и 18 тестов защиты образа прошли. Прогон24 продолжил копию проверенного диска22;
незавершённая копия23 не использовалась. Диск E: снова читался из WSL.

## Фактический результат

| Измерение | Прогон24 |
| --- | --- |
| Гостевая RAM из `/proc/meminfo` | 4010876 КиБ |
| Ёмкость `/dev/shm` | 2053566464 байт |
| Минимум доступной гостевой RAM | 1872412 КиБ, около 1,79 ГиБ |
| Наблюдение | 80 выборок, 264,631 с |
| Причина завершения | Защита резерва общей памяти |
| Свободная SHM после замораживания | 325754880 байт |
| Убийства OOM / записи OOM в ядре | 0 / 0 |
| Основное окно и навигация Steam | Не подтверждены; на кадрах Linux desktop |

В прогоне 22 с 2560 МиБ та же защита сработала через 205,986 с. Большая RAM вместе
с большей стандартной ёмкостью tmpfs продлили этот запуск примерно на 59 с,
но рабочий интерфейс не появился. Это не независимая проверка RAM при одинаковом
размере SHM. За последние 56,366 с наблюдения использование SHM выросло примерно
на 1,64 ГБ. Причина этого роста пока не установлена. Тайм-аут IPC 500 мс,
отсутствие диагностического LD_PRELOAD, четыре vCPU, CPU max и sandbox сохранены;
фактические окружения и карты процессов проверены.

Отдельный 20,019-секундный гостевой замер не показал вытеснения страниц,
задержек выделения памяти, OOM или swap; больших страничных ошибок стало на 36
больше. Одновременно на Windows наблюдалась подкачка: в двух замерах доступно
668/622 МиБ, вход страниц 0/20095 в секунду. Давление памяти на хосте могло
влиять на тайминги. Этот результат не доказывает достаточный бюджет для телефона
и не устанавливает единственную причину нестабильности Steam.

## iPhone и GetMoreRAM

Пользователь подтвердил iPhone 16 Pro Max и намерение применять
[GetMoreRAM](https://github.com/hugeBlack/GetMoreRam). Он включает Increased
Memory Limit для App ID; требуется переустановка подписанного приложения.
Фактический entitlement и доступная память процесса на этом телефоне пока
не измерены, версия iOS не указана. Бюджет 4 ГиБ на телефоне не включён автоматически:
нужно оставить память самому приложению, дисплею и QEMU/TCG и проверить запуск
на устройстве. Steam-режим, игры через Steam/Proton и хранилище игр iPhone
остаются незавершёнными. Проверка на ПК не подтверждает работу на iPhone.

## Сохранность

Steam потребовал завершения принадлежащих тесту процессов; это нештатное
завершение приложения. Отдельно механизм Stop ВМ завершился штатно: код QEMU 0,
синхронизация/отключение гостевого диска, без recovery-маркера. Проверка пакетов
прошла, четыре ELF клиента не изменились, приватные namespace-процессы завершены.
Финальная проверка отдельной копии прошла все пять этапов без ошибок и сохранила
хеш исходного диска. Временное подключение образа снято штатно, его помощники
завершены. Журналы аккаунта и пиксели экранов сохранены приватно.

Доказательства: [run24/outcome.json](experiments/linux-guest/evidence/steam-local-arm64-20261017/run24/outcome.json).
