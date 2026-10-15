# Direct Linux guest: bounded feasibility experiment

This branch advances the requested **real Linux kernel + Linux Steam + Big Picture on iPhone** route. It preserves the previous Playport/Madeira source snapshot and all existing CI workflows. It does not replace the application, provide an IPA, or claim an iPhone Steam session.

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

`ios/LinuxGuestProfile.swift` validates the generated assets and creates the native argv with mandatory `split-wx=on`. It is source prepared for that integration; it does **not** start QEMU itself. `ci/check_linux_guest_profile.py` and the manual `ideck-linux-guest-profile-check` workflow typecheck it against the real Apple SDK and run separate synthetic Mac validation checks. Neither check has run here.

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

The Apple workflow has no automatic trigger, dependency download, signing, artifact upload or publication. Before any owner-approved push/dispatch, check the current free quota and disabled paid subscription; historical quota numbers are not current authorization. Set `expected_commit` to the exact reviewed branch commit and select the existing private repository. Internal budget: 240 seconds; provider cap: 10 minutes. This task is a compiler gate, not an IPA build.

## Failed controls retained

1. Initial netboot probe: framebuffer existed but evdev was absent. Added the signed `evdev.ko` from the **same** verified Alpine modloop, without replacing the kernel.
2. A `dd` framebuffer writer left a cursor overlay; disabling it exposed an unrefreshed black scanout. These runs failed the pixel check. The replacement uses a real static guest ELF, mmap damage, msync and framebuffer pan/unblank ioctls. The pixel acceptance rule was not relaxed.
3. Diagnostic WIP equality initially failed under Windows automatic CRLF conversion. Explicit `core.autocrlf=false` produced byte-identical patched sources. The supplied archive was not edited.

## Licensing and scope

`RESEARCH.md` records the pinned projects and their source licenses. No third-party runtime source has been copied into this experiment, no original license was changed, and no Steam binary is committed or repackaged for distribution. The existing Playport/Madeira app and a future linked QEMU/Husk target require a file-level license/exception review before combining or distributing them. Do not assume that sharing ARM64 instructions, a Metal backend or a JIT helper makes their runtime ABIs interchangeable.
