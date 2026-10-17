# Debian GUI implementation — 2026-10-17

This work continues the accepted Debian console at `338ee806` and device
acceptance documentation at `b8a943f`. The target is a real local VM desktop:
Xorg modesetting, Openbox, tint2, PCManFM, Mousepad and xterm. Software rendering
is the first stage. A Metal framebuffer presenter is not guest GPU acceleration.
Steam client/runtime compatibility remains a later task; the upstream ARM64
Steam client means x86 emulation is not an established client prerequisite.
This is Debian, not SteamOS.

## Measured host result

[Receipt and original logs](evidence/gui-host-20261017/receipt.json),
[actual scanout after reopening the file](evidence/gui-host-20261017/desktop-after-reopen.png).
The final offline preparation CLI completed with unchanged entry/exit source
hashes. All341 packages configured in the actual ARM64 system VM, including
systemd-sysusers and udev; normal configure, empty successful audit and exact
persisted package manifest passed. This resolves the earlier PRoot sysusers
assertion for host preparation without bypassing scripts.

Two final GUI boots passed: **38.882s /34.546s**, each including scripted
interaction and Stop. Both had actual Xorg/KMS, local X connection, mapped
Openbox/tint2/PCManFM/Mousepad/xterm, UID1000 clients and emulated keyboard/pointer.
Alt+left drag moved the xterm from82,105 to122,129; Alt+right resized556x316 to
598x342. The two virtual input devices need ordering time between modifier
press and mouse press in this automated harness. This is not a phone latency
benchmark. File creation and the editor launch command are typed into real
xterm through the emulated keyboard. Mousepad receives actual keyboard text
and Ctrl-S; its saved text is independently checked on disk. On boot2 both
files are checked before writes, then the existing file is opened in Mousepad.
Two independent control Stops, clean unmounts and read-only fsck passed.

A further **43.466s** boot passed the same interaction/Stop/fsck and actual
`ld-linux-aarch64.so.1 --list` checks for all **423 PT_INTERP executables**.
The inventory contains1133 AArch64 ELF files and3791 DT_NEEDED edges. One
standalone static residual is retained: the non-executable private
libsystemd-core DSO's reference to libsystemd-shared. No global private search
path or fabricated library was added. This is an actual executable-loader
resolution gate, not a claim to execute every DSO/plugin in every possible
future load context. The old minbase checker is unchanged.

| Final two-boot snapshot | Bytes |
| --- | ---: |
| Logical raw size |1342177280 |
| Used filesystem blocks |884133888 |
| Free filesystem blocks |458043392 |
| gzip level9 (measured host snapshot, not app payload) |400617549 |
| Raw+gzip+512MiB reserve |2279665741 |

Raw snapshot SHA-256:
`a32f7b9c0c59e651492811458e3a46667010eb4be54d07a79487e94c5e43ed06`.
gzip SHA-256:
`c1476f9e179b3dc5f6c8c3bbfce3e7e6e38351e4d914bc49aaa01b677a76b078`.
Streaming decompression count/digest matches the retained raw snapshot. It
contains acceptance files and post-install history/free-block contents; final
app seed preparation/size/profile remains a separate gate. No optimized
production transfer size is promised from this laboratory snapshot.

Builder individual peak RSS **810754048bytes**; maximum sampled host-QEMU
VmHWM: provisioning **1415208960**, GUI boots **826548224 /811683840**, loader
boot **828547072bytes**. These are host measurements, not iOS Jetsam or guest
process peaks. Guest RAM1GiB,4vCPU,256MiB TCG and no swap stayed unchanged.

All341 configured package copyright files are present, resolved within the
image and hashed in the notices manifest. The read-only rdump is only a
content/ELF extraction: its host ownership errors are not claimed as an inode
ownership audit. Actual client and saved-file UIDs were checked inside Linux.
The raw image itself, clean unmount and fsck are the filesystem evidence.

Final offline suite: **253tests,249PASS,4SKIP,0failures/errors**. Skips are
explicit Swift toolchain, user-QEMU BusyBox/PTY, original QEMU RCU source archive
and new Swift pointer execution, all absent in this restored workspace.
All30 overlay inputs,78 original source members,6 patched hashes and19 exact
copies validate. Apple checks/IPA/device and CI remain NOT RUN.

