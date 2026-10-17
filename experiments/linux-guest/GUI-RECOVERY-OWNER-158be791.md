# Восстановление существующего GUI-диска в IPA158be791

Инструкция проверена по исходникам
`158be7910d1c372cdddbf7cb87706ad2ce69042f`, а не по предполагаемым кнопкам.
Production9c4d host recovery gate — [PASS](evidence/gui-recovery-production9c4d-20261017/README.md).
**Phone recovery — NOT RUN**: восстановление существующего диска на телефоне
ещё должен проверить владелец. Сборка IPA для этого SHA уже существует по
сообщению владельца; новая CI этой документацией не запускалась.

## Обновление через SideStore с сохранением userdata

Обновить существующую установленную копию обычным SideStore sideload того же
приложения, сохранив его app identity и прежний аккаунт/подпись. Официальная
[SideStore FAQ](https://docs.sidestore.io/docs/faq#can-i-transfer-my-altstoresideloadly-apps)
описывает установку того же или обновлённого IPA поверх существующего приложения
с сохранением данных. Исходное приложение и диск удалять не требуется.

В source препятствия для такого обновления не обнаружено:

- Packager проверяет bundle ID **`dev.ideck.linuxprobe`**; он тот же, что в
  предыдущей owner-reported GUI-версии27e9736f.
- Отдельный GUI-диск остаётся в
  **`Documents/iDeckDebianGUI-v1/rootfs-v1.raw`**. Существующий диск открывается
  по этому пути, а не заменяется заново bundled seed.
- Recovery сохраняет исходный диск и создаёт собственные backup/work-копии.
  Для первой попытки нужны две полные копии1.25GiB плюс512MiB резерва —3GiB
  дополнительного свободного места. Приложение проверяет место самостоятельно.

Фактические переподписанные identifier/team установленной SideStore-копии и
новой IPA из облака не проверены. Если SideStore сообщает конфликт identity или
собирается поставить отдельную копию, перенос прежнего Documents не подтверждён:
остановить обновление на этом сообщении, сохранить существующую установку/диск
и передать точную ошибку. Удаление приложения или диска не является шагом recovery.

## Первый запуск: JIT и recovery

1. Открыть обновлённое приложение и выбрать
   **“Debian desktop · windows and apps”**. Не запускать другой Linux-режим в
   том же процессе: выбор окружения и native VM одноразовые до полного выхода.
2. Нажать **“Enable JIT”** в панели desktop и дождаться завершения текущего
   рабочего JIT-метода без ошибки. Если нужен walkthrough, его кнопка именно
   **“JIT setup”**. Для уже настроенного built-in helper с текущим pairing и
   установленным LocalDevVPN в нём есть
   **“Continue with the current pairing” → “Connect LocalDevVPN” → “It's connected” →
   “Check setup” → “Enable JIT” → “Done”**. Это условный путь существующего setup.
   Если LocalDevVPN не установлен, его кнопка называется **“Get LocalDevVPN”**.
   Заново создавать pairing, если прежний работает, не требуется. Само attachment
   не заменяет execution check: приложение проверяет JIT перед стартом VM.
3. Для существующего dirty GUI-диска нажать верхнюю **“Recover disk”** до любого
   VM-start в этом процессе. Она запускает отдельную recovery VM на проверенных
   копиях. Кнопка **“Serial recovery”** открывает текстовую консоль; repair-workflow
   запускается через **“Recover disk”**.
4. Оставить iDeck открытым во время копирования, проверок и hashing. Сообщения
   **“Recovery: hashing the checked work copy…”** и
   **“Recovery checks finished. Waiting for Linux shutdown and host sync. Keep iDeck open.”**
   ещё требуют ожидания. Успешный конец — сообщение:
   **“The recovery VM finished checking its copy. Fully close and reopen iDeck, then choose Start desktop to validate and activate it. Original backup is preserved; no disk is promoted in this process.”**
   Оно появляется после clean unmount, возврата VM и host sync. Полный текст
   состояния также доступен через **“Diagnostics”**, раздел **“Startup status”**.
5. До закрытия сохранить MD через **“Share report”** по шагам ниже. Только после
   подтверждённого завершения полностью закрыть iDeck через переключатель
   приложений. Переход на Home или закрытие sheet не создаёт нового процесса.

Если recovery завершилось ошибкой/timeout/недостатком места, успешное восстановление
не подтверждено и work не активируется. Сохранить **“Share report”** или saved
startup MD. Исходный диск/backup не удалять и не заменять; ручной repair требует
отдельного разбора отчёта.

## Новый процесс: активация проверенной копии

1. Снова открыть iDeck → **“Debian desktop · windows and apps”**.
2. Снова нажать **“Enable JIT”** и дождаться завершения без ошибки. JIT относится
   к новому процессу; pairing/setup могут сохраниться, attachment прежнего процесса — нет.
3. Нажать **“Start desktop”**. Именно этот путь в новом процессе проверяет pending
   receipt, original/backup, весь digest work и затем активирует проверенную копию
   перед запуском GUI. Повторный **“Recover disk”** для уже verified receipt не нужен.
4. Проверить свои прежние файлы в GUI. После проверки нажать **“Stop Linux”**,
   дождаться подтверждения clean unmount/data sync, сохранить новый MD report.
   Перед следующей VM-сессией опять полностью закрыть/открыть приложение и включить JIT.

Full-app-restart gate намеренно сохранён. В процессе recovery нет кнопки,
которая превращает завершённую recovery VM в новую GUI VM: активация допускается
только после выхода прежнего процесса и освобождения его native ownership/locks.

## Как экспортировать MD report

- Верхняя **“Share report”** открывает системное окно sharing для текущего
  session `.md`, либо текущего startup-journal MD. Она остаётся доступной при
  заблокированном старте; JIT/работающая VM для экспорта не нужны.
- Если текущего отчёта ещё нет, откроется **“Diagnostics”**. Там есть
  **“Share session report (.md)”** в разделе **“Session report (.md)”**, когда
  session-файл существует.
- После полного перезапуска: **“Diagnostics” → “Refresh saved reports”**, затем
  нужная **“Startup report 1 (.md)”**, **“Startup report 2 (.md)”** и т.д.
  Выбирать нужную попытку по её времени/Attempt/source, номер не является постоянным ID.
- При отдельном запросе на разбор native выхода для той же попытки доступна
  **“Native log summary 1 (.md)”** и соответствующие номера.
- Закрыть окно диагностики можно через **“Done”**. Сам экспорт не запускает JIT,
  recovery или Linux и не читает содержимое пользовательского диска.

Источники названий и поведения:
[chooser](ios/LinuxProbeView.swift), [desktop UI/export](ios/LinuxDesktopView.swift),
[start/recovery/finalization](ios/LinuxTerminalSession.swift),
[receipt/promotion](ios/LinuxGUIRecovery.swift),
[JIT walkthrough patch поверх pinned Husk](husk/patches/0002-jit-setup-routing.patch),
[bundle/packaging](ipa/package_probe.py), [bundle settings](ipa/project.json).
Не передавать pairing-файл или весь Documents для MD-диагностики.
