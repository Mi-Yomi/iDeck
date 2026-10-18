# Future iOS Steam integration checklist

This is an implementation checklist, not an enabled iOS route or an Apple test
result. Keep the accepted Terminal, Debian console, Desktop, GUI payload/Release
and existing user disks unchanged. Current runtime/UI outcomes belong in
`HANDOFF.md`; this document does not promote a host result to iPhone success.

## Requested game storage and optimization — 2026-10-18

The owner now requests local game installation and use of available iPhone
internal storage. This expands the earlier client-only experiment; it does not
authorize purchases or acceptance of account/game agreements. Nothing below is
an enabled phone feature or a measured game-performance result. Run18 separately
verified two short native ARM64 XGalaga launches with keyboard gameplay and clean
exit; Steam/Proton, audio, FPS and iPhone execution remain unverified.

`LinuxDesktopDisk.Specification.validate()` currently caps a raw ext4 image at
4 GiB. GUI and Debian profiles bind the image size, UUID and filesystem geometry
to their seeds, and `LinuxTerminalSession` owns that disk through Stop. Merely
raising the cap or truncating an existing image would leave the filesystem and
profile contracts inconsistent. The Steam host's 12 GiB qcow2 is a different
contract and cannot be copied into the accepted iOS raw-disk route.

For the separate Steam route, keep the game library on a persistent app-owned
disk in internal storage, outside temporary/cache directories. Choose its size
from actual available storage, leaving an explicit reserve for iOS and updates;
never allocate the phone's advertised total capacity or treat RAM as disk space.
Use Apple's [important-usage capacity API](https://developer.apple.com/documentation/foundation/checking-volume-storage-capacity)
for user-requested downloads, handle missing/error results, and recheck before
allocation. A preflight number cannot reserve storage against other apps.
The app must handle allocation/write failures without replacing an existing
library, report remaining space, and preserve the same owner/clean-Stop contract.
Sparse apparent size must not be reported as physically available storage.

Implementation requires a separate persisted Steam disk specification and
guest filesystem initialization/growth for that exact disk. New-disk creation
must be atomic; existing disks must reopen with their saved size/UUID, never be
silently shrunk, reformatted or resized at every boot. Test interrupted creation,
low space, competing owners, clean Stop/reopen and game-file persistence before
enabling the route. Existing GUI/Debian paths remain unchanged.

