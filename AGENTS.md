# Private iDeck-BCD import: static quarantine

This independent private copy preserves BCD/Madeira history and licences. Read
`docs/migration/AUDIT-20261019.md` and `docs/migration/FIRST-SCOPE.md` first.

- The owner has authorized source inspection/import, not execution of third-party
  build/install/test scripts or installation of BCD's IPA. Do not execute those
  or enable/dispatch CI until separately authorized. Current free CI quota is4
  minutes; paid capacity is OFF. Do not create keys or broaden connector grants.
- There are no active workflow files in this import. The upstream workflow is
  retained, unchanged, at `docs/upstream-workflows/build-ipa.yml.disabled` only
  for reading. It contains upstream OTA/signing/upload operations and must not
  be run. The API for Actions settings is not accessible to this integration.
- App/runtime source is preserved exactly for the baseline. Its original
  feedback/log-upload, update and remote-recommendation endpoints are STILL
  present. Before any authorized execution, disable/replace those outbound
  paths, including automatic checks, and verify fail-closed local-only behavior.
  Quarantine is a development restriction, not an implemented network sandbox.
- Do not copy iDeck/Husk source until file-level licences are verified. Prefer
  new small changes through existing BCD interfaces. Do not add Linux ext4,
  QEMU guest or old cache/recovery stacks to this Wine/FEX architecture.
- Preserve all notices and credits. BCD Material retains GPL-3.0-only + its
  exception/additional terms. Mark modifications and dates; preserve the exact
  attribution line. Use our branding before distributing a modified app and
  do not imply upstream endorsement.
- Do not change any native submodule during this initial scope. FEX's AGENTS.md
  forbids AI-generated contributions to FEX. Dock has separate AGENTS.md;
  its credentials, ownership checks, Valve client and original DRM stay intact.
- No tokens, passwords, pairing records, Steam IDs, login caches or personal
  paths in Git or diagnostics. No inherited automatic sending of logs. A local
  diagnostic export must use bounded allowlisted fields and explicit sharing.
- Positive native build/device/game evidence remains NOT RUN for this copy.
  BCD Dock is headless; full Steam UI/Big Picture is a separate experiment.
