> CURRENT DELIVERED RESULT — CI44 PASS, 19 October 2026,20m36s.
> https://codemagic.io/app/6ad03ce9a8a969b53f3a4aa9/build/6ad6168f7550aed8109022c2 .
> **Built source: c21eb465c765038e41f16e409bf940ca680d5693.**
> IPA **1086811015 bytes**, SHA-256
> **0e0667fb6b3507a30633bd0512f48a08c27879f33c998539d35f3513f6f19dae**.
> Coordinator verified ZIP,7 arm64 iPhoneOS/ad-hoc Mach-O binaries and19 locked
> resources/cache. All27 Swift checks PASS, including
> `LINUX_STEAM_RECOVERY_BINDING_PASS` and `LINUX_STEAM_RECOVERY_SCOPE_PASS`.
> Owner-only Drive delivery is complete; no personal Drive URL is stored in Git.
> CI/artifact/inspection/delivery facts are coordinator supplied. This docs-only
> update did not rebuild/download the IPA, run CI or access a user disk. Its
> commit differs from the built source and changes no code/config/payload pins.
>
> **Positive12-GiB journal replay/promotion and device acceptance: NOT RUN.**
> Passing host regressions does not establish owner recovery readiness. First
> copy-first recovery requires **24 GiB +512 MiB additional actual free space**;
> original data remains preserved by the recovery design. No owner-disk recovery
> result is claimed. BusyBox corresponding-source completeness remains **OPEN**.
>
> Latest coordinator balance: **4 free minutes, paid OFF**. New full CI runs are
> **BLOCKED by quota**; do not dispatch. Provider23/worker21 configuration is
> unchanged. Earlier quota, failed CI43 and Apple NOT RUN checkpoints below are
> historical and superseded by CI44 only within the verification limits above.

> Historical IPA delivery result: **CI #30 PASS**, built commit
> **7421a2b61215df3fc8fcd74df75348f00574f2fc**.
> https://codemagic.io/app/6ad03ce9a8a969b53f3a4aa9/build/6ad553f47550aed8108ff6f4 .
> Native QEMU/ANGLE, Swift/host checks, full Husk typecheck, app-build, signature
> verification and packaging PASS. **iDeck-Steam-Device-7421a2b6.ipa**:
> **710626140 bytes**, SHA-256
> **5e09a4bf1107090acf8bad208fe5acdbcc11235e34972fe5372b6dfec7dd71da**.
> Downloaded IPA passed ZIP CRC, seven arm64 iPhoneOS Mach-O checks, ad-hoc
> CodeDirectory/no-provisioning checks and all 19 locked Linux/Debian/GUI/Steam
> resource pins. Private owner-only Drive delivery is complete; user has the IPA.
> No personal Drive URL is recorded. Results are supplied by the coordinating
> delivery executor; this docs-only session performed no IPA download or CI run.
> **Built SHA above differs from the following documentation commit's SHA**;
> that docs commit changes neither code nor payload/overlay pins.
> iPhone/device Steam/Big Picture/games **NOT RUN**. Official Valve client download
> occurs at first on-device setup/launch with network consent; client not bundled.
> BusyBox corresponding-source provenance **OPEN**. Earlier pending Apple/IPA/CI
> statements below are historical and superseded by CI #30's build result only.

> Historical payload result, 18 October 2026: final rebuilt payload uploaded by the owner's
> authorized browser is delivered and independently verified. Private Release
> 416567174 has uploaded asset **654660064**, **303667200 bytes**, server and full
> readback SHA-256 **f74e22f44422d5dded7dd23d2a8e9a22a98e2df13edd4620187943529a29c62c**.
> Pinned URL: https://api.github.com/repos/Mi-Yomi/iDeck/releases/assets/654660064 .
> Runtime Steam lock is **ready**; overlay pin refreshed. The old hashes,
> empty-Release and blocked-lock instructions below are historical and superseded.
>
> Independent evidence: `experiments/linux-guest/evidence/steam-device-readback-20261018/`.
> Five files, all 1816 baseline Git blobs, 23 exact source bindings, reconstructed
> bootstrap, complete 12 GiB raw digest/UUID/features, strict read-only fsck and
> bounded Valve/account-path/package checks PASS. Full checkout: 503 tests OK,
> 5 skips; git check-attr, 125 AST checks, 81-file/five-patch source overlay,
> standalone/incremental Xcode staging script and Steam package resource verifier
> PASS, including full expanded staged gzip digest. Raw SHA-256 is
> **ee04c5c66adf4ac1f56b9b36145c9b0ca164d3d09e59ffaf06805fa6815a0626**.
> Existing GUI/Debian assets match their previous metadata; no Release/main,
> secret, bound source or user disk was changed in this integration session.
>
> Use the **post-pinning pushed remote SHA**, not baseline eb743c38, for the manual
> CI inputs below. The workflow already imports `ideck-debian-payload` and its
> exact-repo token fallback uses `IDECK_DEBIAN_PAYLOAD_TOKEN`; no new secrets or
> Steam URL variables are required. Code and fallback/scope tests were checked;
> actual Codemagic group/token access is still untested. No CI was started here.
> Apple/Swift/native IPA/guest/device gates remain NOT RUN. BusyBox corresponding
> source/revision/patch/recipe provenance remains OPEN, as documented separately;
> delivery readiness does not establish complete distribution readiness.

