# Read-only DNS / managed proxy diagnosis

Continuation source: verified remote Steam commit
`170c0e0c928a41b2af5ededeb774ee19f886bb88`, same private selected environment,
one executor. No VM, Steam process or image writer was started in this step.
No request to `client-update.steamstatic.com` was repeated while the owner was
preparing its allowlist addition. The earlier CONNECT403 receipt remains historical.

## Observed paths

`host-baseline.json` and `dns-versus-proxy.json` establish:

- Host `getaddrinfo` for permitted `client-update.fastly.steamstatic.com` and
  `deb.debian.org` also returns EAI_AGAIN(-3). This reproduces the symptom outside
  the guest, with host NSS configured as `files dns`.
- The existing host resolver is **172.31.1.221**. One bounded ordinary UDP DNS
  query for the permitted Fastly hostname, sent only to this already configured
  resolver on port53, received **ECONNREFUSED, errno111**, after0.001s. No public
  resolver, DNS override, alternate protocol or fallback was used.
- The host already has HTTP/HTTPS proxy configuration for **proxy:8080**.
  Its existing `/etc/hosts` entry resolves that service to172.31.1.221 without
  public DNS. No credentials were present; raw environment values and unrelated
  hosts were not dumped.
- A bounded HTTPS GET of the permitted exact first locked Fastly ZIP, using
  `urllib`'s normal existing proxy and normal TLS, returned **HTTP200**. Only one
  response byte was read and no cache was changed. This was not a direct-connect
  comparison or a request to the refused updater hostname.

Thus a working managed application-proxy path coexists with a refusing ordinary
host DNS endpoint. The guest error has a sufficient upstream explanation; these
observations do not establish a separate guest resolver/libc defect. They also do
not reveal whether the host DNS refusal is intentional policy, a missing service
or a service fault. That administrative distinction is not visible here.

## Exact pinned backend, not an assumed proxy feature

The actual extracted library is libslirp0 **4.8.0-1+deb13u1**, package SHA-256
`6125698173f8be0d0de01ff897a0df3c5e50fb09f70238b26dd6574aaa0934e1`,
library SHA-256
`12ee83fb069a5be30b9e450f69a5e07eec4861f2e9b574c46a4052f086c341f3`.
`binary-source-binding.json` records its actual dpkg Source/Version fields.

The source index was independently authenticated from the same signed pinned
Debian InRelease and its SHA256 table. The exact source package, upstream tar and
Debian patch tar were then checked against that index. An offline replay rehashed
the same nine inspected source/patch files. See `pinned-slirp-source.json` and
`read_pinned_slirp.py`; source archives remain private, not in Git.

Relevant source paths (line numbers refer to the verified upstream4.8.0 tar):

| File / routine | Actual behavior reviewed |
| --- | --- |
| `src/socket.c:968`, `sotranslate_out4` | Guest virtual-nameserver traffic on port53 is translated through `get_dns_addr`. |
| `src/slirp.c:434`, `get_dns_addr_resolv_conf`; `:487`, `get_dns_addr` | Linux reads the host `/etc/resolv.conf` and selects its nameserver. |
| `src/socket.c:762`, `sosendto` | UDP is emitted using the host `sendto` socket call. |
| `src/tcp_subr.c:377`, `tcp_fconnect` | TCP uses a host stream socket and `connect`; this is not HTTP CONNECT proxy negotiation. |

The single Debian urgent-data bounds patch was reviewed; it does not add a proxy
adapter or change these DNS/connect routines. No library or patch was modified.
The exact QEMU10.0.13 manual documents virtual DNS10.0.2.3 and has no HTTP proxy
option for the `user` backend. `pinned-qemu-man-reference.json` records the actual
authenticated package/manual identities and inspected sections.

The repository runner additionally supplies a closed QEMU environment containing
PATH/locale/module directory, without the host proxy variables. Its ordinary-user
namespace launcher also supplies a closed environment without proxy variables.
Neither the QEMU invocation nor the guest startup configures an explicit
application proxy. Blindly inheriting env would not make libslirp a transparent
HTTP proxy client. This was source inspection only; no env was changed.

The resulting current DNS path is:

`guest 10.0.2.3:53 -> libslirp -> configured host 172.31.1.221:53 -> refusal`

The independently working host HTTPS path is:

`proxy-aware host downloader -> existing proxy:8080 -> permitted HTTPS origin`

