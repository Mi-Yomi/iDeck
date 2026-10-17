# Следующий milestone: persistent POSIX Linux и минимальный desktop

Обновление **2026-10-17**: [GUI-DESKTOP.md](GUI-DESKTOP.md) описывает настоящий
Xorg/Openbox/tint2/PCManFM/Mousepad/xterm, clean1.25GiB GUI seed и два real host
boot со вводом/scroll/menu/save/reopen/Stop/fsck. Native Desktop route и отдельные
profile/disk/payload staging уже реализованы в исходниках;269 tests/5SKIP.
Host Debian6.12.107/QEMU10.0.13 отличается от production Alpine6.18.35/iOS10.0.12.
Доставка exact modules блокирует matching-kernel GUI gate и sealing asset lock.
Apple/full native link/IPA/device GUI NOT RUN; CI не запускался. Старые статусы
ниже исторические, новый `ipa/gui.lock.json` намеренно blocked.

Обновление реализации G0/G1: [DESKTOP-ROOTFS.md](DESKTOP-ROOTFS.md) и новый
host receipt описывают locked Debian builder и отдельный ext4 storage contract.
Ниже сохранён исходный design; его прежние tool/package «не готовы» отражают
состояние до этой реализации. Guest mount/two-boot, GUI и Apple/device gates
по-прежнему не пройдены; module closure заблокирован недоступным pinned archive.

План от **2026-10-16**, база **190f87caa0aac16e81d20cd699bd54b5e9f4d8f9**.
Это feasibility/design; runtime, payload, CI, guest/host network settings здесь
не менялись. Сначала один настоящий desktop с сохранением файлов и рабочим
вводом, затем отдельный software-GL gate, затем отдельная Steam/CEF задача.

## От чего продолжаем

