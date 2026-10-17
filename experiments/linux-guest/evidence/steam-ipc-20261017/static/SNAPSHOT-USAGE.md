# Address-only AArch64 IPC stack snapshot

` snapshot-ipc-stack.py ` is an original guest diagnostic. It selects1–4 existing threads from the exact UID1000 native Steam and first browser executables under `/home/ideck/.local/share/Steam/steamrtarm64`. The browser must belong to the specified Steam PID and have no `--type` argument. It refuses an existing tracer, wrong identity/UID/executable, a mixed stopped/running thread group, reused PID, non-AArch64 host, non-root execution, or an existing output file. It never launches the client or attaches children.

Example, with real PIDs selected by the independent monitor:

```sh
python3 /opt/ideck-diagnostics/snapshot-ipc-stack.py \
  --main-pid NATIVE_PID --browser-pid BROWSER_PID \
  --tid NATIVE_PID --tid BROWSER_IPC_TID \
  --output /tmp/ideck-address-snapshot-unique.json
```

Capture performs PTRACE_SEIZE with only PTRACE_O_TRACEEXEC (to distinguish a concurrent exec event from a real SIGTRAP signal), PTRACE_INTERRUPT, and GETREGSET/NT_PRSTATUS. It retains only PC,SP,x29,x30. It reads at most32 exact16-byte frame records from `/proc/TID/mem`, only while the thread is ptrace-stopped, inside the same readable/writable mapping containing SP, requiring aligned/increasing frame pointers and executable return addresses. It outputs addresses, module paths and exact mapping/file offsets; it never outputs argument registers, arbitrary memory, syscall buffers, argv or environment. ELF VA offsets must be derived from the module PT_LOAD metadata; file offset is not universally equal to VA. It does not guess or remove PAC bits, so a signed return pointer stops the walk honestly.

There are no target memory/register writes, breakpoints, fork/clone tracing, syscall changes or timeout modifications. The per-stop polling bound is750ms, with one bounded cleanup retry; at most4 threads are processed and the inter-thread work budget is8seconds. An independent guest memory/time guard remains required. Ptrace briefly pauses selected threads and may perturb timing; this is a causal diagnostic, not baseline performance evidence.

Cleanup always attempts detach, including capture/read failures and ordinary interruption. Existing group-stop state is preserved with an explicit SIGSTOP sent through a pinned pidfd, followed by verification that TracerPid is0 and the same target remains T. A pidfd prevents signaling a recycled process ID. Running targets receive no artificial Stop/Cont signal. A concurrent external stop is preserved when observed; do not concurrently signal or attach the selected processes. Detach/restore failures are recorded as failures. Forced termination of the diagnostic itself is outside this guarantee; do not kill it while attached.

The Linux manual states that PTRACE_DETACH restarts a tracee and that its signal argument can be ignored outside signal-delivery-stop; passing SIGSTOP only to DETACH is insufficient. This tool therefore uses explicit pidfd signaling for restoration. See [ptrace(2)](https://man7.org/linux/man-pages/man2/ptrace.2.html). The272-byte ARM64 register layout follows [Linux AArch64 ptrace UAPI](https://raw.githubusercontent.com/torvalds/linux/master/arch/arm64/include/uapi/asm/ptrace.h).

Verification:16 offline tests passed for the pure walker, bounds/PAC/short reads, identity checks, failure cleanup and stop restoration. Two actual SEIZE/INTERRUPT/DETACH integration probes on this task's own harmless WSL sleep children passed: running→S and pre-stopped→T, both TracerPid0. Those tests did not read real registers or memory, touch Steam, or interact with a VM. Actual AArch64 GETREGSET/frame capture remains NOT RUN by the reviewing agent.

The relevant next observation is the actual return chain of the contended shared-object mutex or failed connect. Do not assume the live implementation is steamclient.so rather than chromehtml.so. The late syscall trace proves contention on `/dev/shm/u1000-ValveIPCSharedObj-Steam` inode106+0x18; no500ms event timeout was observed, so a timeout shim is not justified.
