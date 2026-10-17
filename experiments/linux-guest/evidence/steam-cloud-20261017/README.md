# Private cloud continuation, 2026-10-17

Work started from the verified remote Steam branch at
`b493a4909f81a5df0c226d9562a049e59e191039`. One agent, private cloud only.
No laptop/Windows/WSL access, subagents, credentials, CI or Release mutations.

The current execution blocker is **missing official Steam client bytes**.
The unmodified pinned installer failed on its first official HTTPS component
with `URLError: <urlopen error Tunnel connection failed: 403 Forbidden>`.
No ZIP was downloaded, and no alternate endpoint/proxy/security workaround was
attempted. This is a transfer-layer observation, not a Steam/CEF root cause.

The shell's existing GitHub route returned `Forbidden` for both metadata and
octet-stream requests to GUI asset 650023557. No HTTP status/body was obtained
through gh. The existing authorized GitHub connector separately returned
metadata with the expected 292065280-byte size and
`sha256:112bdba6e12ae182fb347e52e7368e26f748bb3dc2bcd77dbd3122fb14dcdedd`.
That tool explicitly rejects binary downloads. Thus asset existence/digest are
confirmed, but its bytes were not materialized; GitHub credential failure is
not established. Library search resolved no suitable GUI seed or client.

Safe independent preparation completed:

- All 94 prior IPC evidence entries passed size/SHA-256 verification.
- The existing GUI downloader authenticated the signed Debian release/indexes
  and downloaded 432 unique files (341 guest package pins, 94 host package pins,
  one provisioning kernel pin; some identical all-architecture files overlap).
- The existing GUI lab builder prepared a **new disposable scratch image**.
  This is not the accepted seed and is not the owner's unavailable Steam disk.
- Its standard offline provisioning completed in 623.065 seconds, with the
  exact 341-package manifest, clean guest unmount and QEMU exit 0. An independent
  subsequent host fsync and read-only `e2fsck -f -n` passed with no task QEMU
  writer. The strict Steam fsck parser accepted all five passes, one version and
  one target summary, with no warnings or additional output. Full stdout/stderr
  and before/after hashes are retained. The 1342177280-byte scratch hash stayed
  `425893ed8c04270e293f7b5ed8b4db5cf94d3c98db17f66f0666de515f821f22`.
  This is provisioning evidence, **not GUI seed acceptance**. No GUI or Steam
  screenshot was produced in this cloud turn.
- The provisioning VM used its unmodified host-only profile: Cortex-A72, four
  vCPUs, 1024 MiB guest RAM and no networking. Sampled QEMU peak RSS was
  1407672320 bytes. The host cgroup limits are 16 GiB and four CPUs. These are
  separate from the unchanged Steam host profile (max, four vCPUs, 1536 MiB).
- The production GUI kernel/initramfs were reproduced with exact accepted
  hashes. Current Steam bootstrap was reproduced exactly: 11665437 bytes,
  SHA-256 `6a0081d76fedbb38b72e705334513313093b46e701907ed8b6d516640978df7f`.
  Its original Stop function and namespace-helper bytes are preserved.
- 45 Steam dependency packages / 18238048 bytes were checked against the same
  authenticated index and downloaded. See `prepare_support.py` and its receipt.
  Cache availability is separate from guest installation.
- 129 existing offline Steam tests passed on this cloud workspace filesystem.
  These are guard/unit tests, not ARM64 runtime or UI acceptance.

Private working inputs are retained under `/workspace/steam-cloud-20261017`.
No disk, Debian package, Valve binary or account material is committed here.
The hashes in `manifest.json` cover only the explicitly retained evidence.
No task QEMU remains. The provisioned raw image was fsynced after its sole VM
writer exited and was unchanged by the offline check. No host image mount was
created. The exact current Steam bootstrap has been built, **not booted** here;
its 45-package guest installation and byte-empty successful Steam dpkg audit
remain NOT RUN. No Steam experiment disk was created from an unaccepted seed.

Steam main UI, Big Picture, their input/restart/screenshots, runtime RAM/SHM,
ARM64 stack capture and IPC tracing are **NOT RUN** here. The historical first
webhelper timeout remains unexplained; no timeout/CPU/security change was made.
Steam on iPhone, Apple runtime and GPU acceleration remain **NOT RUN**.

Continuation needs a supported permitted transfer of the locked official Steam
components and a verified seed contract. Do not relax hashes or use this scratch
image as the accepted `ipa/gui.lock.json` seed. Preserve cached inputs, separate
disk ownership, original Stop and all security settings.
