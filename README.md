# iDeck private Apple compiler check

This private repository transports a reproducible, audited development-source snapshot for a bounded manual Codemagic check. It is **not a full mirror of the original Git history**.

## Source provenance

- Original source checkpoint: `1b07a996efe8cec2e12e3d3c1e19805c198fcccf`
- Exact reconstructed Git tree: `a305e267ebdb87ec4d202f4f8d5c499cc5ffbe44`
- Public Playport baseline: `412de5f8c0bdd26d84e0127eb5776ba992e3b152`, https://github.com/playportdev/playport
- Nonrecursive Madeira header pin: `8c050d03f4d89096e1e2e2c8bb44479fffd86619`, https://github.com/willfaust/Madeira

`source.patch.gz` contains the binary Git diff against the baseline. `source-manifest.json` binds the exact source/tree and compressed/diff/inventory hashes. `source-files.json.gz` lists every tracked path, Git identity, mode, byte count and SHA-256. `ci/reconstruct_source.py` verifies these before executing any project compiler-check code. Upstream and dependency license notices remain in the reconstructed tree.

The snapshot includes the audited tracked tree, including original public documentation/media and build records. It excludes untracked work, local credentials, SDK installations and private runtime outputs. The reconstructed checkout's HEAD remains the public baseline with the approved private diff staged; the exact index tree is the source identity.

## First manual check

`ideck-main-apple-source-check` uses Xcode 26.6 on the Personal M2 runner, with a 25-minute provider cap and a 1,020-second internal compiler budget. The exact iPhoneOS 26.5 SDK is checked at runtime. Before dispatch, verify free macOS minutes remain and paid subscription is disabled. The workflow's input assertions record that check; they do not enforce provider billing.

The check compiles six real package modules for arm64 iOS, emits the actual JITHelperXPC module, and typechecks 92 development / 80 release main-app Swift sources against Apple SDK and real pinned C headers. It creates no guest-runtime substitutes. The build does not link the Wine/FEX/CEF runtime, create an IPA, sign, install or establish actual Steam Big Picture/gameplay success.

No automatic GitHub workflows, automatic retry, cache, signing, secret groups, publishing or artifact upload is configured. Inherited `.github` files stay inside the reconstructed source only. Bounded actual compiler-failure diagnostics and a compact machine-readable result are printed into the private build log.

Build configuration and source presence do not constitute a successful Apple build; consult the actual Codemagic run result.
