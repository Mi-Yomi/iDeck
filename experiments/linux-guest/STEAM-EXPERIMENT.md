# Private ARM64 Steam host experiment

This branch adds a real-client experiment above the accepted Debian Desktop. It
does not enable a Steam app button, change the accepted GUI payload or certify
Steam on iPhone. The separate [profile](profiles/steam-host-experiment.json)
requires explicit QEMU user networking and a new qcow2 overlay. The accepted seed
is verified against `ipa/gui.lock.json` and remains a read-only backing file.

## Source and distribution boundary

Reviewed DroidDeck upstream commit `64d78aa812305d707700e2ad460f3b94d03ed50c`:

- [droiddeck-steam-install](https://github.com/Droid-Deck/DroidDeck/blob/64d78aa812305d707700e2ad460f3b94d03ed50c/tools/linuxfs/overlay/usr/local/bin/droiddeck-steam-install)
- [droiddeck-session](https://github.com/Droid-Deck/DroidDeck/blob/64d78aa812305d707700e2ad460f3b94d03ed50c/tools/linuxfs/overlay/usr/local/bin/droiddeck-session)
- [GPL-3.0 license](https://github.com/Droid-Deck/DroidDeck/blob/64d78aa812305d707700e2ad460f3b94d03ed50c/LICENSE)

The Python installer is an original implementation of the observed manifest
selection, with strict verification and extraction. No DroidDeck implementation
was copied. Valve's actual manifest contains ARM64 ELF components; the selected
channel is `steamdeck_publicbeta`, version `1792192922`. The committed lock pins
17 ZIPs / 360,938,891 bytes; they expand to 960,528,505 bytes, including 12 verified
internal library aliases. Preserve official filenames, hashes and license files.

The [Valve beta requirements](https://github.com/ValveSoftware/steam-for-linux/blob/master/README.beta.md)
describe kernel/glibc, namespaces, D-Bus, X11 and graphics/audio requirements.
They are requirements to investigate, not evidence of successful execution here.
The [Steam Subscriber Agreement](https://store.steampowered.com/subscriber_agreement/)
does not give this project blanket redistribution permission. No Valve binaries
are committed, placed in the app payload or uploaded to a Release. Downloads and
the resulting installation are private local experimental inputs. No agreement,
account login or game installation is automated. Stop at any newly presented
agreement and request the owner's decision.

## Inputs and installation

`tools/steam_client.py` has separate `capture`, `download` and `install` operations.
Capture writes a new lock; do not silently update an existing pin. Download uses
only approved official HTTPS CDNs and checks each exact size/SHA-256. Install
requires a new destination, checks space, rejects overlapping entries/traversal,
and extracts regular files before bounded internal aliases. Publication is atomic
and never replaces an installation. Linux requires `renameat2(RENAME_NOREPLACE)`;
DrvFS/9p rejects this operation here, so install inside guest ext4, not `/mnt/e`.

`tools/steam_dependencies.py` resolves the ELF-derived package requirements
against the authenticated, pinned Debian index. It preserves every accepted GUI
package/version. `ipa/steam-dependencies.lock.json` pins 41 additional packages /
17,714,248 bytes; this is a static dependency inventory, not a runtime pass.

`guest/steam/install-cached.py` is an explicit private-QEMU-cache mode. The host
binds its HTTP server only to loopback; the guest uses QEMU's `10.0.2.2` alias.
There are no proxies, redirects, credentials or general HTTP fallback. All bytes
still must match the independently obtained official locks. It configures only
the new guest disk and requires both `dpkg --audit` exit0 and empty output, then
verifies every pre-existing package version. The client is installed with UID1000
and HOME `/home/ideck` into `/home/ideck/.local/share/Steam`. Existing installations
are refused, never repaired or overwritten automatically.

After successful publication and alias creation, only the17 verified installer
ZIP cache files are removed from the guest to leave space for Valve's own updater.
Every pinned cache file is checked before deletion; foreign files are preserved.
The host download cache remains available for a new private test disk.

## Running the experiment

Use the existing pinned host QEMU10.0.13 with its matching extracted Debian ELF
loader. This differs from iOS QEMU10.0.12-utm. If `qemu-img` is absent, extract the
matching authenticated `qemu-utils` package into a task-local directory; do not
install a system package. Supply its extraction receipt with `binary_sha256`.

Build an experiment initramfs using:

```sh
python3 tools/prepare_steam_bootstrap.py \
  --initramfs "$GUI/initramfs-desktop.gz" \
  --modloop vendor/alpine-3.24.1-aarch64/modloop-virt \
  --unsquashfs "$EXISTING_UNSQUASHFS" --output "$TASK/bootstrap"
```

The builder verifies accepted GUI inputs and exact Alpine6.18.35 modules, adds
`failover`, `net_failover`, `virtio_net`, and creates a separate `/ideck-steam-init`.
The original GUI PID1 and its shutdown procedure are preserved. Only the explicit
experiment init grows the new overlay filesystem and enables networking.

Run the host-only profile with `tools/steam_vm.py`:

```sh
python3 tools/steam_vm.py --host "$HOST_TOOLS" \
  --seed "$GUI/gui-rootfs-v1.raw" --kernel "$GUI/vmlinuz-virt" \
  --bootstrap "$TASK/bootstrap" --cache "$TASK/client-cache" \
  --debs "$TASK/deps-cache/debs" --commands "$TASK/commands" \
  --qemu-img "$TASK/image-tools/usr/bin/qemu-img" \
  --image-tool-receipt "$TASK/image-tools/receipt.json" \
  --output "$TASK/new-run" --seconds 1100 --enable-experimental-network
```

All paths must remain on the task's E: storage. `--output` must not exist. The
runner never resumes a dirty disk or automatically recreates an existing one.
Its command queue accepts explicit `NNN-name.sh` guest scripts, executes each
once, records exit status and a real QMP screenshot. A `STOP` file requests the
production independent control-channel stop. A fresh output means a fresh disk;
existing overlays and user disks remain untouched.

After GUI readiness, run inside the new guest:

```sh
python3 /opt/ideck-steam/install-cached.py --port PORT --private-qemu-cache
```

From the existing desktop user's terminal, use `ideck-steam desktop`, then
`ideck-steam stop` to return to Debian Desktop. `ideck-steam big-picture` requests
the upstream gamepad UI flags. Each command requires the existing X11 authority,
UID1000 HOME/runtime directory and a valid or newly started session D-Bus. A real
launch lock and process check refuse a second client. CEF software rendering is
explicit; Chromium sandbox remains enabled. Android/proot preloads and service
impersonation are not transferred. No launcher return code proves a visible UI.

The guest Stop still terminates writers, syncs and unmounts before poweroff. The
host runner additionally waits for its QEMU subprocess to exit and host fsync to
succeed; only then may it clear `needs-recovery`. A timeout, forced exit or fsync
failure remains failed. This does not weaken the embedded iOS lifetime contract:
its owner thread and disk lock still remain retained until application exit.

The observed Cortex-A72 attempt exited132 before its first window. The experiment
profile now uses QEMU `max`; a fresh run displayed the real Steam updater. Its
self-update requested additional669522KB and was interrupted by clean VM Stop
when E: approached exhaustion. This establishes the native updater window only,
not the main client or Big Picture. The current chroot also returns EPERM for an
ordinary user's user/mount namespace probe. A proper Steam root namespace needs
work before CEF sandbox readiness can be claimed; do not disable the sandbox.

Actual outcome and evidence are recorded in HANDOFF and the experiment receipt.
Software UI rendering does not establish playable performance or GPU acceleration.
