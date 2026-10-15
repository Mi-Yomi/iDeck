# HANDOFF — продолжение iDeck, 2026-10-15

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
