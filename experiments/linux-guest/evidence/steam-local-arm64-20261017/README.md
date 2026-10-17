# Local ARM64 Steam continuation — 2026-10-17

## Night continuation — ordinary launch and gamepad UI (2026-10-18)

Run17 removed the diagnostic preload and used the original helper/launcher and
native 500 ms wait. Actual process maps/environment confirmed its absence.
The SHM reserve guard fired at 52.17 seconds; only the Linux desktop was visible.
This is a failed client-start attempt, not a stable launch. Controlled application
cleanup required native SIGKILL, followed by original clean unmount/QEMU0/fsync;
all four client ELFs persisted unchanged and no private namespace holders remain.
The full strict preboot fsck of run16 passed, with all five passes and no errors.
Run18 compares the V3 diagnostic baseline with a private `-gamepadui`-only launch;
its runtime outcome remains pending. Never use the rejected V2 interposer.

The source Big Picture launcher now selects `-gamepadui` without SteamOS/device
flags that previously reached the Steam Deck welcome wizard. The current guest
bootstrap retains the original launcher; run18 tests the flag change in a private
copy. 32 targeted launch/namespace/bootstrap/game-inventory tests pass. The new
read-only game preflight inventories compatibility components; it does not launch
a game or establish GPU support. The owner's new storage/game request is recorded
in STEAM-IOS-INTEGRATION.md. A persistent Steam phone route and physical iPhone
tests are still required; no full-phone-storage feature is enabled by this change.

**V3 correction (latest): V2 is rejected for further Steam runs.** Its C
syscall wrapper broke AArch64 custom-child-stack clone semantics. A real guest
regression passes with libc, gives SIGSEGV in the controlled V2 test child, and
passes with V3's stack-preserving non-futex tail entry; real/raw fallback and
ordinary ABI cases also pass. Earlier narrow ABI tests missed this case. This
is not evidence of a Steam crash, and V2's later UI hangs cannot be attributed
to upstream Steam from these runs. Current source/library hashes and the
rejected historical version are documented in [`../../diagnostics/ipc-connect-wait`](../../diagnostics/ipc-connect-wait/README.md).

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

**Run14 reached the real Big Picture sign-in screen and accepted the user's
phone QR login. Its final authenticated frame is the Steam Deck Welcome
language wizard. Main/library UI and navigation are not yet verified.** Real QMP screenshots
and all account/QR material stay private on E:. The public screenshot receipt
records hashes and the visually verified stage. No game was launched or
downloaded by the operator. Host QEMU/TCG only; no iPhone/Apple/GPU claim.

## New causal measurement and UI result — runs12–14

Run12's narrow two-TID trace, before any manual group pause, captured two
literal500ms connect waits returning ETIMEDOUT (~0.502s). The trace is marked
incomplete (bounded operator SIGINT/strace-2), with diagnostic detach proven.
Its initial staging hash assertion failed on an extra heredoc newline; that
failed guard is retained and is not relabelled a verified deployment.

Run13 used the exact private syscall interposer in observe mode, with no ptrace
and the original500ms argument. The first ten gated native connect waits all
returned errno110 at500.5–511.8ms before any manual pause. See
[exact pre-freeze timing events](diagnostics/observe-first10.json).
The observer later died on an X11 query timeout; its daemon resource guard also
ended. Owned processes were frozen/cleaned afterwards; later timings are not
used as the baseline. This monitoring failure is retained, not hidden.

Run14 changes one Steam runtime variable: the same interposer's mode from
observe to extend-5000, injected after UID1000 drop in a private helper clone.
Its exact digest/mapping/frame/syscall gate accepted the native connect call
at chromehtml0x60420, chain0x63a98→0x5b368. It returned0, errno0 after
**3.322421696 seconds**, beyond the original0.5s deadline. One browser then
reached BrowserReady, SharedJS FirstPaint, Big Picture and the actual login
screen. SHM stayed about683MB free instead of growing to exhaustion.
Renderer Seccomp2 and NoNewPrivs1 remained active. Original launcher/helper,
CPUmax/4vCPU/1536MiB/12GiB, software CEF, NAT and TLS validation are unchanged.

