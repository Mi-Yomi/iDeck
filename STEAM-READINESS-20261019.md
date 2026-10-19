# Steam readiness snapshot, 19 October 2026

Newer source candidate: [owner offline cache and Auto RAM](STEAM-OFFLINE-CACHE-AUTO-RAM-20261019.md).
It adds explicit cache import and Steam-only experimental Auto/fixed RAM with
after-JIT/final native-entry checks. No new Apple/QEMU/device run or delivered IPA
is claimed; the successful delivered result below belongs to209315cd only.

Delivered result: **CI #35 [Build finished](https://codemagic.io/app/6ad03ce9a8a969b53f3a4aa9/build/6ad5824c7550aed8108ffe54)** for built source
**`209315cd8b330c0ba1b5a7a28f2cf2884a86dafa`**. The coordinating executor reports
LINUX_STEAM_READINESS_PASS, LINUX_LAUNCHER_NAVIGATION_PASS,
LINUX_GUI_RECOVERY_PASS, full upstream/integrated Swift typechecks and native
build/package PASS. This confirms the signed-memory conversion fix passed the
integrated Apple gate that failed in the previous run.

IPA: **710808045 bytes**, SHA-256
`ae6692c885c1200fcf1a86645c8c53dba6d61322d96af73c4fdd781ffe352231`.
The coordinating executor independently checked the downloaded IPA: CRC,
embedded commit/Bundle ID, seven arm64 iPhoneOS ad-hoc Mach-O files and all 19
resource pins PASS. Private Drive delivery to the owner is confirmed. This
repository contains no personal delivery link. Results are supplied by the
coordinating executor; this docs-only update did not start CI or download IPA.
The documentation commit is not the IPA's built source SHA.

Device/visual/Steam checks remain **NOT RUN**. The phone's black Steam screen
has not been diagnosed; a current device report is required. Build/typecheck
success does not prove guest LSE, rendered GUI/Steam or game compatibility.
The MaPC SystemCheck approach was adapted using our own code; no MaPC code or
dependency was copied. **MetalFX is not implemented.** BusyBox corresponding-source
provenance remains **OPEN**.

The following records the original implementation and earlier validation stages.

Historical failure: the parent's actual readiness CI for `14d2ea33d75a7f14787e039a394f88ad6fa02e07`
[failed integrated Swift typecheck](https://codemagic.io/app/6ad03ce9a8a969b53f3a4aa9/build/6ad5804a7550aed8108ffdfb)
at `LinuxTerminalSession.swift:29:44`: `Int?` could not convert to `UInt64?`.
The parent reported Mac runtime markers (including LINUX_STEAM_READINESS_PASS)
and upstream typecheck PASS; native downloads had not started. The SDK returns
signed `Int`. The follow-up uses an explicit nonpositive -> unknown guard and
failable `UInt64(exactly:)`, with typed boundary fixtures. One new affected call
was found; the pre-existing worker comparison is unchanged. Follow-up local
checks: **550 tests OK (545 PASS, 5 SKIP)**, generator/overlay/staging/resource
verification PASS. New Swift/Apple execution **NOT RUN**. See current HANDOFF and
`experiments/linux-guest/evidence/steam-memory-types-20261019/`. The following
original validation describes the pre-fix source, not a successful integrated
Apple build of readiness.

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

For a future source change, CI uses `ideck-linux-probe-ipa`, the same Steam branch,
and `expected_commit=<full reviewed source SHA>`. The coordinating executor must
freshly verify at least 120 free macOS minutes and disabled paid billing before
setting `free_quota_verified=true`, `private_source_verified=true`,
`native_build_approved=true`. Existing `ideck-debian-payload` /
`IDECK_DEBIAN_PAYLOAD_TOKEN` is sufficient; no secret or Release change.
BusyBox corresponding-source provenance remains **OPEN**.
