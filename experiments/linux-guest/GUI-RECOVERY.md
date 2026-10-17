# GUI recovery after process termination

**Release gate BLOCKED.** Earlier two-cycle acceptance was withdrawn: exit0 with
`Fix? no` was insufficient, and the old serial token could match terminal echo.
The corrected nonce/status protocol and strict full-output gate were exercised in
two independent real force-kill attempts; both correctly refused activation for
unresolved counter mismatches. A pristine target passes the positive gate.
Successful force-kill/recovery/GUI-relaunch acceptance is **NOT established**.

The diagnostic fix is pushed as7a9225a; initial host proof isdb542ce. Native
transaction/UI integration now implements the workflow below. Apple compilation,
Swift IO regressions, new IPA and iPhone recovery are **NOT RUN** here. Parent
coordinates the single CI build after review and fresh quota/paid-OFF checks.

## App workflow and durable transaction

Enable JIT and choose Start desktop. If the unchanged normal clean-superblock
validator refuses needsRecovery BEFORE native entry, this process uses its ONE
VM for recovery instead. The top bar also offers Recover disk before an attempt.
The UI shows backup/copy/check/result stages; Share report and Diagnostics remain
fixed outside disabled inputs. The original disk is never attached to recovery.

The GUI-only helper exclusively locks the original and recovery workspace, records
its identity/uid/gid/mode/UUID/size/SHA-256, streams and fsyncs an independent backup,
hash-verifies it, then separately copies/verifies the work image. No APFS clone or
sparse allocation saving is assumed. A new attempt needs two1.25GiB copies plus
512MiB reserve. A resume first validates the backup and reclaims only uncommitted
work; actual free space is checked again before copying. Verified backups remain.

After ordered assessment/replay/read-only verification AND SCAN_CLEAN markers, guest shutdown and
host fsync, the worker writes a verified receipt only. Its work/source descriptors,
lease and QEMU owner thread remain retained until PROCESS exit. Main-loop return
never authorizes promotion, closing a native-owned image, or another qemu_init.
The UI requires fully closing/reopening iDeck and choosing Start desktop.

In that fresh process, before its first VM, promotion requires a different process
UUID AND exclusive locks, matching immutable-tool/suffix receipts, original/backup
hashes and source identity, plus the existing strict CLEAN validator on work. It
hashes/fsyncs the recovered image, durably records promoting, atomically renames
work to active, fsyncs both directories, then records promoted. If killed around
rename, the next fresh process recognizes only the recorded original hash or
recovered hash; unknown states fail closed. The per-generation original.raw and
receipt remain for rollback/review. A subsequent recovery uses a new generation.

Copying/running interruptions retry from the original/verified backup. A failed
journal/manual-action/read-only gate or rejected clean header blocks activation
and requires a separate decision; there is no general/destructive repair action.
Reports export fixed phase/failure codes and exit numbers, never file contents or
arbitrary native/error text. Raw backup export/rollback UI is not implemented.
This cannot intercept SIGKILL or guarantee unsaved/uncommitted writes survive.

The current [strict-gate receipt](evidence/gui-recovery-20261017/strict-gate-receipt.json)
records base/suffix/source hashes, complete nonce-framed status0 after sync, actual
SIGKILL, verified independent snapshots, rejected output gates and read-only
control-file checks after replay. Rejected work was never promoted. The old
[receipt](evidence/gui-recovery-20261017/receipt.json) is withdrawn and retained
for audit. The owner image was neither available nor accessed.

The test uses the earlier authenticated cloud seed46fea, with the SAME production
Alpine6.18.35 kernel/base initramfs and Debian package closure as the current local
payload. Current published local seed9c4d is unavailable in this environment and
must be checked separately. No iPhone recovery or Apple/native test is claimed.
The [glibc resolver smoke](evidence/gui-recovery-20261017/trusted-tools-loader.json)
also ran the actual seed interpreter `/lib/ld-linux-aarch64.so.1 --list` in the
production-kernel guest. e2fsck resolved libext2fs/libcom_err/libblkid/libuuid/
libe2p/libc from `/lib/aarch64-linux-gnu`; blockdev resolved libc. That separately
instrumented RO inspection is separate from recovery acceptance.

