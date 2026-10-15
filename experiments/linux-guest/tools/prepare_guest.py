#!/usr/bin/env python3
"""Build deterministic probe initramfs from the same pinned Alpine as Husk119."""
import argparse
import gzip
import hashlib
import json
import stat
import subprocess
import tarfile
import urllib.request
from pathlib import Path
from steam_abi import elf

NAME = "alpine-netboot-3.24.1-aarch64.tar.gz"
URL = "https://dl-cdn.alpinelinux.org/alpine/v3.24/releases/aarch64/" + NAME
SHA256 = "54fe38fa41cce740ba379458ed63cfcd89ab06ae5e6a47a06dafe0a34e8427e8"
SIZE = 431008592
ROOT = Path(__file__).resolve().parents[1]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def entry(name, content, mode, inode):
    encoded = name.encode() + b"\0"
    fields = [inode, mode, 0, 0, 1, 0, len(content), 0, 0, 0, 0, len(encoded), 0]
    header = b"070701" + b"".join(f"{value:08x}".encode() for value in fields)
    record = header + encoded
    record += b"\0" * (-len(record) % 4)
    record += content + b"\0" * (-len(content) % 4)
    return record


def frame(phase):
    # BGRA, 800x600, no font/assets/copyrighted imagery. Different quadrants
    # exercise row stride, channel order and a second scanout after real input.
    colors = ((34, 51, 204, 255), (51, 204, 68, 255), (204, 85, 34, 255), (204, 204, 204, 255))
    output = bytearray()
    for y in range(600):
        for x in range(800):
            index = ((y // 300) * 2 + x // 400 + phase) % 4
            output.extend(colors[index])
    return bytes(output)


def prepare(archive, out, sevenzip, frame_probe):
    data = archive.read_bytes()
    if len(data) != SIZE or digest(data) != SHA256:
        raise ValueError("Alpine archive differs from the locked upstream bytes")
    out.mkdir(parents=True, exist_ok=False)
    with tarfile.open(archive) as source:
        kernel = source.extractfile("boot/vmlinuz-virt").read()
        initramfs = source.extractfile("boot/initramfs-virt").read()
        modloop = source.extractfile("boot/modloop-virt").read()
    module_image = out / "modloop-virt"
    module_image.write_bytes(modloop)
    module_path = "modules/6.18.35-0-virt/kernel/drivers/input/evdev.ko"
    evdev = subprocess.check_output([str(sevenzip), "e", "-so", str(module_image), module_path], timeout=60)
    if len(evdev) != 42335 or evdev[:6] != b"\x7fELF\x02\x01" or evdev[18:20] != b"\xb7\x00":
        raise ValueError("unexpected evdev module for the pinned AArch64 kernel")
    init = (ROOT / "guest/ideck-init").read_bytes().replace(b"\r\n", b"\n")
    executable = frame_probe.read_bytes()
    abi = elf(executable)
    if abi["e_machine"] != 183 or abi["class"] != "ELF64" or abi["interpreter"] or abi["needed"]:
        raise ValueError("frame probe must be a static AArch64 Linux ELF")
    frames = [frame(0), frame(1)]
    cpio = entry("ideck", b"", stat.S_IFDIR | 0o755, 1)
    cpio += entry("ideck-init", init, stat.S_IFREG | 0o755, 2)
    cpio += entry("ideck/fb-probe", executable, stat.S_IFREG | 0o755, 3)
    cpio += entry("ideck/evdev.ko", evdev, stat.S_IFREG | 0o644, 4)
    cpio += entry("TRAILER!!!", b"", 0, 5)
    # Linux supports a sequence of compressed cpio archives. The original
    # distro initramfs and its module metadata stay byte-for-byte intact.
    probe = initramfs + gzip.compress(cpio, mtime=0)
    (out / "vmlinuz-virt").write_bytes(kernel)
    (out / "initramfs-ideck.gz").write_bytes(probe)
    report = {"schema": 1, "upstream_url": URL, "upstream_sha256": SHA256,
              "upstream_size": SIZE, "original_initramfs_sha256": digest(initramfs),
              "init_source_sha256": digest(init), "width": 800, "height": 600,
              "modloop_sha256": digest(modloop), "evdev_path": module_path, "evdev_sha256": digest(evdev),
              "frame_probe_sha256": digest(executable), "frame_probe_source_sha256": digest((ROOT / "guest/fb_probe.c").read_bytes()),
              "cpu": "cortex-a72", "memory_mib": 1024, "vcpus": 4, "tcg_cache_mib": 256,
              "kernel": {"file": "vmlinuz-virt", "sha256": digest(kernel), "size": len(kernel)},
              "initramfs": {"file": "initramfs-ideck.gz", "sha256": digest(probe), "size": len(probe)},
              "frames_bgra_sha256": [digest(f) for f in frames],
              "purpose": "boot-display-input only; Alpine musl is not the Steam glibc rootfs"}
    (out / "profile.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--sevenzip", type=Path, required=True)
    parser.add_argument("--frame-probe", type=Path, required=True)
    args = parser.parse_args()
    prepare(args.archive, args.out, args.sevenzip, args.frame_probe)
