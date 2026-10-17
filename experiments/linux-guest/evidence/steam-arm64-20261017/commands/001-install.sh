set -eu
python3 /opt/ideck-steam/install-cached.py --port "$IDECK_CACHE_PORT" --private-qemu-cache || {
 cat /var/log/ideck-steam-install/result.json 2>/dev/null || true
 tail -80 /var/log/ideck-steam-install/dpkg.log 2>/dev/null || true
 tail -80 /var/log/ideck-steam-install/client-install.log 2>/dev/null || true
 exit 1
}
cat /var/log/ideck-steam-install/result.json
df -h /
