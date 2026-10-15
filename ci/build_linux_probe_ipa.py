#!/usr/bin/env python3
"""Build the pinned native dependencies, real app and ad-hoc IPA on Apple CI.

No device installation or Apple account credentials. The IPA needs the owner's
normal sideload signing before installation. No Steam/GPU acceptance is implied.
"""
import hashlib
import json
import os
import platform
import shutil
import signal
import subprocess
import sys
import tarfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments/linux-guest"
sys.path.insert(0, str(EXPERIMENT / "tools"))
from stage_husk import PIN, prepare
from stage_bundle import verify


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def restore_guest(output):
    lock = json.loads((EXPERIMENT / "ipa/guest.lock.json").read_text())
    archive = EXPERIMENT / lock["archive"]
    if archive.stat().st_size != lock["size"] or sha(archive) != lock["sha256"]:
        raise ValueError("Linux guest archive integrity failure")
    if output.exists():
        raise ValueError("Guest destination must be new")
    with tarfile.open(archive) as source:
        members = source.getmembers()
        if len(members) != 3 or {m.name for m in members} != set(lock["files"]):
            raise ValueError("Unexpected Linux guest archive members")
        checked = {}
        for member in members:
            expected = lock["files"][member.name]
            if not member.isfile() or member.size != expected["size"]:
                raise ValueError("Unexpected Linux guest member type/size")
            raw = source.extractfile(member).read()
            if hashlib.sha256(raw).hexdigest() != expected["sha256"]:
                raise ValueError("Linux guest member hash mismatch")
            checked[member.name] = raw
    output.mkdir(parents=True)
    for name, raw in checked.items():
        (output / name).write_bytes(raw)
    return verify(output)


