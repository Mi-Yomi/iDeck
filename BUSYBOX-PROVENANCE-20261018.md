# BusyBox provenance clarification — no payload change

The final Steam payload and all delivery receipts remain preserved. No upload retry, network probe, CI, ready pinning or accepted-payload edit was performed for this clarification.

## What is established

The unchanged accepted GUI initramfs `f8d8f4cc92f3f8d49e68adb90ab50d901c54f115d6134ae7030526fdee3de8b4` contains `/usr/bin/busybox`:

| Item | Verified value |
| --- | --- |
| Binary size | 919304 bytes |
| Binary SHA-256 | `97d52efa149563c8d886e3670e2496d4140d3c54138017afd3a105e0397fae2e` |
| Embedded version/banner | `BusyBox v1.37.0 (2026-01-10 15:38:28 UTC)` |
| Licence identification | BusyBox GPLv2-only; original shared Alpine notice preserved |
| GPLv2 text | Present in the Debian seed at `/usr/share/common-licenses/GPL-2` |
| Embedded configuration snapshot | 30368 bytes, 1084 CONFIG/set-or-unset lines |
| Configuration SHA-256 | `65290dba19ad49da626a177ba59bdc8b08d5b192508ace15178bb01e264bc0bf` |

The configuration was recovered statically from the binary's embedded bzip2 block at offset 825704. It enables `CONFIG_BBCONFIG=y` and `CONFIG_FEATURE_COMPRESS_BBCONFIG=y`. No ARM executable, emulator, guest or applet was launched. The original embedded bytes, hash and extraction metadata are under `evidence/steam-device-review-20261018/busybox-*`. The upstream build-prefix path in the config belongs to the distro binary, not the owner's computer.

This improves the earlier receipt: configuration information is now available. It does **not** establish which external source/package build produced this binary. The pruned initramfs has Alpine keys/tools but no retained BusyBox `.PKGINFO`/installed-package record tying this ELF to a package revision. An embedded version/banner is not that link.

## What remains missing

- The exact Alpine BusyBox package revision (`1.37.0-rN`), authenticated package identity and a matching package ELF digest.
- The corresponding ap­orts commit/`APKBUILD`, vendor patch set (or verified proof there were no modifications), and compilation/installation scripts for that binary.
- A fetched and digest-verified complete BusyBox source archive/tree corresponding to those inputs, including original file-level notices/licence material.
- A demonstrated corresponding-source delivery route or applicable valid upstream source offer. The generic BusyBox/Alpine home-page links in the old notice are not proof of these materials.

The upstream BusyBox version, licence name and GPLv2 licence text are **not** the missing pieces. The recovered config resolves one part of the earlier limitation; matching source/patch/recipe provenance remains unresolved.

## Distribution consequence and resolution

For distribution of binary copies to other recipients, this is an **open corresponding-source readiness gate**: the existing evidence cannot demonstrate GPLv2 source provision. BusyBox's own [licensing guidance](https://www.busybox.net/license.html) describes exact matching source/config/build scripts and the GPLv2 section-3 source/offer routes. A private repository flag or an unfulfillable written promise does not supply those materials. This is a technical release-readiness assessment, not a determination that storing the owner's private test artifact itself is unlawful.

The existing verified kernel source lock covers Linux modules, not BusyBox. The retained Husk Swift/header source slice, iDeck scripts, Debian package locks and netboot/binary hashes also do not contain the missing BusyBox source tree. Therefore this cannot currently be closed using only the already verified source archives in this workspace. The configuration can be supplied from this new static recovery; the rest needs a separately verified matching upstream/distro source set.

A concrete resolution is to identify an authenticated Alpine `.apk` whose BusyBox ELF matches the binary digest above, bind its package revision to the appropriate ap­orts recipe/patches and source digests, and provide the complete corresponding source and build/config material through an applicable GPLv2 route before distribution acceptance. This can be added alongside the binary as source/provenance material without changing the accepted GUI/Terminal/Debian binaries or silently replacing BusyBox. A validated, applicable upstream written offer would need its own evidence; none was assumed or invented here.

## Preserved delivery state

Final tar remains **303667200 bytes**, SHA-256 **`f4084e40e854580a8e68a5f199936bf37e4a5f6779086c6b449b940a02325f56`**. The new prerelease still has no uploaded asset, and `ipa/steam.lock.json` remains blocked. The CONNECT403 network blocker and exact delivery continuation remain in `STEAM-DEVICE-DELIVERY-20261018.md`. Waiting for confirmation of the allowlist change; no upload attempt was repeated.
