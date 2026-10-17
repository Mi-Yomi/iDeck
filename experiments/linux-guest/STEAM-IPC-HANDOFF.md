# Steam IPC diagnosis and online handoff — 2026-10-17

## Night continuation — updater restart and native game checks (2026-10-18)

Run18 observed a real Steam self-update finishing with exit code 42. The old
launcher treated that restart request as failure. The source launcher now retries
at most twice while holding its lock, revalidates the client and refuses a retry
if an old client remains. Three focused tests cover these cases; 32 targeted
launcher/namespace/bootstrap/game-inventory tests pass. The automatic retry path
has not yet been triggered by another real updater run. Big Picture now requests
`-gamepadui` without the SteamOS first-boot flags.

The private V3 diagnostic run reached Big Picture's “Logging in” screen. Login
completed successfully at 22:12:40 UTC; the earlier narrow auth probe missed that
marker. The UI then remained black and its window disappeared. This is not a
working Big Picture/navigation result. The renderer disappeared after sampled
available memory fell to 162,564 KiB, but an OOM kill is not proven. Collect kernel
and renderer-exit evidence before attributing the failure or changing resources.
The stack-safe V3 probe remains diagnostic-only; never use rejected V2.

A separate authenticated Debian ARM64 XGalaga package was installed after Steam
cleanup, preserving all existing package versions. Two launches reached gameplay
with keyboard input; the second actual frame shows score 100. Both exited through
the game's quit key with code 0, without forced signals. These short 70/39-second
checks establish native X11 game/input/relaunch behavior only: not Steam/Proton
compatibility, audio, measured FPS, GPU acceleration or iPhone performance.

Run18 completed the original guest unmount → QEMU0 → host fsync path. All four
client ELFs remain unchanged, no private namespace/game owners remain, and dpkg
audit is clean. Post18 full offline fsck passed all five phases plus summary with no errors;
exclusive ownership and unchanged source SHA before/after were verified.
Run18 preboot's full strict check of run17 passed all five phases and summary.
Sanitized receipts and procedures: `experiments/linux-guest/evidence/steam-local-arm64-20261017/run18`.
Account logs and screen pixels remain private outside Git. Available iPhone
internal storage is still a separate implementation task, not an enabled feature;
see `STEAM-IOS-INTEGRATION.md` for the existing fixed-size disk constraints.

## Local ARM64 continuation — 2026-10-18 (latest)

**V3 correction (latest): V2 is rejected for further Steam runs.** Its C
syscall wrapper broke AArch64 custom-child-stack clone semantics. A real guest
regression passes with libc, gives SIGSEGV in the controlled V2 test child, and
passes with V3's stack-preserving non-futex tail entry; real/raw fallback and
ordinary ABI cases also pass. Earlier narrow ABI tests missed this case. This
is not evidence of a Steam crash, and V2's later UI hangs cannot be attributed
to upstream Steam from these runs. Current source/library hashes and the
rejected historical version are documented in `diagnostics/ipc-connect-wait`.

Run15 restored the user's login automatically and reached native login/library
readiness, but the desktop main window stayed on its loading screen. Closing
Special Offers raised an unresponsive-window prompt; it was cancelled and the
popup minimized, without End Process. A same-client Big Picture URI was
forwarded successfully, but no Big Picture interface was observed. Kernel OOM
count was zero; about600MiB was available and sampled reclaim counters did not
advance. Run15 then completed original unmount/QEMU0/fsync after controlled app
cleanup. Run16 changed only V2 to V3 forwarding, with desktop/resources preserved.
The actual V3 frame gate passed and its first connect woke after177.170713ms.
Saved login persisted. A real QMP frame shows the main Steam Store content
and publisher artwork, after a long blank-content phase. Library navigation
and Big Picture remain unverified: fixed native URI requests were forwarded,
XTest clicks injected, but no visible Library/menu/BP response was confirmed.
Later the main windows disappeared and X BadWindow was logged. Service Worker
not responding is an observed earlier symptom, not a proven cause. No account
pixels or raw post-login logs enter Git. Controlled app cleanup required
native SIGKILL; original VM Stop then completed unmount/QEMU0/host fsync.
All four client ELFs are unchanged, no private namespace holders remain and
dpkg audit is empty. Full post-run15 fsck passed strictly (all five passes).
Run17 tests removal of the diagnostic preload with the original helper,
launcher, native500ms and unchanged resources; its preboot full fsck checks
the clean run16 disk before any new writer. This is not yet a successful BP
or navigation result. See run16/screen-stage-receipt.json in local evidence.

