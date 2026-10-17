# Debian GUI implementation — 2026-10-17

This work continues the accepted Debian console at `338ee806` and device
acceptance documentation at `b8a943f`. The target is a real local VM desktop:
Xorg modesetting, Openbox, tint2, PCManFM, Mousepad and xterm. Software rendering
is the first stage. A Metal framebuffer presenter is not guest GPU acceleration.
Steam client/runtime compatibility remains a later task; the upstream ARM64
Steam client means x86 emulation is not an established client prerequisite.
This is Debian, not SteamOS.

The native Desktop route and separate GUI transport/staging recipe are now
implemented. **The production payload is blocked**, not published or installable:
the exact Alpine module bytes are not materialized in this executor. Original
kernel GUI boots, Apple compilation, IPA and iPhone GUI remain NOT RUN.

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

Current offline suite: **272 tests,267 PASS,5 SKIP,0 failures/errors**. Skips
are explicit Swift executable checks (existing profile, pointer and desktop
input), user-QEMU BusyBox/PTY, and the original QEMU RCU source archive.
All37 overlay inputs,81 original source members,10 patched hashes and25 exact
copies validate. All81 original members also match the actual pinned Husk Git
blobs. The full source stage and native-recipe patch check pass. The new C
pointer function body compiles and runs against unit queue fixtures; this is
not a full QEMU/iOS compilation. Mandatory Apple checks remain NOT RUN.

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
256 MiB: **1342177280 bytes**. The same capacity is retained for the separate GUI v1 seed after clean
configuration and measured desktop use (about884MB allocated,458MB free).
It is not an automatic expansion of an existing user disk. Neither the
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

## Audit guard correction

Readonly review found that `test -z "$(dpkg --audit)"` discarded a failing audit
exit status when stdout was empty. The runner now captures stdout in a file,
records exit status immediately, and requires both status0 and byte-empty
output. Configure failure also blocks audit/acceptance. Three executable shell
regressions cover nonzero+empty stdout, successful but nonempty/newline/space
output, and configure failure. No fake dpkg success substitutes for VM evidence.

[Fresh acceptance after the fix](evidence/gui-audit-fix-20261017/receipt.json):
two private-copy real GUI boots43.556/37.786s, audit status0/empty file,
input/wheel/menu/save/reopen, two clean Stops/fsck; immutable seed unchanged.
Runner snapshots/digests match the corrected frozen source. Old receipts remain
historical. The seal gate binds the current runner hash, rejecting old results.
This remains host Debian6.12.107/QEMU10.0.13; Alpine/iOS acceptance is NOT RUN.

## Clean GUI seed and native Desktop route

Current immutable seed: `.work/gui-20261017/gui-seed-final-v4/seed/`.
It is prepared only from the exact retained lab snapshot above. A real offline
VM terminates all session writers, installs the current desktop scripts/config,
removes acceptance documents/history/recent-files/logs, clears the machine-id
for first production boot, runs normal dpkg configuration/audit and unmounts.
A NEW `e2image -ra` output omits unallocated stale blocks. Read-only fsck, UUID,
size, and actual in-image script bytes are checked. The accepted console disk
and immutable lab source are never changed. Full raw capacity is budgeted.

| Clean seed v4 | Value |
| --- | --- |
| Raw size |1342177280 bytes |
| Raw SHA-256 | `46fea0230963ca494a5adeef19f46668f559f77522e3b82215d5f543646b0791` |
| gzip size |270352431 bytes |
| gzip SHA-256 | `8deb611138ad0afe400669d4d615093fea567d0950f48f55c97d608446a61769` |
| GUI UUID | `b66e1c8d-9cbf-45a7-b97b-dcc8f68efca7` |
| Bundle image | `iDeckLinuxDesktop/gui-rootfs-v1.raw` |
| Mutable app disk | `Documents/iDeckDebianGUI-v1/rootfs-v1.raw` |

[Clean-seed evidence](evidence/gui-native-20261017/receipt.json) records two
fresh-copy boots, wheel evdev events in both directions, window move/resize,
keyboard typing/Mousepad save, reopen before writes after boot, a real right
click menu launching another xterm, two clean Stops and read-only fsck. The
800x600 menu scanout is retained. Original seed entry/exit hashes are identical.
**Both** host kernel and QEMU differ from the app: Debian6.12.107+deb13-arm64 /
QEMU10.0.13 versus original Alpine6.18.35-0-virt / iOS10.0.12-utm. This is host
GUI evidence and does not establish matching-kernel or iPhone GUI acceptance.

`LinuxDesktopView` presents the existing real Husk Metal framebuffer, with
landscape side controls, hardware keyboard, software keyboard, arrows/function
keys, Ctrl/Alt/Shift/Super, right click and scroll. Normal graphical text goes
to QEMU keyboard events. Serial recovery is a separate explicit panel. The
first text implementation supports the US layout and4096 ASCII characters per
paste; an unsupported Unicode paste is wholly rejected, with a visible message.
Unicode/IME/clipboard support is not claimed. Hardware left/right modifier
ownership is paired and all held keys/buttons release on focus/background,
view cancellation/removal and Stop. Input C/BQL calls run on a dedicated queue.
Stop normally follows releases but has an independent250ms control fallback if
the input queue stalls; it never forces QEMU teardown.

