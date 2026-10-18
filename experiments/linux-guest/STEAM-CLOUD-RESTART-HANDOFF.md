# Safe checkpoint for the replacement cloud task

## Run21 — more memory did not establish stable navigation (2026-10-18)

The 2560 MiB desktop comparison completed 20 minutes with 351 samples, no
kernel OOM and a minimum 809388 KiB available. A 20.021-second probe recorded
zero selected reclaim, allocation-stall and major-fault deltas. Lifetime reclaim
was nonzero, and increasing guest RAM also increased the default tmpfs capacity;
this was not an independent fixed-SHM experiment.

Actual Store artwork rendered. Library and Add a Game clicks did not establish
working navigation; the main window disappeared temporarily and returned with
a blank body. More RAM therefore did not solve UI continuity. The native client
remained alive while several browser subprocesses disappeared; this evidence
does not identify a fatal signal or the root cause. No Steam game launch,
usable Big Picture or iPhone performance is claimed.

The application still required owned-process termination, including one SIGKILL.
The separate original VM Stop completed cleanly: guest unmount, QEMU0 and host
fsync, no recovery marker, no private namespaces, clean package audit and four
unchanged client ELFs. Full post21 integrity passed run22's read-only preboot
check on a separate copy: all five phases and summary, no errors, original21
preserved. Account logs, screenshots and dump contents remain private.

Run22 compares the same 2560 MiB desktop configuration without diagnostic
LD_PRELOAD, restoring the native 500 ms IPC deadline while retaining the
restart-aware launcher and sandbox. Its result is pending. The iPhone storage
route remains unimplemented; the existing 4 GiB seed contract is unchanged.
Sanitized evidence: `experiments/linux-guest/evidence/steam-local-arm64-20261017/run21`.


## Run20 — measured memory pressure, desktop still incomplete (2026-10-18)

The ordinary desktop control completed 20 minutes with saved login and one
actual updater restart. The main navigation bar appeared, but Store content
remained blank and a visible Library click did not establish navigation. No
usable desktop, Big Picture or Steam game launch is claimed by this run.

Memory pressure is now measured independently of OOM: available memory reached
32,216 KiB; a 20.04-second window recorded 141,011 pages scanned by background
reclaim and 1,774 by direct reclaim, five normal-zone allocation stalls and 332 major
faults. No swap was enabled. All 248 samples and kernel logs had no OOM kill.
This establishes reclaim pressure, not the sole cause of the UI stall. The
kernel has no PSI interface; the corrected read-only probe reports that absence.
Captured dump exception headers indicate requested dumps (0xffffffff), not
fatal signals; raw dump memory and account pixels remain private.

The app's ordinary shutdown timed out and owned-process termination was needed.
The separate VM Stop completed guest unmount, QEMU0 and host fsync; namespaces
were gone, package audit was clean and four client ELFs were unchanged. Full
post20 integrity passed run21's read-only preboot check on a separate copy:
all five phases plus summary, no errors; the original run20 disk was preserved.

Run21 compares 2,560 MiB with 1,536 MiB while retaining desktop mode, CPU,
sandbox and V3 diagnostic. The explicit host-only memory option records both
configured and effective budgets, preserving the pinned default profile.
25 runner and 18 seed-protection checks pass. The comparison result is pending;
it is not an iPhone RAM recommendation. iOS storage integration, Apple build,
device gameplay and Steam/Proton support remain unverified/unimplemented as
described in STEAM-IOS-INTEGRATION.md. Sanitized evidence is in
`experiments/linux-guest/evidence/steam-local-arm64-20261017/run20`.


## Run19 — updater retry confirmed; no kernel OOM (2026-10-18)

The bounded updater restart now has an actual runtime check: run19 recorded one
`update_restart_requested`, restarted the native client and completed login.
The four pinned client ELFs remained unchanged. Big Picture showed loading,
then a black window through the 20-minute observation limit; navigation is not
verified. The guest could resolve Steam and fetch the Store over HTTPS (200).

