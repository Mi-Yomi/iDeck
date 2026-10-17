# GUI payload delivery — local rebuild 2026-10-17

The new payload is published in a private prerelease and downloaded back with
matching size/SHA-256 and checksum. GitHub server digest matches too. These bytes
supersede the unavailable cloud seed. [Publication receipt](evidence/gui-local-20261017/github-publication.json).
Repository private status was checked before and after upload. No existing assets,
console URL/token, new credentials or CI configuration were changed.

| Artifact | Value |
| --- | --- |
| Local archive | `E:\Freddy Fazbear\iDeck.work\gui-local-20261017\payload-final\ideck-debian-gui-v1.tar` |
| Bytes | 292065280 |
| SHA-256 | `112bdba6e12ae182fb347e52e7368e26f748bb3dc2bcd77dbd3122fb14dcdedd` |
| Checksum | `E:\Freddy Fazbear\iDeck.work\gui-local-20261017\payload-final\SHA256SUMS` |
| Release | [ideck-debian-gui-v1-local-20261017](https://github.com/Mi-Yomi/iDeck/releases/tag/ideck-debian-gui-v1-local-20261017) |
| Asset API URL | `https://api.github.com/repos/Mi-Yomi/iDeck/releases/assets/650023557` |
| Release source/evidence commit | `65cf483580ff27db57a33c2c53dcf67448861b0b` |
| Remote roundtrip | PASS: exact tar and checksum downloaded into `release-roundtrip` on E: |
| Trust root | [gui.lock.json](ipa/gui.lock.json) |
| Evidence | [local receipt](evidence/gui-local-20261017/receipt.json) |

Offline replay matches the new tar exactly. Restore and isolated full Husk staging
verify all five assets. Large images/tar are not Git objects. The old console Release,
URL, token and payload remain untouched. Upload used existing `gh`, no new token and
no `--clobber`; the unique tag and Release were checked absent before creation.

## Apple handoff (do not dispatch automatically)

Gwen must check the actual pushed HEAD of `codex/linux-guest-feasibility-20261015`,
private `Mi-Yomi/iDeck`, at least120 free macOS minutes and paid billing OFF for this
run. Select workflow `ideck-linux-probe-ipa` (Xcode27.0), with `expected_commit` equal
to that full pushed SHA (including the final documentation/receipt commit, which
adds no payload or runtime changes beyond the Release source commit). Only after preflight set `free_quota_verified=true`,
`private_source_verified=true` and `native_build_approved=true`; dispatch once.

Set a separate `IDECK_GUI_PAYLOAD_URL` to `https://api.github.com/repos/Mi-Yomi/iDeck/releases/assets/650023557`. Put it in the already imported `ideck-debian-payload`
group (Secret). Keep `IDECK_DEBIAN_PAYLOAD_URL` and `IDECK_DEBIAN_PAYLOAD_TOKEN` intact.
When `IDECK_GUI_PAYLOAD_TOKEN` is unset/empty, only the exact approved HTTPS API for
Mi-Yomi/iDeck release assets can reuse the existing Debian token. No new token/group
is required. Never substitute the browser download URL or a local E: path.

The workflow performs the mandatory actual Swift runtime gate, downloads and
verifies the exact new GUI tar via `gui_bundle.py`, restores/stages all five locked
assets, and then attempts native linking/IPA packaging. This work did not run CI.
Apple compilation/link/IPA, GUI on iPhone, Steam and guest GPU acceleration are
NOT RUN. A host GUI PASS does not establish any of those results.
