# HANDOFF — продолжение iDeck, 2026-10-15

Ночная передача Dots: [DOTS_OVERNIGHT.md](DOTS_OVERNIGHT.md). В ней указаны
текущий этап, работа четырёх подагентов и порядок сборки/фиксации результата.
Для следующего Codemagic запуска нужен полный текущий pushed HEAD, включая
коммит этой инструкции; SHA последнего исправления кода указан отдельно.

## Последняя Apple-попытка: pixman download reset

[Build `6ad130983ffd2c7f0ad3b5a1`](https://codemagic.io/app/6ad03ce9a8a969b53f3a4aa9/build/6ad130983ffd2c7f0ad3b5a1)
на SHA `ab86fe490027cf35a184f08745b3e4f12b80aa11` завершился **failed**.
Источник сведений в этом разделе — краткая browser-сводка координатора;
полный raw log автору раздела не передан, сводка не выдаётся за полный лог.

- `swift-source-check`: exit 0, 59.852 секунды. Source stage и guest hashes
  приняты; overlay SHA-256
  `b70bc4bfe6ad22b053d5392603ec93fe5176726a851ad5236080cc050e5afeb8`.
- QEMU archive SHA-256
  `7c9605290b34152debb842e965a55d2e4fbba4793e536ab677b4027e5dc0ba1a`
  принят, распаковка прошла с ровно одним ранее разрешённым пропуском symlink.
  Ошибки распаковки и JSON из предыдущей попытки здесь не повторились:
  `result.json` создан.
- Первый новый отказ: `Worker.fetch` при TLS `do_handshake` для
  `https://www.cairographics.org/releases/pixman-0.38.0.tar.gz` —
  `URLError`, внутри `ConnectionResetError`, errno 54. Общее время 126.498 секунды.
  Native library compilation, runtime linking и IPA packaging не достигнуты.

Lock сохраняет pixman 0.38.0: **891 291 байт**, SHA-256
`a7592bef0156d7c27545487a52245669b00cf7e70054505381cff2136d890ca8`.
Отдельная read-only проверка того же URL из облачной среды координатором
получила `Tunnel connection failed: 403 Forbidden`. Это отказ другого proxy,
не объяснение Apple TLS reset. Обход запрета не выполнялся; постоянная
недоступность URL на Apple runner этим не доказана.

В `ci/build_linux_probe_ipa.py` добавлен bounded retry для transient
transport failures и HTTP 408/429/500/502/503/504: не более **3 попыток**, backoff
**2/4 секунды**, общий deadline файла **300 секунд** вместе с попытками,
ожиданием, проверкой и публикацией; он также ограничен остатком worker budget.
Socket timeout — не более 60 секунд. Main-thread `SIGALRM` ограничивает полное
wall-clock время даже при медленном непрерывном ответе; неподдерживаемая среда
или уже активный timer дают отказ, прежний signal handler восстанавливается.
Certificate/SSL, access denial (включая 401/403/407), integrity/size и filesystem
errors, исчерпание бюджета не повторяются. TLS/security checks не отключены.

Каждая попытка пишет собственный exclusive partial. Только полностью проверенный
size/SHA-256 публикуется через no-clobber `os.link`; существующий destination,
включая dangling symlink, не перезаписывается. Собственный partial удаляется и
при ошибке. Диагностика URL/attempt/bytes/duration/error/errno/HTTP status идёт
в stdout и `downloads` в `result.json`; HTTPError response закрывается.
Source URLs, pins, locks, extraction/data_filter, guest checks, native recipe и
workflow не менялись. Старые evidence-снимки сохранены.

Работа ведётся в существующем облачном checkout `/workspace/iDeck`, только в
Linux-ветке, исходный HEAD `00745fb36b444df8d0e4b43842e0d8eb9a65999c`.
**Проверено координатором:** `python3 -B -m unittest discover -s
experiments/linux-guest/tests -v` — **56 host tests PASS**, exit 0, 0.607 секунды,
Python 3.12.14/Linux. Это 20 новых network-free download regressions и 36 прежних
request/source/guest/extraction tests. Проверены transient recovery, предел
попыток/deadlines, fatal SSL/access/integrity/filesystem отказы, partial cleanup,
no-clobber publication и signal timer/handler restoration. Независимый reviewer
не нашёл correctness/security blocker; Swift/Xcode/IPA auditor не установил
дополнительного доказанного blocker до следующего Apple run. Это host-проверки,
не компиляция native implementations или linking с Apple SDK.

Локальный лог: `.work/native-download-retry/host-tests.log`, SHA-256
`b92e977e5a6b7a4cc80de6428290b15bcba75f2143a01ced96a8207292e05a09`; лог не добавлен в Git. Отчёт с hash script/tests/lock:
`experiments/linux-guest/evidence/native-download-retry.json`.

Новая CI из этого checkout не запускалась; ей управляет browser-координатор.
Перед следующим запуском нужны свежие private/free-quota/billing проверки и
точный новый pushed SHA. Лимиты **6900 секунд / 120 минут** сохраняются.
**IPA нет; Linux/JIT на iPhone и Steam не проверены.**

## Распаковка native sources и JSON отчёт — 2026-10-16

По переданному пользователем логу build `6ad129af3ffd2c7f0ad3b35b`, SHA
`3a10400ebf40fc2d1d0578447d6f55b98f2dca66`, Swift gate **прошёл**: worker
продолжил установку build tools/Rust, checkout и подготовку полного Husk.
Следующий отказ — `tarfile.AbsoluteLinkError` на
`qemu-10.0.12-utm/roms/edk2/EmulatorPkg/Unix/Host/X11IncludeHack`. Затем
`finally` скрыл эту причину ошибкой `bytes is not JSON serializable`.
Native library compilation, linker и IPA packaging не запускались.

Исправления в той же Linux-ветке, все новые файлы на E:

- `unpack_source` повторно проверяет исходный size/SHA и пропускает только
  symlink по этому точному пути с target `/opt/X11/include`. Правило явно
  записано в native lock и попадает в отчёт. Другой тип/target, отсутствие
  ожидаемой ссылки или дубликат отклоняются. Остальные файлы проходят прежний
  Python `data_filter`; режим `fully_trusted` не используется.
- Это X11 include для **EDK2 Unix host emulator** (Host.inf, XCODE IA32/X64).
  iOS recipe собирает QEMU dylib, не этот firmware emulator. Пропускается сама
  ссылка, не весь каталог roms/edk2. Содержимое архивов, их URL, size/SHA,
  Git pins и Rust version не изменены.
- `restore_guest` раньше возвращал из `verify()` словарь с байтами трёх файлов;
  теперь возвращает их size/SHA-256. Проверка и сами гостевые bytes не меняются.
  Тот же `write_result` используется в finally и в regression: реальный гостевой
  архив + исключение распаковки теперь дают валидный JSON с исходной ошибкой,
  и исходное исключение продолжает выходить наружу.

**Проверено:** 36 host tests PASS; полный проход `data_filter` по записям всех
семи исходных архивов в Python 3.12.14 обнаружил только указанную абсолютную
ссылку. Negative tests сохраняют отказы для других absolute/outside links,
path traversal, неверных hash и изменённых omission rules. Доказательства и
результат полной распаковки — `experiments/linux-guest/evidence/native-input-fix.json`.
Все 7 реальных архивов полностью распакованы новым helper на Windows/Python
3.12.14 за 359.61 секунды вместе с guest/report check; пропущена ровно одна
указанная ссылка. `native-input-unpack.json` — фактический отчёт этого запуска.
Более медленный дублирующий WSL/Python 3.14 запуск остановлен SIGINT после
463.712 секунды; его частичный каталог сохранён в `.work`, за PASS он не принят.

Новая Apple-сборка из этой сессии не запускалась. Следующий запуск — тот же
`ideck-linux-probe-ipa`, эта же ветка и новый полный pushed SHA; прежний 3a10400
повторять не нужно. Требования текущей бесплатной квоты ≥120 macOS минут,
отключённой оплаты и private repository остаются. Старые evidence JSON ниже
сохраняются как снимки прошлых ревизий, их pending-состояния не переписываются.

## Исправление неполного Swift source archive — 2026-10-16

Пользователь передал полный вывод build `6ad126603ffd2c7f0ad3b258`:
`ideck-linux-probe-ipa`, правильная ветка и SHA
`e9dfb4b3dcfc68b58da5b6ea389b502e4a17a927`. Guard принял запрос. Xcode 27.0
(27A266a), iOS SDK 27.0: profile/evidence typecheck, native syntax и Mac validator
tests прошли; `husk-upstream-typecheck` упал при создании PCH из-за отсутствующего
`husk-console-abi.h`. Native libraries, linker и упаковка IPA не запускались.
Источник этих Apple-результатов — переданный пользователем лог, сохранённый в
`experiments/linux-guest/evidence/codemagic-ipa-e9dfb4b-user-log.txt`.

Причина — неполный подготовленный нами offline source slice: включили
`husk-console-host.h`, но пропустили его локальный include `husk-console-abi.h`.
В архив добавлен **оригинальный** файл из того же Husk commit
`0695248f491cda877f7969d1f0cc89aeede1482e` (blob
`18221e15875818efc166d37513fadea61dc37e57`); прежние 77 файлов byte-identical.
Теперь в архиве 78 файлов. Обновлены archive/overlay locks. Restore проверяет
цепочку всех literal quoted includes из HuskBridge.h до записи файлов на диск.
Это проверка комплектности; Apple compiler gate сохранён полностью.

Проверки исправления: **31 host tests PASS**; новый regression воспроизводит
неполный пакет с корректными хешами и проверяет отказ. Реальный Windows Clang
20.1.3 на старом source slice повторил `husk-console-abi.h file not found`
(exit 1), на исправленном slice с overlay прошёл `-fsyntax-only -x c -Wall
-Wextra -Werror` (exit 0). Системный компилятор использован без установки;
все новые файлы и временные каталоги на E. Распаковка source slice и применение
overlay проверены.
Протокол и хеши — `experiments/linux-guest/evidence/source-header-fix.json`.
Старый `ipa-build-preparation.json` остаётся историческим отчётом предыдущего SHA.

Повтор Apple-сборки здесь **не запускался**. Новый полный SHA после push нужно
указать в том же `ideck-linux-probe-ipa`, на той же Linux-ветке. Не повторять
старый e9dfb4b. Остальные inputs и требование свежей проверки 120 бесплатных
macOS минут/отключённой оплаты не изменены. IPA пока нет; Apple Swift success,
native link, device execution и Steam не заявлены.

Ниже сохранены предыдущие этапы; их «NOT RUN» и 77 файлов относятся к состоянию
до этого запуска и исправления.

## Исправление Codemagic и отдельный IPA workflow — 2026-10-16

Работа остаётся на `codex/linux-guest-feasibility-20261015` в `E:\Freddy Fazbear\iDeck`.
Точный новый commit: `git rev-parse HEAD` после фиксации этой части. Старый
`aea73cfe2ca4b5661a56863ab6dea2908071ed2e` больше не является вершиной после push.

По переданному пользователем результату, build `6ad11d5f3ffd2c7f0ad3af4f` выбрал
**main / a77ab500cdf8c8307af36a58b25816a3fa4d66db**, а не запрошенную Linux-ветку.
Пустой `EXPECTED_SOURCE_COMMIT` старого workflow был отклонён схемой до запуска
компилятора. Это не Swift/linker failure. Raw log этой сборки здесь не получен.

Исправлено в Linux-ветке:

- Все обязательные hash/commit inputs получили непустой sentinel `REQUIRED`.
  Его нельзя принять за разрешённый SHA: новый первый шаг проверяет формат и
  отказывает с понятным сообщением. Defaults подтверждений остаются `false`.
- Linux workflows дополнительно требуют правильные CM_BRANCH, CM_REPO_SLUG,
  CM_COMMIT, точный EXPECTED_COMMIT и clean checkout. Отчёт guard сохраняется.
- Первые 15 workflow сохраняют исходные execution bodies после нового guard.
  Linux source check поднят первым в списке. **main не изменён**; сначала выбрать
  Linux-ветку, затем workflow, иначе CI снова прочитает старый YAML.
- Добавлен шестнадцатый workflow **ideck-linux-probe-ipa**: реальные native builds,
  XcodeGen, xcodebuild, проверка bundle и ad-hoc IPA. Подробности в
  `experiments/linux-guest/ipa/README.md`.
- Отдельный project spec сохраняет реальные app/native sources, QEMU, ANGLE,
  pairing/StikJIT, но исключает embedded MoltenVK/PS4 и Android resource staging.
  Probe-only entry открывает Linux; отдельный bundle ID `dev.ideck.linuxprobe`.
- Проверенные Linux kernel/initramfs/profile теперь действительно включены в Git
  как архив 19 623 827 байт, SHA256
  `f973fe00e1cf54772589c3e54c8bc22a7396604ec927004267f9a4aea9d39efb`.
- Семь официальных native source archives реально скачаны и прочитаны локально;
  размеры/SHA закреплены. Git dependencies и Rust 1.99.1 закреплены. Новый WebKit
  ANGLE pin ещё не проверен Apple-компилятором. Homebrew tool versions фиксируются
  в отчёте каждого запуска; они не объявлены детерминированными.
- Отдельный format-patch исправляет игнорирование ошибок patch/отсутствующего
  dylib в upstream native recipe. Verifiers не ослаблены.

**Проверено здесь:** 30 host tests PASS; nonempty substitutions и сохранение старых
execution bodies в YAML; AST/JSON; полный source+guest stage в
`.work/husk-linux-ipa-staged`; применение native patch; `bash -n` canonical Git
версии shell recipe. Исходный Windows checkout имеет CRLF, поэтому его первый
прямой bash -n отказал на переводах строк; LF-версия из Git прошла. CI checkout
использует core.autocrlf=false. Индекс прежнего source export остаётся
`a305e267ebdb87ec4d202f4f8d5c499cc5ffbe44`; Husk base clean; main не менялся.

**Не выполнено:** server-side YAML validation новой версии, Apple Swift/native
компиляция, линковка, создание IPA, подпись владельцем, device run, Steam. Код
workflow — подготовленный путь сборки, не доказательство её успешности. Новая
сборка из этой сессии не запускалась: browser tool остаётся недоступен; текущая
квота не проверена. Dots, по сообщению пользователя, выполняет отдельную Swift
проверку предыдущего SHA; её итог пока не передан.

Для следующего запуска IPA: выбрать эту ветку и workflow `ideck-linux-probe-ipa`,
новый полный SHA в `expected_commit`, свежие private/free-quota attestations и
`native_build_approved=true`. Нужно **минимум 120 бесплатных macOS минут**, paid
disabled; worker aggregate 6900 секунд, provider cap 120 минут. Это лимит, не ETA.
Настройка Meson/Ninja/pkg-config/XcodeGen/rustup выполняется только на временном
runner. Локальная Windows-система, сертификаты/ключи и телефон не изменяются.
Сам workflow сначала выполняет Swift gate; отдельный повтор source check перед
ним не обязателен. При успехе артефакт `iDeck-Linux-Probe.ipa`, SHA в result.json;
IPA требует обычной подписи владельца для sideload. Нативные outputs сохраняются
в `native-products.tar.gz`, даже если следующая сборка приложения упадёт.

Локальные проверки:

```powershell
$env:TEMP = 'E:\Freddy Fazbear\work\temp'
$env:TMP = $env:TEMP
$env:PYTHONDONTWRITEBYTECODE = '1'
& 'C:\Users\Sevex\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest discover -s experiments/linux-guest/tests -v
git diff --check
git -C .work/source write-tree
```

Ниже сохранены предыдущие состояния; старые формулировки об отсутствии guest
в Git/IPA workflow и старые SHA относятся к прошлым этапам.

## Запрос компиляции: подготовка запуска

Пользователь попросил «скомпиль давай чекать». Ветка для существующего Codemagic:
`codex/linux-guest-feasibility-20261015`, workflow `ideck-linux-guest-profile-check`.
GitHub API подтвердил `Mi-Yomi/iDeck` как private. В workflow добавлено сохранение
`result.json` и отдельных compiler logs; остальные workflow не менялись.

Автоматический доступ к Codemagic сейчас заблокирован неисправностью локального
инструмента: и browser REPL, и Computer Use возвращают `failed to write kernel
assets: Системе не удается найти указанный путь. (os error 3)` до выполнения кода.
Повторная инициализация browser REPL не помогла. Это не ошибка компиляции.
Текущую бесплатную квоту и отключённую оплату проверить не удалось; старое число
66/500 не использовано как актуальное. Запуск Apple worker не подтверждён.

Ручной запуск в существующем приложении
`https://codemagic.io/app/6ad03ce9a8a969b53f3a4aa9`:

1. Проверить, что осталось не менее 10 бесплатных macOS минут и платная подписка
   отключена; выбрать private `Mi-Yomi/iDeck`.
2. Start new build → ветка выше → `ideck-linux-guest-profile-check`.
3. `expected_commit`: полный SHA HEAD этой опубликованной ветки (`git rev-parse
   HEAD`); `free_quota_verified=true`, `private_source_verified=true` только после
   соответствующей проверки. Gate отклонит другой или грязный checkout.
4. Сохранить URL сборки и результат. Успешный status должен быть
   `apple_husk_source_typecheck_and_host_checks_pass`; оба
   `upstream_husk_typechecked` и `integrated_husk_typechecked` должны быть true.

Эта задача проверяет весь настоящий Swift app source с pinned bridge и iOS SDK,
а также компилирует и запускает Mac validator tests. Она ещё не линкует native
QEMU/ANGLE/rppairing и не создаёт IPA. Ошибки baseline и overlay необходимо
разбирать отдельно, не заменяя runtime API заглушками и не ослабляя gates.

## Новое состояние после просьбы продолжить

Работа продолжена в `E:\Freddy Fazbear\iDeck`, ветка `codex/linux-guest-feasibility-20261015`.
Коммит реализации: `5baf235d52b2a5ec64587519e3ad2ec4c0fbd592`. Этот HANDOFF — следующий отдельный коммит; его точный ID: `git log -1 --format=%H -- HANDOFF.md`.
Локальный `main` остался на `a77ab500cdf8c8307af36a58b25816a3fa4d66db`.

Теперь подготовлена **интеграция настоящего Linux-пробника в исходники iOS-приложения Husk**, а не только генератор аргументов QEMU:

- Выбор Linux / прежняя библиотека Husk до создания Android-экрана. Выбор один на процесс; общая JIT-область не переиспользуется другой средой.
- Реальный вызов `qemu_init` / `qemu_main_loop` в отдельном потоке с сохранённым argv; существующие JIT/prewarm и `husk_display_init` / `HuskDisplay`.
- Отдельный каталог сессии, проверка размеров/SHA-256 файлов до старта, IO вне main thread. Android snapshots, GL probe, диски и watchers не вызываются этим маршрутом.
- Два framebuffer проверяются по каждому RGB-каналу каждого пикселя; реальные записи Linux evdev проверяются на нажатие/отпускание A и указателя, обе оси. UI предлагает тап по изображению, Send A и сохранение отчёта.
- Отчёт содержит OS, SHA-256 исполняемого файла приложения, параметры гостя, хеши кадров/serial и отдельные статусы. Physical screen / Steam / accelerated guest GPU не объявляются проверенными.
- Выделение JIT в Husk может быть 512 MiB при запросе TCG 256 MiB; это явно записывается. Безопасного in-process restart/teardown display в pinned bridge нет: после сессии закрыть и открыть приложение. Deadline прекращает сбор доказательств, не убивает общий процесс.

**На Windows Swift и iOS runtime не компилировались и на телефоне не запускались. IPA и Steam Big Picture на iPhone по-прежнему нет.** Интеграция пока является исходниками с подготовленной проверкой Apple SDK.

## Что действительно проверено в продолжении

1. Получен полный clean checkout `Leviidev/Husk` на `0695248f491cda877f7969d1f0cc89aeede1482e`. Исходный checkout `.work/husk-base` не изменён. Патч оформлен через `git format-patch` из отдельного authoring worktree.
2. Итоговая сборочная копия исходников и гостя: `.work/husk-linux-staged-final`. Все изменённые файлы совпали с `husk/overlay.lock.json`. Первая `.work/husk-linux-staged` была sparse-промежуточной и не является полной сборочной копией; сохранена. Теперь stage tool отказывает sparse checkout.
3. В offline source-check архиве **77 настоящих upstream Swift/header/license файлов**, каждый с SHA-256 и original Git blob ID. Архив не содержит native runtime binaries. License/headers сохранены, лицензии проекта не заменялись; старый Playport/Madeira target с QEMU не объединялся.
4. **20 host guard/staging tests PASS**. Host Clang проверил исходный C bridge. AST всех Python-скриптов и YAML проверены; среди CI workflow изменён только ранее добавленный Linux compiler check.
5. Сработал тот же resource stage, который добавлен в Xcode project. Из его выходного каталога `.work/ios-probe-bundle/iDeckLinuxProbe` **повторно реально загружен Linux в Windows QEMU**: оба кадра по 480 000 пикселей и guest keyboard/pointer PASS, 25.125 секунды. Raw run: `.work/linux-boot/run-ios-bundle`.
6. Индекс прежнего восстановленного source export остался **`a305e267ebdb87ec4d202f4f8d5c499cc5ffbe44`**. Ни staged diff прежней работы, ни main не сбрасывались. Push / CI dispatch / signing / device install не было.

Evidence: `experiments/linux-guest/evidence/ios-integration.json`, `host-smoke-ios-bundle.json`, `ios-staging-tests.txt`; общий индекс hashes обновлён. Git-staged bytes проверены против locks. Архив помечен binary; формат-patch сохраняет обязательные пробелы пустых context lines, а применённый source diff отдельно проходит whitespace check.

## Точные команды этой части

PowerShell из корня репозитория; повторный stage требует нового output-каталога.

```powershell
$taskPy = 'C:\Users\Sevex\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:TEMP = 'E:\Freddy Fazbear\work\temp'
$env:TMP = $env:TEMP

& $taskPy -m unittest discover -s experiments/linux-guest/tests -v
& $taskPy experiments/linux-guest/tools/stage_husk.py --upstream .work/husk-base --guest .work/linux-boot/probe-final --out .work/husk-linux-staged-final
& $taskPy .work/husk-linux-staged/scripts/ideck-stage-linux-guest.py .work/husk-linux-staged/guests/ideck-linux .work/ios-probe-bundle/iDeckLinuxProbe
& $taskPy experiments/linux-guest/tools/host_smoke.py --qemu .work/linux-boot/qemu/qemu-system-aarch64.exe --guest .work/ios-probe-bundle/iDeckLinuxProbe --out .work/linux-boot/run-ios-bundle
& 'C:\Program Files\Windhawk\Compiler\bin\clang-20.exe' -fsyntax-only -x c -Wall -Wextra -Werror .work/husk-base/src/app/Husk/HuskBridge.h

git -C .work/source write-tree
git -C .work/husk-base status --short
git diff --cached --check
git -C .work/husk-linux-staged-final diff --cached --check
```

Resource stage в host run использовал первый staged каталог до удаления неиспользуемого Python import; алгоритм и все три полученных файла идентичны итоговому stage. Final source stage уже включает полный checkout, финальный session source и окончательный overlay lock.

## Apple задача и оставшиеся ограничения

Существующий manual `ideck-linux-guest-profile-check` расширен: **480 секунд aggregate, provider cap 10 минут**. Точные clean commit / текущая бесплатная квота / private repository остаются входными gates. Ни текущая доступность Xcode 27 runner, ни квота в этой части не проверялись; задача не отправлялась.

Теперь worker проверяет profile/evidence для iOS, запускает Mac validator tests на реальном ранее записанном serial и negative fixtures, восстанавливает offline source slice и typecheck'ит **исходный и затем patched Husk Swift application против настоящего Apple SDK и HuskBridge.h**. JIT/QEMU API-заглушек нет. Это typecheck Swift/C declarations; не компиляция native implementation bodies, не линковка и не IPA.

Следующая независимая граница — выполнить эту Apple проверку на существующем разрешённом runner, затем собрать pinned Husk с его настоящими native dependency outputs и patched `project.yml`. Для device run: Linux → Enable JIT → Start Linux → увидеть первый кадр → тап и Send A в течение 20 секунд → второй кадр → сохранить отчёт и запись экрана. Снимки Android и сохранения не сбрасывать.

Параллельно будущему этапу остаётся собрать отдельный **glibc ARM64 rootfs + полный официальный Steam с common resources**, затем настоящий client/CEF и Big Picture. Здесь это не делалось. Требования GPU/игр и сведения о старом WIP остаются в предыдущем отчёте ниже.

## Новые hashes

- Offline Husk source-check archive: `044316e0de837a47c5dd1b765b5f15a939a07030ae8415fdd6add8f6bceb823f` (340 363 bytes).
- Overlay lock: `2dc41640bd14d8711259c6b8019349a7f013f5f494485487354cc799c1d6cbd4`.
- Kernel: `47970e0ee0478fe5c60824a89f162d5a353fa29466e5d3bddb0f9c506f1ed756`.
- Initramfs: `5f64312eeef340991c6b0d97bd9d1fb01649c1763e14d7fb8231ad16551e9343`.
- Final session source: `41012830eda0d37ab75e078f76a57300d554afcfdd9f37b6b490d8286e3231e9`.

## Изменённые файлы реализации

```text
.gitattributes
BUILD_PROGRESS.md
README.md
ci/check_linux_guest_profile.py
codemagic.yaml
experiments/linux-guest/README.md
experiments/linux-guest/evidence/artifact-hashes.json
experiments/linux-guest/evidence/host-smoke-ios-bundle.json
experiments/linux-guest/evidence/ios-integration.json
experiments/linux-guest/evidence/ios-staging-tests.txt
experiments/linux-guest/husk/README.md
experiments/linux-guest/husk/husk119-source-check.tar.gz
experiments/linux-guest/husk/overlay.lock.json
experiments/linux-guest/husk/patches/0001-isolated-linux-probe-route.patch
experiments/linux-guest/husk/patches/series
experiments/linux-guest/husk/source-check.lock.json
experiments/linux-guest/ios/LinuxGuestProfile.swift
experiments/linux-guest/ios/LinuxProbeEvidence.swift
experiments/linux-guest/ios/LinuxProbeSession.swift
experiments/linux-guest/ios/LinuxProbeView.swift
experiments/linux-guest/ios/tests/main.swift
experiments/linux-guest/tests/test_staging.py
experiments/linux-guest/tools/stage_bundle.py
experiments/linux-guest/tools/stage_husk.py
experiments/linux-guest/tools/typecheck_source.py
```

---

Ниже сохранён отчёт **предыдущего этапа**. Его формулировки «ещё не интегрировано», бюджет 240 секунд и отсутствие copied Husk source относятся к состоянию до продолжения; актуальные изменения перечислены выше.

# HANDOFF — iDeck, 2026-10-15

## Результат этой сессии

Приоритет пользователя сохранён: настоящий Linux со своим ядром и Linux Steam / Big Picture на iPhone 16 Pro Max, iOS 27. Сделан ограниченный проверяемый шаг: получены официальные ARM64 ELF Steam и реально запущен прямой Linux-гость с проверкой изображения и ввода на Windows-хосте. **Steam на iPhone, Big Picture, iOS JIT/Metal и игры здесь не запускались; IPA нет.**

Все новые рабочие данные находятся на E. Корень: `E:\Freddy Fazbear\iDeck`.

## Git и сохранённая работа

- Ветка: `codex/linux-guest-feasibility-20261015`.
- Исходный transport HEAD / неизменённый локальный main: `a77ab500cdf8c8307af36a58b25816a3fa4d66db`.
- Коммит реализации и evidence: `36d2463190b1fbac503960a30e0f6bf5dccb7e79`.
- Этот HANDOFF сохраняется отдельным следующим локальным коммитом. Его точный ID: `git log -1 --format=%H -- HANDOFF.md`.
- Push, PR, изменение GitHub/main, dispatch CI, подпись или установка на телефон не выполнялись.
- Начальный `git status --short --branch`: чистый `main...origin/main`. Ветка создана до редактирования.
- Репозиторий приватный и является transport-снимком для CI, а не полной историей разработки.
- Снимок восстановлен в `.work/source`: Playport HEAD `412de5f8c0bdd26d84e0127eb5776ba992e3b152` + исходный staged patch. Все **2 023** записи и точное index tree `a305e267ebdb87ec4d202f4f8d5c499cc5ffbe44` проверены штатными hash/tree gates. Original source checkpoint: `1b07a996efe8cec2e12e3d3c1e19805c198fcccf`. Этот staged diff — сохранённая прежняя работа; не сбрасывать.
- Прочитан восстановленный `AGENTS.md` и его локальные изменения к upstream. У transport-репозитория собственного AGENTS.md нет. Реализация добавлена отдельно, старый снимок и dependency pins не обновлялись.
- Первый полный clone был прерван из-за зависшего получения pack; его незавершённый каталог сохранён в `E:\Freddy Fazbear\work\ideck-incomplete-clone-20261015`. Успешный clone использовал `--depth 1 --single-branch` и HTTP/1.1.
- Штатный reconstruction fetch превысил 180 секунд, но FETCH_HEAD был получен. Локальная копия `.work/reconstruct_source_resumed.py` возобновила checkout/apply, сохранив проверку commit/tree/inventory/всех SHA. Исходный `ci/reconstruct_source.py` не менялся.

## Что доступно

1. Transport CI scripts, manifests, pairing source ZIP и архивы прежних native/Wine prerequisites — сохранены.
2. Полный восстановленный экспорт Playport-derived iDeck, включая документацию и исходники приложения — проверен, не пересобран.
3. Дополнения пользователя скопированы в `E:\Freddy Fazbear\inputs\ideck-20261015`: архитектурное решение и диагностический WIP. Архив содержит 16 base / 18 patched текстовых файлов, не полный DroidDeck runtime.
4. WIP: все заявленные hashes проверены; `git apply --check` + применение дают **побайтно тот же patched/**. На Windows необходим `-c core.autocrlf=false`. APK не собирался, runtime/асинхронное поведение не принято. В WIP название blocked-status отличается от `BLOCKED_PROCESS_ISOLATION_UNAVAILABLE` из последнего запроса — это ещё не интегрированный финальный фикс.
5. Официальные Steam ZIP и три выделенных ELF лежат только в `.work/steam-abi`, в Git не добавлены.
6. Linux/QEMU, generated guest assets, raw logs и все неудачные контролируемые прогоны сохранены в `.work/linux-boot`.

В полученном transport и точном source export не найдены полный ранее скомпилированный DroidDeck export, исходный Diagnostic APK/native payloads, архив 200 SHM mock-тестов, содержимое rootfs r9 и полный Android RescueParty log. Их прежние результаты не объявлялись повторно проверенными. Список с hashes: `experiments/linux-guest/evidence/source-inventory.json`.

## Основные новые доказательства

**Steam ABI.** Официальный URL из pinned DroidDeck installer:
`https://client-update.fastly.steamstatic.com/steam_client_steamdeck_publicbeta_linuxarm64`.
Manifest version `1791918634`; SHA-256 `65079d08bbcc0e7fdc3d9b153aadc4c9befc62913c3e4ee0b02425690366f15f`.
Шесть `_linuxarm64_linuxarm64` ZIP проверены по size/SHA-256. Все 87 ELF — AArch64.

| ELF | SHA-256 |
|---|---|
| `steamrtarm64/steam` | `090846de94be2fcd2ffe5475af412687a720f34dda6b96d1daffe2c587316456` |
| `steamrtarm64/steamwebhelper` | `48ceef78c6f9310369fb4baa95d7076b67e6a2fbb5a00dc71f23f076d0d3df01` |
| `steamrtarm64/libcef.so` | `891d85f97231fcafa5763b7140039c5d3cbbb99f2a42ede08de5991abcbc3cdb` |

GNU readelf независимо подтвердил architecture/interpreter/DT_NEEDED. Client и helper требуют `/lib/ld-linux-aarch64.so.1`; максимальные наблюдавшиеся GLIBC version requirements этих трёх файлов: 2.29 / 2.29 / 2.25 соответственно. Самого loader в проверенных ZIP нет. Это не dependency-closure proof и не минимальная glibc-версия всей будущей установки. Для этих клиентских ELF x86-translator не нужен; архитектуру игр/Proton проверять отдельно.

**Реальный Linux host test.** Alpine 3.24.1, kernel `6.18.35-0-virt`, ARM64 Linux, QEMU `virt`, `cortex-a72`, 4 vCPU, 1024 MiB RAM, TCG cache 256 MiB, software virtio-gpu 800×600, virtio keyboard/tablet. Скомпилированный из `guest/fb_probe.c` статический AArch64 ELF выполняет реальные Linux syscalls, framebuffer ioctls и mmap. Это не mock.

Финальный run: `.work/linux-boot/run-final`. Status `host_boot_framebuffer_input_pass`; QEMU exit 0. Два кадра: каждый из **480 000 пикселей** совпал. Guest evdev: KEY_A down/up, ABS_X=8192, ABS_Y=24575, BTN_LEFT down/up. Время хостового прогона 25.953 секунд; это не iPhone benchmark. Raw command line, logs, decoded events и exact hashes сохранены. Коммитный serial log имеет LF и обрезанные конечные пробелы; hash исходного неизменённого raw log указан отдельно.

Первый writer через `dd` не дал надёжного полного scanout: сначала cursor overlay, после отключения курсора — black frame. Проверка осталась строгой. Финальный probe использует mmap + msync + pan/unblank ioctls. В netboot initramfs также не хватало evdev; модуль взят из modloop того же SHA-verified архива и версии ядра.

**Предел host proof:** Windows QEMU 11.1.0 (`v11.1.0-12130-ge470268ff4`) отличается от Husk119 QEMU 10.0.12-utm. iOS split-WX/JIT, Metal, подпись, jetsam, touch-маршрут на телефоне и Steam UI им не проверяются. Alpine/musl — только boot probe; для Steam нужен отдельный glibc rootfs.

## Точные рабочие команды

PowerShell, из указанного каталога. Это запись уже выполненных команд; повторный host run требует нового output-каталога.

```powershell
Set-Location -LiteralPath 'E:\Freddy Fazbear\iDeck'
$taskPy = 'C:\Users\Sevex\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$taskClang = 'C:\Program Files\Windhawk\Compiler\bin\clang-20.exe'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:TEMP = 'E:\Freddy Fazbear\work\temp'
$env:TMP = $env:TEMP

git status --short --branch
git -C .work/source write-tree
& $taskPy experiments/linux-guest/tools/steam_abi.py --work .work/steam-abi

& $taskClang --target=aarch64-linux-gnu -fuse-ld=lld -nostdlib -static -ffreestanding -fno-builtin -fno-stack-protector -O2 -Wall -Wextra -Werror '-Wl,-e,_start' experiments/linux-guest/guest/fb_probe.c -o .work/linux-boot/fb-probe-final

& $taskPy experiments/linux-guest/tools/prepare_guest.py --archive .work/linux-boot/alpine-netboot-3.24.1-aarch64.tar.gz --out .work/linux-boot/probe-final --sevenzip 'C:\Windows\System32\7z.exe' --frame-probe .work/linux-boot/fb-probe-final

& $taskPy experiments/linux-guest/tools/host_smoke.py --qemu .work/linux-boot/qemu/qemu-system-aarch64.exe --guest .work/linux-boot/probe-final --out .work/linux-boot/run-final

& $taskPy experiments/linux-guest/tools/verify_wip.py --archive '../inputs/ideck-20261015/droiddeck-tl-source-fix-WIP-20261015.tar.gz' --out .work/wip-check-lf
& $taskPy -m unittest discover -s experiments/linux-guest/tests -v
git diff --cached --check
```

Compiler: LLVM clang 20.1.3, source revision `923a5c4f83d2b3675bb88e9fe441daeaa4d69488`, installed executable reused read-only. No compiler installation was performed. Guest output is static AArch64 ELF, no PT_INTERP or DT_NEEDED. QEMU was downloaded from the provider linked by qemu.org and unpacked with:

```powershell
7z x .work/linux-boot/qemu-w64-setup-20260811.exe '-o.work/linux-boot/qemu' 'qemu-system-aarch64.exe' '*.dll' 'share/*' 'COPYING*' 'LICENSE*' -r -y
```

The provider SHA-512 and the Alpine provider SHA-256 were checked before using them. Download/research helper sources remain at `E:\Freddy Fazbear\work\ideck-research\fetch_boot_inputs.py`, `collect.py`, `make_evidence.py`. Exact URLs/sizes/checksums are committed in `evidence/boot-inputs.json`. No system-wide installer ran.

Independent ABI command (each of `steam`, `steamwebhelper`, `libcef.so`):

```powershell
wsl -d archlinux --exec readelf -h -l -d '/mnt/e/Freddy Fazbear/iDeck/.work/steam-abi/key-elf/steamrtarm64/steam'
wsl -d archlinux --exec readelf --version-info '/mnt/e/Freddy Fazbear/iDeck/.work/steam-abi/key-elf/steamrtarm64/steam'
```

## Изменённые файлы

Implementation commit:

```text
.gitattributes
BUILD_PROGRESS.md
README.md
ci/check_linux_guest_profile.py
codemagic.yaml
experiments/linux-guest/README.md
experiments/linux-guest/RESEARCH.md
experiments/linux-guest/evidence/artifact-hashes.json
experiments/linux-guest/evidence/boot-inputs.json
experiments/linux-guest/evidence/diagnostic-wip-check.json
experiments/linux-guest/evidence/frame-0.png
experiments/linux-guest/evidence/frame-1.png
experiments/linux-guest/evidence/guest-profile.json
experiments/linux-guest/evidence/guest-serial.log
experiments/linux-guest/evidence/host-guard-tests.txt
experiments/linux-guest/evidence/host-smoke.json
experiments/linux-guest/evidence/readelf-key-objects.txt
experiments/linux-guest/evidence/repositories.lock.json
experiments/linux-guest/evidence/source-inventory.json
experiments/linux-guest/evidence/steam-abi.json
experiments/linux-guest/guest/fb_probe.c
experiments/linux-guest/guest/ideck-init
experiments/linux-guest/ios/LinuxGuestProfile.swift
experiments/linux-guest/ios/tests/main.swift
experiments/linux-guest/tests/test_guards.py
experiments/linux-guest/tools/host_smoke.py
experiments/linux-guest/tools/prepare_guest.py
experiments/linux-guest/tools/steam_abi.py
experiments/linux-guest/tools/verify_wip.py
```

Данный HANDOFF — отдельное добавление. Все ранее существовавшие Codemagic workflow objects проверены YAML-parser'ом: они не изменились; добавлен один manual-only workflow. `.gitattributes` закрепляет LF только для новых experiment/check файлов, чтобы Windows не ломал hash identity. Новые секреты/ключи не создавались; targeted secret scan совпадений не нашёл.

## Что прошло / что не запускалось

- PASS: exact reconstruction tree/inventory; WIP hashes и patch equivalence.
- PASS: официальные package hashes; 87 ELF ABI; независимый GNU readelf ключевых объектов.
- PASS: реальная cross-компиляция guest ELF, actual ARM64 kernel/guest execution, точные framebuffer кадры, decoded evdev input, штатный QMP quit.
- PASS: 9 host guard tests, Python syntax, YAML structure/неизменность старых workflows, git whitespace check, hashes committed evidence.
- NOT RUN: сборка/typecheck `LinuxGuestProfile.swift` с Apple SDK; prepared CI workflow.
- NOT RUN: iOS QEMU linking, IPA, signing/install/device run, Android/WIP APK build, Linux Steam/CEF runtime, Big Picture, пользовательский вход, игры, ускоренный guest GPU.

## Артефакты и SHA-256

| Артефакт | SHA-256 |
|---|---|
| Alpine netboot archive (431008592 bytes) | `54fe38fa41cce740ba379458ed63cfcd89ab06ae5e6a47a06dafe0a34e8427e8` |
| QEMU installer archive (206615928 bytes) | `f98a8aeb5f7faea9765b6dee28316c266cd179d80354a2fed8e50176f9a2e59f` |
| QEMU executable | `952f897511177803722efed6fefe79bc3e7e5a51a026112dfc40f9a37fb0dad2` |
| Guest kernel | `47970e0ee0478fe5c60824a89f162d5a353fa29466e5d3bddb0f9c506f1ed756` |
| Generated initramfs | `5f64312eeef340991c6b0d97bd9d1fb01649c1763e14d7fb8231ad16551e9343` |
| Compiled guest framebuffer probe | `62e9ab98f0730d00e052e2b9b0741070975ccc79229ce8ebe456303b9fee4d3d` |
| Supplied WIP archive | `c94c298326184137a4571ae883b02e7315a5aa4c94b7bab63e286729752fbe52` |

Все committed evidence files: `experiments/linux-guest/evidence/artifact-hashes.json`. Steam binaries остаются локально, не распространяются. Linux/QEMU notices и оригинальные архивы сохранены рядом с рабочими файлами.

## Блокеры и следующий конкретный шаг

1. **Apple compile gate.** Подготовлен `ideck-linux-guest-profile-check` в существующем `codemagic.yaml`, runner M2/Xcode 27.0, aggregate 240 секунд, provider cap 10 минут. Он typecheck'ит реальный Swift profile для arm64 iOS и запускает небольшие synthetic Mac tests. Он не собирает/линкует VM и не создаёт IPA. Входы: exact `expected_commit`, актуальные `free_quota_verified=true` и `private_source_verified=true`. До внешнего push/dispatch нужно актуальное подтверждение квоты/отключённой оплаты; старые 66/500 минут — историческая запись. Здесь задача была локальная, поэтому ничего не отправлено.
2. **iPhone probe integration.** В отдельной Linux session на pinned Husk119 подключить prepared profile/guest и существующие JIT self-test + software display/input. Не использовать Android snapshots/автосохранение/GL policy: `QemuRunner.run()` сейчас содержит общую Android-логику даже вокруг phase0. Не трогать сохранения Husk. Новый Linux session directory обязателен. Проверить те же два кадра и реальные touch/key события на iPhone 16 Pro Max; получить OS build, signed binary hash и логи.
3. **Steam guest.** Отдельный glibc ARM64 disk: фактический loader + DT_NEEDED closure, Xorg/modesetting/software Mesa, полный официальный клиент с `_all` ресурсами. Сначала настоящий `steam -gamepadui` и CEF, затем пользовательский вход и три минуты живой навигации. Нынешний Alpine probe для этого недостаточен.
4. **GPU/games.** Отдельный этап и отдельные измерения; никакие frameblit/JIT/AArch64 результаты не доказывают Metal/Vulkan ускорение гостевых игр. FEX/Box64 выбирать по ELF конкретных игр/Proton, не по названию каталога клиента.
5. **Лицензии.** Исследованные проекты и pins сведены в `RESEARCH.md`. Не склеивать автоматически GPLv3/exception app с QEMU/Husk: перед комбинированным target/distribution проверить конкретные файлы и зависимости. В этой сессии чужой runtime-код не перенесён, лицензия проекта не менялась, публикации не было.

Muguet — подготовленный WASM/AOT, Madeira/Playport — Windows/Wine, CyPort — конкретный macOS Mach-O port, d2r-mobile — конкретная Switch/HLE adaptation. Они дают технические приёмы, но не заменяют отсутствующий Linux guest/Steam proof. REA не понадобился: ABI вопрос удалось закрыть без декомпиляции.
