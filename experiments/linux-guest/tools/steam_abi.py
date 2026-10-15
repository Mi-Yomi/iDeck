#!/usr/bin/env python3
"""Inspect (never execute) the official Steam Linux ARM64 payload.

Only Valve's HTTPS CDN is used. Every ZIP must match its manifest SHA-256 and
size before it is opened. Proprietary downloads stay in the ignored work dir.
The result is static ABI evidence, not a dependency-closure or runtime pass.
"""
import argparse
import hashlib
import json
import re
import struct
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

CDN = "https://client-update.fastly.steamstatic.com/"
MANIFEST = "steam_client_steamdeck_publicbeta_linuxarm64"
MAX_PACKAGE = 512 * 1024 * 1024
MACHINES = {3: "i386", 40: "ARM", 62: "x86_64", 183: "AArch64"}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def packages(data):
    text = data.decode("utf-8")
    version = re.search(r'"version"\s+"([0-9]+)"', text)
    if not version or not re.match(r'\s*"linuxarm64"\s*\{', text):
        raise ValueError("unexpected Steam manifest")
    found = {}
    for name, body in re.findall(r'\t"([^"\n]+)"\s*\{([^{}]+)\}', text):
        fields = dict(re.findall(r'"([^"\n]+)"\s+"([^"\n]*)"', body))
        if name in found:
            raise ValueError("duplicate package")
        filename, digest = fields.get("file", ""), fields.get("sha2", "")
        size = int(fields.get("size", "0"))
        if not re.fullmatch(r"[a-zA-Z0-9_.-]+", filename) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("invalid package filename/hash")
        if not 0 < size <= MAX_PACKAGE:
            raise ValueError("package exceeds bounded download limit")
        found[name] = {"file": filename, "sha256": digest, "size": size}
    if not found:
        raise ValueError("no manifest packages")
    return version[1], found


def download(url, path, size=None, digest=None):
    if path.exists():
        data = path.read_bytes()
        if size is not None and len(data) == size and sha256(data) == digest:
            return data
        raise ValueError(f"existing input is not the requested verified file: {path}")
    partial = path.with_name(path.name + ".partial")
    # A stopped transfer is evidence, and is not silently overwritten.
    with urllib.request.urlopen(url, timeout=60) as response, partial.open("xb") as out:
        if not response.url.startswith(CDN):
            raise ValueError("unexpected CDN redirect")
        count = 0
        while chunk := response.read(1024 * 1024):
            count += len(chunk)
            if count > (size if size is not None else 1024 * 1024):
                raise ValueError("download exceeds declared size")
            out.write(chunk)
    data = partial.read_bytes()
    if size is not None and (len(data) != size or sha256(data) != digest):
        raise ValueError("package size/SHA-256 mismatch")
    partial.rename(path)
    return data


def elf(data):
    if len(data) < 52 or data[:4] != b"\x7fELF" or data[4] not in (1, 2) or data[5] not in (1, 2):
        raise ValueError("invalid ELF header")
    bits = 64 if data[4] == 2 else 32
    order = "<" if data[5] == 1 else ">"

    def unpack(fmt, offset):
        if offset < 0 or offset + struct.calcsize(order + fmt) > len(data):
            raise ValueError("truncated ELF structure")
        return struct.unpack_from(order + fmt, data, offset)

    def region(offset, size):
        if offset < 0 or size < 0 or offset + size > len(data):
            raise ValueError("ELF segment outside file")
        return data[offset:offset + size]

    def cstring(raw, offset=0):
        if not 0 <= offset < len(raw):
            raise ValueError("invalid ELF string offset")
        end = raw.find(b"\0", offset)
        if end < 0:
            raise ValueError("unterminated ELF string")
        return raw[offset:end].decode("utf-8", errors="strict")

    header = unpack("HHIQQQIHHHHHH" if bits == 64 else "HHIIIIIHHHHHH", 16)
    e_type, machine = header[:2]
    phoff, phsize, phnum = header[4], header[8], header[9]
    expected = 56 if bits == 64 else 32
    if phnum == 0xffff or (phnum and phsize != expected):
        raise ValueError("unsupported ELF program header layout")
    segments, interp, dynamic = [], None, []
    for i in range(phnum):
        values = unpack("IIQQQQQQ" if bits == 64 else "IIIIIIII", phoff + i * phsize)
        if bits == 64:
            kind, _, offset, va, _, filesz, _, _ = values
        else:
            kind, offset, va, _, filesz, _, _, _ = values
        raw = region(offset, filesz)
        if kind == 1:
            segments.append((va, offset, filesz))
        if kind == 3:
            interp = cstring(raw)
        if kind == 2:
            step = 16 if bits == 64 else 8
            if filesz % step:
                raise ValueError("invalid dynamic table size")
            for pos in range(offset, offset + filesz, step):
                tag, value = unpack("qQ" if bits == 64 else "iI", pos)
                if tag == 0:
                    break
                dynamic.append((tag, value))
    table = dict(dynamic)
    strings = b""
    if 5 in table:
        address, length = table[5], table.get(10, 0)
        for va, off, size in segments:
            if va <= address and address + length <= va + size:
                strings = region(off + address - va, length)
                break
        if not strings:
            raise ValueError("dynamic string table is not file-backed")
    needed = [cstring(strings, value) for tag, value in dynamic if tag == 1]
    return {"class": f"ELF{bits}", "endian": "little" if order == "<" else "big",
            "machine": MACHINES.get(machine, str(machine)), "e_machine": machine,
            "elf_type": e_type, "interpreter": interp, "needed": needed,
            "soname": cstring(strings, table[14]) if 14 in table else None,
            "rpath": cstring(strings, table[15]) if 15 in table else None,
            "runpath": cstring(strings, table[29]) if 29 in table else None,
            "size": len(data), "sha256": sha256(data)}


