# Debian ARM64 console — handoff for Apple review

Continues `3bcb4811726c690a988b95c828c11661090869ca` on
`codex/linux-guest-feasibility-20261015`. This stage adds a separate Debian
console route; it does not add a GUI or Steam. **Host success is not an iPhone
test. Swift/Apple compilation, native link, IPA and Debian device execution
are NOT RUN in this Windows task. Codemagic was not started.**

## App and storage contract

- The chooser retains Terminal and Probe and adds Debian ARM64. Debian uses
  the existing JIT setup, pairing, SideStore helper, real `qemu_init` /
  `qemu_main_loop`, serial socket and separate supervisor control socket.
  No substitute runtime or fabricated Apple types are used.
- Debian stores its mutable root at `Documents/iDeckDebian/rootfs-v1.raw`.
  Terminal continues using its existing `Documents/iDeckLinux` FAT16 data.
  The immutable app-bundled seed is opened read-only and is never a QEMU drive.
- First import streams the seed through SHA-256 into a locked, mode-0600
  `.rootfs-import-v1.partial`. It requires 512 MiB plus 32 MiB free reserve,
  validates ext4, fsyncs, then publishes with no-clobber `linkat`. A failed
  copy is not published. An interrupted partial can only be restarted after
  acquiring its lock; other active importers cannot remove it. The narrow
  crash window between publication and removal of the reserved hardlink is
  recognized only for the same locked, validated inode.
- An existing disk always wins. Reopen checks identity, lock, size, geometry,
  UUID, feature bits, superblock checksum and clean/recovery state; it does
  **not** compare a legitimately modified disk to the original seed SHA.
  `needsRecovery` displays an offline ext4 recovery error. No automatic
  format, reseed, fsck, repair or existing-user-disk replacement occurs.
- The production initramfs retains Alpine merged-/usr symlinks. It loads
  `virtio_mmio`, `virtio_blk`, then exact `crc16`, `mbcache`, `jbd2`, `ext4`
  modules for `6.18.35-0-virt`. PID 1 stays in Alpine; a getty-controlled Debian
  `/bin/sh -i` runs through chroot, with `/proc`, `/sys`, `/dev` bound and
  `/run` in tmpfs. `/root` and the rest of the Debian ext4 root persist.
- Debian dash inherits ignored INT/QUIT from asynchronous getty startup.
  `env --default-signal=INT,QUIT` resets them before entering the shell.
  This is required for the tested Ctrl-C behavior, not a cosmetic setting.
- Stop uses `org.ideck.control`, independently of serial shell text. PID 1
  terminates guest writers, syncs, unmounts nested mounts and ext4, syncs again,
  reports clean unmount, then powers off. There is no automatic test poweroff.
  Shell `exit` uses the same shutdown path.
- **A QEMU loop return is not proof that its block backend closed.** After
  unmount + loop return + host fsync, the app may report the observed orderly
  guest stop, but still retains its exclusive disk owner until app exit.
  No `qemu_cleanup`, unlock or second VM initialization is attempted. A Stop
  timeout or failure cannot later become a clean result. Reopen the app for
  another session. The existing process-wide mode selection and additional
  Terminal/Debian/Probe guards prevent two VMs in the same process.
- Debian exports `result.json`, `result.md`, and bounded `linux-serial.log`.
  Reports include import stage, static storage failure, seed/initramfs hashes,
  independent control-channel evidence, loop return, host sync and retained
  ownership. Existing durable startup journals and native/crash-log exports
  remain available before JIT or disk access. Markdown keeps its allowlist;
  no pairing/token data is added.

## Exact payload (outside Git)

Final directory:
`E:\Freddy Fazbear\iDeck.work\debian-console-20261016\payload-final`

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `ideck-debian-console-v1.tar` | 75601920 | `84851a3597901f1e3ef293c1490dc9c8a4a78b286bea8d2a10c330cb1413c558` |
| `bundle/vmlinuz-virt` | 10351104 | `47970e0ee0478fe5c60824a89f162d5a353fa29466e5d3bddb0f9c506f1ed756` |
| `bundle/initramfs-debian.gz` | 11317380 | `e647f9ff80a3c93333f607a6961505103164bcc17c935eb4d0a06d253f36aa7d` |
| `bundle/rootfs-v1.raw` | 536870912 | `a081d86594a0c59e585541ae26fa586468f267767dc081796f51186ea9c01217` |
| transport member `rootfs-v1.raw.gz` | 53918211 | `97e55ebdf61892848e55a45e4016163e6c55b737afb2c31ccb3939a23e12a747` |

