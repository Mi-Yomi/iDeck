# Steam IPC diagnosis and online handoff — 2026-10-17

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
