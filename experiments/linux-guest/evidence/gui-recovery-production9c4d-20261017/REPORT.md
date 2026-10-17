# Production9c4d recovery gate — PASS for exact158be791

The repository's existing two-cycle `check_gui_recovery.py --cycles 2` completed
with exit0 and empty stderr. Source/worktree/remote remained
`158be7910d1c372cdddbf7cb87706ad2ce69042f` on
`codex/linux-guest-feasibility-20261015`. **No tracked source or documentation was
changed; no commit, push or HEAD advance was made.** The separate Steam worktree
remains clean at `d0a8201f6495989fd5ab7c01e1bb17c7604747ca`.

This is the previously missing host recovery acceptance on the actual production
seed, not the old46fea run. Production input:1342177280 bytes, full SHA-256
`9c4d978f0ea33b608735e203c0e1695ca89188c02b097e610f971cffe1c05791`.
It was obtained from the owner's private Release asset650023557 through existing
`gh` access and the standard locked restore. Tar SHA-256:
`112bdba6e12ae182fb347e52e7368e26f748bb3dc2bcd77dbd3122fb14dcdedd`.
Preflight and postflight rehashed all five production GUI assets without change.

## Actual acceptance outcome

| Cycle | Result | Recovery VM elapsed seconds | Guest checked whole-image SHA-256, matched on host before promotion | Preserved interrupted original/backup SHA-256 |
| --- | --- | ---: | --- | --- |
| 1 | PASS | 63.260 | `5b717ed7b63090fe9b8da85f956582b20aaa9f65823c759f59bd100f302d7244` | `a604cce375b0bcc62ea5614524dc3424813d6d5e7fe2f828cd9cd7acea451a1b` |
| 2 | PASS | 67.410 | `e5e2591b68be89e468375db326f3af41d0f23ae86d612849cec2e4c0cd21f5cd` | `39832916ef6e7d13760982376df09f26e0c037d43ae1c2f2a440a3fb0fb95a4f` |

Both actual GUI force-kills returned-9 only after a complete nonce-framed sync
receipt absent from the terminal input. Both dirty headers had RECOVER set
(incompat198). Only disposable lab copies were interrupted; the production seed
was a read-only tools disk in recovery and was not the normal GUI write target.
Both recovery VMs emitted ordered assessment/replay, scoped summary reconciliation,
VERIFY0, SCAN_CLEAN, IMAGE_SHA256, DONE and clean-unmount receipts, then exited0.
No timeout or forced recovery shutdown was counted as clean.

The immutable guest tools and exact unchanged suffix bound the final complete
1342177280-byte image digest before promotion. The preserved original-1.raw and
original-2.raw still match each cycle's original digest; the existing strict
clean-header validator correctly refuses both dirty backups. They were not repaired,
replaced or deleted. The original production seed also remains unchanged.

The next QEMU process booted the promoted image. Cycle2 read cycle1's control file
before any new write, then created/synced cycle2's file. The final new GUI process
mapped the real GUI windows, reopened BOTH control files with a complete nonce
receipt, requested the standard Stop and confirmed clean unmount/QEMU exit0.
No synthetic shell echo was accepted as completion.

| Complete offline check | Tool exit | Strict output gate exit | Full unfiltered output | Output SHA-256 |
| --- | ---: | ---: | --- | --- |
| post-recovery-1 | 0 | 0 | [lab/fsck-1.log](lab/fsck-1.log) | `41950a3783c6bfb98e3f5bee1c19d032033f194f0092cb2077c2b9aab7f98588` |
| post-recovery-2 | 0 | 0 | [lab/fsck-2.log](lab/fsck-2.log) | `88c61da0d744f5d3b0b0d024540e893d3c31c18f1c19d9a4162343e268dc0d09` |
| post-final-GUI-Stop | 0 | 0 | [lab/final-fsck.log](lab/final-fsck.log) | `83e864b35333e62eaea063cd72a5fa55d54ef7b6875a125a71e5aa573635542c` |

All three checks ran after the corresponding writer had exited and retained all
five passes, exact target summary and version with no unapproved output. Exit0
with Fix?no would fail the unchanged repository awk gate. Postflight reevaluated
the saved complete streams using that same exact gate; no repair was performed.
Final active.raw SHA-256:
`f25d28f94581d2b48733387edce53a4d0152f45782974f2be51c8a25cfb5f236`.
Its strict header is clean: state1, RECOVER absent, orphan0, error_count0, valid
CRC32C. An additional read-only-descriptor host fsync after final Stop passed
without changing the final image hash.

## Exact inputs and restart boundary

The six host-proof source inputs are unchanged from the preceding reviewed digest
harness. Suffix15856 bytes, SHA-256
`af2591aaf362e150f80d66ccff1ca11acc6379f240e387e1667b51f70ec30ff5`.
All five runtime initramfs files exactly match the accepted base plus that suffix.
Host remains authenticated QEMU10.0.13/TCG, Cortex-A72/4vCPU/1024MiB/256MiB TCG,
software GUI and **-nic none**. No CPU, memory, timeout, network or security setting
was changed. Preflight available bytes were26417721344, above the
unchanged harness floor5637144576; no sparse savings were counted. All source
images, failed/historical outputs, installed Steam disks and caches remain present.

`full-app-restart-gate.json` records the unchanged native guards and the focused
**17/17 PASS** offline recovery regressions. Receipt-only finalization never
promotes or releases native ownership after QEMU loop return. Promotion still
requires a different process UUID, exclusive locks, original/backup identities,
recorded guest digest and complete host work hash before durable atomic rename.
The one-qemu_init/retained-owner-thread and full-close/reopen UI requirements remain.
These are source/regression checks here; the Linux host harness runs separate QEMU
SUBPROCESSES and does not execute the Apple embedded runtime or native Swift
transaction. The owner separately reported Swift recovery/startup regressions and
an IPA built for exact158be791 in Codemagic build6ad367417550aed8108f8f4f. No CI
was dispatched or rerun here, and no source change invalidates that existing IPA.

The external read-only observer began during recovery1, after the first GUI
process had already exited. It recorded four later distinct QEMU PIDs and their
exits, including both recovery processes, GUI2 and final GUI. The first GUI's
actual kill/nonce proof comes from the unchanged harness and its complete serial
log, not from invented observer coverage. No observer signal or configuration
change occurred. At completion no task QEMU or image mount remained.

## Deliverables and remaining limits

- [Original unmodified harness receipt](lab/receipt.json)
- [Independent postflight, complete hashes and preservation checks](postflight.json)
- [Native restart guard review and explicit runtime scope](full-app-restart-gate.json)
- [Input, host-tool and storage receipts](preflight.json)
- [Exact command/exits](execution.json), [17-test log](focused-tests.log)
- Full serial/control/qemu logs under each `lab/gui-*`, `lab/recovery-*` and
  `lab/final-relaunch`; frozen exact source inputs under `frozen-sources`.

Private raw images stay in this selected workspace only; nothing was published.
Steam disks retain hashes1f6816b0…253415 and462a5804…a11e3; all17 client ZIPs and
45 dependency packages rehashed unchanged. Steam networking remains blocked and
was not retried. No main/Steam/GUI branch mixing, merge, payload publication,
Codemagic or network/security change occurred.

**Production9c4d HOST QEMU recovery gate: PASS.** Source fixes were not needed.
Phone recovery/UI gestures, device memory/JIT/embedded-QEMU lifetime and GPU
acceleration are **NOT RUN by this host gate**. The owner's interrupted phone
image was not accessed or recovered; unsynced/uncommitted writes are not promised.
