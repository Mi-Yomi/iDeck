set -u
printf 'IDECK_SHM_CAPACITY\n'
findmnt /dev/shm
df -B1 /dev/shm
ls -l /dev/shm | head -30
printf 'IDECK_SHM_ALLOCATION\n'
du -B1 -s /dev/shm
