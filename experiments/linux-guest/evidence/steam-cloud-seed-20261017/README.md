# Private experimental seed accepted; Steam download still blocked

This follow-up started clean from remote Steam branch commit
`96268f4c95ed9c9e07279d9ccd9b0b716f85171f`. One agent, cloud only, offline VM
acceptance; no laptop, subagent, network/security change, CI or Release mutation.

**A separate experimental GUI seed passed acceptance.** It is not the production
`9c4d978f…` seed. `ipa/gui.lock.json`, production payload inputs and all guest
scripts remain unchanged. No disk/client bytes are committed or published.

| Private artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `experimental-seed-v4/seed/gui-rootfs-v1.raw` | 1342177280 | `a7758d821f67ec48646d4586ec54aeab8b8db31238f0be6dfaabc5966c46a5a2` |
| `experimental-seed-v4/seed/gui-rootfs-v1.raw.gz` | 270444186 | `a5f23c8978bdef7846a800fd3c6207fe032ed4f1bc48450fe17a1704c0f6d05d` |

Paths above are relative to the retained private directory
`/workspace/steam-cloud-20261017`. They are not download links or promised inputs
in a different cloud workspace. The seed hash was unchanged through the Alpine
gate; only a new private copy was writable.

| Successful final check | Seconds | QEMU sampled peak RSS bytes | Real glibc loader checks |
| --- | ---: | ---: | ---: |
| Lab boot1 | 90.198 | 842698752 | 423 |
| Lab boot2, persistence | 86.519 | 831393792 | 423 |
| Seed cleanup boot | 58.913 | 799580160 | — |
| Original Alpine kernel boot1 | 52.164 | 980742144 | 423 |
| Original Alpine kernel boot2, persistence | 52.384 | 974184448 | 423 |

These real QEMU boots verified UID1000 GUI apps, X11 windows, keyboard typing and
file ownership, pointer move/resize, actual evdev wheel events +1/-1, root menu
launch, save/reopen and reading saved files before new writes. Both Alpine boots
also checked a persisted machine ID. Every successful boot had clean guest
unmount, QEMU exit0, subsequent host fsync and strict read-only offline fsck.
Six supplemental strict checks cover the five VM outputs and the seed itself;
all retained full stdout/stderr and accepted exactly five passes/version/summary,
with no warnings or proposed changes. Hashes stayed unchanged by each check.
The GUI package audit requires exit0 and byte-empty output. The 341 pinned GUI
packages are preserved; the 45 extra Steam packages are **not installed** here.

All five final boots used the existing host-only Cortex-A72/four-vCPU/1024MiB
configuration, software display and `-nic none`. Alpine used the exact original
6.18.35 kernel and GUI bootstrap. These measurements are GUI seed acceptance,
not Steam RAM/SHM, GPU acceleration or iPhone/Apple acceptance.

## Capture readiness fix and retained failures

The first cleanup attempt emitted no `WHEEL_BYTES` rows; earlier lab boots had
96 bytes each. This was not the previous prompt/CRLF parsing issue. The runner
acknowledged capture before its background reader necessarily opened evdev.
The host acceptance helper now opens evdev fd4 synchronously before readiness,
lets the bounded reader inherit that open file description, closes it after
capture, and preserves unexpected reader failures. The capture limit is still
two seconds; CPU, RAM, input assertions and all other deadlines are unchanged.
The precise cause of the original empty capture was not instrumented and remains
unproven; this closes an established readiness gap without claiming that cause.
See `capture-failure-analysis.json`, archived source and the failed serial log.

49 GUI regressions passed, including three actual POSIX-shell tests for an open
descriptor before a deliberately delayed reader, rejecting a bad device, and
preserving reader failure. The final five VM boots ran the corrected helper.
The preserved provision receipt uses the old runner; the existing seed builder
compares its complete common/provisioning AST, excluding only the inactive GUI
branch. Both new lab boots require and retain the exact current runner hash.
No provenance check was relaxed.

The failed cleanup copy and its full strict fsck are retained. Two subsequent
preparation errors (missing `tree` link, then a symlink `probe` rejected by the
existing verifier) happened before any new cleanup VM. They were corrected using
already available verified bytes, with new output directories and no verifier
change. Finalization continued from the exact accepted frozen lab snapshot.
Original provisioned and earlier lab images remain private and unchanged.

## Remaining inputs and network configuration

Exact failed official URLs, the narrow hostname/path allowlist and owner/admin
settings are in [NETWORK.md](NETWORK.md); all 17 pinned component URLs and hashes
are in [locked-downloads.json](locked-downloads.json). No failed download was
retried and no signed private URL or credential is included.

Steam client ZIPs remain **0/17**. Main Steam UI, Big Picture, Steam input/restart,
Steam RAM/SHM, IPC tracing and ARM64 Steam stack capture are **NOT RUN**. No Steam
timeout, sandbox, namespace-helper, sentinel/cache or runtime flag was changed.
The existing Steam runner still requires the production seed hash: using this
experimental seed later needs a separate, verified Steam-only seed contract,
without changing the production GUI lock. No Steam disk was created by bypassing
that guard. The exact Steam bootstrap from the previous cloud step is built but
has not been booted here.

All task QEMU processes have exited and no host disk mount was created. Storage
usage is recorded in `storage.json`; recompute it before a Steam disk/update or
12GiB flattened offline copy plus the mandatory 4GiB reserve. Existing disks,
failed evidence and cached inputs were preserved rather than purged for space.
