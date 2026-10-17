# First CEF failure: exact ARM64 evidence, 2026-10-17

Scope: static inspection of locked Valve client 1792192922 and existing run5/run6 logs. No VM/disk interaction, package installation, binary patch, branch edit, CI action, or default flag change. Binary copies stay in this private scratch directory; do not commit them.

## Three distinct failure paths

1. **CEF child connection failure, observed first.** run5/016-cef-state.log:170 records PID2357 `ChildThreadImpl::EnsureConnected()` at 10:54:03, before browser PID2422 starts at 10:54:19. Exact `libcef.so` SHA-256 `891d85f97231fcafa5763b7140039c5d3cbbb99f2a42ede08de5991abcbc3cdb`, size218132264, matches the verified lock ZIP. Its function at0x99a59a4 logs that precise message with source line942; 0x99a5a04 passes0 to0x6329a94, which calls `_exit`. This is a failed child-to-browser connection, not a success message. The old snapshot did not identify whether PID2357 was a renderer or utility; fresh PID/role chronology is needed.
2. **Steam's Chrome-init timeout.** Exact `steamui.so` SHA-256 `9a59e3bbbee2c6de7a2559986ae5407c01e7416ac5ac2d9e40f11c8aceffc1ee`: call0x1000ebc invokes `CreateSharedJSContext:BWaitForChromeInit` at0x1000b88 with120000ms. It uses `Plat_MSTime64` deadline, invokes virtual slots64(pump) and72(readiness) on `m_pChromeController` atthis+216, sleeps1/2/4/8/16/32 then50ms. False readiness at the deadline logs at0x1001778 and continues creation at0x1000ec8. The closed virtual implementation and the reason it never becomes ready remain unresolved. This ARM64 code does not use the 2400-iteration loop reported for a different x86 lxrun build.
3. **Later shared-memory exhaustion.** run5/024-shm-capacity.log shows769449984-byte tmpfs100%full after multiple restarts; the parent independently identified the SIGBUS mapping. This cannot explain the initial attempt while fresh `/dev/shm` was empty. Preserve the first-attempt trace separately from accumulated retry failure.

## Confirmed prerequisite: lsof admission check

Exact `steamclient.so` SHA-256 `276f021548f9016de834274f4042b796604530d910d114b77ee170b46e409072` has `GetIPCConnectionDetails` at0xeceb70. It checks `/usr/sbin/lsof`, `/usr/bin/lsof`, `/sbin/lsof`, `/bin/lsof`, falls back to PATH, and executes:

```
lsof -P -F upnR -i TCP@<peer-address:port>
```

The function parses UID/PID/PPID/port and returns peer PID. Caller0x5815a0 rejects false at0x5815e0, logs `Connection rejected`, increments its rejection counter, and returns false. No bypass is appropriate: supply the real dependency if measured missing, and preserve ownership validation. Run7 preflight reported by the parent confirms lsof is absent. This establishes a real missing dependency; **it is not yet proven to cause the earlier Chrome-init timeout**. The static HTTP403 response branch has not been traced. Runtime signatures: `GetIPCConnectionDetails`, `command failed: 127`, `WebUITransport`, `Connection rejected`.

The [SteamARM stage22 record](https://raw.githubusercontent.com/LukeOkk/SteamARM/main/benchmarks/stage22-native-arm64-bringup.txt) describes lsof fixing transport403, but its E5 had already reached BrowserReady before lsof was added. Its lxrun/macOS W^X, rewritten x18 and subpage-memory fixes do not transfer to this real Linux/QEMU guest.

## Exact connection timer and bounded probe prerequisite

In exact libcef0x99a52b4/0x99a52bc default delay is15000000 microseconds. GOT0xcf179b0 points to `ipc-connection-timeout` at0x1c48be2. At0x99a5368 an integer value is parsed and0x99a5370–5380 multiplies seconds by1000000. At0x99a545c the EnsureConnected callback is selected;0x99a5480 supplies the delay. These match [Chromium126 ChildThreadImpl](https://raw.githubusercontent.com/chromium/chromium/126.0.6478.183/content/child/child_thread_impl.cc): the15-second callback is cancelled when its browser channel connects. [Chromium126 BrowserChildProcessHostImpl](https://raw.githubusercontent.com/chromium/chromium/126.0.6478.183/content/browser/browser_child_process_host_impl.cc) forwards this switch from browser to children.

Thus `--ipc-connection-timeout=60` has verified child-level semantics. **A Steam-to-webhelper forwarding path is not verified.** No matching `-cef-ipc-connection-timeout` option was found in exact steamclient/chromehtml strings; this absence alone is not exhaustive proof of unsupported forwarding. The official `steamwebhelper.sh` simply passes its arguments through taskset and has no extra-argument environment hook. Do not add guessed flags, modify the wrapper, or claim this probe ran.

Only consider a one-variable timeout probe after fresh evidence identifies the child role, its disappearance at the connection deadline, the still-live browser, and an explicit supported forwarding path. Record the switch in both actual browser and child argv. Bound total duration and shm headroom. Do not change sandbox or other switches.

## Next measurements, in order

1. Freeze/capture first failure before retry accumulation: PID/PPID/type, thread CPU time and wchan, namespace IDs, selected status fields, fd/socket/pipe links, `/proc/net/unix` and tcp endpoints, `/dev/shm` free bytes and object sizes. Do not read environment, login/session data or message bodies. Correlate the failing child with the exact CEF line and process exit.
2. Confirm whether browser I/O is runnable and making progress, blocked in futex, waiting on a dead peer, or waiting on a subprocess. Inspect the passed Mojo descriptor in the child and its parent. Keep child connection failure separate from Steam's shared-object IPC.
3. Inspect complete first-attempt `transport_steamui.txt`, cef_log, webhelper, steamui_html and client stdout for admission rejection, BrowserReady, NSS/locale FATAL, missing subprocess, and permission errors. Existing short tails do not establish their absence.
4. If a bounded syscall trace is required, trace only the relevant browser/child/subprocess tree; capture syscall numbers, errno, descriptor identity and timing, without I/O buffers or environment. Trace overhead itself can change a15-second TCG deadline, so report traced and baseline runs separately. No security setting change is justified by missing diagnostics.
5. Missing system D-Bus and launcher-service warnings are observations, not proven UI blockers. The exact launcher-service exit127 path previously inspected disables that helper and returns. Do not make a broad service/package change before evidence narrows the fault.

`record-first-failure.py`, `inspect-cef-ipc.py`, and `find-cef-ipc-refs.py` reproduce the local static checks. SHA/size receipt covers selected text evidence. Apple/iPhone, main Steam UI and Big Picture are not validated by this analysis.
