#!/usr/bin/env python3
"""Build the pinned native dependencies, real app and ad-hoc IPA on Apple CI.

No device installation or Apple account credentials. The IPA needs the owner's
normal sideload signing before installation. No Steam/GPU acceptance is implied.
"""
import ast
import configparser
import contextlib
import errno
import hashlib
import http.client
import json
import os
import platform
import re
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
NATIVE_PYTHON_REQUIREMENTS = EXPERIMENT / "ipa/python-requirements.lock.txt"
NATIVE_PYYAML_VERSION = "6.0.2"


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


def ensure_native_python(worker, report):
    """Prepare the host generator's Python without modifying system packages."""
    directory = worker.output / "native-python"
    receipt = {"status": "failed", "venv": str(directory),
               "requirements_sha256": sha(NATIVE_PYTHON_REQUIREMENTS),
               "base_python": sys.version.split()[0], "base_implementation": sys.implementation.name,
               "host_system": platform.system(), "host_machine": platform.machine()}
    report["native_python"] = receipt
    if (receipt["base_implementation"] != "cpython" or sys.version_info[:2] != (3, 12)
            or receipt["host_system"] != "Darwin" or receipt["host_machine"] != "arm64"):
        raise RuntimeError("Locked native Python wheel requires CPython 3.12 on macOS arm64")
    if os.path.lexists(directory):
        raise FileExistsError("Native Python environment must be new")
    worker.run("python-venv", [sys.executable, "-I", "-m", "venv", directory])
    interpreter = directory / "bin/python3"
    worker.run("python-install", [interpreter, "-I", "-m", "pip", "--isolated", "--disable-pip-version-check",
               "install", "--no-input", "--no-cache-dir", "--no-index", "--no-deps", "--only-binary=:all:",
               "--require-hashes", "--requirement", NATIVE_PYTHON_REQUIREMENTS])
    probe = worker.run("python-probe", [interpreter, "-I", "-c",
        "import json, sys, yaml; print(json.dumps({'python_version': sys.version.split()[0], "
        "'executable': sys.executable, 'prefix': sys.prefix, 'pyyaml_version': yaml.__version__, "
        "'pyyaml_module': yaml.__file__}))"])
    identity = json.loads(probe)
    keys = {"python_version", "executable", "prefix", "pyyaml_version", "pyyaml_module"}
    if (not isinstance(identity, dict) or set(identity) != keys
            or not all(isinstance(value, str) for value in identity.values())):
        raise ValueError("Unexpected native Python probe identity")
    receipt.update(identity)
    if (identity["pyyaml_version"] != NATIVE_PYYAML_VERSION
            or not identity["python_version"].startswith("3.12.")
            or Path(identity["executable"]).absolute() != interpreter.absolute()
            or Path(identity["prefix"]).resolve() != directory.resolve()
            or not Path(identity["pyyaml_module"]).resolve().is_relative_to(
                (directory / "lib/python3.12/site-packages").resolve())):
        raise ValueError("Native Python probe differs from the isolated locked environment")
    # build_ios.sh writes command -v python3 into cross-darwin.meson; install
    # this PATH before native-base generates it, so later Meson uses this same
    # interpreter for virglrenderer host generators and their yaml import.
    worker.env["PATH"] = str(directory / "bin") + os.pathsep + worker.env["PATH"]
    worker.env["VIRTUAL_ENV"] = str(directory)
    receipt["status"] = "ready"


def verify_native_python_cross_files(report, cross):
    """Check the actual generated Meson files bind the verified interpreter."""
    receipt = report["native_python"]
    receipt["status"] = "failed"
    receipt["cross_files"] = {}
    interpreter = Path(receipt["venv"]) / "bin/python3"
    for filename in ("cross-ios.meson", "cross-darwin.meson"):
        path = cross / filename
        parser = configparser.ConfigParser(interpolation=None)
        with path.open(encoding="utf-8") as stream:
            parser.read_file(stream)
        command = ast.literal_eval(parser["binaries"]["python"])
        if (not isinstance(command, list) or len(command) != 1 or not isinstance(command[0], str)
                or not Path(command[0]).is_absolute()
                or Path(command[0]).absolute() != interpreter.absolute()):
            raise ValueError("Generated Meson cross file uses a different Python: " + filename)
        receipt["cross_files"][filename] = {"sha256": sha(path), "python": command[0]}
    receipt["status"] = "ready"


