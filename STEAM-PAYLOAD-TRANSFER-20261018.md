# Final payload preservation / fresh-session rebuild

The requested Library save was attempted through the current Library skill's required prepared-upload helper for a 303667200-byte local file. It stopped before upload preparation completed: `library upload failed: hosted apps tools/list request failed: network`. No Library ID or successful create/finalize result was returned. **`library_file_id` is unavailable; the file-size limit was not evaluated.** No direct-write substitute, temporary host, homemade server, alternate GitHub upload route or deletion was used.

The exact original file is still preserved:

- Filename: `ideck-steam-device-v1.tar`.
- Local path: `/workspace/iDeck/.work/steam-device-payload-20261018-review-final/ideck-steam-device-v1.tar`.
- Size: **303667200 bytes**.
- SHA-256: **`f4084e40e854580a8e68a5f199936bf37e4a5f6779086c6b449b940a02325f56`**.
- Source, receipts and candidate lock: `evidence/steam-device-review-20261018`.

Keep this old workspace until a supported cloud transfer/snapshot is confirmed. The tar is outside Git and is not present in the empty prerelease. The original f4084e40 bytes cannot be recovered by cloning Git alone.

## Rebuild from the reviewed current remote

This is the reproducible **procedure**, not a guarantee of byte-identical f4084e40 output. The existing ext4 preparation writes check/growth timestamps. A fresh candidate can therefore have a different raw/archive SHA-256 even with the same reviewed code and inputs. The script reports its new digest; revalidate and update delivery notes/pins rather than substituting the previous hash.

Use a fresh approved **Linux amd64 cloud** session with Python 3.11+, existing authorized `gh`, `dpkg-deb`, and at least **20 GiB free**. It installs no system package and changes no secrets/security/network settings. It extracts exact pinned build tools and their complete shared-library closure into a new private scratch directory, then uses the existing `gui_host_tools` pinned-loader mechanism. The full preparation must still pass strict fsck and expanded gzip verification.

From an existing clean iDeck clone (the saved environment may initially open main):

```bash
cd /workspace/iDeck
[ -z "$(git status --porcelain)" ] || exit 1
steam_branch=codex/steam-arm64-experiment-20261017
git fetch origin "refs/heads/$steam_branch:refs/remotes/origin/$steam_branch"
if git show-ref --verify --quiet "refs/heads/$steam_branch"; then
  git switch "$steam_branch"
else
  git switch -c "$steam_branch" "refs/remotes/origin/$steam_branch"
fi
git merge --ff-only "refs/remotes/origin/$steam_branch"
bash experiments/linux-guest/tools/rebuild_steam_candidate.sh
```

No reset, force, other branch update, existing disk edit, upload or CI occurs. The script requires HEAD to match the fetched remote and checks all bound source hashes against the committed reviewed candidate before downloading. It expects the current blocked delivery state; source/contract changes require review, not bypassing these checks. On success, its final JSON identifies the new `.work/steam-fresh-rebuild-*/candidate` directory, tar/hash and candidate lock. Save `host-inputs.json`, `candidate/result.json`, `candidate/bootstrap/bootstrap.json`, fsck logs and the candidate lock alongside it.

## Required external inputs

1. **Existing private GUI asset**, unchanged and independently rechecked during this task:
   - Release `ideck-debian-gui-v1-local-20261017` in private `Mi-Yomi/iDeck`.
   - Asset ID **650023557**, filename `ideck-debian-gui-v1.tar`.
   - Size **292065280**, SHA-256 **`112bdba6e12ae182fb347e52e7368e26f748bb3dc2bcd77dbd3122fb14dcdedd`**.
   - API URL `https://api.github.com/repos/Mi-Yomi/iDeck/releases/assets/650023557`; the script streams it using existing `gh` auth and verifies/restores through the unchanged `ipa/gui.lock.json`. Do not create a token if access is unavailable.
2. **Exact Alpine modloop**, already in Git:
   `vendor/alpine-3.24.1-aarch64/modloop-virt`, SHA-256 `f969d12c8e23b486c8df651f04a4a9767f32fee16aed385c23462c31ea6cb47b`. Kernel/bootstrap/clean GUI seed come from the verified GUI asset. No host qcow2, E: disk or local account state is required.
3. **15 exact Debian amd64 host packages**, filenames/versions/sizes/SHA-256 in
   `evidence/steam-device-review-20261018/rebuild-host-tool-pins.json`. These are the existing e2fsprogs 1.47.2-3+b12 tool closure, squashfs-tools 4.6.1-1, and pinned libc/blkid/uuid/lzma/lz4/zstd/zlib/xxhash libraries. Original pins come from the existing host/GUI locks; the three additional library pins were derived from the exact authenticated amd64 index already bound in `ipa/steam-dependencies.lock.json`, with its compressed hash rechecked locally. The script fetches only the fixed official `https://deb.debian.org/debian/<pool filename>` URLs and verifies every size/digest before `dpkg-deb -x`; no maintainer scripts or system install run.

The extracted 15-package closure and all four tool launchers were actually smoke-checked here: e2fsck/tune2fs/resize2fs **1.47.2**, unsquashfs **4.6.1**, with the matching pinned loader/library path. The fresh-session script passed Bash syntax and three inline Python AST checks. The complete fresh rebuild script was **not** rerun in this old session; the underlying payload builder and integrity gates were already exercised for the preserved candidate.

The existing Debian console asset **647969136** is needed later by the full IPA workflow, not by this seed rebuild. It remains in `ideck-debian-console-v1`, 75601920 bytes, SHA-256 `84851a3597901f1e3ef293c1490dc9c8a4a78b286bea8d2a10c330cb1413c558`.

BusyBox matching-source provenance remains open as described in `BUSYBOX-PROVENANCE-20261018.md`; rebuilding the same binary does not close it. No Valve/account bytes are introduced. Upload/pinning waits for an approved cloud environment where the actual GitHub upload endpoint is allowed; no CI should run as if an asset already existed.