All 319 kernel samples had `oom_kill=0`, and before/after dmesg contained no OOM
kill. Minimum available memory was 156,884 KiB. A sandboxed helper disappeared
after Steam's own assertion dumper traced its browser parent. This rules out an
observed kernel OOM kill in this run, not user-space allocation failure or other
memory pressure. Forked Chromium children retained `--type=zygote`; an empty
renderer-argument match cannot establish that no renderer exists.

The read-only game inventory found the ARM64 client beside an x86-64 runtime
launcher service, no Proton/FEX candidates and no Vulkan ICD. A render node is
not GPU acceptance. Three inventory tests pass, including architecture reporting
through a runtime symlink and refusing to inspect a symlink outside its root.

Owned application cleanup needed one SIGKILL after the ordinary request and
SIGTERM. This is not a clean client exit. All namespace holders were then absent,
package audit was clean, and the original VM unmount/QEMU0/fsync path completed.
Post19 integrity passed run20's full read-only preboot check on a separate copy:
all five phases plus summary, no errors; original run19 preserved.
Sanitized evidence is in `experiments/linux-guest/evidence/steam-local-arm64-20261017/run19`;
raw account logs, pixels and memory remain private. Run20 compares ordinary
desktop mode with identical resources, sandbox and diagnostic V3. No new iPhone
storage feature, Steam/Proton game acceptance or device result is claimed.


## Night continuation — updater restart and native game checks (2026-10-18)

Run18 observed a real Steam self-update finishing with exit code 42. The old
launcher treated that restart request as failure. The source launcher now retries
at most twice while holding its lock, revalidates the client and refuses a retry
if an old client remains. Three focused tests cover these cases; 32 targeted
launcher/namespace/bootstrap/game-inventory tests pass. At the end of run18 the automatic retry path was only unit-tested; run19 above
subsequently exercised it with the real updater. Big Picture now requests
`-gamepadui` without the SteamOS first-boot flags.

The private V3 diagnostic run reached Big Picture's “Logging in” screen. Login
completed successfully at 22:12:40 UTC; the earlier narrow auth probe missed that
marker. The UI then remained black and its window disappeared. This is not a
working Big Picture/navigation result. The renderer disappeared after sampled
available memory fell to 162,564 KiB, but an OOM kill is not proven. Collect kernel
and renderer-exit evidence before attributing the failure or changing resources.
The stack-safe V3 probe remains diagnostic-only; never use rejected V2.

A separate authenticated Debian ARM64 XGalaga package was installed after Steam
cleanup, preserving all existing package versions. Two launches reached gameplay
with keyboard input; the second actual frame shows score 100. Both exited through
the game's quit key with code 0, without forced signals. These short 70/39-second
checks establish native X11 game/input/relaunch behavior only: not Steam/Proton
compatibility, audio, measured FPS, GPU acceleration or iPhone performance.

Run18 completed the original guest unmount → QEMU0 → host fsync path. All four
client ELFs remain unchanged, no private namespace/game owners remain, and dpkg
audit is clean. Post18 full offline fsck passed all five phases plus summary with no errors;
exclusive ownership and unchanged source SHA before/after were verified.
Run18 preboot's full strict check of run17 passed all five phases and summary.
Sanitized receipts and procedures: `experiments/linux-guest/evidence/steam-local-arm64-20261017/run18`.
Account logs and screen pixels remain private outside Git. Available iPhone
internal storage is still a separate implementation task, not an enabled feature;
see `STEAM-IOS-INTEGRATION.md` for the existing fixed-size disk constraints.

## Local ARM64 continuation — 2026-10-18 (latest)

**V3 correction (latest): V2 is rejected for further Steam runs.** Its C
syscall wrapper broke AArch64 custom-child-stack clone semantics. A real guest
regression passes with libc, gives SIGSEGV in the controlled V2 test child, and
passes with V3's stack-preserving non-futex tail entry; real/raw fallback and
ordinary ABI cases also pass. Earlier narrow ABI tests missed this case. This
is not evidence of a Steam crash, and V2's later UI hangs cannot be attributed
to upstream Steam from these runs. Current source/library hashes and the
rejected historical version are documented in `diagnostics/ipc-connect-wait`.

