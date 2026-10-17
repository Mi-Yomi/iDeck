# Debian GUI implementation — 2026-10-17

The real local desktop now passes two system-QEMU boots with the **original
production Alpine6.18.35-0-virt kernel**: Xorg modesetting/KMS/VT, Openbox, tint2,
PCManFM, Mousepad and xterm. The native Desktop route and exact GUI payload are
ready for Apple review. **Apple compilation, native link, IPA and iPhone GUI
are NOT RUN.** Host QEMU10.0.13 differs from iOS10.0.12-utm.

This is Debian13 ARM64 with software rendering. Metal presents the framebuffer;
it does not establish guest GPU acceleration. Steam, Big Picture and games are
separate later gates. The upstream ARM64 Steam client means x86 emulation is
not an established client prerequisite. Debian is not SteamOS.

## Original-kernel evidence

[Acceptance](evidence/gui-alpine-20261017/acceptance.json),
[receipt](evidence/gui-alpine-20261017/receipt.json),
[actual menu/window scanout](evidence/gui-alpine-20261017/boot2/desktop-menu.png).

Both fresh-copy runs passed actual X connections, mapped clients, UID1000,
virtual keyboard typing/Mousepad save, pointer move/resize, tablet evdev wheel
±1, right-click menu launching another xterm, and reopening saved documents
before any writes on boot2. Each ended with an independent control Stop,
terminated writers, reverse unmount, clean receipt and read-only `e2fsck -fn`.
Normal `dpkg --configure -a`, explicitly successful `dpkg --audit` with byte-empty
stdout, and the exact341-package installed manifest passed in both runs.

| Original-kernel host run | Seconds | QEMU sampled peak VmHWM bytes |
| --- | ---: | ---: |
| Boot1 |29.489 |932151296 |
| Boot2/persistence |27.410 |922447872 |

Timings cover the host acceptance run, not pure kernel boot or iPhone latency.
Memory numbers are Linux-host QEMU measurements, not iOS Jetsam or guest-process
peaks. Guest RAM1GiB,4vCPU,256MiB TCG/no swap remained unchanged.

Kernel SHA-256 stays
`47970e0ee0478fe5c60824a89f162d5a353fa29466e5d3bddb0f9c506f1ed756`.
The original virtio GPU/input modules and exact evdev stay in the accepted
probe initramfs; its test init is not the GUI boot entrypoint. Matching ext4
modules come from the verified vendor modloop, with the accepted metadata,
vermagic, hashes and real dependency order. DRM/VT are now exercised, not inferred.

The first original-kernel attempt exposed a real first-start bug: dbus-uuidgen
rejects an existing zero-byte machine-id placeholder. PID1 now removes only
that empty regular placeholder, rejects a symlink, and preserves nonempty IDs.
The two successful boots verify the same generated ID hash. The failed attempt
was never counted as GUI success; its serial recovery/control Stop/clean unmount
and subsequent read-only fsck also passed. Logs are retained under
[evidence/first-start-recovery](evidence/gui-alpine-20261017/first-start-recovery).

Previous Debian-kernel/QEMU preparation evidence remains in
[gui-host-20261017](evidence/gui-host-20261017/receipt.json),
[gui-native-20261017](evidence/gui-native-20261017/receipt.json) and
[gui-audit-fix-20261017](evidence/gui-audit-fix-20261017/receipt.json).
Those host preparation kernels were never substituted for the production kernel.
The audit fix captures stdout to a file and checks status0 AND a byte-empty file;
`test -z "$(dpkg --audit)"` is not used as an acceptance guard.

## Separate authenticated build inputs

[gui-inputs.lock.json](ipa/gui-inputs.lock.json) remains separate from the
accepted console locks. It authenticates one Debian trixie/main InRelease with
the accepted GPG signers/freshness, arm64/amd64 by-hash indexes, exact versions,
architectures, sizes and .deb hashes. Offline replay reruns the APT solver and
compares the entire closure. No security metadata is mixed into this schema.

| Closure | Packages | Download bytes | Declared installed bytes |
| --- | ---: | ---: | ---: |
| ARM64/all desktop |341 |175210844 |736205824 |
| amd64 QEMU/e2fsprogs/kmod |94 |36998708 |172119040 |
| Provision-only Debian kernel |1 |92902468 |177777664 |

