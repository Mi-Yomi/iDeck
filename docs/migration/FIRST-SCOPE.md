# Minimal first migration scope

No iDeck code is copied by the import. Existing BCD runtime is preserved.

1. Before execution: quarantine upstream destinations. Keep local feedback and
   diagnostics; disable log/feedback HTTP, auto-updater and remote recommendations
   until our destination, trust key, consent and privacy policy are deliberately
   chosen. Keep built-in recommendations. Do not repoint user data to a guessed
   endpoint. Review archived OTA tooling; design a manual build-only workflow
   later, with zero upload/publish/signing steps and a separately approved budget.
2. Reuse BCD's library and launch/session model as the simple launcher. Start with
   one installed-game primary action, visible launch state and an actionable,
   bounded failure reason. Preserve authentication/ownership/DRM, per-game setup,
   prefix data and actual JIT/memory gates. Avoid a second launcher state machine.
3. Reuse BCDJIT/BCDJITLive and JITSetup: display current JIT/readiness inline,
   route to existing setup, recheck on return, require explicit launch after the
   recheck. Never infer JIT PASS from a successful tap or an entitlement alone.
4. Keep HardwareInput.releaseAll, GamepadInput and PadKeyboardMouse focus and
   disconnect cleanup. Audit routes, keyboard/text focus, session overlay and
   scene transitions; add a regression only for a demonstrated gap. These
   release paths already exist, so porting our QEMU input implementation adds
   risk without a demonstrated benefit.
5. Add a local diagnostic Markdown renderer through BCD's existing session
   states. Allowlist source/build identity, OS/device class, real JIT check,
   launch/setup phase, fixed error code and stop state; distinguish UNKNOWN,
   attempted and proven outcomes. Bound values and escape Markdown. Exclude raw
   logs/argv/paths, arbitrary error text, account IDs, tokens, pairing records,
   credentials and unknown fields. Export only after a user action; never upload
   to the inherited author intake. Test exact rendered rows using production
   Swift code when execution is authorized, not only source-string checks.

Suggested first implementation change: disable inherited outbound services and
add the local-only status/report surface; leave the native engine/submodules
unchanged. The launcher/JIT/focus work then changes only confirmed gaps in the
existing BCD UI. All resulting app/build/device tests require separate execution
authorization. No build-time or speed estimate is an acceptance result.

Excluded: copying Linux ext4/QEMU/rootfs/cache/recovery code; converting old user
VM disks; replacing Wine/FEX/DXMT; bundling Valve/account data; bypassing Steam
ownership/DRM; claiming Big Picture from Dock; native dependency rewrites; CI or
paid capacity. Full Steam UI is a separately scoped, separately measured project.