Run15 restored the user's login automatically and reached native login/library
readiness, but the desktop main window stayed on its loading screen. Closing
Special Offers raised an unresponsive-window prompt; it was cancelled and the
popup minimized, without End Process. A same-client Big Picture URI was
forwarded successfully, but no Big Picture interface was observed. Kernel OOM
count was zero; about600MiB was available and sampled reclaim counters did not
advance. Run15 then completed original unmount/QEMU0/fsync after controlled app
cleanup. Run16 changed only V2 to V3 forwarding, with desktop/resources preserved.
The actual V3 frame gate passed and its first connect woke after177.170713ms.
Saved login persisted. A real QMP frame shows the main Steam Store content
and publisher artwork, after a long blank-content phase. Library navigation
and Big Picture remain unverified: fixed native URI requests were forwarded,
XTest clicks injected, but no visible Library/menu/BP response was confirmed.
Later the main windows disappeared and X BadWindow was logged. Service Worker
not responding is an observed earlier symptom, not a proven cause. No account
pixels or raw post-login logs enter Git. Controlled app cleanup required
native SIGKILL; original VM Stop then completed unmount/QEMU0/host fsync.
All four client ELFs are unchanged, no private namespace holders remain and
dpkg audit is empty. Full post-run15 fsck passed strictly (all five passes).
Run17 tests removal of the diagnostic preload with the original helper,
launcher, native500ms and unchanged resources; its preboot full fsck checks
the clean run16 disk before any new writer. This is not yet a successful BP
or navigation result. See run16/screen-stage-receipt.json in local evidence.

The owner resumed local work. Run14 **reached the real Steam Big Picture
sign-in screen**, verified from a QMP screenshot, then refreshed its QR through
actual XTest mouse input. The user scanned/approved it; the final authenticated frame is Steam Deck's
Welcome language wizard. Main/library UI and navigation remain pending.
QR/account screenshots are private on E:, never public Git evidence. These are
host QEMU/TCG results, not iPhone/Apple/GPU/game acceptance.

The causal measurement advanced: unchanged observe-mode connect waits failed
ten times at about500ms before any manual freeze or ptrace. An opt-in, digest/
mapping/frame/UID/syscall-gated interposer changed only this native connect wait
to5s; the same verified call returned0 after3.322421696s. One browser then reached
BrowserReady, SharedJS paint and Big Picture login without SHM runaway. CPUmax,
4vCPU,1536MiB,12GiB, software rendering and forced CEF sandbox are unchanged.
The normal launcher/helper are unchanged; own source and tests are in
`diagnostics/ipc-connect-wait`. This probe is not enabled by default.

The Steam-only stale-X preflight repairs copied-disk Xorg prerequisites.
Diagnostic browser recognition now requires direct native PPid; optional trace
`--tid` selects only a verified existing subset.44 targeted source tests pass;
the historical narrow ABI passes below are superseded by the V3 regression above. All45 locked
dependencies and four installed client ELFs persisted through runs13/14 without
reinstallation. Run11's busy-unmount/forced-stop disk remains rejected and
preserved; runs12/13 stopped cleanly and following full offline fscks passed.
Run14's original VM Stop completed unmount/QEMU0/fsync after controlled owned
application termination (native Steam required SIGKILL). Run15 is a fresh copy
with a full offline check and the same connect probe; only launcher mode changes
to desktop, avoiding the SteamOS-specific startup flags. Main UI is not yet
claimed. Its operator monitor budget is longer; no Steam timeout was changed.
See [exact results, limits, private screenshot hashes and continuation gates](evidence/steam-local-arm64-20261017/README.md).

