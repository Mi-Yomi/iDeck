# Steam RECOVER refusal and copy-first recovery — source candidate

Baseline `c1c3cc851c90fc4fe343cd8221eb887fe61dce85`, Steam branch only.
The delivered CI#42/source08978cd9 predates these changes. No new IPA, Apple
execution, actual recovery or device success is claimed. CI is not started.

## Established device evidence

Coordinator read the real4967-byte owner Markdown report from19 October11:44:32:
Build119, source `08978cd962e5c53818a287f41285d32a702ac5ad`, iOS27/build24A5430a.
`terminal_prepare_failed`, elapsed0.611s, phase`disk`, JIT before Start PASS;
import`existing_steam_disk_preserved`, storage failure`needsRecovery`;
**RECOVER SET, state1, last_orphan0, error_count0**. Cache is verified local input,
not an installed client. Recovery fields and guest/QEMU-return markers UNKNOWN;
no serial snapshot supplied. These facts are coordinator supplied, not a local
read of the owner file. No personal Library identity or screenshot is committed.

The exact failed condition is the RECOVER flag. Its origin is **unknown**.
Zero error_count and state1 do not establish a clean filesystem, and the
screenshot/report do not prove corruption. This attempt failed before native
entry; it did not mount or replace the existing disk. Cache serial behavior has
not been exercised by this failed attempt.

The existing normal guard checks magic/revision, CRC32C, UUID and feature set
before observing the four state fields. A needsRecovery refusal precedes later
geometry/journal-layout checks, so those checks cannot be assumed complete from
the normal refusal alone. They remain required for recovery eligibility.

For future diagnosis retain current Source commit/App build/Attempt/checkpoints,
status, preparation phase, Import and Storage failure plus all four ext4 values.
`checksum` denotes the bounded superblock CRC, `assetDigest` denotes a seed/resource
SHA failure, and `locked`/`ownership`/`metadata` identify different identity/lease
guards. This current report does not export raw headers, inode/device paths or a full
current userdata hash; recovery can later record the checked work digest. A mutable user disk is not expected to match seed SHA.
Previous attempt Stop/unmount/host-sync checkpoints may help establish history;
their absence alone does not establish why RECOVER is set.

## UI correction

A sticky presentation flag records the three pre-native termination paths,
including failures before worker creation. All worker preparation failures
publish their finished snapshot and end environment orchestration. The screen
stops showing Linux/frame waiting or a preparation spinner, hides an inapplicable
Stop and presents the Russian refusal and direct **Диагностика / отчёт** action.
Input/session ownership guards are unchanged. A guest Steam-action blocker in an
already running VM is a separate state and keeps its Stop action.

## Explicit Steam recovery

An owner must fully restart iDeck after the refused attempt, open diagnostics
before starting any VM, then explicitly confirm **Подготовить безопасное
восстановление Steam**. After a consumed attempt the sheet closes into the existing session view with
progress/cancel/Stop controls; a preflight refusal stays visible without a VM.
JIT is still actually checked. Recovery uses1536 MiB
with the existing1 GiB reserve and a final fresh native-entry budget check;
it does not require network consent or attach the Steam cache/client. The
trusted GUI kernel/initramfs and immutable e2fsck1.47.2 tools are already bundled
and fully hashed by the existing recovery argv builder. **No new large payload,
Release, raw seed or user-disk rebuild is needed.**

The existing copy-first transaction now has an explicit typed Steam scope.
Default GUI calls still reject Steam. Only the exact12 GiB Steam UUID is accepted,
and only RECOVER=true/state1/orphan0/error_count0 after all immutable header,
geometry and journal-layout checks. Other states fail closed for manual review.
The first space guard precedes long12-GiB hashing. Initial backup+work require
**24 GiB +512 MiB actual free space**, in addition to the retained original.
A verified reusable backup may reduce the later work-copy requirement to
12 GiB +512 MiB. Sparse/APFS savings are not used as permission to proceed.
The source opens readonly and stays locked throughout the transaction/VM; copy/fsync/full-hash/identity
guards and receipt format are reused. Cancellation is checked at completed file
operations. No source disk is attached to the recovery VM.

The separate generated Steam guest identifies tools/work by serial, checks
their different UUID/capacity/RO roles, assesses the unmounted work readonly,
runs only `-p -E journal_only`, returns work to RO and requires two complete
readonly checks with strict output grammar. This option is limited to journal
replay by [e2fsprogs1.47.2](https://github.com/tytso/e2fsprogs/blob/v1.47.2/e2fsck/e2fsck.8.in).
Steam deliberately does **not** use the GUI counter-reconciliation mount or any
general repair: remaining count, inode, directory or unknown output refuses
activation and requires manual review. There is no `-y`, formatting, dirty-bit
editing or execution of code/configuration from the mutable work filesystem.

The full12-GiB work digest is reported only after strict clean scans and no
further target writes. Guest shutdown and host fsync must succeed before the
receipt becomes verified. No promotion occurs in the native-owning process.
After a complete app restart and explicit environment Start, fresh exclusive
locks, original/backup/work hashes, exact scope/tool/suffix pins, clean header
and receipt checks precede atomic rename and directory fsync. The original
backup is retained. Failed, incomplete or changed transactions cannot activate.

The GUI guest, generator and old acceptance source hashes remain byte-identical.
Copy/hash/fsync/lock/receipt-result methods and promotion body are unchanged
except the explicit scope constructor and corresponding suffix pin. Native
thread retention, normal ext4 validator and one-QEMU guard remain in force.
Steam recovery suffix:13484 bytes, SHA-256
`6301147c7fee492fc3288038b299a487e1ef1b7e5cab805902ddfbcf307d1eb0`.

## Verification and practical limits

**607 Python tests OK,5 SKIP**; original GUI receipt bindings, generated guest
shell syntax, strict scope/no-general-repair checks, blocked UI wiring and
normal safety regressions PASS. The Apple gate now additionally requires
`LINUX_STEAM_RECOVERY_SCOPE_PASS`: production scope predicates, actual12-GiB
sparse negative fixture, low-space before hashing/copies, original header and
normal guard preservation, and finite timeout checks. This is not a positive
filesystem repair fixture and Swift execution is NOT RUN here.

Full81-file upstream restoration, five patches,29 exact overlay copies,
generators, original23 Steam bindings, real Linux/cache staging/repeat/resource
verification, AST/shell/Git attributes and immutable safety comparisons PASS.
Evidence: `experiments/linux-guest/evidence/steam-safe-recovery-20261019/`.

Executor is available, with only about1 GiB free after staging. It has no system
QEMU/e2fsck and cannot provide24 GiB free for a full positive copy-first test.
The earlier configured package metadata retrieval was denied by proxy403; no
workaround was used. **Positive real12-GiB replay, new Apple/UIKit build and
phone recovery/activation/Steam remain NOT RUN.** On a phone, hashing/copying
many full images can take substantial time and IO. The unchanged GUI watchdog
is60/90/180 seconds; the separate Steam scope retains60s supervisor and scales
inactivity/absolute limits by the rounded-up image ratio10:900/1800 seconds.
Trusted milestones can renew inactivity, never the absolute deadline. This is
a finite conservative source limit, not a measured device calibration; timeout
preserves the original/backup and cannot promote. Keep iDeck in foreground.

Workflow cap35/internal30 still exceeds the latest supplied26 free CI minutes.
No CI or limit changes here; coordinator must review a suitable smaller build
budget, fresh free quota/reserve and paid OFF before any manual run. This source
candidate must not be described as an already delivered or phone-verified fix.
BusyBox corresponding-source provenance remains OPEN; controls remain key/mouse.
