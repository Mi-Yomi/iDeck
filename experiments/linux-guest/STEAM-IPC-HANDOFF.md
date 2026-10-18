Latest verified native game-tool run29, 2026-10-18: official ARM64 Runtime4 container (UID1000/64-bit/aarch64) and GE Wine11.0 Staging versions passed all6 probes. Managed dbus-run-session repeat passed with no new namespace holders; initial autolaunch/cleanup-race failures are preserved. Client4ELFs/package versions unchanged, OOM0, clean original Stop/QEMU0/noRecovery/full offline-copy fsck/source preservation PASS, input mount closed normally. Clean private source29 SHA c450673a940e0cefb1b27dc5a21697c7335e6fa8663e51c356da8d5a5e4dc03e. This is tool execution, NOT Steam/game/GPU/iPhone acceptance. Last accepted UI remains27; interrupted28 never reused. Bin-arm64 preflight/containment4Linux tests passed; GE also has a working legacy bin alias, so no Steam-stall causation claimed. iPhone16ProMax/iOS27 user-reported, hardware untested. No default/iOS route activated. Read [native runtime result](../../GAME-RUNTIME-RESULT-20261018.md).

Latest verified local run27, 2026-10-18: actual Store-Library-Store-Library navigation, Big Picture Home/game details rendered, 4GiB/native500ms/sandbox, zero OOM. Ordinary application shutdown, clean original VM Stop/QEMU0, full post-fsck/source preservation PASS. Pinned zero V5 + stock CEF watchdog flag; later owned CPU-affinity phase is separate/confounded. One bounded run only; full BP menu/return, Steam games, repeat launch and iPhone unverified. Run26 interrupted/inconclusive, preserved and not reused. Render-only pinned profile + 4 tests and actual CLI hash/overwrite checks PASS. No default/iOS launch profile activated. Read [current UI result](../../STEAM-UI-RESULT-20261018.md).

# Steam IPC diagnosis and online handoff — 2026-10-17

## Latest run25 — allocation fix; run26 preparing (2026-10-18 04:48 UTC)

A new manual request authorized solving the remaining issue. The pinned browser's
fresh25MiB stream memset is now selectively skipped only for fully verified
already-zero tmpfs holes. Actual ARM64 fixtures and browseractivation/two call
receipts passed. Same4GiB/native500ms/sandbox, original20min monitor234samples:
OOM0/min2763224KiB, maxSHM76935168B, maxlargecount2/allocated741376B. This removes
the measured allocation growth in one run. Mainnavbar rendered but content was
black; a Libraryclick plus303sec standardURIphase did not verify navigation.

CleanVMStop/QEMU0/no recovery marker/fullpost25fsck/sourcepreservation passed;
appshutdown separately needed one ownedSIGKILL. Four clientELFs/audit unchanged,
namespaces/inputmount closed. Newest CLEAN private source25 SHA
20a30a61ccbba6830442e067907f7dc9fcad22e452f57a98760dbe8b2790cef0. Keep24/22;
never use incomplete23. Run26 is preparing from25 with only the existing owned
browser-affinity0-3 helper added to the zero/native500 control. Earlier affinity
alone failed; this combination is pending. Check fresh private NIGHT-PROGRESS.md
and ACTIVE-RUN26.md/processes before acting; old PID/live-state claims below are
historical. Old automation staysPAUSED. No new iPhone/game/storage acceptance.

Current report: repository-root SHM-RESULT-20261018.md. Guarded experimental code:
experiments/linux-guest/diagnostics/shm-zero-init; sanitized run25 evidence under
experiments/linux-guest/evidence/steam-local-arm64-20261017/run25. Ordinary and
iOS launch profiles do not enable the new library automatically.

## Latest run24 — 4096 MiB host comparison (2026-10-18)

A fresh user request authorized more RAM after the overnight deadline. Run24
actually used4096MiB, native500ms IPC and the same sandbox/CPU/observer as22.
It reached the shared-memory reserve guard at264.631s with1872412KiB guest
MemAvailable and zero kernelOOM; no main Steam UI was visible. Default tmpfs
capacity also increased. Host Windows paging was observed and remains a timing
confounder. Do not treat RAM alone as a verified fix or as an iPhone budget.

