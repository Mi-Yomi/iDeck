#!/usr/bin/env python3
"""Real QEMU/TCG boot, exact framebuffer pixels and decoded guest evdev input."""
import argparse
import hashlib
import json
import os
import queue
import re
import struct
import subprocess
import threading
import time
from pathlib import Path
from prepare_guest import frame


def verify_assets(guest):
    profile = json.loads((guest / "profile.json").read_text())
    if profile.get("schema") != 1:
        raise ValueError("unsupported profile")
    expected = {"width": 800, "height": 600, "cpu": "cortex-a72", "memory_mib": 1024,
                "vcpus": 4, "tcg_cache_mib": 256}
    if any(profile.get(key) != value for key, value in expected.items()):
        raise ValueError("unsupported machine configuration")
    for key, expected_name in (("kernel", "vmlinuz-virt"), ("initramfs", "initramfs-ideck.gz")):
        item = profile[key]
        if item["file"] != expected_name:
            raise ValueError("unexpected asset name")
        source = (guest / item["file"]).resolve()
        if source.parent != guest.resolve():
            raise ValueError("asset symlink escapes guest directory")
        content = source.read_bytes()
        if len(content) != item["size"] or hashlib.sha256(content).hexdigest() != item["sha256"]:
            raise ValueError("guest asset integrity failure: " + key)
    return profile


def decode_events(log, label):
    match = re.search(r"IDECK_EVENTS_BEGIN:" + label + r"\r?\n(.*?)IDECK_EVENTS_END:" + label, log, re.S)
    if not match:
        raise ValueError("missing guest input capture: " + label)
    data = bytes.fromhex(match[1])
    if not data or len(data) % 24:
        raise ValueError("invalid AArch64 evdev capture length")
    return [{"seconds": s, "microseconds": us, "type": t, "code": c, "value": v}
            for s, us, t, c, v in struct.iter_unpack("<qqHHi", data)]


def validate_events(keyboard, tablet):
    def present(events, kind, code, value):
        return any(e["type"] == kind and e["code"] == code and e["value"] == value for e in events)
    if not all(present(keyboard, 1, 30, v) for v in (1, 0)):
        raise ValueError("guest did not receive KEY_A press and release")
    if not all(present(tablet, 1, 272, v) for v in (1, 0)):
        raise ValueError("guest did not receive BTN_LEFT press and release")
    for code, value in ((0, 8192), (1, 24575)):
        if not present(tablet, 3, code, value):
            raise ValueError("guest tablet axis did not match the injected coordinate")


def ppm_rgb(data):
    header = re.match(rb"P6\s+(\d+)\s+(\d+)\s+255\s", data)
    if not header or tuple(map(int, header.groups())) != (800, 600):
        raise ValueError("unexpected framebuffer screenshot format")
    rgb = data[header.end():]
    if len(rgb) != 800 * 600 * 3:
        raise ValueError("truncated framebuffer screenshot")
    return rgb


class QMP:
    def __init__(self, process):
        self.process = process
        self.messages = queue.Queue()
        self.sequence = 0
        def receive():
            for line in process.stdout:
                try:
                    self.messages.put(json.loads(line))
                except json.JSONDecodeError:
                    self.messages.put({"invalid": line.decode(errors="replace")})
        threading.Thread(target=receive, daemon=True).start()
        greeting = self.messages.get(timeout=15)
        if "QMP" not in greeting:
            raise ValueError("missing QMP greeting")
        self.greeting = greeting
        self.command("qmp_capabilities")

    def command(self, name, arguments=None):
        self.sequence += 1
        request = {"execute": name, "id": self.sequence}
        if arguments is not None:
            request["arguments"] = arguments
        self.process.stdin.write((json.dumps(request) + "\n").encode())
        self.process.stdin.flush()
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            response = self.messages.get(timeout=max(0.01, deadline - time.monotonic()))
            if response.get("id") == self.sequence:
                if "error" in response:
                    raise ValueError(response["error"])
                return response.get("return")
        raise TimeoutError("QMP command timed out: " + name)


