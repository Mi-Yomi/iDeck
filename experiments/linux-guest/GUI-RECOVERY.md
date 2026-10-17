# GUI recovery after process termination

**Current production9c4d host gate PASS**, tested runtime/source
`158be7910d1c372cdddbf7cb87706ad2ce69042f`. The unchanged two-cycle repository
harness performed actual force-kills, copy recovery, full guest digest binding
before promotion, new GUI-process persistence, clean Stop and three strict full
offline fsck checks. Recovery63.260/67.410s;17 focused regressions PASS. All source
assets, original backups and Steam data were preserved. No runtime fix was needed.
See [production receipts/full logs/manifest](evidence/gui-recovery-production9c4d-20261017/README.md).

Owner reports the IPA for exact158be791 and Swift recovery/startup regressions
passed in Codemagic build `6ad367417550aed8108f8f4f`. This documentation checkpoint
does not change that runtime or require a rebuild for source changes. No CI was
dispatched here. **Phone recovery is still NOT RUN.** Use the source-verified
[owner UI sequence and MD export instructions](GUI-RECOVERY-OWNER-158be791.md).

The prior [old46fea digest receipt](evidence/gui-recovery-20261017/digest-receipt.json),
[failed earlier Apple compiler report](evidence/gui-recovery-20261017/apple-ci-37869aa-parent-report.json)
and [former Library transport failure](evidence/gui-recovery-20261017/library-ipa-attempt.json)
are retained historical evidence. Production seed9c4d was subsequently obtained
from the exact authorized private Release and rehashed; its previous transport
blocker is closed. These host measurements do not establish iOS memory behavior.

## App workflow

Enable JIT and Start desktop. If the unchanged original clean-validator refuses
needsRecovery BEFORE native entry, this process uses its ONE VM for copy recovery.
Recover disk is also available before an attempt. Share report and Diagnostics
stay fixed above scrolling/disabled inputs, including failure/low-space states.

The GUI-only helper locks the source and workspace, records identity/uid/gid/mode/
UUID/size/SHA256, streams/fsyncs an independent backup and verifies its readback,
then makes/verifies a separate work copy. Two1.25GiB copies+512MiB reserve are
required initially. Resume validates the backup, reclaims only uncommitted work,
and checks actual free space again. Verified backups and the source are preserved.
No existing image is resized/reformatted/reseeded. Console and Probe disks are
outside this workflow.

Recovery has its own monotonic watchdog, independent of desktop readiness:
60seconds for supervisor startup,90seconds without an accepted trusted milestone,
and180seconds absolute for checks. Progress never renews the absolute deadline.
Hashing is an explicit in-progress state: keep iDeck open until confirmed finish.
DONE starts the existing30second shutdown watchdog. A timeout latches failure,
records supervisor/progress/deadline in diagnostics and prevents promotion from
that attempt; original/backup and native locks remain preserved. It performs no
forced native teardown. Normal desktop/console startup remains60seconds.
Owner reports the unchanged Swift helper/watchdog assertions and full IPA build
PASS at158be791. Neither the old46fea run nor the new production9c4d host harness
executes the native Apple timer/controller; phone validation remains separate.

Recovery attaches ONLY the work copy and the immutable bundled seed. The latter
is RO/noload and supplies pinned glibc e2fsck, Bash and coreutils through chroot;
no executable/configuration comes from the mutable target. Unique virtio serials,
exact sizes and RO bits identify roles despite their shared filesystem UUID.
Every fsck/journal operation runs with the work target UNMOUNTED; read-only scans
also enforce block-device RO. Only journal_only replay and the restricted kernel
cycle below can write the copy. No generic preen, -y or dirty-bit editing is enabled.

## Restricted primary-summary-counter class

After journal replay, a FULL unmounted `e2fsck -fn -E fixes_only` scan must be clean
or contain ONLY the two exact primary free-summary-counter warnings/Fix?no, with
all five ordered passes complete and exit0. Group/inode/directory repairs and all
unknown diagnostics are rejected. Eligibility also requires state1, no RECOVER,
last_orphan0, error_count0 and exact supported features. `fixes_only` suppresses
optional optimization proposals; it does not skip consistency checks.

For that narrow class, no app or target file is accessed: the kernel mounts the
COPY noatime/nosuid/nodev/noexec, syncs it and unmounts it. Runtime SHA256 before/
after must cover exactly1342173184 bytes outside primary block0 and match. Bash
pipefail and dd's byte count reject short/error streams. All4096 primary-block
bytes are compared; only global free counts, ordinary mount time/count/lifetime
bookkeeping and checksum may differ. A final independent FULL read-only scan must
have strictly clean output. Unknown classes/scope changes stop for review.

