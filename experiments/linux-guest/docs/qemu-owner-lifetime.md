# QEMU owner thread after Linux Stop

Investigation starts at iDeck `341541d09251556eff6fd9c99f5abd83ea20fb82`,
Husk `0695248f491cda877f7969d1f0cc89aeede1482e` (2.0.0 build 119).

## Device evidence supplied by the parent reviewer

The second Debian session reached READY, then Stop crashed in native RCU:
`synchronize_rcu +324 → call_rcu_thread +184 → qemu_thread_start`.
EXC_BAD_ACCESS / SIGSEGV / KERN_INVALID_ADDRESS at zero; this is not Jetsam.
QEMU UUID `94db2dc1-9f93-3c02-bfae-bee74b405080` and app UUID
`da5fd3ad-b4ec-3c19-b43a-818fabb544ab` match the delivered IPA according to
the independent reviewer. This executor has not downloaded that IPA or IPS.

The reviewer decoded instruction at dylib offset `0x86c264` (8831588):
`0xf900014b = STR X11,[X10]`, with X10 = 0. Preceding instruction at
`0x86c234` loads X10 from `[X8,#24]`. In the pinned LP64 reader layout,
`node.le_next` is offset 16 and `node.le_prev` is offset 24. This maps the
fault to the write through `le_prev` in `QLIST_REMOVE` in `wait_for_readers`,
inlined in `synchronize_rcu`. The QEMU owner/Swift thread was absent from the
snapshot while four MTTCG vCPU threads remained. No personal raw metadata is
needed or committed here.

The first session's Markdown receipt (source 341541d, started
2026-10-17T03:53:40Z, elapsed 379.325 s) reports unmount, loop return and host
sync. Its `cleanStopped` predates host log/socket close and worker exit.
The second screenshot shows READY and `ideck-debian-ok`, but the command is
not visible. Debian persistence and a healthy shutdown tail are therefore
**not final device PASS**.

## Exact source evidence

