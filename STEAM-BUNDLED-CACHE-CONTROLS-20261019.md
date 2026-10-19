Latest Apple result (coordinator supplied): CI#38 on a33d19ba failed in
`mac-tests` at `SteamBundledChecks.swift:30`, exit-5. iOS typecheck/native
syntax/Mac compile PASS; integrated Husk/native build/new IPA were not reached.
The new fixture expected raw `blocked: digest`, whereas the existing protected
renderer intentionally outputs `blocked&#58; digest`. Only the fixture changed:
it now requires exact escaped Markdown cells, rejects raw forms and verifies
unknown/injected statuses are redacted. The production renderer/importer/input
and all cache/payload pins are unchanged. Corrected Apple runtime NOT RUN here;
no new CI dispatched. Full587 Python tests OK/5 SKIP and real resource gates PASS.
Latest coordinator quota104 free, paid OFF;95/90 caps fit with9-minute provider
reserve, subject to fresh coordinator checks. Evidence:
`experiments/linux-guest/evidence/steam-bundled-fixture-fix-20261019/`.

# Bundled Steam package cache and screen controls

Source baseline: `52aa5b55d3c3466adf59ac2edac82a4b670f767f`, Steam branch only.
This is a new source candidate, **not a new built/delivered IPA**. The preceding
delivered IPA is still built at `7782926dffb3ab513715518c18f8e667ca3c0c40`.
Apple compilation, actual touch UI and device behavior for this change **NOT RUN**.

## Real cache and delivery

All17 Valve ZIPs and45 Debian packages were obtained from the exact existing
locks, using normal CA/hostname verification through the already configured
managed proxy. No source, redirect, proxy/DNS/security setting or token changed.
The previously refused updater host was not requested. No Steam executable,
package installer, login, account data, games or agreement acceptance was used.

Canonical `owner-steam-cache.tar`: **379228160 bytes**, SHA-256
`a75ea9bb8a19946cf81b2fb3d6cc4db97db6a1fe0938e4f23857c2c6e826adef`.
Input bytes379176939; all62 original name/size/SHA pins match. Independent
`tarfile` streaming checks verified every member's name/type/size/hash and fixed
metadata. Official ZIP safety inventory:960528505 expanded bytes,12 internal
links validated, no extraction. Real stage/repeat/standalone resource gate PASS.
This is actual official cache evidence, distinct from synthetic test fixtures.

The cache is retained in the owner's **private ChatGPT Library** as
`owner-steam-cache.tar`, tool-confirmed379228160 bytes. No sharing action occurred.
The native Library download link/IDs are given separately to the coordinator,
not copied into the app/resource lock or Git. Local original:

```text
/workspace/iDeck/.work/steam-bundled-gamepad-20261019/owner-cache/owner-steam-cache.tar
```

An ordinary `gh release create` attempted a separate private cache release/tag
`ideck-owner-steam-cache-v1-20261019`, targeting baseline52aa5b5, without changing
the existing Linux payload Release. Asset upload returned **HTTP401 Bad
credentials** from
`https://uploads.github.com/repos/Mi-Yomi/iDeck/releases/417003571/assets`.
This was **not an automatic approval-review rejection**. No retry, new
credentials, auth login or workaround followed. Subsequent release GET417003571
returned404; listing releases and the remote tag found no such cache release/tag.
The request's ID is not proof of an existing release or uploaded asset.

**Delivery completed:** the coordinating executor reports authorized private
upload and independent full readback for release417038191, prerelease=true:
https://github.com/Mi-Yomi/iDeck/releases/tag/ideck-owner-steam-cache-v1-20261019 .
The actual tag ref is1593537c7ae7e7fdada864afb1830cac83a91fa4. Asset655626057 is
379228160 bytes; server digest and independently downloaded full SHA match
`a75ea9bb8a19946cf81b2fb3d6cc4db97db6a1fe0938e4f23857c2c6e826adef`.
`ipa/steam-cache.lock.json` now pins
`https://api.github.com/repos/Mi-Yomi/iDeck/releases/assets/655626057`.
Remote/readback facts are coordinator supplied; this pinning step reverified the
real existing TAR and staging locally, without repeating failed credentials.
The earlier401 attempt above is historical. Existing releases were not changed.

Cache `source_commit` remains52aa5b55d3c3466adf59ac2edac82a4b670f767f: it records
actual cache preparation, not the app build or release tag. Its source-input
hashes/sizes were rechecked against those exact Git blobs. The delivery tag SHA
is recorded separately. Archive, entries, source inputs and functional code are
unchanged; only delivery/URL and the necessary overlay-lock hash changed.
New pinning evidence: `experiments/linux-guest/evidence/steam-cache-pin-20261019/`.

## Automatic Start path

The app's new resource is separate `iDeckSteamCache/owner-steam-cache.tar`.
Xcode stages it through the shared canonical-format verifier; final IPA packaging
requires exact full digest, all62 entries and the exact resource manifest.
The original five-file Linux payload and its `valve_client_bundled=false` describe
that unchanged seed; the separate cache is what adds client package bytes to
the future IPA. Original kernel/initramfs/raw and all23 source bindings remain.

Start checks full bundled TAR SHA, then reuses a verified existing cache or calls
the existing bounded importer into `Documents/iDeckSteamOffline-v1`. No file
picker is required. Reserved partial restart, publication reconciliation,
no-replace/permissions/lock/hash/space gates remain. Corrupt existing files are
preserved and refused. The new helper runs before the existing/new userdata
branch. Existing `rootfs-v1.raw` is opened and validated; it is never replaced
with a new seed. Both paths attach the same pinned readonly cache block device.
All blocking cache/disk/report IO precedes the existing fresh RAM/native gate.
Cancellation is checked between chunks without per-chunk report persistence.

