# Debian GUI local rebuild — 2026-10-17

The new locally built Debian ARM64 seed passed **two real production-Alpine GUI
boots** on Windows/Arch WSL. Apple compilation, native link, IPA and GUI on iPhone
are **NOT RUN**. Host QEMU10.0.13 differs from iOS QEMU10.0.12-utm. Rendering is
software Xorg modesetting; no Steam or guest GPU-acceleration readiness is claimed.

## Current evidence and bytes

[Receipt](evidence/gui-local-20261017/receipt.json),
[acceptance](evidence/gui-local-20261017/acceptance.json),
[replay/restore/staging](evidence/gui-local-20261017/payload-validation.json),
[regressions](evidence/gui-local-20261017/regressions.json).
The old [cloud receipt](evidence/gui-alpine-20261017/receipt.json) remains historical
evidence for different seed bytes. It is not the current payload contract.

| Current artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| Raw seed | 1342177280 | `9c4d978f0ea33b608735e203c0e1695ca89188c02b097e610f971cffe1c05791` |
| Compressed seed | 270384751 | `fd9b0da7bc4a88a029aedc60fbfb2f1604c35ccf8d8f935697cb45574b7de44a` |
| Kernel | 10351104 | `47970e0ee0478fe5c60824a89f162d5a353fa29466e5d3bddb0f9c506f1ed756` |
| Production initramfs | 11319304 | `f8d8f4cc92f3f8d49e68adb90ab50d901c54f115d6134ae7030526fdee3de8b4` |
| Transport tar | 292065280 | `112bdba6e12ae182fb347e52e7368e26f748bb3dc2bcd77dbd3122fb14dcdedd` |

Kernel/initramfs/module bytes match the previous production inputs. The raw seed
UUID remains `b66e1c8d-9cbf-45a7-b97b-dcc8f68efca7`; its fresh filesystem/package
configuration metadata changes its hash. It is not identical to the unavailable
cloud tar `4b4b0bb1f75d5b662a8c1d866f482329449ee4d52d181e585ef4964a3540bbdb`.

| Production acceptance | Seconds (whole test) | QEMU sampled peak VmHWM bytes |
| --- | ---: | ---: |
| Boot1 | 105.071 | 977494016 |
| Boot2 | 53.775 | 973451264 |

Both runs verified mapped Xorg/Openbox/tint2/PCManFM/Mousepad/xterm, UID1000 apps,
virtual keyboard typing and editor save, pointer move/resize, tablet wheel ±1,
root right-click menu launching xterm, machine-id persistence, clean control Stop,
QEMU exit0 and read-only fsck. Boot2 read/reopened saved files before new writes.
Both ran normal `dpkg --configure -a`, checked `dpkg --audit` exit0 AND byte-empty
stdout, the exact341-package manifest and 423 real glibc-loader executions.
Seed entry/exit hashes match; QEMU only wrote a new private copy.

## Rebuild inputs and local workflow

`ipa/gui-inputs.lock.json` is unchanged: one signed trixie/main release, authenticated
by-hash indexes,341 ARM64/all GUI packages,94 amd64 host packages and the provision-only
Debian6.12.107 kernel. APT replays the exact dependency closures offline. Existing
local cache/toolchains were reused; missing official .debs were fetched with TLS and
size/SHA checks. Host packages were extracted locally, never system-installed.

The local workspace is `E:\Freddy Fazbear\iDeck.work\gui-local-20261017`. `build.raw` is a14GiB ext4 build volume on E:;
`posix/` is its mountpoint while working. Retain the authenticated cache, clean
`posix/seed-final/seed`, module manifest, lab evidence and `payload-final/rebuild-inputs`.
`env.sh` redirects HOME/TMP/cache to E:, disables Python bytecode/core dumps and uses
the locally extracted official APT/dpkg. `apt-get` only supplies relocated method/CPU
table paths. `run-phase.py` binds the previously verified Debian keyring explicitly;
its package checks are unchanged. No Windows path is assumed available in Apple CI.

Local phases, using the existing `archlinux` WSL and the retained wrapper:

