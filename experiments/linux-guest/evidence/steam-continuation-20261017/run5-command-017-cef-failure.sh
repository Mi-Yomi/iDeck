set -u
for name in steamui_html.txt webhelper_gpu.txt bootstrap_log.txt steamui_system.txt systemmanager.txt; do
 echo "IDECK_LOG=$name"
 tail -70 /home/ideck/.local/share/Steam/logs/$name
done
printf 'IDECK_KERNEL_FAULTS\n'
dmesg | tail -30
printf 'IDECK_DUMP_FILES\n'
find /tmp/dumps -maxdepth 2 -type f -printf '%f %s bytes\n' 2>/dev/null | head -15