All package maintainer scripts, including sysusers/udev, ran in a real disposable
ARM64 system VM from a read-only offline .deb volume. Bootstrap unpack is
followed by normal configuration, empty successful audit and exact installed
manifest. No maintainer script or dpkg success was fabricated. Temporary standard
policy-rc.d prevents provisioning service autostart and is then removed. Every
installed copyright file is present; the earlier notices manifest is retained.

Official host tools are extracted locally from authenticated .debs, without host
system installation. An additional10-package/4010988-byte official amd64 closure
provided unsquashfs; its signed-index provenance/pins are retained in
[module-tools.lock.json](evidence/gui-alpine-20261017/module-tools.lock.json).
The vendor modloop bytes came through parent commits1d5f743/831b66c, and their
size17670144/SHAf969d12...6cb47b were independently checked after fast-forward.
The vendor `.gitattributes` prevents the repository's global text/EOL rule from
rewriting those binary bytes. Parent/index/worktree bytes match exactly.

The Debian6.12.107 provision kernel was only a preparation instrument. The
production suffix is built by `gui_bootstrap.py` from original kernel/probe bytes
and the accepted Alpine module closure. `gui_gate.py` then executes two real
original-kernel boots on a NEW private seed copy, checks persistence/Stop/fsck,
source/input identities and immutable seed entry/exit hashes.

## Clean seed and sealed payload

The measured extracted tree was714733572 bytes. The initial tree plus512MiB
workspace, rounded to256MiB, selected **1342177280 bytes**, retained after real
configuration and measurements (about884MB used/458MB free). The accepted
512MiB console disk is not reused or expanded.

Current immutable seed: `.work/gui-20261017/gui-seed-final-v4/seed/`.
A real offline VM stopped all writers, installed the current desktop scripts,
removed acceptance documents/history/recent files/logs, cleared machine-id for
first boot, ran normal configure/audit and unmounted. A NEW `e2image -ra` output
omits unallocated stale blocks. Header/UUID/script bytes and read-only fsck pass.

| GUI v1 artifact | Value |
| --- | --- |
| Raw bytes |1342177280 |
| Raw SHA-256 | `46fea0230963ca494a5adeef19f46668f559f77522e3b82215d5f543646b0791` |
| gzip bytes |270352431 |
| gzip SHA-256 | `8deb611138ad0afe400669d4d615093fea567d0950f48f55c97d608446a61769` |
| UUID | `b66e1c8d-9cbf-45a7-b97b-dcc8f68efca7` |
| Production initramfs bytes |11319304 |
| Production initramfs SHA-256 | `f8d8f4cc92f3f8d49e68adb90ab50d901c54f115d6134ae7030526fdee3de8b4` |
| Sealed tar bytes |292034560 |
| Sealed tar SHA-256 | `4b4b0bb1f75d5b662a8c1d866f482329449ee4d52d181e585ef4964a3540bbdb` |

[gui.lock.json](ipa/gui.lock.json) is now **ready**, bound to the exact original-
kernel acceptance report and asset bytes. This is the current payload contract;
earlier preparation receipts' false/not-tested flags describe their pre-gate
state. `seal_gui_payload.py` rejects stale/missing/failed reports, wrong kernel,
seed/initrd/package/source bindings and changed machine-id across boots.

The archive is outside git at
`.work/gui-20261017/sealed-gui/ideck-debian-gui-v1.tar`. Exact offline replay
produced the identical tar. Seal/replay/restore/staged bundles all verify their
five assets: kernel, production initrd, raw GUI root, desktop profile and notices.
The independent GUI helper enforces HTTPS/token scope, hashes/size, safe flat
archive members, bounded gzip/raw restore and low space. Xcode and IPA packaging
both verify the GUI assets. Large IPA hashes stream1MiB chunks too.

Private Release upload is **not complete**: existing gh GraphQL and REST reads
return `Forbidden`; no Release upload action is exposed here. No credentials were
read or changed. [GUI-PAYLOAD-DELIVERY.md](GUI-PAYLOAD-DELIVERY.md) gives the exact
validated artifact/checksum, parent upload step and future private asset URL
configuration. Parent must complete that transport before the single Apple build.
The iPhone importer copies a verified raw Xcode resource; no streaming gzip
importer on iPhone is claimed.

