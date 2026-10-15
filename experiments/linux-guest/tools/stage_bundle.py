#!/usr/bin/env python3
"""Verify and copy only the three probe assets into an iOS resource directory.

Used both before source staging and by Xcode's resource build phase. No network,
archive extraction, arbitrary script execution or Steam redistribution.
"""
import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path

CONFIG = {"schema": 1, "width": 800, "height": 600, "cpu": "cortex-a72",
          "memory_mib": 1024, "vcpus": 4, "tcg_cache_mib": 256}


def regular(path, limit):
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= limit:
        raise ValueError("expected a bounded regular file: " + path.name)
    return path.read_bytes()


def verify(guest):
    if guest.is_symlink() or not guest.is_dir():
        raise ValueError("guest must be a real directory")
    raw = regular(guest / "profile.json", 65536)
    profile = json.loads(raw)
    if any(profile.get(key) != value or type(profile.get(key)) is not type(value)
           for key, value in CONFIG.items()):
        raise ValueError("unsupported machine configuration")
    files = {"profile.json": raw}
    for key, name in (("kernel", "vmlinuz-virt"), ("initramfs", "initramfs-ideck.gz")):
        asset = profile[key]
        if asset["file"] != name or type(asset["size"]) is not int:
            raise ValueError("unexpected guest asset name/size")
        data = regular(guest / name, 64 * 1024 * 1024)
        if len(data) != asset["size"] or hashlib.sha256(data).hexdigest() != asset["sha256"]:
            raise ValueError("asset integrity failure: " + name)
        files[name] = data
    return files


def stage(guest, destination):
    files = verify(guest)  # validate everything before any destination write
    if guest.resolve() == destination.resolve() or guest.resolve() in destination.resolve().parents:
        raise ValueError("destination must be outside the input guest directory")
    if destination.is_symlink():
        raise ValueError("destination is a symlink")
    # Refuse existing symlink ancestors too, rather than following a bundle
    # folder outside the caller's intended build product directory.
    if any(parent.is_symlink() for parent in destination.parents):
        raise ValueError("destination ancestor is a symlink")
    destination.mkdir(parents=True, exist_ok=True)
    for name in files:
        target = destination / name
        if target.is_symlink() or (target.exists() and not target.is_file()):
            raise ValueError("unsafe existing destination asset: " + name)
    for name, data in files.items():
        # Temp files are alongside the result (E on this workstation), never C.
        with tempfile.NamedTemporaryFile(dir=destination, prefix=".ideck-", delete=False) as handle:
            temporary = Path(handle.name)
            try:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            except BaseException:
                handle.close()
                temporary.unlink(missing_ok=True)
                raise
        try:
            os.replace(temporary, destination / name)
        finally:
            temporary.unlink(missing_ok=True)
    return {name: {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
            for name, data in files.items()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("guest", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    print(json.dumps(stage(args.guest, args.destination), indent=2))
