#!/usr/bin/env python3
"""Reconstruct the exact upstream Swift/header slice for an offline SDK check.

This is not a runtime source export: native QEMU and other linked libraries
remain external build prerequisites. Every included file is pinned upstream.
"""
import hashlib
import json
import subprocess
import tarfile
from pathlib import Path
from stage_husk import ROOT, PIN, load_overlay, local_path


def restore(output):
    lock = json.loads((ROOT / "husk/source-check.lock.json").read_text())
    if lock["commit"] != PIN or lock["archive"] != "husk119-source-check.tar.gz":
        raise ValueError("unexpected source slice identity")
    archive = ROOT / "husk" / lock["archive"]
    raw = archive.read_bytes()
    if len(raw) != lock["archive_size"] or hashlib.sha256(raw).hexdigest() != lock["archive_sha256"]:
        raise ValueError("source archive integrity failure")
    if output.exists() or output.is_symlink():
        raise ValueError("source slice output must be new")
    files = {}
    with tarfile.open(archive) as source:
        for entry in source:
            if entry.name not in lock["files"] or entry.name in files or not entry.isfile():
                raise ValueError("unexpected/duplicate/non-regular source member")
            expected = lock["files"][entry.name]
            if entry.size != expected["size"] or not 0 < entry.size <= 2 * 1024 * 1024:
                raise ValueError("source member size mismatch")
            data = source.extractfile(entry).read()
            blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
            if hashlib.sha256(data).hexdigest() != expected["sha256"] or blob != expected["git_blob"]:
                raise ValueError("source member hash mismatch")
            local_path(output, entry.name)
            files[entry.name] = data
    if set(files) != set(lock["files"]):
        raise ValueError("incomplete source slice")
    output.mkdir(parents=True, exist_ok=False)
    for name, data in files.items():
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return lock


def overlay(output):
    lock = load_overlay()
    # A scratch index makes git apply independent of the enclosing transport
    # repository. No fabricated upstream commit or stub runtime types are used.
    def git(*args):
        subprocess.run(["git", "-c", "core.autocrlf=false", "-C", str(output), *args],
                       check=True, capture_output=True, timeout=30)
    git("init", "--quiet")
    git("add", ".")
    patches = (ROOT / "husk/patches/series").read_text().splitlines()
    git("apply", "--check", *[str(ROOT / "husk/patches" / p) for p in patches])
    git("apply", "--index", *[str(ROOT / "husk/patches" / p) for p in patches])
    for name, expected in lock["patched_files"].items():
        if hashlib.sha256((output / name).read_bytes()).hexdigest() != expected:
            raise ValueError("unexpected patched source hash")
    for source, destination in lock["copies"].items():
        target = local_path(output, destination)
        if target.exists():
            raise ValueError("overlay would replace a source file")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(local_path(ROOT, source).read_bytes())


def swift_sources(output):
    return sorted((output / "src/app/Husk").rglob("*.swift")) + sorted(
        (output / "src/app/Shared").rglob("*.swift")) + [output / "src/app/HuskJITHelper/HuskJITMessages.swift"]