Honest stages: verified packages → Linux desktop → **Install / resume** →
**Launch Big Picture**. These last two remain explicit actions. A cache is not
a fully installed client or proof of a working window. Existing installer and
runtime failures are not claimed fixed by predownload; actual blocker/status
remains visible. Steam updater/login/agreements may require network and owner
action. No automatic agreement acceptance, account copy or silent network
fallback on cache failure. Advanced explicit cache import remains available.

Expected IPA growth is about379 MB (362 MiB); from the prior710858044-byte IPA,
roughly1.09 GB total before measuring actual packaging/compression. On phone,
the bundle and imported cache are separate copies. First cache import requires
archive size +1 GiB free reserve. New userdata retains12 GiB +1 GiB provisioning
gate separately; existing userdata does not reimport12 GiB. No resize/sparse/
all-storage feature was added. Auto RAM experimental cap4096 is unchanged.

## Screen controls: actual backend

The pinned runtime exposes Linux QEMU named key and pointer events via
`husk_display_send_key` and `husk_display_send_pointer_buttons`. Its separate
`husk_gamepad_*` bridge feeds the Android translation runtime and is not a Linux
HID/joystick path in this profile. The new original UI uses only the existing
serialized Linux input queue and liveness gate. No DroidDeck code/assets were
copied; conventional gamepad positioning follows the requested style.

| Screen control | Guest keyboard/mouse event |
|---|---|
| Left digital stick | WASD, axis dead zone0.22, diagonals |
| Right digital stick / D-pad | Arrow keys |
| A / Start | Enter |
| B / Select | Escape |
| X / Y | Space / Tab |
| L1 / R1 | Shift / Control |
| L2 / R2 | Right / left mouse at the current cursor |

This is **keyboard/mouse mapping, not an enumerated Linux gamepad**. No analog
HID axes, controller detection, relative mouse-look or universal game bindings
are claimed. Pointer placement remains the normal guest touch input.

UIKit tracks independent touch identities, retains stick ownership and combines
held controls; multiple fingers can hold stick+face+trigger. Multiple owners of
the same key/button do not release each other or a physical keyboard/touch click.
Blank overlay regions pass through to the existing display. Hide releases only
screen controls and preserves VM/session. Home/background/Stop use existing
release-all/serialized queue handling. Ordinary keyboard/touch/navigation,
one-VM/native ownership and Stop remain. Accessibility actions provide individual
direction/button taps; physical visual/multitouch acceptance still needs device.

## Checks and next CI

**587 Python tests OK:582 PASS,5 SKIP.** Offline fixtures exercise real canonical
pack/stage/repeat/standalone verification, corruption, missing delivery, links,
no replacement, shared existing payload transport and budget exhaustion before
spawning a new child. Full source overlay, generators, all23 bindings, protected
recovery/disk/payload files, real original Steam staging, AST/shell/attrs PASS.
Evidence: `experiments/linux-guest/evidence/steam-bundled-gamepad-20261019/`.

Mandatory Apple gate now also requires **LINUX_STEAM_BUNDLED_CACHE_PASS** and
**LINUX_STEAM_SCREEN_CONTROLS_PASS**, compiling the actual production helpers.
Fixtures cover bundle auto-import/reuse, whole-pin refusal even with an existing
cache, interruption/retry/publication recovery, preservation of a synthetic
userdata sentinel, simultaneous controls, overlapping physical key/mouse
ownership, neutral/nonfinite sticks and release-all. The integrated pinned Husk
typecheck includes the actual new UIKit overlay. These Apple checks are
**NOT RUN here**; no Apple SDK/compiler is available in this Linux environment.
Device, graphics, games and new installed-client acceptance remain NOT RUN.

The user explicitly authorized using the remaining106 free minutes; the former
120-minute prerequisite is removed for this task. Only the dedicated
`ideck-linux-probe-ipa` workflow changed: provider cap **95 minutes**, aggregate
worker budget **90 minutes from script entry**, including initial cache/source
preparation. At the coordinator's106-minute snapshot this leaves11 minutes below
the provider cap. Fresh quota with reserve, **paid OFF**, private source and
native-build approval remain mandatory. No CI was dispatched/cancelled here.

Coordinator continuation after reviewing the final pushed pinning commit:

- Source branch `codex/steam-arm64-experiment-20261017`; workflow
  `ideck-linux-probe-ipa`; `expected_commit=<full final post-pin HEAD>`.
- `free_quota_verified=true`, `private_source_verified=true`,
  `native_build_approved=true`, only after fresh quota/reserve and paid-OFF checks.
- Provider cap95/internal90 remain; no static120-minute prerequisite in the
  active native workflow/worker. The authorized106-minute snapshot leaves11
  minutes below the provider cap. Other workflows/environments are unchanged.
- Keep existing `ideck-debian-payload` / `IDECK_DEBIAN_PAYLOAD_TOKEN`; no new
  secret or URL override. The pinned cache URL uses existing private transport.
- Run all mandatory Apple markers, including bundled-cache/screen-controls,
  fresh-handoff/offline/Auto RAM and integrated actual Husk/UIKit typecheck.
  No CI dispatch occurred here; new Apple/device checks remain NOT RUN.

BusyBox corresponding-source provenance remains **OPEN**. This change does not
close that inherited limitation or establish general distribution permission.