VM Stop and final offline integrity passed; four clientELFs and package audit
passed. No owned VM/input mount remains. The newest clean private continuation
is `resume-local-20261017/run24/steam-experiment.qcow2`, SHA-256
`7d2261892e4991e6536a1dbd2cb7a6e82727e5eb700d2412527e39b91e7f77e5`. Preserve earlier22; never continue incomplete23. No new Apple
build/device/game/storage acceptance. Userdevice iPhone16ProMax; GetMoreRAM
planned, actual signed entitlement/process limit untested. Current report:
`RAM-RESULT-20261018.md`. Earlier checkpoints below are historical.

## Current checkpoint — 2026-10-18 01:00 UTC

Read `NIGHT-RESULT-20261018.md` at the repository root for the current outcome.
The older sections below are historical snapshots: their pending runs, live PIDs
and disk paths are not current instructions.

Run23 failed BEFORE guest boot when WSL lost access to E: (EIO/ENODEV during
continuation preparation). There is no CPU-affinity experiment result from23.
The last verified continuation source is the private
`resume-local-20261017/run22/steam-experiment.qcow2`, SHA-256
`22218a60a774116e38881548419da68a1f870c9ef88745aff7f465d6790929e8`.
Its earlier full offline check passed and a fresh Windows read after the host
failure matched that hash. Preserve the incomplete23 copy for diagnosis; do not
use it as a continuation source. No test VM, helper or input mount remains live.
Before any future boot, diagnose WSL's E: access, verify the input mount and
source identity, then use the existing guarded copy/check path into a new output.
Do not repair or overwrite the verified source, or reset unrelated WSL sessions.

Affinity widening was already tested in run6 without a visible main interface;
see `experiments/linux-guest/evidence/steam-continuation-20261017/README.md`.
The newer baseline confirms the restriction persists, not that it causes the
failure. Do not repeat the old probe as a newly discovered fix. Run23 would
have compared a changed configuration but did not execute.

The official ARM64 client runtime was statically checksum/ELF verified only.
It is not installed or executed; its version differs from the bundled runtime.
Do not count it as a working game/Proton stack. Evidence for this checkpoint:
`experiments/linux-guest/evidence/steam-local-arm64-20261017/run23` and
`runtime-arm64-static` in that same evidence directory. Real Library/Big Picture,
Steam game launches, iPhone integration and internal game storage remain
unverified or unimplemented. No new long tests after01:00UTC; final01:30UTC.

## Run22 — native IPC still reaches the shared-memory guard (2026-10-18)

At the same 2560 MiB budget, removing diagnostic LD_PRELOAD restored the native
500 ms IPC deadline. Actual client/browser maps and environments confirmed the
library and its control variable were absent. The early 90-second browser probe
ran during package extraction; the later probe passed. The restart-aware
launcher handled the updater's restart, but no main Steam window was established.

The shared-memory guard stopped observation after 205.986 seconds, leaving
376815616 bytes free out of 1294241792. All 69 samples had OOM0; minimum available
RAM was 1318872 KiB. More RAM therefore did not make the ordinary client usable
under this host TCG setup. The previous diagnostic run's intermittent Store
rendering remains insufficient for stable navigation or Steam game acceptance.

The frozen test was ended early through owned application cleanup and the
original VM Stop. Application termination was unclean; VM unmount/QEMU0/fsync
was clean, with no recovery marker or remaining namespace holders. Four client
ELFs and the package audit passed. A separate final offline read-only check
passed all five phases plus summary with no errors and preserved the source
disk hash. No iOS code, accepted payload, storage contract or other branch was
changed. Evidence: `experiments/linux-guest/evidence/steam-local-arm64-20261017/run22`.


## Run21 — more memory did not establish stable navigation (2026-10-18)

The 2560 MiB desktop comparison completed 20 minutes with 351 samples, no
kernel OOM and a minimum 809388 KiB available. A 20.021-second probe recorded
zero selected reclaim, allocation-stall and major-fault deltas. Lifetime reclaim
was nonzero, and increasing guest RAM also increased the default tmpfs capacity;
this was not an independent fixed-SHM experiment.

Actual Store artwork rendered. Library and Add a Game clicks did not establish
working navigation; the main window disappeared temporarily and returned with
a blank body. More RAM therefore did not solve UI continuity. The native client
remained alive while several browser subprocesses disappeared; this evidence
does not identify a fatal signal or the root cause. No Steam game launch,
usable Big Picture or iPhone performance is claimed.

The application still required owned-process termination, including one SIGKILL.
The separate original VM Stop completed cleanly: guest unmount, QEMU0 and host
fsync, no recovery marker, no private namespaces, clean package audit and four
unchanged client ELFs. Full post21 integrity passed run22's read-only preboot
check on a separate copy: all five phases and summary, no errors, original21
preserved. Account logs, screenshots and dump contents remain private.

