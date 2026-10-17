# Steam ARM64 CPU requirement: reproduced LSE fault

The initial pinned Valve ARM64 client executes `ldaddal x1, x0, [x0]`
(instruction word `f8e10000`) at ELF virtual address/file offset `0xe2548`.
This is an Armv8.1 **FEAT_LSE** atomic instruction. The QEMU Cortex-A72
model does not expose that feature. Changing libraries cannot repair this
particular SIGILL. [Arm's description of LSE and LDADDAL](https://developer.arm.com/community/arm-community-blogs/b/tools-software-ides-blog/posts/compiler-flags-across-architectures-march-mtune-and-mcpu)
provides the architectural context.

## Observed execution

The original binary was extracted locally from the verified official archive,
without adding Valve bytes to Git or a distributed payload:

| Input | Identity |
| --- | --- |
| Client lock version | `1792192922` |
| `steamrtarm64/steam` size | `10174384` bytes |
| Native binary SHA-256 | `73da03ead208a74e14bee566869a4235063dc4a9e1063f29c4608de6d78bd4ea` |
| Archive SHA-256 | `26c731703e4a641c8d9ec1ac80e2bc40e3837fc312d180ab32316e33ed980834` |
| Debian libc | `2.41-12+deb13u4`, ARM64, pinned in `ipa/gui-inputs.lock.json` |
| Host user QEMU | `10.0.13 (Debian 1:10.0.13+ds-0+deb13u1)` |
| User QEMU SHA-256 | `73cc2584f119f9e74c85c0a8549dbb6fd104ae3897a06a7500797f9e5b4d0943` |

The reproduction ran the real binary using the pinned extracted dynamic loader,
an empty private HOME, core dumps disabled and `unshare --net` (an empty network
namespace). No guest VM, shared disk or live network request was used.

* `cortex-a72`: subprocess return `-4` (SIGILL). The last translated block is
  exactly one `ldaddal` at PC `0x780643712548`. The opcode occurs once in this
  binary, at `0xe2548`; independent GDB disassembly agrees.
* `cortex-a76`: the same binary advances to the genuine Valve updater's Startup
  messages, then exits `148` with `Steam data link does not exist, client is
  misconfigured` for the deliberately absent private `~/.steam/steam` link.
  This isolated instruction diagnosis is not a full installation or UI test.

The user-mode result corroborates the earlier full-VM Cortex-A72 exit `132`.
The original full-VM fault PC was not captured, so its exact PC is not claimed.
These observations concern the initially pinned binary; a Steam update may
introduce additional requirements.

`tools/steam_cpu_probe.py` builds a small **original**, static ARM64 ELF with the
same instruction word. It verifies both the returned old value (`41`) and the
stored new value (`42`) before exiting. Actual execution results:

| CPU model | Return | Result |
| --- | --- | --- |
| cortex-a72 | `-4` | SIGILL as expected for unavailable LSE |
| cortex-a76 | `0` | Both atomic results correct |
| max | `0` | Both atomic results correct |

Reproduce with the existing user-mode QEMU, using a **new** output directory
under the permitted task workspace (the helper refuses an existing directory):

```sh
python3 tools/steam_cpu_probe.py \
  --qemu-user '/path/to/existing/qemu-aarch64' \
  --output '/permitted/task/workspace/new-lse-probe'
```

The probe uses no network syscall, Steam binary, VM or block backend. Full local
traces and extracted binaries stay outside Git in `review/cpu-probe` of this
experiment's workspace. Small logs, checksums and receipts are in
[`evidence/steam-cpu-20261017`](evidence/steam-cpu-20261017/receipt.json).

## Pinned iOS QEMU source assessment

The local `qemu-10.0.12-utm.tar.xz` was verified against
`ipa/native-sources.lock.json`: size `142836072`, SHA-256
`7c9605290b34152debb842e965a55d2e4fbba4793e536ab677b4027e5dc0ba1a`.
It is the pinned [UTM release source archive](https://github.com/utmapp/qemu/releases/download/v10.0.12-utm/qemu-10.0.12-utm.tar.xz),
not the host 10.0.13 source. The inspected source provides the necessary LSE
model and TCG translation path:

| Source location in that archive | Evidence |
| --- | --- |
| `target/arm/cpu.h:2179` | `ID_AA64ISAR0.ATOMIC` occupies bits 20–23 |
| `target/arm/tcg/cpu64.c:314` | A72 `ID_AA64ISAR0=0x00011120`; ATOMIC=0 |
| `target/arm/tcg/cpu64.c:355` | A76 `ID_AA64ISAR0=0x0000100010211120`; ATOMIC=2 |
| `target/arm/tcg/cpu64.c:1141` | max TCG explicitly sets ATOMIC=2 (`FEAT_LSE`) |
| `target/arm/cpu64.c:758` | max uses the TCG model under TCG; host under KVM/HVF |
| `target/arm/cpu-features.h:407` | `aa64_atomics` requires ATOMIC != 0 |
| `target/arm/tcg/a64.decode:527` | LDADD instruction decoding exists |
| `target/arm/tcg/translate-a64.c:3757` | LDADD is gated on `aa64_atomics` and calls `tcg_gen_atomic_fetch_add_i64` |
| `tcg/tcg-op-ldst.c:1288` | The TCG atomic fetch-add implementation exists |

`do_atomic_ld` in `translate-a64.c` explains that the TCG atomic primitive
provides the full barrier needed for acquire/release semantics. The inspected
file hashes are recorded in `qemu-source.json`.

This is source compatibility evidence for the missing instruction. It does
**not** verify the built `libqemu-aarch64-softmmu.dylib`, its build configuration,
the complete Steam client, or execution on iPhone. Host `-cpu max` success is
not evidence that the same model works in the pinned iOS runtime.

## Dependency chain for a future iOS Steam-only CPU gate

No production profile or runtime was changed for this investigation. An iOS
Steam experiment still needs all of the following separately validated:

1. A separate Steam profile, CPU choice and diagnostics. Current
   `ios/LinuxGuestProfile.swift:85` and `ios/LinuxTerminalProfile.swift:48`
   require `cortex-a72`. `LinuxDebianProfile.swift:61` and
   `LinuxGUIProfile.swift:105` obtain their base arguments through that guarded
   profile. Do not silently change the accepted Terminal/Debian/Desktop CPU.
2. The actual pinned Apple-built runtime and TCG path. Native sources are locked
   in `ipa/native-sources.lock.json`; `ci/build_linux_probe_ipa.py` builds and
   packages `libqemu-aarch64-softmmu.dylib`. Record its identity and actual
   selected model rather than inferring it from the host executable.
3. A runtime gate on that **built** iOS runtime: guest feature advertisement
   (`atomics`/ATOMIC), successful execution of this static probe, and then the
   verified real client. The candidate A76 is sufficient for the reproduced
   LSE instruction; it is not yet a claim about every updated Steam component.
4. Existing JIT pairing, argv lifetime, same-thread QEMU initialization/loop,
   disk ownership and Stop contracts. `ios/LinuxTerminalSession.swift` retains
   the owner thread after the loop (around lines 559–587), and
   `finalizeIfClean()` (around line 796) does not treat loop return as backend
   cleanup. A separate Steam path must keep these guarantees and report its
   real CPU instead of reusing hard-coded Cortex-A72 metadata.
5. Apple Swift/runtime regressions and a real device test. **NOT RUN** by this
   CPU investigation. CPU support alone does not resolve namespace, graphical
   API, memory, storage, updater, Big Picture or game-performance requirements.
