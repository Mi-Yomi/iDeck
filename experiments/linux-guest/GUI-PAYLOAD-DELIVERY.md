# GUI v1 private Release handoff — 2026-10-17

The payload is sealed and validated locally. It has **not** been uploaded to a
Release. The current executor's existing `gh` access rejects both GraphQL and
REST reads with `Forbidden`. No token was created, read, printed or changed.
The connected GitHub tools expose no Release-asset upload action here.

| Artifact | Value |
| --- | --- |
| Cloud archive | `/workspace/iDeck/.work/gui-20261017/sealed-gui/ideck-debian-gui-v1.tar` |
| Bytes | 292034560 |
| SHA-256 | `4b4b0bb1f75d5b662a8c1d866f482329449ee4d52d181e585ef4964a3540bbdb` |
| Checksum file | `/workspace/iDeck/.work/gui-20261017/sealed-gui/SHA256SUMS` |
| Reviewed trust root | [ipa/gui.lock.json](ipa/gui.lock.json) |
| GUI evidence | [acceptance.json](evidence/gui-alpine-20261017/acceptance.json) |
| Replay/restore/staging | [payload-validation.json](evidence/gui-alpine-20261017/payload-validation.json) |

An offline rebuild produces the identical tar hash. The archive is an
uncompressed, flat USTAR containing five locked transport members: the root
image is gzip compressed inside it. Restoring it yields five verified app
assets, including the 1.25GiB raw image. It exceeds Drive's observed256MiB
raw-download limit; retain it as a private Release asset rather than a Drive
raw-export dependency. Large root images and this tar are not Git objects.

Parent's required step is to transfer this exact archive and checksum file from
the retained cloud workspace to a host with **existing approved private Release
upload access**, then upload to the parent-approved private Release. Verify the
SHA-256 before and after transfer. Do not create credentials or overwrite an
existing asset. With that approved host's existing `gh` setup:

```sh
# Run in the directory containing the validated archive and SHA256SUMS.
sha256sum -c SHA256SUMS
# Set IDECK_GUI_RELEASE_TAG to the actual parent-approved private Release tag.
gh release upload "$IDECK_GUI_RELEASE_TAG" \
  ideck-debian-gui-v1.tar SHA256SUMS --repo Mi-Yomi/iDeck
```

The command deliberately omits `--clobber`. If an asset of the same name
exists, stop and resolve the destination with parent rather than replacing it.
Download the uploaded asset into a new directory through that host's existing
approved access, then verify its exact bytes/hash again.

After actual upload, obtain the real numeric asset ID from the Release and
configure the existing private CI download route:

```text
IDECK_GUI_PAYLOAD_URL=https://api.github.com/repos/Mi-Yomi/iDeck/releases/assets/<actual-uploaded-asset-id>
```

`IDECK_GUI_PAYLOAD_TOKEN` is an optional override. When it is unset/empty,
only for this exact approved Mi-Yomi/iDeck GitHub asset API, the downloader reuses
`IDECK_DEBIAN_PAYLOAD_TOKEN` from the already imported `ideck-debian-payload` CI
group. No new secret/group is needed. Other transports never read or receive
this fallback. The GUI URL remains separate; Debian URL/token values are not
replaced. This executor does not read or configure live credentials. Do not
substitute an invented ID, public URL, refreshed payload hash or source image.
`gui_bundle.py fetch` enforces the exact committed size/hash, HTTPS, the allowed
repository asset API/token scope and safe redirects without logging credentials
or signed URLs. The separate accepted Debian console URL/lock remains unchanged.

Before the single Apple build, parent must review the source/ready GUI lock,
confirm the Release download, and perform fresh free-quota/paid-OFF preflight.
CI was not run here. Apple/full native link/IPA/iPhone GUI remain NOT RUN.