**Latest requested network recheck:** started at verified Steam remote
`12074eaf…`, a descendant of the requested `bfcb3a8…`. A new full first locked
Fastly ZIP GET returnedHTTP200 with exact size/hash. Actual production9c4d inputs,
both stopped installed disks,17 ZIPs,45 dependency packages, qemu-utils receipt
and all7 evidence manifests/338 files match; storage entry gate passes.
Current allowed-host system DNS still returns EAI_AGAIN and the configured
resolver refuses UDP53. The actual native updater host is absent from the three
announced additions; its prior CONNECT403 was not retried. No VM/image write,
policy/proxy/DNS/TLS/runtime/security change or cleanup ran. Read
[new receipts and exact remaining owner/platform prerequisites](evidence/steam-network-recheck-20261017/README.md).
Preserved guest audit/fsck results were revalidated, not newly run. UI/Big Picture
remain NOT REACHED;149 Steam regressions PASS. All private originals remain here.

**Latest read-only follow-up:** the selected cloud remained accessible after a
reported disconnect; installed disks/caches rehashed unchanged, no VM or writer.
At verified remote Steam `d0a8201f…`, exact native code establishes application
proxy discovery / `-bootstrapperproxy` / HTTPS CONNECT, but guest proxy
reachability/resolution, TLS and approval for the new updater host remain
unverified. The denied hostname was not retried. No DNS/proxy/security patch was
made. Static Chrome-init readiness is now mapped to the controller's shared IPC
connection byte. Read [current findings and exact approval boundary](evidence/steam-proxy-ipc-static-20261017/README.md)
before any continuation. UI/Big Picture remain NOT REACHED.

**Fresh-task follow-up:** the next executor actually downloaded all17 locked
Steam ZIPs and the exact production Release, restored production9c4d and installed
the client/45 dependencies on an independent cloud disk. It is now stopped after
two clean VM boots/Stops, persistence and two strict full offline fsck checks.
Its updater is blocked by host CONNECT403 for `client-update.steamstatic.com` and,
separately, guest DNS EAI_AGAIN for both Steam hosts. Main UI/Big Picture remain
NOT REACHED; no CEF browser existed for IPC/stack capture. Read the current
[fresh cloud evidence and private input/continuation boundary](evidence/steam-fresh-network-20261017/README.md)
before using the older transition inventory below. No old a7758d82 bytes were
transferred or substituted. No network/security policy was changed.

The owner published a new network configuration and requested a **fresh task**.
Owner/parent-reported version:
`71a66f3c-3170-475c-82f6-cf3dc0ded790~cecfgver_6ad378804dc88199be22c7b77b1cebb4`.
This old task did not apply it, retest denied URLs, change policy or start a new
VM. Its last read-only process/mount check found **zero QEMU processes and zero
task image mounts**. There is no VM left to stop. No new dependency disk exists.
The parent will start one replacement executor only after this task ends.

Repository: `https://github.com/Mi-Yomi/iDeck.git`.
Branch: `codex/steam-arm64-experiment-20261017`.
Implementation/evidence checkpoint:
`26daced6d5ba1578998ff1f293ec3547e8d4f226`.
This handoff is a following documentation-only commit; use the full final SHA
returned by the parent for the fresh checkout. Verify remote/branch/HEAD and
foreign changes before work. Keep one agent, cloud only; no laptop/Windows/WSL,
main/GUI branch changes, GUI payload/Release mutations, CI or force-push.

## What is in Git

- Read `HANDOFF.md`, `STEAM-IPC-HANDOFF.md`, `STEAM-IOS-INTEGRATION.md` and the
  evidence indexes. No repo/ancestor AGENTS.md or repo `.agents/skills` existed
  in this old checkout; inspect the fresh environment's instructions again.
- `profiles/steam-experimental-seed-20261017.lock.json` is the explicit reviewed
  contract for the independent experimental raw seed `a7758d82…`.
  SHA-256: `44c00d8e354033f684b0194837419ef6d82bafd299f9a53c7fc831f86b2df2bc`.
- `tools/steam_seed.py` verifies actual seed/kernel/bootstrap/receipt bytes,
  repository bindings, all 105 pinned acceptance artifacts, real Alpine boot
  source/persistence data and full fsck streams. An external/self-asserted
  contract or mismatching seed fails closed. The production `9c4d978f…` GUI lock
  remains unchanged and is still the default without the explicit runner flag.