On the disposable test, descriptors AND bitmaps agreed at111837free blocks and
142603free inodes; primary summaries were111843/142605. The kernel cycle changed
ONLY12 bytes in primary block0; every other byte was hash-identical, preserving
all inode/directory/file/link/permission/xattr/bitmap/journal bytes. See
[kernel byte scope](evidence/gui-recovery-20261017/kernel-counter-lab.json) and
[upstream kernel source](evidence/gui-recovery-20261017/kernel-counter-source.json).

## Native ownership and activation

After final strict fsck/SCAN_CLEAN and sync, immutable guest tools hash ALL
1342177280 bytes while the unmounted work device remains RO. Bash pipefail and
an exact dd byte count reject partial reads. Only the trusted supervisor control
port emits the lowercase64hex IMAGE_SHA256 result. No target writes follow.
Ordered assessment/replay/scope/verification/SCAN_CLEAN/IMAGE_SHA256 receipts,
guest shutdown and host fsync authorize a verified RECEIPT only. This receipt
stores the GUEST digest without hashing a native-owned file on the host. The
QEMU owner thread, source/work descriptors and locks remain retained until PROCESS exit. Main-loop return
never authorizes rename, closing a native-owned image or another qemu_init.
Fully close/reopen iDeck, then Start desktop.

In the fresh process BEFORE its VM, promotion requires a different process UUID
AND exclusive locks, bound tool/suffix receipts, original/backup hashes and source
identity, plus the existing strict clean header on work. It hashes the whole
work file and MUST match the recorded guest digest before promotion. Missing or
changed digests fail closed; it never establishes a fresh baseline. It fsyncs work,
durably records promoting, atomically activates it, fsyncs directories and records
promoted. Kills around rename are idempotent: only recorded original/recovered
hashes are accepted. Original.raw and generation receipts remain for rollback/
review; no raw backup export or rollback UI is implemented. Unknown repair classes
never become destructive automatic repair. SIGKILL cannot be intercepted and
unsaved/uncommitted writes are not guaranteed.

## Evidence and remaining gates

The prior [scoped receipt](evidence/gui-recovery-20261017/scoped-receipt.json)
is historical evidence for the earlier suffix. Review528c2eb found that native
verified receipts did not yet bind the checked whole-image hash; a changed byte
outside the superblock could pass promotion. The current implementation records
the final guest digest and rejects missing/mismatched digests. Its new real
TWO-cycle digest receipt supersedes that run for current source acceptance.

The initial [receipt](evidence/gui-recovery-20261017/receipt.json) is WITHDRAWN:
exit0 did not exclude Fix?no and its serial substring token could match tty echo.
The later [strict journal-only test](evidence/gui-recovery-20261017/strict-gate-receipt.json)
correctly refused both attempts. Their historical source/logs are retained. The
current scoped receipt uses full output-line nonces absent from the input command,
separate status/failure markers and actual completed sync before SIGKILL.

General preen was investigated only on disposable copies. The
[complete structure/content comparison](evidence/gui-recovery-20261017/repair-structure-analysis.json)
found21229 identical logical paths,17318 matching regular-file hashes,1440symlinks,
2471directories and matching ownership/modes/links/timestamps/xattrs. Extra writes
were18 lossless directory-index constructions plus their metadata/checksums, not
proof of danger. The narrower kernel method avoids all those non-SB writes.
Actual [glibc resolver smoke](evidence/gui-recovery-20261017/trusted-tools-loader.json)
verified the interpreter and libraries in the production-kernel guest.

The small deterministic cpio suffix adds recovery/check scripts and gives desktop
/tmp a temporary64MiB tmpfs to avoid stale Xorg locks. Accepted base initramfs,
kernel, GUI seed and GUI locks stay unchanged; no new large payload is needed.
Source/native unit gates do not replace VM/device evidence. Host QEMU10.0.13 also
differs from iOS10.0.12-utm.

Run on NEW disposable output with the CURRENT verified restored9c4d assets:

```sh
python3 experiments/linux-guest/tools/check_gui_recovery.py \
  --assets /path/to/verified-restored-gui-assets \
  --host /path/to/authenticated-extracted-amd64-tools \
  --output /path/to/new-disposable-lab --cycles 2
```

That exact host command has now passed on production9c4d with source158be791.
Owner reports the coordinated Apple Swift IO/lock/space/partial-copy/receipt,
fresh-child rename/mutation/missing-digest regressions and existing IPA build
passed for that SHA. No CI should be dispatched merely to publish this evidence.
The remaining acceptance is owner device recovery with the existing dirty GUI
disk and the required full-app restart. The owner's phone image was not available,
accessed or recovered by this host run. Phone recovery remains NOT RUN.
