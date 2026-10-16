#!/usr/bin/env python3
"""Resolve ext4 from the original locked Alpine modloop; never guess its closure.

Offline only. Supply an already downloaded archive and a trusted unsquashfs
executable. The output is build input, not permission to publish a guest payload.
The archive SHA authenticates module bytes. Signature checks below validate the
PKCS#7 container, not a public-key trust chain; kernel acceptance needs a boot.
"""
import argparse
import hashlib
import json
import re
import struct
import subprocess
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

import prepare_guest

KERNEL = "6.18.35-0-virt"
VERMAGIC = KERNEL + " SMP preempt mod_unload modversions aarch64"
MODLOOP_SHA256 = "f969d12c8e23b486c8df651f04a4a9767f32fee16aed385c23462c31ea6cb47b"
KERNEL_SHA256 = "47970e0ee0478fe5c60824a89f162d5a353fa29466e5d3bddb0f9c506f1ed756"
SIGNATURE_MARKER = b"~Module signature appended~\n"
MODULE_PREFIX = f"modules/{KERNEL}/"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def module_path(value):
    path = PurePosixPath(value)
    if (not re.fullmatch(r"kernel/(?:[A-Za-z0-9_.+-]+/)*[A-Za-z0-9_.+-]+\.ko", value)
            or value != path.as_posix() or path.is_absolute()
            or any(part in (".", "..") for part in path.parts)
            or not value.startswith("kernel/") or not value.endswith(".ko")):
        raise ValueError("unsafe or unsupported module path")
    return value


def module_name(path):
    return PurePosixPath(path).name.removesuffix(".ko").replace("-", "_")


def dependencies(data):
    result = {}
    for line in data.decode("utf-8").splitlines():
        if not line:
            continue
        if line.count(":") != 1:
            raise ValueError("malformed modules.dep")
        path, refs = line.split(":")
        path = module_path(path)
        if path in result:
            raise ValueError("duplicate modules.dep entry")
        result[path] = [module_path(ref) for ref in refs.split()]
    for refs in result.values():
        if any(ref not in result for ref in refs):
            raise ValueError("missing modules.dep dependency")
    return result


def soft_dependencies(data):
    result = {}
    for line in data.decode("utf-8").splitlines():
        fields = line.split()
        if not fields or fields[0].startswith("#"):
            continue
        if (len(fields) < 3 or fields[0] != "softdep"
                or not re.fullmatch(r"[A-Za-z0-9_-]+", fields[1])
                or fields[1].replace("-", "_") in result):
            raise ValueError("malformed modules.softdep")
        pre, post, target = [], [], None
        for item in fields[2:]:
            if item in ("pre:", "post:"):
                target = pre if item == "pre:" else post
            elif target is None or not item.replace("_", "").replace("-", "").isalnum():
                raise ValueError("malformed soft dependency")
            else:
                target.append(item.replace("-", "_"))
        result[fields[1].replace("-", "_")] = (pre, post)
    return result


def closure(dep, soft, builtin, requested="ext4"):
    names = {}
    for path in dep:
        name = module_name(path)
        if name in names:
            raise ValueError("ambiguous module name")
        names[name] = path
    builtins = {module_name(module_path(p)) for p in builtin.decode().splitlines() if p}
    ordered, active, seen = [], set(), set()

    def visit(name):
        if name in seen or name in builtins:
            return
        if name not in names or name in active:
            raise ValueError("missing or cyclic module dependency")
        active.add(name)
        path = names[name]
        pre, post = soft.get(name, ([], []))
        for item in pre:
            visit(item)
        for item in dep[path]:
            visit(module_name(item))
        active.remove(name)
        seen.add(name)
        ordered.append(path)
        for item in post:
            visit(item)

    visit(requested)
    if not ordered:
        raise ValueError("expected loadable ext4 in this pinned kernel")
    return ordered