Read the archive from `ipa/native-sources.lock.json`, not a moving QEMU branch:
[UTM QEMU 10.0.12-utm release source](https://github.com/utmapp/qemu/releases/download/v10.0.12-utm/qemu-10.0.12-utm.tar.xz),
142836072 bytes, SHA-256
`7c9605290b34152debb842e965a55d2e4fbba4793e536ab677b4027e5dc0ba1a`.
The executor fetched this public source archive and independently verified
both fields. No new compiler, runtime, binary or package was installed.
Line numbers below refer to this archive, whose formatting can differ from
the GitHub tag's raw files.

* `system/vl.c:2851–2853`: shared-library `qemu_init()` explicitly calls
  `rcu_register_thread()` on its caller. At 2899 it calls `qemu_init_subsystems()`.
* `include/qemu/rcu.h:36–39`: register before read-side use; unregister before
  thread exit. The intrusive `rcu_reader_data.node` belongs to that reader.
* `include/qemu/coroutine-tls.h:118–123` and `util/rcu.c:68`: actual `__thread`
  storage, no TLS destructor that unregisters it.
* `util/rcu.c:373–386`: registration inserts the TLS address in `registry`;
  unregister removes it under `rcu_registry_lock`.
* `util/rcu.c:102–105`: grace-period processing removes the reader with
  `QLIST_REMOVE` before moving it to `qsreaders`. Null `le_prev` is invalid
  linkage, not an optional argument. `call_rcu_thread` calls this code.
* `system/runstate.c:830–839`: `qemu_main_loop()` returns status, without
  teardown or unregister. `qemu_init_subsystems()` acquires BQL at 867.
  `qemu_cleanup()` is separate (891), including vm shutdown/block drain/close.
* `util/qemu-thread-posix.c:487–545`: QEMU's pthread wrapper runs its notifier
  list on exit; the Foundation-created owner does not use that wrapper. Even
  the wrapper is not an automatic RCU unregister contract for arbitrary TLS.
* `system/qemu.symbols` does not export `rcu_unregister_thread`. The app's
  narrow hand-written bridge is not a general QEMU teardown interface.

In both existing Linux workers, the Swift closure returned just after
`qemu_main_loop()` and async report publication, despite retaining QEMU's
other resources. The source lifecycle defect is proven. The device's stale
RCU linkage is strongly explained by it; a full device fix claim still needs
the new build and Stop/relaunch test.

## Narrow containment

`LinuxQEMUThreadLifetime.retainCurrentThread` returns `Never`. Both Linux
workers enter it on the **same** native thread after loop return. A private
NSCondition blocks indefinitely, with a loop for spurious wakes. There is no
polling, sleep, cancellation exit, new owner thread or release API.

The retention callback runs after acquiring that private mutex, before its
first wait. Terminal records `qemuOwnerThreadRetained` synchronously before
queueing loop-return handling. The report says RETENTION ENTERED; it is a
code-reached receipt, not a sampled thread-liveness or RCU-drain measurement.
Waiting releases only the private condition mutex, preserving the owner
thread, its TLS and existing BQL ownership until process exit. It intentionally
retains the native stack (configured 16 MiB) and existing runtime resources.
RCU callbacks requiring BQL may remain blocked; drain is **NOT VERIFIED**.

Do not add unregister alone: it removes one RCU node, but does not prove the
other owner-thread/TLS/BQL/display/vCPU contracts have been discharged. Do not
add `qemu_cleanup`, BQL unlock, disk unlock or restart as part of this fix.
The process still permits one VM invocation. Dirty-disk refusal, failure
latch, no-reseed, disk/resource retention, Terminal and Probe routes remain.

After the narrow clean-stop receipt the durable journal records
`consoleLogCloseBegin → consoleLogCloseReturned → consolePeersCloseBegin →
consolePeersCloseReturned`. Each record fsyncs before returning. These mark
close **attempts** reaching/returning; existing best-effort log IO is unchanged.
The new report field is set only after that path returns. Neither it nor the
earlier receipt certifies ongoing process health, backend close, or drain.
Old journals remain readable and report tail completion as NOT ESTABLISHED.

## Regression and remaining gates

`tools/check_qemu_rcu_lifetime.py --archive <existing-verified-archive>
--out <new-directory> --cc cc` compiles the exact archive registry, grace-period,
read-lock/unlock functions, reader struct, TLS and list macros. Native pthread
mutex/event and atomic adapters replace the unrelated QEMU/GLib platform layer;
no QEMU backend is built or executed. The offline suite enables it with
`IDECK_QEMU_RCU_ARCHIVE=<archive>`; without the source/compiler it explicitly skips.

The native test has three separate processes: actual exit without unregister
leaves the expired TLS address registered (never dereferenced); unregister
control removes it; retained native owner survives 10000 grace periods with
four concurrent readers and repeated condition signals, keeping its TLS node
and mutex ownership. This validates the native RCU lifetime mechanism, not
the Swift wait or iOS crash. Source hashes and results are in
`evidence/qemu-owner-lifetime-native.json`.

The mandatory Apple gate separately executes the **production Swift helper**
on a real Foundation thread with pthread TLS destructor negative control,
checks that cancellation does not end it while the host queue remains usable,
and requires `LINUX_QEMU_OWNER_LIFETIME_PASS`. Journal reopen/tail-order and
Markdown compatibility tests execute production helpers there too.

**NOT RUN here:** Swift compiler/Apple SDK, full QEMU backend, app link/IPA,
Codemagic and iPhone test. No toolchain was installed to hide a SKIP.
The owner must review the commit, check free quota and build separately.
On iPhone: boot Debian, write a unique file and read it back, Stop, wait at least
60 seconds, export normal and startup Markdown, then fully exit/relaunch the
app and read that exact file. Repeat Stop/wait/export, including Terminal/Probe
smoke where needed. READY alone is insufficient. Preserve a new IPS if a crash
persists; keep block drain NOT VERIFIED and disk lock retained throughout.
