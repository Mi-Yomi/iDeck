# Stable cache block-device identity checks

Baseline `460d5f260089e0c9f0a62d0049a6ee04b9e78468`.
Full Python log:599 tests OK,5 SKIP, real Git checkout. New cache regressions use
actual temporary sysfs-shaped files and canonical cache bytes; fstat block type
and ioctl results are modeled, not real kernel block devices. Both vda/vdb orders,
serial identity failures, descriptor closure, readonly and size checks are covered.
The actual Swift cache-argv fixture is included in the mandatory Apple profile
checks; its synthetic canonical archive is independently validated in Python.

`validation.log` and `validate.py` record full pinned source/overlay restoration,
generators, original source bindings, real retained Linux/cache staging and
resource checks, AST/shell and Git attributes. Run the script from repository
root with the already retained authorized inputs. Use a fresh output source
directory. It does not fetch assets, start QEMU, mount or access a user disk.
`verification.json` adds separate immutable baseline comparisons and precise
device/Apple/host limitations.

QEMU source documents unstable ARM virtio-mmio enumeration; see the linked source
in `STEAM-CACHE-DEVICE-IDENTITY-20261019.md`. The screenshot's specific device
mapping remains unobserved here. Real QEMU/guest BLKROGET is NOT RUN: no system
QEMU binary and configured Debian package metadata retrieval returned proxy403.
No alternative host, proxy, TLS or policy change followed. No loop-device mount
was attempted; this process has zero effective capabilities. The cache is a raw
TAR block stream rather than a mounted filesystem.

No screenshot/Library identity, transfer credentials, account data, Valve bytes
or user disk is included. Original base payload/cache locks remain unchanged.
No CI was started or cancelled; the coordinator's existing CI#41 uses the older
baseline source. New Apple/Swift, VM and device verification remain NOT RUN.
