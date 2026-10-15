# Direct Linux guest: bounded feasibility experiment

This branch advances the requested **real Linux kernel + Linux Steam + Big Picture on iPhone** route. It preserves the previous Playport/Madeira source snapshot and all existing CI workflows. It does not replace the application, provide an IPA, or claim an iPhone Steam session.

2026-10-16: [A separate native IPA build recipe](ipa/README.md) is now available
as `ideck-linux-probe-ipa`, alongside the ten-minute Swift source check. The
verified guest bytes are included in Git. The Apple run at 3a10400 passed the
Swift/profile/evidence gate, then stopped on an unused absolute link in the
QEMU archive; binary guest data also broke JSON reporting. These preparation
issues are fixed here. Native compilation/linking and an actual IPA are pending.

## Measured in this session

- Reconstructed all 2,023 source entries to the original declared Git tree. The transport repository and the reconstructed source have distinct identities; see `evidence/source-inventory.json`.
- Downloaded six binary packages selected by DroidDeck's pinned installer from Valve's official CDN. Size/SHA-256 verification passed. All 87 ELF files in these packages are AArch64, including `steam`, `steamwebhelper` and `libcef.so`. The client/helper require `/lib/ld-linux-aarch64.so.1`; this loader is not in those packages. Common assets, a complete glibc rootfs and runtime loading are still outstanding.
- Booted Alpine's actual AArch64 Linux 6.18.35 kernel under Windows QEMU/TCG. A source-built, static AArch64 program uses Linux syscalls and framebuffer ioctls/mmap. Two 800×600 frames match **every pixel**; Linux evdev captures confirm key press/release and absolute pointer coordinates/button press/release. No simulated kernel, display or input is used in this integration test.
- Verified the attached diagnostic WIP's 16 base / 18 patched source files and exact patch equivalence. It remains uncompiled and untested on a device.

The host control uses Windows QEMU 11.1.0 (`v11.1.0-12130-ge470268ff4`), **not** Husk's QEMU 10.0.12-utm. It cannot verify iOS JIT, Metal presentation, memory limits or game performance. The Alpine/musl probe is intentionally separate from the future glibc Steam system.

## Minimal configuration

| Component | First probe | Subsequent Steam experiment |
|---|---|---|
| Kernel / machine | Alpine 6.18.35 AArch64, QEMU `virt`, `cortex-a72`, 4 vCPU | Keep the proved machine shape first; select a glibc rootfs and audit its loader/dependencies |
| Memory | 1,024 MiB guest + 256 MiB TCG cache | Measure real available memory/jetsam before increasing |
| iOS execution | Husk119 JIT/self-test and QEMU split-WX allocator, still to integrate/test | Same, separately measure client/CEF footprint |
| Display | `virtio-gpu-pci` software scanout, 800×600 | Xorg modesetting + software Mesa; no Gamescope prerequisite |
| Input | virtio keyboard and absolute tablet / Linux evdev | Native touch/controller mapping, then BP navigation |
| Storage / network | Kernel + initramfs, no disk/network/snapshot | Independent ext4 disk, slirp with ROM disabled, no unauthenticated forwarded shell |
| GPU | CPU-generated pixels uploaded by the host presenter | Guest Vulkan/accelerated rendering is a separate unproven milestone |

In the pinned Husk source, `QemuRunner.run()` performs a GL probe and Android snapshot work around the existing Alpine profile. Do not merely swap its argv and treat it as an isolated Linux session. Integrate an explicit Linux branch/session that skips those Android operations, uses a dedicated directory, registers `husk_display_init()` after `qemu_init`, forwards input through the same software bridge, and runs only after the existing JIT self-test succeeds. Preserve the Android profile and its data.

