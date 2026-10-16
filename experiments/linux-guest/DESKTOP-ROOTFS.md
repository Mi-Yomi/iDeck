# Debian/ext4 preparation — G0/G1 implementation

This is an offline host preparation and storage change. It does not select a
desktop route, mount ext4 in the VM, modify the terminal FAT image, or add Xorg.
The next gates remain in [DESKTOP-MILESTONE.md](DESKTOP-MILESTONE.md).

**2026-10-16 local continuation:** real host Linux/Debian/ext4 two-boot acceptance
now passed. See [the measured result](evidence/local-debian-ext4.json). The seed
rebuilt locally from authenticated pins matches the historical raw/gzip hashes
below exactly. Both system-QEMU boots mounted ext4, executed glibc 2.41 and all
POSIX checks, then unmounted cleanly; read-only fsck exited 0 and the seed was
unchanged. This resolves the host input/boot blocker, not the iPhone Debian gate.
The older cloud results and unavailable-input observations below are historical.

## Local host two-boot runner

`tools/check_debian_ext4_boot.py` adds a host-only acceptance path. Supply a
reviewed seed/profile from the existing builder, a real `desktop_modules.py`
output and an existing system-QEMU executable. It verifies seed and module
inputs, appends a separate test suffix to the unchanged locked probe initramfs,
and attaches only a **new disposable copy** of the seed. The original seed,
terminal FAT disk, iOS entry points and production bundle locks are unchanged.

```sh
python3 tools/check_debian_ext4_boot.py \
  --seed /absolute/seed/rootfs-v1.raw \
  --profile /absolute/seed/desktop-rootfs-profile.json \
  --modules /absolute/verified-module-output \
  --qemu /absolute/qemu-system-aarch64 \
  --out /absolute/new/two-boot-output --e2fsck /absolute/e2fsck
```

On Windows, use Windows paths and system-QEMU, plus `--wsl-distribution archlinux`
and `--e2fsck /usr/bin/e2fsck` to run the final read-only filesystem check in an
already installed WSL distribution. No distribution is installed by the runner.
The source builder needs a POSIX workspace: a plain WSL-mounted NTFS directory
does not support every required file type/mode. In this task, the temporary
build filesystem is backed by a new scratch image on E:, never by the user disk.

Both boots use `virt`, Cortex-A72, 4 CPUs, 1024MiB RAM, TCG/256MiB cache and
`-nic none`. The supervisor loads `virtio_mmio` before `virtio_blk`, loads the
verified ext4 dependency order, mounts the separate ext4 root and executes real
Debian processes through chroot. Each boot requires glibc execution and the
exact configured package manifest. The first creates files using real ownership,
mode, hardlink/symlink, rename and `dd conv=fsync` operations; the second checks
content, inode/link count and metadata again. Execution is also checked as
UID/GID1000. Both require checked sync/unmount and guest poweroff. Finally the
runner requires `e2fsck -fn` exit 0 without changing the test image, and rehashes
the untouched seed. Logs, commands, exit codes, input/output hashes and equivalent
JSON/Markdown reports are retained even on failure. This is not a crash-consistency
test, GUI test, IPA build or iPhone Debian test.

The module resolver retains the complete original metadata. Softdep declarations
are indexed by their normalized owner; strict body/duplicate validation applies
when the hard/soft dependency closure reaches that owner (including builtins).
Unrelated Alpine rows such as `softdep cifs gcm` and repeated ksmbd/btrfs rows
no longer block ext4. Unattributable headers and malformed/duplicate reachable
declarations still fail. The strict whole-file parser remains available.

