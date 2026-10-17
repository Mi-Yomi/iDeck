set -eu
export DISPLAY=:0 XAUTHORITY=/run/ideck/Xauthority
printf 'IDECK_AFFINITY_PROBE=guest_user_threads_0-3_only\n'
for round in $(seq 1 24); do
 for pid in $(pgrep -u 1000 -x steamwebhelper || true); do
  allowed=$(sed -n 's/^Cpus_allowed_list:[[:space:]]*//p' /proc/$pid/status 2>/dev/null || true)
  if [ "$allowed" != '0-3' ]; then
   setpriv --reuid=1000 --regid=1000 --init-groups taskset -apc 0-3 "$pid" 2>/dev/null | head -4 || true
  fi
 done
 if xdotool search --onlyvisible --class '^Steam$' >/run/ideck/visible-steam-windows 2>/dev/null; then
  echo IDECK_STEAM_WINDOW_CANDIDATE
  cat /run/ideck/visible-steam-windows
  break
 fi
 if ! python3 -c 'import os; s=os.statvfs("/dev/shm"); raise SystemExit(0 if s.f_bavail*s.f_frsize >= 256*1024**2 else 1)'; then
  echo IDECK_SHM_HEADROOM_LIMIT
  break
 fi
 sleep 5
done
printf 'IDECK_AFFINITY_END\n'
tail -35 /home/ideck/.local/share/Steam/logs/steamui_html.txt
df -B1 /dev/shm
xwininfo -root -tree | head -45
