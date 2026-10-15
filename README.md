# iDeck private Apple compiler check

This private repository initially transports a reproducible source snapshot for a bounded, manual Codemagic compiler check. It is not yet a full mirror of the development Git history.

The planned source reconstruction uses Playport baseline `412de5f8c0bdd26d84e0127eb5776ba992e3b152`, an audited private binary diff, the exact source-tree hash, and a SHA-256 file inventory. Original upstream and dependency licenses remain in the reconstructed source.

The first check will compile real package sources for arm64 iOS and typecheck the actual main iDeck app sources with Apple SDK headers. Runtime linking, an installable IPA, device tests, and Steam Big Picture gameplay are separate, unverified gates.

No source snapshot or build configuration has been uploaded yet. No automatic GitHub Actions, signing, paid billing, publishing, or credentials are configured here.