`LinuxGUIProfile` validates a separate versioned profile, original kernel hash,
bounded initrd/profile reads, ext4 UUID/features/size, and streamed seed digest.
The first copy needs raw capacity plus512MiB reserve. Existing GUI disks reopen
by mutable filesystem identity and remain locked through process exit. The
accepted Debian console seed/path is separate. One VM/process, same retained
QEMU owner thread and existing Stop/fsync guards remain unchanged. No cleanup,
unregister, unlock, user disk reset, resize or reseed is added.

Production PID1 explicitly loads the exact original virtio GPU/input/evdev and
ext4 closure, uses udev/DRM/VT, private Xauthority, root Xorg and UID1000 clients,
no network and local X sockets. It enables serial recovery/Stop before X
readiness; only a tested X connection and mapped clients emit GUI READY.
Unexpected desktop exit leaves recovery/Stop available. Session writers must
terminate and mounts unmount in reverse order before the clean receipt.
These production-script behaviors still require the original-kernel VM gate.

## Production input blocker and remaining gates

Missing local bytes: original `boot/modloop-virt`,17670144 bytes, SHA-256
`f969d12c8e23b486c8df651f04a4a9767f32fee16aed385c23462c31ea6cb47b`,
from the locked official Alpine netboot archive. Parent reports a separately
verified copy, but parent filesystem paths/file IDs are not local paths here.
A direct scan of the original kernel did not produce a readable configuration;
VT support is not established here. Actual DRM/VT/matching-kernel checks remain.

Observed transfer failures (no endless retries, unknown binaries or live token
requests): official CDN `403 CONNECT tunnel failed`; Library helper
`hosted apps tools/list request failed: network`; Library prepare-materialize
returns `workspace_path:null`; Drive raw archive exceeds its268435456-byte
limit (HTTP413); the supported streamed file-reference GET fails with URLError;
Drive inline modloop request returns `Transport closed`. No `download_file`
tool/command is exposed here. No credentials or signed URLs appear in evidence.

An alternative input is the exact extracted tree: four `.ko` files and three
metadata files (~1.99MB), plus manifest, as already pinned by
[local-debian-ext4-modules.json](evidence/local-debian-ext4-modules.json).
`gui_bootstrap.py` compares those complete metadata/module identities against
the accepted original closure, then rechecks every byte/ELF/vermagic and real
dependency order. A self-asserted modloop digest cannot bless other modules.
The standalone-modloop provenance may differ, while exact content must match.

Next commands, only after those actual module bytes arrive:

```sh
python3 experiments/linux-guest/tools/gui_bootstrap.py \
  --modules .work/gui-20261017/alpine-modules \
  --output .work/gui-20261017/desktop-bootstrap
python3 experiments/linux-guest/tools/gui_gate.py \
  --seed .work/gui-20261017/gui-seed-final-v4/seed \
  --bootstrap .work/gui-20261017/desktop-bootstrap \
  --cache .work/gui-20261017/cache \
  --lock experiments/linux-guest/ipa/gui-inputs.lock.json \
  --output .work/gui-20261017/alpine-gui-acceptance
python3 experiments/linux-guest/tools/seal_gui_payload.py \
  --seed .work/gui-20261017/gui-seed-final-v4/seed \
  --bootstrap .work/gui-20261017/desktop-bootstrap \
  --acceptance .work/gui-20261017/alpine-gui-acceptance \
  --modules .work/gui-20261017/alpine-modules \
  --output .work/gui-20261017/sealed-gui
```

The gate uses two private-copy system-QEMU boots with original kernel/initrd,
all real GUI/input/menu/package/persistence checks, two Stops/fsck and immutable
seed checks. The seal helper requires these exact successful reports and
bindings to current source/package/seed/bootstrap identities. It emits a new
reviewable lock and deterministic gzip-in-tar transport; it never uploads or
modifies the committed lock. Retain original raw/gzip, module manifest and the
small `sealed-gui/rebuild-inputs` files for exact offline replay. `gui_bundle.py prepare` takes a new combined seed-input directory containing these four files.

Current [gui.lock.json](ipa/gui.lock.json) is deliberately `blocked`, with no
invented asset hashes. CI fails before Apple/native tool setup or private fetch.
After a reviewed seal, copy the exact lock, refresh overlay input hashes and
review/tests before parent coordinates private Release transfer and the one
approved Apple build. The transport is independent from the accepted Debian
console lock: HTTPS-only token-scope/redirect guards, exact hashes/sizes,
no links/traversal, bounded gzip/raw restore, low-space checks, independent
written-file verification, Xcode prebuild stage and IPA packaging verification.
IPA hashing streams1MiB chunks too. The iPhone importer still copies a verified
raw Xcode resource; no streaming gzip-on-iPhone importer is claimed.

Apple compilation/full native link, IPA/device GUI, guest GPU acceleration and
Steam are NOT RUN. CI remains parent-controlled and was not dispatched here.

The exact source of systemd's chroot override is
[upstream running_in_chroot](https://github.com/systemd/systemd/blob/v257/src/basic/virt.c#L846-L876).
`SYSTEMD_IN_CHROOT=0` is used only for real VM udev startup/trigger/settle,
not to bypass dpkg package configuration. Modesetting options follow the
[Debian driver manual](https://manpages.debian.org/trixie/xserver-xorg-core/modesetting.4.en.html)
and were exercised in the actual KMS server.
