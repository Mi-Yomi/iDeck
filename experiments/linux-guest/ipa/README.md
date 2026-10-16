# iDeck Linux Probe IPA build

The `ideck-linux-probe-ipa` Codemagic workflow is a **native source build recipe**.
The [Apple run at 5cd442c](https://codemagic.io/app/6ad03ce9a8a969b53f3a4aa9/build/6ad174a63ffd2c7f0ad3c64c)
built the real runtime, linked the app and produced `iDeck-Linux-Probe.ipa`:
**49,205,131 bytes**, SHA-256
`2c38939b7c0d03586879b69451a4e42afa3d62399ab165fe76e8810f472a6513`.
The result status is `linux_probe_ipa_built`; parent/root independently audited
the downloaded bytes, ARM64 iOS-device binaries, bundled dependencies, guest
assets and matching provenance. Of 92 steps, 91 exited zero; the initial missing
Metal probe was the one expected nonzero and recovered through Apple's download.
See `../evidence/first-ipa-success.json`. Preserve the successful build revision,
native pins and original artifacts. Owner sideload re-signing must use a copy;
installation, device Linux/JIT/input and Steam remain untested. Earlier evidence
remains historical.

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

Before `native-base` generates the Meson cross file, the worker creates a
build-only venv using CPython 3.12 on macOS arm64. It installs only the exact
[PyYAML 6.0.2](https://pypi.org/pypi/PyYAML/6.0.2/json) cp312/macOS arm64 wheel
from `python-requirements.lock.txt`, using isolated pip, no index/dependencies,
binary-only mode and required SHA-256 verification. The venv interpreter must
import the expected yaml version with executable, prefix and module paths
inside that environment before its bin directory is prepended to child PATH.
After native-base, both generated `cross-ios.meson` and `cross-darwin.meson`
must name that exact absolute venv Python; each file hash is recorded before
ANGLE/GPU starts. This also checks the actual files rather than assuming PATH
selection. System packages and QEMU's own Python setup are not changed. Setup,
identity or import failures stop the build. This preparation passed in the
Apple run at c9bd25b; wheel identity and host tests alone do not prove linking.

The QEMU-specific patch `0002-qemu-ios-needs-exe-wrapper.patch` marks generated
cross-file properties with `needs_exe_wrapper = true` only for a configure
cross build. It keeps the actual iOS compiler and machine settings, while
preventing Meson's host-execution heuristic from running device binaries on
macOS. The worker checks/applies the patch and records its SHA before QEMU
setup. This control passed in the Apple run at 9e2e481; a native host compiler
probe is the next separate setup boundary. Exact QEMU
`meson-logs/meson-log.txt`, `config-meson.cross` and `config-meson.native` paths
are retained as artifacts when produced; a missing previous log is not rebuilt.

Before QEMU, the worker resolves clang and the macOS SDK explicitly, queries
that compiler's actual default Apple arm64 Darwin/macOS triple, and builds a
new C executable with explicit `-target` and `-isysroot`. The probe includes
TargetConditionals.h and rejects an iPhone/non-macOS target; it must compile,
link and execute with the expected marker. Only then does the worker publish
`IDECK_QEMU_HOST_CC`, which `0003-qemu-macos-build-compiler.patch` passes via
QEMU's `--host-cc` for build-machine generators. Invalid paths/triples and
compile/link/execute failures stop the build. Ambient SDKROOT and iOS target
compiler flags stay intact. Parent reports this gate passed in the Apple run
at 5cd442c; structured result content and parent/root static package audit
confirm the built artifact. This is not device execution proof.

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
existing aggregate budget. This preparation passed in the Apple run at efa6741;
full runtime and app linking remain separate gates.

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
its ANGLE build passed on Apple at c9bd25b. Full runtime integration remains
separate and unverified. Homebrew tool
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

The integrated suite passes 110 network-free host tests (15 QEMU host compiler,
8 QEMU cross-build, 19 Python setup/cross-file, 12 Metal bootstrap,
20 bounded-download and 36 earlier tests), with independent review. The host
compiler tests simulate xcrun/clang/probe subprocess results; they do not execute
an Apple compiler or a real macOS binary. The QEMU tests isolate their Git repositories
and verify conditional property emission and fail-closed patch application;
a full primary configure control differs by exactly four inserted lines. Setup tests simulate subprocess/pip/Apple outputs; they do
not install packages, execute an Apple compiler or download a component. The earlier tests include wrong branch/SHA/default-input rejection,
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
the next run passed Swift typechecking. The latest Apple run completed native-base,
Metal component preparation, ANGLE, Python yaml preparation and GPU dependencies;
the successful run at 5cd442c also passed the build-machine compiler probe,
QEMU integration/rebuild, app linking and packaging. Parent/root static artifact
audit passed; device execution remains separate.

The new extraction helper fully unpacked all seven locked source archives on
Windows/Python 3.12.14 and wrote a valid result with real guest metadata. Only
the documented X11 symlink was omitted. This 359.61-second host control did not
run an Apple compiler. A slower duplicate WSL extraction was interrupted and is
not counted as a passing control; see `../evidence/native-input-fix.json`.
