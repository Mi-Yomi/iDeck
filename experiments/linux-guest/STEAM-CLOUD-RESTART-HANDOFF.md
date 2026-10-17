# Safe checkpoint for the replacement cloud task

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
