# iDeck-BCD: process-private fixed x64 images

Fork-local change, 2026-10-22. Opt-in: `env.MADEIRA_FIXED_IMAGE_ISOLATION = 1`.
Set it on the launcher entry before starting a fresh Wine session. It requires
the matching rebuilt `xtajit64.dll` and default per-process alias callbacks.

## Problem and behavior

Wine's iOS port runs Windows processes in one host address space. Two x64
executables without relocations, such as the reported `1cestart.exe` and
`1cv8s.exe`, can require the same image base while both processes remain alive.
Moving the PE header or waiting for the parent to exit cannot solve that case.

With the switch enabled, each eligible fixed x64 image has private backing.
The original guest range is reserved with no access from the first process
onward, so an untranslated child access cannot silently read its parent.
Windows still sees the original image base in the PE header, loader, query and
server records. Owner-aware Wine paths and FEX translate image access to the
current process's backing. Pure x64 images do not consume native executable
pool copies; FEX compiles their code into its existing private emulator cache.

The FEX callback uses an explicit versioned tag and checked data export, distinct
from ARM64EC execution aliases. Decode, scalar/atomic data accesses, protection,
self-modification and unmap notifications follow the appropriate address domain.
Unmap withdraws the window and process teardown releases its backing. Guest
guards remain reserved for the session. Wine's native I/O boundary translates
image buffers before kernel copyin/copyout; cross-process memory operations use
the target process owner.

The feature is limited to non-hybrid, non-builtin, non-resource AMD64 images
with stripped relocations and a preferred base at or above 4 GiB. It does not
implement a separate address space for arbitrary heaps or every Windows mapping.
The switch defaults to off. Existing relocatable images follow the existing path.
Unknown native fault encodings, unaligned native atomics and native exclusive
monitor sequences on a guest guard are refused rather than emulated with
non-atomic copies. A device log can reveal whether an application needs one of
these additional native paths; the supported FEX atomics translate before access.
Native pins and the shipped PE ntdll ABI are unchanged; FEX changes are applied
by a checked fork-local build overlay and restored after the build.

## Validation

Actions runs compiled host tests for the actual native window registry, guard
reservation and I/O helper, plus extracted production FEX callback/address IR.
It rebuilds FEX, verifies `IosGuestWindowAbi` in the resulting DLL, and builds
two distinct executables at the identical fixed address. A separate
`fixed-image-test-<build>` artifact includes these executables and their instructions
in `FIXED-IMAGE.md`; the two IPAs remain in `unsigned-ipa-<build>`.

See `tests/proc/FIXED-IMAGE.md` for the simultaneous parent/child device test.
Device test and actual 1C launcher/client: **NOT RUN**. Host tests and a successful
IPA build cannot establish that 1C runs on a device. The repository contains no
1C binaries or business databases.

For 1C, enable the switch for the installed launcher and start `1cestart.exe`
from a fresh session. Reinstallation is not part of this change. A useful device
log should contain `[fixed-image] reserved guest ...; backing is private per
process` and show both launcher processes reaching execution. Record the device,
iOS version, build and result separately before treating this as a verified fix.
