# Pinned Steam stream zero-initialization experiment

Experimental and opt-in. No normal launcher or iOS profile loads this library.
It must establish actual browser activation, stream events and working UI before
being described as a Steam fix. Lower SHM allocation alone is insufficient.

The pinned ARM64 browser creates two 25 MiB + 16 byte shared files for an IPC
connection. Its new-stream branch zeroes the entire mapping at `0x1407bc`, then
initializes the header at `0x1407c8`. The native client waits 500 ms for the
reply. Earlier observations showed both large allocation growth and delayed
connection responses under TCG. This experiment tests avoiding redundant writes
to a file whose complete contents are already zero.

The `memset` interposer is active only in the ordinary UID1000 browser, with its
exact checked ELF SHA-256, file identity, call-site offset and instruction bytes.
It refuses other executables, `--type=` children and inherited fork processes.
The whole target must be the base of a shared read/write mapping at file offset
zero, backed by a regular UID1000 mode0700 single-link tmpfs file of exactly
26214416 bytes, with a checked `u1000-Shm_XXXXXXXX` pathname and matching inode.
Both `st_blocks == 0` and `SEEK_DATA` returning `ENXIO` must establish all holes;
file identity and allocation are rechecked before returning the unchanged
address. Any failed guard falls back to libc's ordinary `memset`.

Linux documents that reads of file holes return zero and supports these seek
operations on tmpfs: [lseek(2)](https://man7.org/linux/man-pages/man2/lseek.2.html).
This does not remove or punch holes in an existing file. It does not change a
timeout, shared-memory limit, syscall ABI, kernel policy or Chromium sandbox.
Only an explicit private preload after dropping to UID1000 enables the test.
Bounded metadata-only activation/stream receipts go to a new mode0600 file in
the private runtime directory; failure to write a stream receipt retains the
ordinary zero operation. After128 eligible calls the ordinary path is used.

`shm-zero-unit.c` includes the production checker directly. It creates its own
exclusive temporary tmpfs file and exercises hole detection, actual contents,
nonzero data, full fallback clearing, mapping offset/size/private-map rejection,
permissions and ownership/link/allocation guards. It has no production identity
override. Compile with `-O2 -fno-builtin -Wall -Wextra -Werror`; run as UID1000.
ARM64 builds use the existing private pinned cross toolchain. Runtime fixtures
must also pass inside the actual ARM64 guest before Steam is launched.

The library exports only the standard `memset` entry. It does not interpose
`syscall`, so it does not reuse the old stack-changing clone-wrapper defect.
Client executables, account data, caches and live shared objects are preserved.
Private ELF payloads and account logs are excluded from Git.

Run25 established actual activation and two eligible calls, both actual ARM64
fixtures passing, and no repeated large-stream allocation over the bounded
20-minute observation plus a five-minute URI control. Maximum SHM was about77MB
and maximum combined resident allocation of the two large streams741376bytes.
Main navigation rendered but the content stayed black; Library navigation and
games remain unverified. This is an allocation fix observed in one run, not a
complete Steam UI fix. See [run25 evidence](../../evidence/steam-local-arm64-20261017/run25/README.md).

`shm-zero-ipc-unit.c` adds a bounded cross-process check: separate virtual
addresses map the same exclusive test file, observe untouched zero holes,
exchange data in both directions, and confirm that a blocked shared futex waiter
is actually awakened. It runs as UID1000 with its own temporary file; it does
not inspect or modify a Steam stream. Both ordinary and preload-fallback runs
must pass in the actual ARM64 guest, in addition to the original checker tests.

`render-tested-profile.py` renders the exact private launcher/helper used in
run27 from the pinned launcher, namespace helper and compiled V5 library. It
rejects different input hashes and existing output directories, and neither
installs files nor launches Steam. Example from this directory:

```sh
python3 render-tested-profile.py \
  --launcher ../../guest/steam/ideck-steam \
  --namespace-helper ../../guest/steam/namespace-check.py \
  --zero-library /path/to/private/libideck-shm-zero.so \
  --output /path/to/new-private-profile
python3 test_render_profile.py
```

The rendered profile uses the stock `-cef-disable-hang-timeouts` argument with
the same sandbox and native 500 ms IPC deadline. Its receipt lists the required
fresh ARM64 fixtures, pinned library location, credential drop, original bounded
owner/resource guardian, application shutdown, original VM Stop and offline
filesystem check. Rendering is not permission to omit these runtime controls.
The separately recorded browser affinity phase uses all four guest CPUs;
rendering alone does not apply it. Original launchers and iOS profiles remain
unchanged. A newly compiled library with a different hash requires separate
review and validation; do not simply replace the pin.
