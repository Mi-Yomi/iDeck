# Isolated Linux route on pinned Husk

This overlay connects the Linux probe to actual `qemu_init`, `qemu_main_loop`,
Husk JIT and software Metal/input APIs. It is source integration, not an accepted
iOS runtime. Upstream stays at `0695248f491cda877f7969d1f0cc89aeede1482e`.

## What changes

- The app chooses Linux or the existing Husk library before constructing either
  runtime's screen. The selection is shared across windows and fixed for this
  process. Android maintenance/download reconnection moves to library selection.
  Previously scheduled OS background download callbacks retain upstream behavior.
- Linux checks JIT availability and uses the existing prewarm/execution path.
  Husk's prewarmed allocation can be 512 MiB, although this guest requests a
  256 MiB TCG cache. The report records both rather than claiming a 256 MiB total.
- Asset hashing and file IO run off the UI thread. A unique directory under
  `Documents/iDeckLinuxSessions` contains each session. The QEMU thread retains
  both strings and argv pointer storage for the process lifetime.
- No Android GL probe, disk, snapshot load/save, bridge watcher or Android boot
  policy runs in this route. Software display registers after QEMU init.
- The UI displays the real guest, forwards taps, offers a Send A button and
  exports serial/result files. The guest capture window is 20 seconds: tap the
  image and press Send A when prompted. Missing releases/axes fail validation.
- The native verifier compares every RGB channel in both 800×600 frames from
  the QEMU display bridge and decodes real AArch64 evdev records. This does not
  independently establish pixels on the physical panel; retain a screen recording.
- Reports include app executable SHA-256, OS version, guest/profile hashes,
  argv, input outcome and framebuffer hashes. They do not declare Steam or
  accelerated guest graphics verified.

One guest start per process is deliberate. The pinned software display bridge
has no safe unregister/reset API. On loop exit, no second runtime or QEMU cleanup
is attempted against a live MTKView; close/reopen the app. A 120-second evidence
deadline stops validation, not the guest process. No watchdog kills the app.

## Reproduce source/resource staging locally

Use a complete clean local checkout of the pinned Husk commit and a guest
directory produced by `prepare_guest.py`. Expand a sparse clone before staging;
the staging tool does not fetch missing objects or install dependencies.

```text
python experiments/linux-guest/tools/stage_husk.py --upstream .work/husk-base --guest .work/linux-boot/probe-final --out .work/husk-linux-staged-final
python .work/husk-linux-staged-final/scripts/ideck-stage-linux-guest.py .work/husk-linux-staged-final/guests/ideck-linux .work/ios-probe-bundle-new/iDeckLinuxProbe
```

Use a fresh output worktree. `overlay.lock.json` binds canonical new sources,
format-patch series, patched upstream bytes and the source-check archive. The
input source checkout and old iDeck export are not edited. Images remain ignored.

The first staging run used a sparse checkout; that directory is retained as an
intermediate, not a complete app source result. The final run used the full
checkout and the tool now rejects sparse inputs.

## Apple compiler gate (passed at 3a10400; native build pending)

The first `ideck-linux-probe-ipa` run used this gate at transport commit e9dfb4b.
Profile/evidence iOS checks and Mac validator tests passed, but upstream app
typechecking stopped at a missing `husk-console-abi.h` in the offline archive.
The archive now includes the original pinned header and validates the bridge's
literal local-include chain before restoration. The supplied Apple log and a
real local Clang before/after check are retained in `../evidence/`.
The user-supplied log of build `6ad129af3ffd2c7f0ad3b35b` at 3a10400 shows the
corrected Swift gate completed: the worker proceeded through tool setup and
source staging before failing on QEMU archive extraction. This confirms the
gate's completion, not native compilation, linking or device execution.

The manual `ideck-linux-guest-profile-check` has a 480-second aggregate budget
and a 10-minute provider limit. Current free-quota/private-source checks and the
exact clean reviewed transport commit are still required. No trigger, network
download, dependency installation, signing, IPA, push or device action.

The worker performs:

1. Real iOS SDK typechecking of profile/evidence code; native Mac validator tests
   against a captured real guest log and negative fixtures.
2. Integrity-checked restoration of 78 exact upstream Swift/header/license files
   from `husk119-source-check.tar.gz` into `.work/linux-profile-apple`.
3. Whole-app Swift typechecking for `arm64-apple-ios16.0`, Swift 5 mode, using
   the real `HuskBridge.h`, app Swift sources, Shared Swift sources and
   `HuskJITMessages.swift`. Upstream is checked before the patched version.
   An upstream SDK/compiler failure is retained and blocks acceptance; no fake
   JIT/QEMU declarations or disabled verifier are used to force a pass.

This does not compile C/Objective-C runtime bodies, link libraries, sign or prove
a device session. A full app build needs the pinned Husk build scripts/native
dependency outputs and Xcode project regeneration from patched `project.yml`.
The worker records the actual Xcode/SDK version; configuration is not proof it
is installed. No Swift compiler or Apple SDK check has run on this Windows host.

## Measured locally

- All 78 upstream files match SHA-256 and their original Git blob IDs; the
  previous 77 files are unchanged.
- Patch application and the complete independent staged worktree match the lock.
- Thirty-six host tests passed, including rejection of the missing transitive
  header even with valid archive hashes. Synthetic fixtures are not device
  execution. Host Clang reproduced the old archive's missing-header failure and
  passed syntax checking of the corrected staged archive with the same flags.
- Kernel/initramfs bytes after resource staging matched the previous images.
  A real Windows QEMU run from that bundle passed both full pixel comparisons
  and guest key/pointer checks in 25.125 seconds.

Next device test: record signed app identity and OS version; choose Linux;
enable JIT; Start Linux; observe frame A; tap and Send A during capture; observe
frame B; save the report and a screen recording. A compiler pass is insufficient.