The tar carries the compressed seed, exact kernel/initramfs, both profiles and
license notes. [debian.lock.json](ipa/debian.lock.json) pins every transport and
app-bundle member. A second independent invocation of the production `prepare`
command reproduced the complete final tar and all bundle hashes at
`payload-final-reproduced`. `payload-final-restored` was restored from the tar
by the same bounded helper used in CI and was used for the final host test.
Earlier `payload-build` / `payload-reproduced` directories are historical and
must not be uploaded in place of the final payload.

Reproduce locally without installing anything (existing Python):

```powershell
python experiments/linux-guest/tools/debian_bundle.py prepare `
  'E:\Freddy Fazbear\iDeck.work\local-debian-ext4\seed' `
  experiments/linux-guest/ipa/debian.lock.json `
  --modules 'E:\Freddy Fazbear\iDeck.work\local-debian-ext4\modules' `
  --destination 'E:\Freddy Fazbear\iDeck.work\debian-console-rebuild-new'
```

The output must be new. The helper verifies the reference seed/gzip/profile,
module manifest and each module/dependency file, original guest archive,
production scripts, and all resulting files against committed locks.

## Delivery blocker and precise Apple CI steps

**BLOCKER: the final 75,601,920-byte tar has not been uploaded to a CI-readable
private endpoint. No asset ID, token, release or Codemagic secret group was
created by this task. E: is not accessible to Codemagic.**

Concrete delivery path: attach the exact final tar as a Release asset of the
existing **private** `Mi-Yomi/iDeck` repository, then download its bytes through
the GitHub asset API. This is a separate owner/reviewer step after code review;
do not place the tar, raw disk, token or signed URL in Git. For example, with
an already available authenticated `gh` (do not install it merely for this):

```powershell
gh release create ideck-debian-console-v1 `
  'E:\Freddy Fazbear\iDeck.work\debian-console-20261016\payload-final\ideck-debian-console-v1.tar' `
  --repo Mi-Yomi/iDeck --target codex/linux-guest-feasibility-20261015 `
  --prerelease --title 'iDeck Debian console payload v1' `
  --notes 'Exact private CI payload; SHA-256 84851a3597901f1e3ef293c1490dc9c8a4a78b286bea8d2a10c330cb1413c558. No iPhone verification.'
gh api repos/Mi-Yomi/iDeck/releases/tags/ideck-debian-console-v1 `
  --jq '.assets[] | {name, url, size}'
```

If that tag already exists, inspect it first; do not replace someone else's
asset. Upload through the GitHub UI is also sufficient. Capture the returned
**asset API URL**, not a release-page URL:
`https://api.github.com/repos/Mi-Yomi/iDeck/releases/assets/ACTUAL_ASSET_ID`.
No actual ID is currently known; the example is not a working download URL.

1. In Codemagic application environment variables, create the group
   `ideck-debian-payload` already referenced by the IPA workflow. Add secret
   `IDECK_DEBIAN_PAYLOAD_URL` containing the actual asset API URL and secret
   `IDECK_DEBIAN_PAYLOAD_TOKEN` containing a token limited to read access to
   this private repository's Contents. Do not paste the token into this repo,
   build inputs, command arguments or reports. The downloader restricts token
   use to this exact repo's GitHub asset API and strips it on HTTPS redirects.
   An existing private signed HTTPS object URL is an alternative; leave the
   token unset for that transport.
2. After review, select branch `codex/linux-guest-feasibility-20261015`, workflow
   `ideck-linux-guest-profile-check`, and set `expected_commit` to the **full
   pushed SHA containing this handoff**. Perform the existing quota/privacy
   checks for this actual run before setting `free_quota_verified=true` and
   `private_source_verified=true`. It requires no Debian download.
