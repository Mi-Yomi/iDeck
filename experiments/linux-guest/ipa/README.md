# iDeck Linux Probe IPA build

The `ideck-linux-probe-ipa` Codemagic workflow is a **native source build recipe**.
Its first Apple run at e9dfb4b stopped in the Swift source gate because the offline
Husk archive missed `husk-console-abi.h`. The original pinned header is now
included, with a local-include completeness check and a regression test. The
corrected revision has not run on Apple hardware yet; native builds/linking were
not reached and there is no IPA. See `../evidence/source-header-fix.json`.

Select branch `codex/linux-guest-feasibility-20261015` **before** selecting the
workflow. Set `expected_commit` to the full current pushed SHA. `main` deliberately
remains unchanged and does not contain this workflow. Do not reuse the old build
button for the failed `main` run.

Inputs for this workflow:

- `expected_commit`: exact transport checkout SHA, not the Playport source SHA.
- `free_quota_verified=true`: freshly verified at least 120 free macOS minutes
  with paid subscription disabled. The old 10-minute check is not sufficient.
- `private_source_verified=true`: private `Mi-Yomi/iDeck` selected.
- `native_build_approved=true`: approve downloads and build-tool setup on the
  disposable worker. Homebrew installs Meson, Ninja, pkg-config, XcodeGen and
  rustup; rustup installs the locked Rust toolchain and iOS target into `.work`.
  No Windows tools, Apple accounts, certificates or device installations change.

The source check runs first, followed by the actual native dependency builds,
Xcode project generation, `xcodebuild build`, bundle validation, ad-hoc signing
and ZIP packaging. The worker budget is 6,900 seconds; the provider cap is 120
minutes. This is a cap, not a measured duration or a guarantee that a cold build
finishes within it. No automatic trigger or retry is configured.

## Scope and provenance

`project.json` is a separate XcodeGen spec derived from the pinned Husk119
project and the iDeck overlay. It keeps the real Swift/C/Objective-C sources,
Metal shaders, QEMU/ANGLE libraries, pairing and StikJIT helper. It omits the
embedded PS4 and MoltenVK binaries and the Android/Phase0 resource staging.
`IDECK_LINUX_PROBE_ONLY` routes directly to the Linux screen, without a library
chooser. Unused library implementation sources remain in the build; this is not
a stripped or stubbed runtime. Bundle ID is `dev.ideck.linuxprobe` (separate from
Husk), with the matching helper/widget IDs. Normal Husk source/target is retained.

`native-sources.lock.json` fixes the seven official source archive sizes/hashes,
Husk/GPU/libucontext Git revisions, and Rust version. WebKit ANGLE is now pinned
to a concrete revision, instead of upstream's moving shallow default branch;
its compatibility with this recipe is **not yet measured**. Homebrew tool
versions are recorded per build, not claimed to be reproducibly pinned.
Cargo dependencies remain locked by upstream `Cargo.lock`.

The separately applied `0001-fail-closed-native-build.patch` prevents the pinned
native script from ignoring rejected patches or a missing QEMU output. It is
not part of the Swift-only source slice, and does not weaken a verifier.

`../husk/linux-probe-guest.tar.gz` contains exactly the previously host-tested
`profile.json`, `vmlinuz-virt` and `initramfs-ideck.gz`. `guest.lock.json` checks
the archive and each member before staging. The original Alpine 3.24.1 archive,
module and compiled probe identities are in the bundled profile and
`../evidence/boot-inputs.json`; the guest recipe and `fb_probe.c` remain in this
repository. This Alpine/musl guest is a boot/display/input probe, not a glibc
Steam rootfs. Preserve upstream license notices and source provenance.

## Acceptance and artifacts

Success requires `LINUX_IPA_BUILD_RESULT.status = linux_probe_ipa_built`, a real
`iDeck-Linux-Probe.ipa` and its SHA-256. `xcodebuild` must exit successfully; the
new DerivedData directory cannot supply a stale app. Packaging verifies guest
hashes, app/helper IDs, required framework/plugin/shader files, arm64 iOS-device
platforms, packaged dynamic dependencies, code signatures and ZIP integrity.

The IPA is ad-hoc signed for the owner's usual sideload signing; it is not an
App Store/TestFlight export or a provisioned install. On-device JIT, Metal output,
touch/key input, Steam and game performance still need separate measurements.

Artifacts retain the request report, Swift-check logs, native build logs,
`native-products.tar.gz` (expensive native outputs plus their manifest), final
result and IPA if successfully produced. A failed native step is not a linker
error unless the corresponding linker was actually executed. No mock object or
downloaded old Husk109 IPA is substituted for Husk119 output.

## Local checks performed

Thirty-one host tests passed, including wrong branch/SHA/default-input rejection,
real guest archive restoration, source staging, simulator/incorrect app identity
rejection, a real nonzero child-process failure and rejection of the missing
transitive header with valid package hashes. Host Clang reproduced the exact
old-archive error and passed the corrected archive. These do not execute Xcode.
The canonical Git version of the patched shell script passes `bash -n`.
The 15 existing workflows preserve their original execution bodies after the
new request guard; YAML defaults no longer resolve omitted required inputs to
empty environment strings. The first Apple run passed YAML/request validation;
the remaining Swift/native build results are still pending the corrected run.
