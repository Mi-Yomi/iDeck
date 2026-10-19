# Steam branch: restore GUI recovery and failure diagnostics

Apple CI completed successfully for **built SHA
9018b9bfbaab7b50d6011ae1e29e5eba0995fd28**:
https://codemagic.io/app/6ad03ce9a8a969b53f3a4aa9/build/6ad570cd7550aed8108ffb95 .
Provider status: **Build finished**. Runtime link, Apple source/host checks, full
app build and IPA packaging **PASS**. Actual host markers:
`LINUX_GUI_RECOVERY_PASS`, `LINUX_STARTUP_PREPARATION_PASS`,
`LINUX_STARTUP_FAILURE_PASS`, `LINUX_EXT4_DIAGNOSTICS_PASS`.
Markdown renderer: **318 assertions PASS**.

Delivered recovery IPA: **710726196 bytes**, SHA-256
**95b7a07a6379a32fd80bb8fc256d3de5eba8f3c6341a7ffa7f541c17b712b38a**.
Downloaded IPA CRC/hash, seven arm64 iPhoneOS Mach-O/ad-hoc checks and all 19
resource pins **PASS**. Private owner-only Drive delivery is complete; no personal
Drive link is included. Results are supplied by the coordinating delivery
executor; this documentation-only session performed no IPA download or CI run.
The subsequent **docs SHA is not the built SHA** above; no code/payload/overlay
changes accompany this delivery record.

Baseline: `ff39aaf43afa4a6805c7e05d2d1a754a2865c901`, only
`codex/steam-arm64-experiment-20261017`. The reported screen says Debian desktop
and shows the old offline-ext4-recovery refusal. The screenshot does **not**
establish installed source SHA or actual filesystem corruption. No phone disk
was accessed, repaired, replaced or reset in this work.

The Steam and GUI branches share ancestor `27e9736f35ffb7c572e2fa81c75458ee1d1b8ff9`.
The GUI recovery/diagnostics work at `7e3235e8a533112fb543855d7aded2502f50b5c9`
was never integrated into this Steam branch. The later GUI head
`3718c9f627c7d5791988aa47108513ae895b1167` was also reviewed; its unrelated
keyboard changes are outside this fix.

The exact old message comes from `LinuxTerminalWorker.start()` catching
`LinuxDesktopDisk.Invalid.needsRecovery`. That guard rejects a validated ext4
header with RECOVER set, state != 1, nonzero last_orphan or error_count. The
message previously asserted an unclean-shutdown cause without recording which
field triggered it. The failure screen offered Share report only at the bottom
of scrollable controls, and only if a session Markdown file was available.

The fix restores the existing GUI-only transaction and its bounded recovery VM,
watchdog, preparation cancellation and late-callback failure guards. Its core,
guest script, strict fsck/scope parsers and generator are byte-identical to the
reviewed GUI reference. The original stays protected and is never attached to
the recovery VM: full verified original/work copies are required, with space
for two copies plus 512 MiB reserve. Journal-only replay operates on work;
strict read-only fsck output, checked image SHA-256, clean guest exit and host
fsync are required. Promotion is possible only in a fresh app process after
exclusive owner-lock checks and revalidation. The original backup is retained.
Normal GUI start can enter this one-use recovery VM when its preboot dirty
gate refuses; Recover disk also selects it explicitly before any native start.
Neither path boots the desktop in that same recovery process.

Share report and Diagnostics now remain in a fixed top bar, independent of
JIT/readiness/input/Stop. Current attempt and saved startup reports are distinct.
Only bounded numeric ext4 observations and allowlisted errors are exported.
Startup failures no longer diagnose corruption or a shutdown cause from a flag.

A separate proven Steam dispatch bug is fixed: report hashing now selects
`steam-profile.json` before the desktop fallback. Steam reports identify their
mode and preserve its import/dirty-state diagnostics. Steam's 12 GiB disk and
Debian console remain outside GUI recovery: dirty disks refuse safely and offer
diagnostics. No GUI transaction is allowed to act on the Steam UUID/size.

Payload/GUI/Debian/Terminal locks and all 23 Steam source bindings are unchanged.
Only app/overlay sources change; the GUI runtime initramfs suffix is generated
from the existing recovery source without altering the accepted bundled payload.
The source-fix session performed no Release, secret, main, CI dispatch or
user-data migration change; the subsequent Apple CI result is recorded above.

Validation: **538 Python tests OK (533 PASS, 5 SKIP)**, including real AWK/output
gates, generator/CPIO checks, git attributes and full source-overlay regressions.
Actual sealed Steam asset staging/repeat and its package resource verifier pass
without `hashlib.file_digest`. The mandatory Apple gate now includes real Swift
IO/locking/interrupted-promotion/relaunch checks plus repeated dirty Steam opens,
byte preservation and rejection by GUI recovery. Apple source/host checks and
native IPA now **PASS** for the built SHA above. New guest boot, UIKit
layout/share-sheet and phone recovery execution remain **NOT RUN**.
Imported old-cloud receipts retain their historical scope; they do not establish
new device acceptance. BusyBox source provenance remains **OPEN**.

The recovery IPA has been delivered. Preserve the installed app/data while
updating; the previously installed source version remains unknown. Steam 12 GiB
recovery remains fail-closed outside the GUI-only transaction. The device
report must establish source/build/mode, storage failure, ext4 observations and
recovery phase/result before declaring this particular device problem resolved.
