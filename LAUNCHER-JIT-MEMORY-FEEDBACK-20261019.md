> CURRENT SOURCE CORRECTION — stable Steam cache device identity, 19 October 2026.
> Based on `460d5f260089e0c9f0a62d0049a6ee04b9e78468`. Coordinator-inspected
> device screenshot10:51 UTC shows `offline_cache_not_readonly`; this is separate
> from RAM/JIT feedback. The old guest guessed `/dev/vdb`, although ARM virtio
> disk order is unstable and root is already found by UUID. New argv supplies a
> cache serial; the guest selects its unique identity, checks major/minor, then
> still requires actual RO=1, exact size and all pinned bytes. Device mapping
> on the owner's phone remains unmeasured; no real host QEMU result is claimed.
> **599 Python tests OK /5 SKIP**, full overlay and real repeated staging PASS.
> New Apple/Swift/phone acceptance **NOT RUN**. Base payload/cache, native worker,
> user disks and safety guards unchanged; no Release or payload rebuild needed.
> CI#41 on460d5f26 was coordinator-reported running and lacks this correction.
> No parallel/new CI started here; recheck fresh remaining quota and paid OFF
> before any future manual run. Current cap55/worker50 remains unchanged.
> BusyBox provenance **OPEN**. [Cause, safety and evidence](STEAM-CACHE-DEVICE-IDENTITY-20261019.md).

# Launcher feedback and JIT — source candidate

Baseline: `c810b682601634920e8ff601b6832c08524896e9`, Steam branch only.
The delivered CI#40 IPA uses `cf773c48e4c11d9c341667cb55e5b40522655df8` and
predates this correction. No new Apple build or device result is claimed.

## Confirmed cause and scope

The coordinator inspected the owner's screenshot pixels. It shows an actual
Start refusal: manifest, JIT and network passed, but memory failed with
`Недостаточно бюджета процесса с резервом; Auto не использует всю физическую RAM`.
This proves the click reached the memory preflight. It does not prove a hit
testing failure or JIT failure. The old UI offered a generic repeat instruction
without a directly applicable memory action. No numeric memory measurement was
visible, so the owner's actual budget and whether1536 will fit remain unknown.

This executor requested the identified screenshot through the supported Library
materialization path; preparation succeeded but the current transfer helper
returned `download failed`. No image bytes were inspected locally, no alternate
URL was guessed and no access restriction was bypassed. Screenshot observations
above are explicitly coordinator supplied. No screenshot or personal identifier
is committed here.

## Change

The launcher publishes a visible checking message before scheduling the existing
JIT/readiness checks on the main queue. The primary action stays available;
repeated clicks report that the check is in progress without creating another
attempt. An existing owner still resumes immediately. Failure before ownership
shows the existing exact session error. First readiness loads on appearance,
refreshes when memory/network selection changes, and is read afresh on Start.

Memory refusal now shows the measured **additional process budget** and the
minimum for the chosen mode. Auto offers an explicit **Проверить запуск с
1536 MiB** action using the existing fixed mode, plus fresh measurement. The
owner is told that1536 may be tight for Steam/games and can still be refused.
If it cannot fit, the actions are to close other apps/reopen iDeck and measure
again; no VM starts from a cached successful observation.

The memory policy is unchanged: Auto minimum3584 MiB = guest1536 + future host
overhead1024 + reserve1024; fixed1536 minimum2560 MiB retains its existing1024
reserve. No RSS is subtracted from `os_proc_available_memory()` again and
physical RAM is not treated as available process budget. The same plan is
recomputed after bounded cache/disk IO and rechecked after ownership/report
fsync immediately before native entry. The worker, disk and native code are
byte-identical to the baseline. Cache IO uses bounded1 MiB chunks; this review
found no whole-cache RAM loading or proven double-count bug. Device heap or
jetsam behavior was not profiled, and no safety margin was reduced.

JIT off now ends the pending spinner and presents a clear inline prompt with
**Открыть настройку JIT**. It opens the existing Husk `JITSetupFlow`, refreshes
pairing and prefers the built-in helper only for Automatic when available,
preserving explicit method selection. The existing TrollStore marker guard
still prevents stock Magnifier being treated as a JIT provider. Real JIT is
rechecked after attach, foreground return and sheet dismissal. Opening another
app is never accepted as proof; a successful check asks the owner to press Start
again. A diagnostic-journal error also clears any stale positive JIT observation and
shows its exact reason. Errors remain visible with the setup action; no automatic VM start on
return and no indefinite pending-launch spinner while waiting for JIT.

Home/Resume, preparation cancellation, one-QEMU ownership, disk locking,
safe Stop, data/cache pins and native entry guards are retained. Backgrounding
also clears an unconsumed launcher intent so it cannot later start unexpectedly.

## Checks and limits

Full real-checkout Python regression: **595 tests OK,5 SKIP**. New regressions
cover visible click feedback, repeated press, JIT-off/setup/recheck/manual
continuation, active owner, the exact screenshot memory refusal, explicit fixed
selection, stale readiness and the unchanged post-IO/native memory gates.
Actual pure Swift fixtures cover JIT state transitions and3000 MiB synthetic
budget: Auto refused, existing fixed1536 accepted, later2559 refused. Those
fixtures are wired into mandatory Apple markers but were **not executed here**.

Full pinned81-file Husk restoration, five patches, exact overlay copies,
generators, unchanged23 original Steam bindings, real Linux/cache staging and
repeat/resource checks, Python AST, shell syntax, Git attributes and diff checks
PASS. Evidence: `experiments/linux-guest/evidence/launcher-jit-feedback-20261019/`.
The five skipped checks need Swift, a pinned QEMU native source/compiler setup
or user-mode QEMU. New Swift/iOS typecheck, integrated Apple build, UIKit hit
testing/rendering and actual phone JIT/memory/Steam behavior remain **NOT RUN**.
BusyBox corresponding-source completeness remains **OPEN**; controls remain
keyboard/mouse mapping, not Linux HID. No user disk or account was accessed.

## Next manual CI — coordinator only

Dedicated `ideck-linux-probe-ipa`: `mac_mini_m2`, Xcode27.0, provider cap**55**,
worker total budget**3000 seconds (50 minutes)**. The supplied62-minute free
snapshot leaves7 minutes beyond the provider cap; fresh quota with reserve and
paid OFF must be checked again before dispatch. Other workflows and secret
environment are unchanged. Use the exact reviewed remote HEAD:

```text
expected_commit=<full reviewed post-fix remote HEAD>
free_quota_verified=true
private_source_verified=true
native_build_approved=true
```

No CI was started here. Previous cap70/65 and cap95 instructions are historical.