def ensure_metal_toolchain(worker, report):
    """Compile a real shader; acquire Apple's component only when explicitly missing."""
    receipt = {"status": "failed", "download_requested": False, "sdk": "iphoneos",
               "initial_probe": "failed", "selection_mode": "angle_env_i_path_home",
               "ignored_developer_dir_override": bool(worker.env.get("DEVELOPER_DIR")),
               "ignored_toolchains_override": bool(worker.env.get("TOOLCHAINS"))}
    report["metal_toolchain"] = receipt
    # The pinned ANGLE recipe invokes xcodebuild with only PATH/HOME. Match
    # that selection exactly: inherited DEVELOPER_DIR/TOOLCHAINS could otherwise
    # make a successful probe test a different compiler from the actual build.
    angle_environment = ["/usr/bin/env", "-i", "PATH=" + worker.env["PATH"], "HOME=" + worker.env["HOME"]]
    directory = worker.output / "metal-toolchain"
    directory.mkdir()
    source = directory / "probe.metal"
    source.write_text("kernel void ideck_toolchain_probe() {}\n", encoding="utf-8")

    def probe(label, output):
        # xcrun --find can resolve a stub even when the component is absent.
        # Require an actual compiler invocation and a newly produced AIR file.
        worker.run(label, angle_environment + ["xcrun", "--sdk", "iphoneos", "metal", "-c", source, "-o", output])
        if not output.is_file() or output.stat().st_size == 0:
            raise ValueError("Metal compiler did not produce a nonempty probe AIR file")
        return {"path": str(output.relative_to(worker.output)),
                "size": output.stat().st_size, "sha256": sha(output)}

    try:
        artifact = probe("metal-probe-before", directory / "probe-before.air")
    except RuntimeError:
        diagnostic = (worker.output / "metal-probe-before.log").read_text(errors="replace")
        # No generic compiler, license, permission or account failure authorizes
        # a download. Preserve its original error and log instead.
        if ("missing Metal Toolchain" not in diagnostic
                or "xcodebuild -downloadComponent MetalToolchain" not in diagnostic):
            receipt["initial_probe"] = "failed"
            raise
        receipt["initial_probe"] = "missing_component"
        receipt["download_requested"] = True
        worker.run("metal-toolchain-download", angle_environment + ["xcodebuild", "-downloadComponent", "metalToolchain"])
        artifact = probe("metal-probe-after", directory / "probe-after.air")
    else:
        receipt["initial_probe"] = "passed"
    receipt["probe_artifact"] = artifact
    receipt["compiler_version"] = worker.run("metal-version", angle_environment + ["xcrun", "--sdk", "iphoneos", "metal", "--version"])
    receipt["status"] = "ready"


