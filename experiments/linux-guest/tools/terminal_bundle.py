#!/usr/bin/env python3
"""Deterministic offline terminal resources; also runs standalone in Xcode.

No downloaded dependencies or external tools. The original probe is only read;
the terminal adds a compressed CPIO suffix and a preformatted empty FAT16 disk.
"""
import argparse
import gzip
import hashlib
import io
import json
import os
import stat
import struct
import tempfile
from pathlib import Path

DISK_SIZE = 128 * 1024 * 1024
SECTOR_SIZE = 512
TOTAL_SECTORS = DISK_SIZE // SECTOR_SIZE
SECTORS_PER_CLUSTER = 8
FAT_SECTORS = 128
ROOT_ENTRIES = 512
OUTPUT_NAMES = ("terminal-profile.json", "initramfs-terminal.gz", "userdata-seed.raw", "LICENSES-terminal.txt")
SCRIPT_NAMES = ("ideck-terminal-init", "ideck-terminal-login", "TERMINAL-LICENSES.txt")
CONFIG = {"schema": 1, "mode": "terminal", "width": 800, "height": 600,
          "cpu": "cortex-a72", "memory_mib": 1024, "vcpus": 4, "tcg_cache_mib": 256,
          "disk_size_bytes": DISK_SIZE, "filesystem": "fat16", "control_port": "org.ideck.control"}


def metadata(data):
    return {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def directory(path):
    path = Path(path)
    if path.is_symlink() or not path.is_dir() or any(p.is_symlink() for p in path.parents):
        raise ValueError("expected real directory without symlink ancestors")
    return path


def regular(path, limit):
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= limit:
        raise ValueError("expected bounded regular file: " + path.name)
    return path.read_bytes()


def checked(path, expected, limit):
    if not isinstance(expected, dict) or set(expected) != {"size", "sha256"} or type(expected["size"]) is not int:
        raise ValueError("invalid file receipt")
    data = regular(path, limit)
    if metadata(data) != expected:
        raise ValueError("integrity failure: " + path.name)
    return data


def load_lock(path):
    lock = json.loads(regular(Path(path), 65536))
    if type(lock.get("schema")) is not int or lock["schema"] != 1:
        raise ValueError("unsupported terminal lock")
    if set(lock["files"]) != set(OUTPUT_NAMES) or set(lock["inputs"]["scripts"]) != set(SCRIPT_NAMES):
        raise ValueError("unexpected terminal lock files")
    if set(lock["inputs"]["probe_files"]) != {"profile.json", "vmlinuz-virt", "initramfs-ideck.gz"}:
        raise ValueError("unexpected original probe inputs")
    return lock


def seed_bytes():
    """A superfloppy FAT16 volume: no MBR/partition offset or executable code."""
    reserved, fats = 1, 2
    root_sectors = (ROOT_ENTRIES * 32 + SECTOR_SIZE - 1) // SECTOR_SIZE
    data_sectors = TOTAL_SECTORS - reserved - fats * FAT_SECTORS - root_sectors
    clusters = data_sectors // SECTORS_PER_CLUSTER
    if not 4085 <= clusters < 65525 or FAT_SECTORS * SECTOR_SIZE // 2 < clusters + 2:
        raise ValueError("invalid FAT16 geometry")
    disk = bytearray(DISK_SIZE)
    disk[:11] = b"\xeb\x3c\x90IDECK001"
    struct.pack_into("<HBHBHHBHHHII", disk, 11, SECTOR_SIZE, SECTORS_PER_CLUSTER,
                     reserved, fats, ROOT_ENTRIES, 0, 0xf8, FAT_SECTORS,
                     32, 64, 0, TOTAL_SECTORS)
    struct.pack_into("<BBBI", disk, 36, 0x80, 0, 0x29, 0x49444543)
    disk[43:54] = b"IDECK DATA "
    disk[54:62] = b"FAT16   "
    disk[510:512] = b"\x55\xaa"
    for index in range(fats):
        offset = (reserved + index * FAT_SECTORS) * SECTOR_SIZE
        disk[offset:offset + 4] = b"\xf8\xff\xff\xff"
    return bytes(disk)


def cpio_entry(name, content, mode, inode):
    encoded = name.encode("ascii") + b"\0"
    fields = [inode, mode, 0, 0, 1, 0, len(content), 0, 0, 0, 0, len(encoded), 0]
    result = b"070701" + b"".join(f"{n:08x}".encode("ascii") for n in fields) + encoded
    result += b"\0" * (-len(result) % 4)
    result += content
    return result + b"\0" * (-len(result) % 4)


def build_files(probe, scripts):
    cpio = b""
    for inode, name in enumerate(SCRIPT_NAMES[:2], 1):
        cpio += cpio_entry(name, scripts[name], stat.S_IFREG | 0o755, inode)
    cpio += cpio_entry("TRAILER!!!", b"", 0, 3)
    stream = io.BytesIO()
    # Stored DEFLATE blocks avoid compressor-version heuristics for this small
    # suffix. GzipFile fixes filename/mtime/OS; original gzip bytes stay intact.
    with gzip.GzipFile(filename="", mode="wb", fileobj=stream, compresslevel=0, mtime=0) as compressor:
        compressor.write(cpio)
    ramdisk = probe["initramfs-ideck.gz"] + stream.getvalue()
    seed = seed_bytes()
    profile = dict(CONFIG)
    profile["kernel"] = {"file": "vmlinuz-virt", **metadata(probe["vmlinuz-virt"])}
    profile["initramfs"] = {"file": "initramfs-terminal.gz", **metadata(ramdisk)}
    profile["seed"] = {"file": "userdata-seed.raw", **metadata(seed)}
    return {"terminal-profile.json": (json.dumps(profile, sort_keys=True, indent=2) + "\n").encode("utf-8"),
            "initramfs-terminal.gz": ramdisk, "userdata-seed.raw": seed,
            "LICENSES-terminal.txt": scripts["TERMINAL-LICENSES.txt"]}


def verify_files(files):
    profile = json.loads(files["terminal-profile.json"])
    if any(type(profile.get(k)) is not type(v) or profile.get(k) != v for k, v in CONFIG.items()):
        raise ValueError("unsupported terminal configuration")
    for key, name in (("initramfs", "initramfs-terminal.gz"), ("seed", "userdata-seed.raw")):
        if profile.get(key) != {"file": name, **metadata(files[name])}:
            raise ValueError("terminal profile asset mismatch")
    if len(files["userdata-seed.raw"]) != DISK_SIZE:
        raise ValueError("incorrect persistent disk size")


def publish(files, destination, fresh=False):
    destination = Path(destination)
    if destination.is_symlink() or any(p.is_symlink() for p in destination.parents):
        raise ValueError("unsafe destination")
    if fresh and destination.exists():
        raise ValueError("preparation requires a new output directory")
    if destination.exists() and not destination.is_dir():
        raise ValueError("destination is not a directory")
    for name in files:
        path = destination / name
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise ValueError("unsafe destination asset")
    destination.mkdir(parents=True, exist_ok=not fresh)
    for name, data in files.items():
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=destination, prefix=".ideck-terminal-", delete=False) as handle:
                temporary = Path(handle.name)
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, destination / name)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    return {name: metadata(data) for name, data in files.items()}


