#!/usr/bin/env python3
"""Reconstruct an audited source tree from pinned public upstream + private diff.

This intentionally does not claim to mirror the original iDeck commit history.
No runtime binaries, credentials, SDKs or untracked work are imported.
"""
import gzip
import hashlib
import io
import json
import os
import re
import subprocess
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = "https://github.com/playportdev/playport.git"
BASE = "412de5f8c0bdd26d84e0127eb5776ba992e3b152"
MADEIRA = "8c050d03f4d89096e1e2e2c8bb44479fffd86619"
DEST = ROOT / ".work" / "source"


def run(*args, cwd=None):
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    return subprocess.check_output(args, cwd=cwd, text=True, timeout=180, env=env).strip()


def decompress(data, limit):
    with gzip.GzipFile(fileobj=io.BytesIO(data)) as stream:
        result = stream.read(limit + 1)
    if len(result) > limit:
        raise SystemExit("Compressed source input exceeds decompressed size limit")
    return result


def reconstruct():
    manifest = json.loads((ROOT / "source-manifest.json").read_text())
    if manifest.get("schema") != 1 or manifest.get("upstream_url") != UPSTREAM or manifest.get("base_commit") != BASE:
        raise SystemExit("Unrecognized source manifest baseline")
    for key in ("source_commit", "source_tree", "madeira_commit"):
        if not re.fullmatch(r"[0-9a-f]{40}", manifest.get(key, "")):
            raise SystemExit(f"Invalid manifest {key}")
    compressed = (ROOT / "source.patch.gz").read_bytes()
    if hashlib.sha256(compressed).hexdigest() != manifest.get("compressed_patch_sha256"):
        raise SystemExit("Compressed source patch SHA-256 mismatch")
    if manifest["madeira_commit"] != MADEIRA:
        raise SystemExit("Unapproved Madeira pin")
    patch_bytes = decompress(compressed, 50 * 1024 * 1024)
    if hashlib.sha256(patch_bytes).hexdigest() != manifest.get("patch_sha256"):
        raise SystemExit("Source patch SHA-256 or size mismatch")
    if DEST.exists():
        raise SystemExit(f"Refusing to reuse existing reconstructed checkout: {DEST}")
    DEST.parent.mkdir(parents=True, exist_ok=True)
    patch = DEST.parent / "source.patch"
    patch.write_bytes(patch_bytes)
    run("git", "init", "--quiet", str(DEST))
    run("git", "remote", "add", "upstream", UPSTREAM, cwd=DEST)
    run("git", "fetch", "--depth=1", "upstream", BASE, cwd=DEST)
    run("git", "-c", "core.hooksPath=/dev/null", "checkout", "--quiet", "--detach", "FETCH_HEAD", cwd=DEST)
    if run("git", "rev-parse", "HEAD", cwd=DEST) != BASE:
        raise SystemExit("Fetched upstream commit mismatch")
    run("git", "apply", "--check", "--index", str(patch), cwd=DEST)
    run("git", "apply", "--index", str(patch), cwd=DEST)
    actual_tree = run("git", "write-tree", cwd=DEST)
    if actual_tree != manifest["source_tree"]:
        raise SystemExit(f"Reconstructed tree mismatch: {actual_tree}")
    run("git", "diff", "--exit-code", cwd=DEST)
    module = run("git", "ls-files", "--stage", "upstream/madeira", cwd=DEST).split()
    if module[:2] != ["160000", manifest["madeira_commit"]]:
        raise SystemExit("Reconstructed Madeira gitlink mismatch")
    inventory_gz = (ROOT / "source-files.json.gz").read_bytes()
    if hashlib.sha256(inventory_gz).hexdigest() != manifest.get("inventory_sha256"):
        raise SystemExit("Source inventory SHA-256 mismatch")
    inventory = json.loads(decompress(inventory_gz, 5 * 1024 * 1024))
    entries = inventory.get("entries", [])
    if inventory.get("schema") != 1 or len(entries) != manifest.get("tracked_entry_count"):
        raise SystemExit("Source inventory schema/count mismatch")
    actual_entries = set()
    for record in run("git", "ls-tree", "-rz", actual_tree, cwd=DEST).split("\0"):
        if not record:
            continue
        metadata, path = record.split("\t", 1)
        mode, kind, sha = metadata.split()
        actual_entries.add((path, mode, kind, sha))
    declared_entries = {(item["path"], item["mode"], item["kind"], item["git_sha"]) for item in entries}
    if len(declared_entries) != len(entries) or declared_entries != actual_entries:
        raise SystemExit("Source inventory does not exactly match reconstructed Git tree")
    seen = set()
    for item in entries:
        relative = PurePosixPath(item["path"])
        if relative.is_absolute() or ".." in relative.parts or str(relative) in seen:
            raise SystemExit("Unsafe or duplicated inventory path")
        seen.add(str(relative))
        if item["kind"] == "commit":
            if item["path"] != "upstream/madeira" or item["git_sha"] != manifest["madeira_commit"]:
                raise SystemExit("Unexpected inventory submodule")
            continue
        file = DEST / relative
        if item["mode"] == "120000":
            content = os.readlink(file).encode()
        else:
            if not file.resolve().is_relative_to(DEST.resolve()):
                raise SystemExit("Inventory file escapes checkout")
            content = file.read_bytes()
        if len(content) != item["size"] or hashlib.sha256(content).hexdigest() != item["sha256"]:
            raise SystemExit(f"Source file SHA-256 mismatch: {relative}")
    print(json.dumps({"status": "source_tree_verified", "source_commit": manifest["source_commit"],
                      "source_tree": actual_tree, "base_commit": BASE,
                      "history": "pinned baseline plus exact-tree diff; not a full mirror"}))
    return DEST


def fetch_madeira_headers(destination):
    """Nonrecursive, exact public commit: supplies actual WinIOS C headers only."""
    module = destination / "upstream/madeira"
    module.mkdir(parents=True, exist_ok=True)
    if any(module.iterdir()):
        raise SystemExit("Refusing to reuse nonempty Madeira directory")
    run("git", "init", "--quiet", str(module))
    run("git", "remote", "add", "origin", "https://github.com/willfaust/Madeira.git", cwd=module)
    run("git", "fetch", "--depth=1", "origin", MADEIRA, cwd=module)
    run("git", "-c", "core.hooksPath=/dev/null", "checkout", "--quiet", "--detach", "FETCH_HEAD", cwd=module)
    if run("git", "rev-parse", "HEAD", cwd=module) != MADEIRA:
        raise SystemExit("Fetched Madeira commit mismatch")
    run("git", "diff", "--exit-code", "HEAD", cwd=module)
    print(json.dumps({"status": "madeira_headers_pinned", "commit": MADEIRA, "recursive": False}))


if __name__ == "__main__":
    fetch_madeira_headers(reconstruct())
