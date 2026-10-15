#!/usr/bin/env python3
"""Bounded, manual FEX-only control; no signing, SDK copy or account changes."""
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import zipfile

MADEIRA = "279fd0f83170425db002fe25d6bd62f6355f497d"
FEX = "f59cab95659e8add0c88f0c76ec1cf483c536dbf"
RECIPE = "6a3145c0544fae7210ebd3be4f501db3e6226dd1a4d18253431e05f6964c0cd1"
PINS = {
    "External/fmt": "407c905e45ad75fc29bf0f9bb7c5c2fd3475976f",
    "External/range-v3": "ca1388fb9da8e69314dda222dc7b139ca84e092f",
    "External/xxhash": "e626a72bc2321cd320e953a0ccf1584cad60f363",
    "External/unordered_dense": "3234af2c03549bc85656bfd3a86993bf1cd8aef1",
}
ARCHIVES = (
    "FEXCore/Source/libFEXCore.a", "FEXCore/Source/libFEXCore_Base.a",
    "FEXCore/Source/libJemallocLibs.a", "External/fmt/libfmt.a",
    "External/cephes/libcephes_128bit.a", "External/xxhash/cmake_unofficial/libxxhash.a",
    "External/SoftFloat-3e/libsoftfloat_3e.a",
)
ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / ".work/madeira-fex-control"
OUT = ROOT / ".work/runtime-control-artifacts"
EVIDENCE = SOURCE / "build/control-evidence"


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def validate_platform(arch, members, commands):
    if not re.search(r"(?:architecture:|are:)\s+arm64\s*$", arch.strip()):
        raise ValueError("Archive is not exactly arm64")
    count = len([line for line in members.splitlines() if line.strip()])
    if not count:
        raise ValueError("Empty archive")
    modern = len(re.findall(r"^\s*cmd LC_BUILD_VERSION\s*$", commands, re.M))
    legacy = len(re.findall(r"^\s*cmd LC_VERSION_MIN_IPHONEOS\s*$", commands, re.M))
    platforms = re.findall(r"^\s*platform (\S+)\s*$", commands, re.M)
    if modern + legacy != count or len(platforms) != modern:
        raise ValueError("Each object must have one iOS platform load command")
    if any(platform not in ("IOS", "2") for platform in platforms):
        raise ValueError("Non-iOS object platform detected")
    return count


class Control:
    def __init__(self):
        self.deadline = time.monotonic() + 1380
        self.steps = []

    def run(self, label, *args, cwd=ROOT, seconds=None):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeError("Aggregate 23-minute control budget exhausted")
        timeout = min(remaining, seconds or remaining)
        log = OUT / (label + ".log")
        started = time.monotonic()
        env = dict(os.environ, GIT_TERMINAL_PROMPT="0", JOBS="4", LC_ALL="C")
        with log.open("wb") as stream:
            proc = subprocess.Popen(args, cwd=cwd, env=env, stdout=stream,
                                    stderr=subprocess.STDOUT, start_new_session=True)
            try:
                code = proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
                code = 124
        self.steps.append({"label": label, "exit_code": code,
                           "elapsed_seconds": round(time.monotonic() - started, 3)})
        print(f"[{label}] exit={code}", flush=True)
        if code:
            with log.open("rb") as stream:
                stream.seek(max(0, log.stat().st_size - 24000))
                print(stream.read().decode("utf-8", errors="replace"), flush=True)
            raise RuntimeError(f"{label} failed with exit {code}")
        return log.read_text(errors="replace") if log.stat().st_size < 1024 * 1024 else ""


def add_file(archive, path, name, cap):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > cap:
        raise ValueError(f"Unsafe, absent or oversized artifact: {name}")
    archive.write(path, name)