class Worker:
    def __init__(self, output):
        self.output = output
        self.started = time.monotonic()
        self.env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", GIT_TERMINAL_PROMPT="0",
                        HOMEBREW_NO_AUTO_UPDATE="1", HOMEBREW_NO_ANALYTICS="1")
        for variable, name in (("TMPDIR", "tmp"), ("CARGO_HOME", "cargo"), ("RUSTUP_HOME", "rustup")):
            path = output / name
            path.mkdir()
            self.env[variable] = str(path)
        self.steps = []

    def remaining(self):
        seconds = 6900 - (time.monotonic() - self.started)
        if seconds <= 0:
            raise TimeoutError("Aggregate native-build budget exhausted")
        return seconds

    def run(self, name, command, cwd=ROOT):
        log = self.output / (name + ".log")
        print("IDECK_BUILD_STEP=" + name, flush=True)
        before = time.monotonic()
        with log.open("wb") as stream:
            process = subprocess.Popen(list(map(str, command)), cwd=cwd, env=self.env,
                                       stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
            try:
                code = process.wait(timeout=self.remaining())
            except BaseException:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
                raise
        self.steps.append({"name": name, "exit_code": code, "seconds": round(time.monotonic()-before, 3)})
        if code:
            with log.open("rb") as stream:
                stream.seek(max(0, log.stat().st_size - 16000))
                print(stream.read().decode("utf-8", errors="replace"))
            raise RuntimeError(name + " failed; see its log")
        return log.read_text(errors="replace").strip() if log.stat().st_size < 1000000 else "see log"

    def clone(self, name, url, commit, dest, sparse=None):
        self.run(name + "-init", ["git", "init", "--quiet", dest])
        self.run(name + "-remote", ["git", "-C", dest, "remote", "add", "origin", url])
        args = ["git", "-C", dest, "fetch", "--depth", "1"]
        if sparse:
            args += ["--filter=blob:none"]
        self.run(name + "-fetch", args + ["origin", commit])
        if sparse:
            self.run(name + "-sparse-init", ["git", "-C", dest, "sparse-checkout", "init", "--cone"])
            self.run(name + "-sparse-set", ["git", "-C", dest, "sparse-checkout", "set", *sparse])
        self.run(name + "-checkout", ["git", "-C", dest, "-c", "core.autocrlf=false", "checkout", "--detach", "FETCH_HEAD"])
        actual = self.run(name + "-identity", ["git", "-C", dest, "rev-parse", "HEAD"])
        if actual != commit:
            raise ValueError(name + " resolved to a different commit")

    def fetch(self, item, destination):
        print("IDECK_SOURCE=" + item["filename"], flush=True)
        with urllib.request.urlopen(item["url"], timeout=min(60, self.remaining())) as response, destination.open("xb") as stream:
            received = 0
            while chunk := response.read(1024 * 1024):
                self.remaining()
                received += len(chunk)
                if received > item["size"]:
                    raise ValueError("Source exceeds locked size")
                stream.write(chunk)
        if received != item["size"] or sha(destination) != item["sha256"]:
            raise ValueError("Source archive differs from lock: " + item["filename"])


def main():
    out = ROOT / ".work/linux-ipa"
    out.mkdir(parents=True, exist_ok=False)
    report = {"status": "failed", "ipa_created": False, "device_tested": False, "steam_executed": False}
    worker = None
    try:
        if platform.system() != "Darwin":
            raise RuntimeError("Apple SDK and macOS are required for the native IPA build")
        if os.environ.get("IDECK_WORKFLOW_ID") != "ideck-linux-probe-ipa":
            raise RuntimeError("Select the dedicated ideck-linux-probe-ipa workflow")
        if os.environ.get("NATIVE_BUILD_APPROVED") != "true":
            raise RuntimeError("Native build/tool setup approval is required; this is a separate 120-minute workflow")
        # Recheck here as well as in YAML: direct script execution is not a bypass.
        sys.path.insert(0, str(ROOT / "ci"))
        from check_build_request import main as check_request
        check_request()
        worker = Worker(out)
        report["steps"] = worker.steps
        report["commit"] = worker.run("checkout", ["git", "rev-parse", "HEAD"])
        report["xcode"] = worker.run("xcode", ["xcodebuild", "-version"])
        worker.run("swift-source-check", [sys.executable, "-I", "ci/check_linux_guest_profile.py"])
        lock = json.loads((EXPERIMENT / "ipa/native-sources.lock.json").read_text())
        if lock["husk_commit"] != PIN:
            raise ValueError("Native recipe and app source use different Husk commits")
        report["native_lock_sha256"] = sha(EXPERIMENT / "ipa/native-sources.lock.json")
        report["husk_commit"] = PIN
        # Only this disposable CI worker is modified. No host installation,
        # login, signing certificate, new key or paid resource is involved.
        worker.run("build-tools", ["brew", "install", "meson", "ninja", "pkg-config", "xcodegen", "rustup"])
        prefix = worker.run("rustup-prefix", ["brew", "--prefix", "rustup"])
        worker.env["PATH"] = str(Path(prefix) / "bin") + os.pathsep + worker.env["PATH"]
        worker.run("rust-toolchain", ["rustup", "toolchain", "install", lock["rust_toolchain"],
                                     "--profile", "minimal", "--target", "aarch64-apple-ios"])
        worker.env["RUSTUP_TOOLCHAIN"] = lock["rust_toolchain"]
        report["rust"] = worker.run("rust-version", ["rustc", "--version"])
        report["tool_receipts"] = worker.run("tool-receipts", ["brew", "list", "--versions", "meson", "ninja", "pkg-config", "xcodegen", "rustup"])
        for tool in ("meson", "ninja"):
            if not Path("/opt/homebrew/bin", tool).is_file():
                raise RuntimeError("Pinned Husk GPU recipe expects /opt/homebrew/bin/" + tool)
        upstream = out / "husk-base"
        worker.clone("husk", "https://github.com/Leviidev/Husk.git", PIN, upstream)
        guest = out / "guest"
        report["guest_assets"] = restore_guest(guest)
        source = out / "husk"
        report["source_stage"] = prepare(upstream, guest, source)
        worker.run("native-recipe-patch", ["git", "apply", "--check", EXPERIMENT / "ipa/0001-fail-closed-native-build.patch"], source)
        worker.run("native-recipe-apply", ["git", "apply", EXPERIMENT / "ipa/0001-fail-closed-native-build.patch"], source)
        downloads = source / "third_party/sources"
        unpacked = source / "third_party/build"
        downloads.mkdir(parents=True); unpacked.mkdir(parents=True)
        for item in lock["archives"]:
            archive = downloads / item["filename"]
            worker.fetch(item, archive)
            with tarfile.open(archive) as tar:
                tar.extractall(unpacked, filter="data")
        for item in lock["git"]:
            dest = source / item["destination"]
            dest.parent.mkdir(parents=True, exist_ok=True)
            worker.clone(item["name"], item["url"], item["commit"], dest, item.get("sparse"))
        worker.run("native-base", ["bash", "scripts/build_ios.sh", "libffi", "glib", "pixman", "libucontext", "libslirp"], source)
        cross = source / "build/ios-arm64"
        shutil.copyfile(cross / "cross-darwin.meson", cross / "cross-ios-darwin.meson")
        worker.run("native-angle", ["bash", "scripts/build_angle_ios.sh"], source)
        worker.env["PKG_CONFIG_LIBDIR"] = str(cross / "sysroot/lib/pkgconfig") + ":" + str(cross / "sysroot/share/pkgconfig")
        worker.run("native-gpu", ["bash", "scripts/build_gpu_ios.sh"], source)
        worker.run("native-qemu", ["bash", "scripts/build_ios.sh", "qemu"], source)
        worker.run("native-integrate-husk", ["bash", "scripts/integrate_husk.sh"], source)
        worker.run("native-qemu-integrated", ["bash", "scripts/build_ios.sh", "qemurebuild"], source)
        worker.run("native-pairing", ["bash", "scripts/build_rppairing_ios.sh"], source)
        # Retain expensive native outputs even if the later app link fails.
        # A future importer must verify this manifest; it is not a cache hit by
        # itself and this workflow never substitutes it for a source build.
        native_files = ["build/ios-arm64/lib/libqemu-aarch64-softmmu.dylib",
                        "build/ios-arm64/sysroot/lib/libANGLE-shared.dylib",
                        "build/ios-arm64/lib/libhusk_rppairing.a",
                        "src/app/Husk/Resources/legal/LICENSES-rppairing-crates.txt"]
        native_manifest = {"husk_commit": PIN, "transport_commit": report["commit"],
                           "native_lock_sha256": report["native_lock_sha256"], "files": {}}
        for name in native_files:
            path = source / name
            if not path.is_file() or path.stat().st_size == 0:
                raise ValueError("Native build did not produce " + name)
            native_manifest["files"][name] = {"size": path.stat().st_size, "sha256": sha(path)}
        (source / "native-products.json").write_text(json.dumps(native_manifest, indent=2) + "\n")
        native_archive = out / "native-products.tar.gz"
        with tarfile.open(native_archive, "w:gz") as tar:
            for name in ["native-products.json", *native_files]:
                tar.add(source / name, arcname=name, recursive=False)
        report["native_products_sha256"] = sha(native_archive)
        project = source / "src/app/project-linux.json"
        shutil.copyfile(EXPERIMENT / "ipa/project.json", project)
        worker.run("xcodegen", ["xcodegen", "generate", "--spec", project.name], project.parent)
        derived = out / "DerivedData"
        worker.run("app-build", ["xcodebuild", "-project", project.parent / "iDeckLinuxProbe.xcodeproj", "-scheme", "Husk",
                   "-sdk", "iphoneos", "-configuration", "Release", "-derivedDataPath", derived,
                   "CODE_SIGNING_ALLOWED=NO", "CODE_SIGNING_REQUIRED=NO", "CODE_SIGN_IDENTITY=", "build"], source)
        sys.path.insert(0, str(EXPERIMENT / "ipa"))
        from package_probe import package
        report.update(package(worker, derived / "Build/Products/Release-iphoneos/Husk.app", source, report["commit"]))
        report["status"] = "linux_probe_ipa_built"
    except Exception as error:
        report["failure"] = str(error)
        raise
    finally:
        if worker:
            report["elapsed_seconds"] = round(time.monotonic()-worker.started, 3)
        (out / "result.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print("LINUX_IPA_BUILD_RESULT=" + json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