The seed builder now checks both `dpkg --audit` exit status and empty output.
It also copies the exact verified QEMU helper to its fresh output directory and
passes a relative filename with a controlled cwd to PRoot. This handles spaces
in `E:\Freddy Fazbear`: [PRoot 5.1 parses `-q` by splitting on spaces without
shell quoting](https://github.com/proot-me/proot/blob/v5.1.0/src/cli/proot.c#L67-L136).
The helper hash is rechecked; no wrapper, substitute binary or system install is
introduced. These changes may alter build receipts; compare actual seed hashes
with the historical baseline rather than assigning the old hashes to new outputs.

## Full offline CLI replay, 2026-10-16

The [complete replay receipt](evidence/desktop-rootfs-cli-replay.json) supersedes
the earlier staged-only limit below. **Two fresh complete final builder CLI runs
passed and produced byte-identical raw, gzip, profile, build receipt, package and
ownership manifests.** They used separate output/cache metadata directories and
the same verified package/tool inputs on this host. This is measured same-host
reproducibility, not a universal across-host/date/VM claim.

Current local outputs: `/workspace/ideck-desktop-build/cli-replay-v2/` and
`/workspace/ideck-desktop-build/cli-independent-v2/`. Each contains the raw/gzip,
reviewed seed profile, complete receipt, manifests and private local logs.

| Current measurement | Bytes |
| --- | ---: |
| Raw ext4 logical size | 536,870,912 |
| gzip transfer | 53,918,211 |
| Allocated filesystem blocks | 175,714,304 |
| Free filesystem blocks | 361,156,608 |
| resize2fs -P estimate, not a validated minimum | 168,038,400 |

Raw SHA-256: `a081d86594a0c59e585541ae26fa586468f267767dc081796f51186ea9c01217`.
gzip SHA-256: `97e55ebdf61892848e55a45e4016163e6c55b737afb2c31ccb3939a23e12a747`.
Current raw+gzip+512MiB first-import reserve is **1,127,660,035 bytes**, plus
iOS installation space and optional legacy backup. Images remain local.

The first two full CLI attempts passed every functional gate but differed in
inode timestamps and generated `var/log/alternatives.log` content. The builder
now fixes the directory hash seed, sorts publication paths, pins/audits all four
manifest inode timestamps and nanoseconds after mke2fs, clears only that generated
installation log, and pins the last-change day of all validated locked seed
accounts in primary/backup shadow files. Password fields, other account fields,
package DB, notices and other logs/docs remain intact. This is fresh-seed
preparation; no existing user image is modified.

Independent checks on each final image: actual cmp/hash/gzip stream, read-only
Swift/fsck, all 6,744 manifest UID/GID/mode entries and 26,976 timestamp fields,
all 19 locked rows in each shadow/backup, tool/source/manifest hashes — PASS.
Final regressions: **182 tests PASS** including actual Swift/ARM64 PTy checks.
Disposable ext4 tool roundtrip passed and the exact seed hash stayed unchanged.
`end_to_end_replay_of_final_source:true` now applies to both final receipts;
builder digest is captured at entry and an edit during execution rejects output
profile/receipt. Guest mount, two boots, Apple/device and GUI remain untested.

## Earlier staged host result, 2026-10-16 (historical)

[Full receipt](evidence/desktop-rootfs-host-preparation.json), including exact
raw/gzip hashes, source hashes, staged provenance and independent checks:

| Measurement | Bytes |
| --- | ---: |
| Raw ext4 logical size | 536,870,912 |
| gzip transfer | 53,918,756 |
| Allocated filesystem blocks | 175,718,400 |
| Free filesystem blocks | 361,152,512 |
| resize2fs -P estimate, not a validated minimum | 168,042,496 |

Raw SHA-256: `db0a5b715ff4caf5e326d30d79cce8146baa33246e5fa89c522b62c4f5254f84`.
gzip SHA-256: `7971640d7a295c78a853b1a49fb4abdb6cb222efff67eaf6165d564393004f54`.
Both remain local under the build workspace; no image is committed or published.
The first-import budget raw+gzip+512MiB is **1,127,660,580 bytes**, plus iOS
installation space and an optional legacy backup. This does not prove desktop
package fit; this seed has no Xorg/udev/Openbox/xterm yet.

Actual ARM64 configure/audit/exact90-package manifest and glibc execution passed;
700 ELF files/1,888 DT_NEEDED edges and 6,744 source-manifest UID/GID/mode entries
passed. Independent read-only fsck, raw/gzip hashes, gzip stream digest and Swift
CRC/UUID/features/geometry checks passed. A disposable image copy preserved
content, hardlink/symlink and ownership/mode through separate tool opens and
fsck; the seed hash stayed unchanged. Final regression suite: 174 tests PASS.

**Staged finalization, not a full final-source CLI replay:** the configure stage
had already completed when review found host umask effects. The current shared
helper explicitly fixes public guest directory/config modes. A fresh image was
then generated from that audited tree with the corrected helper/config and all
image checks repeated. Two rejected candidates had an invalid empty
base_features assignment in mke2fs.conf; neither is an accepted filesystem.
The retained local finalizer script hash is in the receipt. A clean end-to-end
replay of the final source and byte-identical rebuild remain unverified.

Host-only memory observations: builder individual VmHWM 790,860KiB; late 1s
sampling saw a maximum aggregate RSS of 241,464KiB and missed earlier aggregate
peaks. Neither measures guest/iOS use. The device baseline remains 1GiB RAM,
4vCPU/256MiB TCG; actual desktop memory/Jetsam fit is unmeasured.

## Locked inputs and replay

`ipa/desktop-rootfs.lock.json` records the authenticated Debian 13/trixie
InRelease, by-hash arm64/amd64 indexes and every package version, architecture,
size and SHA-256. The G0/G1 selection is 90 minbase/POSIX packages: **35,157,424
bytes of .deb downloads**, **155,331,584 bytes of declared Installed-Size**.
Those figures exclude metadata and the separately pinned host tools. Notices
remain in the packages' `/usr/share/doc` trees.

`udev`, `systemd-standalone-sysusers` and `libsystemd-shared` have separate
authenticated deferred pins. Their actual systemd-sysusers postinst hit an
assertion under this PRoot/QEMU preparation environment. They are not reported
as configured, patched to skip scripts, or silently included in a passing image.
Configure and test them inside the real VM before G2.

Use the existing Debian archive keyring; no new signing key or connection is
created. All downloads use official Debian endpoints. Retain the authenticated
cache: the mutable mirror can remove old pool objects, and snapshot access was
blocked here. Replay rechecks signatures, index hashes, package hashes and a
90-day release maximum age (also enforced without Valid-Until). This pin's
release date is 2026-09-12; repin after its freshness window. No expiry bypass.
Exact package inputs and two byte-identical complete raw/gzip rebuilds on this
host are verified. Broader host/date reproducibility remains unproven.

```sh
python3 tools/debian_rootfs.py download --offline --cache /absolute/private/cache \
  --lock ipa/desktop-rootfs.lock.json
python3 tools/debian_rootfs.py build --offline --cache /absolute/private/cache \
  --lock ipa/desktop-rootfs.lock.json --output /absolute/new/output \
  --qemu /absolute/qemu-aarch64-static --qemu-sha256 REVIEWED_HELPER_SHA256
```

Run from this directory. Build requires x86_64 Linux, Python, apt/GPG tooling,
dpkg-deb and a C compiler. The QEMU helper is an explicit independently reviewed
input: the CLI will not discover, download or trust a helper by filename. Output
must not exist; failures preserve local logs and never resume or replace an image.
Payload output stays local until size/hash/checks are reviewed.
These replay commands require the already authenticated retained cache.
`--offline` rehashes every required cached input and fails before fetching or
creating a download temporary on a miss/corruption. It cannot create a new lock;
signature/freshness checks still run. It restricts builder fetches, and does not
claim network namespace isolation for package scripts.

The builder extracts pinned official host tools locally. It runs actual ARM64
glibc and package maintainer scripts using QEMU user-mode/PRoot, then requires
strict final `dpkg --configure -a`, empty audit and exact installed package
identities. The child-only compatibility filter forces old PRoot's supported
stat/access fallbacks and EPERM ownership handling. It grants no privileges and
changes no host mount, networking or system security settings. PRoot fake root
is preparation, not a VM test or a security boundary.

Actual ext4 ownership is applied from authenticated archive metadata,
statoverrides and explicit generated-user metadata. Every manifest entry's
persisted UID/GID and source mode is audited; mke2fs-created internal inodes
are outside that manifest. Symlink targets need the separate POSIX gate.
`e2fsck -fn`, ELF AArch64 interpreter/DT_NEEDED closure and actual glibc execution
must pass before a seed profile/receipt is emitted. `/home/ideck` is UID/GID1000,
mode0700; root and user passwords are locked. No guest APT source is enabled.

The optional `tools/check_ext4_roundtrip.py` takes explicit `--image`, fresh
`--output`, `--debugfs`, `--e2fsck` and `--library-path` paths. It writes only a
disposable copy, then reopens it to check content, hardlink/symlink, UID/GID and
mode, runs read-only fsck and rehashes the unchanged seed. Its receipt is an
unmounted ext4 tool check; Linux syscalls, rename, fsync and two guest boots are
not proven by it.

## Storage contract

`LinuxDesktopDisk` and `LinuxDesktopProfile` are separate from the existing FAT
implementation. They use `rootfs-v1.raw`, exact size/UUID/4KiB geometry and the
explicit ext4 features 0x2c/0xc2/0x443. Superblock CRC32C, clean state, journal,
recovery and metadata-error checks reject incompatible/damaged headers. This is
a superblock contract, not a substitute for fsck or inode-tree validation.

Provisioning streams the exact reviewed raw seed SHA-256 through a locked
temporary descriptor and publishes without replacing an existing destination.
The same locked descriptor survives publication. Directory-relative operations
and inode checks reject directory/temp replacement; cleanup never removes an
unknown replacement. Reopen verifies mutable filesystem identity/contract,
not the original seed digest, so legitimate file/package changes survive.

There is no user-facing gzip importer or runtime route yet. The primitive
reserves raw size +32MiB before copying an already materialized raw seed. A future
importer must enforce the broader raw+compressed+512MiB installation budget in
the milestone, stream bounded decompression, and use a reviewed app profile
rather than letting an imported image supply its own trusted digest. No
crash/power-loss atomicity or directory-fsync guarantee is claimed here.

Linux host tests execute the actual Swift disk helper. Apple typecheck and
CryptoKit profile tests are wired into the existing parent-controlled CI;
they have not run for this change. Existing terminal/probe/JIT and userdata
paths remain unchanged. No QEMU argument accepts the new disk yet.

## Earlier same-kernel ext4 blocker (historical)

`ipa/desktop-kernel-source.lock.json` records the original kernel/archive hashes
and official aports config observation `CONFIG_EXT4_FS=m`. This is source config
evidence, not an IKCONFIG extraction or successful mount. The committed
initramfs lacks the ext4 module closure. The original 431,008,592-byte Alpine
netboot archive was unavailable here (HTTP403 at the official CDN and checked
official mirrors); no guessed closure or substitute kernel is accepted.

The minimum missing external payload is **`boot/modloop-virt`**, taken unchanged
from `alpine-netboot-3.24.1-aarch64.tar.gz`, for kernel `6.18.35-0-virt`:

SHA-256 **`f969d12c8e23b486c8df651f04a4a9767f32fee16aed385c23462c31ea6cb47b`**.

Its actual byte size is unknown here. This is the historical committed pin in
`evidence/guest-profile.json` and retained bundle profile; no newly downloaded
modloop was measured. A local-only search of `/workspace`, `/tmp`, artifact
archive member lists and Git payload paths found no matching input. No other
executor, proxy, mirror attempt or network request was used for this follow-up.
The complete 431,008,592-byte netboot archive is also accepted, but is not needed
if the owner already has its exact modloop member saved.

Given that local file and a trusted unsquashfs executable:

```sh
python3 tools/desktop_modules.py --modloop /absolute/modloop-virt \
  --unsquashfs /absolute/unsquashfs --out /absolute/new/module-output
```

The standalone mode snapshots a bounded regular file without following a leaf
symlink, then requires the exact pinned digest. It explicitly reports original
archive/kernel bytes as unverified and keeps the expected kernel pin separate.
Alternatively, provide the original complete pinned archive:

```sh
python3 tools/desktop_modules.py --archive /absolute/alpine-netboot-3.24.1-aarch64.tar.gz \
  --unsquashfs /absolute/unsquashfs --out /absolute/new/module-output
```

Archive mode checks archive/kernel/modloop hashes. Both modes resolve modules.dep
plus softdeps/builtins, verify AArch64 ELF .modinfo/vermagic and signature-container
structure, then emits load order and per-module size/hash. Signature structure
does not claim public-key certificate verification; kernel acceptance and ext4
mount need the actual VM. Exact closure/bytes remain unknown until that input is
available. Two-boot POSIX persistence, Xorg/Openbox/xterm and Apple/device memory
fit remain gated; the 1GiB RAM/4vCPU/256MiB TCG baseline is unchanged.
