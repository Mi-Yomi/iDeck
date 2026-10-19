> CURRENT CI BUDGET — provider35 / worker30 minutes, 19 October 2026.
> Cache identity code from4f8f70bd is unchanged. Exact locked QEMU10.0.12-utm
> archive digest/size and serial/GET_ID/RO source support independently verified;
> upstream Linux6.18.35 sysfs/20-byte ID support reviewed. **602 Python tests
> OK /5 SKIP**, overlay/pins and timeout cleanup checks PASS.
> CI#41 consumes the earlier62-minute balance. Coordinator must verify the fresh
> remainder with reserve and paid OFF after it finishes before any manual run.
> No CI started/cancelled here; old cap55/50 and larger limits are historical.
> New Apple/phone/real QEMU verification **NOT RUN**; BusyBox provenance **OPEN**.
> [Budget and serial review](STEAM-CI-BUDGET35-REVIEW-20261019.md).

> CURRENT SOURCE CORRECTION — stable Steam cache device identity, 19 October 2026.
> Based on `460d5f260089e0c9f0a62d0049a6ee04b9e78468`. Coordinator-inspected
> device screenshot10:51 UTC shows `offline_cache_not_readonly`; this is separate
> from RAM/JIT feedback. The old guest guessed `/dev/vdb`, although ARM virtio
> disk order is unstable and root is already found by UUID. New argv supplies a
> cache serial; the guest selects its unique identity, checks major/minor, then
> still requires actual RO=1, exact size and all pinned bytes. Device mapping
> on the owner's phone remains unmeasured; no real host QEMU result is claimed.
> **599 Python tests OK /5 SKIP**, full overlay and real repeated staging PASS.
> New Apple/Swift/phone acceptance **NOT RUN**. Base payload/cache, native worker,
> user disks and safety guards unchanged; no Release or payload rebuild needed.
> CI#41 on460d5f26 was coordinator-reported running and lacks this correction.
> No parallel/new CI started here; recheck fresh remaining quota and paid OFF
> before any future manual run. Current cap55/worker50 remains unchanged.
> BusyBox provenance **OPEN**. [Cause, safety and evidence](STEAM-CACHE-DEVICE-IDENTITY-20261019.md).

> CURRENT SOURCE CORRECTION — launcher memory/JIT feedback, 19 October 2026.
> Based on `c810b682601634920e8ff601b6832c08524896e9`. The coordinator inspected
> the owner's screenshot: manifest/JIT/network PASS, **Auto memory preflight
> BLOCKED** before native entry. This proves click handling reached preflight;
> hit testing/JIT failure is not established. Actual numeric budget is unknown.
> The new source shows measured process budget/minimum and offers the existing
> fixed1536 mode with fresh checks. Reserves and native/disk safety are unchanged.
> JIT off shows an inline setup action; returning rechecks real JIT and offers
> explicit continuation, without auto-starting a VM or leaving a pending spinner.
> **595 Python tests OK /5 SKIP**, exact full overlay/real repeated staging PASS.
> New Apple/Swift/UI and phone behavior **NOT RUN**; CI#40 below predates this fix.
>
> Next manual CI: reviewed post-fix remote HEAD, `ideck-linux-probe-ipa`,
> `mac_mini_m2`, Xcode27.0, **cap55 / worker50 minutes**. Supplied62-minute free
> snapshot leaves7 minutes beyond cap; freshly verify quota/reserve and paid OFF
> before dispatch with the existing four approval inputs. No CI started here.
> BusyBox provenance **OPEN**. See [cause, changes and evidence](LAUNCHER-JIT-MEMORY-FEEDBACK-20261019.md).
> Older wait/cap70/65/95 and JIT-return instructions below are historical.

> CURRENT DELIVERED RESULT — unified launcher, Apple CI#40 PASS, 19 October 2026.
> https://codemagic.io/app/6ad03ce9a8a969b53f3a4aa9/build/6ad5e8747550aed8109013fd . Duration16m44s.
> **Built source: cf773c48e4c11d9c341667cb55e5b40522655df8.**
> `LINUX_UNIFIED_ENVIRONMENT_PASS` confirmed in mac-tests.log.
> IPA **1086777985 bytes**, SHA-256
> **9c8565f28f8a25cd81109a74562f4bf915c532095b2605b4f8f0f8f7b5e8c7c0**.
> Coordinator independently verified ZIP CRC, resources/cache and all7 Mach-O
> binaries as arm64 iPhoneOS ad-hoc. Owner-only Drive delivery is confirmed;
> the personal Drive URL is not stored in Git. CI/artifact/delivery facts in this
> block are coordinator supplied; this docs-only task did not download/rebuild
> the IPA, change code/pins/secrets, dispatch CI or modify any Release.
>
> One **Запустить среду** entry uses the existing VM/disk/cache, with local
> installation then Steam launch driven by guest receipts. Home/Resume retain
> that VM; explicit JIT/network consent and safe Stop remain. Source regression:
> **591 Python tests OK /5 SKIP**, full overlay and real repeated staging PASS.
> **iPhone/device, automatic real Steam installation/rendering and gameplay
> NOT RUN — WAIT FOR OWNER FEEDBACK.** Apple CI is not device acceptance.
> Controls remain keyboard/mouse mapping, not a Linux HID gamepad. Disk12 GiB
> and experimental Auto4096 unchanged; BusyBox source provenance **OPEN**.
>
> Latest coordinator quota snapshot: **62 free minutes, paid OFF**. Current
> provider cap70 / worker65 exceeds that remainder: **do not start another CI**.
> Any future run requires a newly reviewed suitable limit, fresh free quota with
> reserve, paid-OFF/private/native checks and the exact reviewed source SHA.
> Historical dispatch instructions below do not authorize a new run.
> Details: [unified launcher](UNIFIED-ENVIRONMENT-LAUNCHER-20261019.md).