The owner resumed local work. Run14 **reached the real Steam Big Picture
sign-in screen**, verified from a QMP screenshot, then refreshed its QR through
actual XTest mouse input. The user scanned/approved it; the final authenticated frame is Steam Deck's
Welcome language wizard. Main/library UI and navigation remain pending.
QR/account screenshots are private on E:, never public Git evidence. These are
host QEMU/TCG results, not iPhone/Apple/GPU/game acceptance.

The causal measurement advanced: unchanged observe-mode connect waits failed
ten times at about500ms before any manual freeze or ptrace. An opt-in, digest/
mapping/frame/UID/syscall-gated interposer changed only this native connect wait
to5s; the same verified call returned0 after3.322421696s. One browser then reached
BrowserReady, SharedJS paint and Big Picture login without SHM runaway. CPUmax,
4vCPU,1536MiB,12GiB, software rendering and forced CEF sandbox are unchanged.
The normal launcher/helper are unchanged; own source and tests are in
`diagnostics/ipc-connect-wait`. This probe is not enabled by default.

The Steam-only stale-X preflight repairs copied-disk Xorg prerequisites.
Diagnostic browser recognition now requires direct native PPid; optional trace
`--tid` selects only a verified existing subset.44 targeted source tests pass;
the historical narrow ABI passes below are superseded by the V3 regression above. All45 locked
dependencies and four installed client ELFs persisted through runs13/14 without
reinstallation. Run11's busy-unmount/forced-stop disk remains rejected and
preserved; runs12/13 stopped cleanly and following full offline fscks passed.
Run14's original VM Stop completed unmount/QEMU0/fsync after controlled owned
application termination (native Steam required SIGKILL). Run15 is a fresh copy
with a full offline check and the same connect probe; only launcher mode changes
to desktop, avoiding the SteamOS-specific startup flags. Main UI is not yet
claimed. Its operator monitor budget is longer; no Steam timeout was changed.
See [exact results, limits, private screenshot hashes and continuation gates](evidence/steam-local-arm64-20261017/README.md).

Latest requested-network recheck at verified Steam remote `12074eaf…`: a fresh
locked Fastly ZIP GET returnsHTTP200 with exact size/hash, but current configured
DNS fails and the native updater hostname is absent from the announced additions.
No refused-host retry, proxy/DNS/security change or VM/Steam launch ran. Actual
production inputs, stopped installed disks,45-package audit receipts and both
prior strict fsck streams were revalidated;149 Steam tests pass. See
[current receipts and remaining network gate](evidence/steam-network-recheck-20261017/README.md).
There is no new browser/IPC/stack observation; the historical timeout remains
unexplained and main UI/Big Picture remain NOT REACHED.

New static follow-up at verified Steam remote `d0a8201f…`: the virtual
`ChromeHTML_Controller_003` readiness target is now resolved to
`chromehtml.so:0x4ea10`, reading controller+`0x20c` = IPC+`0x9c`. The exact
shared-stream response path sets that flag at `0x5b3e8`; disconnect clears it.
This is the flag the120000ms Steam UI loop polls. The per-browser BrowserReady
message and Chromium child's EnsureConnected timeout remain separate paths.
See [bounded disassembly, verified vtable and measurement implications](evidence/steam-proxy-ipc-static-20261017/README.md).
No historical runtime timeout/root cause is proven; no new trace or ARM64 stack
capture ran. The current cloud client still stops before CEF, pending approved
updater access plus a supported guest network/proxy/TLS path. Native application
proxy mechanisms were statically found, but no configuration was changed.

Latest independent cloud attempt: all17 locked ZIPs and the production GUI Release
were actually obtained, production9c4d booted, and all45 dependencies installed
with empty successful dpkg audit. The updater then failed before CEF: host
CONNECT403 for its newly observed `client-update.steamstatic.com` endpoint,
plus guest DNS EAI_AGAIN for both Steam CDN hosts. No browser/SHM growth existed
to trace or sample, and the historical first webhelper timeout below remains
unexplained. Both VMs are cleanly stopped; full offline checks and installation
persistence passed. See [current receipts and precise continuation boundary](evidence/steam-fresh-network-20261017/README.md).

