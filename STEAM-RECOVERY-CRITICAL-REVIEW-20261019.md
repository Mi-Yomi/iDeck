> Historicala669a397 review. CI43 compiled standalone Swift, then failed the
> host renderer fixture before integrated Husk checks. Its24/22 budget is superseded
> by [the CI43 correction and23/21-minute budget](STEAM-CI43-REPORT-REGRESSION-20261019.md).
> Positive12-GiB recovery/device acceptance remains NOT RUN.

# Steam recovery critical review — 19 October 2026

Source review starts at `0f413a857c7b5273eef09c25d4746a7abe65e443`, on
`codex/steam-arm64-experiment-20261017`. This supersedes its recovery protocol
and CI budget statements. CI#42 built08978cd9 and predates both recovery changes.
**This is an unaccepted source candidate, not a verified phone-recovery result.**
No CI, user-disk operation, Release update or payload rebuild was performed.

The coordinator-read owner report establishes RECOVER SET/state1/orphan0/
error_count0 and a pre-native disk refusal. It does not establish why RECOVER
arose, that fsck will succeed, or that any owner files are corrupt or clean.

## Findings and changes

1. Host preparation already hashes the original, backup and work. The guest
   lacked a full input-digest comparison before journal writes. Steam now gets
   the expected source SHA-256 through its trusted argv, sets only work block
   device RO, hashes all12884901888 bytes with immutable tools and pipefail,
   verifies dd's full byte count and exact digest, and only then assesses/replays
   the journal. A mismatch cannot reach the RW transition.
2. Steam's result lacked an explicit per-run binding. A schema2 receipt now
   binds exact Steam UUID/size, canonical generation UUID, a fresh nonce per
   prepared attempt and source SHA. The guest validates unique canonical argv
   fields and returns BIND before supervisor READY, then SOURCE_SHA256 after
   actual full hashing. The ordered host parser rejects missing, duplicate,
   stale, mixed or out-of-order milestones. `recordResult` requires the matching
   verified binding. Fresh-process promotion independently requires its saved
   nonce/source match, no failure, strict scan/tool/suffix/exit pins and existing
   disk hashes/locks. Schema1 Steam receipts are refused without deletion or
   migration. Existing schema1 GUI receipts/protocol remain supported.
3. A late READY could previously mark a failed/timed-out recovery ready despite
   `acceptRecoveryActivity()` returning false. It must now pass that guard and
   the Steam binding gate before any ready checkpoint. Failed receipts cannot
   become verified or promote. A binding refusal records terminal_stop_failed
   and terminal_clean_stop=false as well as preserving the disk guards.
4. Reducing the worker constant alone would leave synchronous cache/payload
   preparation outside its blocking wall-clock timer. The existing POSIX timer
   now bounds those fetch/stage operations, archive extraction/creation and
   packaging by the same remaining aggregate budget. Child commands still have
   their existing finite wait and process-group kill on exception. A final
   remaining-budget check precedes the success status. No timer guard was
   removed, nested/foreign active timers remain refused, and download retry
   limits/integrity/access checks remain intact.

The Steam suffix is14872 bytes, SHA-256
`646d9ade5f07dccf86504c86a0facad43218db2268247ba68c6d3d04b8fff862`.
The normal Steam bootstrap/cache contract, GUI guest/generator/awk and all23
original Steam source bindings remain unchanged.

## Preserved data and lifecycle boundaries

The original remains readonly, locked and absent from recovery VM argv. Full
backup/work copies and their hashes precede VM entry. Only the separate work
copy receives journal-only replay. The target is never mounted; strict readonly
full checks precede its final full digest. Counter reconciliation/general repair,
`-y`, formatting and dirty-bit clearing are forbidden. Unknown/counter/inode/
directory output refuses activation. Original backup remains after promotion.

Source/work identity, regular-file/link/owner checks, exclusive locks, fsync,
copy and atomic rename methods are byte-identical to the reviewed baseline.
The promotion body's only change is the additional failure/binding guard before
backup IO. Existing before/after-rename interruption regressions remain mandatory
on Apple. Normal ext4 validation, one-native-invocation ownership, retained worker
thread and clean-stop/unmount/loop-return/host-sync requirements remain intact.

