#!/usr/bin/env python3
"""Apply the pinned iDeck overlay in a NEW local Husk source worktree.

Never edits the input checkout, fetches dependencies, builds, signs, installs,
pushes, or touches a device. Failed staging directories are kept for diagnosis.
"""
import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path, PurePosixPath
from stage_bundle import stage, verify
from terminal_bundle import prepare as prepare_terminal

ROOT = Path(__file__).resolve().parents[1]
PIN = "0695248f491cda877f7969d1f0cc89aeede1482e"


def git(cwd, *args):
    return subprocess.check_output(["git", "-c", "core.autocrlf=false", "-C", str(cwd), *args],
                                   stderr=subprocess.STDOUT, timeout=180,
                                   env=dict(os.environ, GIT_NO_LAZY_FETCH="1", GIT_TERMINAL_PROMPT="0"))


def local_path(base, relative):
    rel = PurePosixPath(relative)
    if rel.is_absolute() or ".." in rel.parts or "\\" in relative or ":" in relative:
        raise ValueError("unsafe overlay path")
    candidate = base.joinpath(*rel.parts)
    if not candidate.resolve().is_relative_to(base.resolve()):
        raise ValueError("overlay path escapes its root")
    return candidate


def load_overlay():
    lock = json.loads((ROOT / "husk/overlay.lock.json").read_text())
    if lock["upstream_commit"] != PIN:
        raise ValueError("unexpected Husk pin")
    for relative, expected in lock["inputs"].items():
        path = local_path(ROOT, relative)
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("overlay input differs from its reviewed lock: " + relative)
    return lock


def prepare(upstream, guest, output):
    lock = load_overlay()
    verify(guest)
    if output.exists() or output.is_symlink():
        raise ValueError("output must be a new directory")
    if git(upstream, "rev-parse", "HEAD").decode().strip() != PIN:
        raise ValueError("Husk checkout is not the exact pinned commit")
    if git(upstream, "status", "--porcelain", "--untracked-files=all").strip():
        raise ValueError("input Husk checkout must be clean")
    if any(line.startswith(b"S ") for line in git(upstream, "ls-files", "-t").splitlines()):
        raise ValueError("use a complete Husk checkout; expand its sparse checkout first")
    if output.resolve().is_relative_to(upstream.resolve()) or upstream.resolve().is_relative_to(output.resolve()):
        raise ValueError("input checkout and output must be separate directories")
    for relative in lock["copies"].values():
        local_path(output, relative)
    patches = (ROOT / "husk/patches/series").read_text().splitlines()
    if not patches or any(not name or "/" in name or "\\" in name for name in patches):
        raise ValueError("invalid patch series")
    # Check all patches against an unchanged baseline before creating a worktree.
    git(upstream, "apply", "--check", *[str(ROOT / "husk/patches" / name) for name in patches])
    output.parent.mkdir(parents=True, exist_ok=True)
    git(upstream, "worktree", "add", "--detach", str(output.resolve()), PIN)
    git(output, "apply", "--index", *[str(ROOT / "husk/patches" / name) for name in patches])
    changed = {}
    for relative, expected in lock["patched_files"].items():
        path = local_path(output, relative)
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError("patched file differs from lock: " + relative)
        changed[relative] = actual
    for source, destination in lock["copies"].items():
        target = local_path(output, destination)
        if target.exists() or target.is_symlink():
            raise ValueError("overlay would replace an upstream file: " + destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(local_path(ROOT, source).read_bytes())
        changed[destination] = hashlib.sha256(target.read_bytes()).hexdigest()
    guest_assets = stage(guest, output / "guests/ideck-linux")
    terminal_assets = prepare_terminal(guest, output / "guests/ideck-linux-terminal")
    from steam_bundle import load_lock as load_steam_lock, stage as stage_steam
    steam_lock = ROOT / "ipa/steam.lock.json"
    steam_assets = {"status": "external_sealed_payload_required"}
    if load_steam_lock(steam_lock)["status"] == "blocked":
        steam_assets = stage_steam(None, output / "guests/ideck-steam", steam_lock)
    git(output, "diff", "--check")
    report = {"schema": 1, "status": "source_and_guest_staged", "upstream_commit": PIN,
              "overlay_lock_sha256": hashlib.sha256((ROOT / "husk/overlay.lock.json").read_bytes()).hexdigest(),
              "changed_files": changed, "guest_assets": guest_assets, "terminal_assets": terminal_assets, "steam_assets": steam_assets,
              "ios_compiled": False, "runtime_linked": False, "device_executed": False,
              "next": "On an existing Husk Apple build host: regenerate Xcode project, build unsigned, then perform authorized device test."}
    (output / "ideck-linux-stage.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--guest", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.upstream.resolve(), args.guest.resolve(), args.out.absolute()), indent=2))
