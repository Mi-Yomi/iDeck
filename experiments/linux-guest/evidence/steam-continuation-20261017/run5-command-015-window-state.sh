set -u
sleep 25
export DISPLAY=:0 XAUTHORITY=/run/ideck/Xauthority
xset q
xset s reset
xset dpms force on
printf 'IDECK_VISIBLE_WINDOWS\n'
xdotool search --onlyvisible --name '.*' getwindowname %@ 2>/dev/null || true
printf 'IDECK_CLIENT_LOG\n'
grep -v '^IDECK_NAMESPACE_ROOT_READY=' /home/ideck/steam-experiment-logs/rooted-desktop-01.log | tail -55
printf 'IDECK_CEF_LOG\n'
tail -45 /home/ideck/.local/share/Steam/logs/cef_log.txt 2>/dev/null || true
printf 'IDECK_PROCESS_SANDBOX\n'
for pid in $(pgrep -u 1000 -x steamwebhelper); do
 printf 'PID=%s\n' "$pid"
 grep -E '^(Name|Uid|Gid|NSpid|NoNewPrivs|Seccomp|Seccomp_filters):' /proc/$pid/status
 readlink /proc/$pid/ns/user /proc/$pid/ns/mnt /proc/$pid/ns/pid
 done
sleep 3
