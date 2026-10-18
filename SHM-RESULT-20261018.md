Latest verified native game-tool run29, 2026-10-18: official ARM64 Runtime4 container (UID1000/64-bit/aarch64) and GE Wine11.0 Staging versions passed all6 probes. Managed dbus-run-session repeat passed with no new namespace holders; initial autolaunch/cleanup-race failures are preserved. Client4ELFs/package versions unchanged, OOM0, clean original Stop/QEMU0/noRecovery/full offline-copy fsck/source preservation PASS, input mount closed normally. Clean private source29 SHA c450673a940e0cefb1b27dc5a21697c7335e6fa8663e51c356da8d5a5e4dc03e. This is tool execution, NOT Steam/game/GPU/iPhone acceptance. Last accepted UI remains27; interrupted28 never reused. Bin-arm64 preflight/containment4Linux tests passed; GE also has a working legacy bin alias, so no Steam-stall causation claimed. iPhone16ProMax/iOS27 user-reported, hardware untested. No default/iOS route activated. Read [native runtime result](GAME-RUNTIME-RESULT-20261018.md).

Latest verified local run27, 2026-10-18: actual Store-Library-Store-Library navigation, Big Picture Home/game details rendered, 4GiB/native500ms/sandbox, zero OOM. Ordinary application shutdown, clean original VM Stop/QEMU0, full post-fsck/source preservation PASS. Pinned zero V5 + stock CEF watchdog flag; later owned CPU-affinity phase is separate/confounded. One bounded run only; full BP menu/return, Steam games, repeat launch and iPhone unverified. Run26 interrupted/inconclusive, preserved and not reused. Render-only pinned profile + 4 tests and actual CLI hash/overwrite checks PASS. No default/iOS launch profile activated. Read [current UI result](STEAM-UI-RESULT-20261018.md).

# iDeck: исправление роста общей памяти, 18 октября 2026

В одном полном запуске устранён быстрый рост общей памяти Steam. Рабочая
библиотека Steam пока не получена: меню отрисовалось, содержимое осталось чёрным.
Исправление сохраняется как эксперимент; обычный запуск и профиль iPhone его
автоматически не включают.

В браузерной части Steam найдено обнуление двух новых блоков по 25 МиБ.
Эта работа выполнялась до ответа клиенту с таймером 500 мс. Новая библиотека
проверяет точную версию Steam, место вызова, владельца и соответствие отображения
файлу. Она пропускает запись только когда ядро подтверждает, что весь новый файл
уже заполнен нулями. При любой неудачной проверке выполняется обычное обнуление.
Sandbox и исходные исполняемые файлы клиента сохранены.

| Измерение | Прогон 24: 4 ГиБ без исправления | Прогон 25: то же с исправлением |
| --- | --- | --- |
| Таймер IPC | 500 мс | 500 мс |
| Наблюдение | 264,631 с до защиты SHM | 1211,877 с до заданного срока |
| Большие блоки SHM | 63 на позднем замере | Максимум 2 |
| Рост/использование SHM | Рост около 1,64 ГБ за последние 56 с | Максимум 76 935 168 байт всей SHM |
| Физическая память двух больших блоков | Каждый выделялся полностью | Максимум 741 376 байт суммарно |
| Убийства OOM | 0 | 0 |
| Минимум доступной гостевой RAM | 1 872 412 КиБ | 2 763 224 КиБ |
| Интерфейс | Linux desktop | Вход успешен; меню Steam, чёрное содержимое |

Внутри настоящей ARM64 ВМ прошли обе проверки библиотеки. Журнал подтвердил
два вызова оптимизации из нужного места Steam. После основного наблюдения
добавлены 303 с проверки стандартной команды `steam://open/library`: Steam
принял её с кодом 0, но работающая навигация не подтверждена. Содержимое окон
и журналы аккаунта остаются в приватном каталоге на E:; в Git сохранены
измерения и хеши кадров.

Занятые потоки браузера продолжали выполнять код libcef/JavaScript. Проверка
адресов восстановила их обычное выполнение с TracerPid 0 и не читала данные
пользовательской памяти. Все браузерные процессы были ограничены ядрами 2–3
из четырёх доступных. Подготовлен прогон 26 с расширением этого ограничения
до 0–3 и тем же исправлением SHM. Расширение ядер отдельно уже пробовали раньше;
его сочетание с исправлением памяти ещё требует результата.

Stop ВМ завершился штатно, QEMU вернул 0. Сам Steam потребовал завершения
принадлежащих тесту процессов, включая один SIGKILL. Проверка пакетов прошла,
четыре ELF клиента сохранились. Полная проверка отдельной копии диска прошла
пять этапов без ошибок; хеш исходного диска до и после совпал. Временное
подключение образа снято штатно.

[Код и проверки](experiments/linux-guest/diagnostics/shm-zero-init/README.md),
[измерения прогона 25](experiments/linux-guest/evidence/steam-local-arm64-20261017/run25/README.md).
Это один локальный запуск. Стабильный Steam/Big Picture, игры через Steam/Proton,
работа на iPhone 16 Pro Max, его доступная RAM с GetMoreRAM и хранилище игр
на устройстве пока не подтверждены.
