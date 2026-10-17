# Native Steam proxy mechanism and Chrome IPC readiness

Read-only continuation at verified remote Steam commit
`d0a8201f6495989fd5ab7c01e1bb17c7604747ca`, one executor, selected private cloud.
The environment remained accessible after the reported disconnect. Both stopped
Steam disks retained their exact hashes;17/17 locked client ZIPs and45/45 locked
dependency packages rehashed correctly. See `environment-verification.json`.
No VM/client was started, no image/mount was written, no network/security setting
was changed and the refused updater hostname was **not requested again**.

Main Steam UI / Big Picture remain **NOT REACHED**. The current cloud failure is
still the earlier updater failure, before any CEF process. This analysis does
not reproduce or solve the historical first webhelper timeout.

## Exact inputs and reproducibility

The relevant ELFs were extracted privately from the already verified locked
`bins_linuxarm64_linuxarm64.zip.c10ca8366386600247b22796da24febe0805cbd7`, archive
SHA-256 `26c731703e4a641c8d9ec1ac80e2bc40e3837fc312d180ab32316e33ed980834`.
`binary-inputs.json` records archive entries, sizes, SHA-256 and actual ELF ABI /
NEEDED data. No client binary or disk is included in this evidence directory.

`replay_static.py` first checks all four exact ELF identities and the existing
authenticated private Capstone5.0 library, then decodes bounded selected ranges.
It has no network, guest/client execution, disk-image or configuration operations.
`capstone-provenance.json` independently binds the library to its existing pinned
Debian package. Its C ABI was checked with known AArch64 NOP/RET instructions; separate instruction
field checks verify the flag read/write. Independent system `readelf -rW`
confirms the two vtable relocations (`independent-readelf.txt`). Two replay
processes produced byte-identical outputs. The earlier69/12/94-file evidence
manifests were also revalidated, without editing those pinned artifacts.

Replay against private inputs, choosing a **new** output directory:

```sh
python3 experiments/linux-guest/evidence/steam-proxy-ipc-static-20261017/replay_static.py \
  --elf-dir /workspace/steam-fresh-20261017/proxy-ipc-research-20261017/key-elf \
  --capstone /workspace/steam-fresh-20261017/host/usr/lib/x86_64-linux-gnu/libcapstone.so.5 \
  --output /workspace/steam-fresh-20261017/proxy-ipc-research-20261017/new-replay
```

## Proxy support found in the native updater

This is stronger than finding proxy-related strings or assuming libcurl use:

| Exact native `steam` address | Inspected behavior |
| --- | --- |
| `0x8df3c`, `0x8e0e8–0x8e0f8` | Registers `-bootstrapperproxy` on the command-line parameter at global `0x9b0ba0`. |
| `0xaa384–0xaa3d0` | Bootstrap initialization reads that parameter's value and passes it to the manually configured HTTP proxy method `0x183a60`. |
| `0xb26e0` | The manifest-download path constructs a request with this native HTTP engine (`0x186df8`). |
| `0x19a810` | Native HTTP discovery calls real `getenv` for `HTTP_PROXY`, lowercase `http_proxy`, and fallback `ALL_PROXY`/`all_proxy`; then checks `HTTPS_PROXY`, `https_proxy` and the same fallbacks. It parses the proxy host/port and reads `NO_PROXY`/`no_proxy`. |
| `0x1aa210–0x1aa2cc` | The request-resolution task invokes that environment discovery when needed, then calls `CHTTPClient::BShouldRequestUseProxy` (`0x1a8920`). |
| `0x19eaf0`, format `0x75d2f8` | Native HTTP code constructs `CONNECT %s HTTP/1.1` for the HTTPS origin authority. |

The environment parser strips a scheme prefix and optional user-info before
host/port parsing. No proxy credentials are needed or requested for the existing
host proxy, and none were present in its sanitized configuration. The existence
of credential parsing does not authorize adding credentials.

**Conclusion:** this exact native updater contains implemented application-proxy
mechanisms, including a recognized bootstrap option and environment discovery.
The previous statement that native Steam support was wholly unverified is now
narrowed by exact binary control flow. This is **static mechanism verification**,
not a successful guest proxy request, a Valve support guarantee, or proof that
every main-client/CEF/login transport uses it. The bootstrap option's complete
value grammar and scope were not established; do not invent a command line.