def run(qemu, guest, out):
    profile = verify_assets(guest)
    out.mkdir(parents=True, exist_ok=False)
    serial = out / "serial.log"
    argv = [str(qemu), "-M", "virt", "-cpu", "cortex-a72", "-smp", "4", "-m", "1024",
            "-accel", "tcg,thread=multi,tb-size=256", "-kernel", str(guest / "vmlinuz-virt"),
            "-initrd", str(guest / "initramfs-ideck.gz"),
            "-append", "console=ttyAMA0 loglevel=6 rdinit=/ideck-init fbcon=nodefer vt.global_cursor_default=0",
            "-nic", "none", "-device", "virtio-gpu-pci,xres=800,yres=600",
            "-device", "virtio-tablet-pci", "-device", "virtio-keyboard-pci",
            "-display", "none", "-monitor", "none", "-serial", "file:" + str(serial),
            "-qmp", "stdio", "-no-reboot"]
    result = {"schema": 1, "status": "failed", "host_os": os.name,
              "host_runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "qemu_sha256": hashlib.sha256(qemu.read_bytes()).hexdigest(),
              "qemu_version": subprocess.check_output([str(qemu), "--version"], text=True).strip(),
              "argv": argv, "profile": profile, "ios_executed": False, "steam_executed": False,
              "gpu_acceleration_verified": False,
              "host_differences": "Windows QEMU 11.1 TCG; not Husk QEMU 10.0.12-utm; no iOS split-WX allocator or Metal presenter"}
    started = time.monotonic()
    with (out / "qemu-stderr.log").open("wb") as err:
        proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=err,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        try:
            qmp = QMP(proc)
            result["qmp_version"] = qmp.greeting
            def log():
                return serial.read_text(errors="replace") if serial.exists() else ""
            def until(markers, timeout=90):
                deadline = time.monotonic() + timeout
                while time.monotonic() < deadline:
                    text = log()
                    if "IDECK_PROBE_FAILED:" in text or "Kernel panic" in text:
                        raise RuntimeError("guest failed; see serial.log")
                    if all(m in text for m in markers):
                        return text
                    if proc.poll() is not None:
                        raise RuntimeError("QEMU exited before probe completed")
                    time.sleep(0.1)
                raise TimeoutError("guest did not emit: " + repr(markers))
            def screenshot(phase):
                path = out / f"frame-{phase}.ppm"
                bgra = frame(phase)
                expected = bytearray()
                for i in range(0, len(bgra), 4):
                    expected.extend((bgra[i + 2], bgra[i + 1], bgra[i]))
                deadline = time.monotonic() + 8
                while time.monotonic() < deadline:
                    qmp.command("screendump", {"filename": str(path), "format": "ppm"})
                    data = path.read_bytes()
                    actual = ppm_rgb(data)
                    if actual == expected:
                        return {"file": path.name, "sha256": hashlib.sha256(data).hexdigest(),
                                "all_480000_pixels_match": True}
                    time.sleep(0.1)
                raise ValueError("guest framebuffer pixels do not match phase " + str(phase))
            until(["IDECK_FRAME_A", "IDECK_INPUT_READY:keyboard", "IDECK_INPUT_READY:tablet"])
            result["boot_to_capture_ready_host_seconds"] = round(time.monotonic() - started, 3)
            result["frame_a"] = screenshot(0)
            qmp.command("input-send-event", {"events": [{"type": "key", "data": {"down": True, "key": {"type": "qcode", "data": "a"}}}]})
            qmp.command("input-send-event", {"events": [{"type": "key", "data": {"down": False, "key": {"type": "qcode", "data": "a"}}}]})
            qmp.command("input-send-event", {"events": [
                {"type": "abs", "data": {"axis": "x", "value": 8192}},
                {"type": "abs", "data": {"axis": "y", "value": 24575}},
                {"type": "btn", "data": {"down": True, "button": "left"}}]})
            qmp.command("input-send-event", {"events": [{"type": "btn", "data": {"down": False, "button": "left"}}]})
            text = until(["IDECK_PROBE_DONE"], timeout=45)
            keyboard, tablet = decode_events(text, "keyboard"), decode_events(text, "tablet")
            result["keyboard_events"], result["tablet_events"] = keyboard, tablet
            validate_events(keyboard, tablet)
            result["frame_b"] = screenshot(1)
            qmp.command("quit")
            proc.wait(timeout=10)
            if proc.returncode != 0:
                raise RuntimeError("QEMU did not shut down cleanly")
            result["status"] = "host_boot_framebuffer_input_pass"
        except Exception as error:
            result["error"] = f"{type(error).__name__}: {error}"
            raise
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)
            result["elapsed_host_seconds"] = round(time.monotonic() - started, 3)
            result["qemu_exit_code"] = proc.returncode
            (out / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "elapsed_host_seconds": result["elapsed_host_seconds"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qemu", type=Path, required=True)
    parser.add_argument("--guest", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.qemu.resolve(), args.guest.resolve(), args.out.resolve())
