# Steam user-namespace diagnosis — 2026-10-17

The production Alpine 6.18.35-0-virt guest now passes a real UID1000
user-namespace + mount-namespace preflight after Debian becomes the root of a
private mount namespace. The same command fails with EPERM in the original
Debian chroot. This establishes the namespace prerequisite; it does not establish
Steam/CEF sandbox success, Big Picture, or execution on an iPhone.

## Actual guest evidence

Collected on the separate run5 Steam test disk. Local raw evidence is under
`E:\Freddy Fazbear\iDeck.work\steam-arm64-experiment-20261017\run5`:

- `002-namespace-matrix.log`: direct libc syscall results and root/namespace,
  capabilities, seccomp, mount and namespace-limit snapshots.
- `005-namespace-exec.log`: the raw matrix plus normal post-exec UID1000 tests.
- `007-namespace-native.log`: corrected-root exec passes again; outside path
  ownership and Alpine-native exec diagnostics.
- `010-namespace-pid.log`: both corrected-root UID1000 exec preflights pass,
  including a child PID namespace and private proc mount.

| Context | Test | Observed result |
| --- | --- | --- |
| Original Debian chroot, root or UID1000 | Raw `unshare(CLONE_NEWUSER)` | `-1`, errno 1/EPERM |
| Alpine real root, root or UID1000 | Raw `unshare(CLONE_NEWUSER)` | `0` |
| Corrected Debian private real root, root or UID1000 | Raw `unshare(CLONE_NEWUSER)` | `0` |
| Original Debian chroot, UID1000 after exec | `unshare --user --map-root-user --mount /usr/bin/true` | exit 1, `Operation not permitted` |
| Corrected Debian private real root, UID1000 after exec | Identical command | **exit 0**, empty stdout/stderr |
| Corrected Debian private real root, UID1000 after exec | User + mount + PID namespace, `--fork --mount-proc /usr/bin/true` | **exit 0**, empty stdout/stderr |

Both exec tests use `/usr/bin/setpriv --reuid=1000 --regid=1000 --init-groups`
before executing `/usr/bin/unshare`. Every root-changing raw probe is isolated
in a forked child. PID1's root identity remained device 2/inode 1. Its mount
namespace was not replaced.

The raw Python UID1000 tests outside the chroot created a user namespace but
then received EACCES 13 opening `/proc/self/setgroups`. They drop root credentials
inside an already running process. That is not equivalent to executing a normal
UID1000 program: the credential transition can change proc-file ownership via
the process's dumpable state. The successful ordinary exec test is the launch
gate. The helper never changes dumpable policy.

The first outside exec diagnostic attempted to run Debian binaries through an
explicit `/sysroot` loader. It failed before its intended test with exit 127 and
`/sysroot/usr/bin/unshare: cannot open shared object file: Permission denied`.
This is retained as a failed diagnostic, not a namespace failure or success.
The current outside diagnostic instead attempts Alpine's own
`/usr/bin/busybox unshare -U -r -m /usr/bin/busybox true` after dropping child
credentials to UID/GID1000. It also records path modes, owners, symlinks and
access as both root and UID1000. Run5 command 007 fails before exec with
`PermissionError`, errno 13. Its path evidence shows the Alpine root `/` is
mode `0700`, owned by UID/GID0. UID1000 cannot search `/` and receives EACCES
for its child paths. Permissions are left unchanged. This path-access failure
is separate from the Python in-process proc mapping failure above. The raw
outside syscall already proves creation of the namespace; the corrected Debian
root exec supplies successful UID1000 mapping and mount-namespace proof.

The observed user/mount/PID namespace limits were all 6004. `/dev/pts` was a
read-write devpts mount and `/dev/shm` a read-write tmpfs. `/proc/config.gz` and
`/sys/kernel/security/lsm` were unavailable; securityfs was not mounted. These
missing readouts are recorded, not interpreted as missing kernel support.

## Minimal root correction

Linux's [`create_user_ns`](https://raw.githubusercontent.com/torvalds/linux/v6.18/kernel/user_namespace.c)
rejects `current_chrooted()` with EPERM. The
[`current_chrooted` check](https://raw.githubusercontent.com/torvalds/linux/v6.18/fs/namespace.c)
compares the process root with the mount namespace's topmost root. Changing a
subdirectory or pivoting a submount inside the existing chroot does not by
itself establish that invariant.

`guest/steam/namespace-check.py` performs the following only in the dedicated
Steam launch process:

1. Adopt the existing Alpine PID1 root via `/proc/1/root`.
2. Create a private mount namespace with `unshare(CLONE_NEWNS)`.
3. Mark `/` recursively private before any mount movement.
4. Move the mounted Debian `/sysroot` over `/` with `MS_MOVE`, then adopt that
   mount as the process root. This is the mount step used for an initramfs root
   transition; it does not delete Alpine files or alter PID1's mount tree.
5. Run the real UID1000 exec preflight, followed by a separate short-lived child
   test of `unshare --user --map-root-user --mount --pid --fork --mount-proc
   /usr/bin/true`. Refuse Steam launch on either failure. Both tests passed in
   run5 command 010 with exit 0 and empty stdout/stderr.
6. Execute the existing `ideck-steam desktop` or `big-picture` launcher via
   `setpriv` as UID/GID1000, using its established X11/runtime environment.

Guest root commands, with the reviewed helper staged at `/opt/ideck-steam`
(the Steam bootstrap builder automatically includes every `guest/steam` file):

```sh
python3 /opt/ideck-steam/namespace-check.py probe
python3 /opt/ideck-steam/namespace-check.py launch desktop
# Only after the real normal client has been observed:
python3 /opt/ideck-steam/namespace-check.py launch big-picture
```

The helper refuses a different kernel, a missing `ideck.steam_experiment=1`
opt-in, a missing Steam PID1 marker, or execution outside the original Debian
chroot. It accepts no arbitrary command. Its `probe` exit 0 means that collection
finished; inspect each reported test status/errno/exit code.

## Stop and security contract

The launch process creates no PID namespace. The isolated preflight child
tests a PID namespace and private proc mount, then exits before Steam starts.
Steam and its descendants remain visible to the existing Alpine PID1 Stop
sequence. The launcher holds no extra root supervisor
or namespace descriptor after exec. The original sequence must still kill/wait
for children before sync, unmount and QEMU shutdown; actual Stop evidence is
required before calling a session clean. Embedded QEMU owner-thread and disk
lock lifetime rules remain unchanged.

This code changes no sysctl, LSM, seccomp, file permission or sandbox option.
It neither passes `-no-cef-sandbox` nor treats root access as a Steam runtime
solution. Eleven focused fixture tests exercise guards, private propagation/move
ordering, errno reporting, credential drop, exec preflight diagnostics and
fail-closed launch. They mock host privileged calls and supplement the actual
guest evidence above.
