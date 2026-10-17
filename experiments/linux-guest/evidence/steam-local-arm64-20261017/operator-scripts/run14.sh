set -eu
ulimit -c 0
base='/mnt/e/Freddy Fazbear/iDeck.work/steam-arm64-experiment-20261017'
task="$base/resume-local-20261017"
export PYTHONDONTWRITEBYTECODE=1 TMPDIR="$task/tmp" HOME="$task/tmp"
exec python3 "$base/source/experiments/linux-guest/tools/steam_vm.py" \
 --host "$base/prior-build/production/vm/host" \
 --seed "$base/prior-build/seed-final/seed/gui-rootfs-v1.raw" \
 --kernel "$base/prior-build/bootstrap/vmlinuz-virt" \
 --bootstrap "$task/bootstrap-display" --cache "$base/client-cache" \
 --debs "$base/deps-cache/debs" --commands "$task/commands14" \
 --qemu-img "$base/image-tools/usr/bin/qemu-img" --image-tool-receipt "$base/image-tools/receipt.json" \
 --output "$task/run14" --continue-from "$task/run13" --seconds 1500 --enable-experimental-network