> PREVIOUSLY DELIVERED RESULT — Apple CI#39 PASS, 19 October 2026.
> https://codemagic.io/app/6ad03ce9a8a969b53f3a4aa9/build/6ad5d2987550aed810900dd2 . Duration25m41s.
> **Built source: bcbb8db7c909d34f05ccdf6ec95675f26f29ed78.** LINUX_STEAM_BUNDLED_CACHE_PASS
> and LINUX_STEAM_SCREEN_CONTROLS_PASS confirmed in mac-tests.log;
> native/link/signature/resources PASS. Ad-hoc arm64 iPhoneOS IPA:
> **1086741944 bytes**, SHA-256
> **84ec6d48c496fdaccb9ff02ceda11c1250d8eaefb58b431342f0217ceb2573c9**.
> ZIP CRC and exact Info.plist SHA checks PASS. Actual embedded cache
> **379228160 bytes**, SHA-256
> **a75ea9bb8a19946cf81b2fb3d6cc4db97db6a1fe0938e4f23857c2c6e826adef**.
> Owner-only Drive delivery and owner notification confirmed by the coordinator;
> no personal Drive link is stored in this repository. All CI/artifact/readback/
> delivery facts above are coordinator supplied. This docs-only update does not
> rebuild/download the IPA, dispatch CI or change code/payload/overlay/source pins.
> Its commit is distinct from the built source SHA above.
>
> **Device / Steam / gameplay NOT RUN.** Controls are keyboard/mouse mapping,
> not a detected Linux HID gamepad. No manual cache import is needed in this
> built IPA; local Install/resume and Launch Big Picture remain explicit.
> Steam updater/login/agreements may need network and owner action; existing
> guest/runtime errors are not declared fixed by predownload. Disk12 GiB and
> experimental Auto cap4096 unchanged. BusyBox source provenance **OPEN**.
>
> Historical CI#39 checkpoint: **79 free macOS minutes, paid OFF**.
> The then-configured cap95 exceeded79; no CI was authorized by that checkpoint.
> Any future build requires a separately reviewed smaller provider cap and
> matching internal budget within fresh remaining quota with reserve, plus
> private/native approvals and paid-OFF verification. No cap/code change now,
> no new CI run/cancel here. Historical run instructions below are superseded.

**Исходный запрос ниже сохранён как история; повторно не выполнять. Ждём device feedback.**

# Исторический запрос для Dots — выполнен Apple CI#39

Собери настоящий iDeck Linux Probe IPA из приватного репозитория
`https://github.com/Mi-Yomi/iDeck`, ветка
`codex/steam-arm64-experiment-20261017`. Пользователь разрешил сборку и push
необходимых исправлений в эту ветку. Сам iPhone сейчас недоступен для проверки:
модель iPhone 16 Pro Max, версия iOS 27 со слов владельца.

Примени Ponytail: минимальные законченные изменения, существующие инструменты
и проверки. Если навык ещё не установлен, прочитай `SKILL.md` проекта
`https://github.com/dietrichgebert/ponytail` и следуй ему. Не создавай новую
архитектуру ради сборки.

1. Выбери указанную ветку, запиши полный SHA её актуального удалённого HEAD и
   проверь чистый checkout. Прочитай `GAME-RUNTIME-RESULT-20261018.md`,
   `STEAM-UI-RESULT-20261018.md`, `experiments/linux-guest/README.md`,
   `ci/check_build_request.py`, `ci/build_linux_probe_ipa.py`, `codemagic.yaml`
   и блок текущего состояния в `HANDOFF.md`. Старые PID, локальные пути E: и
   незавершённые диски из истории не являются входами Codemagic.
2. В Codemagic выбери приватный **Mi-Yomi/iDeck**, затем именно эту ветку,
   workflow **`ideck-linux-probe-ipa`**. Разрешение Steam-ветки добавлено только
   этому ручному IPA workflow; `main` и посторонние ветки должны отклоняться.
   Не подменяй `CM_BRANCH`, `CM_COMMIT` или фактический HEAD для обхода проверки.
