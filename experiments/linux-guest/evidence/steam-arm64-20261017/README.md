# Steam ARM64 experiment evidence — 2026-10-17

The input receipts authenticate this separate experiment's inputs and fixture
tests. `runtime-summary.json` records the actual VM outcomes: Cortex-A72 exited
132; CPU max displayed the genuine Valve updater window in
`cpu-max/002-desktop.png`. The main client and Big Picture were not reached.
No Apple build, iPhone launch or game-performance result is claimed.

`upstream-receipt.json` binds the reviewed DroidDeck commit/files, the official
Valve ARM64 manifest and all 17 locally verified client archive hashes. Client
binaries and manifest contents are deliberately absent from this evidence tree;
no redistribution permission or agreement acceptance is claimed.

`elf-needed.json` records static DT_NEEDED inspection of 87 AArch64 ELF files.
The separately locked 41 Debian packages add the observed active UI/driver-query
dependencies to the accepted GUI's 341 packages. The signed existing trixie
index, exact APT simulation and actual `.deb` SONAME contents were checked.
Unused legacy bundled FFmpeg aliases are not claimed independently loadable.

The image-tool receipt pins the separately extracted QEMU 10.0.13 `qemu-img`;
its real version check used the existing pinned host loader/libraries without a
system install. Windows client/helper fixture logs and their receipt retain
actual counts. The recorded earlier WSL/9p atomic-publication errors are an
unsupported-filesystem finding, not a relaxed publication check.

The final CPU-max run completed guest sync/unmount, QEMU exit and host fsync.
`post-run-inputs.json` records the unchanged read-only seed and successful
read-only qcow2 structural check; ext4 fsck was NOT RUN. The Steam self-update
remains unfinished because the host drive approached exhaustion.

`test-summary.json` records 63 passing touched-code tests. The final helper cache
cleanup has 12 tests in `cleanup-v2-tests.log`; earlier receipts retain their
historical counts. `bootstrap-final.json` binds the rebuilt cleanup-v2 initramfs,
which was NOT BOOTED. The actual runs used the prior initramfs plus the explicit
equivalent cleanup command preserved in `commands/007-release-installer-cache.sh`.