- `tools/steam_vm.py` supports `--experimental-seed-contract PATH`, binds that
  contract on continuation and checks full offline-copy +4GiB reserve before
  initial image writes. Existing ownership/dirty/Stop gates remain intact.
  Offline fsck now uses the pinned extracted checker/loader pair; the old cloud
  host had no global `/usr/sbin/e2fsck`.
- 148 Steam tests PASS. Real read-only verification in two independent processes
  produced configuration SHA-256
  `d07392982666405ea54b33aabbb5db806e085bdc26ee4ac08e4f6c294adaad2b`.
  It binds both Python startup snapshots and the exact inputs/profile. A real
  other 1.25GiB seed was refused. Actual runner preflight made zero image/VM
  calls and no output directory because storage failed.
- See `evidence/steam-seed-contract-20261017` for config/rejection receipts,
  dependency cache verification, host closure, inventory and safe storage plan.
  See `evidence/steam-cloud-seed-20261017` for the separate seed's five successful
  boots, real GUI input/persistence, six strict fsck checks and screenshots.
- No raw disk, compressed seed, Valve client or Debian package cache is in Git.

## Private inputs present in the old task only

All following paths are relative to `/workspace/steam-cloud-20261017` in the
**old selected private workspace**. A fresh task is not guaranteed to inherit
them. A path is not delivery: inspect actual available storage and rehash files.
No disk/client was uploaded or published for this transition.

| Input path | Bytes | SHA-256 |
| --- | ---: | --- |
| `experimental-seed-v4/seed/gui-rootfs-v1.raw` | 1342177280 | `a7758d821f67ec48646d4586ec54aeab8b8db31238f0be6dfaabc5966c46a5a2` |
| `experimental-seed-v4/seed/gui-rootfs-v1.raw.gz` | 270444186 | `a5f23c8978bdef7846a800fd3c6207fe032ed4f1bc48450fe17a1704c0f6d05d` |
| `gui-bootstrap/vmlinuz-virt` | 10351104 | `47970e0ee0478fe5c60824a89f162d5a353fa29466e5d3bddb0f9c506f1ed756` |
| `gui-bootstrap/initramfs-desktop.gz` | 11319304 | `f8d8f4cc92f3f8d49e68adb90ab50d901c54f115d6134ae7030526fdee3de8b4` |
| `steam-bootstrap/initramfs-steam.gz` | 11665437 | `6a0081d76fedbb38b72e705334513313093b46e701907ed8b6d516640978df7f` |
| `steam-bootstrap/bootstrap.json` | 4476 | `d6533c920dd548c61ac560d77e0d4d561eb3594e7e9519ae7998dd67da01f913` |

Additional old-task inputs:

- `deps-cache/debs`: all 45 additional locked ARM64/all packages, 18238048 total
  downloaded bytes, last rehashed successfully. **Not installed in a Steam VM**;
  its successful byte-empty dpkg audit is NOT RUN.
- `gui-cache`: signed cached Debian metadata and 432 unique GUI/provision/host
  inputs for the 341 guest package pins, 94 host pins and provisioning kernel.
  Revalidate with the existing pinned tools before use; preserve source files.
- `gui-lab/host`: actual extracted QEMU10.0.13 and matching loader/libc/e2fsck.
  Pinned e2fsck SHA-256:
  `be1f2c99e0dc73640cffb549da5f3f4b15da0f89e7334c6730feb69eff784571`.
  `gui-lab/kernel`, `alpine-modules`, `module-tools`, `unsquashfs` and build
  receipts also remain private. Matching modloop bytes are independently in Git
  at `vendor/alpine-3.24.1-aarch64/modloop-virt`, hash `f969d12c…47b`.
- All originals, frozen lab images and failed outputs are retained. Nothing was
  deleted to gain space; `space-inventory.json` distinguishes allocated/logical
  bytes and shared inodes.