> Fresh-session result, 18 October 2026: uploads.github.com now answers ordinary
> GET with HTTP302 (the previous CONNECT403 is gone). Rebuilt from b01986212fd46f27136ea204c401b8918d49ee02;
> NEW final tar303667200B, SHA25616e29b3a94d9487a244d6047bea7efaee897166459a0e4b482147f6c57625e79.
> Strict fsck/full12GiB gzip hash/tar restore/staging/input and account-path checks PASS;
> 503 Python tests OK,5 skips; exact source slice/five-patch overlay PASS.
> Authorized ordinary gh upload reached uploads.github.com but returned HTTP401
> Bad credentials with the existing GH_TOKEN. Existing GitHub connector confirms
> Release416567174 still has zero assets. No new credentials/security changes.
> Runtime/overlay locks remain unchanged and BLOCKED; no asset/readback/ready pin/CI.
> Local tar is preserved in .work/steam-fresh-rebuild-VudASXFO/candidate/.
> Current evidence: experiments/linux-guest/evidence/steam-device-delivery-fresh-20261018.
> BusyBox matching source/revision/patch/recipe gate remains OPEN; private owner build.
> Apple, guest and device runtime NOT RUN. Earlier f4084e40/CONNECT403 notes below
> describe the old session; do not use that old hash for the rebuilt tar.

> Recheck after the owner reported the allowlist change: at 2026-10-18 16:44:29 UTC,
> one ordinary HTTPS HEAD still failed at CONNECT with 403/envoy in this session.
> No upload retry or alternate route followed. A new published cloud-environment
> session must receive the saved artifact through a supported cloud workspace/
> artifact transfer or retained snapshot; then verify its exact size/hash before
> upload. The tar itself is outside Git; only receipts/source pins are committed.
> BusyBox source/provenance clarification is in BUSYBOX-PROVENANCE-20261018.md.

# Steam payload delivery checkpoint — upload blocked

The owner explicitly authorized uploading the final reviewed replacement payload to a new private Mi-Yomi/iDeck Release and pinning its URL/hash. The reviewed code/candidate was committed and pushed as **`0fffdaf787d10acc86e0caa785dfe27ff81be025`**, with `[skip ci]`. The exact checked candidate supersedes the old ca2a3da payload; no old payload was uploaded.

## Actual result

