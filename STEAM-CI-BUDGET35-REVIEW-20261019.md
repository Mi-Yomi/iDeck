> CURRENT DELIVERED RESULT — Apple CI#42 PASS, 19 October 2026.
> https://codemagic.io/app/6ad03ce9a8a969b53f3a4aa9/build/6ad5fa7a7550aed81090197b .
> **Built source: 08978cd962e5c53818a287f41285d32a702ac5ad.**
> IPA **1086788107 bytes**, SHA-256
> **faaa7f32a6ade15e62c23ebbd15a57e8fac6c9d4517a9b36f5fc47189e0002c0**.
> Coordinator independently checked real ZIP CRC, all7 Mach-O binaries as arm64
> iPhoneOS/ad-hoc,19 resources/cache and25 Swift PASS markers. The delivered IPA
> includes stable cache serial identity and launcher JIT/RAM feedback.
> Owner-only Drive delivery is confirmed; no personal Drive URL is stored in Git.
> These CI/artifact/inspection/delivery facts are coordinator supplied. This
> docs-only update did not download/rebuild the IPA, alter code/pins/config,
> dispatch/cancel CI or modify a Release. Its commit differs from built source.
>
> CI#41 PASS on460d5f26 was an intermediate JIT/RAM build without the cache fix.
> The source correction is compiled in CI#42, but **device / actual cache fix,
> JIT/RAM flow, Steam installation/rendering and gameplay on iPhone NOT RUN**.
> Wait for owner feedback. Controls remain keyboard/mouse mapping, not Linux
> HID; Auto4096 and disk12 GiB unchanged. BusyBox source provenance **OPEN**.
>
> Latest coordinator balance: **26 free minutes, paid OFF**. Current provider
> cap35 / worker30 no longer fits: **do not start another CI**. A future run
> requires a separately reviewed smaller limit, fresh quota with reserve,
> paid OFF, exact reviewed source SHA and private/native approvals. No automatic
> dispatch is authorized. Historical budget/NOT RUN/dispatch checkpoints below
> describe their earlier source verification and do not supersede this block.

# Historical CI#42 budget and cache serial review

Baseline `4f8f70bdfabdf2a8f1dbedc589b7b70f1ed1a4a2`.
Only the dedicated `ideck-linux-probe-ipa` cap and native worker budget change:
**35 provider minutes /1800 seconds (30 minutes) internal**, leaving five
provider minutes for setup/termination/artifact overhead. Other workflows,
environment, secrets, dependency/overlay/payload pins and functional cache code
are unchanged. No CI was started or cancelled.

The following dispatch parameters record the completed CI#42 setup. Its earlier
quota snapshots are not authority for another build: the latest26-minute balance
is below cap35 and worker30. Do not reuse these limits or dispatch again without
a separately reviewed smaller budget and fresh quota/reserve/paid-OFF checks.
Historical provider and inputs:

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