These timings were collected with the now-rejected V2 wrapper. They show
its observed deadline failure under this TCG profile, with that ABI limitation;
they do not isolate an upstream cause. It does not establish a universal safe timeout, an iPhone fix or a
MOPS bug. The diagnostic is **not enabled by default**. Owned source, exact
build provenance and limitations are in
[`diagnostics/ipc-connect-wait`](../../diagnostics/ipc-connect-wait/README.md).
Private signed-index cross tools were extracted without package installation.
Native and real guest ARM64 unit/ABI/preload tests passed, including a
dladdr check that the requested interposer actually loaded. An earlier
space-split LD_PRELOAD test was invalid; only corrected v2 tests are accepted.

The V6 monitor catches display query timeout/OSError and freezes on other
exceptions; actual harmless-child failure tests verify cleanup. Its UI
candidate is never acceptance. At its operator budget it froze the client;
the same identities were subsequently resumed with the identical SHM guard.
Escape dismissed Steam's own screensaver, revealing the real login UI.
The user requested a fresh QR; an XTest click in the verified active
`Steam Big Picture Mode` window produced a loading spinner and new QR. The
user scanned and approved on their phone; the client logged on with resultOK.
Account identifiers/raw auth logs and QR screenshots are excluded from Git.

Run12/13 application stops required bounded owned signals; original VM Stop
then completed guest unmount→QEMU0→host fsync. Run13/14 preboot full strict
offline checks independently validate the stopped run12/13 disks. Both boots
verify all four client ELFs, control file, machine ID, installed lsof and empty
dpkg audit without reinstall. Run11 remains an independently failed, preserved
disk and is never used for continuation. Run14 then completed original VM Stop with QEMU0/host fsync after bounded
owned application termination (native Steam required SIGKILL). Run15 performs
the full post-run14 offline check on its copy. It keeps the same connect
probe/resources and changes only the existing launcher mode to desktop, because
run14's SteamOS flags lead into the Steam Deck Welcome wizard.

44 current source tests pass:13 display,5 bootstrap,17 stack and9 trace,
including inherited assertion argv and narrow-TID refusals. These tests are
separate from the actual screen/ARM64 runtime evidence.

The remaining acceptance work is authenticated main UI/navigation, controlled
application cleanup, original VM Stop and full final offline fsck. Preserve
all private originals; do not continue run11 or publish account screenshots.
The sections below retain the earlier run9–11 evidence and operator failures.

## Scope and actual changes

Started from verified remote/local `12074eaf24cd8c51cf74cd0f185a5454057aa9d9`,
after reviewing and fast-forwarding the Steam branch only. Source was initially
clean. Original local disks, cache, GUI seed and GUI branch were preserved.
All new artifacts are under `E:\Freddy Fazbear`; no system packages, firewall,
VPN, proxy, certificate policy or global environment were changed.

A copied disk could not start Xorg because `/tmp/.X0-lock` and
`/tmp/.X11-unix/X0` survived an earlier boot. The new Steam-only
`guest/steam/prepare-display.py` verifies root/kernel/opt-in/root identity;
old root-owned singleton file/socket, safe parent directories, numeric lock,
no X server/listener/kernel socket and no lock FD/maps owner; revalidates
metadata before unlinking only these two endpoints. Inconclusive checks refuse.
The original GUI initramfs bytes and PID1 Stop function remain unchanged.
Run10 actually removed the two stale objects and reached X11; run11 found none.
This fixes the pre-Steam desktop prerequisite, not Steam's initialization.

Both IPC tools now require the browser's direct parent to be native Steam.
Steam's assertion dumper inherits the executable/argv, so argv alone falsely
classified it as another browser. Regression tests cover the inherited-argv
case, absent/wrong parent and renderer. The updated tool also completed a real
four-thread AArch64 address snapshot; all diagnostic ptraces detached and
previous group stops were restored. No register or target memory writes.

## Inputs and installation actually verified locally

- All 17 locked client ZIPs and 45 locked dependency packages rehashed.
- Accepted GUI seed SHA-256 `9c4d978f0ea33b608735e203c0e1695ca89188c02b097e610f971cffe1c05791`;
  seed used read-only by QEMU, matching accepted kernel and pinned QEMU10.0.13.
