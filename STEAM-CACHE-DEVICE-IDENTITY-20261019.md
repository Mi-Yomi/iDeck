> CURRENT CI BUDGET — provider35 / worker30 minutes, 19 October 2026.
> Cache identity code from4f8f70bd is unchanged. Exact locked QEMU10.0.12-utm
> archive digest/size and serial/GET_ID/RO source support independently verified;
> upstream Linux6.18.35 sysfs/20-byte ID support reviewed. **602 Python tests
> OK /5 SKIP**, overlay/pins and timeout cleanup checks PASS.
> CI#41 consumes the earlier62-minute balance. Coordinator must verify the fresh
> remainder with reserve and paid OFF after it finishes before any manual run.
> No CI started/cancelled here; old cap55/50 and larger limits are historical.
> New Apple/phone/real QEMU verification **NOT RUN**; BusyBox provenance **OPEN**.
> [Budget and serial review](STEAM-CI-BUDGET35-REVIEW-20261019.md).

# Steam cache block-device identity — source correction

Baseline `460d5f260089e0c9f0a62d0049a6ee04b9e78468`, Steam branch only.
Coordinator supplied owner screenshot evidence at10:51 UTC: Advanced shows
`IDECK_STEAM_BLOCKER:offline_cache_not_readonly`, package verification completed,
explicit retry enabled, Open Steam disabled. The coordinator inspected the
pixels; this executor did not inspect that screenshot locally. No device-node
mapping, ioctl values or mounts can be inferred directly from those pixels.
This is a separate blocker from the earlier Auto RAM/JIT feedback correction.

## Cause found in code

The old guest `open_device()` unconditionally opened `/dev/vdb`, checked block
type, then rejected `BLKROGET != 1` before checking capacity. QEMU already sets
the cache backend `readonly=on`. The cache is a raw canonical TAR, read directly
with `pread`; it has no filesystem mount or mount flags. Host package validation
does not prove which guest block node was selected.

The hardcoded device ordinal is invalid on ARM `virt`: QEMU explicitly documents
that virtio-mmio enumeration order depends on kernel traversal and is unstable;
it recommends stable disk identities. The existing Steam root boot path already
scans disks by UUID. It therefore boots correctly when root becomes`vdb`, while
the old cache reader then selects that writable root and emits this exact RO
blocker. This is a concrete code defect and a consistent explanation of the
observed error; the actual owner's node order remains **unmeasured**.
Primary source: [QEMU10.0 virt transport setup](https://github.com/qemu/qemu/blob/v10.0.0/hw/arm/virt.c#L1045).

Saved diagnostic recovery only exports reports; it does not restore a Steam
status into the live action state. The live blocker clears the matching action
admission and permits explicit retry, while INSTALLED is never emitted by this
failed cache check. Package-verified status refers to host bytes and is still
true. No stale-success receipt or mount transition was found to explain this
code path. Retrying the unchanged old VM cannot fix a device-selection error.

## Correction and safety

QEMU now gives only the cache virtio block device serial
`ideck-steam-cache-v1` (20 bytes). The value is generated into the Swift contract
from the guest constant. The guest searches whole virtio disks by that exact
serial, rejects missing/duplicate identities, and compares the opened descriptor
major/minor against sysfs before checking actual RO and size. Linux exports the
virtio block serial as a disk attribute:
[Linux6.18 virtio block driver](https://github.com/torvalds/linux/blob/v6.18/drivers/block/virtio_blk.c#L834).

No fallback to a guessed ordinal, another readonly disk, a writable cache or
network source was added. Open remains `O_RDONLY|O_NOFOLLOW|O_NONBLOCK|O_CLOEXEC`.
`BLKROGET=1`, exact capacity and all62 pinned header/content hashes remain
mandatory before installer writes. Partitions, serial prefixes and changed
device identity are refused. All failed opens close the descriptor.

Only the app argv and existing appended own-code runtime change. New suffix:
**14112 bytes**, SHA-256
`a0f3d0ee2c0560a60e4ef4ac709f75a2fc63470543c7ebcb6f2da8366561d205`.
The original kernel/initramfs/raw archive, all23 source bindings, cache archive
and its source pins, GUI/Debian/terminal payloads, userdata helpers, native worker,
Home/Resume, cancellation, Stop/fsync and disk locks are unchanged.
No Release or payload/cache rebuild/upload is needed. A new reviewed IPA and
fresh VM are needed to supply both the serial argv and updated runtime. Existing
user data must be preserved; no hot repair or silent reseeding is performed.

## Checks and limits

**599 Python tests OK,5 SKIP** in the real checkout. New regressions exercise
real temp sysfs-shaped file IO with both disk orders, including cache=`vda` and
writable root=`vdb`; the block type/ioctl boundaries are explicitly modeled.
Missing/duplicate/prefix/partition serials, major/minor mismatch, writable cache
and wrong capacity are refused. Existing complete synthetic installer/journal/
resume and userdata preservation tests pass. An actual-production Swift argv
fixture now supplies a valid synthetic cache Handle and asserts serial,
readonly backend and unchanged root device. Its canonical fixture bytes were
independently validated in Python; Swift execution remains pending Apple CI.

Full81-file pinned source overlay, five patches, generated contract, unchanged
original Steam bindings, real Linux/cache staging and repeat/resource checks,
AST, shell, Git attributes and diff checks PASS. Evidence:
`experiments/linux-guest/evidence/steam-cache-readonly-20261019/`.

**Real host QEMU boot/BLKROGET and device result NOT RUN**: this executor has no
QEMU system binary. Attempting normal package metadata retrieval from the
configured Debian snapshot returned proxy HTTP403; no alternate route, proxy,
TLS or access-policy change was attempted. The container also has no effective
capabilities for a private loop-device mount. A filesystem mount is not the
cache's production access path. Unit boundary models are not real kernel/device
proof. New Apple build/Swift and phone Steam installation/rendering/gameplay
remain **NOT RUN**. BusyBox corresponding-source provenance remains **OPEN**.

Coordinator reports CI#41 on460d5f26 was already running when this evidence
arrived. That immutable build does not include this correction. No new or
parallel CI was started or cancelled here. Existing cap55/worker50 is unchanged;
remaining free quota must be checked again after the current run, paid OFF,
before deciding a suitable limit and one future manual CI for this new HEAD.
