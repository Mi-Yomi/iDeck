# iDeck Linux Probe IPA build

The `ideck-linux-probe-ipa` Codemagic workflow is a **native source build recipe**.
The latest [Apple run at 86d4ac0](https://codemagic.io/app/6ad03ce9a8a969b53f3a4aa9/build/6ad15b143ffd2c7f0ad3c111) passed the Swift source gate,
verified all seven source archives (pixman on its first attempt), and completed
`native-base`. It stopped at `native-angle` because the Xcode 27 runner lacked
the Metal toolchain. These results come from the coordinator's browser summary,
not a full raw log. Full QEMU/Husk compilation, app linking and IPA packaging
remain unverified. See `../evidence/metal-toolchain-bootstrap.json`; earlier
source-header, extraction/JSON and download-retry evidence are preserved as
historical snapshots. There is no IPA or device Linux/Steam proof yet.

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
finishes within it. No automatic build trigger or build rerun is configured.
Source archive fetches have bounded transient retries with unchanged TLS and
integrity checks; access denial, certificate errors and hash mismatches fail.

Before ANGLE, the worker compiles a minimal Metal shader using
`xcrun --sdk iphoneos metal -c`, requiring a newly produced nonempty AIR
file. If that probe explicitly reports a missing Metal Toolchain and Apple's
recovery command, it runs
[`xcodebuild -downloadComponent metalToolchain`](https://developer.apple.com/documentation/xcode/downloading-and-installing-additional-xcode-components)
once, then recompiles to a different new AIR file. This follows Apple's
[shader compilation flow](https://developer.apple.com/documentation/metal/building-a-shader-library-by-precompiling-source-files).
Probe, download and version commands use `env -i` with PATH/HOME only, matching
the pinned ANGLE recipe; inherited DEVELOPER_DIR/TOOLCHAINS cannot test another
compiler. Compiler version, AIR size/hash and booleans for ignored overrides
are recorded in `result.json`. Generic compiler, license, permission, component
download or reprobe failures remain fatal; there is no automatic license
acceptance or alternate compiler. The component uses the disposable runner and
existing aggregate budget. This preparation still needs its Apple CI rerun.

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

QEMU's locked archive contains an absolute `X11IncludeHack -> /opt/X11/include`
symlink for the EDK2 Unix host emulator. That firmware emulator is not built by
the iOS QEMU dylib recipe. The lock explicitly records this one omitted symlink:
its complete path, type and target must match. All other members retain Python's
`data_filter`; there is no trusted/full-access extraction fallback. Extraction
rechecks archive size/SHA-256 and records omissions in `result.json`. The source
archives themselves are unchanged. Guest report entries contain size/SHA-256,
not binary asset bytes, so a failed build can retain its original error in JSON.

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

The integrated suite passes 68 network-free host tests (12 Metal bootstrap,
20 bounded-download and 36 earlier tests), with independent review. Bootstrap
tests simulate subprocess/Apple outputs; they do not execute an Apple compiler
or download a component. The earlier tests include wrong branch/SHA/default-input rejection,
real guest archive restoration, source staging, simulator/incorrect app identity
rejection, a real nonzero child-process failure and rejection of the missing
transitive header with valid package hashes. Extraction tests reject other
absolute/outside links, path traversal, mismatched omission rules and altered
archive bytes. A real-guest regression writes the failure report while preserving
the original extraction exception. Host Clang reproduced the exact
old-archive error and passed the corrected archive. These do not execute Xcode.
The canonical Git version of the patched shell script passes `bash -n`.
The 15 existing workflows preserve their original execution bodies after the
new request guard; YAML defaults no longer resolve omitted required inputs to
empty environment strings. The first Apple run passed YAML/request validation;
the next run passed Swift typechecking. The latest Apple run completed native-base;
Metal component preparation, full QEMU/Husk runtime and app linking remain
pending a new Apple run.

The new extraction helper fully unpacked all seven locked source archives on
Windows/Python 3.12.14 and wrote a valid result with real guest metadata. Only
the documented X11 symlink was omitted. This 359.61-second host control did not
run an Apple compiler. A slower duplicate WSL extraction was interrupted and is
not counted as a passing control; see `../evidence/native-input-fix.json`.