def prepare(probe_guest, out, scripts=None, lock_path=None):
    here = Path(__file__).absolute().parent.parent
    scripts = directory(scripts if scripts is not None else here / "guest")
    probe_guest = directory(probe_guest)
    lock = load_lock(lock_path if lock_path is not None else here / "ipa/terminal.lock.json")
    probe = {name: checked(probe_guest / name, expected, 64 * 1024 * 1024)
             for name, expected in lock["inputs"]["probe_files"].items()}
    script_data = {name: checked(scripts / name, expected, 65536)
                   for name, expected in lock["inputs"]["scripts"].items()}
    files = build_files(probe, script_data)
    if {name: metadata(data) for name, data in files.items()} != lock["files"]:
        raise ValueError("generated terminal resources differ from lock")
    verify_files(files)
    if probe_guest.resolve() == Path(out).resolve() or probe_guest.resolve() in Path(out).resolve().parents:
        raise ValueError("output must be outside input assets")
    return publish(files, out, fresh=True)


def stage(source, destination, lock_path):
    source = directory(source)
    destination = Path(destination)
    if source.resolve() == destination.resolve() or source.resolve() in destination.resolve().parents:
        raise ValueError("destination must be outside source assets")
    lock = load_lock(lock_path)
    files = {name: checked(source / name, lock["files"][name], DISK_SIZE) for name in OUTPUT_NAMES}
    verify_files(files)
    return publish(files, destination)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    preparation = sub.add_parser("prepare")
    preparation.add_argument("probe_guest", type=Path)
    preparation.add_argument("out", type=Path)
    preparation.add_argument("--scripts", type=Path)
    preparation.add_argument("--lock", type=Path)
    staging = sub.add_parser("stage")
    staging.add_argument("source", type=Path)
    staging.add_argument("destination", type=Path)
    staging.add_argument("lock", type=Path)
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare(args.probe_guest, args.out, args.scripts, args.lock)
    else:
        result = stage(args.source, args.destination, args.lock)
    print(json.dumps(result, sort_keys=True, indent=2))
