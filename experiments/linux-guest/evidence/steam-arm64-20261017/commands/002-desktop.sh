set -eu
test -x /home/ideck/.local/share/Steam/steamrtarm64/steam
install -d -o 1000 -g 1000 -m 0700 /home/ideck/steam-experiment-logs
setpriv --reuid=1000 --regid=1000 --init-groups env -i PATH=/usr/local/bin:/usr/bin:/bin HOME=/home/ideck USER=ideck LOGNAME=ideck LANG=C.UTF-8 DISPLAY=:0 XAUTHORITY=/run/user/1000/Xauthority XDG_RUNTIME_DIR=/run/user/1000 /usr/local/bin/ideck-steam desktop > /home/ideck/steam-experiment-logs/desktop.log 2>&1 &
sleep 70
cat /home/ideck/steam-experiment-logs/desktop.log
xwininfo -root -tree
ps -eo uid,pid,comm,args | head -70
find /home/ideck/.local/share/Steam/logs -maxdepth 1 -type f -name '*.txt' -exec sh -c 'echo LOG:$1; tail -40 "$1"' sh {} \; 2>/dev/null || true
