# iDeck build progress

Updated: 2026-10-15, 05:22 UTC.

## Goal and current boundary

The priority is **genuine Valve Steam Big Picture on iOS**, with DroidDeck-like
interaction and session behavior. A themed native library or headless Steam
account integration is not a substitute.

There is **no completed iDeck IPA or verified Steam session on an iPhone yet**.
The results below are real Apple compiler and native-library builds, verified
separately from application linking and device operation.

## Verified results

| Stage | Result | Evidence |
|---|---|---|
| iDeck application Swift source | Six dependency modules and real helper modules compiled; all 92 development and 80 release app Swift files passed typechecking. | [Apple source gate](https://codemagic.io/app/6ad03ce9a8a969b53f3a4aa9/build/6ad04ade546ce6236ceeba22) |
| Current Madeira FEX | Seven real iOS archives; all 154 object files independently checked. | [FEX control](https://codemagic.io/app/6ad03ce9a8a969b53f3a4aa9/build/6ad050ed546ce6236ceebb52) |
| Wine generated headers and server | 356 verified headers and a real 49-object iOS wineserver archive. | [Wine control](https://codemagic.io/app/6ad03ce9a8a969b53f3a4aa9/build/6ad0576e546ce6236ceebc85) |
| FreeType and win32u | 42 font-engine objects plus 46 window-subsystem objects; all 88 members verified in the merged archive. | [FreeType/win32u control](https://codemagic.io/app/6ad03ce9a8a969b53f3a4aa9/build/6ad05a7b546ce6236ceebd02) |
| FFmpeg | Four real iOS archives, 209 object files, 45 required API definitions and 127 public headers verified. | [FFmpeg control](https://codemagic.io/app/6ad03ce9a8a969b53f3a4aa9/build/6ad06029546ce6236ceebdf7) |

All downloaded native objects above were checked for arm64 iOS device targeting,
minimum iOS 17.0 and SDK 26.5. Original artifacts, source identities, file hashes,
compiler evidence and license notices are retained. This does not establish
runtime compatibility merely from matching architectures.

The current-Madeira controls use source commit
`279fd0f83170425db002fe25d6bd62f6355f497d`. They are separate from the preserved
Playport baseline and do not silently upgrade its dependency pins.

## In progress

- [Crypto prefix and target API-link control](https://codemagic.io/app/6ad03ce9a8a969b53f3a4aa9/build/6ad06207546ce6236ceebe3c): the corrected-input run passed the exact source-input guard and pinned checkout, then stopped before compilation because its host label is `Apple M2 (Virtual)`. A narrow host-label compatibility correction is under review. It builds real GMP, Nettle and GnuTLS, then checks 106 APIs in an unsigned, nonexecuted iOS link probe.
- Current Madeira app toolchain preflight: preparing an Xcode 27 / Swift 6.4 check for its real StikJIT framework and Swift sources.
- Remaining native ntdll and LLVM/DXMT closure, with exact ABI checks for reusable upstream PE components.

Current source supports an in-tree SM5 shader-conversion path separate from
Apple's converter. A converter-free private first-frame experiment is being
reviewed; this is not yet a linked or tested application, and it would not claim
DXIL/D3D12 support. The default project has a converter staging/signing phase
that must not run accidentally during an unsigned control.

## DroidDeck source findings

Reviewed source snapshot:
[`7fc61b4c`](https://github.com/Droid-Deck/DroidDeck/tree/7fc61b4c3d6552a5aaad35d29054d77e3466d794).
Concrete adaptation targets are Steam-recognized touch-controller layouts,
Steam/game window focus, separate interface/game resolution, first-frame
reporting and bounded recovery from failed starts or update loops.

DroidDeck uses the real Linux ARM64 Steam client and Linux display/input services.
The iOS route requires different platform integration; its Linux binaries and
flags cannot simply be copied into Windows Steam under Madeira.

## Remaining acceptance gates

1. Link a real current runtime and app with complete resources, fonts and PE/CEF dependencies.
2. Verify signing, entitlements and JIT on the target device.
3. Show actual readable Steam content, then genuine Big Picture navigation and input.
4. Verify Steam/game focus, restart behavior and an authorized owned-game launch.

The user reports that Madeira's built-in JIT worked stably on this phone about a
week earlier. That is useful device history, but it does not replace testing the
new signed iDeck build.

Last verified Codemagic usage: **28 of 500 free macOS minutes**. Paid subscription
is disabled. All workflows are manual and bounded; no public repository release
or paid build is authorized by this document.
