#!/usr/bin/env python3
"""Exact Debian payload transport and Xcode resources; stdlib, no system installs.

The committed lock is the trust root. A private HTTPS URL is only a transport;
its value (possibly a signed credential) is never included in receipts/logs.
"""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tarfile
import tempfile
import time
import urllib.request
import urllib.parse

NAMES = {"vmlinuz-virt", "initramfs-debian.gz", "rootfs-v1.raw",
         "desktop-rootfs-profile.json", "debian-profile.json", "LICENSES-debian.txt"}


def prepare(seed, modules, output, lock_path):
    """Offline reproducible rebuild; all inputs and outputs must match the lock."""
    lock = load_lock(lock_path)
    experiment = Path(__file__).resolve().parents[1]
    for name, expected in lock["inputs"]["seed"].items(): checked(seed / name, expected)
    checked(modules / "manifest.json", lock["inputs"]["modules"])
    for name, expected in lock["inputs"]["guest"].items(): checked(experiment / "guest" / name, expected)
    output.mkdir(parents=True, exist_ok=False)
    from check_debian_ext4_boot import prepare_boot
    receipt = prepare_boot(output, modules, production=True)
    bundle = output / "bundle"
    bundle.mkdir()
    for name in ("vmlinuz-virt", "initramfs-debian.gz"): shutil.copyfile(output / name, bundle / name)
    for name in ("rootfs-v1.raw", "desktop-rootfs-profile.json"): shutil.copyfile(seed / name, bundle / name)
    shutil.copyfile(experiment / "guest/DEBIAN-LICENSES.txt", bundle / "LICENSES-debian.txt")
    profile = {"schema": 1, "mode": "debian", "control_port": "org.ideck.control",
               "kernel": {"file": "vmlinuz-virt", **metadata(bundle / "vmlinuz-virt")},
               "initramfs": {"file": "initramfs-debian.gz", **metadata(bundle / "initramfs-debian.gz")}}
    (bundle / "debian-profile.json").write_text(json.dumps(profile, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    verify(bundle, lock)
    archive = output / lock["payload"]["filename"]
    transport = {name: bundle / name for name in NAMES - {"rootfs-v1.raw"}}
    transport["rootfs-v1.raw.gz"] = seed / "rootfs-v1.raw.gz"
    with tarfile.open(archive, "w", format=tarfile.USTAR_FORMAT) as tar:
        for name, path in sorted(transport.items()):
            checked(path, lock["transport_files"][name])
            info = tarfile.TarInfo(name); info.size = path.stat().st_size; info.mode = 0o644
            with path.open("rb") as stream: tar.addfile(info, stream)
    checked(archive, {k: lock["payload"][k] for k in ("size", "sha256")})
    return receipt


def metadata(path):
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"size": path.stat().st_size, "sha256": digest}


def real_directory(path):
    if path.is_symlink() or any(p.is_symlink() for p in path.parents) or not path.is_dir():
        raise ValueError("unsafe Debian directory")


def safe_destination(path):
    if path.is_symlink() or any(p.is_symlink() for p in path.parents):
        raise ValueError("unsafe Debian destination ancestors")


def checked(path, expected):
    if path.is_symlink() or not path.is_file() or metadata(path) != expected:
        raise ValueError("Debian integrity mismatch: " + path.name)


def load_lock(path):
    lock = json.loads(path.read_text(encoding="utf-8"))
    if lock["schema"] != 1 or set(lock["files"]) != NAMES:
        raise ValueError("unsupported Debian payload lock")
    return lock


class HTTPSOnlyRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urllib.parse.urlsplit(newurl).scheme != "https":
            raise ValueError("payload redirect is not HTTPS")
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected is not None:
            # GitHub hands back a signed asset URL; never forward the API token.
            redirected.remove_header("Authorization")
        return redirected


def verify(source, lock):
    real_directory(source)
    if {p.name for p in source.iterdir()} != NAMES:
        raise ValueError("Debian bundle must contain exactly the locked files")
    for name, expected in lock["files"].items():
        checked(source / name, expected)
    return lock["files"]


def stage(source, destination, lock_path):
    lock = load_lock(lock_path)
    verify(source, lock)
    if destination.resolve() == source.resolve() or source.resolve() in destination.resolve().parents:
        raise ValueError("Debian destination overlaps source")
    safe_destination(destination)
    destination.mkdir(parents=True, exist_ok=True)
    real_directory(destination)
    if any(p.name not in NAMES or p.is_symlink() or not p.is_file() for p in destination.iterdir()):
        raise ValueError("unexpected Debian destination contents")
    for name in sorted(NAMES):
        fd, temporary = tempfile.mkstemp(prefix=".debian-stage-", dir=destination)
        try:
            with os.fdopen(fd, "wb") as target, (source / name).open("rb") as origin:
                shutil.copyfileobj(origin, target, 1024 * 1024)
                target.flush(); os.fsync(target.fileno())
            checked(Path(temporary), lock["files"][name])
            os.replace(temporary, destination / name)
        finally:
            Path(temporary).unlink(missing_ok=True)
    return verify(destination, lock)


def restore(archive, destination, lock_path):
    lock = load_lock(lock_path)
    checked(archive, {k: lock["payload"][k] for k in ("size", "sha256")})
    safe_destination(destination)
    if destination.exists() or destination.is_symlink():
        raise ValueError("Debian restore destination must be new")
    # Validate the ENTIRE flat archive before writing. No extraction of links,
    # devices, duplicates, traversal or unbounded decompressed content.
    expected = (NAMES - {"rootfs-v1.raw"}) | {"rootfs-v1.raw.gz"}
    with tarfile.open(archive, "r:") as tar:
        members = tar.getmembers()
        if (len(members) != len(expected) or {m.name for m in members} != expected
                or any(not m.isfile() or m.size != lock["transport_files"][m.name]["size"] for m in members)):
            raise ValueError("unexpected Debian payload members")
        destination.mkdir(parents=True)
        real_directory(destination)
        if shutil.disk_usage(destination).free < (sum(x["size"] for x in lock["files"].values())
                + lock["transport_files"]["rootfs-v1.raw.gz"]["size"] + 64 * 1024**2):
            raise ValueError("insufficient space for Debian bundle")
        for member in members:
            path = destination / member.name
            with path.open("xb") as target, tar.extractfile(member) as origin:
                shutil.copyfileobj(origin, target, 1024 * 1024)
            checked(path, lock["transport_files"][member.name])
        compressed = destination / "rootfs-v1.raw.gz"
        expected_size = lock["files"]["rootfs-v1.raw"]["size"]
        count = 0
        with gzip.open(compressed, "rb") as origin, (destination / "rootfs-v1.raw").open("xb") as target:
            while chunk := origin.read(1024 * 1024):
                count += len(chunk)
                if count > expected_size:
                    raise ValueError("Debian seed exceeds locked size")
                target.write(chunk)
        checked(destination / "rootfs-v1.raw", lock["files"]["rootfs-v1.raw"])
        compressed.unlink()
    return verify(destination, lock)


def fetch(destination, lock_path):
    lock = load_lock(lock_path)
    url = os.environ.get("IDECK_DEBIAN_PAYLOAD_URL", "")
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("set IDECK_DEBIAN_PAYLOAD_URL to the private exact payload HTTPS URL")
    if destination.exists() or destination.is_symlink():
        raise ValueError("payload download destination must be new")
    safe_destination(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    real_directory(destination.parent)
    request = urllib.request.Request(url, headers={"Accept": "application/octet-stream"})
    token = os.environ.get("IDECK_DEBIAN_PAYLOAD_TOKEN", "")
    if token:
        if (parsed.hostname != "api.github.com" or parsed.port not in (None, 443)
                or parsed.query or parsed.fragment
                or not re.fullmatch(r"/repos/Mi-Yomi/iDeck/releases/assets/[0-9]+", parsed.path)):
            raise ValueError("payload token is restricted to Mi-Yomi/iDeck GitHub release asset API")
        request.add_unredirected_header("Authorization", "Bearer " + token)
    fd, temporary = tempfile.mkstemp(prefix=".debian-download-", dir=destination.parent)
    try:
        count = 0
        deadline = time.monotonic() + 300
        with os.fdopen(fd, "wb") as target, urllib.request.build_opener(HTTPSOnlyRedirect).open(request, timeout=60) as response:
            while chunk := response.read(1024 * 1024):
                if time.monotonic() > deadline:
                    raise TimeoutError("payload download deadline exceeded")
                count += len(chunk)
                if count > lock["payload"]["size"]:
                    raise ValueError("payload exceeds locked size")
                target.write(chunk)
        checked(Path(temporary), {k: lock["payload"][k] for k in ("size", "sha256")})
        os.link(temporary, destination)
    except Exception:
        # URL/error representations can contain signed secrets.
        raise RuntimeError("Debian payload download/integrity check failed; URL omitted") from None
    finally:
        Path(temporary).unlink(missing_ok=True)
    return {k: lock["payload"][k] for k in ("size", "sha256")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("fetch", "restore", "stage", "verify", "prepare"))
    parser.add_argument("source", type=Path)
    parser.add_argument("lock", type=Path)
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--modules", type=Path)
    args = parser.parse_args()
    if args.command in ("stage", "restore") and args.destination is None:
        parser.error("--destination is required")
    if args.command == "prepare":
        if args.destination is None or args.modules is None: parser.error("--destination and --modules required")
        result = prepare(args.source, args.modules, args.destination, args.lock)
    elif args.command == "fetch": result = fetch(args.source, args.lock)
    elif args.command == "verify": result = verify(args.source, load_lock(args.lock))
    else: result = globals()[args.command](args.source, args.destination, args.lock)
    print(json.dumps(result, indent=2))