3. The compiler workflow must finish successfully, including actual macOS
   executables for `LINUX_DESKTOP_DISK_CHECKS_PASS`,
   `LINUX_DESKTOP_PROFILE_CHECKS_PASS`, and
   **`LINUX_CONSOLE_RUNTIME_REGRESSION_PASS`**. `result.json` must report
   `swift_runtime_regression: "PASS"` and both upstream/integrated Husk
   typechecks. A parse-only result or skipped Swift test is insufficient.
4. Then, when separately authorized, select `ideck-linux-probe-ipa`, same full
   SHA and branch. Retain its existing 120-minute quota/private-source checks
   and `native_build_approved` confirmation. This task does not authorize or
   dispatch that run. The script repeats the mandatory Swift gate, fetches
   the locked tar, restores and verifies every byte **before** native tool /
   dependency setup, stages `guests/ideck-debian`, and builds the real runtime.
5. Xcode stages `Husk.app/iDeckDebian`; packaging rechecks every exact resource
   and rejects a missing/corrupt seed, kernel, initramfs, profile or license.
   The normal artifact remains `.work/linux-ipa/iDeck-Linux-Probe.ipa`, with
   three Linux routes. It needs owner sideload signing as before; existing
   pairing/JIT/SideStore paths are retained. The app includes the raw seed and
   additionally needs at least 544 MiB free for first import, beyond install
   space. No automatic CI trigger was added.

The asset API supports binary downloads through `Accept: application/octet-stream`
and may return bytes or an HTTPS redirect; read-only Contents permissions are
documented by [GitHub](https://docs.github.com/en/rest/releases/assets#get-a-release-asset).
Secret groups are selected through `environment.groups` as described in
[Codemagic's documentation](https://docs.codemagic.io/yaml-basic-configuration/configuring-environment-variables/).

## Validation and limits

- Final production host run: `debian-console-20261016/host-006`. Two offline
  QEMU 11.1.0 system VMs, Cortex-A72 / 4 CPUs / 1024 MiB / TCG 256 MiB.
  Debian arm64, glibc 2.41, 90-package database and empty successful package
  audit. Serial command input and real Ctrl-C interrupt pass on both boots.
  An idle console stays alive. Serial marker text cannot acknowledge Stop.
- Boot 1: control-channel Stop; boot 2: interactive shell exit. Both guests
  unmounted ext4, powered off, and QEMU exited 0. Contents, permissions,
  UID/GID, renamed file, symlink, hardlink/inode/link count persisted.
  Read-only `e2fsck -fn` returned 0 without changing the disposable disk.
  The original reference seed stayed unchanged. No existing userdata opened.
- Python regression suite includes malformed transport/hash/size, truncated
  decompression contract, low-space, symlink/ancestor and private transport
  guards, all previous Terminal/Probe/JIT/diagnostic checks, and overlay
  application against real pinned Husk sources. Exact run counts and logs
  are in the committed evidence receipt.
- **Swift runtime/storage executable tests: NOT RUN locally.** Added mandatory
  Apple cases exercise actual storage IO/locks, real child-process interrupted
  import, retry, publication interruption, same-process and other-process
  contention, insufficient space, bad seed hash, dirty disk preservation,
  Debian argv/owned disk, and production Stop decisions under reordered events,
  timeout/failure/late acknowledgments and loop return alone. These do not
  emulate QEMU and do not replace testing the installed app on iPhone.
- Final host QEMU is 11.1.0, whereas the app links pinned Husk QEMU
  10.0.12-utm. Host process exit closes its backend; the embedded iOS loop
  return is deliberately **not** treated as equivalent. Safe backend cleanup,
  in-process restart, iPhone Debian operation, GUI and Steam are not claimed.
- Old host attempts remain locally: `host-001` hit a harness TCP-reset handling
  error after guest poweroff; `host-003`–`host-005` exposed/debugged inherited
  ignored SIGINT. They are not passing acceptance evidence. `host-006` uses
  the corrected final payload and is the reported acceptance result.

Before declaring Debian on iPhone verified: review this commit, run the Apple
gates, install the resulting IPA, import the seed, enter commands, create a
file, Stop, **exit the app**, relaunch and verify that file. Also verify the
recovery message on a disposable dirty copy; never damage or reseed the
owner's real disk for a test.
