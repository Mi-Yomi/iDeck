set -u
printf 'IDECK_COMPOSER_LOG\n'
tail -25 /home/ideck/.local/share/Steam/logs/steamui_html.txt
printf 'IDECK_AFFINITY_BEFORE\n'
for pid in $(pgrep -u 1000 -x steamwebhelper); do
 printf 'PID=%s\n' "$pid"
 grep -E '^(Name|Uid|Cpus_allowed_list|NoNewPrivs|Seccomp):' /proc/$pid/status
 done
printf 'IDECK_SHM\n'
df -B1 /dev/shm
printf 'IDECK_WINDOWS\n'
DISPLAY=:0 XAUTHORITY=/run/ideck/Xauthority xwininfo -root -tree | head -35
