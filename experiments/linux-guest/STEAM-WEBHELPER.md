# Webhelper startup: bounded diagnostic evidence

Static inspection of the pinned official ARM64 client and the existing host
`run5/015`–`018`, `024` logs was performed without operating the VM or disks.
No default launch flags or sandbox policy were changed by this inspection.
The precise input hashes and small disassembly excerpts are in
[`evidence/steam-cef-static-20261017`](evidence/steam-cef-static-20261017/analysis.json).
Valve binaries remain in the private local cache, outside Git and payloads.

## Verified flag effects

`-cef-disable-hang-timeouts` is registered in the exact pinned
`steamrtarm64/steamclient.so` with the description “disables GPU and renderer
hang timeouts”. Its consumer at `0xeb6030` checks the registered parameter and
adds Chromium `--disable-hang-monitor` and `--disable-gpu-watchdog`.
These are distinct from sandbox controls. This establishes recognition and
the forwarding behavior; it does **not** establish that the flag suppresses
Steam's webhelper initialization timeout.

There is a separate IPC failure path in that binary: at `0xebbb08` a counter
increments, and a branch can restart the helper after more than four failures.
The message reference and restart calls begin at `0xebbce4`. No check of the
hang-timeouts parameter was found in this inspected path. The precise string
`Timed out waiting for webhelper init` occurs separately in `steamui.so` at
`0x1cb7450`; its full call path was not established here.

`-system-composer` is registered in the exact pinned `steamui.so` with the
description “Force the use of the system browser composer”. Its parameter
object is `0x2547990`; consumers at `0xec8160` and `0xece308` query it and select
composer mode `1` before consulting `OverrideBrowserComposerMode`. It is a
real composition-path override suitable for a bounded diagnostic. Static
inspection does not prove that it fixes Vulkan initialization or that it
produces a working login interface. The host log's missing Vulkan surface
extensions are real, but their causal relationship to the webhelper timeout
has not been established.

## Missing runtime launcher service

The guest log reports `steam-runtime-launcher-service: not found`, followed by
the client disabling that service and continuing into CEF. The pinned native
client has an explicit handling path for child exit status `127`
(`steamclient.so:0xcbce0c`): it logs a diagnostic, stores `-1` for the service
PID and returns (`0xcbcef0`). That path does not terminate the client.

This is not evidence that the service is mandatory for displaying the UI.
Its absence still leaves Steam Runtime/game-launch functionality unverified.
A [Steam Runtime contributor's response](https://github.com/ValveSoftware/steam-for-linux/issues/13475)
identifies it as a Steam Runtime component and distinguishes its absence from
an unrelated audio crash; that discussion concerns another platform and is
not proof of this ARM64 guest's compatibility.

## What the available logs establish

The run reached real CEF browser/renderer processes and repeated helper
restarts; one renderer had UID `1000`, `NoNewPrivs=1` and `Seccomp=2`.
The primary webhelper-init failure remained unresolved in the inspected
`015`–`018` capture. A missing system D-Bus socket, failed Vulkan topology/
surface initialization, and substantial CPU consumption were also observed.
Those observations do not identify a unique initial cause. In particular,
the available memory snapshot did not show exhaustion at that earlier point.

The later `024-shm-capacity.log` does establish a separate resource failure:
`/dev/shm` used all `769449984` bytes, with repeated `26214416`-byte
`u1000-Shm_*` objects accumulated after CEF retries. This can explain a later
shared-memory allocation failure; it does not retroactively prove the first
webhelper timeout was caused by a full tmpfs. The parent runner separately
owns the crash evidence and any clean stop/reboot or bounded flag trial.

No Steam login/Big Picture success or iPhone execution is claimed by this
static inspection. A rendered updater or error dialog is not that success.