The trusted tool seed is attached RO and mounted ro,noload; its glibc e2fsck runs
inside chroot, with its immutable loader/libraries and an explicit empty fsck
configuration. No executable/configuration comes from the work target. Target and
tools share a filesystem UUID; two unique virtio serials, RO bits and sizes select
their roles. The work target is never mounted and is block-device RO during both
`e2fsck -fn` passes. Only `e2fsck -p -E journal_only` gets a writable target. Any
manual-action/error exit blocks activation; there is no general repair or -y.
The [Debian e2fsck manual](https://manpages.debian.org/trixie/e2fsprogs/e2fsck.8.en.html)
documents journal-only replay and read-only checking.

Both old checks returned fsck0 while printing unresolved free-block/free-inode
counter mismatches/Fix?no. [Upstream source analysis](evidence/gui-recovery-20261017/e2fsck-source-analysis.json)
identifies PR_NO_OK on these two problems: rejecting their fix does not clear the
filesystem-valid flag. This explains exit0, not the origin of any owner-image
problem. The new pinned-LC_C output gate accepts only banner+five ordered passes+
ordinary summary. Any extra diagnostic blocks SCAN_CLEAN and native promotion.
The checksum/clean-superblock gate remains necessary, but cannot substitute.

A separate [disposable host preen experiment](evidence/gui-recovery-20261017/counter-lab-experiment.json)
is NOT enabled as an automatic counter-only solution: `-p -f -E fixes_only` changed
209199 bytes outside the primary superblock and the following -fn still printed
an Optimize?no proposal. Changes outside the superblock do not by themselves prove
unsafe repair: group descriptors, checksums and other metadata must be classified.
Source snapshots/control file remained intact. This was
an isolated lab copy, never an app/owner-image action. The app enables journal_only
only; general preen, manual dirty-bit editing and destructive answers stay absent.

Force-kill also left persistent `/tmp/.X0-lock`, blocking Xorg on relaunch. The
small deterministic newc suffix now overlays the accepted desktop PID1 with two
reviewed changes: mount `/tmp` as mode1777,size64m tmpfs and unmount it after killing
session writers. Existing disk `/tmp` contents are hidden, not deleted. `/home`
remains on ext4. The accepted base initramfs, GUI seed and payload lock are unchanged;
no new large artifact or cloud export is needed.

Reproduce in a NEW disposable output directory (needs space for copies/backups):

```sh
python3 experiments/linux-guest/tools/check_gui_recovery.py \
  --assets /path/to/verified-restored-gui-assets \
  --host /path/to/existing/authenticated-extracted-amd64-tools \
  --output /path/to/new-disposable-lab --cycles 2
```

With current old-seed warnings this normal acceptance command must fail closed.
Use `--verify-output-blocker` to reproduce two independent refusals plus the
pristine positive gate; its blocked_verified status is explicitly NOT acceptance.

The script verifies every input asset against its profile before creating any VM;
uses existing relocated Debian tools; disables guest networking; does not install
packages, contact an API, or read an owner disk. Retain the output receipts/logs and
original-N.raw snapshots. Native promotion must wait for a fully fresh app process;
host QEMU subprocess exit is not a model for safe same-process native teardown.

## Remaining checks

The cloud has the old46fea assets; current9c4d raw seed is retained on the parent's
Windows/WSL workspace, not this selected filesystem. Live credential/token requests
are prohibited; no authenticated fetch or known-failing artifact transport was
attempted. This is an explicit current-production-assets blocker. Rerun with9c4d.
The unresolved-counter recovery also needs a separately validated safe method;
the app deliberately stops for review. Apple
gate now requires real Swift IO/lock/low-space/partial-copy/control-receipt and
fresh-child-process before/after-rename interruption tests. Those tests use sparse
synthetic unit bodies and do not substitute for this real VM gate. They are NOT
RUN without the Apple toolchain. Device must check live report sharing, recovery
after force-quit, relaunch/promotion and saved user files. The owner's original
image is unavailable; it has not been restored or claimed healthy.
