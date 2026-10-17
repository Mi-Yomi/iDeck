set -u
for n in $(seq 1 36); do
 if pgrep -u 1000 -x steamwebhelper >/dev/null; then break; fi
 if ! pgrep -u 1000 -x steam >/dev/null; then break; fi
 sleep 5
done
printf 'IDECK_RESTART_VERIFICATION\n'
grep -v '^IDECK_NAMESPACE_ROOT_READY=' /home/ideck/steam-experiment-logs/rooted-desktop-composer-probe.log | tail -50
printf 'IDECK_AFFINITY_FIRST_HELPER\n'
for pid in $(pgrep -u 1000 -x steamwebhelper || true); do
 printf 'PID=%s\n' "$pid"
 grep -E '^(Name|Uid|Cpus_allowed_list|NoNewPrivs|Seccomp):' /proc/$pid/status
 done
