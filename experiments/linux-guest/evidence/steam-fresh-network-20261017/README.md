# Fresh private cloud: installed client, updater network blocker

Started from remote-verified Steam branch
`codex/steam-arm64-experiment-20261017` at
`bfcb3a8bb2a719240daf04ed9023d8a425444e7a`. One executor, cloud only.
No repo/ancestor `AGENTS.md` or repo `.agents/skills` was present. All four prior
evidence manifests verified. The owner-reported network version is recorded in
`summary.json`; its control-plane identifier was not independently introspected.

**Main Steam UI and Big Picture are NOT REACHED.** This independent cloud
installation fails in the updater before any CEF browser. It does not reproduce
or explain the historical first webhelper-init timeout.

## Actual downloads and production inputs

- The first exact locked Fastly ZIP GET returned **origin HTTP 200**, 386432 bytes,
  SHA-256 `90b8202eb03a0a95bf444d0daa6849c7e63a0e32fa9367ddb369d6218d2978b1`.
  All **17/17** locked ZIPs subsequently downloaded and rehashed, 360938891 bytes.
  See `preparation/first-locked-steam-get.json` and `client-cache.json`.
- Existing `gh` access downloaded private Release asset **650023557**:
  292065280 bytes, SHA-256
  `112bdba6e12ae182fb347e52e7368e26f748bb3dc2bcd77dbd3122fb14dcdedd`.
  Metadata, actual binary verification and restore receipts are in `preparation`.
  No token was created or disclosed; no signed URL was logged.
- The pinned GUI tool restored and verified all five production files. Raw seed:
  1342177280 bytes, SHA-256
  `9c4d978f0ea33b608735e203c0e1695ca89188c02b097e610f971cffe1c05791`.
  No old private seed/cache was transferred. No experimental contract was selected.
- Signed Debian metadata/solver authenticated the 94 GUI host pins, qemu-utils
  `1:10.0.13+ds-0+deb13u1` and the separate squashfs tooling closure. All extraction
  is private under `/workspace/steam-fresh-20261017/host`; no system install.
  qemu-utils package SHA-256 is `6d31339b…4dca30`; actual qemu-img SHA-256 is
  `77a92b0ca43516403064a4d0939f91c38b9ab2447b32e8f66709dcf29432d626`.
  Its receipt also binds the matching extracted loader and host closure.
- The unchanged runner's entry gate passed with **29534867456** free bytes,
  requiring **17179869184** for a full 12GiB offline copy plus 4GiB reserve.
  All subsequent copy gates rechecked actual free space without a sparse discount.
  The separately reported hypothetical full overlay + full copy + reserve was
  529903616 bytes above that initial free space; it was not claimed as guaranteed
  capacity. Originals, failed outputs and caches were retained throughout.

## Installation and first attempt

The guest installed **45/45** additional locked packages, preserving all **341**
GUI package versions. `dpkg --audit` returned **0 with exactly empty stdout and
stderr**, both after install and after the second boot. Real lsof 4.99.4 is
installed. This establishes its prerequisite, not an IPC root cause or fix.

The guest installer now accepts explicit `--retain-client-cache`. The same
size/hash/owner checks run, but the 17 verified installer ZIPs are preserved and
the receipt records their retained count. Existing default behavior remains
available. Actual installation and later boot verified the retained files.
No runtime cache or sentinel was deleted. **149 offline Steam tests PASS**,
including real-file retention/corruption checks.

The separate current Steam bootstrap is **11665853 bytes**, SHA-256
`af9aa6fb9a25a805ad3b8465aa2cada6ceaaffb103ec663e831d998c43276f4e`.
It differs from the old 6a0081d7 archive because it includes this installer option.
Its exact bytes booted in both cloud VMs. Production GUI inputs/payload are unchanged.
The original Stop, namespace helper and launcher are unchanged. UID1000 namespace
preflights passed; HOME/DISPLAY/runtime/Xauthority and session D-Bus behavior were
preserved. The real native launch included `-cef-force-sandbox`. No CEF child
started here, so CEF runtime seccomp/namespaces are **NOT VERIFIED by this run**.

First-attempt evidence is under `first-attempt` and `run1`:

1. Native Steam requested
   `https://client-update.steamstatic.com/steam_client_steamdeck_publicbeta_linuxarm64`.
   Its updater reported `Download failed: http error 0`, then
   `Steam needs to be online to update`, and exited. Its installed updater
   manifest was absent on this fresh disk. The older local updater success does
   not carry over to this independent installation.