For Windows games, inspect the actual ARM64 compatibility stack before choosing
dependencies. [Valve Proton](https://github.com/ValveSoftware/Proton#arm64-builds)
documents ARM64 builds; [FEX](https://github.com/FEX-Emu/FEX) supplies x86
translation. Prefer the compatible Steam-delivered runtime over an unrelated
system build. The read-only `tools/steam_game_preflight.py --steam-root PATH`
inventories default-library Proton candidates, local FEX binaries, Vulkan ICD
manifests, render nodes and known Steam Runtime launcher-service locations without
reading account files or launching anything. It follows runtime symlinks only
within their installation root and reports the resolved ELF architecture.
Run19's read-only inventory found only an x86-64 launcher service (ELF machine
62) beside the ARM64 client (183), with no Proton/FEX candidates or Vulkan ICD.
Adding that x86-64 service to PATH would not provide a native ARM64 runtime.
This inventory does not establish why the client UI stalls. The matching game
runtime still needs installation and execution checks before game acceptance.
Presence alone proves neither execution nor GPU acceleration. External Steam
libraries need separate inspection. Verify an authorized game's actual renderer,
input, frame timing, repeated launches and saved data on the physical iPhone;
host QEMU software-rendered Steam UI does not satisfy these checks.

An official ARM64 client runtime was cached and statically inspected on Oct18:
[Valve steamrt3c build3c.0.20260824.257593](https://repo.steampowered.com/steamrt3c/images/3c.0.20260824.257593/).
The 52,436,064-byte `steam-runtime-steamrt-arm64.tar.xz` has SHA256
`2f2be461b6a4360828e200e1644e18cd957eedc36a38e5a1e13a39276320b6e2`, matching
Valve's same-origin SHA256SUMS (not a detached signature). Its launcher service,
wrapper and bwrap have ELF machine183. It was not installed or executed, and
differs from the client's bundled x86 runtime3c.0.20261007.263964. Compatibility
is unverified. This client runtime is not a complete tested Proton/game stack.
The archive remains outside Git; sanitized receipt: `evidence/steam-local-arm64-20261017/runtime-arm64-static`.

The host runner accepts an explicit `--experimental-memory-mib 2560` control
after measured guest memory pressure; its default remains the pinned 1536 MiB.
Receipts distinguish the profile budget from the effective QEMU budget. Run20
measured direct reclaim and allocation stalls without a kernel OOM kill. This
motivates a comparison, not an iPhone RAM recommendation or a verified UI fix.

## Guest inputs and delivery

- [ ] Start a separate Steam asset/profile contract and permanent disk identity.
  Preserve `ipa/gui.lock.json`, `ipa/gui-inputs.lock.json`,
  `ipa/desktop-rootfs.lock.json`, `ipa/desktop-kernel-source.lock.json` and the
  accepted `gui-rootfs-v1.raw` as verified read-only inputs. The host qcow2 overlay
  is not an iOS-ready raw seed; `LinuxDesktopDisk` currently validates raw ext4.
- [ ] Use the production Alpine `vmlinuz-virt` pinned by the GUI lock, SHA-256
  `47970e0ee0478fe5c60824a89f162d5a353fa29466e5d3bddb0f9c506f1ed756`, and exact
  `vendor/alpine-3.24.1-aarch64/modloop-virt`, SHA-256
  `f969d12c8e23b486c8df651f04a4a9767f32fee16aed385c23462c31ea6cb47b`.
  Preserve merged-/usr, virtio block and exact ext4 modules. Networking adds the
  verified `failover` → `net_failover` → `virtio_net` closure.
- [ ] Carry `guest/steam/namespace-check.py`, `guest/steam/ideck-steam`,
  `guest/steam/install-cached.py`, `tools/steam_client.py`,
  `ipa/steam-client.lock.json` and `ipa/steam-dependencies.lock.json` through
  `tools/prepare_steam_bootstrap.py`. Its existing builder includes all files in
  `guest/steam`; retain exact input hashes in the build receipt.
- [ ] Adapt the **host-only** bootstrap before an iOS user-disk route. The current
  `/ideck-steam-init` requires `ideck.steam_experiment=1` and
  `ideck.steam_disk_grow=1`, then resizes a new disposable overlay. Do not apply
  that growth path automatically to an existing iOS disk. Preserve the original
  `guest/gui/ideck-desktop-init` Stop function and separate control channel.
- [ ] Create a separate Steam asset lock/sealer and staging validation. Extend
  `tools/stage_husk.py`, `husk/overlay.lock.json`, its reviewed patch series,
  `ipa/project.json`, `ipa/package_probe.py` and `ci/build_linux_probe_ipa.py`
  only in the future Steam change. Existing GUI checks remain required. Pin an
  accessible private asset URL/size/digest for CI; a local E: path is not delivery.

Current separately built IPC bootstrap, not an accepted iOS payload:

| Item | Identity |
| --- | --- |
| Local file | `E:\Freddy Fazbear\iDeck.work\steam-arm64-experiment-20261017\bootstrap-ipc-20261017\initramfs-steam.gz` |
| Size | `11665437` bytes |
| SHA-256 | `6a0081d76fedbb38b72e705334513313093b46e701907ed8b6d516640978df7f` |
| Namespace helper SHA-256 | `96c929eafefb2f76aa7751fb1869baa6def54e5e31be2a0e6620a486bca64b0d` |
| Receipts | Same directory: `bootstrap.json`; committed copy in `evidence/steam-ipc-20261017/bootstrap.json` |

The archive preserves the accepted GUI initramfs prefix and original Stop bytes;
its input receipt includes unchanged namespace-helper bytes. Run8 began booting
this new archive but was deliberately stopped before GUI readiness or commands.
Full boot/dependency installation/Steam validation of this archive is **NOT RUN**.
The previous namespace archive was booted in run6; do not transfer that acceptance
to this new archive. See `STEAM-IPC-HANDOFF.md` for current host limitations.
The helper itself passed actual host-guest UID1000
user/mount and user/mount/PID/private-proc preflights; see
[STEAM-NAMESPACES.md](STEAM-NAMESPACES.md). These are separate assertions.

## Client, dependencies and services

- [ ] Preserve the official client lock: 17 ZIPs, 360,938,891 downloaded bytes,
  channel `steamdeck_publicbeta`, initial version `1792192922`. A subsequent
  Valve self-update is separate from that pin and needs its own runtime receipt.
  Keep Valve client bytes out of Git, app payloads and Releases until the owner
  has approved the distribution path and the applicable terms permit it. No
  account/password/token publication or automated acceptance of agreements. The
  owner's later game request permits local game checks; the two native XGalaga
  runs do not establish Steam/Proton game compatibility.
- [ ] Install the exact 45 additional ARM64 Debian packages in
  `ipa/steam-dependencies.lock.json` (18,238,048 download bytes), preserving all
  341 existing GUI package versions. `tools/steam_dependencies.py` records the
  authenticated index and ELF-derived closure, including NSS/NSPR, ALSA/Pulse,
  PipeWire, GTK2, IBus, SDL2, OpenAL, NetworkManager client library, VA/VDPAU,
  libssh2 and nghttp2. The new lsof/liblsof0/libtirpc3t64/libtirpc-common closure
  supplies a real client TCP peer-identity dependency; guest install and its
  effect on the first timeout must be assessed from the current local receipts. A library's presence does not prove its service/device.
  Require both `dpkg --audit` exit 0 and empty output, plus actual loader checks.
- [ ] Keep UID/GID1000, `HOME=/home/ideck`, `DISPLAY=:0`,
  `XAUTHORITY=/run/user/1000/Xauthority`, `XDG_RUNTIME_DIR=/run/user/1000`, working
  X11 and a session D-Bus. Launch only through the namespace correction and
  ordinary-user launcher. Both preflights must pass; keep CEF sandbox enabled.
- [ ] Preserve the supported `-cef-force-sandbox`: Valve's interrupted-init
  sentinel otherwise silently enables sandbox fallback. Verify actual helper
  arguments and sandboxed child state, not just launcher intent. Do not remove
  the sentinel/cache or use sandbox bypass flags.
- [ ] Review `guest/steam/shm-recovery.py` separately before any device feature.
  It is an explicit host diagnostic recovery with same-boot manifest/hash,
  process/fd/map and exclusive-launcher checks, never automatic live-memory
  cleanup. Repeated stream allocation/initial IPC failure remains unresolved;
  recovery alone is not its fix. Host tracing/ptrace tools are not app dependencies.
- [ ] Replace the host cache delivery assumption with an explicit phone path.
  `install-cached.py --private-qemu-cache` depends on the host runner's loopback
  HTTP cache at guest address `10.0.2.2`; that server does not exist automatically
  on iPhone. Prefer the pinned official HTTPS downloader with working guest CA
  certificates/DNS or a separately reviewed on-device verified transfer. Do not
  turn the private cache exception into unrestricted HTTP fallback.

## Native runtime, CPU and network gates

The user authorizes a larger host RAM budget and plans to use GetMoreRAM on
iPhone when needed. The host runner accepts an explicit 4096 MiB comparison;
the pinned default remains 1536 MiB. This also increases the guest's default
tmpfs capacity, so it does not independently isolate RAM from shared memory.

[GetMoreRAM](https://github.com/hugeBlack/GetMoreRam) enables Increased Memory
Limit for the selected App ID and requires reinstalling the signed application.
Apple documents this [entitlement](https://developer.apple.com/documentation/bundleresources/entitlements/com.apple.developer.kernel.increased-memory-limit)
for supported devices. Before selecting a larger iPhone guest budget, verify
the entitlement in the actual signed application and measure available process
memory on that device, including QEMU/display/TCG overhead. The tool alone
does not establish an available byte count or change the existing iOS profile.

- [ ] Build and record the actual iOS `libqemu-aarch64-softmmu.dylib` from Husk
  `0695248f491cda877f7969d1f0cc89aeede1482e` and QEMU `10.0.12-utm`, using
  `ipa/native-sources.lock.json`. Keep its pinned libffi, GLib, pixman,
  libucontext, libslirp 4.9.1, epoxy/virgl and ANGLE recipe dependencies. Retain
  `libANGLE-shared.dylib`, `libhusk_rppairing.a`, StikJIT and existing packaging,
  signing/JIT/SideStore behavior. Native library presence is not a guest GPU claim.
- [ ] Add a **Steam-only** CPU gate. `LinuxGuestProfile.swift` and
  `LinuxTerminalProfile.swift` currently require Cortex-A72; GUI/Debian argument
  builders inherit that guard. Do not weaken accepted modes. The initial real
  client needs FEAT_LSE (`ldaddal`); A72 lacks it. A76/max source support exists
  in the pinned iOS QEMU, but the built iOS runtime must advertise the feature
  and execute `tools/steam_cpu_probe.py`'s original static probe correctly.
  See [STEAM-CPU.md](STEAM-CPU.md); host QEMU10.0.13 success is not that gate.
- [ ] Add explicit network opt-in only to the separate Steam profile. Verify
  actual iOS QEMU user networking/libslirp, `virtio-net-device`, DNS and HTTPS.
  The host reference `profiles/steam-host-experiment.json` uses IPv4 NAT,
  `10.0.2.15/24`, gateway `10.0.2.2`, DNS `10.0.2.3`, no port forwarding. Preserve
  `-nic none` in accepted modes. Reassess RAM, storage/import reserve and update
  headroom on the device; host 1536 MiB RAM/12 GiB virtual disk are not iOS budgets.

## Swift route, disk ownership and Stop

- [ ] Add an explicitly experimental `LinuxSteamProfile.swift` (proposed, not
  present) and separate route/asset directory. Review `LinuxGUIProfile.swift`,
  `LinuxDesktopProfile.swift`, `LinuxDesktopDisk.swift` and
  `LinuxTerminalSession.swift` together. Verify seed size/hash and free space,
  atomic first import, interrupted import/retry, ownership/dirty state and
  never-overwrite publication. A dirty disk produces a recovery error, never
  automatic recreation. Never permit two VMs or mount the seed writable.
- [ ] Reuse the real `LinuxDesktopView.swift`, `LinuxDesktopInput.swift`,
  `LinuxDesktopInputState.swift` and `LinuxDisplayPointer.swift` only after the
  route is wired to the runtime. Preserve modifier release, right click,
  scrolling and input liveness around Stop. Do not promise a working Steam
  button before runtime validation; retain a real return-to-Desktop path.
- [ ] Preserve `LinuxConsoleLifecycle.swift`, `LinuxTerminalSession.swift`,
  `LinuxTerminalDiagnostics.swift` and `docs/qemu-owner-lifetime.md`: guest
  writers stop, sync/unmount is acknowledged, then QEMU loop completion and host
  fsync are checked. A host fsync failure is permanently failed even on repeated
  finalization. Timeout/forced termination is never clean. Loop return does not
  prove block-backend/RCU cleanup: retain the same native QEMU owner thread and
  exclusive disk ownership until application exit. Preserve result JSON/Markdown
  export and existing crash logs, pairing and JIT paths.

## Required future validation

- [ ] Run the mandatory Apple Swift executable/runtime regressions through
  `ci/check_linux_guest_profile.py` and `tools/typecheck_source.py`, including
  `ios/tests/ConsoleLifecycleChecks.swift`, `DesktopDiskChecks.swift`,
  `GUIProfileChecks.swift`, `TerminalChecks.swift`, `DiagnosticsChecks.swift`,
  `DesktopInputChecks.swift` and `DisplayPointerChecks.swift`; add corresponding
  Steam-only profile/import/network/CPU cases. Keep Python ownership/lifetime
  and bootstrap regressions passing.
- [ ] Compile/link the exact new Apple target, validate staged hashes and IPA,
  then test on device: CPU probe, namespace preflights, real client window,
  Big Picture, persistence, Stop, app exit/reopen, recovery diagnostics and
  unchanged accepted modes. **Steam Apple build, IPA and iPhone runtime are
  NOT RUN by this branch's host work.** No Codemagic run or settings change is
  authorized by this checklist. UI software rendering is not GPU acceleration
  or evidence of playable game performance.
