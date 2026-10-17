# Private Steam continuation evidence

These records supplement, rather than replace, the earlier updater-only evidence.
They concern host QEMU 10.0.13 with CPU `max` and the production Alpine 6.18.35
kernel. They are not Apple, iPhone, Big Picture or GPU-acceleration acceptance.

## Run5

The runner copied the explicitly selected clean run4 into a new private overlay.
Run4 was not written: its SHA-256 remained
`c16ec63c8d1761fc41d8f16f288612c8e058d0f0caec3bcc2c7a79de48ea99a9`.
Before boot, a flattened offline ext4 copy passed `e2fsck -f -n` with exit0.
The final cache-cleanup bootstrap from the previous turn was genuinely booted.
The accepted GUI seed was verified and QMP reported its backend read-only.

`013-finish-update` records Valve's **Update complete, launching Steam** at
10:51:10 UTC. No full reinstall or fresh full client download was invoked.
`014`–`018` show the updated native client and real CEF processes after correcting
the chroot restriction. `015` records UID1000, NoNewPrivs1, Seccomp2 and separate
user/PID namespaces for a child. No sandbox bypass was supplied by this project.
The stock Chromium command line also contains its separate unsandboxed zygote;
that does not erase the independently observed sandboxed child.

The exact copied diagnostic helper in run5 had one extra trailing newline:
`56fd1367fe01eacf36cb280044de94db82d492c76fba0f362c48e50e66193e82`.
The source/built-initramfs helper is
`96c929eafefb2f76aa7751fb1869baa6def54e5e31be2a0e6620a486bca64b0d`.
Do not conflate their byte identities. The actual namespace syscall/exec results
are in `run5-010-namespace-pid.log`; the process code differs only by that newline.

The **main UI did not appear**. `steamui_html.txt` reports
`Timed out waiting for webhelper init`, followed by repeated helper restarts.
The screenshot `run5-015-window-state.png` is the real retained Debian desktop,
not a Steam UI success. `019` proves the normal UID1000 `-shutdown` request stopped
both client and helper processes without force, retaining that desktop.

A bounded `-cef-disable-hang-timeouts` diagnostic also failed. It was removed,
restoring the exact original launcher SHA-256
`470bdf1559fb5272776dd076cf04a58a3a81b4c451bf97b9a870d8e1f9957603`.
`023` extracts only exception metadata from the local minidump: signal7/SIGBUS,
address at offset0 of `/dev/shm/u1000-Shm_9adf2d5b`.
`024` proves the tmpfs was 100% full: 769449984 bytes used, zero available,
with repeated roughly25MiB shared objects. This is a secondary exhaustion after
retries, not proof of the first initialization timeout's cause. No raw minidump,
client binary, account or credential is included here.

The independent VM Stop then obtained guest clean-unmount acknowledgement,
QEMU process exit0 and successful host fsync. `run5-result.json` records
`clean_shutdown: true`; the new overlay remains local and run4 is preserved.

## Run6: actual final bootstrap and preserved installation

Run6 used the final runner, copied clean run5 without modifying it (source SHA-256
`e0303edd5b58ca819d8340e18725e7f574068791f72aee9693692ce483fa2626`), and passed a
second offline read-only ext4 check. The 12GiB flattened pre-boot filesystem hash
is `35a2b864e36060a6a75e2c5a95922f4ee52119f7c0bd57039d1d7682b5e8dbed`.

The exact namespace bootstrap `573ed99583fa2b40a51f7ad0e3c825d28a0b226a06ada517243d0468b686b170`
was genuinely booted. The guest verified the source helper hash `96c929...`;
machine-id `01565bdc88738f43157a024d6ad341d2`, the fsynced user document, and
the original native client hash `73da03...` all survived. Steam reported installed
version1792192922, pending version0, **Download skipped**, **Nothing to do**, and
then completed its executable checksum verification. No full reinstallation.
Its previous SIGBUS nevertheless caused Steam's own unclean-client warning;
clean filesystem shutdown is not a claim that that earlier client exit was clean.

Two explicit bounded diagnostics did **not** produce the main interface:
`-system-composer`, and widening UID1000 webhelper thread affinity from CPUs2–3
to all four guest CPUs0–3. Valve's pinned `steamwebhelper.sh` invokes
`taskset 0x7c`; the actual restricted mask was measured before changing it.
No model/production CPU change or sandbox bypass was made. The affine probe
stopped when shared-memory headroom fell below256MiB. Later cleanup reclaimed
space (110915584 bytes used in `005`); there was still a webhelper-init timeout.
Neither that memory behavior nor affinity proves the initial timeout's cause.

`005-final-stop-restore` returned1 because the ordinary Steam shutdown request
did not finish within its bound. `006` still observed active Steam plus a zombie
helper. **Steam's final graceful shutdown failed.** The launcher was then
atomically restored to its original exact bytes while preserving the old running
script's inode. The CPU-affinity probe was temporary, not a new default.
`dpkg --audit` returned0 with both output streams empty, and the user document
still matched. The system `libXrandr.so.2` and `XRRGetOutputInfo` symbol loaded;
the native client's separate XRR warning is not proof of a missing system library.

The subsequent independent VM Stop obtained clean-unmount acknowledgement,
QEMU exit0 and host fsync without forcing QEMU. The runner's `clean_shutdown`
therefore refers to the **guest filesystem/backend stop**, not a successful
Steam application shutdown or a successful UI test. Do not promote the failed
application stop to clean. Final **post-stop** `e2fsck -f -n` also returned0 with
the run6 owner lock held and no QEMU writer. No repair was performed. The checked
12GiB raw filesystem SHA-256 is
`6b8a1beeb22de348ba040fbaa13c8616e91895c1e379dff2789521b4b1e83409`;
see `run6-post-stop-result.json` and `run6-post-stop-offline-fsck.log`.

Main UI, login, Big Picture and their input tests: **NOT REACHED**. No account,
agreement or game was used. The screenshot shows the actual Debian desktop after
the failed attempt. The primary remaining failure is the native Steam/CEF startup
and IPC handshake; its unique root cause has **not** been established.

## Byte identities and scope

`run5-files.json` binds the copied records, including their exact CR/LF bytes.
The local full logs, command scripts and disk are in
`E:\Freddy Fazbear\iDeck.work\steam-arm64-experiment-20261017\run5` and
`commands-continue1`. A command's exit0 establishes completion of that diagnostic,
not a visible Steam window. `run6-files.json` also binds the exact queued commands
and build-time bootstrap receipts. The latter's original NOT RUN field describes
the time of construction; run6 supplies the subsequent actual boot evidence.