Cloud input follow-up: a **separate experimental GUI seed** now passed full
offline acceptance, SHA-256
`a7758d821f67ec48646d4586ec54aeab8b8db31238f0be6dfaabc5966c46a5a2`.
Production GUI lock/seed are unchanged. See
[cloud seed receipts and exact network requirements](evidence/steam-cloud-seed-20261017/README.md).
The official locked Steam download still has zero ZIPs after tunnel403; no
Steam/CEF runtime or new root-cause claim follows from GUI seed acceptance.
The runner now has an explicit reviewed experimental-seed contract; see
[contract/preflight evidence](evidence/steam-seed-contract-20261017/README.md).
Production GUI defaults are unchanged. Current storage fails the full12GiB
offline-copy +4GiB reserve gate before any image write, so dependency install
and the Steam bootstrap boot are still NOT RUN. No security/network settings
or Steam runtime flags were changed.

**Main UI and Big Picture remain NOT REACHED.** The owner stopped local work to
take the laptop away. Continue in the private cloud environment, independently
of this laptop. The current evidence directory is `evidence/steam-ipc-20261017`;
its manifest records file sizes/hashes. No Valve binary, disk or account material
is included. Earlier static notes are hypotheses where explicitly marked.

## What the observations establish

1. Native ARM64 Steam1792192922 is installed and its updater completed in earlier
   work. Run7's normal verification checked sizes in about20 seconds. A later
   launch after a forced exit performed executable checksums for several minutes.
   That CPU-active verification was not another full install or a CEF deadlock.
2. Valve's `.cef-initialize-sentinel` triggered automatic sandbox fallback in
   the first run7 attempt despite no such option in our launcher. That attempt
   cannot count as sandbox validation. Supported `-cef-force-sandbox` forwards
   `-force-sandbox`; exact binary control flow and the next runtime log show it
   overrides fallback. A child PID2688 had NoNewPrivs1/Seccomp2 and nested PID
   namespaces. Its later zombie exit status was0, not SIGSYS/SIGILL; argv did not
   prove it was a renderer. Preserve sandbox and the corrected private-root helper.
3. Repeated large SHM mappings appear **within one browser lifetime**, before
   the native readiness timeout or browser restart. In the first attempt browser
   PID972 retained25MiB+16-byte objects: used636084224 bytes at83.6 seconds,
   696786944 at the85-second diagnostic freeze. Capacity769449984, mode1777.
   The force-sandbox attempt also accumulated21 large objects by176.452 seconds
   from the resumed diagnostic's origin. A later bounded phase used583626752
   bytes with185823232 free. No new SIGBUS was intentionally allowed.
4. After the fallback attempt's processes had died and all fd/maps were checked,
   the explicit recovery removed38 manifested unreferenced objects (713775200
   logical bytes, 694685696 allocated orphan bytes). `/dev/shm` became0 used.
   This does not fix the underlying allocator/connection problem. Do not remove
   arbitrary or live SHM. Initial recovery attempts refused process churn without
   deleting anything; the final convergent inventory and tests retain that guard.
5. `lsof` was absent. Exact `steamclient.so::GetIPCConnectionDetails` searches for
   and invokes it to identify TCP peer UID/PID/PPID. The authenticated dependency
   lock now adds lsof, liblsof0, libtirpc3t64 and libtirpc-common, preserving all
   original41 extra/341 GUI pins. Actual guest installation was queued for run8
   but never ran. No claim that it caused or resolved the initial timeout.

## The 500ms hypothesis is NOT a runtime diagnosis

Exact steamwebhelper allocates two25MiB streams and zeroes their storage before
replying to a connection request. Static client copies in both steamclient.so
and chromehtml.so have a500ms response wait path. A duplicate-client-ID branch
appears to replace stream pointers. This motivates investigation, but does not
prove repeated IDs, runtime timeout, or the final loss of ownership.

The first syscall trace ended too early, before the first large allocation.
The later `live-pairs` trace shows **zero literal500ms waits**, and17 successful
waits on a5-second robust shared allocator mutex, without ETIMEDOUT. Native
PID2243 address0xffff4a25e018 and browser TID2547 address0xffff9a4ed018 map to
inode106 `/dev/shm/u1000-ValveIPCSharedObj-Steam`, offset0x18. Observed futex
values correspond to WAITERS plus owner TID. The trace covers only its bounded
interval and selected TIDs, not every earlier event.

