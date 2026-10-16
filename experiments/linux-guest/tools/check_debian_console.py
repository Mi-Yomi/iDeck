#!/usr/bin/env python3
"""Real offline system-QEMU acceptance of the exact production Debian payload.

Two boots on a fresh seed copy, interactive input, independent Stop channel,
POSIX persistence and read-only fsck. No reference seed is attached to QEMU.
"""
import argparse
import json
from pathlib import Path
import select
import shutil
import socket
import subprocess
import time

from debian_bundle import load_lock, metadata, verify


def boot(qemu, bundle, disk, output, phase, stop_by_exit=False):
    servers = []
    for _ in range(2):
        server = socket.socket(); server.bind(("127.0.0.1", 0)); server.listen(1); server.settimeout(30)
        servers.append(server)
    args = [str(qemu), "-machine", "virt", "-cpu", "cortex-a72", "-smp", "4", "-m", "1024",
            "-accel", "tcg,thread=multi,tb-size=256", "-display", "none", "-monitor", "none",
            "-nodefaults", "-nic", "none", "-no-reboot", "-kernel", str(bundle / "vmlinuz-virt"),
            "-initrd", str(bundle / "initramfs-debian.gz"),
            "-append", "console=ttyAMA0 earlycon=pl011,0x09000000 rdinit=/ideck-debian-init panic=0 loglevel=6",
            "-drive", "if=none,id=debian,format=raw,cache=writethrough,file=" + str(disk).replace(",", ",,"),
            "-device", "virtio-blk-device,drive=debian"]
    for name, server in zip(("serial0", "control0"), servers):
        args += ["-chardev", f"socket,id={name},host=127.0.0.1,port={server.getsockname()[1]}"]
    args += ["-serial", "chardev:serial0", "-device", "virtio-serial-pci",
             "-device", "virtserialport,chardev=control0,name=org.ideck.control"]
    logs = [bytearray(), bytearray()]
    sockets = []
    process = None
    started = time.monotonic()
    report = {"phase": phase, "argv": args, "status": "failed", "stop_method": "shell_exit" if stop_by_exit else "control_channel"}
    try:
        with (output / f"qemu-{phase}.log").open("wb") as stderr:
            process = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=stderr, stderr=subprocess.STDOUT)
            sockets = [server.accept()[0] for server in servers]
            for channel in sockets: channel.setblocking(False)
            closed = set()
            def pump():
                active = [s for s in sockets if s not in closed]
                if not active:
                    time.sleep(0.05)
                    return
                readable, _, _ = select.select(active, [], [], 0.05)
                for channel in readable:
                    try: data = channel.recv(65536)
                    except ConnectionResetError: data = b""
                    if data: logs[sockets.index(channel)].extend(data)
                    else: closed.add(channel)
                    if sum(map(len, logs)) > 4 * 1024**2: raise RuntimeError("serial bound exceeded")
            def until(predicate, seconds=90):
                deadline = time.monotonic() + seconds
                while not predicate():
                    pump()
                    if time.monotonic() > deadline: raise TimeoutError("guest acceptance deadline")
                    if b"IDECK_DEBIAN_FAILED:" in logs[0] or b"IDECK_DEBIAN_STOP_FAILED" in logs[1]:
                        raise RuntimeError("guest supervisor failure")
                    if process.poll() is not None and not predicate():
                        pump()
                        if not predicate(): raise RuntimeError("guest exited before expected evidence")
            until(lambda: b"IDECK_DEBIAN_READY\n" in logs[1])
            until(lambda: b"debian# " in logs[0])
            # Leave the production console idle: readiness cannot auto-poweroff.
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline: pump()
            if process.poll() is not None: raise RuntimeError("production console powered off while idle")
            report["interactive_idle_alive"] = True
            # Real serial input, not an initramfs self-test. All writes are in
            # the disposable guest root, isolated from host paths/userdata.
            commands = ["test \"$(dpkg --print-architecture)\" = arm64", "getconf GNU_LIBC_VERSION",
                        "dpkg --audit > /run/ideck-audit && test ! -s /run/ideck-audit",
                        "test \"$(dpkg-query -W -f='${Package}\\n' | wc -l)\" -eq 90"]
            if phase == 1:
                commands += ["mkdir /root/ideck-production-check", "cd /root/ideck-production-check",
                    "printf 'production-persistence-v1\\n' > original", "chmod 640 original", "chown 1000:1000 original",
                    "ln original hard", "ln -s original symbolic", "mv original saved", "ln -sf saved symbolic",
                    "stat -c %i saved > inode", "sync"]
            else:
                commands += ["cd /root/ideck-production-check", "test \"$(cat saved)\" = production-persistence-v1",
                    "test \"$(stat -c %a:%u:%g saved)\" = 640:1000:1000",
                    "test \"$(stat -c %i hard)\" = \"$(cat inode)\"",
                    "test \"$(readlink symbolic)\" = saved", "cmp symbolic hard", "test \"$(stat -c %h saved)\" = 2"]
            for index, command in enumerate(commands):
                marker = f"IDECK_CONSOLE_COMMAND_{phase}_{index}_PASS"
                sockets[0].sendall((command + " && echo " + marker + "\r").encode())
                until(lambda: marker.encode() in logs[0], seconds=20)
            report["serial_commands_passed"] = len(commands)
            sockets[0].sendall(b"stty -a; grep -E '^(Name|Pid|PPid|SigIgn|SigCgt):' /proc/$$/status; cat /proc/$$/stat; echo IDECK_TTY_DIAGNOSTICS\r")
            until(lambda: b"IDECK_TTY_DIAGNOSTICS" in logs[0], seconds=5)
            sockets[0].sendall(b"printf 'IDECK_SLEEP_BEGIN\\n'; sleep 30\r")
            until(lambda: b"IDECK_SLEEP_BEGIN" in logs[0], seconds=5)
            deadline = time.monotonic() + 0.3
            while time.monotonic() < deadline: pump()
            prompt_start = len(logs[0])
            sockets[0].sendall(b"\x03")
            # Wait for the fresh prompt: canonical VINTR flushes pending input,
            # so sending the next command in the same burst is not a valid test.
            until(lambda: b"debian# " in logs[0][prompt_start:], seconds=5)
            sockets[0].sendall(b"echo IDECK_DEBIAN_CTRL_C_PASS\r")
            until(lambda: b"IDECK_DEBIAN_CTRL_C_PASS" in logs[0], seconds=5)
            report["ctrl_c_interrupt_passed"] = True
            # A serial echo must not act as a supervisor acknowledgment.
            sockets[0].sendall(b"echo IDECK_DEBIAN_CLEAN_UNMOUNT\r")
            deadline = time.monotonic() + 0.3
            while time.monotonic() < deadline: pump()
            if b"CLEAN_UNMOUNT" in logs[1]: raise RuntimeError("serial text reached control channel")
            if stop_by_exit: sockets[0].sendall(b"exit\r")
            else: sockets[1].sendall(b"IDECK_STOP_V1\n")
            until(lambda: b"IDECK_DEBIAN_CLEAN_UNMOUNT\n" in logs[1], seconds=30)
            until(lambda: process.poll() is not None, seconds=30)
            pump()
            code = process.wait()
            if code != 0 or b"STOP_FAILED" in logs[1]: raise RuntimeError("QEMU did not stop cleanly")
            report.update(status="pass", qemu_exit=code, guest_clean_unmount=True)
    finally:
        if process is not None and process.poll() is None:
            process.kill(); process.wait(); report["forced_termination"] = True
        for channel in sockets + servers: channel.close()
        for name, data in zip(("serial", "control"), logs): (output / f"{name}-{phase}.log").write_bytes(data)
        report["seconds"] = round(time.monotonic() - started, 3)
        (output / f"boot-{phase}.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def check(args):
    lock = load_lock(args.lock)
    verify(args.bundle, lock)
    args.out.mkdir(parents=True, exist_ok=False)
    seed = args.bundle / "rootfs-v1.raw"
    disk = args.out / "disposable.raw"
    shutil.copyfile(seed, disk)
    report = {"schema": 1, "status": "failed", "scope": "host production Debian console; NOT iPhone",
              "seed": metadata(seed), "production_initramfs": metadata(args.bundle / "initramfs-debian.gz"),
              "boots": [], "apple_swift": "NOT RUN", "ios_device": "NOT RUN"}
    try:
        report["boots"].append(boot(args.qemu, args.bundle, disk, args.out, 1))
        report["boots"].append(boot(args.qemu, args.bundle, disk, args.out, 2, stop_by_exit=True))
        before = metadata(disk)
        if args.wsl:
            path = subprocess.check_output(["wsl", "-d", args.wsl, "--", "wslpath", "-u", str(disk)], text=True).strip()
            command = ["wsl", "-d", args.wsl, "--", "e2fsck", "-fn", path]
        else: command = ["e2fsck", "-fn", str(disk)]
        result = subprocess.run(command, capture_output=True, timeout=60)
        (args.out / "fsck.log").write_bytes(result.stdout + result.stderr)
        report["fsck"] = {"argv": command, "exit_code": result.returncode, "disk_unchanged": metadata(disk) == before}
        if result.returncode != 0 or metadata(disk) != before: raise RuntimeError("read-only fsck failed")
        report["status"] = "pass"
    finally:
        report["seed_unchanged"] = metadata(seed) == report["seed"]
        if not report["seed_unchanged"]: report["status"] = "failed"
        report["disposable"] = metadata(disk)
        (args.out / "result.json").write_text(json.dumps(report, indent=2) + "\n")
        (args.out / "result.md").write_text("# Production Debian console host check\n\n"
            + "Status: " + report["status"] + "\n\nTwo real offline boots; serial commands, Stop channel / shell exit, persistence and fsck.\n"
            + "\nSwift / Apple / iPhone: NOT RUN. This does not prove QEMU backend cleanup inside iOS.\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("qemu", "bundle", "lock", "out"): parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--wsl")
    print(json.dumps(check(parser.parse_args()), indent=2))
