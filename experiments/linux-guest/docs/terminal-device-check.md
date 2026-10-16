# Terminal and persistence device check

This is the acceptance plan for the new terminal stage. It is not a recorded
passing run. No local QEMU/Swift execution, Apple build or two-boot device test
has been completed for this feature yet. Keep the original accepted probe IPA
and guest assets unchanged.
The source stage passed 140 host Python tests, resource/staging and source
checks. These checks support an Apple build; they do not replace the following
real guest and device acceptance.

The terminal runs the existing guest BusyBox ash with a real controlling TTY
established by getty on ttyAMA0, with
TERM=dumb. It is a local line console with basic control keys, not a full VT
emulator or a promise that full-screen terminal apps work. Two local AF_UNIX
socket pairs carry console traffic and an independent fixed Stop protocol
(IDECK_STOP_V1 on org.ideck.control).
The shell does not inherit the supervisor's control descriptor. An echo in the
console is not a clean-unmount acknowledgement.
There is no SSH, guest networking, Steam or full desktop/rootfs in this stage.

## Before starting

Use the newly reviewed IPA only after its Apple build passes. Re-sign a copy
through the normal owner SideStore flow and keep its installed executable hash
separate from the original IPA hash. Record the app source revision and OS.
Complete the existing JIT setup/execution check; debugger attachment alone is
not execution verification.

Choose terminal before starting any VM. One VM owns the process; never start
the probe and terminal in the same process. Pairing files and credentials stay
with the owner and must not be included in reports committed to Git.

## First launch: create a file and stop during a foreground command

1. Start the terminal and wait for the real guest shell and a successful /data
   mount. A mount error is a failure: do not format, reset, or replace the disk.
2. Choose your own unpredictable, nonsensitive token for TOKEN below. Do not
   reuse a sample token, password or other secret. Run:

   ```sh
   printf '%s\n' 'TOKEN' > /data/owner-check.txt
   cat /data/owner-check.txt
   /usr/bin/busybox sleep 300
   ```

3. While sleep is in the foreground, press the app Stop control. This must use
   the independent control channel; it must not wait for the shell prompt or
   inject a shutdown command as terminal text.
4. Wait for the complete clean-stop result: guest IDECK_TERMINAL_CLEAN_UNMOUNT acknowledgement after
   stopping children/sync/unmount, QEMU loop return, and host userdata fsync.
   A button press, timeout, EOF, lost control connection or process termination
   alone is not clean-stop proof. Keep the disk and diagnostics on failure.
   If the report records a failure or timeout, leave it as failed; do not infer
   success from a still-responsive console or manually replace the data disk.
   Startup (60 seconds) and Stop (30 seconds) timeouts report failure without
   forcing shutdown or claiming a clean stop. A guest STOP_FAILED is sticky.
   If only console output closes, try the independent Stop control when it is
   available; serial EOF alone cannot acknowledge a clean unmount.
5. After clean stop, fully close the app and reopen it into a new process.
   The current process cannot safely restart QEMU or switch VM modes.
   Its disk lock remains held until process exit, including after orderly stop.
   Main-loop return does not prove full block-layer drain; the report's
   qemu_block_layer_drained_verified remains false.

## Second launch: read the same file

1. Re-enable and verify JIT as needed, choose terminal, and start it again.
2. Read the file without recreating it:

   ```sh
   cat /data/owner-check.txt
   ```

3. Compare its complete contents with your first-launch value. PASS requires
   an exact match from the same Documents/iDeckLinux/userdata.raw disk after
   the fresh-process boot. Seed recreation or merely reading cached terminal
   text does not count.
4. Stop cleanly again and save the terminal report/diagnostics privately.

Only /data persists. Files elsewhere in the initramfs are volatile. The FAT16
volume does not supply POSIX permissions, symlinks or a persistent Linux rootfs.
The promise being tested is orderly stop followed by another app launch;
uninstall/reset and unclean termination are outside that proof. Existing user
data must never be overwritten because it no longer matches the empty seed.

## Probe, JIT and Markdown regressions

In a fresh process run the original separate Linux probe. Its bundled kernel,
initramfs/profile hashes and JIT gate must remain unchanged. Repeat framebuffer
A/B and keyboard/pointer acceptance and save the probe report. Framebuffer
matching and guest input do not automatically verify physical screen transition
or guest GPU acceleration.

Check the existing Markdown-only primary export and separate raw JSON/log
secondary export. Export failure must not change the guest result. Confirm that
Markdown excludes raw private container paths, arbitrary terminal/serial text,
pairing credentials and private artifact URLs/IDs. The existing Foundation
renderer tests must run on the Apple gate; source checks alone are insufficient.

Record the actual results separately: shell interaction, initial mount, file
write, Stop under foreground load, each clean-stop condition, fresh-process read
and original probe/JIT/Markdown regression. Report failed or untested stages as
such. Keep the token, raw device logs and screenshots private; Git evidence
should contain only sanitized outcomes and necessary digests. This check says
nothing about Steam, games, networking or accelerated guest GPU.
Terminal elapsed time covers the whole worker session, including disk
preparation, initialization, interaction and Stop. It is not pure boot time or
the existing probe's separate post-init polling interval.