This explains why the new host allowlist fixed locked host downloads without
establishing guest updater connectivity. There is no functioning supported
QEMU guest-to-managed-proxy adapter demonstrated by this profile.

## Minimal supported continuation and approval boundary

For the **unchanged native-socket QEMU profile**, the necessary operator-supplied
network capability is precise:

1. Make the environment's **already configured private resolver** answer ordinary
   UDP53 queries from the QEMU host process, so10.0.2.3 can forward them. Do not
   assign an external resolver or substitute hostnames/IPs.
2. Provide a **platform-supported, policy-enforced native TCP443 egress path**
   for QEMU to the approved exact updater hostname
   `client-update.steamstatic.com`, preserving destination restrictions and TLS
   verification. Direct origin egress is NOT tested or authorized as a workaround
   for the managed proxy. A generic unrestricted egress/escalation is not a fix
   requested by this evidence.

These are required capabilities, not a claim that this platform exposes a
particular supported switch. Its available read-only interfaces do not establish
that such a native-socket route exists. If the platform supports **only** its
managed HTTP CONNECT proxy, the unchanged `-netdev user` profile has no documented
automatic route through it. An explicitly supported native Steam/updater proxy
configuration would need separate review, owner authorization and runtime
validation. Steam support for such a configuration is **NOT VERIFIED** here;
no speculative env forwarding, proxy relay, tunnel or backend substitution is
implemented or offered as a proven solution.

Enabling native egress or changing DNS/proxy/security configuration exceeds this
read-only instruction. That remediation step is stopped for owner/platform
agreement. The concrete requested review is **private DNS53 service + controlled
QEMU native TLS443 capability**, or confirmation that the platform is proxy-only
and can document a supported application proxy integration. Do not merely publish
one more hostname and declare the guest network fixed. Runtime redirects, login
and other Steam services may need separately observed/approved destinations; no
wildcard or game network expansion is requested now.

Primary references: [QEMU user-mode network](https://www.qemu.org/docs/master/system/devices/net.html#using-the-user-mode-network-stack),
[QEMU user backend options](https://www.qemu.org/docs/master/system/invocation.html#network-options),
[official managed command networking scope](https://learn.chatgpt.com/docs/cloud/internet-access#agent-security-command-network-requirements).
The latter documents proxy-mediated allowlists; it does not certify native QEMU
egress in this selected environment. Exact Debian source URLs/hashes are in the
source receipt. Source conclusions and platform-support unknowns are kept distinct.

## Production seed provenance, freshly rehashed

The source was the existing authorized private GitHub Release asset **650023557**:
`https://api.github.com/repos/Mi-Yomi/iDeck/releases/assets/650023557`, Release
`ideck-debian-gui-v1-local-20261017`. The prior step used existing `gh api` with
`Accept: application/octet-stream`; no new token or alternate delivery was used.
Both the binary download receipt and local archive hash are independently checked.

| Item | Size | SHA-256 |
| --- | ---: | --- |
| `ideck-debian-gui-v1.tar` | 292065280 | `112bdba6e12ae182fb347e52e7368e26f748bb3dc2bcd77dbd3122fb14dcdedd` |
| Restored `gui-rootfs-v1.raw` | 1342177280 | `9c4d978f0ea33b608735e203c0e1695ca89188c02b097e610f971cffe1c05791` |

Restore used the existing `tools/gui_bundle.py restore` against the unchanged
`ipa/gui.lock.json`; it checked the exact archive/member hashes, decompressed
the pinned raw gzip and verified all five production files. Actual private paths:
`/workspace/steam-fresh-20261017/release/ideck-debian-gui-v1.tar` and
`/workspace/steam-fresh-20261017/gui/gui-rootfs-v1.raw`. Rehashes in
`host-baseline.json` again match the complete production identity. This is not
a7758d82 or a rebuilt seed. Availability/provenance is established; the separately
pending GUI recovery validation itself is **NOT RUN by this diagnostic step**.

Both installed Steam disks retain their committed hashes. All17 client ZIPs and
all45 extra dependency cache packages were rehashed unchanged; see
`preservation.json`. No original, failed output, installed client, cache or
sentinel was removed. No VM/mount remains, no CI or GUI-branch change occurred.
Steam main UI/Big Picture, historical IPC cause, Apple/iPhone and GPU acceleration
remain at their preceding NOT REACHED/NOT RUN status.
