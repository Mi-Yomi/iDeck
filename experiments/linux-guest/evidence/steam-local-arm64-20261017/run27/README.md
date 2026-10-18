# Run27: bounded desktop navigation and Big Picture rendering

Actual local ARM64 QEMU observation, 4096 MiB / four vCPUs. Store → Library →
Store → Library was visually verified. Big Picture showed instructional tips,
main Home and a game-detail view. Full Big Picture menu/return navigation,
repeat-launch stability, Steam/Proton games and iPhone remain unverified.
Black transition frames are recorded as transitions, not successful UI checks.

The clean source was run25; interrupted run26 was not reused. Run27 added the
stock CEF hang-timeout flag, with actual browser argument proof. A later,
separately recorded one-shot phase widened 95 owned browser threads from CPUs
2–3 to 0–3. It does not isolate the contribution of each condition. Native IPC
remained 500 ms, V5 lazy-zero was active and the sandbox remained enabled.

The original 1503.935 s monitor and 331.751 s continuation both ended by their
own budgets. There was no kernel OOM or browser-unresponsive termination message.
The minimum available RAM over both phases was 1927896 KiB. Maximum sampled
SHM use was 159047680 bytes in the main phase and 110493696 bytes in continuation.
Eight real stream-zero events included seven guarded lazy operations and one
ordinary fallback. See `ui-log-summary27.json` for current parsed log metadata;
the older `ui-stage.json` source-name regex missed timestamp-prefixed CEF lines.

Fresh original ARM64 checker/fallback fixtures passed before Steam. The new
cross-process IPC test was added during this run: ordinary and preload-fallback
ARM64 cases passed, including an observed blocked shared-futex wake. The first
test location was root-only and failed before execution; it was corrected without
loosening that directory. Other recorded harness errors concern receipt parsing
and a post-click active-window query; their corrected results are retained.

Application shutdown completed normally without SIGTERM/SIGKILL. Original VM
Stop returned QEMU0, all four client ELF hashes remained unchanged, package audit
was empty and no private namespace holder remained. Full offline fsck on a copy
passed five phases plus summary; source hashes before/after matched. The input
mount was normally unmounted and its keeper exited. See the JSON/log receipts.

Screenshots and raw account logs remain private. `screen-stage-receipt.json`
contains image hashes and reviewed observations only. Scripts containing embedded
ELF payloads are excluded. The render-only profile tool produces the exact tested
launcher/helper hashes, with four source tests and separate real-library CLI
checks. It does not install a normal/iOS launch profile.
