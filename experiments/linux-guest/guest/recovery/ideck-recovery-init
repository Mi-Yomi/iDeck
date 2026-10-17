#!/bin/sh
# Clone-only recovery. Tools come from the immutable, RO bundled Debian seed.
# The target is NEVER mounted. No general repair, -y, or dirty-bit editing.
BB=/usr/bin/busybox
export PATH=/run/bin:/usr/sbin:/usr/bin:/sbin:/bin
control_open=0
fail() {
    echo "IDECK_RECOVERY_FAILED:$1"
    [ "$control_open" = 0 ] || echo "IDECK_RECOVERY_FAILED:$1" >&3
    $BB sync
    $BB poweroff -f
    while :; do $BB sleep 3600; done
}
$BB mkdir -p /proc /sys /dev /run /tools
$BB mount -t proc proc /proc || fail proc
$BB mount -t sysfs sysfs /sys || fail sys
$BB mount -t devtmpfs devtmpfs /dev || fail dev
exec </dev/console >/dev/console 2>&1
$BB mkdir -p /run/bin
$BB --install -s /run/bin || fail applets
for module in virtio_pci virtio_mmio virtio_blk; do modprobe "$module" || fail module; done
while IFS= read -r module; do insmod "/lib/modules/6.18.35-0-virt/$module" || fail ext4; done < /ideck/ext4-load-order
n=0
control=
while [ "$n" -lt 30 ]; do
    for port in /sys/class/virtio-ports/*; do
        [ -r "$port/name" ] || continue
        [ "$(cat "$port/name")" != org.ideck.control ] || control=/dev/${port##*/}
    done
    [ -b /dev/vda ] && [ -b /dev/vdb ] && [ -c "$control" ] && break
    n=$((n+1)); sleep 1
done
[ -c "$control" ] || fail control
exec 3<>"$control" || fail control_open
control_open=1
trap 'fail cancelled' USR2 TERM INT
(
    while IFS= read -r command <&3; do
        if [ "$command" = IDECK_STOP_V1 ]; then kill -USR2 1; exit; fi
    done
) &
echo IDECK_DESKTOP_RECOVERY_READY >&3
# Same UUID in seed and clone is intentional. Never select either by UUID alone.
tools=
work=
for disk in /sys/block/vd*; do
    case "$disk" in /sys/block/vda|/sys/block/vdb) ;; *) fail extra_disk;; esac
    case "$(cat "$disk/serial")" in
        ideck-recovery-tools) [ -z "$tools" ] || fail duplicate_tools; tools=${disk##*/} ;;
        ideck-recovery-work) [ -z "$work" ] || fail duplicate_work; work=${disk##*/} ;;
        *) fail disk_identity ;;
    esac
done
[ -n "$tools" ] && [ -n "$work" ] && [ "$tools" != "$work" ] || fail disk_identity
[ "$(cat /sys/block/"$tools"/ro)" = 1 ] && [ "$(cat /sys/block/"$work"/ro)" = 0 ] || fail readonly
[ "$(cat /sys/block/"$tools"/size)" = 2621440 ] && [ "$(cat /sys/block/"$work"/size)" = 2621440 ] || fail size
for disk in "/dev/$tools" "/dev/$work"; do
    case "$(blkid "$disk")" in *'UUID="b66e1c8d-9cbf-45a7-b97b-dcc8f68efca7"'*) ;; *) fail uuid;; esac
done
mount -t ext4 -o ro,noload "/dev/$tools" /tools || fail tools_mount
mount -o bind /dev /tools/dev || fail bind_dev
mount -o bind /proc /tools/proc || fail bind_proc
# Explicit chroot invokes the seed's glibc ELF interpreter and pinned libraries.
# No executable, library or configuration is read from the mutable target.
check() {
    chroot /tools /usr/bin/env -i PATH=/usr/sbin:/usr/bin:/sbin:/bin LC_ALL=C E2FSCK_CONFIG=/dev/null \
        /usr/sbin/e2fsck "$@" "/dev/$work" 3>&-
}
set_target_mode() {
    chroot /tools /usr/sbin/blockdev "--set$1" "/dev/$work" 3>&- || fail target_mode
    [ "$(cat /sys/block/"$work"/ro)" = "$2" ] || fail target_mode
}
set_target_mode ro 1
check -f -n
assessment=$?
echo "IDECK_RECOVERY_ASSESS:$assessment" >&3
case "$assessment" in 0|4) ;; *) fail assessment;; esac
set_target_mode rw 0
check -p -E journal_only
replay=$?
echo "IDECK_RECOVERY_REPLAY:$replay" >&3
case "$replay" in 0|1) ;; *) fail replay;; esac
set_target_mode ro 1
(ulimit -f 2048 || exit 8; check -f -n) >/run/verification.log 2>&1
verified=$?
cat /run/verification.log 3>&-
echo "IDECK_RECOVERY_VERIFY:$verified" >&3
[ "$verified" = 0 ] || fail manual_review
awk -f /ideck-fsck-clean.awk /run/verification.log 3>&- || fail verification_output
echo IDECK_RECOVERY_SCAN_CLEAN >&3
sync || fail sync
umount /tools/proc || fail unmount_proc
umount /tools/dev || fail unmount_dev
umount /tools || fail unmount_tools
sync || fail final_sync
echo IDECK_RECOVERY_DONE >&3
echo IDECK_DESKTOP_CLEAN_UNMOUNT >&3
poweroff -f
fail poweroff_returned
