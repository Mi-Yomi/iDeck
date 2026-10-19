# One environment launcher — source candidate, 19 October 2026

Based on `7fdb81605c117fdc03dba8c7dd9fc4dc80beda77`, on the Steam branch only.
The delivered CI#39 IPA was built from `bcbb8db7c909d34f05ccdf6ec95675f26f29ed78`
and predates this change. No new IPA, Apple execution or device acceptance is
claimed here. This task did not start Codemagic or change a Release.

## Owner flow

The launcher has one primary action, **Запустить среду**, and Settings. Start
uses the existing Steam session, `iDeckSteam-v1` disk, verified bundled cache,
fresh JIT/memory preflight and existing one-QEMU ownership guard. Network consent
and JIT setup remain explicit owner actions; no preview starts a VM. Returning
from setup continues only a pending explicit Start in the foreground. Repeat
presses cannot create another session. Steam login and agreements remain manual.

After actual `IDECK_DESKTOP_READY`, with the console and readonly cache ready,
the same worker sends INSTALL once. Only `IDECK_STEAM_INSTALLED` advances to
BIG_PICTURE once. Missing/corrupt assets, guest blockers and uncertain command
timeouts retain their errors; no automatic retry, disk replacement or GUI
recovery is performed. A definitive blocker permits explicit retry in Advanced
Settings. A launch-request receipt acknowledges the command, not a rendered
window; a healthy long-running Steam process need not exit within180 seconds.

Home and **Продолжить среду** retain the same preparation, worker and disk.
Settings/Advanced expose diagnostics and the old GUI/terminal/Debian/test routes;
legacy disks are preserved without migration. Ownership remains sticky after an
attempt, failure or Stop. The separate confirmed Stop uses the original guest
shutdown, drain/unmount, fsync and native lifetime machinery; a new VM still
requires reopening iDeck. Backgrounding retains the existing preparation-cancel
and input-release behavior; it does not stop a running VM.

The active screen keeps the guest display, compact keyboard/controls actions
and safe Stop. Existing pointer, physical/software keyboard, modifiers and
multitouch key ownership/release-all are reused. Screen controls send keyboard
and mouse events; they do not expose a Linux HID gamepad.

## Guest receipt ordering

The sealed original guest source and payload remain unchanged. The existing
derived offline-cache runtime overlay now closes its action-lock ExitStack
after the installer and cache context finish, before emitting INSTALLED. This
prevents automatic launch racing the just-completed installer lock. Generated
own-code cpio suffix: **12988 bytes**, SHA-256
`a2e0ffbbc253ba6d08a4e3d2991cea557552b6b78e9cb8431a6d76ef76cf15a9`.
The Swift contract is regenerated exactly from that source.

The regression executes the actual derived Python action with a synthetic
installer and cache context, using a real `fcntl` lock. At the success
receipt a second file descriptor must acquire that lock; installer failure must
emit no success receipt and must release the lock. This is lock-order evidence,
not execution of the real Valve installer or a device VM.

## Verification and boundaries

`python3 -m unittest discover -s experiments/linux-guest/tests -v`:
**591 tests, OK, 5 SKIP** in a real Git checkout. Full source restoration
(81 pinned upstream files), five patches, exact overlay copies, unchanged Theme,
generated contracts, real Linux and cache staging/repeat/resource verification,
142 Python AST checks, recovery shell syntax and Git binary attributes PASS.
The standalone staging checks also run without `hashlib.file_digest`.
Evidence: `experiments/linux-guest/evidence/unified-environment-20261019/`.

All23 original Steam source bindings, base kernel/initramfs/raw locks, bundled
cache lock, GUI/Debian/terminal payloads, recovery/disk helpers and native
ownership/lifetime implementation remain unchanged. No user disk was accessed.
The cache remains379228160 bytes, SHA-256
`a75ea9bb8a19946cf81b2fb3d6cc4db97db6a1fe0938e4f23857c2c6e826adef`,
asset655626057; no new payload or cache upload is needed.

New Swift/iOS typecheck, integrated Husk/native build, visual layout,
device Home/Resume/Stop, automatic real installation, Steam rendering and
gameplay: **NOT RUN**. The new pure Swift launch/state fixtures are mandatory
in the next Apple check, marker `LINUX_UNIFIED_ENVIRONMENT_PASS`, alongside
`LINUX_STEAM_BUNDLED_CACHE_PASS` and `LINUX_STEAM_SCREEN_CONTROLS_PASS`.
Disk12 GiB and experimental Auto memory cap4096 remain unverified on device.
Known incomplete BusyBox corresponding-source provenance remains **OPEN**.

## Next manual CI — coordinator only

Review the pushed commit and use private `Mi-Yomi/iDeck`, branch
`codex/steam-arm64-experiment-20261017`, workflow `ideck-linux-probe-ipa`:

```text
expected_commit=<full newly reviewed remote HEAD>
free_quota_verified=true
private_source_verified=true
native_build_approved=true
```

Provider: `mac_mini_m2`, Xcode27.0, **70 minutes**; worker total native budget
**3900 seconds (65 minutes)**, including its existing preflight time accounting.
Coordinator's 09:15 UTC snapshot was79 free minutes, paid OFF, no active build:
9 minutes beyond the provider cap. Recheck actual remaining free quota with
reserve and paid OFF immediately before one manual dispatch. The previous
cap95 instructions are historical. Existing group `ideck-debian-payload` and
`IDECK_DEBIAN_PAYLOAD_TOKEN` serve both pinned private assets through existing
code; no secret or workflow authentication setting changed. Other workflows
are unchanged. This executor dispatched no CI.