- `client-cache` is empty: **0/17 Steam ZIPs**, no installed cloud Steam client.
  The owner's installed local Steam disk was never transferred or accessed.

`qemu-img` and its extraction/binary receipt are still absent. Offline signed
metadata/solver verified the only missing host package is `qemu-utils`
`1:10.0.13+ds-0+deb13u1`, 2024216 bytes, SHA-256
`6d31339b1630153fe7c5f8a51426b8fa6ce35731aeb015a84f2d333c4e4dca30`.
All other dependencies match existing host pins. Materialize through the
authorized official Debian route only after checking space; no system install.

## First steps in the fresh task

1. Confirm the requested new environment version and recheck its actual files,
   tools, available bytes and owners. Network availability in the new version
   has not been tested here. Do not resume an old command queue/output.
2. If the private `a7758d82…` bytes are actually available, use the explicit
   contract and rehash them. Do not pretend a rebuilt filesystem has that hash.
   From `experiments/linux-guest`, the read-only check is:

   ```sh
   python3 tools/steam_seed.py \
     --contract profiles/steam-experimental-seed-20261017.lock.json \
     --seed /ACTUAL_PRIVATE_INPUT/gui-rootfs-v1.raw \
     --kernel /ACTUAL_PRIVATE_INPUT/vmlinuz-virt \
     --bootstrap /ACTUAL_PRIVATE_STEAM_BOOTSTRAP \
     --storage-root /ACTUAL_NEW_OUTPUT_FILESYSTEM
   ```

   Exit0 means preparation gates only; exit2 means valid contract/blocked space;
   exit1 rejects inputs/provenance. For a later VM explicitly pass the same
   contract with `--experimental-seed-contract`; do not alter the GUI lock.
3. If that private seed is absent, the authorized production GUI Release remains
   an independent legitimate route: asset650023557, 292065280-byte tar, SHA-256
   `112bdba6e12ae182fb347e52e7368e26f748bb3dc2bcd77dbd3122fb14dcdedd`.
   Verify/restore with the pinned GUI tools and use the production `9c4d978f…`
   default **without** the experimental flag. Record an independent fresh disk.
   No `a7758d82…` substitution/claim is allowed. If both deliveries are absent,
   the pinned builders can create another independent seed, but its new hash
   needs full acceptance and an explicitly reviewed separate contract.
4. Recompute storage for this fresh filesystem. The old task had 15690088448
   available bytes, below the17179869184-byte entry floor. Its conservative
   available-free target including full overlay, offline copy, reserve and known
   new caches/tools was30612663459 bytes. These are old-workspace observations,
   not an assumption about the fresh task. Preserve all source images/data.
5. Reuse an existing authorized private Release connection. Only in the new task
   may the owner-approved network routes be tested/downloaded. Exact URLs and
   narrow hosts are in `evidence/steam-cloud-seed-20261017/NETWORK.md`; all17
   pinned Steam URLs/hashes are in `locked-downloads.json`. Shell API had
   `Forbidden` without HTTP status/body; the public Steam CDN had tunnel403 on
   its first ZIP. GitHub connector metadata worked but its text fetch did not
   support binaries. Do not invent credentials, leak signed URLs or bypass403.
6. After actual host/guest storage gates and image tools pass, create only a new
   disposable Steam disk, preserve read-only backing and exclusive ownership,
   install the45 locked deps and require dpkg audit exit0 AND byte-empty output.
   Keep namespace helper/UID1000/HOME/X11/D-Bus/network and `-cef-force-sandbox`.
   No sentinel/cache deletion, live SHM cleanup, guessed timeout/CPU changes or
   sandbox/security bypass. Read the IPC handoff before any bounded Steam run.

This remains preparation. The exact Steam archive is built/not booted here;
main Steam UI/Big Picture/input/restart, Steam RAM/SHM/IPC/ARM64 stack capture,
Apple/iPhone and GPU acceleration remain NOT RUN. Stop at account/new terms
for the owner; no secrets in chat or games. No long run/download was begun by
this final handoff checkpoint.
