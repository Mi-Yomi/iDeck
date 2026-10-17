set -u
setpriv --reuid=1000 --regid=1000 --init-groups env -i PATH=/usr/local/bin:/usr/bin:/bin HOME=/home/ideck USER=ideck LOGNAME=ideck LANG=C.UTF-8 DISPLAY=:0 XAUTHORITY=/run/user/1000/Xauthority XDG_RUNTIME_DIR=/run/user/1000 timeout 40 /usr/local/bin/ideck-steam desktop
echo ACTUAL_LAUNCHER_EXIT:$?
dmesg | tail -30
ls -l /home/ideck/.local/share/Steam/steamrtarm64/steam
setpriv --reuid=1000 --regid=1000 --init-groups env LD_LIBRARY_PATH=/home/ideck/.local/share/Steam/steamrtarm64:/home/ideck/.local/share/Steam/steamrtarm64/panorama /lib/ld-linux-aarch64.so.1 --list /home/ideck/.local/share/Steam/steamrtarm64/steam
cat /proc/cpuinfo | head -25
find /home/ideck -maxdepth 5 -name '*log*' -type d