`ios/LinuxGuestProfile.swift` validates the assets and creates native argv with mandatory `split-wx=on`. The continuation adds `LinuxProbeSession.swift` and `LinuxProbeView.swift`: a one-session QEMU owner, isolated UI route, software display/input, strict framebuffer/evdev evidence and a shareable report. [The pinned Husk overlay](husk/README.md) connects these to the actual app entry point. Source staging and the Apple Swift typecheck passed; native app compilation, linking and device testing remain pending.

`ci/check_linux_guest_profile.py` and the manual `ideck-linux-guest-profile-check` typecheck the original and patched Husk Swift application using the real C bridge and Apple SDK, and run the profile/evidence validator tests on Mac. The exact offline upstream source slice has 78 files, including the original `husk-console-abi.h` missed by the first archive. Restore checks the bridge's complete literal local-include chain as well as file hashes. Existing notices/license remain included; the archive contains no runtime binaries. The first Apple attempt and local reproduction/fix are recorded in `evidence/source-header-fix.json`; the later gate completion and preparation fixes are recorded in `evidence/native-input-fix.json`.

## Reproduce on this Windows workstation

Run from the repository root. All outputs and caches belong on E. The exact workstation tool paths and executed commands are in the root `HANDOFF.md`. Generic commands:

```text
python experiments/linux-guest/tools/steam_abi.py --work .work/steam-abi
clang --target=aarch64-linux-gnu -fuse-ld=lld -nostdlib -static -ffreestanding -fno-builtin -fno-stack-protector -O2 -Wall -Wextra -Werror -Wl,-e,_start experiments/linux-guest/guest/fb_probe.c -o .work/linux-boot/fb-probe
python experiments/linux-guest/tools/prepare_guest.py --archive .work/linux-boot/alpine-netboot-3.24.1-aarch64.tar.gz --out .work/linux-boot/probe-new --sevenzip <7z-executable> --frame-probe .work/linux-boot/fb-probe
python experiments/linux-guest/tools/host_smoke.py --qemu .work/linux-boot/qemu/qemu-system-aarch64.exe --guest .work/linux-boot/probe-new --out .work/linux-boot/run-new
python -m unittest discover -s experiments/linux-guest/tests -v
```

Input URLs, provider checksums, sizes and local hashes are in `evidence/boot-inputs.json`. The QEMU Windows binary provider is linked by [qemu.org](https://www.qemu.org/download/#windows). The installer was unpacked with 7-Zip, never installed. Preserve its COPYING/source information. Guest preparation refuses an archive that differs from the pinned SHA-256. Use a fresh output directory; no old result or guest is overwritten. In PowerShell, quote `'-Wl,-e,_start'`.

The Swift-only Apple workflow has no automatic trigger, dependency download, signing or publication; it retains compiler logs and the result as CI artifacts. Before dispatch, check the current free quota and disabled paid subscription; historical quota numbers are not current authorization. Set `expected_commit` to the exact reviewed branch commit and select the existing private repository. Internal budget: 480 seconds; provider cap: 10 minutes. The separate IPA workflow includes this gate and has its own 120-minute cap.

## Failed controls retained

1. Initial netboot probe: framebuffer existed but evdev was absent. Added the signed `evdev.ko` from the **same** verified Alpine modloop, without replacing the kernel.
2. A `dd` framebuffer writer left a cursor overlay; disabling it exposed an unrefreshed black scanout. These runs failed the pixel check. The replacement uses a real static guest ELF, mmap damage, msync and framebuffer pan/unblank ioctls. The pixel acceptance rule was not relaxed.
3. Diagnostic WIP equality initially failed under Windows automatic CRLF conversion. Explicit `core.autocrlf=false` produced byte-identical patched sources. The supplied archive was not edited.

## Licensing and scope

`RESEARCH.md` records the pinned projects and their source licenses. The continuation includes an exact source-only Husk slice for offline compiler checking, with its existing GPL notices and LICENSE; no license was replaced or newly selected. No Steam binary is committed or repackaged for distribution. This is a separate Husk experiment, not a link between the Playport/Madeira app and QEMU. Combining/distributing those targets still requires a file-level license/exception review.