- Run10 installed only the four missing locked packages: lsof, liblsof0,
  libtirpc3t64 and libtirpc-common. All 45 pins match; 382 installed packages
  unchanged. dpkg audit exit0, stdout/stderr empty. See
  [preflight](preflight-result.json) and [actual command log](run10/001-preflight-deps.log).
- UID1000 HOME, runtime directory, Xauthority/X11 and native D-Bus reply passed.
- Guest DNS and normal certificate-verified HTTPS returned200 from **both**
  client-update.steamstatic.com and client-update.fastly.steamstatic.com;
  response12582 bytes, SHA-256
  `cc9b371505d0c96fea42b05b8ce56e477eff6326b6a267a706b803d6e169e501`.
  The earlier cloud proxy/DNS refusal is not the local blocker.
- CPU max, four vCPUs,1536MiB RAM,12GiB disk and software rendering unchanged.
  Launcher SHA `11cc1c70d2960a745b0f2c31a989eedc3ed23a1f6a95d5be7e6094cd25a7f790`
  and private-root helper SHA
  `96c929eafefb2f76aa7751fb1869baa6def54e5e31be2a0e6620a486bca64b0d` unchanged.
  The forced CEF sandbox remains enabled; sentinel/cache preserved.

## First-browser evidence and measurement limits

Run10's operator guard was incorrectly reduced to128MiB and sampled too slowly.
It overshot: SHM fell through156MiB to16MiB/3MiB before stopping owned groups.
Browser1087 was a zombie with raw exit7 (SIGBUS). This is a resource-exhaustion
consequence, not a newly established cause. [Actual status](run10/006-postfreeze-status.log)
and the original operator script retain the error; do not repeat that guard.

Run11's first guard refused an already-traced Steam assertion target, allowing
further SHM growth. Owned application processes were then terminated; native945
required SIGKILL (unclean application stop). The strict SHM helper first refused
process churn without removing anything. After a convergent inventory it removed
only41 manifested, same-boot, unreferenced objects, with per-object FD/maps scans,
ownership/inode/hash checks. Reclaimed792418448 logical bytes; empty baseline
769449984 free. See [manifest and both receipts](shm-recovery).

The next watcher stopped at131.98s after launch with566374400 SHM bytes free.
Its reason `second_browser_before_diagnosis` was false: PID2479 was browser2295's
assertion dumper, not a second browser. It had ptraced2295; the watcher correctly
refused to signal a traced target but mistakenly stopped the dumper itself.
Only the identified owned dumper was resumed, allowed to finish, and the browser
was stopped via pinned pidfd only after TracerPid became0.

The completed selected dump metadata reports exception code `0xffffffff`, a
**manually requested/nonfatal assertion dump**, not a fatal signal. Its comment:
`Assert( CefCrashReportingEnabled() ):/data/src/webhelper/html_chrome.cpp:625`.
Browser2295 remained alive. The private625048-byte dump SHA-256 is
`c65f748e402af41f887188223e1b4d4473bf44e404dd0d93f62546bf8ad6034a`.
No raw dump, environment, argument registers or message buffers were exported.
Only bounded PC/SP/FP/LR, frame addresses, maps and the78-byte software assertion
were decoded. Breakpad's official ARM64_OLD context/manual-dump format informed
the parser; [metadata](first-browser/dump-addresses.json),
[assertion](first-browser/assertion-comments.json), [completion](first-browser/crash-handler-completion.json).

Actual AArch64 captures (four existing native/browser threads):

| Thread | Verified stopped location / return path | Interpretation |
|---|---|---|
| native2192 | libc`0xebde4`; chromehtml`0x60420` → `0x63a98` → `0x5b368` | syscall in shared IPC connect-response wait path |
| native HTMLController2296 | libc`0x8f228`, LR`0x828b8` | frame walk ends at a signed/non-executable return; no guessed PAC stripping |
| browser2295 | crashhandler`0x7bce8`; return reaches steamwebhelper`0x25a398` | still unwinding/waiting in the assertion handler after dump completion |
| EarlyIPCAccept2316 | libc`0xa3f8c`, LR webhelper`0x1407c0` | MOPS SETM inside memset of a new shared stream |

