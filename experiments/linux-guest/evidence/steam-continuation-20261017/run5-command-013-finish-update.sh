set -u
for n in $(seq 1 120); do
 if grep -qE 'Update complete|steamwebhelper|Fatal|fatal|client_exit_nonzero' /home/ideck/steam-experiment-logs/continuation-desktop.log; then break; fi
 sleep 5
done
date -u
tail -110 /home/ideck/steam-experiment-logs/continuation-desktop.log
echo IDECK_PROCESSES_AFTER_UPDATE
ps -eo uid,pid,stat,comm,args | grep -E 'steam|webhelper|pressure-vessel' | head -25
echo IDECK_VISIBLE_WINDOWS
xdotool search --onlyvisible --name 'Steam|Sign in' getwindowname 2>/dev/null || true
