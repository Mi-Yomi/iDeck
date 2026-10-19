# Owner offline cache and experimental Auto RAM

Delivered result: **[Apple CI finished](https://codemagic.io/app/6ad03ce9a8a969b53f3a4aa9/build/6ad595967550aed810900168)** for built source
**`7782926dffb3ab513715518c18f8e667ca3c0c40`**. The coordinating executor confirms
LINUX_STEAM_FRESH_HANDOFF_PASS, LINUX_STEAM_AUTO_MEMORY_PASS,
LINUX_STEAM_OFFLINE_CACHE_PASS, typecheck/native build/link/resources PASS.
IPA **710858044 bytes**, SHA-256
`ad404c43b6899fc2b8787df33e835792a5f4f4c6377b838a18e12b552bc9b373`, **ad-hoc**.
Private Drive delivery to the owner is confirmed; no personal delivery link is
stored in this repository. These are coordinating-executor supplied results;
this documentation update did not rebuild/download IPA or start CI. The docs
commit differs from the built source SHA.

**Device NOT RUN; real owner cache NOT PREPARED.** The delivered IPA contains
code for import/offline source/Auto RAM, no bundled Valve bytes. Physical RAM,
readonly guest-cache boot/import with actual packages and Steam behavior remain
unverified. Disk remains12 GiB, no resize. The experimental4096 MiB ceiling is
not a physical-device acceptance. Standard Steam update/login/agreements may
still require internet and owner action after local package extraction.

Latest coordinator quota snapshot: **106 free macOS minutes, paid OFF**, below
our120-minute requirement. **Do not start a new CI under this snapshot.** Any
future build requires a fresh >=120-minute check and existing approvals. No
threshold or security setting was changed.

The owner can now prepare all17+45 exact locked inputs and the canonical TAR
with the separate host-only command below, under the applicable terms, then
transfer the private TAR to the phone, Import before Steam Start and use
Install/resume for offline extraction. Existing pack/verify is unchanged.
No real input acquisition/packing, transfer, owner-PC execution or agreement
acceptance was performed here. The delivered app, overlay and payload did not
change; this host-only addition needs no new app CI.

## One-command preparation on the owner's PC

From the owner's updated checkout, using existing Python3.11 and a native NTFS
output volume (Windows execution **NOT RUN** here):

```powershell
py -3.11 'E:\Freddy Fazbear\iDeck.work\steam-arm64-experiment-20261017\experiments\linux-guest\tools\steam_offline_download.py' --directory 'E:\Freddy Fazbear\SteamOffline'
```

The checkout path must match the actual owner checkout; this command was not
executed on that PC. It downloads only the existing17 Valve lock names from
the locked manifest's official Fastly origin and45 Debian pool paths from the
existing official Debian contract. The Debian lock must match the accepted
GUI input hash and release descriptor. No new/current manifest, mirror,
credentials or version override is accepted. This verifies captured lock pins,
not a newly authenticated Debian index or the latest Steam client.

Standard CA/hostname-verified HTTPS only, no proxy credentials or TLS bypass.
**All redirects are refused**, including same-origin redirects; a redirect/404
requires source review, never a fallback or silent repin. Each request has a60s
socket timeout, bounded1 MiB reads, exact size/SHA and a15-minute elapsed check
between reads. Content length, if supplied, must be exact; encoded responses
are refused. Files remain temporary until fsync and an independent rehash, then
publish by atomic no-replace rename using the existing Windows/Linux helper.
No files are extracted/executed and no agreements are accepted.

The command automatically packs/verifies the62 files using the unchanged
`steam_offline_cache.py` and prints the real TAR size/SHA. Result:
`E:\Freddy Fazbear\SteamOffline\owner-steam-cache.tar`, **379228160 bytes**.
Input bytes plus TAR are **758405099 bytes**; allow at least2 GiB initially.
A preflight requires missing inputs + TAR +1 GiB reserve. Existing verified
output is checked and reported without network or repacking. Keep this personal
cache local/private; do not add it to Git, Release, CI or the IPA.

After an interrupted/error run, repeat the exact command. All completed input
files are rehashed and reused; the unfinished component restarts from byte0.
There is no HTTP Range continuation. Corrupt existing inputs/output and unsafe
links are preserved and refused, never automatically deleted/replaced. Soft
interruptions remove the command's own temporary file. A hard process kill may
leave a randomly named private temporary file or pack directory; retry ignores
it and does not delete files that could belong to another active run. Such
orphans can consume space until the owner reviews them with preparation stopped.
Symlinks, hardlinks and Windows junction/reparse paths are refused. Unsupported
atomic rename/filesystem behavior fails closed; native Windows/NTFS is intended,
not WSL on a Windows-mounted volume. Existing manual pack/verify below remains
available if the owner already has the exact pinned files.

**575 tests OK (570 PASS, 5 SKIP)**, offline synthetic transport only. This
includes62-part download/pack/verify, repeat with network forbidden, retry after
interruption, wrong hash/size/status/URL/encoding, unsafe paths, no-replace races,
verified TLS context and redirect refusal. Full overlay/generator/source pin and
original real Steam staging checks passed without changing their files.
Evidence: `experiments/linux-guest/evidence/steam-offline-download-20261019/`.
Live official download/URL availability, actual Windows execution, real owner
cache preparation and device acceptance **NOT RUN**. No actual TAR digest is
claimed, no Valve bytes downloaded, and no new CI was started. BusyBox source
provenance remains OPEN.

The following preserves implementation history and the original Linux checks;
Apple checks for the built SHA above subsequently passed, device checks did not.

Fresh-handoff correction after review of `756e08c44456f62b48d45a9f08fdaf42321c34b3`:
that source measured before synchronous report/journal IO, then persisted again
before QEMU. The shared production gate now completes all blocking preparation
IO, samples/rechecks and atomically commits entry; handoff has no intervening
synchronous persistence or extra queue hop. Mandatory crash-journal fsync still
precedes entry. Post-entry report persistence is asynchronous and cannot release
native ownership on failure. A memory refusal retains the userdata lock/dirty
bytes and closes that preparation permanently; attempted is not reset.

A mandatory `LINUX_STEAM_FRESH_HANDOFF_PASS` Swift fixture injects deterioration
while a real journal fsync is held at a semaphore barrier, checks retained real
flock/synthetic dirty-header bytes, rejects repeated entry and failed journal
sync, and covers success/non-Steam controls. **560 Python tests OK (555 PASS,
5 SKIP)**; generators/overlay/real staging/pins PASS. New Swift/Apple/QEMU/device
execution **NOT RUN** here. Evidence is in
`experiments/linux-guest/evidence/steam-fresh-handoff-20261019/`. The coordinator
reports holding/stopping the 756e08c CI; this task did not dispatch/cancel CI.
The OS may still change headroom after any preflight; this check does not reserve
physical RAM or establish protection from jetsam.

The following describes the underlying offline-cache/Auto implementation.

Source baseline: `33ece4ee09c7f8953a57b88827740a3ee3008fd6`, Steam branch only.
The original source candidate followed IPA #35, built at
`209315cd8b330c0ba1b5a7a28f2cf2884a86dafa`, which predates this update.
No new CI, download/client execution, agreement acceptance, private package
publication or actions on the owner's PC were performed here.

## Owner-local cache: implemented source path

The original pack/verify tool reads only the17 pinned Valve ZIP filenames and
45 Debian .deb filenames from owner-obtained directories. It performs bounded SHA-256/size and
regular-file/identity checks, then writes canonical deterministic USTAR. It does
not read account directories, download anything, run Steam, install packages,
accept terms or upload an artifact. It refuses existing output and unsafe links.
Only metadata, own code and synthetic fixtures are committed; no Valve bytes.

After obtaining the exact official pinned inputs under their applicable terms,
the owner can run these commands locally (not executed here with Valve inputs):

```sh
python3 experiments/linux-guest/tools/steam_offline_cache.py pack \
  --client-directory /path/to/17-pinned-zips \
  --debs-directory /path/to/45-pinned-debs \
  --output owner-steam-cache.tar
python3 experiments/linux-guest/tools/steam_offline_cache.py verify owner-steam-cache.tar
```

For Windows PowerShell with an existing Python3.11 installation and an NTFS
output volume (actual Windows execution NOT RUN), after placing the files in
`E:\Freddy Fazbear\SteamOffline\client` and `...\debs`, use the following.
`$repo` must point to the owner's checkout containing this tool and these locks;
no checkout update/download or PC action was performed by this docs task.
The output must not already exist.

```powershell
$repo = 'E:\Freddy Fazbear\iDeck.work\steam-arm64-experiment-20261017'
$stage = 'E:\Freddy Fazbear\SteamOffline'
$tool = Join-Path $repo 'experiments\linux-guest\tools\steam_offline_cache.py'
$out = Join-Path $stage 'owner-steam-cache.tar'
py -3.11 $tool pack --client-directory (Join-Path $stage 'client') --debs-directory (Join-Path $stage 'debs') --output $out
if ($LASTEXITCODE -ne 0) { throw 'Cache packing failed' }
py -3.11 $tool verify $out
if ($LASTEXITCODE -ne 0) { throw 'Cache verification failed' }
(Get-Item -LiteralPath $out).Length
Get-FileHash -LiteralPath $out -Algorithm SHA256
```

Input names, versions, sizes and hashes come only from
`ipa/steam-client.lock.json` (17 ZIP) and `ipa/steam-dependencies.lock.json`
(45 .deb) under `experiments/linux-guest`. Input bytes379176939 plus output
379228160 = **758405099 logical bytes**, about723 MiB; allow at least2 GiB
working space, separately from Python/checkout/any unrelated files. Packing
needs no Linux raw/SteamOS/account image. The phone importer separately requires
archive-size free capacity plus1 GiB reserve, and the existing guest installer
retains its own dependency/extraction/update-space checks.

These pins select version 1792192922/steamdeck_publicbeta; they do not certify
that it is the latest client. Expected input bytes 379176939; canonical archive
size **379228160 bytes**. The full archive SHA is printed after actual packing;
no real archive SHA is fabricated here. Windows host code avoids POSIX directory
fsync; actual Windows execution was not run. Unsupported link/filesystem behavior
fails rather than overwriting output.

Before starting a Steam VM, the owner explicitly selects the TAR using the app's
Import button. Expected headers and individual file hashes are compiled from the
reviewed locks, not supplied by the imported archive. Exact byte equality of
USTAR headers rejects traversal, links, duplicates, unexpected order/metadata,
PAX/GNU extensions and extra members. Body SHA-256, padding, exact tail and size
are checked. No archive extraction is performed by the app. Cap 512 MiB, 1 MiB
streaming buffers, actual free capacity >= archive plus 1 GiB reserve. No userdata
path is accepted by the import helper.

Import is serialized with Start. It writes an owner-only reserved partial under
`Documents/iDeckSteamOffline-v1`, fsyncs/validates, then atomically publishes
`packages.tar` without replacing an existing published cache. Interrupted partial
copies can restart under an exclusive inode lock. An interruption after link
publication is reconciled only when the exact reserved alias and published name
refer to the same verified two-link inode; arbitrary links are refused. A cache
handle rechecks all pins and retains a shared lock before/through VM ownership.

The archive is attached as a separate **readonly raw virtio block device**. It
is data-only TAR, not an ext4 image and not a ramdisk. No new native filesystem
builder/dependency is needed. Host checks file identity again at native entry;
the guest checks `/dev/vdb` is a block device, BLKROGET=1 and its exact capacity,
then verifies all headers/hashes before installer writes. Only exact pinned URL,
name, size and SHA requests can read bounded slices. Missing/corrupt cache does
not fall back to HTTP when the offline marker is present.

A separate reserved guest cache (`/var/cache/ideck-steam-offline-v1`) preserves
prior incomplete network downloads without relying on or overwriting them.
The real existing installer retains its durable journal, Debian package-version
and audit gates, ZIP safety/expanded-size bounds, UID1000 extraction, no-replace
client publication, link/conflict checks and interrupted-install retry. The
readonly cache is independent of `iDeckSteam-v1/rootfs-v1.raw`, so this path works
with a new seed or an existing Steam disk. It never replaces that disk or copies
account/cookies/tokens/games. On a process with no imported cache, the existing
explicit-consent HTTPS route remains available. Corrupt published caches fail
closed and are not automatically replaced or erased.

This is **predownload + offline installation**, not a fully preinstalled or
permanently offline Steam client. The existing Install/resume action performs
local dpkg/extraction; Big Picture starts the actual client afterwards. Steam's
own updater, sign-in and agreements may still need internet and owner action.
The original guest free-space/update reserve checks remain; predownload does
not repair an unrelated package/conflict/space or runtime failure.

## No new large Linux payload

All payload locks and all 23 Steam source bindings are unchanged. The app verifies
the original initramfs and appends a deterministic **12960-byte** runtime newc
suffix, following the existing bounded runtime-overlay pattern. The suffix
contains only our offline source and a narrowly derived `device-action.py` that
wraps the original installer in that source. The original source file in Git,
base PID1, kernel, modules, Stop/control logic, seed and GUI recovery generator
are unchanged. The existing bootstrap copies these overlay files into `/opt`.

Actual pinned-base CPIO inspection confirmed the base `device-action.py` equals
the current original source, the original bootstrap copies the file glob, and
only the two intended runtime files are overridden. Reference appended initramfs
size11712092; SHA-256
`269122bd2f1a3a983f6f020b6d79ba328ceba5ca446a80a70222410994e991c4`.
Suffix SHA-256
`c93832baf0071934761384f7beb22c078f3568e0e2f91f1ecef891b5dee78c73`.
These are Python reference/structure checks, not executed Swift append or QEMU.
No Linux-only payload rebuild/upload or new secret is required for this design.
The application itself still requires a new Apple build and real boot testing.

## Auto RAM: implemented conservative policy

Steam-only choices: Auto or the previous fixed 1536 MiB route. Auto rounds down
in 256 MiB increments, min 1536, **experimental capped ceiling 4096 MiB**. It uses
positive `os_proc_available_memory()` Int -> `UInt64(exactly:)`; unknown/zero,
insufficient budget and arithmetic overflow refuse startup. The API is treated
as additional process headroom, not total physical RAM. No current RSS is
subtracted again and no entitlement/JIT/OS limit is changed.

Auto retains 1 GiB for future QEMU/display/IO/JIT/TCG commitment plus 1 GiB safety
reserve. This is conservative unallocated headroom, not a measurement of already
resident bytes; prewarmed VA does not prove which pages are resident. It does not
charge a separate256 MiB TCG on top of a claimed already-resident512 MiB region.
The fixed 1536 route retains its existing 1 GiB host-reserve policy as the explicit
fallback. No fallback silently treats unknown memory as sufficient.

Preview has no allocation/JIT side effect. Start checks again after the actual
JIT path before reserving attempted; the worker recalculates after long import,
passes the same selected guest MiB to argv/report, freezes that plan, and rechecks
its required budget on the QEMU thread immediately before `enterNative`. Budget
deterioration/unknown at that last gate blocks native entry and preserves data.
No attempted/entered flag is reset and no second VM is started. JSON/Markdown
report selected mode, effective memory, future overhead/reserve, final recheck
and readonly cache configuration. This is not proof that4096 is usable on a phone
or that iOS cannot later jetsam the process; device calibration remains required.

## Disk and delivery boundaries

The existing 12 GiB Linux raw already uses iPhone storage. The UI now shows this
fixed size, measured phone free capacity and the first-import reserve. Resize,
all-storage allocation and sparse saving are **not implemented**. Existing disk
geometry, ownership, no-overwrite import and GUI-only recovery remain unchanged.
Future growth requires explicit owner choice, validated offline copies/full fsck
and atomic activation in a fresh process; no online resize/shrink is implied.

Redistribution permission for Valve bytes in a private Release/Drive/IPA remains
unconfirmed. Personal-use language in the
[Steam Subscriber Agreement](https://store.steampowered.com/subscriber_agreement/)
is not treated as blanket cloud repackaging permission. This change ships only
own code/locks; the owner prepares/transfers personal files separately under
applicable terms. No SteamOS/SteamFrame recovery image, automated EULA acceptance,
login or account snapshot is used. BusyBox corresponding-source provenance OPEN.

## Verification

558 Python tests OK (553 PASS, 5 SKIP), including actual synthetic canonical TAR
IO, corruption/link/traversal/bounds, pinned readonly device boundary and real
guest installer logic with modeled root/dpkg/setpriv/device boundaries. The
installer case exercised interruption before client publication, retry, ready
repeat, userdata preservation and an opener that forbids any network. No real
Steam binary was executed. Apple gate now requires
`LINUX_STEAM_OFFLINE_CACHE_PASS` and `LINUX_STEAM_AUTO_MEMORY_PASS`; production
Swift fixtures cover actual import corruption/locking/interruption/publication
reconciliation and RAM unknown/boundaries/step/overhead/overflow/deterioration.
Those new Swift fixtures are **NOT RUN** in this Linux environment.

Generators, source overlay, existing real sealed Steam staging/repeat/resource
gate, recovery source/history preservation, AST/shell/Git attributes PASS.
Evidence: `experiments/linux-guest/evidence/steam-offline-auto-20261019/`.
New Apple/integrated typecheck/native build/QEMU/device/owner-PC acceptance
**NOT RUN**. No CI was started. The next manual run must use the full new pushed
source SHA and freshly verify quota (the reported 125 minutes is not a new quota
attestation), disabled paid billing, private source and native-build approval.
