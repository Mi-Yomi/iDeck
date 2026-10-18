# Run25: pinned lazy-zero stream initialization

Same4096MiB/max/4vCPU/native500ms/sandbox configuration as24. The new private
preload skips the pinned browser's whole-stream memset only after establishing
that the complete owned tmpfs mapping is already all holes. Two actual calls
passed the exact caller/file/mapping guards. Both ARM64 runtime fixtures passed
before Steam. No original client ELF or normal/iOS launch profile changed.

The original monitor completed1211.877s/234samples with no kernelOOM and
minimum2763224KiB available. Maximum SHM was76935168B; only two26214416B streams
were observed, with at most741376B physically allocated in total. This is a
measured improvement over24's repeated full-size stream growth, in one run.

LoginSuccess and a main navigation bar appeared, but content stayed black.
A visually grounded Library click did not establish navigation. After the
original bounded monitor, the existing identity-checked URI guardian resumed
the same owned client for303.095s and dispatched steam://open/library (exit0).
No healthy Library/BigPicture/game result was established. See actual privately
reviewed frame hashes in screen-stage-receipt.json; account pixels are excluded.

006's300s readiness wait ended before the browser finished starting; later015
proved activation and absence of the old IPC-timeout shim. This is recorded as
a failed diagnostic command, not hidden as an all-pass run. Native IPC remained
500ms. Generic launch-profile.library_source_sha256 refers to the old shim's
regression baseline, not the newly loaded zero library; run25-zero-build.json
and actual zero-runtime-tests.json identify the new payload.

Two PC-only hot-thread captures used the existing tested seize/interrupt/detach
helper, with no register writes/user-memory reads and TracerPid0/stateR restored.
These are samples of active libcef execution, not proof of an infinite JS loop.
Browser/child affinity was2-3, with four guestCPUs available. Both GPU/compositing
disable flags were already present. One network-service restart was reported;
that alone does not establish the remaining failure's cause. Next26 combines
the new zero control with the existing0-3 affinity helper.

Original VMStop was clean/QEMU0/no recovery marker; application shutdown needed
owned-process termination including oneSIGKILL. All4clientELFs/audit/namespace
checks passed. Full offline fsck passed all5phases+summary/noerrors, original
sourceSHA20a30a61ccbba6830442e067907f7dc9fcad22e452f57a98760dbe8b2790cef0
unchanged, rawcopySHA4c11447b7d46d810cb4b43f9dd2523338d91bcf3fe665db728793934f9257f57.
Full stdout/stderr were inspected; input mount/keeper normally closed.

Only sanitized metadata and selected non-payload scripts are included. The
embedded ELF staging script, raw account logs, pixels, heaps and dumps are not
included. No iPhone, Steam/Proton game, storage or GPU-acceleration acceptance.
