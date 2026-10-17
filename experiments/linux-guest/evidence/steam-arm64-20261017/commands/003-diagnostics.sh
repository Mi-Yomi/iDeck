set -u
uname -a
getent ahostsv4 client-update.fastly.steamstatic.com
python3 -c 'import urllib.request; r=urllib.request.urlopen("https://client-update.fastly.steamstatic.com/steam_client_steamdeck_publicbeta_linuxarm64",timeout=20); print("VALVE_MANIFEST_HTTPS_STATUS",r.status); print("VALVE_MANIFEST_BYTES",len(r.read(1048576)))'
setpriv --reuid=1000 --regid=1000 --init-groups unshare --user --map-root-user --mount true
echo USER_MOUNT_NAMESPACE_STATUS:$?
cat /proc/sys/kernel/unprivileged_userns_clone 2>/dev/null || true
cat /proc/sys/user/max_user_namespaces
free -m
df -h /
tail -100 /home/ideck/steam-experiment-logs/desktop.log
xwininfo -root -tree
find /home/ideck/.local/share/Steam/logs -maxdepth 1 -type f -name '*.txt' -exec sh -c 'echo LOG:$1; tail -60 "$1"' sh {} \; 2>/dev/null || true
