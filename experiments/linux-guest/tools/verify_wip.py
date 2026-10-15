#!/usr/bin/env python3
"""Verify the supplied text-only diagnostic WIP without compiling/installing it."""
import argparse
import hashlib
import json
import shutil
import subprocess
import tarfile
from pathlib import Path, PurePosixPath


def verify(archive, out):
    out.mkdir(parents=True, exist_ok=False)
    prefix = "droiddeck-tl-source-fix-WIP-20261015"
    with tarfile.open(archive) as source:
        seen = set()
        for member in source.getmembers():
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts or path.parts[0] != prefix or member.name in seen:
                raise ValueError("unsafe or duplicate archive member")
            seen.add(member.name)
            target = out.joinpath(*path.parts)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            elif member.isfile() and member.size <= 1024 * 1024:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.extractfile(member).read())
            else:
                raise ValueError("unexpected archive member type/size")
    snapshot = out / prefix
    inventory = json.loads((snapshot / "evidence/source-files-sha256.json").read_text())
    counts = {}
    for side in ("base", "patched"):
        expected_paths = set()
        for path, hashes in inventory.items():
            relative = PurePosixPath(path)
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("unsafe inventory path")
            expected = hashes.get(side + "_sha256")
            if expected is None:
                continue
            expected_paths.add(path)
            data = (snapshot / side / path).read_bytes()
            if hashlib.sha256(data).hexdigest() != expected:
                raise ValueError("snapshot file hash mismatch")
        actual_paths = {p.relative_to(snapshot / side).as_posix() for p in (snapshot / side).rglob("*") if p.is_file()}
        if actual_paths != expected_paths:
            raise ValueError("snapshot file inventory differs")
        counts[side] = len(expected_paths)
    candidate = out / "patch-check"
    shutil.copytree(snapshot / "base", candidate)
    subprocess.run(["git", "init", "--quiet", str(candidate)], check=True)
    patch = (snapshot / "translationlayer-source-fix-WIP.patch").resolve()
    subprocess.run(["git", "-c", "core.autocrlf=false", "apply", "--check", str(patch)], cwd=candidate, check=True)
    subprocess.run(["git", "-c", "core.autocrlf=false", "apply", str(patch)], cwd=candidate, check=True)
    expected_files = {p.relative_to(snapshot / "patched").as_posix(): p.read_bytes()
                      for p in (snapshot / "patched").rglob("*") if p.is_file()}
    actual_files = {p.relative_to(candidate).as_posix(): p.read_bytes() for p in candidate.rglob("*")
                    if p.is_file() and ".git" not in p.relative_to(candidate).parts}
    if actual_files != expected_files:
        raise ValueError("applied patch differs from supplied patched tree")
    result = {"status": "archive_hashes_and_patch_equivalence_pass", "file_counts": counts,
              "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
              "compiled": False, "apk_created": False, "device_run": False}
    (out / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    verify(args.archive, args.out)
