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

**Remaining delivery blocker:** the private GitHub asset URL does not exist yet.
`ipa/steam-cache.lock.json` seals the real local bytes but deliberately omits
`payload_url`. `steam_bundled_cache.prepare_for_build` stops before Apple/native
setup with `STEAM_BUNDLED_CACHE_ASSET_NOT_UPLOADED`. It accepts an explicitly
materialized `IDECK_STEAM_CACHE_FILE` on an approved runner, verifying the same
full digest and canonical entry contract. No synthetic substitute or unchecked
URL is accepted. No Valve binaries are committed to Git or publicly uploaded.

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

Minimal coordinator continuation:

1. Materialize the retained owner cache with authorized tools; verify size/full
   SHA. Use an existing authorized private uploader to place it in Mi-Yomi/iDeck
   without changing repository audience or the original Linux payload asset.
2. Verify actual server upload/readback. Add only the real same-repository asset
   API `payload_url` to `ipa/steam-cache.lock.json`, update delivery facts, and
   update that file's SHA in `husk/overlay.lock.json`. Never invent an asset ID.
3. Run checks, commit `[skip ci]`, push only the Steam branch, verify remote SHA
   and clean checkout. Cache content digest stays exactlya75ea9bb…e826adef.
4. After review and fresh quota/paid-OFF checks, dispatch **one** manual build:
   branch `codex/steam-arm64-experiment-20261017`, workflow
   `ideck-linux-probe-ipa`, `expected_commit=<full final post-pin HEAD>`,
   `free_quota_verified=true`, `private_source_verified=true`,
   `native_build_approved=true`. Keep existing `ideck-debian-payload` group and
   `IDECK_DEBIAN_PAYLOAD_TOKEN`; no new secret. The cache fetch uses the pinned
   API URL and existing private payload transport; do not set the Linux-seed URL
   override to select cache bytes. All previous mandatory Apple markers remain.

BusyBox corresponding-source provenance remains **OPEN**. This change does not
close that inherited limitation or establish general distribution permission.