Local retained artifacts: `.work/gui-20261017/vm-final/` (current mutable lab
image), `host-gui-acceptance-2boots.raw` and `host-gui-acceptance.raw.gz` (exact
measured two-boot snapshot), authenticated `cache/`, `configured-elf-tree/`
and complete logs. Large artifacts are not in git or published to a Release.
Preserve them before moving to another execution environment.

## Separate authenticated inputs

[gui-inputs.lock.json](ipa/gui-inputs.lock.json) is deliberately separate from
both accepted `desktop-rootfs.lock.json` and `debian.lock.json`. It locks one
Debian trixie/main InRelease and its arm64/amd64 by-hash indexes. GPG validation
requires the existing accepted Debian archive signers, freshness <=90 days and
Valid-Until when supplied. Security metadata is not mixed into this lock.
Every package identity, architecture, pool path, size, digest and declared
Installed-Size is checked against those authenticated indexes. Offline replay
reruns the APT solver using only those indexes and compares the entire closure;
an authentic but incomplete subset is rejected. APT only simulates dependency
resolution on the host. It does not install or download packages.

| Input | Packages | Download bytes | Declared installed bytes |
| --- | ---: | ---: | ---: |
| ARM64/all GUI root | 341 | 175210844 | 736205824 |
| amd64 host QEMU/e2fsprogs/kmod closure | 94 | 36998708 | 172119040 |
| Provision-only Debian kernel | 1 | 92902468 | 177777664 |

All blobs have been downloaded and hashed in this cloud workspace. Guest
copyright/notices remain in the packages' `/usr/share/doc` trees. No package
maintainer script is executed on the host, and no host system package is
installed. The helper extracts authenticated tools into its new private output.

`gui_rootfs.py lock` creates a new lock with exclusive creation. `download`
verifies blobs; `verify` authenticates metadata and replays dependency resolution.
Mutable mirrors can remove pinned pool objects: preserve the authenticated cache.
The retained InRelease is dated 2026-09-12; expiry must be handled by a reviewed
repin, never by disabling freshness checks.

## Disposable system-VM preparation

[gui_vm.py](tools/gui_vm.py) requires an already complete offline cache. Missing
or corrupt input fails before a VM output directory is created. It pre-extracts
the guest packages to bootstrap dependency cycles, publishes actual archive
ownership into a new ext4 image using debugfs, then packages the original `.deb`
files on a separate read-only ext4 volume. The VM's actual ARM64 dpkg runs
`--unpack`, every maintainer script, `--configure -a`, an empty successful
`--audit`, and an exact installed-state/version/architecture manifest comparison.
The bootstrap `--force-depends --unpack` is followed by mandatory normal
configuration. No maintainer script is bypassed or rewritten to report success.
A temporary standard policy-rc.d prevents service autostart during provisioning;
it is removed after successful configuration. Udev is started during desktop boot.

The provision kernel is official Debian `6.12.107+deb13-arm64`, authenticated by
its `.deb` pin. Kmod resolves its real module dependencies, aliases, softdeps
and builtins; compressed modules are extracted without importing them into the
production Alpine module tree. This kernel is a **host preparation instrument**.
It is not a proposed replacement for the iPhone's pinned `6.18.35-0-virt` kernel.

The initial extracted tree measured 714733572 logical file bytes. Disposable
scratch capacity was calculated as extraction +512 MiB workspace, rounded to
256 MiB: **1342177280 bytes**. This is a provisioning capacity, not the final
app image size. Final used blocks, compressed transfer and memory measurements
must be taken after clean VM configuration and desktop acceptance. Neither the
old 512 MiB image nor the earlier unmeasured 4 GiB design is silently reused.
Preparation has a free-space guard that budgets full copies rather than sparse
savings and rejects existing output paths.

```sh
# From the repository root; retained cache is private, images stay out of git.
python3 experiments/linux-guest/tools/gui_rootfs.py verify --offline \
  --cache .work/gui-20261017/cache \
  --lock experiments/linux-guest/ipa/gui-inputs.lock.json
python3 experiments/linux-guest/tools/gui_vm.py \
  --lock experiments/linux-guest/ipa/gui-inputs.lock.json \
  --cache .work/gui-20261017/cache --output .work/gui-20261017/new-vm
python3 experiments/linux-guest/tools/check_gui_vm.py \
  --vm .work/gui-20261017/new-vm --output .work/gui-20261017/new-provision --provision
python3 experiments/linux-guest/tools/check_gui_vm.py \
  --vm .work/gui-20261017/new-vm --output .work/gui-20261017/new-desktop-1
python3 experiments/linux-guest/tools/check_gui_vm.py \
  --vm .work/gui-20261017/new-vm --output .work/gui-20261017/new-desktop-2 --persistence
```