Module SHA/dev/inode and actual PT_LOAD translations were checked, including
libcef's nonzero VA/file-offset difference. Exact libc SHA
`70fa4c4cf57eabeb96097cce47582d02379c4cd1de3db3e98ade4dd7089a1b13`
matches the private ELF used for disassembly. The call before webhelper`0x1407c0`
zeroes stream storage plus16-byte header. See [resolved addresses](resolved-address-snapshot.json),
[raw bounded snapshot](first-browser/address-snapshot.json),
[updated-tool repeat](post-pause/address-snapshot-parent.json) and [static checks](runtime-static).

This narrows the live path but **does not prove a500ms timeout or MOPS defect**.
The first browser was deliberately paused, assertion reporting changes timing,
and a sampled PC cannot measure memset duration. Earlier benchmarks did not show
MOPS slower than the alternative. No timeout shim, memset elision, preload,
CPU-feature change, SHM/RAM increase or sandbox bypass was deployed.

A separate15-second trace resumed these already-paused processes. It is explicitly
`baseline_timing:false`, `trace_incomplete` (strace exit-2), detached its own tracer,
and captured503704 bytes. Native2192 subsequently acquired another Steam-owned
tracer4101; no attempt was made to compete with that handler. The wrapper refused
to stop that traced native process. There are ordinary timed browser-thread waits
and successful5-second robust shared-mutex waits; do not turn unrelated
ETIMEDOUT lines into proof of the Chrome-init deadline. See [trace receipt](post-pause/post-pause-trace__result.json)
and [operator receipt](post-pause/post-pause-probe.json).

## Stop, fsck and persistence

Run9 failed before desktop readiness, received original control Stop, clean
unmount, QEMU exit0 and host fsync. Run10 also completed that full clean Stop.
Both source copies had strict full offline fsck acceptance before boot, all five
passes and exact output checks; a checker exit0 alone was never accepted.
Run11 successfully proved persistence from run10 before launching Steam: client
ELFs/control document/machine-id unchanged, lsof present, audit empty, no reinstall.

**Run11 Stop FAILED.** Original PID1 killed guest processes and attempted sync/
unmount, but `/sysroot/dev` returned `Resource busy`; control emitted
`IDECK_DESKTOP_STOP_FAILED`. After its90-second Stop deadline the unchanged runner
killed QEMU (exit-9). `clean_shutdown:false`, `forced:true`, and `needs-recovery`
remain. This is not a clean checkpoint and must not be a continuation source.
The exact namespace holder was not captured, so no cause or shutdown fix is claimed.
The later offline read-only result and separate clean checkpoint are recorded
below when complete. A clean fsck would not erase a failed Stop receipt.

## Historical run11 tests and next experiment (superseded above)

13 display safety tests, five bootstrap preservation tests and24 IPC stack/trace
regressions passed. The two real AArch64 captures independently confirm detach
and group-stop restoration. Watcher fixture tests exercised own harmless children
and refusal/exec cases, but missed the inherited-argv assertion role: their pass
counts are not runtime acceptance. [Logs](display-tests.log), [bootstrap](bootstrap-tests.log),
[IPC](ipc-parent-tests.log). No tests or desktop screenshot count as Steam UI success.

Continue from the **last independently clean, accepted copy**, never from run11.
First correct the operator watcher with direct-parent browser recognition and
explicit assertion-handler coordination; do not pause an active crash dumper.
Use an empty same-boot SHM baseline and a fast384MiB resource guard. Capture the
first IPC connect failure before long group pauses: link its native/browser
TIDs, actual errno/result and addresses to the exact request/response path.
Do not adopt a timeout or memory optimization until that causal measurement exists.
Before VM Stop, detach diagnostics, let owned assertion handlers finish, stop
owned Steam processes, verify no remaining relevant process/namespace holder,
and only then send original Stop. Never use lazy unmount or relabel STOP_FAILED.
If main/login is finally mapped, record the real QMP image, stop for user login/
terms if needed, then separately demonstrate Big Picture and actual navigation.

Private local disks and caches are not transferred by Git. No Valve client ELF,
ZIP/deb, virtual disk, raw dump or credentials are included in this evidence.
The manifest binds every published evidence file; original full logs stay in
`E:\Freddy Fazbear\iDeck.work\steam-arm64-experiment-20261017\resume-local-20261017`.