def module_metadata(data):
    # Parse the real .modinfo section, never accept a stray vermagic string.
    if (len(data) < 64 or data[:7] != b"\x7fELF\x02\x01\x01"
            or struct.unpack_from("<HH", data, 16) != (1, 183)):
        raise ValueError("module is not relocatable AArch64 ELF64")
    offset = struct.unpack_from("<Q", data, 40)[0]
    width, count, names_index = struct.unpack_from("<HHH", data, 58)
    if width != 64 or not count or names_index >= count or offset + width * count > len(data):
        raise ValueError("invalid module section table")

    def section(index):
        start, size = struct.unpack_from("<QQ", data, offset + index * width + 24)
        if start + size > len(data):
            raise ValueError("invalid module section bounds")
        return data[start:start + size]

    names = section(names_index)
    info = []
    for index in range(count):
        name = struct.unpack_from("<I", data, offset + index * width)[0]
        if name >= len(names):
            raise ValueError("invalid module section name")
        if names[name:].split(b"\0", 1)[0] == b".modinfo":
            info.append(section(index))
    if len(info) != 1:
        raise ValueError("missing or duplicate .modinfo")
    fields = [field.decode("ascii") for field in info[0].split(b"\0") if field]
    vermagic = [field[9:] for field in fields if field.startswith("vermagic=")]
    if vermagic != [VERMAGIC]:
        raise ValueError("module vermagic differs from pinned kernel")
    depends = [field[8:] for field in fields if field.startswith("depends=")]
    if len(depends) != 1:
        raise ValueError("missing or duplicate module depends")
    if not data.endswith(SIGNATURE_MARKER):
        raise ValueError("missing module signature")
    trailer = len(data) - len(SIGNATURE_MARKER) - 12
    if trailer < 64:
        raise ValueError("truncated module signature")
    algorithm, hash_id, kind, signer, key, pad, length = struct.unpack_from(">BBBBB3sI", data, trailer)
    if kind != 2 or pad != b"\0\0\0" or not length or trailer - length - signer - key < 64:
        raise ValueError("invalid PKCS#7 module signature container")
    signature = data[trailer - length:trailer]
    if len(signature) < 2 or signature[0] != 0x30:
        raise ValueError("module signature is not DER sequence")
    header_size, payload_size = 2, signature[1]
    if payload_size & 0x80:
        length_bytes = payload_size & 0x7f
        if not 1 <= length_bytes <= 4 or len(signature) < 2 + length_bytes:
            raise ValueError("invalid DER signature length")
        header_size += length_bytes
        payload_size = int.from_bytes(signature[2:header_size], "big")
    if header_size + payload_size != len(signature):
        raise ValueError("truncated DER signature")
    return {"vermagic": vermagic[0], "depends": sorted(filter(None, depends[0].split(","))),
            "signature": {"kind": "PKCS#7", "size": length, "sha256": sha(signature),
                          "algorithm_id": algorithm, "hash_id": hash_id,
                          "public_key_verification": "not_performed; locked archive authenticates bytes"}}


def cat_image(tool, image, path, limit, allow_empty=False):
    data = subprocess.check_output([str(tool), "-cat", str(image), path], timeout=60,
                                   stderr=subprocess.DEVNULL)
    if (not data and not allow_empty) or len(data) > limit:
        raise ValueError("unexpected squashfs member size")
    return data


def prepare(archive, out, unsquashfs):
    if out.exists():
        raise ValueError("output already exists")
    digest = hashlib.sha256()
    size = 0
    with archive.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            size += len(chunk)
            digest.update(chunk)
    if size != prepare_guest.SIZE or digest.hexdigest() != prepare_guest.SHA256:
        raise ValueError("archive differs from locked upstream bytes")
    with tempfile.TemporaryDirectory(prefix="ideck-modules-", dir=out.parent) as temporary:
        image = Path(temporary) / "modloop-virt"
        with tarfile.open(archive) as source:
            for name, maximum, expected in (
                    ("boot/vmlinuz-virt", 16 * 1024**2, KERNEL_SHA256),
                    ("boot/modloop-virt", 512 * 1024**2, MODLOOP_SHA256)):
                entries = [item for item in source.getmembers() if item.name == name]
                if len(entries) != 1 or not entries[0].isreg() or entries[0].size > maximum:
                    raise ValueError("unexpected archive member")
                data = source.extractfile(entries[0]).read(maximum + 1)
                if sha(data) != expected:
                    raise ValueError("kernel/modloop hash differs")
                if name.endswith("modloop-virt"):
                    image.write_bytes(data)
        metadata = {name: cat_image(unsquashfs, image, MODULE_PREFIX + name, 8 * 1024**2,
                                    allow_empty=name == "modules.softdep")
                    for name in ("modules.dep", "modules.softdep", "modules.builtin")}
        dep = dependencies(metadata["modules.dep"])
        paths = closure(dep, soft_dependencies(metadata["modules.softdep"]), metadata["modules.builtin"])
        modules, contents = [], {}
        for path in paths:
            data = cat_image(unsquashfs, image, MODULE_PREFIX + path, 16 * 1024**2)
            info = module_metadata(data)
            # depmod can list transitives as well as direct modinfo dependencies.
            expected = {module_name(p) for p in dep[path]}
            if not {name.replace("-", "_") for name in info["depends"]} <= expected:
                raise ValueError("ELF dependencies differ from modules.dep")
            modules.append({"path": path, "size": len(data), "sha256": sha(data), **info})
            contents[path] = data
        manifest = {"schema": 1, "kernel_release": KERNEL, "kernel_sha256": KERNEL_SHA256,
                    "archive_url": prepare_guest.URL, "archive_size": size,
                    "archive_sha256": digest.hexdigest(), "modloop_sha256": MODLOOP_SHA256,
                    "metadata": {name: {"sha256": sha(data), "size": len(data)}
                                 for name, data in metadata.items()},
                    "load_order": paths, "modules": modules,
                    "total_module_bytes": sum(item["size"] for item in modules),
                    "kernel_load_and_ext4_mount": "not_tested"}
        out.mkdir()
        for path, data in contents.items():
            target = out / MODULE_PREFIX / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        for name, data in metadata.items():
            (out / MODULE_PREFIX / name).write_bytes(data)
        (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--unsquashfs", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.archive, args.out, args.unsquashfs), indent=2))
