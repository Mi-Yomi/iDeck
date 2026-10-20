# iDeck-BCD: кнопка меню, двойной старт Dock, Unity (20 октября 2026)

Жалоба владельца: в Cuphead и No, I'm not a Human нет круглой кнопки меню,
нельзя поделиться логами и включить экранный геймпад; No, I'm not a Human
(Unity) не запускается.

Разобраны логи владельца (вне репозитория): сборка 573, 19 октября
18:49–19:00 (The Farmer Was Replaced, No, I'm not a Human) и сборка 574,
23:20–23:21 (No, I'm not a Human). Лога Cuphead нет.

**На телефоне стоит апстримная BCD** (`[build] v0.1.574`, встроенный список
рекомендаций v1). Ничего из iDeck-BCD на телефон не попало: нужна сборка на
Mac. **Ничего не собрано и не запущено** (`AGENTS.md`).

## 1. Нет круглой кнопки меню

Причина в коде: кнопка рисовалась только после стартового экрана
(`hud.starting == nil`, `!model.launching`). У Steam-игры (старт через BCD
Dock) стартовый экран держится, пока `DockStartScreen` не увидит окно игры.
Если игра падает до первого кадра или Dock останавливается, экран стоит до
конца сессии, и без контроллера (Back + Start) до меню не добраться. Подсказка
на самом экране при этом говорит «or tap the menu button».

В логах: The Farmer Was Replaced (Unity) провела 2,5 минуты на стартовом
экране до `[dock-status] host-ended result=0 starting=1`; No, I'm not a Human в
23:21 остановилась на ошибке Dock (код 30, см. п. 2).

Исправление: кнопка показывается с момента Play, поверх стартового экрана
(его правый верхний угол пуст) и под открытым меню. Это то же меню, что у
Back + Start: «Share logs», «Touch controls», «Quit game». Флага нет: это
исправление по прямой просьбе владельца. Вернуть как было: одна строка в
`BCDSessionLive.swift` (`refresh()`) и условие в `BCDSession.swift`.

## 2. Код 30 после нескольких нажатий Play

Сборка 574, 23:21: три нажатия Play за 3 с, пока включался JIT. Пошли два
старта Dock (`[madeira-dock] launch option 0` в 07.716 и 07.731). Второй
упал с «Something changed while the launch was getting ready» (07.748), и его
`fail()` вызвал `MadeiraDock.cleanup()`: удалил одноразовую передачу входа
первого старта и снял `MADEIRA_DOCK_AUTH_FILE`, а `dockEnded()` вернул
приложению его соединение со Steam. Хост первого старта в 15.454:
`session-account-input-invalid=1`, `probe-result=30`, на экране «BCD Dock
couldn't set up the Steam session (code 30)».

Исправление: `MadeiraDock.startPending` держится от прохождения проверок
`startDock` до конца его задачи (сессия началась или старт упал). Play в это
время только пишет `[madeira-dock] a start is already getting ready: this
Play is ignored`. Старт, отложенный до включения JIT, не затронут: флаг
ставится после проверки JIT.

## 3. Unity: что показывают логи

- Сборка 573 (18:54, No, I'm not a Human): `increased-memory=0`, карта до
  `0x7180000000` (454 ГБ), арена FEX 4 ГБ у потолка, резервы UnityPlayer по
  511 МБ получают `c0000017` (128 раз и больше), дальше цикл исключений. Это
  случай `arena-adaptive` (LARGE-CHANGES §1): установка была без Increased
  Memory Limit.
- Сборка 574 (23:20): `increased-memory=1`, карта 512 ГБ, арена в полосе 16 ГБ
  (`0x7c00000000`). Нехватки адресов, как в 573, здесь не видно, и
  `arena-adaptive` такую полосу не трогает. Auto-tune: «crashed at stage 2
  after 30 s», то есть модули игры загружены, но не было ни одного кадра.
  Лог этой сессии (`NoImNotAHuman.exe-2026-10-19_23-20-20.txt`) отправлен на
  сервер апстрима, локальной копии нет. Причина неизвестна.
- The Farmer Was Replaced (573): UnityPlayer загружен, два резерва по 511 МБ
  прошли, потом Unity сама запустила `UnityCrashHandler64.exe` (BCD его
  блокирует). Падение до первого кадра, причина в этом логе не видна.

Вывод: правок движка под Unity нет, потому что нет доказательств. Нужен лог
сессии игры, запущенной **одним** нажатием Play: «Файлы» › На iPhone › BCD
› `logs` › `NoImNotAHuman.exe-….txt`. «Share logs» в меню отдаёт только два
лога самого BCD, без лога сессии.

## Изменённые файлы

- `app/Madeira/BCDSession.swift`, `app/Madeira/BCDSessionLive.swift`: кнопка меню.
- `app/Madeira/MadeiraDock.swift`, `app/Madeira/ContentView.swift`: один старт Dock за раз.
- `tests/host/check-bcd-session.py`, `tests/host/check-bcd-launch.py`: новые проверки.

## Не проверено

- Не собрано, тесты проекта не запускались. Своя проверка (скрипт вне
  репозитория): оба изменённых теста разбираются Python; новые проверки и
  старые строковые проверки, касающиеся изменённого кода (check-bcd-session,
  check-bcd-launch, check-steam-library, check-steam-games,
  check-dock-installers, check-onboarding, check-jit-method,
  check-dock-gdi-section), выполняются на исходниках; скобки сбалансированы.
- `check-bcd-session.py` читает `.github/workflows/build-ipa.yml`, которого в
  импорте нет, и падает на старте независимо от этого изменения.
- На устройстве: кнопка на стартовом экране (место, перетаскивание, меню
  поверх экрана) и повторный Play во время старта Dock.
