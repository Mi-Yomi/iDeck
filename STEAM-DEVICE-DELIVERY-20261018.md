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