3. Перед запуском проверь фактический остаток бесплатной macOS-квоты: требуется
   минимум **120 минут**, платная подписка должна быть выключена. Старые записи
   об остатке квоты не подходят. После реальной проверки задай inputs:
   `expected_commit=<полный проверенный SHA>`, `free_quota_verified=true`,
   `private_source_verified=true`, `native_build_approved=true`.
   Используй предусмотренные `mac_mini_m2`, Xcode 27.0 и лимит 120 минут.
   Нативная сборка и её закреплённые зависимости разрешены этой задачей.
4. Проверь, что приватная группа `ideck-debian-payload` доступна этому workflow.
   Steam payload независимо проверен и закреплён как ready: asset `654660064`,
   303667200 байт, SHA-256
   `f74e22f44422d5dded7dd23d2a8e9a22a98e2df13edd4620187943529a29c62c`.
   Используется существующий `IDECK_DEBIAN_PAYLOAD_TOKEN` по точному API URL
   из Steam lock; новый секрет или Steam URL variable не требуется.
   Используй существующий механизм получения payload по lock-файлам и
   проверки хешей. Не вставляй токены в код, логи или ответ. Не изменяй принятые
   GUI/Debian/Terminal payload, Release или пользовательские диски, чтобы
   обойти ошибку загрузки.
5. Запусти ручную сборку и дождись результата. При ошибке прочитай конкретный
   журнал, исправь её минимально в этой же ветке, выполни относящиеся к ней
   проверки и push с `[skip ci]`. Для следующей ручной попытки проверь квоту
   заново и передай новый точный SHA. Не запускай слепые повторы или платные
   сборки. Не заменяй реальные библиотеки заглушками и не отключай проверки
   ABI, Apple platform, sandbox, целостности или ветки.
6. Получи **`.work/linux-ipa/iDeck-Linux-Probe.ipa`** и соответствующий
   **`.work/linux-ipa/result.json`**. Подтверди успешный нативный link/package,
   `ipa_created=true`, размер и SHA-256 IPA; проверь bundle ID
   `dev.ideck.linuxprobe`, arm64 iPhoneOS, отсутствие simulator/Mac Catalyst
   и наличие предусмотренных ресурсов/библиотек. Верни ссылку на конкретный
   Codemagic build, точный commit и приватный артефакт IPA с SHA-256.

Это существующая **ad-hoc IPA для последующей подписи владельцем при sideload**,
не готовая персонально подписанная установка. Не запрашивай пароль Apple ID,
не публикуй в App Store/TestFlight и не меняй signing identity. Если требуемая
бесплатная квота, права или секретная группа действительно недоступны, сохрани
точную причину и доступные журналы; не отмечай сборку успешной.

## Что действительно проверено

- В локальной QEMU ARM64 ВМ работала ARM64 WineMine через официальный Runtime4
  и GE-Proton: отрисовка, клик, сброс F2, обычное закрытие и exit 0.
- У x86-64 WineMine подтверждены загрузка выбранного PE и FEX в том же процессе,
  но игрового окна не подтверждено: эксперимент закончился по лимиту.
- Это не проверка Steam-игры, GPU/FPS, JIT или работы приложения на iPhone.
  Локальные Valve-файлы, аккаунт, приватные журналы и образы ВМ не входят в IPA,
  Git или Release. Не добавляй их туда.
- Исходники включают отдельный экспериментальный Steam-маршрут; ready payload
  проверен и должен пройти существующий staging/package gate. Клиент Valve
  в нём отсутствует, установка на устройстве требует явного согласия на сеть.
  Apple/Swift/native link/package для нового pin и Steam/Big Picture/Windows
  gaming на iPhone **NOT RUN**. Не объявляй их проверенными по Python/staging.
- GetMoreRAM требует разрешения Increased Memory Limit для соответствующего
  App ID и повторной подписи/установки владельцем. Его фактический эффект на
  iOS 27 здесь не измерен. Новый UUID-scoped seed Steam имеет фиксированные
  12 GiB и 1536 MiB RAM; импорт/сохранность на iPhone не проверены. Установка игр
  во всё доступное внутреннее хранилище и рост существующего диска не реализованы.
- Полнота BusyBox corresponding-source provenance остаётся OPEN: точная Alpine
  revision и matching source/patch/recipe/source-delivery evidence отсутствуют.
  См. `BUSYBOX-PROVENANCE-20261018.md`; pinning не закрывает этот вопрос.

Заверши конкретным результатом сборки, а не планом: build URL, commit, IPA,
размер, SHA-256 и статус подписи. Отдельно перечисли проверки, для которых
нужен телефон. При отсутствии доступа к Codemagic прямо укажи этот блокер;
не выдумывай запуск или ссылку на IPA.