def ensure_qemu_build_compiler(worker, report):
    """Prove QEMU's generator compiler targets and runs on the macOS build host."""
    receipt = {"status": "failed", "inherited_sdkroot": worker.env.get("SDKROOT")}
    report["qemu_host_compiler"] = receipt
    clang = worker.run("qemu-host-clang", ["xcrun", "--sdk", "macosx", "--find", "clang"])
    sdk = worker.run("qemu-host-sdk", ["xcrun", "--sdk", "macosx", "--show-sdk-path"])
    # QEMU's meson_quote splits on spaces without interpreting shell quotes.
    # Reject tokens it cannot faithfully transport instead of inventing quoting.
    def safe_token(value):
        return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_./:+-]+", value) is not None

    if (not safe_token(clang) or not Path(clang).is_absolute() or not Path(clang).is_file()
            or not safe_token(sdk) or not Path(sdk).is_absolute() or not Path(sdk).is_dir()
            or not Path(sdk).name.startswith("MacOSX") or not Path(sdk).name.endswith(".sdk")):
        raise ValueError("Unsafe or unexpected macOS build compiler/SDK path")
    triple = worker.run("qemu-host-triple", [clang, "-isysroot", sdk, "-dumpmachine"])
    if (not safe_token(triple)
            or re.fullmatch(r"(?:arm64|aarch64)-apple-(?:darwin|macosx?)[0-9]+(?:\.[0-9]+)*", triple) is None):
        raise ValueError("Unexpected macOS build compiler default triple")
    command = [clang, "-target", triple, "-isysroot", sdk]
    receipt.update(clang=clang, sdk=sdk, compiler_default_triple=triple)
    directory = worker.output / "qemu-host-compiler"
    directory.mkdir()
    source = directory / "probe.c"
    executable = directory / "probe"
    source.write_text("#include <TargetConditionals.h>\n#include <stdio.h>\n"
                      "#if !TARGET_OS_OSX || TARGET_OS_IPHONE\n#error macOS build compiler required\n#endif\n"
                      "int main(void) { puts(\"IDECK_QEMU_HOST_COMPILER_OK\"); return 0; }\n", encoding="utf-8")
    worker.run("qemu-host-compile", [*command, source, "-o", executable])
    if not executable.is_file() or executable.stat().st_size == 0:
        raise ValueError("macOS build compiler did not produce a nonempty executable")
    output = worker.run("qemu-host-execute", [executable])
    if output != "IDECK_QEMU_HOST_COMPILER_OK":
        raise ValueError("macOS build compiler executable probe returned unexpected output")
    receipt["probe"] = {"path": str(executable.relative_to(worker.output)), "size": executable.stat().st_size,
                        "sha256": sha(executable), "stdout": output}
    receipt["host_cc"] = " ".join(command)
    # The iOS compiler, flags and ambient SDKROOT remain intact. Only QEMU's
    # documented --host-cc receives the separate proven build-machine command.
    worker.env["IDECK_QEMU_HOST_CC"] = receipt["host_cc"]
    receipt["status"] = "ready"


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
        # Fail before native dependency/tool setup if exact Debian payload bytes
        # are unavailable. The E: development path is never a CI input.
        from debian_bundle import fetch as fetch_debian, restore as restore_debian
        debian_lock = EXPERIMENT / "ipa/debian.lock.json"
        debian_archive = out / "ideck-debian-console-v1.tar"
        report["debian_payload"] = fetch_debian(debian_archive, debian_lock)
        debian_assets = out / "debian-assets"
        report["debian_assets"] = restore_debian(debian_archive, debian_assets, debian_lock)
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
        from debian_bundle import stage as stage_debian
        stage_debian(debian_assets, source / "guests/ideck-debian", debian_lock)
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
        ensure_native_python(worker, report)
        worker.run("native-base", ["bash", "scripts/build_ios.sh", "libffi", "glib", "pixman", "libucontext", "libslirp"], source)
        cross = source / "build/ios-arm64"
        verify_native_python_cross_files(report, cross)
        shutil.copyfile(cross / "cross-darwin.meson", cross / "cross-ios-darwin.meson")
        ensure_metal_toolchain(worker, report)
        worker.run("native-angle", ["bash", "scripts/build_angle_ios.sh"], source)
        worker.env["PKG_CONFIG_LIBDIR"] = str(cross / "sysroot/lib/pkgconfig") + ":" + str(cross / "sysroot/share/pkgconfig")
        worker.run("native-gpu", ["bash", "scripts/build_gpu_ios.sh"], source)
        ensure_qemu_build_compiler(worker, report)
        qemu_host_patch = EXPERIMENT / "ipa/0003-qemu-macos-build-compiler.patch"
        report["qemu_host_compiler"]["recipe_patch_sha256"] = sha(qemu_host_patch)
        worker.run("qemu-host-patch-check", ["git", "apply", "--check", qemu_host_patch], source)
        worker.run("qemu-host-patch-apply", ["git", "apply", qemu_host_patch], source)
        qemu_cross_patch = EXPERIMENT / "ipa/0002-qemu-ios-needs-exe-wrapper.patch"
        report["qemu_cross_patch_sha256"] = sha(qemu_cross_patch)
        qemu_directory = "--directory=third_party/build/qemu-10.0.12-utm"
        worker.run("qemu-cross-patch-check", ["git", "apply", "--check", qemu_directory, qemu_cross_patch], source)
        worker.run("qemu-cross-patch-apply", ["git", "apply", qemu_directory, qemu_cross_patch], source)
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
