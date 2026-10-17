# GUI recovery after process termination — implementation in progress

The diagnostic fix is pushed as7a9225a. Clone-only host recovery now passes two
actual force-kill/recovery/GUI-relaunch cycles. Native transaction/UI integration
is being completed separately; **do not dispatch CI from this intermediate commit**.

[Host receipt](evidence/gui-recovery-20261017/receipt.json) records the exact base
seed/profile, runtime init suffix, actual SIGKILL exits, original hashes, ordered
recovery control markers and strict clean-superblock results. Each next GUI boot
checks earlier control files before writing; the final boot checks both files and
completes a clean control Stop/read-only fsck. Original disposable snapshots were
preserved and rehashed. The owner image was neither available nor accessed.

The test uses the earlier authenticated cloud seed46fea, with the SAME production
Alpine6.18.35 kernel/base initramfs and Debian package closure as the current local
payload. Current published local seed9c4d is unavailable in this environment and
must be checked separately. No iPhone recovery or Apple/native test is claimed.

The trusted tool seed is attached RO and mounted ro,noload; its glibc e2fsck runs
inside chroot, with its immutable loader/libraries and an explicit empty fsck
configuration. No executable/configuration comes from the work target. Target and
tools share a filesystem UUID; two unique virtio serials, RO bits and sizes select
their roles. The work target is never mounted and is block-device RO during both
`e2fsck -fn` passes. Only `e2fsck -p -E journal_only` gets a writable target. Any
manual-action/error exit blocks activation; there is no general repair or -y.
The [Debian e2fsck manual](https://manpages.debian.org/trixie/e2fsprogs/e2fsck.8.en.html)
documents journal-only replay and read-only checking.

Both cycle checks returned fsck0 but printed free-block/free-inode counter
mismatches with `Fix? no`. These messages are retained in the checked-in logs;
no counter fix/general repair was applied. The strict checksum/UUID/geometry/
features/journal/RECOVER/state/last_orphan/error_count gate passed after replay,
and the actual desktop and synchronized control files reopened successfully.

Force-kill also left persistent `/tmp/.X0-lock`, blocking Xorg on relaunch. The
small deterministic newc suffix now overlays the accepted desktop PID1 with two
reviewed changes: mount `/tmp` as mode1777,size64m tmpfs and unmount it after killing
session writers. Existing disk `/tmp` contents are hidden, not deleted. `/home`
remains on ext4. The accepted base initramfs, GUI seed and payload lock are unchanged;
no new large artifact or cloud export is needed.

Reproduce in a NEW disposable output directory (needs space for copies/backups):

```sh
python3 experiments/linux-guest/tools/check_gui_recovery.py \
  --assets /path/to/verified-restored-gui-assets \
  --host /path/to/existing/authenticated-extracted-amd64-tools \
  --output /path/to/new-disposable-lab --cycles 2
```

The script verifies every input asset against its profile before creating any VM;
uses existing relocated Debian tools; disables guest networking; does not install
packages, contact an API, or read an owner disk. Retain the output receipts/logs and
original-N.raw snapshots. Native promotion must wait for a fully fresh app process;
host QEMU subprocess exit is not a model for safe same-process native teardown.