The host script selects both ext4 volumes by UUID, not `/dev/vdX` enumeration.
It mounts proc/sys/dev, a new devpts instance, dev/shm, run and the offline
package volume explicitly. Stop terminates writers, waits, syncs, unmounts the
package volume and nested mounts in reverse order, then root and final sync.
Only then can the host-only clean marker be emitted. Failed runs retain logs
and must not be represented as clean outputs.

Xorg runs as root on VT1 with DRM KMS, modesetting/AccelMethod=none,
ShadowFB=true, SWcursor=true and depth24. It listens only on local authenticated
X sockets (`-nolisten tcp`). The session drops to UID/GID1000 with private
Xauthority and XDG_RUNTIME_DIR, then uses dbus-run-session. Readiness requires a
successful X connection and visible mapped XTerm, Pcmanfm and Mousepad clients.
The panel has launchers for all three. The recovery console uses the proven background getty/wait path, so the
PID1 Stop trap can interrupt its wait. The VM uses `-nic none`, 1GiB RAM,
4 vCPU and 256MiB TCG; no display stream or remote desktop server is involved.

`check_gui_vm.py` runs actual system QEMU, captures actual guest scanout and
injects actual emulated keyboard events. It also checks client UIDs, package
state, a typed/saved file, window movement/resizing and separate control Stop.
A second boot checks the existing file before any write. These checks are
separate from ordinary mocked input-trust unit tests; no mocked X server or
framebuffer probe substitutes for the GUI gate.

## Production input blocker and remaining gates

The restored cloud workspace had no earlier `.work`/rootfs/ext4-module outputs.
The committed probe bundle supplies the original kernel/initramfs and GPU/input
modules, but not ext4's complete production closure. The exact official Alpine
archive request returned `403 CONNECT tunnel failed`. Library located the
previously attached `modloop-virt` (metadata size17670144), but its current
supported download helper failed with
`hosted apps tools/list request failed: network`; no payload bytes were obtained
through that path. No alternate proxy/credential channel was used.

Minimal missing production input: unchanged `boot/modloop-virt` from
`alpine-netboot-3.24.1-aarch64.tar.gz`, SHA-256
`f969d12c8e23b486c8df651f04a4a9767f32fee16aed385c23462c31ea6cb47b`.
The existing `desktop_modules.py --modloop` enforces that pin. A trusted
unsquashfs and that exact file enable a new suffix retaining the original kernel.
GPU/input/evdev and ext4 module load/DRM/VT then need the same-kernel VM gate.

Until that input is available, the host outputs are **not app assets**. No GUI
payload lock, IPA staging, native Desktop chooser/controls or app disk path is
published. The reserved GUI UUID is `b66e1c8d-9cbf-45a7-b97b-dcc8f68efca7` and
future filename `gui-rootfs-v1.raw`; final profile/size and a separate Documents
path must be validated before integration. Existing Debian user disks must
never be reformatted, resized, reseeded or reused for this GUI profile.

Native overlay now pairs left-button release outside letterbox, cancellation,
app focus loss/background, view removal/size change and before Stop. A pure
production Swift transition model handles duplicate/stray transitions; an actual
10,000-cycle Swift check is mandatory in the Apple gate. Local pinned-source
restore/patch/hash checks pass; Swift/Apple/UIKit execution remains NOT RUN.
Native Desktop work still needs right click/scroll, actual text/special keys and
modifiers, plus integration with the verified GUI payload. Preserve the existing single VM/process owner thread retention,
disk lock through process exit, separate Stop socket and console/Terminal/Probe.
No qemu_cleanup/unregister/unlock workaround is authorized by this host gate.
Apple compilation/IPA/device GUI, guest GPU acceleration and Steam are NOT RUN.
CI remains parent-controlled and was not dispatched here.

The exact source of systemd's chroot override is
[upstream running_in_chroot](https://github.com/systemd/systemd/blob/v257/src/basic/virt.c#L846-L876).
`SYSTEMD_IN_CHROOT=0` is used only for real VM udev startup/trigger/settle,
not to bypass dpkg package configuration. Modesetting options follow the
[Debian driver manual](https://manpages.debian.org/trixie/xserver-xorg-core/modesetting.4.en.html)
and were exercised in the actual KMS server.
