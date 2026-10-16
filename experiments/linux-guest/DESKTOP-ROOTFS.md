# Debian/ext4 preparation — G0/G1 implementation

This is an offline host preparation and storage change. It does not select a
desktop route, mount ext4 in the VM, modify the terminal FAT image, or add Xorg.
The next gates remain in [DESKTOP-MILESTONE.md](DESKTOP-MILESTONE.md).

## Actual host result, 2026-10-16

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
Exact package inputs are reproducible; byte-identical raw rebuild is unproven.

```sh
python3 tools/debian_rootfs.py download --cache /absolute/private/cache \
  --lock ipa/desktop-rootfs.lock.json
python3 tools/debian_rootfs.py build --cache /absolute/private/cache \
  --lock ipa/desktop-rootfs.lock.json --output /absolute/new/output \
  --qemu /absolute/qemu-aarch64-static --qemu-sha256 REVIEWED_HELPER_SHA256
```

Run from this directory. Build requires x86_64 Linux, Python, apt/GPG tooling,
dpkg-deb and a C compiler. The QEMU helper is an explicit independently reviewed
input: the CLI will not discover, download or trust a helper by filename. Output
must not exist; failures preserve local logs and never resume or replace an image.
Payload output stays local until size/hash/checks are reviewed.

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

## Same-kernel ext4 blocker

`ipa/desktop-kernel-source.lock.json` records the original kernel/archive hashes
and official aports config observation `CONFIG_EXT4_FS=m`. This is source config
evidence, not an IKCONFIG extraction or successful mount. The committed
initramfs lacks the ext4 module closure. The original 431,008,592-byte Alpine
netboot archive was unavailable here (HTTP403 at the official CDN and checked
official mirrors); no guessed closure or substitute kernel is accepted.

Given that already downloaded, exact archive and a trusted unsquashfs executable:

```sh
python3 tools/desktop_modules.py --archive /absolute/alpine-netboot-3.24.1-aarch64.tar.gz \
  --unsquashfs /absolute/unsquashfs --out /absolute/new/module-output
```

This offline tool checks archive/kernel/modloop hashes, resolves modules.dep plus
softdeps/builtins, verifies AArch64 ELF .modinfo/vermagic and signature-container
structure, then emits load order and per-module size/hash. Signature structure
does not claim public-key certificate verification; kernel acceptance and ext4
mount need the actual VM. Exact closure/bytes remain unknown until that input is
available. Two-boot POSIX persistence, Xorg/Openbox/xterm and Apple/device memory
fit remain gated; the 1GiB RAM/4vCPU/256MiB TCG baseline is unchanged.
