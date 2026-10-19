# Launch failure: No, I'm not a Human — 19 October 2026

Source correction prepared; successful game launch **NOT VERIFIED**. This report
covers the owner's two supplied logs and a minimal change on the private BCD
branch. It does not describe the old iDeck Linux/Steam payload.

## Evidence access and limits

Both Library entries were readable through authorized, bounded `find`/`read`
operations. Current: 3,627,603 bytes / 35,478 lines; previous: 3,076,857 bytes /
31,314 lines (Library metadata). Full byte transfer failed with
`Tunnel connection failed: 403 Forbidden`. Neither complete local files nor
independent log digests were obtained. No alternative proxy or access bypass
was used. Line references below are Library's original line numbers.

Both logs identify build v0.1.573 (573). They launch **different applications**;
the previous log is supporting evidence of a shared allocator condition, not a
second reproduction of this particular game. Raw logs, account data, arbitrary
configuration values, personal paths and transfer capabilities are excluded
from this repository. The [evidence JSON](HOST-VA-LIMIT-EVIDENCE-20261019.json)
contains allowlisted derived facts only.

## First significant blocked transition

| Current log lines | Observed transition | Meaning / limit |
| --- | --- | --- |
| 17–18 | Map ends at `0x7180000000` (454 GiB); installed profile reports extended-VA and increased-memory absent | Actual installed capabilities differ from the source entitlements; changing C cannot grant them |
| 227–230 | Hint walk `0x8000000000` (512 GiB), kernel maximum `0x7180000000`; code keeps walk | Demonstrated overestimate propagates to host/user address limits |
| JIT startup | Pool ready after shrinking requested 896 MiB to 560 MiB | JIT attachment succeeded; this is not evidence of full game compatibility |
| 8916–8917 | Target `NoImNotAHuman.exe` child starts | Launch passes the app/Dock handoff; no ownership bypass is indicated |
| 9233–9239 | UnityPlayer loads | Engine identified from the log, not inferred from the game name |
| 9779 onward | D3D11/DXGI modules load | Does not prove first frame or a fatal shader fault |
| 10524–10542 | First roughly 512 MiB reservation fails high steering, then succeeds via fallback | Early steering failure alone is not the terminal condition |
| 10552–10565 | Next reservation exhausts five tags, whole-map fallback finds largest gap 369 MiB; returns `c0000017` | First significant failed engine memory transition; contiguous VA is insufficient for this request |
| 10573 onward; 10729–10733 | NULL write / `c0000005`, then recursive exception handling | UnityPlayer guest RIP resolves to module offset `0x1236316`; exception storm follows the allocation refusal |

The rejected high windows include `[0x7c00000000,0x8000000000)` and
`[0x7400000000,0x7800000001)`, both above this task's actual ceiling. The native
fallback already scans to the real ceiling and still reports no suitable hole.
Therefore correcting the bound is necessary for accurate placement/reporting,
but cannot itself be claimed to create a 512 MiB contiguous hole. The observed
NULL result/write ordering is consistent with failure propagation inside Unity;
it does not establish every engine allocation's origin.

The previous log has the same overestimate (line 234), reserve failure
`c0000017` (11084), largest gap 389 MiB, and a later Unity exception. It is a
different Unity module/build and application. Its eventual exit code 0 is not
evidence of successful gameplay.

The FEX-reconstructed x64 guest RIP and Unity instruction stream identify the
guest execution path; the native fault PC is ARM64 translated code. The existing
`WineProcessBridge.m` launches Wine through its pthread/`__wine_main` path, and
the observed failing guest thread is `00ac`. Reaching this Unity allocation
does not establish a separate worker-start or prefix-initialization failure.
The shared prefix and per-game dependency mechanisms were inspected as source;
neither log evidence nor this correction establishes prefix corruption or a
missing redistributable. D3D module loading alone also cannot clear later GPU
initialization. These stages must be checked again after the first blocker.

Routine Wine `fixme` output, the early invalid-parameter allocation probe, and
early FEX `mprotect` messages do not identify this blocked transition: startup
continues past them. The crash-handler process gate remains intact. No change
ignores exceptions, suppresses allocation failure, fabricates JIT readiness,
installs guessed redistributables, changes the prefix or bypasses Steam/DRM.

## Minimal source correction

`get_host_addr_space_limit()` previously accepted `TASK_VM_INFO.max_address`
only when larger than the power-of-two hint-walk result. A successful mapping
at a hint of 256 GiB does not establish a 512 GiB ceiling on a non-power-of-two
map. Accept a complete, sane kernel range in either direction instead. Validate
the returned revision count, nonempty range, minimum bound and page alignment;
initialize the reply and preserve the walk fallback for unavailable/invalid
information. Existing user-limit clamping consumes the corrected value.

