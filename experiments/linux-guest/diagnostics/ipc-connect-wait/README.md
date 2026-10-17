# Opt-in ARM64 Steam IPC probe — V3

**Use V3 only. The old V2 C forwarding wrapper is unsafe for AArch64 syscalls
that return on a different child stack.** It is preserved in `historical-v2`
solely to reproduce the regression. Its earlier passing tests were incomplete.

V3 source `ipc-connect-wait-v3.c` SHA-256:
`dd7a19b8531294772b3b11e1742c12341d1df2bd77186fdbf042accdb9c9b4c6`.
Private AArch64 library SHA-256:
`14ae446d263a783d341c0236b7fe9a710f4fe7946eb43afde435063473cabb1c`.
This is a host QEMU/TCG diagnostic, not an enabled launcher default or an iOS
runtime fix. The normal launcher does not inject this probe; the namespace helper
is unchanged. Separate launcher fixes select generic Big Picture and handle the
updater's restart code. No Valve ELF is patched.

V3 adds a stack-free AArch64 assembly entry: every non-futex call tail-forwards
to the original libc syscall entry. The fallback also remains stack-free on
successful syscalls, and enters an errno frame only on kernel error. Only
futex calls enter the existing C checker, retaining the original caller LR and
frame-chain gate. Thus clone/clone3 can return on the kernel-selected child
stack instead of returning into a C wrapper whose frame belongs to the parent.

The real ARM64 regression uses an isolated SIGCHLD clone with a custom child
stack and verifies its SP. Baseline passes; V2's child receives SIGSEGV; V3
passes. V3 unit tests also pass with the real libc target and the raw fallback.
The separate actual ARM64 ABI/preload cases pass with a dladdr check that the
requested interposer loaded. Run tests with core dumps disabled (`ulimit -c 0`).
The controlled old-wrapper test child is not a Steam crash.

The C checker is active only for the exact native Steam executable as
UID/EUID1000, constructor PID and main TID. Observe mode retains the original
500ms; explicit `IDECK_IPC_WAIT_MODE=extend-5000` supplies a local five-second
timespec only at chromehtml0x60420 with return chain0x63a98/0x5b368. Module digest,
file/mapping identity, opcode, syscall shape and live2MiB tmpfs shared-object
ownership/mode must match. Failed guards retain the original call. There is no
production test override. Preload is injected only after UID1000 drop, in a
private helper clone. No global preload, sandbox disable, client/cache deletion,
CPU/RAM/SHM increase or change to Steam's overall CEF timeout is involved.

Historical V2 observations remain accurately labelled: ten instrumented native
connect waits returned ETIMEDOUT at about500ms; a five-second gated wait woke
after3.322s and reached real Big Picture login. A later desktop boot woke after
383ms and restored the user's login, but remained on the UI loading screen.
Those outcomes do not establish V2's ABI transparency or an upstream Steam
renderer defect. Whether the V3 correction resolves that UI issue is being
tested separately with the same desktop/resources/deadline profile.

Build and runtime receipts are under
[`../../evidence/steam-local-arm64-20261017`](../../evidence/steam-local-arm64-20261017/README.md).
Cross tools were extracted privately from33 signed-index SHA-pinned Debian
packages; no system installation occurred. Exact compiler arguments and runtime
closure are recorded. ARM64 tests establish the production assembly behavior;
native x86 tests exercise only the ordinary fixture path. No library, Valve
binary, disk, raw minidump, credential or QR image is committed.
