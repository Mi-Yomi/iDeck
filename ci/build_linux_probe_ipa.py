#!/usr/bin/env python3
"""Build the pinned native dependencies, real app and ad-hoc IPA on Apple CI.

No device installation or Apple account credentials. The IPA needs the owner's
normal sideload signing before installation. No Steam/GPU acceptance is implied.
"""
import contextlib
import errno
import hashlib
import http.client
import json
import os
import platform
import shutil
import signal
import socket
import ssl
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments/linux-guest"
sys.path.insert(0, str(EXPERIMENT / "tools"))
from stage_husk import PIN, prepare
from stage_bundle import verify

DOWNLOAD_MAX_ATTEMPTS = 3
DOWNLOAD_TIMEOUT_SECONDS = 300
DOWNLOAD_BACKOFF_SECONDS = (2, 4)


class DownloadDeadlineExceeded(TimeoutError):
    """The file/worker wall-clock budget expired; this must never be retried."""


@contextlib.contextmanager
def download_deadline(seconds):
    # The production worker is the macOS main thread. Socket timeouts alone do
    # not bound a peer that keeps delivering a few bytes before each timeout.
    if (not hasattr(signal, "setitimer") or not hasattr(signal, "SIGALRM")
            or threading.current_thread() is not threading.main_thread()):
        raise RuntimeError("A main-thread download wall-clock timer is required")
    if signal.getitimer(signal.ITIMER_REAL) != (0.0, 0.0):
        raise RuntimeError("Refusing to replace an active wall-clock timer")
    if seconds <= 0:
        raise DownloadDeadlineExceeded("Source download wall-clock budget exhausted")

    def expired(signum, frame):
        raise DownloadDeadlineExceeded("Source download wall-clock budget exhausted")

    previous = signal.signal(signal.SIGALRM, expired)
    try:
        signal.setitimer(signal.ITIMER_REAL, seconds)
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def transient_download_error(error):
    """Retry only selected transport failures, never TLS/integrity/access errors."""
    if isinstance(error, urllib.error.HTTPError):
        return error.code in (408, 429, 500, 502, 503, 504)
    if isinstance(error, urllib.error.URLError):
        return transient_download_error(error.reason)
    if isinstance(error, (DownloadDeadlineExceeded, ssl.SSLError)):
        return False
    if isinstance(error, (http.client.IncompleteRead, http.client.RemoteDisconnected)):
        return True
    return (isinstance(error, (TimeoutError, socket.timeout))
            or isinstance(error, OSError) and error.errno in
            (errno.ECONNRESET, errno.ECONNABORTED, errno.ENETRESET, errno.ETIMEDOUT, errno.EPIPE))