def main():
    if sys.platform != "darwin":
        raise SystemExit("Approved macOS runner required")
    if os.environ.get("FREE_QUOTA_VERIFIED") != "true" or os.environ.get("PRIVATE_SOURCE_VERIFIED") != "true":
        raise SystemExit("Manual free/private checks must be exactly true")
    helper = ROOT / "ci/mac-core-control.sh"
    if os.environ.get("EXPECTED_RECIPE_SHA256") != RECIPE or digest(helper) != RECIPE:
        raise SystemExit("Helper is not the exact reviewed recipe")
    if SOURCE.exists() or OUT.exists():
        raise SystemExit("Fresh source and evidence directories required")
    OUT.mkdir(parents=True)
    SOURCE.mkdir(parents=True)
    control = Control()
    report = {"result": "failed", "scope": "seven real FEX arm64 iOS archives only",
              "madeira": MADEIRA, "fex": FEX, "external_pins": PINS, "recipe_sha256": RECIPE,
              "wrapper_sha256": digest(Path(__file__)), "jobs": 4, "lto": False,
              "cpu_tune": "cortex-a78", "runtime_linked": False, "ipa_created": False,
              "device_tested": False, "steps": control.steps}
    try:
        sdk = control.run("sdk", "xcrun", "--sdk", "iphoneos", "--show-sdk-version").strip()
        if sdk != "26.5":
            raise RuntimeError(f"Unexpected iPhoneOS SDK: {sdk}")
        report["sdk"] = sdk
        control.run("git-init", "git", "init", "--quiet", cwd=SOURCE)
        control.run("git-remote", "git", "remote", "add", "origin", "https://github.com/willfaust/Madeira.git", cwd=SOURCE)
        control.run("git-fetch", "git", "fetch", "--depth=1", "--filter=blob:none", "origin", MADEIRA, cwd=SOURCE, seconds=180)
        control.run("sparse-init", "git", "sparse-checkout", "init", "--cone", cwd=SOURCE)
        control.run("sparse-paths", "git", "sparse-checkout", "set", "FEX", "build/fex-ios", "LICENSES", cwd=SOURCE)
        control.run("git-checkout", "git", "checkout", "--detach", "FETCH_HEAD", cwd=SOURCE, seconds=180)
        control.run("fex-fetch", "git", "submodule", "update", "--init", "--depth=1", "FEX", cwd=SOURCE, seconds=300)
        control.run("external-fetch", "git", "submodule", "update", "--init", "--depth=1", *PINS, cwd=SOURCE / "FEX", seconds=300)
        for i, (path, pin) in enumerate(PINS.items()):
            actual = control.run(f"external-pin-{i}", "git", "rev-parse", "HEAD", cwd=SOURCE / "FEX" / path).strip()
            if actual != pin:
                raise RuntimeError(f"Unexpected {path} pin")
        control.run("preflight", "bash", str(helper), str(SOURCE), "preflight")
        control.run("fex-ios", "bash", str(helper), str(SOURCE), "fex-ios")
        for configuration in (EVIDENCE / "fex-CMakeCache.txt", SOURCE / "FEX/build-ios/compile_commands.json"):
            if not configuration.is_file() or configuration.is_symlink() or not configuration.stat().st_size:
                raise RuntimeError(f"Missing real compiler configuration evidence: {configuration.name}")
        inventory = []
        for relative in ARCHIVES:
            path = SOURCE / "FEX/build-ios" / relative
            name = path.name
            members = validate_platform((EVIDENCE / (name + ".arch.txt")).read_text(),
                                        (EVIDENCE / (name + ".members.txt")).read_text(),
                                        (EVIDENCE / (name + ".load-commands.txt")).read_text())
            inventory.append({"path": relative, "sha256": digest(path), "size": path.stat().st_size,
                              "object_members": members, "architecture": "arm64", "platform": "iOS"})
        report["archives"] = inventory
        licenses = []
        for i, repo in enumerate([SOURCE, SOURCE / "FEX", *(SOURCE / "FEX" / p for p in PINS)]):
            names = control.run(f"licenses-{i}", "git", "ls-tree", "-r", "--name-only", "HEAD", cwd=repo).splitlines()
            selected = [name for name in names if re.fullmatch(r"(?:LICENSE|COPYING|NOTICE)(?:[._-].*)?|THIRD-PARTY-NOTICES\.md", Path(name).name, re.I)]
            for j, name in enumerate(selected):
                # git show reads exact public committed bytes, including sparse root notices.
                control.run(f"license-{i}-{j}", "git", "show", "HEAD:" + name, cwd=repo)
                licenses.append((OUT / f"license-{i}-{j}.log", f"Licenses/{i}/{name}"))
        report["result"] = "passed"
        with zipfile.ZipFile(OUT / "fex-ios-archives.zip", "w", zipfile.ZIP_DEFLATED) as archive:
            for relative in ARCHIVES:
                add_file(archive, SOURCE / "FEX/build-ios" / relative, "Archives/" + Path(relative).name, 256 * 1024 * 1024)
            for path, name in licenses:
                add_file(archive, path, name, 4 * 1024 * 1024)
            archive.writestr("source-and-archive-manifest.json", json.dumps(report, indent=2))
    except Exception as error:
        report["result"] = "failed"
        report["failure"] = str(error)
        (OUT / "fex-ios-archives.zip").unlink(missing_ok=True)
        print(str(error), file=sys.stderr, flush=True)
    finally:
        (OUT / "result.json").write_text(json.dumps(report, indent=2) + "\n")
        with zipfile.ZipFile(OUT / "fex-evidence.zip", "w", zipfile.ZIP_DEFLATED) as archive:
            add_file(archive, OUT / "result.json", "result.json", 1024 * 1024)
            for step in control.steps:
                path = OUT / (step["label"] + ".log")
                # Bounded diagnostics only, never an entire source/build/cache directory.
                if path.stat().st_size <= 20 * 1024 * 1024:
                    add_file(archive, path, "Logs/" + path.name, 20 * 1024 * 1024)
                else:
                    with path.open("rb") as stream:
                        stream.seek(path.stat().st_size - 20 * 1024 * 1024)
                        archive.writestr("Logs/" + path.name + ".tail", stream.read())
            for relative in ARCHIVES:
                for suffix in (".arch.txt", ".members.txt", ".load-commands.txt"):
                    path = EVIDENCE / (Path(relative).name + suffix)
                    if path.exists():
                        add_file(archive, path, "Platform/" + path.name, 20 * 1024 * 1024)
            for path, name in (
                (EVIDENCE / "fex-CMakeCache.txt", "Configuration/fex-CMakeCache.txt"),
                (SOURCE / "FEX/build-ios/compile_commands.json", "Configuration/compile_commands.json"),
            ):
                if path.exists():
                    add_file(archive, path, name, 20 * 1024 * 1024)
        print("FEX_CONTROL_RESULT=" + json.dumps(report, sort_keys=True), flush=True)
    return 0 if report["result"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
