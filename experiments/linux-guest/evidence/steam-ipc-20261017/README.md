# Steam IPC handoff evidence, 2026-10-17

Read ../../STEAM-IPC-HANDOFF.md first. These are bounded host observations, not
main Steam UI/Big Picture/iPhone acceptance. No client binaries or disk images.

- run7: real diagnostic run; clean VM stop, forced (unclean) application stop.
- run8: deliberate user cancellation before GUI readiness/commands; clean VM stop.
  Its full fsck is the offline pre-boot copied-run7 check, not post-run8 fsck.
- first-failure-7: unsafe automatic Valve sandbox fallback detected and stopped;
  retain as diagnosis only, not sandbox acceptance.
- force-sandbox-trace-7-resumed: sandbox override enabled; initial trace too early
  for large allocation. The timeline spans its later resumed observations.
- force-sandbox-trace-7-live-pairs: later bounded native/browser trace. No observed
  literal500ms timeout; successful5s allocator-mutex waits are a separate path.
- static: exact-binary inspection notes/receipts. The 500ms connection theory in
  SANDBOX-SHM.md is a historical hypothesis, NOT the established first root cause.
  Source binary/disassembly paths in receipts are local provenance, not files
  promised in this Git tree. Obtain exact official inputs to repeat inspection.
- validation:129 offline regression tests on task-owned ext4; no Apple toolchain.
- bootstrap.json: new archive built, only early boot before user interruption.

Trace receipts deliberately retain conservative trace_incomplete for SIGINT
detach. Observed syscall evidence is bounded and tracing can affect timing.
No environment, login store or message-body dump is supplied. Local disk paths
in historical receipts do not imply access from cloud. manifest.json covers the
exact retained bytes, including the original Windows/guest line endings.
