# Steam readiness snapshot, 19 October 2026

Source baseline: `f7a89d2c8e1f324843fd6d215a1ebd60171451aa`.
This is a new source candidate; the parent's CI for that baseline does not
validate these changes. No CI was started, cancelled or modified here.

Home and the Steam launch screen show manifest, cached JIT observation, explicit
network consent and available-process-memory status. Missing/malformed manifests
fail closed through the existing bounded/no-follow `LinuxSteamProfile.load`.
Memory below 1536 MiB + 1 GiB reserve blocks launch; an unavailable/zero measurement
remains unknown and blocks launch. This checks the manifest contract, not payload
hashes or Steam compatibility. LSE, guest GUI and Steam remain unverified.

The snapshot does not open userdata, allocate a disk, acquire/release ownership,
start networking or enable/check executable JIT. In particular it never reads
`JITBootstrap.ready`: that existing getter can perform native prewarm. The cached
JIT result is informational and cannot replace or prevent the actual Start-time
JIT check. A JIT failure can be corrected and checked again.

Start repeats the snapshot on every click before its existing JIT/native path.
Manifest/memory/consent refusal at this point does not consume `attempted`.
The existing serialized main-thread duplicate-click guard and worker's fresh
manifest, hash, memory, disk-owner and native-entry gates remain. Later failure
after the attempt has been reserved never clears `attempted` or entered state.
Conditions can change after preview or during preparation; the preview grants
no authority. The 13 GiB free-space check remains in new-disk provisioning only;
an existing Steam disk is not rejected by a new blanket import-space gate.

Own minimal implementation, inspired by the status/check approach reviewed in
`MaPC/System/SystemCheck.swift` at commit
`37bb046423dbb85c5cb98fee742868dccb96002d`.
No MaPC code or dependency is copied. Its macOS/Rosetta checks are not applicable
to this iPhone ARM64 guest and have not been presented as device evidence.

Validation: 549 Python tests OK (544 PASS, 5 SKIP), including source wiring for
read-only preview, Start ordering, duplicate-attempt guard and unchanged disk
provisioning. Actual production Swift fixtures now cover missing/malformed
manifest, memory threshold ±1/unknown, network/JIT status, repeated reads of an
existing synthetic dirty disk without mutation, and changed conditions between
checks. `LINUX_STEAM_READINESS_PASS` is mandatory in the Apple gate. These Swift
fixtures and the app's Apple build/visual/device behavior are **NOT RUN** here.
Python source checks are not a substitute for their execution.

Generator exactness, 81-file pinned Husk source restoration + five patches,
overlay copies, real sealed Steam stage/repeat and package-resource verification
without `hashlib.file_digest`, Python AST, recovery shell syntax and actual Git
attributes PASS. All 23 Steam source pins, existing payload locks, disk/recovery
implementation and launcher ownership policy remain unchanged. Evidence:
`experiments/linux-guest/evidence/steam-readiness-20261019/`.

Next CI uses `ideck-linux-probe-ipa`, the same Steam branch, and
`expected_commit=<full pushed readiness commit>`. The coordinating executor must
freshly verify at least 120 free macOS minutes and disabled paid billing before
setting `free_quota_verified=true`, `private_source_verified=true`,
`native_build_approved=true`. Existing `ideck-debian-payload` /
`IDECK_DEBIAN_PAYLOAD_TOKEN` is sufficient; no secret or Release change.
BusyBox corresponding-source provenance remains **OPEN**.