One large mmap-to-next-syscall gap was0.753089 seconds; that includes userspace,
scheduling and tracing overhead, not a pure memset duration. Actual25MiB glibc
benchmarks varied ~0.216–0.395s; MOPS was not slower than generic/ZVA64 in the
separate function probe. **No timeout shim, icount change, CPU change, MOPS
disable or RAM increase was implemented.** Do not present any as a proven fix.

`strace -i` identifies the syscall site, not the complete caller. The next useful
measurement is a bounded native/browser IPC thread stack at the actual failure,
with verified ELF identities and PT_LOAD-based load biases. The new
`tools/snapshot_steam_ipc_stack.py` restricts capture to PC/SP/FP/LR, frame return
addresses and maps. Offline tests and harmless host attach/detach tests passed;
an actual ARM64 Steam capture is **NOT RUN**. Review its CLI and SNAPSHOT-USAGE
before running; it does not collect argument registers/message contents.

`tools/trace_steam_ipc.py` traces existing selected native/browser TIDs without
following new sandbox children. It bounds duration/output and omits I/O buffers,
execve and environment. Intentional SIGINT detach yields a conservative
`trace_incomplete` receipt; do not relabel that receipt as complete. Trace overhead
can alter TCG timing. Baseline and traced observations must stay separate.

## Stop, tests and exact remaining work

Run7's Steam shutdown requested ordinary `-shutdown`, but native Steam remained
after the bounded wait and needed SIGKILL: **unclean application stop**. VM Stop
independently succeeded with guest clean unmount, QEMU exit0 and host fsync.
Document and machine-id persisted; dpkg audit exit0 with empty output.

Run8 copied run7 with source ownership and strict offline read-only fsck. That
check completed all5 passes with no warnings/questions. It is post-run7/pre-run8
proof, not post-run8 fsck. Run8 then began the new bootstrap, but was deliberately
interrupted at the owner's request before GUI readiness and any command. Its
KeyboardInterrupt failure and clean VM shutdown are both retained in result.json.
No local writer or task mount remains. Do not restart local processes.

129 Steam tests passed on a real1GiB ext4 fixture. The prior DrvFS fixture lacked
renameat2 atomic publication support;64MiB ext4 was too small for the256MiB test
reserve. Neither limitation justified weakening publication/free-space checks.
The fsck parser now rejects unexpected output even with exit0. Saved runner source
and its hash come from one immutable startup snapshot.

Online continuation:

1. Verify branch/remote and preserve other work. Inspect actual cloud artifacts;
   E: and the local qcow2 chain are unavailable. Use verified cloud GUI assets or
   reproduce them with existing pinned builders. Keep separate Steam disk/cache.
   If a client already exists there, preserve it; otherwise record a fresh
   independent official install without claiming Windows-disk continuity.
2. Build the current bootstrap, install the45-extra closure and require dpkg
   audit exit0 plus empty output. Verify lsof in the actual namespace, ordinary
   UID1000/HOME/XDG_RUNTIME_DIR/X11/D-Bus/network and the sandbox override.
3. Limit retries and SHM growth. Capture the first failure separately, establish
   thread roles and exit statuses, then use the bounded stack/trace diagnostics.
   Repair one demonstrated prerequisite at a time. No guessed flags or sandbox
   bypass. Existing software rendering is a diagnostic host configuration.
4. Attempt real main UI then Big Picture, with actual screenshots/input. Late
   run7 QMP screenshots said `Display output is not active`; they are not UI
   proof. Wake with ordinary input and inspect X11/DPMS before interpreting a
   blank capture. No display/security change was made in this local turn.
5. Stop at account/terms screens for the owner. No credentials, games or new
   agreements. After success test clean app+VM Stop, persistence/restart, and
   offline ext4 fsck with no writer and full-output evaluation.
6. Commit/push only the Steam experiment branch, update HANDOFF and honest evidence.
   No GUI/main merge, GUI payload/Release/Codemagic or Apple CI changes.

CPU max,4vCPU,1536MiB, QEMU10.0.13 TCG remain host-only settings. A72's earlier
FEAT_LSE SIGILL is independently established. Production iOS CPU is unchanged.
Recompute storage for each cloud scenario: continuation plus a12GiB raw fsck
copy and4GiB reserve was roughly25GiB additional local headroom. No unlimited
tmpfs/RAM workaround. Steam on iPhone, Apple runtime and GPU acceleration: NOT RUN.
