#!/usr/bin/env python3
"""Run the locked ARM64 BusyBox under user-mode QEMU, with real Linux PTYs.

This verifies applets/links and the shell's input path, not a guest kernel boot,
iOS UI, persistent disk or clean guest shutdown. No downloads or disk images.
"""
import argparse
import gzip
import hashlib
import json
import os
import select
import subprocess
import tarfile
import tempfile
import time
from pathlib import Path


def cpio_files(data):
    entries = {}
    position = 0
    while position < len(data):
        if data[position:position + 6] not in (b"070701", b"070702"):
            if data[position] != 0:
                raise ValueError("unexpected CPIO bytes")
            position += 1
            continue
        header = data[position:position + 110]
        size = int(header[54:62], 16)
        name_size = int(header[94:102], 16)
        name = data[position + 110:position + 110 + name_size - 1].decode()
        start = (position + 110 + name_size + 3) & ~3
        end = start + size
        if end > len(data):
            raise ValueError("truncated CPIO")
        entries[name] = data[start:end]
        position = (end + 3) & ~3
    return entries


def check(qemu):
    # Imported only on this explicit Linux runner path; the default Python
    # suite remains usable on the Apple runner and Windows host.
    import fcntl
    import pty
    import termios

    experiment = Path(__file__).resolve().parents[1]
    lock = json.loads((experiment / "ipa/terminal.lock.json").read_text())
    archive = experiment / lock["inputs"]["probe_archive"]["archive"]
    if hashlib.sha256(archive.read_bytes()).hexdigest() != lock["inputs"]["probe_archive"]["sha256"]:
        raise ValueError("probe archive digest mismatch")
    with tarfile.open(archive) as bundle:
        ramdisk = bundle.extractfile("initramfs-ideck.gz").read()
    if hashlib.sha256(ramdisk).hexdigest() != lock["inputs"]["probe_files"]["initramfs-ideck.gz"]["sha256"]:
        raise ValueError("probe initramfs digest mismatch")
    entries = cpio_files(gzip.decompress(ramdisk))
    with tempfile.TemporaryDirectory(prefix="ideck-busybox-") as temporary:
        root = Path(temporary)
        for name in ["usr/bin/busybox", "usr/lib/ld-musl-aarch64.so.1"]:
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(entries[name])
            path.chmod(0o755)
        (root / "lib").symlink_to("usr/lib", target_is_directory=True)
        busybox = root / "usr/bin/busybox"
        base = [str(qemu), "-L", str(root)]
        def run(args, **kwargs):
            return subprocess.run(base + list(map(str, args)), check=True, capture_output=True,
                                  timeout=10, **kwargs)
        applets = run([busybox, "--list"]).stdout.decode().splitlines()
        for name in ["cat", "uname", "ls", "stty", "sh"]:
            assert name in applets, "required applet missing: " + name
        links = root / "run/ideck-bin"
        links.mkdir(parents=True)
        run([busybox, "--install", "-s", links])
        environment = dict(os.environ, TERM="dumb", PS1="ideck# ", PATH=str(links))
        for name in ["cat", "uname"]:
            assert (links / name).is_symlink() and (links / name).resolve() == busybox
        sample = root / "synthetic.txt"
        sample.write_text("synthetic-command-test\n")
        assert run([links / "cat", sample]).stdout == b"synthetic-command-test\n"
        assert run([links / "uname", "-m"]).stdout.strip() == b"aarch64"
        lookup = run([busybox, "sh", "-c", "command -v cat; command -v uname"], env=environment).stdout.decode()
        assert lookup.splitlines() == [str(links / "cat"), str(links / "uname")]

        def shell(canonical, eof=False):
            master, slave = pty.openpty()
            process = None
            output = bytearray()
            consumed = 0
            try:
                if canonical:
                    # Execute the exact flags in the shipping login script.
                    login = (experiment / "guest/ideck-terminal-login").read_text()
                    line = next(line for line in login.splitlines() if line.startswith("/usr/bin/busybox stty "))
                    flags = line.split(" ||", 1)[0].split()[2:]
                    subprocess.run(base + [str(busybox), "stty", *flags], stdin=slave,
                                   check=True, timeout=10)
                def controlling_tty():
                    os.setsid()
                    fcntl.ioctl(0, termios.TIOCSCTTY, 0)
                process = subprocess.Popen(base + [str(busybox), "sh", "-i"], stdin=slave,
                                           stdout=slave, stderr=slave, preexec_fn=controlling_tty,
                                           env=environment)
                os.close(slave)
                slave = -1
                def until(marker):
                    nonlocal consumed
                    deadline = time.monotonic() + 5
                    while marker not in output[consumed:]:
                        if time.monotonic() >= deadline:
                            raise AssertionError("PTY timed out waiting for synthetic marker")
                        if select.select([master], [], [], 0.05)[0]:
                            chunk = os.read(master, 65536)
                            if not chunk:
                                raise AssertionError("PTY ended before synthetic marker")
                            output.extend(chunk)
                    consumed = len(output)
                until(b"ideck# " if canonical else b"\x1b[6n")
                if canonical:
                    os.write(master, b'echo CR_SUBMISSION\r')
                    until(b"ideck# ")
                    assert b"CR_SUBMISSION\r\n" in output
                    # Confirm builtins retain real shell state across inputs.
                    os.write(master, b'read -r line; printf "VALUE:%s\\n" "$line"\r')
                    os.write(master, b"synthetic input\r")
                    until(b"ideck# ")
                    assert b"VALUE:synthetic input\r\n" in output
                    os.write(master, b'printf "READ_PENDING\\n"; read -r pending; printf "UNEXPECTED_READ_COMPLETION\\n"\r')
                    until(b"READ_PENDING\r\n")
                    os.write(master, b"\x03")
                    until(b"ideck# ")
                    assert b"UNEXPECTED_READ_COMPLETION" not in output, "Ctrl-C did not interrupt pending read"
                    os.write(master, b"echo AFTER_INT\r")
                    until(b"ideck# ")
                    assert b"AFTER_INT\r\n" in output
                    os.write(master, b"\x04" if eof else b"exit\r")
                else:
                    os.write(master, b"exit\r")
                process.wait(timeout=5)
                assert process.returncode == 0
                if canonical:
                    assert b"\x1b" not in output, "plain shell emitted ANSI cursor protocol"
                    assert b"echo CR_SUBMISSION" not in output, "guest unexpectedly echoed local input"
                return bytes(output)
            finally:
                if process is not None and process.poll() is None:
                    process.kill()
                    process.wait()
                os.close(master)
                if slave >= 0:
                    os.close(slave)
        shell(False)  # Reproduce the old cursor-query failure first.
        shell(True)
        shell(True, eof=True)
        return {"status": "pass", "busybox_sha256": hashlib.sha256(entries["usr/bin/busybox"]).hexdigest(),
                "applets": len(applets), "cat_symlink_execution": True, "uname_symlink_execution": True,
                "ash_path_lookup": True, "old_cursor_query_reproduced": True,
                "canonical_noecho_cr_read_ctrl_c_exit_ctrl_d": True, "guest_kernel_booted": False,
                "userdata_accessed": False, "ios_ui_tested": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("qemu_aarch64", type=Path, help="Existing user-mode QEMU executable; no auto-download")
    args = parser.parse_args()
    print(json.dumps(check(args.qemu_aarch64.resolve()), indent=2))
