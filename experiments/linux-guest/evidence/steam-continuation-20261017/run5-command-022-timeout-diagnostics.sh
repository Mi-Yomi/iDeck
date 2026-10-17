set -u
printf 'IDECK_CURRENT\n'
tail -35 /home/ideck/steam-experiment-logs/rooted-desktop-timeout-probe.log | grep -v '^IDECK_NAMESPACE_ROOT_READY='
tail -25 /home/ideck/.local/share/Steam/logs/steamui_html.txt
printf 'IDECK_RUNTIME_BINARIES\n'
find /home/ideck/.local/share/Steam -maxdepth 7 -name '*launcher-service*' -o -name 'steamwebhelper.sh' -o -name '*crash*cfg'
printf 'IDECK_PROCESSES\n'
ps -eo uid,pid,stat,etimes,pcpu,rss,comm | grep -E 'steam|webhelper'