- Private repo rechecked before and after the action: `private=true`. Existing authorized GitHub credentials were used; no token, credential, secret/group or network/security setting was created or changed.
- New non-latest prerelease created: [ideck-steam-device-v1-20261018](https://github.com/Mi-Yomi/iDeck/releases/tag/ideck-steam-device-v1-20261018), Release ID **416567174**, target/tag commit **`0fffdaf787d10acc86e0caa785dfe27ff81be025`**.
- Upload of `ideck-steam-device-v1.tar` failed: `Post "https://uploads.github.com/repos/Mi-Yomi/iDeck/releases/416567174/assets?...": Forbidden`.
- A separate harmless HEAD confirmed the cause before any GitHub asset response: **`curl: (56) CONNECT tunnel failed, response 403`**, proxy header `server: envoy`. The selected cloud environment rejects CONNECT to `uploads.github.com`. This was not an automatic approval-review rejection or an established GitHub credential-scope failure; API reads and Release creation succeeded. The owner's special retry instruction for an approval rejection caused by missing authorization therefore did not apply. No network restriction was bypassed and no alternate route was attempted.
- Read-only Release API verification after failure: **`assets: []`**. Thus there is no asset API URL, server file size/digest or downloadable file to verify. **`ipa/steam.lock.json` remains blocked**, without a fake ready pin. No CI was started.
- Existing GUI asset 650023557 remains 292065280 bytes, SHA-256 `112bdba6e12ae182fb347e52e7368e26f748bb3dc2bcd77dbd3122fb14dcdedd`; its SHA256SUMS asset is unchanged. Existing Debian asset 647969136 remains 75601920 bytes, SHA-256 `84851a3597901f1e3ef293c1490dc9c8a4a78b286bea8d2a10c330cb1413c558`. Only the newly authorized empty prerelease/tag was created.

## Final local artifact to upload

`/workspace/iDeck/.work/steam-device-payload-20261018-review-final/ideck-steam-device-v1.tar`

- Size: **303667200 bytes**.
- SHA-256: **`f4084e40e854580a8e68a5f199936bf37e4a5f6779086c6b449b940a02325f56`**.
- Candidate lock/provenance: `experiments/linux-guest/evidence/steam-device-review-20261018/steam.lock.candidate.json`, `candidate.json`, `payload-build.json`, `bootstrap.json`, `review-checks.json`.
- Actual asset checks: strict complete read-only fsck before/after new-copy preparation; exact source bindings; unchanged accepted initramfs prefix; exact appended input allowlist; recorded network module GPL declarations; tar/hash restore and standalone Xcode staging; full 12 GiB gzip hash; read-only filesystem lookup and unchanged raw hash. The inherited documented BusyBox source/configuration reconstruction limitation is preserved in the notice; this is not a blanket distribution-licensing acceptance.
- No Valve client binaries or Steam account/session data were sourced into the payload. It is derived from the exact accepted GUI seed plus original iDeck scripts/probe and pinned unchanged Alpine modules. Standard Steam/account paths were absent in read-only inspection. The client/dependencies are downloaded on device only after opt-in, using pinned official HTTPS.
- Python: **503 tests OK, 5 toolchain skips**; AST 173 files PASS. The CI transport check uses real archive bytes with mocked HTTPS/fixture token; it is **not end-to-end Steam**. Apple, new guest boot and iPhone runtime gates remain **NOT RUN**.

## Parent continuation, with no new secrets

Use an existing authorized uploader in an **approved cloud execution environment** where `uploads.github.com` is allowed. Do not use the user's computer or alter this environment's network policy. The owner has authorized this specific final delivery; a new credential is unnecessary. The existing prerelease is empty: do not recreate or overwrite another Release.

1. Upload the exact archive above to tag `ideck-steam-device-v1-20261018`, asset name `ideck-steam-device-v1.tar`, using the existing GitHub mechanism (no `--clobber`).
2. Read the asset metadata; require size 303667200 and server digest `sha256:f4084e40e854580a8e68a5f199936bf37e4a5f6779086c6b449b940a02325f56`. Download through the authenticated asset API to a new file and independently recheck size/SHA-256. Do not pin if upload/readback is incomplete.
3. Copy the committed **review** candidate lock to `ipa/steam.lock.json`, add `payload_url` equal to `https://api.github.com/repos/Mi-Yomi/iDeck/releases/assets/<ACTUAL_ID>`, and update that file's digest in `husk/overlay.lock.json`. No guessed ID, token or signed query URL belongs in Git. Source bindings are unchanged by this pinning-only step; changing bound code requires rebuilding the payload.
4. Ready-fetch now uses the lock URL and existing **`IDECK_DEBIAN_PAYLOAD_TOKEN`** from the already imported **`ideck-debian-payload`** group, scoped to that exact repository asset API and stripped on redirects. Existing Debian/GUI URL/token values stay unchanged; no new URL group, Steam URL variable or Steam token is needed. Optional Steam-specific transport overrides are supported but unnecessary.
5. After fresh remote review, run regressions/staging and commit/push the pinning-only change with `[skip ci]` in the same Steam branch. Confirm exact remote SHA. Then parent may coordinate the sole manual workflow after fresh quota/private/native approvals:

```json
{
  "workflow_id": "ideck-linux-probe-ipa",
  "branch": "codex/steam-arm64-experiment-20261017",
  "inputs": {
    "expected_commit": "<FULL_POST_PINNING_PUSHED_SHA>",
    "free_quota_verified": "true",
    "private_source_verified": "true",
    "native_build_approved": "true"
  }
}
```

These `true` attestations must be earned again for that run. No currently known source SHA is a completed ready-lock pinning SHA; do not launch CI as though the asset were delivered. The mandatory Apple typecheck/runtime regressions, native link/package gate and physical-device checks remain separate from this delivery.
