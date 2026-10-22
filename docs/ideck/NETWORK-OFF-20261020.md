# iDeck-BCD: сервисы апстрима выключены (20 октября 2026)

Пункт 1 `docs/migration/FIRST-SCOPE.md` и пункт 7 аудита для четырёх
исходящих путей: отправка логов, отзывы, проверка обновлений и онлайн-список
рекомендаций. Все четыре по умолчанию выключены и отказывают сразу, с понятным
сообщением на устройстве. Адресов апстрима в коде больше нет (в шапках
файлов они остались как описание исходного поведения). Новых адресов не
придумано.

**Ничего не собрано и не запущено.** Xcode, Swift и тестов проекта на этой
машине нет (`AGENTS.md`). См. «Не проверено» ниже.

## Одно место для своих адресов

`app/Madeira/Info.plist`, словарь `IDeckEndpoints`. Пустая строка (так сейчас)
значит «выключено». Адрес принимается только как `https://` с хостом, иначе
тоже выключено.

| Ключ | Читает | Что должен отвечать адрес | Пока пусто |
| --- | --- | --- | --- |
| `LogIntake` | `LogUpload.swift` | POST gzip, заголовок `X-BCD-Intake: madeira-bcd/2`, ответ JSON `{"code": …}` | Send Log: «Sending logs is off in this build…», лог не упаковывается; кнопки Send Log в окне auto-tune нет |
| `FeedbackIntake` | `FeedbackUpload.swift`, `BCDSettingsLive.swift` | POST JSON (kind, text, build, ios, model, log), ответ `{"code": …}` | «Sending feedback is off in this build…»; приложенный лог тоже не уходит |
| `ReleasesLatest` | `BCDUpdates.swift` | как `GET /repos/<owner>/<repo>/releases/latest` у GitHub: `tag_name`, `html_url` на github.com | Settings › Updates: «Update checks are off in this build. Nothing is asked online.»; при старте ничего не запрашивается, чипа нет |
| `RecommendationsJSON`, `RecommendationsSignature` | `GameRecommendationsSource.swift` | файл формата 1 и его подпись Ed25519 (`tools/publish-recommendations.py`) | только встроенный список; `refresh()` ничего не запрашивает и отвечает `.off`; фоновой проверки нет; скачанный раньше список не читается |
| `RecommendationsPublicKey` | там же | наш открытый ключ Ed25519, 32 байта в base64 | ключ BCD: список с нашего адреса, подписанный нашим ключом, будет отклонён |

Онлайн-список включается, только когда заданы оба адреса. Проверка подписи,
формата, политики и регрессий не изменилась.

Перед тем как заполнять: согласие и политика приватности (FIRST-SCOPE, п. 1),
свой приёмник (Worker апстрима `bcd-logs/` в этот импорт не входит), свой
ключ подписи. Значение можно задать и через build setting (`$(…)` в
Info.plist), но в `.xcconfig` `//` начинает комментарий.

## Что работает локально

- Settings › Logs › «Export BCD's log» (share sheet): не трогали, к
  `LogUpload` не относится.
- Встроенный список рекомендаций v2 с правилом `unity`, «Reset to
  Recommended».
- Кнопка обновления рекомендаций на странице игры отвечает «No list online
  yet: using the built-in list».

## Уточнение к LARGE-CHANGES-20261019.md, §2

Там сказано, что апстримная v3 уберёт правило `unity`. По коду это не так:
`regression(from:)` требует, чтобы скачанный список содержал каждое правило
встроенного, и v3 без `unity` была бы отклонена (`[recs] rejected …: it has no
rule unity`). Но тогда форк не получал бы новых правил апстрима, раз в 6 часов
обращался бы к GitHub апстрима и писал ошибку в лог. Теперь источник
выключен, и вопрос снят.

## Изменённые файлы

- `app/Madeira/Info.plist`: словарь `IDeckEndpoints`, все значения пустые.
- `GameRecommendationsSource.swift`: адреса берутся из Info.plist,
  `RecommendationsStore.online`, `.off` в `RecommendationsRefreshResult`,
  проверки в `initialList`, `start`, `refresh`, `fetch`, необязательный свой ключ.
- `BCDGamePageLive.swift`: `.off` показывается как «нет списка онлайн».
- `LogUpload.swift`, `FeedbackUpload.swift`: `endpoint` стал `URL?`, ошибка
  `.off` до любой работы.
- `BCDSettingsLive.swift`: отзыв при выключенном приёмнике не отправляет
  и приложенный лог.
- `AutoTuneViews.swift`: Send Log в окне auto-tune только при заданном приёмнике.
- `BCDUpdates.swift`: `BCDUpdateFailure.off`, адрес как свойство экземпляра
  (тесты и превью задают свой).
- `app/BCDPreview/BCDSettingsPreviewData.swift`: превью задаёт заглушку
  `https://preview.invalid/…` (зарезервированное имя, запросов нет: ответ
  подставлен), чтобы образец с чипом обновления остался.
- Тесты: `check-remote-recommendations.py` (статические проверки и новый
  раздел Swift-фикстуры «выключено по умолчанию»; дальше конвейер идёт с
  заглушками `https://recs.test/…`), `check-log-upload.py`,
  `check-feedback.py`, `check-bcd-settings.py` (раздел «выключено» в драйвере,
  дальше заглушка `https://updates.test/…`).

## Не проверено

- Не собрано, Swift-фикстуры не запускались, тесты проекта не запускались.
- Своя проверка (скрипт вне репозитория): все четыре изменённых теста
  разбираются Python, Info.plist читается `plistlib`, новые строковые
  проверки тестов выполняются на текущих исходниках, скобки в изменённых
  Swift-файлах сбалансированы, в коде приложения нет адресов апстрима.
- Уже до этого изменения падали при запуске (здесь не исправлялось):
  `check-log-upload.py` и `check-feedback.py` читают `bcd-logs/worker/*`
  (нет в импорте), `check-feedback.py` ещё и `tools/pull-logs.py` (нет);
  `check-remote-recommendations.py` читает `.github/workflows/build-ipa.yml`
  (воркфлоу лежит в `docs/upstream-workflows/`).
- На устройстве: тексты в Settings › Updates, Send Log, Feedback и на
  странице игры; что к этим хостам нет ни одного запроса (нужен журнал сети
  или прокси).
- Другие исходящие пути (Steam, обложки, JIT, Dock) в этом изменении не
  смотрели. Фраза в `AGENTS.md` «endpoints are STILL present» для этих
  четырёх путей устарела; сам `AGENTS.md` не менялся.

## Слияние с BCD 0.1.580 (22.10)

Апстрим добавил пятый исходящий путь: ежедневную проверку новой версии
(`BCDUpdateCheck.swift`, `UpdateNotice.swift`, адрес
`thebcd69.github.io/bcd-games/source.json`). В этой сборке она по умолчанию
выключена: `SteamSignIn.flag("MADEIRA_UPDATE_CHECK", default: false)`, в
каталоге настроек значение `0`. Её источник называет сборки апстрима, а не
этого форка. `env.MADEIRA_UPDATE_CHECK = 1` включает её вручную. Новый
workflow апстрима `altsource.yml` лежит отключённым в
`docs/upstream-workflows/altsource.yml.disabled`.
