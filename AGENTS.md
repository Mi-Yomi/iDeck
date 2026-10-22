# iDeck-BCD: rules for work in this repository

This copy preserves BCD/Madeira history and licences. Read
`docs/migration/AUDIT-20261019.md`, `docs/migration/FIRST-SCOPE.md` and
`docs/ideck/CI-BUILD-20261020.md` first.

Updated 2026-10-20 (owner's decisions): Mi-Yomi/iDeck-BCD is the public build
repository; Mi-Yomi/iDeck is a private mirror whose `main` carries the same
history. Keep the two in step: push the same commits to both.

- Build: `.github/workflows/build-ipa.yml` is the only workflow. It is manual
  (`workflow_dispatch`), runs only in Mi-Yomi/iDeck-BCD, uses a read-only token
  and no secrets, and keeps the two unsigned IPAs as a 14-day Actions artifact.
  Never add signing, OTA, bucket, mail or any other upload step, a push/schedule
  trigger, or a secret. Dispatching it is the owner's call: one run can take up
  to 6 hours of a macOS runner. The upstream original stays byte-identical at
  `docs/upstream-workflows/build-ipa.yml.disabled` (and `altsource.yml.disabled`), for reading only.
- Host checks (`tests/host/check-*.py`) may be run to verify a change. Checks
  that need cc/swiftc/xcrun, Mach or the full submodules only pass on the macOS
  runner; say which ones were not run. Do not run upstream's install, signing,
  OTA or deploy tooling (`tools/sign-and-publish-ota.sh`, `tools/deploy-vm.sh`).
  Do not create keys or broaden connector grants.
- Outbound services: upstream's log/feedback intake, update check and online
  recommendations are OFF by default (`docs/ideck/NETWORK-OFF-20261020.md`); our
  own endpoints go only in Info.plist's `IDeckEndpoints`, https only, and only
  after the owner chooses them. Never repoint user data to a guessed endpoint.
- Do not copy iDeck/Husk source until file-level licences are verified. Prefer
  new small changes through existing BCD interfaces. Do not add Linux ext4,
  QEMU guest or old cache/recovery stacks to this Wine/FEX architecture.
- Preserve all notices and credits. BCD Material retains GPL-3.0-only + its
  exception/additional terms. Mark modifications and dates; preserve the exact
  attribution line. Use our own branding before distributing a modified app,
  verify the Metal Shader Converter's redistribution terms, and do not imply
  upstream endorsement. An Actions artifact of a public repository is a
  distribution: its source is the same commit, with submodules at their pins.
- Do not change any native submodule. FEX's AGENTS.md forbids AI-generated
  contributions to FEX. Dock has separate AGENTS.md; its credentials, ownership
  checks, Valve client and original DRM stay intact.
- The repository is public: no tokens, passwords, pairing records, Steam IDs,
  login caches, Send Log codes or personal paths in Git, commit messages or
  diagnostics. No automatic sending of logs. A local diagnostic export uses
  bounded allowlisted fields and explicit sharing.
- New behaviour goes behind a switch that is off by default unless the owner
  decides otherwise. Device/game evidence for this copy remains NOT RUN until a
  build from this repository has been installed and tried. BCD Dock is
  headless; full Steam UI/Big Picture is a separate experiment.
