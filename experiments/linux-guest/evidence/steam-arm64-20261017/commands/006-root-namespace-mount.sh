set -u
unshare --mount --propagation private /bin/sh -c '
set -eu
mkdir /run/ideck/steam-root-probe
trap "rmdir /run/ideck/steam-root-probe 2>/dev/null || true" EXIT
mount --rbind / /run/ideck/steam-root-probe
cd /run/ideck/steam-root-probe
pivot_root . .
umount -l .
cd /
setpriv --reuid=1000 --regid=1000 --init-groups unshare --user --map-root-user --mount true
echo PRIVATE_DISTINCT_ROOT_USER_NAMESPACE_OK
'
echo PRIVATE_DISTINCT_ROOT_PROBE_EXIT:$?
tail -60 /home/ideck/steam-experiment-logs/desktop.log
xwininfo -root -tree | head -35
df -h /
