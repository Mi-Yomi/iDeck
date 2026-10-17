# Native Steam first-connection and sandbox evidence, 2026-10-17

This is read-only analysis of official locked ARM64 client version 1792192922 and the parent's run7 logs. It does not establish a working Steam UI. No guest process, filesystem, flag, binary or source was changed by this investigation. Binary SHA-256, source-log hashes and selected exact disassembly are in sandbox-shm-receipt.json. Do not commit the private extracted Valve binaries.

## Automatic sandbox fallback and supported restoration

Run7 delta-webhelper.txt records fallback before its first browser child starts. The command line supplied by iDeck contains no sandbox-disabling option, but Valve reports a previous CefInitialize crash and adds --no-sandbox. Therefore that run is unsuitable as evidence of a sandboxed UI even before its memory guard freezes it.

In exact steamwebhelper:

- String 0x781730 is `.cef-initialize-sentinel`. At 0x25a1ec..0x25a200 the helper calls existence test 0x3083e8; that calls __lxstat64. The resolver 0x304b30 joins a relative name to getcwd (0x304b6c). It is a marker in the helper's working directory, not necessarily htmlcache.
- When that pathname exists, 0x25a9ac..0x25a9c8 logs the observed fallback and sets the CefSettings.no_sandbox field to 1.
- At 0x25a204..0x25a26c the helper checks command-line switch `force-sandbox`. If present, 0x25a270..0x25a280 logs `Force enabling sandbox` and clears the same no_sandbox field AFTER the fallback branch. This is a real consumer, not merely a string.
- In Steam's exact steamclient.so, `-cef-force-sandbox` is registered at 0x412634..0x412648 (object 0x2d90990). The consumer at 0xeb50ac..0xeb50c8 tests it and branches to 0xeb69e8, which appends the exact single-dash argument `-force-sandbox` to the helper launch vector. This proves the supported forwarding route.
- Normally the helper creates the sentinel before initialization through fopen(...,"ab") at 0x309028, calls cef_initialize at 0x356cf8, then removes its armed sentinel via unlink at 0x309904 after return. A kill before return can leave it. The observed marker alone does not prove an underlying sandbox defect.

A read-only path check is `/proc/<browser-pid>/cwd` plus stat of its exact `.cef-initialize-sentinel`. Preserve that evidence; no cache wipe or marker deletion is required to use the supported force-sandbox option. A later runtime probe must verify the actual `Force enabling sandbox` log, child argv and sandboxed renderer status. A utility marked `service-sandbox-type=none` is not itself evidence of renderer sandbox failure.

## What allocates 26,214,416-byte objects

The exact helper contains two 0x1900000 constants at 0xdc818 and 0xdc868. The pair constructor at 0xdc7b8 constructs `%s_server` and `%s_client` CShMemStream objects, each with a 25 MiB data region. The stream constructor at 0x1404f0 adds a 16-byte header (0x140674) and explicitly memset-zeroes the whole newly created mapping (0x1407b0..0x1407bc). The corresponding source string is `/data/src/overlay/common/shmemstream.cpp`. Thus each new pair can physically allocate approximately 50 MiB of tmpfs, matching run7; these are not generic Chromium pixel buffers.

Only one direct BL to that pair constructor occurs in the helper: 0xdaf40 inside `CChromeIPCServer::RunFrame` (source `/data/src/common/html/chrome_ipc_server.cpp`). It handles master-stream message type 1, validates protocol version 1, takes the client's identifier from the incoming message, and creates a fresh random logical name `SteamChrome_ClientStream_%u_%u`. The reply is sent only after pair construction: call 0xdafa0 writes 72 bytes. Native steamclient generates that identifier using ThreadGetCurrentProcessId at 0xebb0a4; it is the client PID, not necessarily a distinct thread.

The server has an existing-client-ID branch at 0xdaec0. It clears the previous pair pointers and constructs a new pair. No previous pair destructor is visible on that branch before overwrite. This is a concrete static candidate for retained streams on duplicate connect attempts. It is not yet a measured duplicate-PID leak: the required next observation is repeated connect requests from the same native PID, or repeated logical names with the same PID and changing random suffix.

Run7 disproves an explanation limited to accumulation across browser restarts: PID972 owns the 25 MiB mappings while the first browser remains alive. The guard freezes at 85.085 seconds with shm used696786944/free72663040, before the native120-second readiness timeout. Do not increase memory and call the cause fixed.

## The connection wait is a 500 ms native futex deadline

In steamclient.so 0xebafd0..0xebb474, both master and response stream constructors receive defaulttimeout500 at 0xebb088/0xebb0f4. After writing a76-byte request, the client calls stream wait 0x15ed140 with false,0 at 0xebb2b4. That substitutes the stream's stored default and calls the event's first virtual method at 0x15ed1bc. If false, 0xebb460..0xebb470 resets/cleans the streams and returns unconnected. It never reaches normal pair open at 0xebb348 until the reply arrives.

The event vtable is established by 0x15e7058..0x15e70b0: 0x2c024c0, with RELA entry pointing to 0x15e9bc0. That method divides its timeout by1000 and multiplies the remainder by1000000 (0x15e9c44..0x15e9c60), then calls `syscall@plt` at 0x15e9c84 with ARM64 syscall98, FUTEX_WAIT0, expected0 and a relative timespec. For500ms that is `{tv_sec:0,tv_nsec:500000000}`. ETIMEDOUT110 returns false. The method is the direct syscall wrapper path, not pthread_cond_timedwait or sem_timedwait.

This creates a targeted hypothesis: under TCG, the server's two newly faulted and memset-filled25MiB mappings take longer than the native500ms handshake wait. The client retries, the server allocates more pairs before it can deliver a timely response, and shm grows before any browser restart. Static code proves the deadline and allocation order, not the elapsed runtime timing. The independent CEF network-service15s EnsureConnected exit and later native120s readiness failure must stay separate in the timeline.

## Bounded next measurement and compatibility limits

1. Restore a verified sandbox using the supported Steam argument above. Keep all other launcher options fixed. Capture child argv/status, sentinel existence, monotonic time and shm reserve.
2. Trace only the native client and browser for a short bounded interval: futex waits with relative500ms, openat of u1000-Shm names, ftruncate26214416, mmap/munmap and timestamps. File syscalls alone do not measure the later userspace memset; compare entry/exit of the exact pair constructor or the two memset calls with reply emission if an authorized debugger is available.
3. Useful exact PIE-relative locations: native connect wait return0xebb2b8; intermediate stream wait return0x15ed1c0; syscall return0x15e9c88. Browser connect-ID load0xdadf0, logical-name formatting0xdae18, pair creation0xdaf40, reply emission0xdafa0. Resolve load bases from maps and verify binary hashes first. Capture repeated client PID, not arbitrary data or account contents.
4. No supported configuration for the native500ms timeout was found in the inspected connection path. It is a compiled immediate. `-cef-disable-hang-timeouts` forwards Chrome watchdog options and does not alter this path. CEF `ipc-connection-timeout` controls the independent child connection timer; Steam forwarding remains unproven.
5. A general syscall/futex timeout interposer is unsafe for this experiment's evidence: many unrelated operations share it. Any later proposed shim must be opt-in, exact-hash/module/call-chain scoped, capped, reversible and inactive in CEF children and other client waits. Single returnsite0x15e9c88 alone is insufficient: it is the general SharedObjectEvent wait method. Do not patch or redistribute the Valve binary. No shim was implemented here.