Apple XNU assigns these revision-2 fields from the task map's minimum/maximum
offsets, and its ABI declares them as revision-2 additions. This supports using
the map ceiling rather than the rounded walk estimate. Sources:
[task.c](https://raw.githubusercontent.com/apple-oss-distributions/xnu/main/osfmk/kern/task.c),
[task_info.h](https://raw.githubusercontent.com/apple-oss-distributions/xnu/main/osfmk/mach/task_info.h).
These links describe XNU's implementation, not an independent interrogation of
the owner's device.

The existing `Madeira.entitlements` already requests both capabilities. The
installed-profile absence is an unresolved signing/device constraint, not a
missing source toggle. No entitlement, provisioning identity, sandbox rule,
submodule, app binary, user disk, prefix, save or workflow is changed.

## Verification actually performed

- PASS: Python AST parsing of the new host regression, without importing it.
- PASS: extraction of the actual production limit/clamp bodies into the fixture
  and `cc -std=gnu11 -Wall -Wextra -Werror -fsyntax-only` on that generated C.
  This validates fixture syntax against local mock types, not Apple SDK ABI or
  compilation of the complete native translation unit.
- PASS: static call-site/guard review and `git diff --check`.
- Prepared, **NOT RUN**: `tests/host/check-host-va-limit.py`. It compiles the
  production functions with only OS boundaries mocked, and covers the owner's
  lower ceiling, an underestimated ceiling, equal limits, failed/short replies,
  zero/small/inverted/unaligned ranges, and the user-limit clamp (10 cases).
  It uses ASan/UBSan when executed. Mock results are not game/device evidence.
- NOT RUN: host test binaries, full regressions, upstream scripts, native
  Apple/Swift build, IPA packaging/signing/install, device launch and gameplay.
  No CI was enabled/dispatched; no new credentials or paid resources were used.

The host runner already discovers `tests/host/check-*.py`; no workflow change is
needed to discover the new regression. Static self-review checked both upward
and downward selection, fallback paths and preservation of existing security
and data handling. The native submodule gitlinks remain at the import pins.

## Concrete next execution stages (require separate authorization)

The owner currently allows static analysis/edits and explicitly forbids running
unverified upstream build/install/game scripts. None of the following commands
has been executed for this change.

1. Local host regression only, after review of the small new fixture:

   ```sh
   cd /workspace/iDeck-BCD
   python3 tests/host/check-host-va-limit.py
   ```

   This invokes the local compiler, links and runs a temporary sanitizer-enabled
   C fixture; no Wine, game, device, network service or project build runs.
   After reviewing the existing adjacent scripts, run them separately:

   ```sh
   python3 tests/host/check-small-va-band.py
   python3 tests/host/check-va-pressure-gap.py
   ```

   These also compile/run host fixtures. Review the complete runner and any
   additional selected check before authorizing full regressions; this is not
   blanket permission to execute every inherited check.

2. On an authorized macOS checkout with the exact pinned dependencies and
   prepared Wine/generated headers, review the full native script and its
   transitive generators before authorizing:

   ```sh
   bash build/ntdll-unix/build.sh
   ```

   This compiles many native units, invokes generators and overwrites
   `app/Madeira/libntdll_unix.a`. It is not a one-file syntax check. Relink and
   package the modified app with a separately reviewed local build command;
   the archived OTA/upload/signing workflow must remain disabled. No exact
   signing/export invocation is asserted without the selected local scheme,
   SDK and authorized existing provisioning setup. No CI dispatch is proposed.

3. Before app execution, satisfy the private-copy quarantine in `AGENTS.md` and
   `docs/migration/FIRST-SCOPE.md`: inherited automatic log/feedback/update/
   recommendation destinations still exist and have not been disabled by this
   allocator fix. Use our branding and inspect the existing signed app/profile
   capabilities privately; do not create keys or pretend entitlement requests
   equal granted capabilities. Obtain a fresh actual map measurement.

4. With explicit device permission, preserve the existing prefix/saves, launch
   the same owned game in a fresh process and capture only bounded allowlisted
   diagnostics. Do not wipe/recreate the prefix or download dependencies as a
   trial-and-error remedy. Stop on the first terminal reservation failure.
   Check corrected kernel/host/user ceilings, actual largest hole, the engine
   reserve outcome and any subsequent failure. Acceptance requires an actual
   rendered game frame and responsive input; child creation, JIT readiness,
   quieter logs or a normal exit alone are insufficient.

If the contiguous hole remains below the required reservation, continue from
that measured failure and allocator occupancy; this patch is not an accepted
game-launch fix. Larger capabilities, Unity tuning or a different allocation
policy require evidence and separate scope rather than guessed flags.
