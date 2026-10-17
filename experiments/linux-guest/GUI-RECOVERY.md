# GUI recovery after process termination

Two real force-kill/recovery/GUI-relaunch cycles PASS on the explicitly OLD cloud
seed46fea with corrected nonce framing, preserved files, clean Stop and independent
full fsck. [Scoped receipt](evidence/gui-recovery-20261017/scoped-receipt.json).
**Current production9c4d, Apple/native execution and iPhone recovery are not verified.**
The confirmed Release request failed at the proxy: `Tunnel connection failed: 403
Forbidden`. This is the remaining exact-assets blocker, not a GitHub authorization
finding. No credential/token was read and no CI was dispatched.

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

Ordered assessment/replay/scope/verification/SCAN_CLEAN receipts, guest shutdown
and host fsync authorize a verified RECEIPT only. The QEMU owner thread, source/
work descriptors and locks remain retained until PROCESS exit. Main-loop return
never authorizes rename, closing a native-owned image or another qemu_init.
Fully close/reopen iDeck, then Start desktop.

In the fresh process BEFORE its VM, promotion requires a different process UUID
AND exclusive locks, bound tool/suffix receipts, original/backup hashes and source
identity, plus the existing strict clean header on work. It hashes/fsyncs work,
durably records promoting, atomically activates it, fsyncs directories and records
promoted. Kills around rename are idempotent: only recorded original/recovered
hashes are accepted. Original.raw and generation receipts remain for rollback/
review; no raw backup export or rollback UI is implemented. Unknown repair classes
never become destructive automatic repair. SIGKILL cannot be intercepted and
unsaved/uncommitted writes are not guaranteed.

## Evidence and remaining gates

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

Then parent reviews/runs the coordinated Apple gate: real Swift IO/lock/low-space/
partial-copy/receipt and fresh-child before/after-rename tests, full Husk typecheck,
new IPA and owner device checks. These are NOT RUN here. The owner's original
image was not available/accessed/restored. Exact current9c4d acceptance remains
blocked on [the recorded asset request](evidence/gui-recovery-20261017/current-asset-attempt.json).