Cancellation is checked at completed file-operation boundaries. A full12-GiB
hash/copy may delay cancellation; no immediate abort is promised. Guest/host
failure, Stop, timeout or fsync failure must prevent acceptance, and a native
owner retains locks until app exit. Steam guest deadlines stay finite:
60-second supervisor,900-second milestone inactivity,1800-second absolute limit.
Slow real hardware may time out safely; timings have not been calibrated there.

## Verification and unresolved acceptance

**611 Python tests completed OK,5 SKIP**. This includes actual generated shell
argument-validation execution and a real POSIX timer interrupting stalled cache
preparation before any build child/success. Existing payload-fetch diagnostic,
source/path/integrity, storage/lifecycle and process-group timeout tests pass.
Full81-file upstream restore,5 overlay patches,29 exact copies, unchanged source
pins and repeated real Linux/cache staging/package resource gates pass, including
the Python environment without hashlib.file_digest. AST/shell/git attributes pass.
Evidence: `experiments/linux-guest/evidence/steam-recovery-critical-review-20261019/`.

The mandatory Apple executable now requires
`LINUX_STEAM_RECOVERY_BINDING_PASS` in addition to
`LINUX_STEAM_RECOVERY_SCOPE_PASS` and existing GUI IO/lifecycle checks. It calls
production Swift parser/receipt/promotion code: missing/wrong/duplicate binding,
wrong source/nonce, counter milestones, late/duplicate DONE, old/mixed/failed
receipts, same-process activation and source lock contention. Promotion refusals
must occur before absent backup/work IO. It also checks report allowlisting and
that the sparse negative fixture's original header/guard survive. These are
executable checks in CI, **not executed Apple results in this Linux environment**.

**Apple compilation/execution, positive12-GiB QEMU journal replay and repaired
image promotion, power-loss recovery, iPhone UI/background/Stop/JIT/memory/cache
and owner-data acceptance: NOT RUN.** No Swift/xcrun/QEMU/e2fsck is installed here;
about1 GiB free after staging cannot support24 GiB of physical recovery copies.
No guard was relaxed and no real retained payload/user data was deleted to fit.
First phone recovery needs **24 GiB +512 MiB additional actual free space**;
a reusable fully verified backup later needs12 GiB +512 MiB. No APFS/sparse-copy
savings are assumed. A positive12-GiB fixture with retained source/backup digests,
strict fsck output, guest result and next-process promotion evidence remains an
acceptance blocker; do not describe owner recovery as ready from source tests.
BusyBox corresponding-source completeness remains **OPEN**.

## Exact next manual CI settings — no dispatch here

- Repository private `Mi-Yomi/iDeck`; branch
  `codex/steam-arm64-experiment-20261017`; exact reviewed remote HEAD of this
  change as `expected_commit` (40 lowercase hexadecimal characters).
- Workflow `ideck-linux-probe-ipa`, `mac_mini_m2`, Xcode27.0.
- Provider cap **24 minutes**; worker aggregate **1320 seconds /22 minutes**;
 2 minutes remain inside the provider cap for cleanup/artifacts. The coordinator's
  26-free-minute/paid-OFF snapshot would leave2 minutes beyond that cap, but is
  not a fresh quota check or an authorization to dispatch.
- Set `free_quota_verified=true`, `private_source_verified=true`,
  `native_build_approved=true` only after the coordinator verifies the current
  free balance covers the24-minute cap plus reserve, billing remains OFF and the
  selected SHA/private source are correct. The four inputs map to the existing
  EXPECTED_COMMIT/FREE_QUOTA_VERIFIED/PRIVATE_SOURCE_VERIFIED/NATIVE_BUILD_APPROVED.
- Existing `ideck-debian-payload` group and IDECK_DEBIAN_PAYLOAD_TOKEN only;
  unchanged real Linux/cache Release pins. No new token/secret or large payload.
- Require the new Swift marker, full real Husk Apple typecheck, native/app link,
  signature/packaging and verified artifact before any IPA delivery. A24/22-minute
  cold runner may run out of time; a timeout is failure, never a reason to bypass
  checks, increase paid usage automatically or claim an IPA ready.