2. One normal host GET to that exact newly observed endpoint produced
   **proxy CONNECT 403**, with **no origin HTTP status**. This is a tunnel/network
   refusal, not an origin authentication response. The successful private GitHub
   asset download is separately verified. See `native-updater-host-get.json`.
3. Guest `getaddrinfo` for both `client-update.steamstatic.com` and the permitted
   `client-update.fastly.steamstatic.com` returned **EAI_AGAIN, errno -3**.
   The configured NAT route and nameserver **10.0.2.3** were present. These guest
   DNS failures and the host CONNECT refusal are distinct observations; neither
   proves the other's cause. No successful guest HTTPS update is claimed.
4. Eleven bounded untraced samples observed at most two client processes, **zero
   SHM objects**, and all **769449984** SHM bytes free. No browser was created;
   all client processes exited by the 11.316-second observation endpoint. No
   freeze signal or SHM cleanup occurred. The earlier within-browser SHM growth
   remains unresolved. There was no valid browser target for `trace_steam_ipc.py`
   or `snapshot_steam_ipc_stack.py`; both are **NOT RUN**. An authenticated strace
   package was cached for later diagnosis, not installed or invoked.

No updater hostname override, alternate proxy/resolver, timeout/CPU/RAM adjustment,
sandbox bypass, sentinel/cache deletion or policy change was attempted. The host
profile remains QEMU10.0.13/TCG, max/4vCPU/1536MiB, existing software rendering.

## Stop, offline checks and persistence

- `run1`: installation + one failed updater launch, then actual clean unmount,
  QEMU exit0 and host fsync. No forced host termination or dirty marker remains.
- `run2`: a new owned copy of run1, preserving the original. Before boot, a full
  12GiB flattened offline `e2fsck -f -n` passed all five phases, exact summary and
  version, with no extra output. Raw SHA-256:
  `d04ccf8a75946c78f3cb8e40ade5f285dbcbfb7fd34279ab34d9935a74e28c2d`.
- Second boot verified a UID1000 document, machine-id, four exact client ELFs,
  all 17 installer ZIPs and empty successful dpkg audit. **Steam itself was not
  relaunched**, and the denied updater endpoint was not retried. The VM then
  achieved another clean unmount/QEMU exit0/host fsync.
- After run2, no QEMU writer remained and its owner lock was held exclusively.
  A second complete 12GiB offline check passed the same strict full-output policy.
  Raw SHA-256:
  `2bde57962657f7d45010b5f49230eabcbc71be84abdfd05ee2bc5a25e9fed7a6`.
  The source qcow2 SHA-256 stayed
  `462a5804f296ec1333196fce0ad1a893204e841611c76f5f31e608a7b99a11e3`.
  Both full streams and receipts are retained. Only the runner's disposable
  successful fsck raw copies were removed by its existing policy.

Screenshots are real **Debian Desktop captures after the failed updater**, not
Steam UI proof. Clean application shutdown, UI input/Big Picture, Steam relaunch,
Apple runtime, Steam on iPhone and GPU acceleration remain **NOT RUN**.

Preparation failures are preserved honestly: unsquashfs 4.6.1 returns1 for its
version display; the successful extracted tool was subsequently verified and
used. A first bootstrap attempt refused generated Python bytecode in its source
directory; those files were moved to private retained test storage before the
successful build. `run1/003-first-failure.log` records a missing optional `ip`
utility in an observer. Command004 used `/proc/net/route` and completed capture.
The initial blank bootstrap stdout is retained with an `.empty` suffix.
The raw guest export contained two `result.json` basenames; decoded artifacts
are distinctly named `first-attempt-result.json` and `install-result.json`.

## Exact continuation boundary

Private inputs/disks exist only in this selected environment under
`/workspace/steam-fresh-20261017`. No disk, Valve binary or Debian package is in
this evidence directory or published elsewhere. Do not assume these private paths
will be transferred to another environment. Rehash actual inputs and recompute
space before any new run. Both old command directories intentionally contain STOP.
Use a new command directory/output and explicit `--continue-from .../run2` only
after its clean evidence, source identities, owner and offline-copy gates pass.

Further updater/UI work requires the owner/environment administrator's approved
network route: the newly observed exact updater HTTPS host is currently refused,
and the prescribed guest NAT/DNS must also resolve and reach the approved service.
Adding one hostname alone has not been proven sufficient. Do not work around the
refusal or invent successful DNS/TLS. Once prerequisites work, retain first-failure
IPC/stack bounds, actual UI screenshots/input and the owner-only account/terms
boundary. No passwords, login, agreement acceptance or games occurred here.
