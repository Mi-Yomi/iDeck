# Manual CI budget and cache serial review

Baseline `4f8f70bdfabdf2a8f1dbedc589b7b70f1ed1a4a2`.
Only the dedicated `ideck-linux-probe-ipa` cap and native worker budget change:
**35 provider minutes /1800 seconds (30 minutes) internal**, leaving five
provider minutes for setup/termination/artifact overhead. Other workflows,
environment, secrets, dependency/overlay/payload pins and functional cache code
are unchanged. No CI was started or cancelled.

The old62-minute balance predates the coordinator's current CI#41 and is not
reused as authority. After that run the coordinator must freshly verify free
quota greater than35 minutes with reserve and paid OFF. Use `mac_mini_m2`,
Xcode27.0 and the existing inputs with the exact reviewed final remote HEAD:

```text
expected_commit=<full reviewed remote HEAD containing this change>
free_quota_verified=true
private_source_verified=true
native_build_approved=true
```

The worker clock starts before package preparation. Its remaining budget
decreases through preparation and all steps; native downloads also use the
remaining time. No later step resets it. Exhaustion prevents another child;
timeout kills/reaps the current process group and does not record success.
Existing bounded package preparation remains included in elapsed accounting.
No fixed-duration stage requires more than30 minutes. Coordinator-reported
prior successful builds took16–26 minutes; a slower cold build may still time
out. No timeout bypass, automatic retry or budget extension was added.

## Serial review

Downloaded the **exact locked QEMU10.0.12-utm archive**, independently verified
**142836072 bytes**, SHA-256
`7c9605290b34152debb842e965a55d2e4fbba4793e536ab677b4027e5dc0ba1a`.
Read only its regular `hw/block/virtio-blk.c` and `hw/arm/virt.c` members, without
extracting the source tree or building native code. They confirm serial property
support, GET_ID handling, readonly feature advertisement and unstable ARM disk
enumeration. Member hashes are retained in the evidence JSON. This checks the
actual archive pin, rather than assuming a current QEMU branch is identical.

Upstream Linux6.18.35 exports serial as a disk sysfs attribute, registers it
with `device_add_disk`, uses20-byte IDs and sets disk RO from VIRTIO_BLK_F_RO.
Source: [Linux6.18.35 virtio block driver](https://github.com/gregkh/linux/blob/v6.18.35/drivers/block/virtio_blk.c).
This is upstream source review matching the kernel version; it is not proof
that every Alpine build patch has been independently reproduced.

The generated serial is exactly20 bytes. Missing/duplicate/prefix serials and
partitions fail closed; matching checks the opened device's major/minor, actual
RO=1, exact capacity and every pinned byte before installation. No ordinal or
first-match fallback exists. The host cache remains readonly in QEMU argv.
These paths and all original cache/native guards are unchanged from the
reviewed cache-identity commit.

**602 Python tests OK,5 SKIP**, including aggregate budget/no-reset/timeout
cleanup and cache identity regressions. Overlay hash validation, exact pinned
source review, parsed workflow comparison and diff checks PASS. Evidence:
`experiments/linux-guest/evidence/steam-ci-budget35-20261019/`.
Real host QEMU, new Apple/native build and phone behavior remain **NOT RUN**;
the earlier system-QEMU package retrieval blocker is unchanged. Prior real
staging evidence remains applicable because no functional/resource/overlay
input changed in this task. BusyBox source provenance remains **OPEN**.
