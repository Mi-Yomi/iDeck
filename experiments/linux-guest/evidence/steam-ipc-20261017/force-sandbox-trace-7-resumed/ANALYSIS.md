# Attempt015/016: sandbox restored, early trace misses IPC allocation phase

Valve log explicitly reports `Force enabling sandbox` after detecting the old sentinel, and browser argv contains `-force-sandbox`. No process argv in the monitor contains `--no-sandbox`. PID2688 is observed as a zygote descendant with UID1000, NoNewPrivs1, NSpid2688/4/1 and Seccomp0→2. It is later a zombie. No renderer argv is observed, so this establishes an actual sandbox transition but not a working renderer or UI.

The bounded trace contains321,607 bytes. Its25.019-second stop was the deliberate duration limit; tracer exit-2 is SIGINT sent by the tool, followed by successful detach and no remaining traced TIDs. The original result honestly remains `trace_incomplete` because its classifier requires exit0. One initially selected TID2572 disappeared before PTRACE_SEIZE; the trace nevertheless contains syscalls from the surviving selected threads. Do not silently upgrade the receipt or claim complete coverage.

This trace has no500ms futex waits and no26,214,416-byte ftruncate calls. It ends at Unix1792238921.047, approximately43.4seconds before the first monitor sample containing a large IPC object at1792238964.446. Its small ftruncate calls belong to earlier startup. Thus it neither confirms nor refutes the native500ms handshake hypothesis.

The same first browser PID2527 later holds rapidly increasing large objects:1 at resume161.357s,3 at164.884s,11 at171.446s,19 at174.741s,21 at guard freeze176.452s. Shared-memory usage reaches532,443,136bytes at freeze. A late separately bounded capture may observe those retries, but cannot retrospectively prove the first failure.

`trace-analysis.json` records parsed trace counts/times, exact warning and source SHA. `extraction-receipt.json` pins the original206KB export and every decoded file. All analysis is readonly with respect to the guest and repository.
