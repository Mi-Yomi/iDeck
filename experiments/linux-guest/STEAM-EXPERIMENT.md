# Private ARM64 Steam host experiment

This branch adds a real-client experiment above the accepted Debian Desktop. It
does not enable a Steam app button, change the accepted GUI payload or certify
Steam on iPhone. The separate [profile](profiles/steam-host-experiment.json)
requires explicit QEMU user networking and a new qcow2 overlay. The accepted seed
is verified against `ipa/gui.lock.json` and remains a read-only backing file.

The follow-up has reproduced the exact [LSE CPU fault](STEAM-CPU.md) and verified
the [private Debian root namespace correction](STEAM-NAMESPACES.md), including
real UID1000 user/mount/PID namespace and private-proc creation. No sandbox flag
or system security policy is disabled. Actual client/UI outcomes remain recorded
separately in HANDOFF and runtime evidence.

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
package/version. `ipa/steam-dependencies.lock.json` pins 45 additional packages /
18,238,048 bytes; this is a static dependency inventory, not a runtime pass.

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
Pass `--retain-client-cache` to the guest installer when the experiment requires
preserving those installer ZIPs too. The full size/hash/owner checks still run;
the receipt records the retained count. Runtime cache and sentinel files are
never removed by this installer.

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

Use the selected private cloud task storage; do not access the owner's laptop.
`--output` must not exist. The
runner never resumes a dirty disk or automatically recreates an existing one.
Its command queue accepts explicit `NNN-name.sh` guest scripts, executes each
once, records exit status and a real QMP screenshot. A `STOP` file requests the
production independent control-channel stop. A fresh output means a fresh disk;
existing overlays and user disks remain untouched.

To continue a previously stopped **private experiment**, explicitly add
`--continue-from "$TASK/previous-run"` with another new `--output` directory.
The runner checks that run's clean evidence, seed identity, absence of a recovery
marker and exclusive ownership. It creates a new copy through QEMU's read-locked
image backend, verifies the original did not change, and performs read-only
`e2fsck -f -n` on a flattened offline copy before starting any VM. Failed checks
are never repaired automatically. Existing files and dangling output symlinks
are refused; image output is bound to a newly created exclusive file descriptor.
The experiment's new virtual disk capacity is 12 GiB. Allow space for the source,
new overlay and a temporary full-size raw check; retain several GiB of free space
inside the guest for Valve's update staging.

### Explicit cloud experimental seed

The default runner path still requires the production GUI seed in
`ipa/gui.lock.json`. To select the separate accepted cloud seed `a7758d82…`,
explicitly supply `--experimental-seed-contract
profiles/steam-experimental-seed-20261017.lock.json` along with its actual raw
seed/kernel/bootstrap paths. The reviewed contract pins the complete acceptance
manifest and checks real boot/persistence/source identities and full fsck output.
It preserves the production GUI lock and is never an automatic hash fallback.
Continuation also requires the same contract hash. A future real run retains
startup snapshots of both the runner and validator.

`tools/steam_seed.py --contract PATH --seed RAW --kernel KERNEL --bootstrap DIR
--storage-root DIR` performs only read-only input/configuration and storage
checks, printing a canonical configuration hash. Exit0 is preparation only;
exit2 means a valid seed contract but insufficient storage; exit1 rejects inputs.
The runner checks the existing full-size offline-copy +4GiB reserve policy before
initial image writes, and rechecks it after continuation copies as before.
Offline fsck uses the authenticated extracted host e2fsck/ELF-loader pair rather
than requiring a system-wide checker. No checksum, space, Stop or ownership gate
is relaxed. Current receipts, exact command and the no-deletion storage plan are
in [contract preparation evidence](evidence/steam-seed-contract-20261017/README.md).

After GUI readiness, run inside the new guest:

```sh
python3 /opt/ideck-steam/install-cached.py --port PORT --private-qemu-cache
```

The ordinary-user launcher provides `desktop`, `stop` and `big-picture` modes;
the last requests the upstream gamepad UI flags. Start it through the namespace
entry point below. Each command requires the existing X11 authority,
UID1000 HOME/runtime directory and a valid or newly started session D-Bus. A real
launch lock and process check refuse a second client. CEF software rendering is
explicit; Chromium sandbox remains enabled. Android/proot preloads and service
impersonation are not transferred. No launcher return code proves a visible UI.

The original chroot cannot create the namespaces Chromium needs. For the separate
Steam profile, use the recovery console's fixed root setup entry point:
`python3 /opt/ideck-steam/namespace-check.py launch desktop` (or `big-picture`).
The helper creates a private real Debian root, passes both unprivileged preflights,
then executes the ordinary UID1000 launcher. It does not run Steam as root, make
the helper setuid, or change the accepted Desktop route. `ideck-steam stop` still
requests client shutdown and returns to the existing Debian desktop.

The guest Stop still terminates writers, syncs and unmounts before poweroff. The
host runner additionally waits for its QEMU subprocess to exit and host fsync to
succeed; only then may it clear `needs-recovery`. A timeout, forced exit or fsync
failure remains failed. This does not weaken the embedded iOS lifetime contract:
its owner thread and disk lock still remain retained until application exit.

The original Cortex-A72 attempt exited132 before its first window; the exact
LSE fault is now documented in `STEAM-CPU.md`. The host profile still uses `max`.
An explicit copy of the retained installation completed Valve's self-update.
The corrected private root allows real UID1000 CEF children with seccomp and
user/PID namespaces enabled. This does not establish the main UI or Big Picture:
the later webhelper-init timeout and a secondary shared-memory exhaustion are
recorded separately in `STEAM-WEBHELPER.md` and the continuation evidence.
Do not retain unsuccessful diagnostic flags or disable the sandbox.

Actual outcome and evidence are recorded in HANDOFF and the experiment receipt.
Software UI rendering does not establish playable performance or GPU acceleration.
