> Historical CI43 correction. CI44 on the correctedc21eb465 source subsequently
> passed all27 Swift checks and produced the delivered IPA; see
> [current delivery evidence and acceptance limits](STEAM-DEVICE-DELIVERY-20261018.md).
> Positive12-GiB recovery/device acceptance remains NOT RUN;4 free minutes now
> block new full CI runs. The23/21-minute configuration is unchanged.

# CI43 report regression correction — 19 October 2026

CI43 ran exact source `a669a3977c551fdaad7a4830dec116ec53660d9d`:
https://codemagic.io/app/6ad03ce9a8a969b53f3a4aa9/build/6ad6134b7550aed810902191 .
Coordinator supplied: ios-typecheck/native-syntax/mac-compile PASS, mac-tests
FAILED with exit−5. Its raw log contains exactly
`main/MarkdownReportChecks.swift:15: Precondition failed`.
Integrated Husk checking was not reached; no IPA exists. The run/log facts are
coordinator evidence, not a new local Apple run or independently fetched log.

At that exact commit, line15 required both RECOVER SET and the obsolete prose
`GUI recovery does not apply`. The renderer had already been updated for explicit
copy-first Steam recovery in0f413a85; it instead explains eligible journal-only
replay and requires a reported result. The old test expectation was not updated.
The actual row/prose mismatch explains the reported assertion without disabling
any runtime/storage guard or changing the renderer to repeat obsolete advice.

The fixture now separately retains RECOVER SET, checks the current explicit
copy-first/journal-only restriction and unestablished device acceptance, and
requires UNKNOWN recovery phase/source verification for a mere preboot refusal.
Self-review found another fixture mismatch before the next run: checking_source
passes through the renderer's existing Markdown escaping and is emitted as
`checking&#95;source`. Both renderer and Steam binding fixtures now check that
actual escaped table value. Redaction, unknown/false distinctions, source/nonce,
receipt and production recovery assertions remain mandatory.

**611 Python tests completed OK,5 SKIP**. Fresh81-file source restore,5 patches,
29 exact overlay copies, all23 Steam source bindings, existing real staged
Linux/cache resource verification, AST and git attributes PASS. All packaged
runtime/overlay sources and payload pins are byte-identical to a669a397.
Evidence: `experiments/linux-guest/evidence/steam-ci43-report-fix-20261019/`.
Local source-contract checks do not execute the Foundation renderer. No Swift
compiler/Apple SDK is installed here: new Apple compilation/execution **NOT RUN**.
The prior typecheck/compile PASS does not establish a corrected host-test PASS.
Positive12-GiB recovery/promotion and phone acceptance remain **NOT RUN**;
BusyBox corresponding-source completeness remains **OPEN**.

The coordinator's fresh balance is25 free minutes, paid OFF. As requested,
only the dedicated workflow's provider cap changes24→**23 minutes**, and its
aggregate worker22→**21 minutes /1260 seconds**. This leaves2 minutes inside the
provider cap for cleanup/artifacts and2 minutes beyond the cap in that supplied
snapshot. Existing finite POSIX IO timers, aggregate budget accounting, child
process-group termination, final success guard and approval/source checks remain.
Actual slow preparation/download interruption tests pass. A cold build can still
time out; this is failure, not permission to skip checks or use paid capacity.

No CI dispatched here. Next manual run, after a fresh quota/reserve/paid-OFF
check: private Mi-Yomi/iDeck, branch codex/steam-arm64-experiment-20261017,
workflow ideck-linux-probe-ipa, mac_mini_m2, Xcode27.0. `expected_commit` must be
the exact reviewed remote HEAD containing this fix. The other inputs remain
`free_quota_verified=true`, `private_source_verified=true`,
`native_build_approved=true` only after those verifications. Existing
ideck-debian-payload /IDECK_DEBIAN_PAYLOAD_TOKEN; no new secrets, payload rebuild,
Release update or user-disk operation. Full mandatory Apple host regressions,
including MARKDOWN_REPORT and Steam recovery scope/binding markers, real Husk
typecheck, native/app link and verified packaging must pass before IPA delivery.
