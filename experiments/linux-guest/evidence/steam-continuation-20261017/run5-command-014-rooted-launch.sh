set -eu
sha256sum /run/ideck/namespace-check.py
if pgrep -u 1000 -x steam; then echo IDECK_ERROR=prior_steam_still_running; exit 1; fi
[ ! -e /home/ideck/steam-experiment-logs/rooted-desktop-01.log ]
python3 /run/ideck/namespace-check.py launch desktop > /home/ideck/steam-experiment-logs/rooted-desktop-01.log 2>&1 </dev/null &
sleep 35
printf 'IDECK_ROOTED_LAUNCH_LOG\n'
grep -v '^IDECK_NAMESPACE_ROOT_READY=' /home/ideck/steam-experiment-logs/rooted-desktop-01.log | tail -90
printf 'IDECK_STEAM_PROCESSES\n'
ps -eo uid,pid,stat,pcpu,rss,comm,args | grep -E 'steam|webhelper|pressure-vessel' | head -30
DISPLAY=:0 XAUTHORITY=/run/ideck/Xauthority xdotool search --onlyvisible --name 'Steam' getwindowname %@ 2>/dev/null || true