def inspect(work, manifest_path):
    work.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_path or work / MANIFEST
    if not manifest_path.exists():
        download(CDN + MANIFEST, manifest_path)
    manifest = manifest_path.read_bytes()
    version, all_packages = packages(manifest)
    selected = {k: v for k, v in all_packages.items() if k.endswith("_linuxarm64_linuxarm64")}
    if not selected:
        raise ValueError("no DroidDeck-selected ARM64 binary packages")
    report = {"schema": 1, "manifest_url": CDN + MANIFEST, "manifest_sha256": sha256(manifest),
              "version": version, "packages": [], "elf_files": [], "non_elf_entries": [],
              "scope": "ARM64 binary packages only; common assets and game/runtime closure excluded",
              "executed": False, "dependency_closure_verified": False}
    extracted = work / "key-elf"
    extracted.mkdir(exist_ok=True)
    for name, p in sorted(selected.items()):
        print(f"Verifying {name} ({p['size']} bytes)", flush=True)
        package = work / p["file"]
        download(CDN + p["file"], package, p["size"], p["sha256"])
        report["packages"].append({"name": name, "url": CDN + p["file"], **p})
        with zipfile.ZipFile(package) as archive:
            for info in archive.infolist():
                path = PurePosixPath(info.filename.replace("\\", "/"))
                if path.is_absolute() or ".." in path.parts or any(":" in part for part in path.parts):
                    raise ValueError("unsafe ZIP path")
                if info.is_dir():
                    continue
                if info.file_size > MAX_PACKAGE:
                    raise ValueError("oversized ZIP entry")
                with archive.open(info) as source:
                    prefix = source.read(4)
                    if prefix != b"\x7fELF":
                        report["non_elf_entries"].append({"path": str(path), "size": info.file_size})
                        continue
                    content = prefix + source.read(MAX_PACKAGE)
                record = {"package": name, "path": str(path), **elf(content)}
                report["elf_files"].append(record)
                if path.name in ("steam", "steamwebhelper", "libcef.so") or path.name.startswith("ld-linux"):
                    target = extracted.joinpath(*path.parts)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if target.exists() and target.read_bytes() != content:
                        raise ValueError("conflicting key ELF payload")
                    target.write_bytes(content)
    keys = [f for f in report["elf_files"] if PurePosixPath(f["path"]).name in ("steam", "steamwebhelper", "libcef.so")]
    report["key_elfs"] = keys
    report["key_abi_status"] = "aarch64_observed" if {PurePosixPath(f["path"]).name for f in keys} == {"steam", "steamwebhelper", "libcef.so"} and all(f["e_machine"] == 183 for f in keys) else "requires_review"
    (work / "steam-abi.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["key_abi_status"], "elf_count": len(report["elf_files"]),
                      "keys": [{"path": f["path"], "machine": f["machine"], "interpreter": f["interpreter"]} for f in keys]}))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    inspect(args.work, args.manifest)
