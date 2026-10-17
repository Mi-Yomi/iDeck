# Explicit experimental seed contract; dependency VM blocked before writing

Started clean at verified remote Steam commit
`bf63183b55e2e3ee8e01155c8dc026cbe6e1a939`. One cloud agent; no laptop,
subagents, policy changes, denied download retries, image deletion or CI.

The Steam runner now supports an explicit reviewed host-only contract:
[`profiles/steam-experimental-seed-20261017.lock.json`](../../profiles/steam-experimental-seed-20261017.lock.json).
Its seed is the independently accepted 1342177280-byte raw image with SHA-256
`a7758d821f67ec48646d4586ec54aeab8b8db31238f0be6dfaabc5966c46a5a2`.
Production `ipa/gui.lock.json` and the `9c4d978f…` default remain unchanged.
There is no automatic fallback or arbitrary caller-supplied hash override.

`steam_vm.py --experimental-seed-contract PATH` invokes the same verifier as
`tools/steam_seed.py`. Only the reviewed repository contract path is accepted.
It checks the actual seed/kernel/Steam bootstrap bytes and receipt, unchanged
GUI/client/dependency/profile lock hashes, all 105 files of the pinned acceptance
manifest, real Alpine boot/source hashes, machine-ID persistence, original GUI
bootstrap provenance, and the full strict offline fsck streams. A pass boolean
alone is insufficient. The trust root is the reviewed Git checkout/contract;
external JSON cannot silently select another acceptance set. Future continuation
must match both seed hash and explicit contract hash. Stop, exclusive ownership,
sandbox, guest namespace and production iOS behavior are unchanged.

Two independent CLI processes produced identical validation results, including
the canonical configuration SHA-256:
`d07392982666405ea54b33aabbb5db806e085bdc26ee4ac08e4f6c294adaad2b`.
It binds the input/profile hashes, contract and both Python startup source
snapshots. Filesystem paths/free-space observations are separate. This is input
configuration reproducibility, not VM execution or client/update reproducibility.
See `reproducibility.json`, `verify1.json` and `verify2.json`.

Fail-closed evidence:

- An actual different retained 1342177280-byte image (`425893ed…`) was rejected
  read-only with exit1 before any disk creation; its bytes were not modified.
- 148 existing/new Steam tests passed. Fault fixtures cover same-size wrong
  seeds, symlinks, external contracts, altered kernel/bootstrap/profile/locks,
  missing/corrupt/traversing evidence, rehashed false acceptance, forced boots,
  inconsistent machine IDs, misleading fsck PASS fields and contract mismatch
  on continuation. These fixtures do not claim real VM acceptance.
- The runner's actual preparation function was exercised against the real files
  and current filesystem, with a fence rejecting image-tool/VM calls. It reached
  the storage rejection; image/VM call counts and new-output-directory count
  were zero. See `runner-storage-gate.json`.

The host has no global `/usr/sbin/e2fsck`. The runner now passes the already
authenticated extracted checker through its matching ELF loader/library path
for offline checks, preserving `-f -n` and the strict full-output parser. Its
actual `-V` run succeeded; the command/identity is in `host-tools.json`. This
does not claim a new Steam disk fsck. The existing unit-test API default remains
compatible. Startup snapshots of the runner and validator are retained in a
future real run, so source edits cannot mislabel its validation code.

## Dependency install and storage

All 45 extra packages were rehashed successfully: 18238048 downloaded bytes and
69937152 declared installed bytes. **Guest installation and its dpkg audit are
NOT RUN.** No disposable Steam image, VM, HTTP cache server or new guest writer
was started. The standard 12GiB Steam profile was not shrunk to evade its checks.

| Current storage gate | Bytes |
| --- | ---: |
| Free at inventory | 15690088448 |
| Existing 12GiB offline copy +4GiB reserve floor | 17179869184 |
| Shortfall before any client/image growth | 1489780736 |
| Unique allocated task-file bytes | 16216498176 |

`space-inventory.json` records large files, logical and allocated sizes, hardlink
identity/count and totals by directory. It never follows symlink directories or
deletes data. Shared inodes are counted once; directory attribution uses the
first sorted path. Filesystem free space is authoritative. Major retained groups:

| Group | Unique allocated bytes attributed here |
| --- | ---: |
| Root-level preserved raw copies and task scripts | 4026667008 |
| Final seed/cleanup output `experimental-seed-v4` | 2778263552 |
| Original `gui-lab` inputs/frozen image | 2355752960 |
| First failed cleanup output | 1908285440 |
| Retained preparation output `experimental-seed-v3` | 1704636416 |
| Two-boot Alpine acceptance copy | 1536315392 |
| Frozen input-fix lab copy | 1372413952 |

The safe plan in `space-plan.json` keeps every original, failed output, cache and
receipt. Supply larger private cloud capacity or a separate filesystem under
`/workspace` for new outputs/tools/cache. The conservative target is
**30612663459 free bytes before future staging**: full 12GiB new overlay +12GiB
offline copy +4GiB remaining reserve, 360938891 uncached client ZIP bytes,
2024216 missing host-package download bytes and 184929280 declared bytes for a
separate complete host-tool extraction. This requires 14922575011 more free
bytes than the current snapshot. The snapshot also excludes 1734762496 bytes
from available capacity. Including that gap gives a nominal total-capacity lower
bound of 48692767907 bytes on this same filesystem, assuming the gap stays
constant; actual reserved/metadata allocation can grow. Use measured available
free bytes as the gate, not advertised capacity. The original estimate is retained
in `space-plan.initial.json`; `reconcile_space_budget.py` derives the correction
from the unchanged snapshot. The free-space target and runner thresholds did not
change. Re-measure actual allocation after staging, before image writes and again
before offline conversion; stop if any gate fails. No automatic expansion or
cleanup occurred.

Offline signed-index resolution shows the missing matching host package is
`qemu-utils` version `1:10.0.13+ds-0+deb13u1`, 2024216 bytes, SHA-256
`6d31339b1630153fe7c5f8a51426b8fa6ce35731aeb015a84f2d333c4e4dca30`.
All its other dependencies match the existing pinned GUI host closure. No
package was downloaded or installed; a real `qemu-img` extraction/binary receipt
is still required before a future VM. The existing installer also retains its
guest free-space checks and byte-empty successful `dpkg --audit` requirement.

## Replaying the read-only preparation

From `experiments/linux-guest` in this retained private workspace:

```sh
python3 tools/steam_seed.py \
  --contract profiles/steam-experimental-seed-20261017.lock.json \
  --seed /workspace/steam-cloud-20261017/experimental-seed-v4/seed/gui-rootfs-v1.raw \
  --kernel /workspace/steam-cloud-20261017/gui-bootstrap/vmlinuz-virt \
  --bootstrap /workspace/steam-cloud-20261017/steam-bootstrap \
  --storage-root /workspace/steam-cloud-20261017
```

Exit2 currently means valid contract but blocked storage; exit1 means invalid
input/provenance. Exit0 would mean these preparation gates passed, not a boot.
The images remain local/private and are not included in Git or download links.

Steam ZIPs remain 0/17 after the previously observed tunnel403. Network settings
were not changed and the denied URL was not retried. Steam UI/Big Picture/input,
Steam RAM/SHM/IPC/ARM64 stack capture, Apple/iPhone and GPU acceleration remain
NOT RUN. This is preparation; no Steam client execution or new runtime cause is
claimed. All task QEMU processes remain absent.