Retain the current seed raw/gzip, sealed tar/checksum/lock, exact modules manifest,
authenticated package cache and `sealed-gui/rebuild-inputs` small files. Old
private VM/candidate copies were pruned after their evidence was retained. The
immutable original lab snapshot and current production acceptance VM remain.

## Native Desktop and lifecycle

`LinuxDesktopView` displays the real existing Husk Metal framebuffer. It has
landscape side controls, hardware/software keyboard, special/function keys,
Ctrl/Alt/Shift/Super, right click, wheel/two-finger scroll and serial recovery.
Graphical text goes to QEMU keyboard events. First soft text support is the US
layout/ASCII, up to4096 characters; unsupported Unicode paste is wholly rejected.
Unicode/IME/clipboard support is not claimed. Hardware left/right modifier
ownership and key/button releases are paired through focus/background, cancel,
view removal and Stop. Input C/BQL calls use a dedicated queue. Stop normally
follows releases and has a250ms independent control fallback for a stalled queue.

The app bundle is `iDeckLinuxDesktop/gui-rootfs-v1.raw`; the mutable disk is
`Documents/iDeckDebianGUI-v1/rootfs-v1.raw`. The separate profile checks original
kernel identity, bounded profile/initrd reads, streamed seed hash, ext4 UUID,
geometry/features and disk ownership. Import budgets raw capacity plus512MiB
reserve. Existing disks reopen by mutable filesystem identity, without reseed,
resize or replacement. Accepted console/Terminal/Probe paths remain separate.

One VM/process, the same retained QEMU owner thread with non-polling NSCondition,
and host disk lock through process exit remain unchanged. No qemu_cleanup,
unregister or unlock is added. Production PID1 uses udev, root Xorg on VT1,
UID1000 dbus session, private Xauthority, local X socket/-nolisten tcp, fixed
800x600/depth24, AccelMethod=none/ShadowFB/SWcursor and `-nic none`.

Serial recovery/Stop is enabled before X. GUI READY requires an actual X
connection and mapped XTerm/Pcmanfm/Mousepad windows. GUI failure keeps recovery
available. All writers terminate and mounts unmount in reverse order before
CLEAN_UNMOUNT. Software modesetting follows the
[Debian manual](https://manpages.debian.org/trixie/xserver-xorg-core/modesetting.4.en.html).
The real-VM udev chroot override follows
[upstream systemd v257](https://github.com/systemd/systemd/blob/v257/src/basic/virt.c#L846-L876).
It is not used to bypass package configuration.

## Replay and remaining device gate

```sh
# Existing retained cache and vendor modloop; supply official unsquashfs.
python3 experiments/linux-guest/tools/desktop_modules.py \
  --modloop experiments/linux-guest/vendor/alpine-3.24.1-aarch64/modloop-virt \
  --unsquashfs /path/to/official/unsquashfs --out /new/alpine-modules
python3 experiments/linux-guest/tools/gui_bootstrap.py \
  --modules /new/alpine-modules --output /new/desktop-bootstrap
python3 experiments/linux-guest/tools/gui_gate.py \
  --seed .work/gui-20261017/gui-seed-final-v4/seed \
  --bootstrap /new/desktop-bootstrap --cache .work/gui-20261017/cache \
  --lock experiments/linux-guest/ipa/gui-inputs.lock.json --output /new/gui-gate
```

All output paths must be new. `gui_bundle.py prepare` replays the already sealed
lock from a combined seed-input directory containing raw/gzip and the two small
rebuild files. The exact modules manifest must be retained because its provenance
is locked too. Its offline rebuild, restore and isolated staging were exercised.

Current regressions:274 tests,269 PASS,5 explicit toolchain SKIP. The full pinned
source stage and native recipe patch check pass. Swift executable checks and
Apple SDK/UIKit/full QEMU link remain NOT RUN here. These mandatory Apple checks
are wired into the existing reviewed workflow; no stubs replace them.

Parent coordinates Release delivery, review, fresh free-quota/paid-OFF preflight
and the single Apple build. Device acceptance must then show real windows and
apps, launch/edit/save/reopen, move/resize/right click/scroll, focus-release and
Stop on two fresh app launches with persisted files. Confirm actual screen and
input on iPhone before calling the device GUI accepted. CI was not dispatched.