```sh
# Run inside WSL; mount the existing task build volume before continuing.
base='/mnt/e/Freddy Fazbear/iDeck.work/gui-local-20261017'
bash "$base/env.sh" python3 "$base/run-phase.py" prepare
bash "$base/env.sh" python3 "$base/run-phase.py" provision
bash "$base/env.sh" python3 "$base/run-phase.py" inventory
bash "$base/env.sh" python3 "$base/run-phase.py" boot1
bash "$base/env.sh" python3 "$base/run-phase.py" boot2
bash "$base/env.sh" python3 "$base/run-phase.py" seed
bash "$base/env.sh" python3 "$base/run-phase.py" bootstrap
bash "$base/env.sh" python3 "$base/run-phase.py" production
```

These outputs already exist: do not rerun against them or overwrite them. For another
full rebuild, use a new workspace/output set. The ordinary repository CLI entrypoints
implement the same phases; `gui_seed.py` additionally requires `--acceptance` with
provision/boot1/boot2 reports and `--source-sha256` matching boot2's disk hash. A prior
cloud hash is no longer hardcoded. `gui_gate.py --loader-inventory` repeats the guest
loader audit on production boots. `seal_gui_payload.py` binds current sources and
successful reports; `gui_bundle.py prepare` then replays the sealed lock exactly.

Portability changes pair pinned amd64 tools with their own loader/libc and preserve
spaces/trailing whitespace in kmod paths. An initial600s provisioning timeout was
FAILED/forced/dirty (fsck4), recorded under `failed-provision/`, and discarded. A fresh
build passed with a bounded1800s provisioning deadline. Production readiness/Stop/fsck
requirements were not relaxed. No old user disk was opened or repaired/recreated.
The runner now emits a newline before each serial command's output so a late shell
prompt cannot hide the first evdev or machine-id row. A failed lab check exposed this;
the wheel data was present, cleanup clean and read-only fsck0. Both GUI checks were
repeated with the fixed runner. Provisioning evidence retains its actual runner
snapshot/hash; AST comparison requires the whole runner except its inactive GUI else
branch to be identical. Modified imports/top-level code/provisioning/Stop/fsck fail
closed. Both GUI boots require the exact current runner hash. Archived code is never
executed for provenance validation.

The first offline replay failed its kernel-copy hash check; the isolated four-method
copy experiment did not reproduce it. Final storage diagnostics subsequently found
WSL loop0 allocation failure in p9 writes and ext4 writeback errors whose inode numbers
match the rejected replay files. The first syncfs reported prior ENOMEM, the next passed.
See `rejected-replay.json`, `copy-investigation.json`, `build-volume-writeback.log`
and `build-volume-retention.json` in the current evidence. No security setting or
memory configuration was changed and no filesystem repair was run.
A new-directory replay reproduces the exact sealed tar. After unmount and successful
read-only fsck, a read-only/noload remount again verified the accepted seed, frozen lab
snapshot, bootstrap, exact replay tar, restored and staged assets. This storage check
is recorded in `retained-volume-verification.json`; failed copies were never accepted.
The final archive also passed independent Windows hashing and GitHub download-back.
The retained build volume is now unmounted and its staged Husk worktree locked against
pruning. Use the existing `mount-resident.sh` in a separate WSL session to remount it
before accessing `posix/`; that session keeps WSL alive. Do not recreate the volume.
The final tar/checksum remain outside the mount and accessible directly from Windows.

## App lifecycle and Apple gate

Native Desktop/runtime/guest scripts are unchanged. The real Husk Metal framebuffer,
keyboard/modifiers/right-click/scroll, separate `Documents/iDeckDebianGUI-v1/rootfs-v1.raw`,
hash/free-space/ownership/dirty guards and non-replacement import remain in place.
Terminal/Probe/console stay separate. One VM per process and the same retained QEMU
owner thread/disk lock through app exit remain mandatory; loop return alone is not
backend cleanup. A host fsync error remains terminal FAILED. No unlock/cleanup shortcut.

The suite is 295 tests / 292 PASS / 3 explicit Swift SKIP. Native C/user-QEMU/RCU
tests ran; Swift runtime/Apple SDK/native linking/IPA/device GUI remain NOT RUN.
The existing Apple gate must run the actual Swift regressions before native build.
See [delivery](GUI-PAYLOAD-DELIVERY.md) for Release bytes and CI parameters. CI was not
started here. Device acceptance still needs actual windows, input, save/reopen and
Stop across two fresh iPhone launches; successful console testing does not prove GUI.