Parent сообщил Apple CI **6ad1efad7550aed8108f37fe SUCCESS, 12m21s**, actual
source **190f87caa0aac16e81d20cd699bd54b5e9f4d8f9**. IPA **58868284**, SHA-256
**3e57c5c895afb41de51708458b12644725ccb040f8b0b9fb073bf9b57cd6edae**.
Owner в **09:56 UTC** сообщил «Все прекрасно сработало». Parent осмотрел
READY, вывод uname **Linux (none) 6.18.35-0-virt … Alpine … aarch64**, повторное
**ideck-test**, отсутствие прежнего [6n. Ранее подтверждён один файл после двух
boot с clean guest unmount; теперь он пережил и обновление приложения.
Это owner/manual и parent screenshot evidence, не прямой осмотр снимков этим
executor. Не доказаны crash durability, whole-volume integrity, GUI, Steam/GPU.

Исходный README/RESEARCH задаёт glibc ARM64 rootfs → Xorg/modesetting → software
Mesa → Steam/CEF. Устаревшие «IPA/device pending» в исторических разделах не
описывают этот новый terminal PASS. Alpine/musl probe остаётся диагностикой;
успешный uname не создаёт отсутствующий glibc rootfs.

## Рекомендуемый scope

**Debian 13/trixie arm64 minbase, отдельный ext4 image, Xorg modesetting без
glamor, Openbox и xterm.** Сохранять QEMU virt/cortex-a72, 4 vCPU, 1024 MiB RAM,
TCG tb-size=256 и split-wx=on, virtio-gpu-pci 800×600, keyboard/tablet и Husk
software DisplayChangeListener → BGRA Metal blit. Пока без compositor, display
manager, browser, sound integration, guest networking или swap.

Debian выбран для glibc/apt и дальнейшего ARM64 client dependency closure.
[Debian trixie поддерживает arm64](https://www.debian.org/releases/trixie/),
а [libc6 arm64](https://packages.debian.org/trixie/arm64/libc6) предоставляет
GNU libc. Это рекомендация, не проверенный на данном kernel userspace image.
Openbox — лёгкий standalone window manager, не весь DE. Debian published desktop sizing существенно больше: 2GiB RAM /
10GB disk recommendation, minimum 1GiB предполагает swap. Наши 1GiB без swap
и 4GiB — **экспериментальный budget для узкого Openbox image**, не гарантия
достаточности: G0 измеряет package/image fit, G2/G3 — RSS/peak/Jetsam и пригодность.
Если не помещается — остановиться и пересмотреть scope/budget отдельно.
[Debian hardware requirements](https://www.debian.org/releases/trixie/arm64/ch03s04.en.html).
Xterm даёт настоящий
terminal emulator внутри Linux; host serial line console остаётся recovery.
[Openbox package](https://packages.debian.org/trixie/arm64/openbox),
[xterm package](https://packages.debian.org/trixie/arm64/xterm).

## Состав rootfs и граница точности dependencies

Следующий build должен разрешить **весь arm64/all Depends/Pre-Depends closure**
из одного согласованного snapshot, без recommends и смешения Debian releases.
Зафиксировать InRelease/Packages checksums, каждое имя/версию/architecture/
SHA-256/размер .deb, пакетный manifest и notices. Ниже exact direct package
selection для resolver; это ещё **не готовый transitive lock**. Payload, итоговый
размер, конкретный snapshot timestamp и все transitive versions сейчас не
загружены/не разрешены, не объявлять их проверенными.

| Слой | Direct packages / артефакт | Что проверить |
| --- | --- | --- |
| Base | debootstrap minbase arm64: libc6, dash, coreutils, dpkg, apt и их closure | Реальный /lib/ld-linux-aarch64.so.1, ELF interpreter/DT_NEEDED и запуск shell |
| Tools / POSIX | e2fsprogs, util-linux, passwd, procps, kmod, ca-certificates | ext4 inspect/repair tools; uid/gid, mount, signal и процессные тесты |
| Devices | udev, systemd-standalone-sysusers | udev без смены PID1 на systemd; правила и sysusers реально исполняются |
| X server | xserver-xorg-core, xserver-xorg-input-libinput, xinit, xauth, xkb-data, keyboard-configuration | modesetting входит в core; libinput видит два virtio input устройства |
| Session | openbox, xterm, dbus, dbus-bin, dbus-daemon, dbus-x11 | Session D-Bus, видимый xterm; Xorg root/device access и desktop user UID1000 |
| Fonts / probes | fonts-dejavu-core, fonts-dejavu-mono, xfonts-base, x11-utils, x11-xserver-utils | Реальный font rendering, xdpyinfo/xrandr, keyboard layout |
| Позже G4 | libgl1-mesa-dri, libglx-mesa0, mesa-utils | Software renderer и фактический GL context; не нужно для первого 2D PASS |

На момент просмотра официальные страницы показывали libc6 **2.41-12+deb13u4**,
xserver-xorg-core **2:21.1.16-1.3+deb13u4**, arm64 openbox **3.6.1-12+b2**,
xinit **1.4.2-1+b2**. Это metadata observations, не build pins. Resolver обязан
проверить их вместе перед будущей загрузкой.

В частности Xorg core требует libdrm2/libgbm1/libgl1/libegl1/libepoxy0,
libpixman-1-0, libudev1, libsystemd0 и X11 libraries; наличие этих library deps
не означает запуск systemd PID1 или GPU acceleration. Xterm добавляет Xaw/Xft/
fontconfig/freetype/tinfo, Openbox — GLib/X11/свои rendering libraries.
[Core package dependencies](https://packages.debian.org/trixie/arm64/xserver-xorg-core),
[libinput driver](https://packages.debian.org/trixie/arm64/xserver-xorg-input-libinput),
[xinit](https://packages.debian.org/trixie/arm64/xinit),
[udev alternatives](https://packages.debian.org/trixie/arm64/udev).
Не заменять отсутствующий library ложным symlink на musl.

## Kernel/bootstrap: конкретный недостающий вход

Read-only inspection committed initramfs показал virtio_blk, virtio_net,
virtio-input и DRM/virtio-gpu dependency metadata, отдельный /ideck/evdev.ko.
**ext4.ko/jbd2.ko/mbcache.ko и ext4 entry в modules.builtin не найдены.** Это
не доказательство отсутствия built-in ext4 в самом kernel: config/mount ещё
не проверены. Gate G0 должен разрешить этот вопрос до сборки desktop image.

Сохранить kernel **6.18.35-0-virt** и его hash. Если ext4 не встроен — извлечь
ext4 и **полный фактический modules.dep closure** только из того же pinned
Alpine modloop, с vermagic/signature/hash проверкой. Не угадывать closure как
три .ko и не подставлять Debian kernel modules. Нужны virtio_pci/blk/gpu/input,
evdev, Unix sockets, VT/KD/DRM KMS, devtmpfs, proc/sysfs, devpts, tmpfs, ext4
и их реальная kernel config/module closure. Старые probe bytes не переписывать:
новый desktop bootstrap/suffix имеет отдельный profile/lock и тесты.

Прежний подготовительный источник — Alpine netboot archive **431008592 bytes**,
SHA-256 **54fe38fa41cce740ba379458ed63cfcd89ab06ae5e6a47a06dafe0a34e8427e8**;
рецепт — tools/prepare_guest.py. Этот большой archive сейчас не скачивался.
Если нужный модуль недоступен в pinned inputs — это G0 blocker, а не основание
менять kernel/ослаблять validation внутри того же изменения.

Для минимального перехода оставить PID1/control supervisor в bootstrap
initramfs: он монтирует ext4 в /sysroot и запускает **реальные glibc процессы
из Debian root через chroot**, не userspace-эмуляцию Linux и не fake desktop.
Ядро и процессы остаются внутри полноценной VM. /proc, /sys, /dev, /dev/pts,
/dev/shm и /run получают явные mounts в rootfs; modules tree соответствует
загруженному kernel. Udev запускается/trigger/settle, затем выделяется VT для
Xorg. Сегодня terminal-init не загружает gpu/input/evdev, в отличие от probe-init;
новый bootstrap обязан добавить и проверить их явно. Проверить его root/device access без systemd-logind; root Xorg launcher
и отдельный desktop session uid1000. /home/ideck — uid/gid1000, mode0700;
XDG_RUNTIME_DIR=/run/user/1000 — tmpfs uid1000/mode0700, Xauthority/session
sockets не world-readable. Udev rules и Unix group access проверяются на
реальных devices; не обходить их глобальным chmod666. Session bus через dbus-run-session,
не предполагать наличие system services. Полный systemd boot с switch_root —
дальнейший отдельный выбор; для G1–G3 он не требуется.

Всем session/Xorg/serial детям закрывать supervisor control fd3. Readiness
пишет только supervisor после проверенного mount, X connection и map xterm,
не после одного fork/exec. Ошибки mount/loader/Xorg пишутся статическим stage
кодом; произвольные logs остаются local/manual export.

## Display и input

[Xorg modesetting](https://manpages.debian.org/trixie/xserver-xorg-core/modesetting.4.en.html)
работает через DRM KMS и dumb buffers. Первый config: Driver=modesetting,
AccelMethod=none, SWcursor=true, ShadowFB=true, целевой 800×600/depth24 с
32-bit scanout. VT/DRM master и /dev/dri/card* должны проверяться, а не выводиться
из прежнего /dev/fb0 PASS. Xorg может выбрать другой mode/stride: его фактические
размеры, format, stride, damage и input transform проверяются заново.
Husk C listener принимает x8r8g8b8/a8r8g8b8; Swift MetalView blits BGRA.
Неподдерживаемый format — диагностический отказ, не чёрный экран как PASS.

Rootfs X server: local Unix display :0, -nolisten tcp, session Xauthority;
никакого VNC/SPICE/host forwarded shell для этого milestone. Не переносить
Android GL/snapshot runner. Native graphical route изолирован и выбирается
один раз за app launch, как существующие Linux routes. Нужны отдельный
validated desktop profile и worker, сохраняющие JIT/self-test, journal,
stop/control и ownership; FAT-only 128MiB validators не расширять молча.

Сегодня HuskMetalView передаёт absolute pointer + **left button only**;
probe Send A проверяет только одну клавишу. Desktop UI должен дать ASCII
keyboard/Enter/Backspace/Tab/Esc/arrows и парные modifiers через named QKeyCode,
отпускать на focus loss/background/cancel; нужна проверенная правая кнопка и
scroll либо явно ограниченный первый input scope. Serial sendLine не является
вводом в xterm. Touch mapping при letterbox/rotation и drag проверить реально.
Keyboard text entry должен явно выключать capitalization/correction/smart
quotes/smart dashes. Нерешённый terminal safe-area/long-output UI сохраняется
отдельным backlog, а не считается исправленным новым desktop.

После 2D можно отдельно добавить software GL. Mesa документирует
LIBGL_ALWAYS_SOFTWARE=true и GALLIUM_DRIVER=softpipe/llvmpipe; конкретный
собранный driver и renderer проверять glxinfo, не только environment variables.
[Официальные Mesa envvars](https://docs.mesa3d.org/envvars.html).
Наличие host Metal presenter или compiled virgl dependencies не доказывает
ускорение guest. Не включать virgl/Venus/Vulkan/Gamescope как prerequisite.

## Storage, доставка и сохранение /data

Новый путь **Documents/iDeckLinuxDesktop/rootfs-v1.raw**, raw ext4, начальная
**проектная ёмкость 4 GiB** (не измеренный package footprint). Полный rootfs,
/home и installed config persistent. FAT userdata **Documents/iDeckLinux/userdata.raw**
остается прежним 128 MiB файлом; никогда не конвертировать/форматировать in place.
Не использовать FAT для /usr, package database, POSIX home или symlinks.

Большой rootfs лучше доставить **offline import отдельного .img.gz** с reviewed
profile/size/digest в приложении, а не вшивать 4GiB raw в каждую IPA. Копия seed
не перезаписывает живой rootfs при app update. Stream decompress/hash/bounded
write в same-directory temporary, проверить exact decompressed count/ext4 UUID/
features, fsync и publish no-clobber; отказаться при low-space/truncation/
symlink/hardlink/wrong image без удаления существующих данных. Seed digest —
только для provisioning; mutable rootfs при reopen проверяется по identity,
типу, размеру и FS contract, не по исходному whole-file hash.

Отдельный host owner держит LOCK_EX на rootfs и legacy disk до process exit,
включая после Stop. Два файла захватываются nonblocking в фиксированном порядке,
partial acquisition закрывается только до C entry. file.locking=off допустим
на каждом QEMU file-child только при соответствующем живом проверенном token;
Darwin double-lock fix не отменять. Нельзя передать новый ext4 диск в старый
FAT-only LinuxTerminalDisk и просто ослабить его guards. Root and legacy guest
volumes определять по проверенным UUID/serial/type, не по порядку /dev/vdX.

Для первого desktop boot legacy attachment **read-only и на QEMU, и при mount**,
в rootfs по прежнему пути **/data**: /data/check.txt сразу доступен, source bytes
не меняются. Mount с uid=1000,gid=1000 и ограниченными masks должен позволять
непривилегированному desktop пользователю читать старые файлы: нынешний
terminal umask077/root mapping нельзя переносить вслепую. POSIX user files пишутся в /home/ideck на ext4. Terminal route по
прежнему открывает тот же FAT /data rw, при новом app launch, не одновременно.
Это точный совместимый transition; /data пока сохраняет FAT ограничения.

Позже, только при необходимости writable POSIX /data: copy import с legacy RO
из /mnt/legacy-data в staging directory нового ext4, verified file counts/hashes,
fsync и recoverable atomic publication. Не overwrite непустой destination и не
следовать symlinks из destination. Старый FAT не удаляется, не зеркалируется и
не переименовывается; import — один раз с receipt. После переключения /data в
новом режиме POSIX, legacy доступен RO отдельно. Rollback к terminal видит
старое FAT состояние; новые desktop изменения не объявляются автоматически
синхронизированными назад. Проверить interruption/retry и Unicode filenames.

Пусть D=4GiB, C=compressed image size (пока UNKNOWN). Консервативный first-open
free-space gate: **D+C+512MiB**, плюс отдельный запас iOS installation. При
versioned rootfs replacement с сохранением старого — **2D+C+512MiB**; не обещать
sparse savings. /data backup дополнительно 128MiB. Точные C, used blocks,
compressed transfer и peak host build storage измерить **до** device import.
Не добавлять swapfile/новую entitlement и не увеличивать RAM для обхода jetsam.

## Network и build environment

**G1–G3 offline:** оставить -nic none. Всё нужное уже в prepared rootfs; для
реального Xorg/Xterm/сохранения файла сеть не нужна. Host builder позже потребует
HTTPS к Debian archive/security или выбранному snapshot, verified metadata и
.deb blobs. Точные URLs/hashes/размеры входят в manifest до загрузки payload.
Installer/apt network не должен становиться неограниченным device bootstrap.
Новых аккаунтов, ключей, endpoints, payment или connections в этой задаче нет.

Если позже потребуется apt/Steam network: отдельный opt-in gate для существующего
libslirp backend, virtio-net с **romfile=** (не повторять PXE-ROM failure), guest
DHCP/DNS/CA/HTTPS, bounded connectivity evidence. Без hostfwd/SSH/VNC и без
притворства, что user networking — сетевой firewall. Никаких networking/security
settings сейчас не меняется. [QEMU network documentation](https://www.qemu.org/docs/master/system/devices/net.html).

Сейчас executor: uid1000, CapEff=0, NoNewPrivs=1; mke2fs/e2fsck/debootstrap/
mmdebstrap/system-QEMU не найдены. Есть только уже подготовленный user-mode QEMU
для BusyBox tests. Поэтому full image build здесь ещё не воспроизводится.
Будущему builder нужны: native ARM64 Linux либо pinned user-QEMU binfmt;
debootstrap/mmdebstrap, apt/gpgv/CA metadata trust, tar/xattrs/owner handling,
e2fsprogs с mke2fs/e2fsck/debugfs, compression/hash tooling и full-system
QEMU. Привилегированный builder либо проверенный rootless image pipeline с
корректными uid/gid/mode/xattrs — явное требование; не считать простую extraction
в host-owned directory полноценным POSIX image. Mac IPA gate лишь проверяет и
упаковывает inputs, не исполняет Linux maintainer scripts. Новый builder/подключение
здесь не создавался; отдельное решение до больших downloads/CI.

## Очерёдность реализации и test gates

| Gate | Конкретная реализация | PASS evidence / остановка |
| --- | --- | --- |
| G0: locked inputs | Rootfs dependency manifest/size budget, same-kernel ext4 closure, image/bootstrap builder | Package hashes/architecture/license manifest, loader ELF + all DT_NEEDED; ext4 mount probe; no payload fetch до concrete reviewed lock/budget |
| G1: persistent POSIX | Separate validated ext4 owner/provisioner + offline import + bootstrap chroot | uid/gid/chmod, symlink+hardlink, executable, rename, fsync and package DB survive two guest boots; same-size inode replacement/concurrent owners/space failures reject; legacy sentinel unchanged |
| G2: software desktop on host | Xorg modesetting + udev/VT + Openbox/xterm, no compositor, actual pinned system-QEMU | X connection, mapped real xterm, visible framebuffer changes and typed text; precise display geometry/stride, pointer+keyboard events; no fake Xvfb screenshot substitution |
| G3: Apple/device | Desktop route/software presenter/input + real SDK/native gate, parent-controlled IPA | Existing terminal/probe regressions PASS; owner opens/moves window, types ASCII/path in xterm, saves file, Stop, reopen and reads file; reports/physical screen + input correlated; memory/thermal/startup timing recorded |
| G4: software GL | Add Mesa SW packages/probe after G3 | Actual software renderer/glxinfo + simple redraw, measured RSS/CPU; no accelerated GPU claim |
| G5: future client | Full official ARM64 Steam/common assets + loader/library closure | Real client/CEF UI and navigation are separate task; no game performance promise |

Stop gate для нового режима: stop accepts once → stop session/Xorg/udev and all
writers → wait/reap → sync ext4 → unmount legacy, затем nested /dev/pts и
/dev/shm до /dev, остальные binds /proc,/sys,/run в reverse mount order →
sync/unmount ext4 → **only then** supervisor clean receipt over fd3 →
QEMU loop return + host fsync of both owned images. Если mount busy/timeout,
не выдавать clean PASS и не force-release locks. После normal Stop locks живут
до app exit, как сегодня. Rootfs corruption → отдельная recovery диагностика,
не auto mkfs/replace или fsck -y в startup path.

Три ближайших implementation changes следует разделить: **G0/G1 storage**, затем
**G2 rootfs desktop**, затем **G3 native UI/input/device**. На каждом этапе
terminal/probe остаются доступным rollback. CI отправляет только parent после
quota/payment/exact-SHA проверки. Ни rootfs, ни GUI, ни Steam ещё не реализованы
этим документом. Предложенный 4GiB бюджет/пакеты/config — проект, не benchmark.
