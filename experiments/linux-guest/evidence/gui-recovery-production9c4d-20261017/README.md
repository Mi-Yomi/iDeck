# Production9c4d recovery host acceptance — PASS

**Tested runtime/source commit:**
`158be7910d1c372cdddbf7cb87706ad2ce69042f` on
`codex/linux-guest-feasibility-20261015`.
The owner accepted this result before authorizing this documentation/evidence
checkpoint. No runtime, guest, native source, CI, payload, asset lock or signing
configuration changed. Later documentation HEAD is not the IPA's tested source SHA.

The unchanged `check_gui_recovery.py --cycles 2` ran against the actual restored
production seed,1342177280 bytes / SHA-256
`9c4d978f0ea33b608735e203c0e1695ca89188c02b097e610f971cffe1c05791`.
The seed came from authorized private Release asset650023557 via existing `gh`
access; its292065280-byte tar SHA-256 is
`112bdba6e12ae182fb347e52e7368e26f748bb3dc2bcd77dbd3122fb14dcdedd`.
The standard locked restore and final rehash verified all five GUI assets.
The old46fea seed was not substituted.

| Acceptance | Result |
| --- | --- |
| Two nonce-confirmed sync → actual GUI SIGKILL cycles | PASS; both exits-9, dirty RECOVER headers |
| Copy-only scoped recovery | PASS;63.260s /67.410s, both recovery exits0 |
| Guest whole-image digest matches work before promotion | PASS in both cycles |
| Interrupted originals/backups preserved | PASS; both retained hashes verified |
| New GUI process, previous control file read before writes | PASS |
| Final new GUI, both files reopened, clean Stop/QEMU exit0 | PASS |
| Complete offline fsck after each recovery and final Stop | 3 PASS; exit0 AND strict full-output gate0 |
| Focused unchanged recovery regressions | 17/17 PASS |
| Native full-app-restart source guard retained | PASS; source/regression scope, not new Apple execution |
| **Phone recovery** | **NOT RUN** |

Final disposable `active.raw` SHA-256:
`f25d28f94581d2b48733387edce53a4d0152f45782974f2be51c8a25cfb5f236`.
Host fsync after final Stop passed without changing it. No task VM or mount
remains. Both Steam disks,17 client ZIPs and45 dependency packages rehashed
unchanged. Network/security settings and the blocked Steam network remain unchanged.

## Evidence

- [Original frozen acceptance report](REPORT.md): full cycle/work/backup hashes,
  times, limitations and private-lab paths.
- [Original harness receipt](lab/receipt.json), [exact invocation/exits](execution.json),
  [input/storage/tool/source identities](preflight.json).
- [Independent postflight](postflight.json), [full-app-restart guard review](full-app-restart-gate.json),
  [17-test log](focused-tests.log).
- Complete unfiltered fsck outputs:
  [cycle1](lab/fsck-1.log), [cycle2](lab/fsck-2.log), [final Stop](lab/final-fsck.log).
  Each has all five passes, target summary and version, with no Fix?no or
  unapproved output. Exit0 alone was never accepted.
- Full serial/control/QEMU logs under `lab/gui-1`, `lab/recovery-1`, `lab/gui-2`,
  `lab/recovery-2` and `lab/final-relaunch`; independent read-only process events
  and summary are also retained.
- [Publication provenance](publication-provenance.json) binds exact protected
  runtime Git objects and the accepted original report/receipt/private manifest.
  [Compact manifest](manifest.json) pins the exact bytes in this directory.

`REPORT.md` is preserved byte-for-byte from the report returned BEFORE publication;
its no-commit/no-HEAD-advance statements describe that test checkpoint. The full
private lab still holds disks, generated initramfs and frozen source copies at
`/workspace/gui-recovery-production9c4d-158be791-20261017` in this environment.
This compact Git package omits those binaries and duplicated source snapshots.
Their hashes remain in `preflight.json` and
`original-private-evidence-manifest.json`; exact source is available at158be791.
The original private manifest describes that original wider snapshot, while
`manifest.json` describes only this compact publication.

The process observer started during recovery1 and saw four later distinct QEMU
process lifetimes; it did not invent coverage of the already-finished first GUI
process. That first force-kill is supported by the actual harness receipt,
non-echoable completed serial nonce and mounted dirty header.

The owner reports the existing IPA and Swift recovery/startup tests passed in
Codemagic build `6ad367417550aed8108f8f4f` for exact158be791. No CI was dispatched
or Apple runtime reexecuted here. This documentation-only commit does not require
a rebuild to include runtime fixes. Phone recovery, embedded Apple QEMU lifetime,
device memory/JIT behavior and GPU acceleration remain outside the host proof.

Exact owner UI sequence: [recovery on the existing IPA](../../GUI-RECOVERY-OWNER-158be791.md).