Run22 compares the same 2560 MiB desktop configuration without diagnostic
LD_PRELOAD, restoring the native 500 ms IPC deadline while retaining the
restart-aware launcher and sandbox. Its result is pending. The iPhone storage
route remains unimplemented; the existing 4 GiB seed contract is unchanged.
Sanitized evidence: `experiments/linux-guest/evidence/steam-local-arm64-20261017/run21`.


## Run20 — measured memory pressure, desktop still incomplete (2026-10-18)

The ordinary desktop control completed 20 minutes with saved login and one
actual updater restart. The main navigation bar appeared, but Store content
remained blank and a visible Library click did not establish navigation. No
usable desktop, Big Picture or Steam game launch is claimed by this run.

Memory pressure is now measured independently of OOM: available memory reached
32,216 KiB; a 20.04-second window recorded 141,011 pages scanned by background
reclaim and 1,774 by direct reclaim, five normal-zone allocation stalls and 332 major
faults. No swap was enabled. All 248 samples and kernel logs had no OOM kill.
This establishes reclaim pressure, not the sole cause of the UI stall. The
kernel has no PSI interface; the corrected read-only probe reports that absence.
Captured dump exception headers indicate requested dumps (0xffffffff), not
fatal signals; raw dump memory and account pixels remain private.

The app's ordinary shutdown timed out and owned-process termination was needed.
The separate VM Stop completed guest unmount, QEMU0 and host fsync; namespaces
were gone, package audit was clean and four client ELFs were unchanged. Full
post20 integrity passed run21's read-only preboot check on a separate copy:
all five phases plus summary, no errors; the original run20 disk was preserved.

Run21 compares 2,560 MiB with 1,536 MiB while retaining desktop mode, CPU,
sandbox and V3 diagnostic. The explicit host-only memory option records both
configured and effective budgets, preserving the pinned default profile.
25 runner and 18 seed-protection checks pass. The comparison result is pending;
it is not an iPhone RAM recommendation. iOS storage integration, Apple build,
device gameplay and Steam/Proton support remain unverified/unimplemented as
described in STEAM-IOS-INTEGRATION.md. Sanitized evidence is in
`experiments/linux-guest/evidence/steam-local-arm64-20261017/run20`.


## Run19 — updater retry confirmed; no kernel OOM (2026-10-18)

The bounded updater restart now has an actual runtime check: run19 recorded one
`update_restart_requested`, restarted the native client and completed login.
The four pinned client ELFs remained unchanged. Big Picture showed loading,
then a black window through the 20-minute observation limit; navigation is not
verified. The guest could resolve Steam and fetch the Store over HTTPS (200).

All 319 kernel samples had `oom_kill=0`, and before/after dmesg contained no OOM
kill. Minimum available memory was 156,884 KiB. A sandboxed helper disappeared
after Steam's own assertion dumper traced its browser parent. This rules out an
observed kernel OOM kill in this run, not user-space allocation failure or other
memory pressure. Forked Chromium children retained `--type=zygote`; an empty
renderer-argument match cannot establish that no renderer exists.

The read-only game inventory found the ARM64 client beside an x86-64 runtime
launcher service, no Proton/FEX candidates and no Vulkan ICD. A render node is
not GPU acceptance. Three inventory tests pass, including architecture reporting
through a runtime symlink and refusing to inspect a symlink outside its root.

Owned application cleanup needed one SIGKILL after the ordinary request and
SIGTERM. This is not a clean client exit. All namespace holders were then absent,
package audit was clean, and the original VM unmount/QEMU0/fsync path completed.
Post19 integrity passed run20's full read-only preboot check on a separate copy:
all five phases plus summary, no errors; original run19 preserved.
Sanitized evidence is in `experiments/linux-guest/evidence/steam-local-arm64-20261017/run19`;
raw account logs, pixels and memory remain private. Run20 compares ordinary
desktop mode with identical resources, sandbox and diagnostic V3. No new iPhone
storage feature, Steam/Proton game acceptance or device result is claimed.


## Night continuation — updater restart and native game checks (2026-10-18)

Run18 observed a real Steam self-update finishing with exit code 42. The old
launcher treated that restart request as failure. The source launcher now retries
at most twice while holding its lock, revalidates the client and refuses a retry
if an old client remains. Three focused tests cover these cases; 32 targeted
launcher/namespace/bootstrap/game-inventory tests pass. At the end of run18 the automatic retry path was only unit-tested; run19 above
subsequently exercised it with the real updater. Big Picture now requests
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
