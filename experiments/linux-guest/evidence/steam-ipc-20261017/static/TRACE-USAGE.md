# Bounded IPC trace usage

The executable `trace-first-ipc.py` is a guest diagnostic, not a launcher. Run it only in the parent's separate instrumented probe after a clean tmpfs boot. Do not replace the untraced baseline with its timings. Ptrace overhead can itself cause a deadline failure.

Stage this original Python helper into the experimental guest, then run as root:

```sh
python3 /opt/ideck-diagnostics/trace-first-ipc.py \
  --main-pid ACTUAL_NATIVE_STEAM_PID \
  --wait-browser 45 --seconds 25 \
  --output /tmp/ideck-ipc-trace-UNIQUE
```

The existing strace path defaults to `/opt/ideck-diagnostic-strace/usr/bin/strace`. An explicit `--browser-pid` is optional. Existing output directories are refused. The parent should retain its independent memory/process guard throughout. This helper stops only its tracer, never the client, VM or disk.

Native Steam must already have `-cef-force-sandbox`, and the detected browser must contain its forwarded `-force-sandbox`. The tool confirms fixed executable paths, UID1000, one browser with matching `-steampid`, no `--type`, no existing tracer, and no unexpected PID reuse during discovery. It does not prove runtime sandbox state by itself; retain actual child argv and renderer Seccomp evidence from the independent monitor.

The trace attaches all current native/browser TIDs explicitly, without `-f`, so newly created sandbox children are not ptraced. New threads created after attachment are also not traced. This scope reduces interference with sandbox startup and is recorded in result.json. Syscalls are limited to futex, openat, ftruncate, mmap, munmap, close, unlink/unlinkat, connect, clone/clone3 and exit/exit_group. Read/write/exec buffers and process environment are not captured.

Hard limits are25seconds by default (maximum30),8MiB stored trace (maximum16MiB), and64MiB available shared-memory reserve. On stop the tool signals only strace, drains its pipe to avoid a detach deadlock, and checks detach for original TIDs. It never uses SIGKILL or signals a tracee/process group. An unsuccessful detach is reported, not declared successful.

Outputs: trace.log; before/after maps for native and browser; result.json with timestamps, original TIDs, exact trace command, marker metadata, size/hash of logs, tracer result and surviving attachment checks. Maps should be combined with independently checked on-guest binary hashes before interpreting offsets.

## Which native library matters

The same IPC client implementation exists in steamclient.so AND chromehtml.so. Do not assume the SteamUI call uses the engine's steamclient copy merely because it is mapped. Both contain the500ms handshake. Exact verified ARM64 version1792192922 chains:

| Module | SHA-256 | Handshake return | Stream wait return | Event syscall return |
| --- | --- | --- | --- | --- |
| steamclient.so | 276f021548f9016de834274f4042b796604530d910d114b77ee170b46e409072 | 0xebb2b8 | 0x15ed1c0 | 0x15e9c88 |
| chromehtml.so | 753ca9cb1aff9740a99c84e0d8a8a1270c2cb081fd1a414696da2a5e8c833ae7 | 0x5b368 | 0x63a98 | 0x60420 |

The browser's pair allocation lives in steamwebhelper itself: caller0xdaf40, pair ctor0xdc7b8, stream memset0x1407bc, reply0xdafa0. Resolve module bias from ELF PT_LOAD plus /proc maps; do not subtract the first executable segment start blindly.

`-i` records the kernel syscall instruction pointer. Because these calls go through libc's syscall(), this normally identifies the libc SVC stub, not the original Steam/chromehtml callsite. It cannot prove the whole call chain. A separate bounded stack-unwinding/debugger observation is required if differentiating the two live implementations. Do not infer a specific module solely from a500ms futex timeout.

Look for recurring `{tv_sec=0,tv_nsec=500000000}` futex waits ending ETIMEDOUT in native threads while the browser creates/faults successive26214416-byte mappings. ftruncate/mmap timestamps alone do not time the ensuing userspace memset. A debugger or narrowly scoped original diagnostic shim would be needed to time its entry/exit and correlate the72-byte reply. No binary patch or timeout shim is supplied by this tool.

Offline verification: six tests cover target filtering, syscall allowlist, required sandbox restoration arguments, byte cap, interruption/detach using a harmless fake stderr producer, and refusing an existing output directory before subprocess launch. No guest tracing was performed by the reviewing agent.
