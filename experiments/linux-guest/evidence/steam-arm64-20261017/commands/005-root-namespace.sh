set -u
# Probe a private mount namespace only; no global mounts or sysctls are changed.
unshare --mount --propagation private /bin/sh -c '
set -eu
mount --bind / /
cd /
pivot_root . .
umount -l .
cd /
setpriv --reuid=1000 --regid=1000 --init-groups unshare --user --map-root-user --mount true
echo PRIVATE_ROOT_USER_NAMESPACE_OK
'
echo PRIVATE_ROOT_PROBE_EXIT:$?
