#!/usr/bin/env python3
"""Byte-preserving, bounded transport for already verified private CI ZIPs.

This module never extracts or executes archive contents. The reviewed consumer
must independently verify the resulting ZIP and its original product manifest.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import uuid
import zipfile

CHUNK_BYTES = 3 * 1024 * 1024
MAX_ZIP_BYTES = 128 * 1024 * 1024
MAX_MANIFEST_BYTES = 65536
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
HEX24 = re.compile(r"[0-9a-f]{24}\Z")
NAME = re.compile(r"[a-z][a-z0-9-]{0,63}\Z")


def require(ok, message):
    if not ok:
        raise ValueError(message)


def keys(value, wanted):
    require(isinstance(value, dict) and set(value) == set(wanted), "Unexpected manifest keys")


def integer(value, low, high):
    require(type(value) is int and low <= value <= high, "Invalid integer or size bound")


def digest(value, pattern=HEX64):
    require(isinstance(value, str) and pattern.fullmatch(value), "Invalid identity digest")


def no_duplicate_keys(pairs):
    obj = {}
    for key, value in pairs:
        require(key not in obj, "Duplicate JSON key")
        obj[key] = value
    return obj


def safe_directory(path):
    """Reject symlinks in every existing ancestor, including the directory."""
    path = Path(os.path.abspath(path))
    for part in [*reversed(path.parents), path]:
        require(stat.S_ISDIR(part.lstat().st_mode), "Directory missing, not a directory, or symlink")
    return path


def regular_fd(name, directory_fd):
    require(Path(name).name == name and name not in ("", ".", ".."), "Unsafe file name")
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory_fd)
    try:
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "File must be regular, not linked")
        return fd, info.st_size
    except BaseException:
        os.close(fd)
        raise


def read_regular(name, directory_fd, maximum):
    fd, size = regular_fd(name, directory_fd)
    with os.fdopen(fd, "rb") as stream:
        require(size <= maximum, "File exceeds bound")
        data = stream.read(maximum + 1)
        require(len(data) == size and len(data) <= maximum, "File changed or exceeded bound")
        return data


def validate_provenance(provenance):
    keys(provenance, ("stage", "build_id", "app_id", "bootstrap_commit", "source_commit",
                      "producer_manifest_path", "producer_manifest_sha256", "input_lock_sha256", "evidence_zip_sha256"))
    require(isinstance(provenance["stage"], str) and NAME.fullmatch(provenance["stage"]), "Invalid stage")
    for key in ("build_id", "app_id"):
        digest(provenance[key], HEX24)
    for key in ("bootstrap_commit", "source_commit"):
        digest(provenance[key], HEX40)
    manifest_path = provenance["producer_manifest_path"]
    require(isinstance(manifest_path, str) and len(manifest_path) <= 256
            and re.fullmatch(r"[A-Za-z0-9_./-]+\.json", manifest_path)
            and not manifest_path.startswith('/')
            and all(p not in ('', '.', '..') for p in manifest_path.split('/')),
            "Unsafe producer manifest path")
    for key in ("producer_manifest_sha256", "input_lock_sha256", "evidence_zip_sha256"):
        digest(provenance[key])


def validate_manifest(obj):
    keys(obj, ("schema", "original", "provenance", "chunk_bytes", "chunks"))
    require(type(obj["schema"]) is int and obj["schema"] == 2, "Unsupported schema")
    keys(obj["original"], ("name", "size", "sha256"))
    name = obj["original"]["name"]
    require(isinstance(name, str) and re.fullmatch(r"[a-z][a-z0-9-]{0,63}\.zip", name), "Unsafe original name")
    size = obj["original"]["size"]
    integer(size, 1, MAX_ZIP_BYTES)
    digest(obj["original"]["sha256"])
    validate_provenance(obj["provenance"])
    require(type(obj["chunk_bytes"]) is int and obj["chunk_bytes"] == CHUNK_BYTES, "Wrong chunk size")
    chunks = obj["chunks"]
    count = (size + CHUNK_BYTES - 1) // CHUNK_BYTES
    require(isinstance(chunks, list) and len(chunks) == count, "Missing, extra, or duplicate chunks")
    for index, item in enumerate(chunks):
        keys(item, ("index", "name", "offset", "size", "sha256"))
        integer(item["index"], index, index)
        require(item["name"] == f"chunk-{index:04d}.bin", "Unsafe, duplicated, or reordered chunk name")
        integer(item["offset"], index * CHUNK_BYTES, index * CHUNK_BYTES)
        wanted = min(CHUNK_BYTES, size - index * CHUNK_BYTES)
        integer(item["size"], wanted, wanted)
        digest(item["sha256"])
    return obj


def reassemble(package, expected_manifest_sha256, output):
    """Publish to a new file only after all chunk and whole-ZIP checks pass."""
    digest(expected_manifest_sha256)
    package = safe_directory(package)
    output = Path(os.path.abspath(output))
    parent = safe_directory(output.parent)
    require(output.parent != package, "Output must be outside input package")
    source_fd = os.open(package, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    dest_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    temporary = f".reassemble-{uuid.uuid4().hex}.part"
    created = False
    try:
        require(output.name not in os.listdir(dest_fd), "Output already exists")
        data = read_regular("manifest.json", source_fd, MAX_MANIFEST_BYTES)
        require(hashlib.sha256(data).hexdigest() == expected_manifest_sha256, "Manifest hash mismatch")
        obj = validate_manifest(json.loads(data, object_pairs_hook=no_duplicate_keys))
        names = {"manifest.json", *(item["name"] for item in obj["chunks"])}
        require(set(os.listdir(source_fd)) == names, "Missing or extra package entries")
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=dest_fd)
        created = True
        whole = hashlib.sha256()
        written = 0
        with os.fdopen(fd, "wb") as stream:
            for item in obj["chunks"]:
                chunk = read_regular(item["name"], source_fd, CHUNK_BYTES)
                require(len(chunk) == item["size"], "Chunk size mismatch")
                require(hashlib.sha256(chunk).hexdigest() == item["sha256"], "Chunk hash mismatch")
                whole.update(chunk)
                stream.write(chunk)
                written += len(chunk)
            require(written == obj["original"]["size"], "Whole ZIP size mismatch")
            require(whole.hexdigest() == obj["original"]["sha256"], "Whole ZIP hash mismatch")
            stream.flush()
            os.fsync(stream.fileno())
        # Atomic no-clobber publication. A raced destination causes failure.
        os.link(temporary, output.name, src_dir_fd=dest_fd, dst_dir_fd=dest_fd, follow_symlinks=False)
        return obj
    finally:
        if created:
            os.unlink(temporary, dir_fd=dest_fd)
        os.close(source_fd)
        os.close(dest_fd)


def split_original(original, expected_size, expected_sha256, provenance, package, original_name):
    """Local producer. Inputs must already have independent artifact verification."""
    integer(expected_size, 1, MAX_ZIP_BYTES)
    digest(expected_sha256)
    validate_provenance(provenance)
    original = Path(os.path.abspath(original))
    safe_directory(original.parent)
    package = Path(os.path.abspath(package))
    safe_directory(package.parent)
    package.mkdir()  # Fresh package only; no overwrite or partial input reuse.
    source_fd = os.open(original.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        fd, size = regular_fd(original.name, source_fd)
        with os.fdopen(fd, "rb") as stream:
            require(size == expected_size, "Original size mismatch")
            chunks = []
            whole = hashlib.sha256()
            offset = 0
            while offset < size:
                data = stream.read(min(CHUNK_BYTES, size - offset))
                require(len(data) == min(CHUNK_BYTES, size - offset), "Original changed during read")
                index = len(chunks)
                name = f"chunk-{index:04d}.bin"
                with (package / name).open("xb") as target:
                    target.write(data)
                chunks.append({"index": index, "name": name, "offset": offset, "size": len(data),
                               "sha256": hashlib.sha256(data).hexdigest()})
                whole.update(data)
                offset += len(data)
            require(stream.read(1) == b"", "Original grew during read")
            require(whole.hexdigest() == expected_sha256, "Original ZIP hash mismatch")
        # Producer-only cross-check against the already verified original ZIP.
        # The consumer stays a bounded byte transporter and never extracts ZIPs.
        with zipfile.ZipFile(original) as archive:
            name = provenance['producer_manifest_path']
            matches = [info for info in archive.infolist() if info.filename == name]
            require(len(matches) == 1, "Missing or duplicated original producer manifest")
            require(matches[0].file_size <= 4 * 1024 * 1024, "Producer manifest exceeds bound")
            with archive.open(matches[0]) as stream:
                data = stream.read(4 * 1024 * 1024 + 1)
            require(len(data) == matches[0].file_size, "Producer manifest size mismatch")
            require(hashlib.sha256(data).hexdigest() == provenance['producer_manifest_sha256'],
                    "Original producer manifest identity mismatch")
        obj = validate_manifest({"schema": 2, "original": {"name": original_name, "size": size,
                                  "sha256": expected_sha256}, "provenance": provenance,
                                 "chunk_bytes": CHUNK_BYTES, "chunks": chunks})
        data = (json.dumps(obj, sort_keys=True, indent=2) + "\n").encode()
        require(len(data) <= MAX_MANIFEST_BYTES, "Manifest exceeds bound")
        (package / "manifest.json").write_bytes(data)
        return hashlib.sha256(data).hexdigest()
    finally:
        os.close(source_fd)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = reassemble(args.package, args.manifest_sha256, args.output)
    print(json.dumps({"result": "byte-identical-original", "original": result["original"],
                      "provenance": result["provenance"]}, sort_keys=True))
