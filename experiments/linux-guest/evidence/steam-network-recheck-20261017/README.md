# Requested network configuration: actual revalidation

One executor, selected private cloud only. Started clean on the requested Steam
branch at remote-verified `12074eaf24cd8c51cf74cd0f185a5454057aa9d9`, a descendant
of the requested starting checkpoint `bfcb3a8bb2a719240daf04ed9023d8a425444e7a`.
No repo/ancestor AGENTS.md or repo `.agents/skills` was found. No other branch,
GUI payload/Release, CI, network/security policy or runtime setting was changed.

**Main Steam UI and Big Picture remain NOT REACHED.** No new VM or Steam process
was started: current host DNS and the approved updater/guest networking path
remain unresolved. This is a fresh bounded verification, not another reproduction
of the historical webhelper timeout.

## Actual HTTP and network results

- A complete new GET of the first exact locked Fastly ZIP returned **HTTP200**,
  **386432 bytes**, SHA-256
  `90b8202eb03a0a95bf444d0daa6849c7e63a0e32fa9367ddb369d6218d2978b1`.
  Size/hash match the unchanged client lock. Redirects were refused; no credentials
  were added. The downloaded ZIP remains private, outside Git.
- The supplied network configuration version is recorded as **owner-reported**;
  no interface independently exposed the control-plane version. A successful
  HTTPS request through the existing managed proxy does not prove guest networking.
- Existing system `getaddrinfo` for allowed Fastly and `api.github.com` returned
  **EAI_AGAIN(-3)**. One ordinary UDP query to the existing configured resolver
  `172.31.1.221:53` returned **ECONNREFUSED(111)** in0.001s. No alternate DNS,
  address/hostname substitution, direct-origin or proxy-forwarding experiment ran.
  These observations do not determine whether the resolver refusal is intentional
  platform policy or a configuration/service fault.
- The native updater's actual hostname from the earlier cloud run is
  **`client-update.steamstatic.com`**. It is absent from the three additions named
  in the current request. Its prior result was **proxy CONNECT403 with no origin
  HTTP status**, not an authentication401/403. It was **not requested again**.
  This checkpoint makes no new status or authentication claim for that host.

See `first-locked-steam-get.json` and `current-network.json`. No new GitHub binary
request was necessary because the production Release bytes are actually present
and were rehashed. No new token or credentials were requested or created.

## Actual inputs and gates

The selected filesystem contains the earlier independent production cloud inputs;
their availability was checked rather than inferred from old paths or automatic
transfer. `current-verification.json` records the new checks:

- All **7 prior Steam evidence manifests /338 files** pass exact size/hash checks.
- Production Release asset650023557 tar is292065280 bytes, SHA-256
  `112bdba6e12ae182fb347e52e7368e26f748bb3dc2bcd77dbd3122fb14dcdedd`.
  All5 restored GUI files match the production lock, including raw seed
  `9c4d978f0ea33b608735e203c0e1695ca89188c02b097e610f971cffe1c05791`.
  No experimental seed/contract was selected or relabeled.
- **17/17** client ZIPs and **45/45** locked dependency packages rehash correctly.
  The unchanged bootstrap and all its repository-bound inputs match its receipt.
- Both run1/run2 qcow2 files retain their exact prior hashes, clean receipts,
  available exclusive owner locks and no dirty marker. Their original command
  directories still contain STOP and were not reused or changed.
- The preserved actual guest install receipt verifies45 installed packages and
  unchanged341 GUI package versions. The later boot's preserved audit receipt
  has `dpkg --audit` **exit0, stdout0 bytes, stderr0 bytes**. The disk containing
  that result is unchanged. **No new guest audit or boot ran in this checkpoint.**
- Both previous complete12GiB offline fsck streams were rehashed and reevaluated
  by the current strict parser: all5 phases and exact summaries pass. These are
  revalidated prior checks, **not newly executed fsck**.
- qemu-utils package, actual qemu-img binary, matching loader and bound closure
  receipt all rehash correctly. The extracted qemu-img10.0.13 version probe exits0;
  no system installation or image-tool write was performed.
- Existing storage gate passes: **22218502144** free bytes against the full
  **17179869184** entry requirement (12GiB offline copy +4GiB reserve), without
  sparse discounts. This is the entry gate; capacity must be rechecked after any
  future continuation copy and before every offline copy. No image was written.
- **149 Steam tests PASS** (`steam-tests.log`). No subagents, VM/image writers or
  task-path mounts were observed. Originals, caches, evidence and failed outputs
  remain retained. No sentinel/runtime cache/SHM cleanup occurred.

The two Python sources are the exact bounded probes used here. For replay, copy
each into a **new private directory under /workspace** before running: output is
written alongside the script, never run these sources in the frozen evidence
directory. They use the actual private input paths explicitly; no binary inputs
are published or fetched by them.

## Precise continuation gate

The earlier [native proxy and IPC analysis](../steam-proxy-ipc-static-20261017/README.md)
establishes implemented Steam application-proxy discovery, but the existing
launcher passes a closed environment without proxy settings. Host HTTPS success
does not establish a supported guest-to-managed-proxy socket/name/TLS path.
The current host DNS failure is new; the earlier guest EAI_AGAIN is historical,
**not rerun here**. No supported working guest path has yet been demonstrated.

Required next information from owner/platform:

1. Confirmation that the actual native updater host
   `client-update.steamstatic.com` is now published/approved, before retrying its
   prior network refusal. The listed Fastly/GitHub additions alone do not do this.
2. A platform-supported policy-enforced guest network configuration: working
   configured DNS and native HTTPS for the unchanged NAT path, or the exact
   supported path to the existing managed proxy with unchanged TLS verification.
   An application-proxy experiment needs explicit approval and exact configuration
   as described in that prior handoff. No speculative environment forwarding,
   numeric address, relay, tunnel, DNS override or CA/security change is proposed.

After those gates, use a **new** command/output directory and the unchanged
runner's explicit clean `--continue-from /workspace/steam-fresh-20261017/run2`,
rechecking source hashes, ownership, production inputs, storage and offline copy.
Retain the ordinary UID1000/HOME/X11/XDG_RUNTIME_DIR/D-Bus setup, namespace helper,
`-cef-force-sandbox` and bounded first-failure trace/stack/SHM observations.
No timeout/CPU guess follows from this network checkpoint.

No IPC trace/ARM64 stack capture ran because there is no new browser target.
Steam UI/input/Big Picture/application Stop/relaunch are still unverified.
Apple runtime, Steam on iPhone and GPU acceleration remain **NOT RUN**.
