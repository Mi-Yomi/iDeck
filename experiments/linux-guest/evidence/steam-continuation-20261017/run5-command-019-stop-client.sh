set -eu
setpriv --reuid=1000 --regid=1000 --init-groups env HOME=/home/ideck DISPLAY=:0 XAUTHORITY=/run/user/1000/Xauthority XDG_RUNTIME_DIR=/run/user/1000 /usr/local/bin/ideck-steam stop
for n in $(seq 1 60); do
 if ! pgrep -u 1000 -x steam >/dev/null && ! pgrep -u 1000 -x steamwebhelper >/dev/null; then
 echo IDECK_STEAM_STOPPED_WITHOUT_FORCE
 exit 0
 fi
 sleep 1
done
echo IDECK_STEAM_STOP_TIMEOUT
exit 1