The bundled `libcurl.so.4.8.0` separately identifies itself as7.87.1-DEV and
contains proxy-environment support. That does not prove Steam uses libcurl for
the failed updater request. Official [libcurl proxy documentation](https://curl.se/libcurl/c/CURLOPT_PROXY.html)
also makes options override environment settings, so generic curl behavior
cannot establish any particular caller's runtime configuration. The Valve
command-line wiki was unavailable (HTTP403); no alternate endpoint was used to
work around that response.

## Remaining network and TLS gaps

The current namespace helper constructs a closed UID1000 environment containing
HOME/DISPLAY/XAUTHORITY/XDG_RUNTIME_DIR and normal identity/locale/PATH, without
proxy variables. The runner does not configure application proxy use either.
Nothing was forwarded or changed by this work.

There are additional concrete uncertainties even if proxy discovery is enabled:

1. **Guest proxy name and reachability:** the working host proxy is the existing
   managed `proxy:8080`. The host resolves that internal name through its existing
   hosts entry. The guest has neither a verified name resolution nor a verified,
   platform-supported socket path to that service. Host urllib success does not
   prove QEMU/libslirp TCP can reach it. No numeric-IP substitution, guest hosts
   entry, host relay, tunnel or direct-origin experiment was made.
2. **Origin DNS attempt remains:** native task `0x1a9f70` calls the address parser /
   resolver at `0x1aa064` **before** selecting the proxy. Resolver `0x13fbf0`
   reaches actual `getaddrinfo` at `0x13fc98`. Its return is not immediately fatal
   in the task; proxy selection follows. The selected-proxy branch can populate
   the connection address, but success when origin DNS fails is **not runtime
   verified**. Do not claim that CONNECT eliminates all guest DNS requirements.
3. **TLS trust:** no evidence here establishes the exact Steam TLS trust path
   through the managed service. No CA, trust store, certificate verification,
   sandbox, namespace, seccomp or hostname setting was changed. HTTP CONNECT
   construction alone does not demonstrate a successful authenticated TLS session.
4. **Destination policy:** owner confirmation that the native updater host has
   been published is still pending. The earlier actual result remains **proxy
   CONNECT403, without an origin status**, not an authentication401/403. No retry
   to that host occurred in this follow-up. The separately allowed first locked
   Fastly ZIP previously returned HTTP200 with exact size/hash; that result does
   not authorize the native updater endpoint.

The earlier [exact libslirp/DNS evidence](../steam-network-readonly-20261017/README.md)
still applies to the unchanged backend. Static native proxy discovery offers a
candidate application-level integration; it does not add an automatic proxy
adapter to QEMU.

**Concrete approval boundary:** before any network experiment, obtain owner
confirmation of the newly published updater hostname and platform confirmation
of a supported guest-to-existing-managed-proxy endpoint/name-resolution path,
with policy enforcement and unchanged TLS verification. Then obtain explicit
approval for one native-application proxy configuration experiment. Use only
the exact approved configuration, carry only its selected values through the
closed launcher, retain all session/security settings, and observe one bounded
attempt on a separately gated continuation output. No such patch, configuration
or attempt was implemented here. A mere env pass-through is not a proven fix.

## Previously unresolved Chrome-init readiness is now mapped

This analysis uses the same exact historical client1792192922 ELFs; it is not
a new guest observation. Relevant addresses are module-relative virtual addresses.

| Link | Exact static result |
| --- | --- |
| Steam UI interface acquisition | `steamui.so:0xe6c6bc–0xe6c6d8` requests `ChromeHTML_Controller_003`. |
| Interface factory | `chromehtml.so:0x3e288–0x3e2a4` registers that interface with factory `0x41040`, returning singleton `0x2c61d0`; initializer `0x3e26c` calls its constructor `0x46570`. |
| Controller vtable | Constructor `0x46588–0x465a4` stores `0x2af930`. Relative relocation `0x2af970` gives slot64 → `0x480b8` (pump); `0x2af978` gives slot72 → `0x4ea10` (readiness). |
| Readiness predicate | `0x4ea10`: `ldrb w0, [x0, #0x20c]`; `ret`. |
| IPC subobject | Constructor `0x46688–0x46690` constructs IPC at controller+`0x170`; its constructor clears the connection flags at IPC+`0x9c/0x9d` (`0x54220`). Therefore controller+`0x20c` = IPC+`0x9c`. |
| Flag-setting path | IPC connect function `0x5b078` creates two streams with500ms parameter (`0x5b138`, `0x5b1a4`), sends0x4c bytes, waits at `0x5b364`/return `0x5b368`, reads0x48-byte response and follows its validation path; `0x5b3e8` sets IPC+`0x9c` to1. |
| Failure/reset paths | False response wait goes to `0x5b510`, cancels the request and leaves readiness false. Disconnect routine `0x5ac78` clears IPC+`0x9c` at `0x5ac94`. |

The connection path also calls `0x53228` before setting readiness: an AF_UNIX
socket connects to `/tmp/steam_chrome_shmem_uid%d_spid%u`, with UID/process-specific
formatting at `0x5c670`. Errors in that routine can log/return independently;
the readiness byte alone does not certify that whole channel or rendered UI.

The120000ms Steam UI loop already inspected in earlier evidence is thus waiting
on **Steam's controller IPC connection flag**, while pumping slot64. That is a
more precise observation point than a generic browser-startup or page-ready
assumption. The per-browser `BrowserReady: handle` message and Chromium child's
15-second `EnsureConnected` failure remain distinct code paths.

This closes the static virtual-target gap. It does **not** establish that the
historical runtime hit the500ms response timeout, received duplicate IDs, lost
stream ownership or blocked in any particular function. The retained late trace
still has zero literal500ms waits and17 successful selected robust-mutex waits;
its0.753089s mmap-to-next-syscall gap remains a mixed userspace/scheduling/tracing
interval. No timeout/CPU/SHM allocation change follows from these static findings.

## Next first-failure measurement, after networking works

Use the existing `trace_steam_ipc.py` and `snapshot_steam_ipc_stack.py` within
their documented bounds, after identifying real native/browser PIDs and their
force-sandbox arguments. Resolve the captured PC/LR/FP returns against verified
ELFs/load biases and the newly mapped connect/wait/cancel/pump paths above.
Compare an untraced first attempt with the separate traced attempt; trace
overhead can affect deadlines. Do not extend the stack tool into arbitrary
memory/message/environment capture or claim that it sampled the readiness byte.

Maintain the first child-failure chronology, descriptors/socket identities,
process/thread state, SHM object sizes/headroom and graphics logs. Stop the
bounded observation before restart accumulation/exhaustion. Change one justified
variable only after actual evidence identifies the failure. All45 real
dependencies, including lsof, are now installed with empty successful audit;
their effect on CEF remains untested because this cloud updater never reached it.

No new trace/ARM64 stack/UI/input/Big Picture/application Stop/relaunch test ran.
Existing two cloud VM clean Stops/persistence/full offline fscks remain the
previous receipts, not newly repeated claims. Sentinel/cache and every original
disk/evidence file were retained. Apple runtime, Steam on iPhone and GPU
acceleration remain **NOT RUN**.
