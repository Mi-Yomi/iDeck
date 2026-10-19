> CURRENT SOURCE CORRECTION — stable Steam cache device identity, 19 October 2026.
> Based on `460d5f260089e0c9f0a62d0049a6ee04b9e78468`. Coordinator-inspected
> device screenshot10:51 UTC shows `offline_cache_not_readonly`; this is separate
> from RAM/JIT feedback. The old guest guessed `/dev/vdb`, although ARM virtio
> disk order is unstable and root is already found by UUID. New argv supplies a
> cache serial; the guest selects its unique identity, checks major/minor, then
> still requires actual RO=1, exact size and all pinned bytes. Device mapping
> on the owner's phone remains unmeasured; no real host QEMU result is claimed.
> **599 Python tests OK /5 SKIP**, full overlay and real repeated staging PASS.
> New Apple/Swift/phone acceptance **NOT RUN**. Base payload/cache, native worker,
> user disks and safety guards unchanged; no Release or payload rebuild needed.
> CI#41 on460d5f26 was coordinator-reported running and lacks this correction.
> No parallel/new CI started here; recheck fresh remaining quota and paid OFF
> before any future manual run. Current cap55/worker50 remains unchanged.
> BusyBox provenance **OPEN**. [Cause, safety and evidence](STEAM-CACHE-DEVICE-IDENTITY-20261019.md).

> CURRENT SOURCE CORRECTION — launcher memory/JIT feedback, 19 October 2026.
> Based on `c810b682601634920e8ff601b6832c08524896e9`. The coordinator inspected
> the owner's screenshot: manifest/JIT/network PASS, **Auto memory preflight
> BLOCKED** before native entry. This proves click handling reached preflight;
> hit testing/JIT failure is not established. Actual numeric budget is unknown.
> The new source shows measured process budget/minimum and offers the existing
> fixed1536 mode with fresh checks. Reserves and native/disk safety are unchanged.
> JIT off shows an inline setup action; returning rechecks real JIT and offers
> explicit continuation, without auto-starting a VM or leaving a pending spinner.
> **595 Python tests OK /5 SKIP**, exact full overlay/real repeated staging PASS.
> New Apple/Swift/UI and phone behavior **NOT RUN**; CI#40 below predates this fix.
>
> Next manual CI: reviewed post-fix remote HEAD, `ideck-linux-probe-ipa`,
> `mac_mini_m2`, Xcode27.0, **cap55 / worker50 minutes**. Supplied62-minute free
> snapshot leaves7 minutes beyond cap; freshly verify quota/reserve and paid OFF
> before dispatch with the existing four approval inputs. No CI started here.
> BusyBox provenance **OPEN**. See [cause, changes and evidence](LAUNCHER-JIT-MEMORY-FEEDBACK-20261019.md).
> Older wait/cap70/65/95 and JIT-return instructions below are historical.

# One environment launcher — delivered CI#40, 19 October 2026

Implementation baseline: `7fdb81605c117fdc03dba8c7dd9fc4dc80beda77`, Steam branch.
**Delivered built source: `cf773c48e4c11d9c341667cb55e5b40522655df8`.**
Apple [CI#40](https://codemagic.io/app/6ad03ce9a8a969b53f3a4aa9/build/6ad5e8747550aed8109013fd)
**PASS,16m44s**, including `LINUX_UNIFIED_ENVIRONMENT_PASS` in mac-tests.log.
IPA **1086777985 bytes**, SHA-256
`9c8565f28f8a25cd81109a74562f4bf915c532095b2605b4f8f0f8f7b5e8c7c0`.
Coordinator independently verified ZIP CRC, resources/cache and all7 Mach-O
binaries as arm64 iPhoneOS ad-hoc, then delivered it through owner-only Drive.
The personal Drive link is not stored in Git. These CI/artifact/delivery facts
are coordinator supplied; this documentation update did not download or rebuild
the IPA, change code/payload/pins/secrets, start CI or modify a Release.
The previously delivered CI#39 build predates this launcher.
**iPhone NOT RUN; wait for owner feedback.**

## Owner flow

The launcher has one primary action, **Запустить среду**, and Settings. Start
uses the existing Steam session, `iDeckSteam-v1` disk, verified bundled cache,
fresh JIT/memory preflight and existing one-QEMU ownership guard. Network consent
and JIT setup remain explicit owner actions; no preview starts a VM. The latest correction rechecks JIT after setup and asks for another explicit
Start; it does not start a VM on return. Repeat
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

The local evidence above records the pre-CI source verification; its Apple
NOT RUN fields are historical. The subsequent coordinator-reported CI#40 passed
and confirmed the new pure Swift launch/state marker
`LINUX_UNIFIED_ENVIRONMENT_PASS` in mac-tests.log. Existing bundled-cache and
screen-controls markers remain mandatory; no check was removed.
Visual layout on iPhone, device Home/Resume/Stop, automatic real installation,
Steam rendering and gameplay remain **NOT RUN**. CI success and package
inspection do not establish these device results.
Disk12 GiB and experimental Auto memory cap4096 remain unverified on device.
Known incomplete BusyBox corresponding-source provenance remains **OPEN**.

## Historical CI#40 delivery budget checkpoint

Latest coordinator snapshot after CI#40: **62 free minutes, paid OFF**.
The current `ideck-linux-probe-ipa` provider cap is70 minutes and its internal
worker budget is3900 seconds (65 minutes); **neither fits that remainder**.
Do not reuse the earlier79-minute snapshot or dispatch another run with the
current cap. This docs-only update leaves those code/config limits unchanged.
A future build needs a separately reviewed suitable provider/internal limit,
fresh free quota with reserve, paid OFF and private/native approvals. Then use
`expected_commit=<full newly reviewed remote HEAD>` and the existing
`free_quota_verified`, `private_source_verified`, `native_build_approved` inputs.
No new run or cancellation was performed here.

The existing `ideck-debian-payload` group and `IDECK_DEBIAN_PAYLOAD_TOKEN`
remain unchanged. Delivered build source stays `cf773c48e4c11d9c341667cb55e5b40522655df8` even when this later
status-only documentation commit changes branch HEAD.