def download_error_details(error):
    details = {"error_type": type(error).__name__, "error": str(error)}
    reason = error
    while isinstance(reason, urllib.error.URLError) and isinstance(reason.reason, BaseException):
        reason = reason.reason
    details["reason_type"] = type(reason).__name__
    details["errno"] = getattr(reason, "errno", None)
    if isinstance(error, urllib.error.HTTPError):
        details["http_status"] = error.code
    return details


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
    # verify() returns asset bytes for resource copying. Reports must contain
    # identities, not the kernel/initramfs payloads (bytes are not JSON values).
    return {name: {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
            for name, data in verify(output).items()}


def unpack_source(archive, destination, item):
    """Extract locked source bytes with narrowly reviewed unused-link omissions."""
    if archive.stat().st_size != item["size"] or sha(archive) != item["sha256"]:
        raise ValueError("Source archive differs from lock: " + item["filename"])
    omissions = item.get("omit_symlinks", [])
    expected = {entry["path"]: entry for entry in omissions}
    if len(expected) != len(omissions):
        raise ValueError("Duplicate source-link omission rule")
    omitted = []
    seen = set()

    def source_filter(member, path):
        if member.name in expected:
            rule = expected[member.name]
            if member.name in seen or not member.issym() or member.linkname != rule["target"]:
                raise ValueError("Source member differs from reviewed symlink: " + member.name)
            seen.add(member.name)
            omitted.append(dict(rule))
            return None
        return tarfile.data_filter(member, path)

    with tarfile.open(archive) as source:
        source.extractall(destination, filter=source_filter)
    if seen != set(expected):
        raise ValueError("Reviewed source symlink is absent from the archive")
    return {"archive": item["filename"], "sha256": item["sha256"], "omitted_symlinks": omitted}


def write_result(output, report):
    payload = json.dumps(report, indent=2) + "\n"
    (output / "result.json").write_text(payload, encoding="utf-8")
    print("LINUX_IPA_BUILD_RESULT=" + json.dumps(report), flush=True)


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
        self.downloads = []

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
        record = {"filename": item["filename"], "url": item["url"], "status": "failed", "attempts": []}
        self.downloads.append(record)
        # lexists also rejects dangling symlinks; no network request or overwrite
        # is justified for a destination that was not created by this call.
        if os.path.lexists(destination):
            raise FileExistsError("Source destination must be new: " + str(destination))
        deadline = time.monotonic() + min(DOWNLOAD_TIMEOUT_SECONDS, self.remaining())

        def remaining():
            seconds = min(deadline - time.monotonic(), self.remaining())
            if seconds <= 0:
                raise DownloadDeadlineExceeded("Source download wall-clock budget exhausted")
            return seconds

        with download_deadline(remaining()):
            for number in range(1, DOWNLOAD_MAX_ATTEMPTS + 1):
                before = time.monotonic()
                attempt = {"attempt": number, "url": item["url"], "received_bytes": 0, "status": "failed"}
                record["attempts"].append(attempt)
                partial = None
                try:
                    # Each attempt owns its exclusive file. Only verified bytes
                    # may become destination, via a no-clobber atomic hard link.
                    descriptor, name = tempfile.mkstemp(prefix="." + destination.name + ".", suffix=".part", dir=destination.parent)
                    partial = Path(name)
                    with os.fdopen(descriptor, "wb") as stream:
                        with urllib.request.urlopen(item["url"], timeout=min(60, remaining())) as response:
                            while chunk := response.read(1024 * 1024):
                                remaining()
                                attempt["received_bytes"] += len(chunk)
                                if attempt["received_bytes"] > item["size"]:
                                    raise ValueError("Source exceeds locked size")
                                stream.write(chunk)
                    remaining()
                    if attempt["received_bytes"] != item["size"] or sha(partial) != item["sha256"]:
                        raise ValueError("Source archive differs from lock: " + item["filename"])
                    remaining()
                    os.link(partial, destination)
                    attempt["status"] = record["status"] = "verified"
                    return
                except Exception as error:
                    attempt.update(download_error_details(error))
                    if isinstance(error, urllib.error.HTTPError):
                        error.close()
                    if not transient_download_error(error) or number == DOWNLOAD_MAX_ATTEMPTS:
                        raise
                    # An exhausted worker/file budget is not a transport retry.
                    delay = DOWNLOAD_BACKOFF_SECONDS[number - 1]
                    if remaining() <= delay:
                        raise DownloadDeadlineExceeded("Source download budget cannot fit retry backoff") from error
                    attempt["status"] = "retry"
                    attempt["backoff_seconds"] = delay
                finally:
                    if partial is not None:
                        partial.unlink()
                    attempt["seconds"] = round(time.monotonic() - before, 3)
                    print("IDECK_SOURCE_ATTEMPT=" + json.dumps(attempt), flush=True)
                time.sleep(delay)


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
        report["downloads"] = worker.downloads
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
        report["source_archives"] = []
        for item in lock["archives"]:
            archive = downloads / item["filename"]
            worker.fetch(item, archive)
            report["source_archives"].append(unpack_source(archive, unpacked, item))
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
        write_result(out, report)


if __name__ == "__main__":
    main()
