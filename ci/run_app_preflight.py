#!/usr/bin/env python3
"""Reviewed compiler-only control. No project build, target execution or network."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import signal
import stat
import struct
import subprocess
import sys
import time
import zipfile

PIN = "279fd0f83170425db002fe25d6bd62f6355f497d"
PROJECT = "app/Madeira.xcodeproj/project.pbxproj"
DEVELOPER = "/Applications/Xcode-27.0.app/Contents/Developer"
XCODE = "Xcode 27.0\nBuild version 27A266a"
SECONDS = 510
MIB = 1024 * 1024
LOG_LIMIT = 8 * MIB
PRODUCT_LIMIT = MIB
WORK_LIMIT = 2 * 1024 * MIB
OPTIONAL_SECONDS = 40
OPTIONAL_RESERVE = 10
CHIPS = frozenset(("Apple M2", "Apple M2 (Virtual)"))
FORBIDDEN_OBJECT_COMMANDS = frozenset((
    0x4, 0x5, 0xC, 0xD, 0xE, 0xF, 0x80000018, 0x8000001C, 0x1D,
    0x8000001F, 0x20, 0x22, 0x80000022, 0x80000023, 0x24, 0x25,
    0x27, 0x80000028, 0x2F, 0x30, 0x80000033, 0x80000034,
))
ROOT = Path(__file__).resolve().parents[1]
IMPORT_SOURCE = "import StikJIT\npublic func ideckStikImportProbe(_ paths: DDIPaths) -> DDIPaths { paths }\n"
METAL_SOURCE = "#include <metal_stdlib>\nusing namespace metal;\nkernel void ideck_probe(device uint *out [[buffer(0)]], uint i [[thread_position_in_grid]]) { out[i] = i; }\n"
LIMITATIONS = (
    "Compiler-only evidence: own import object, unchanged Madeira helper and main Swift typechecks. "
    "No native link, resources, target execution, JIT operation, converter use, signing, app/IPA or device result. "
    "SDK headers and toolchain caches stay on the provider. The optional own Metal-to-AIR probe does not use Metal Shader Converter."
)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def validate_toolchain(details):
    if details["xcode-version"] != XCODE or not re.search(r"Apple Swift version 6\.4(?:\D|$)", details["swift-version"]) or details["sdk-version"] != "27.0" or details["host-chip"] not in CHIPS:
        raise ValueError("Actual toolchain/hardware differs from the reviewed Xcode 27.0 / Swift 6.4 / iOS 27.0 / exact M2 target")


def regular(path, maximum):
    if any(part.is_symlink() for part in (path, *path.parents)) or not path.is_file() or path.stat().st_size > maximum:
        raise ValueError(f"Unsafe, missing or oversized file: {path.name}")
    return path


def safe_name(name):
    p = PurePosixPath(name)
    if not name or name != p.as_posix() or p.is_absolute() or ".." in p.parts or any(ord(c) < 32 for c in name) or "\\" in name or ":" in name:
        raise ValueError("Unsafe archive path")
    return name


def validate_lock(lock):
    if lock.get("schema") != 1 or lock.get("madeira_commit") != PIN:
        raise ValueError("Wrong source identity")
    files = lock.get("files", {})
    if len(files) != 98 or len(lock.get("main_swift_sources", [])) != 67 or len(lock.get("helper_swift_sources", [])) != 2 or len(lock.get("bridging_header_closure", [])) != 15:
        raise ValueError("Source membership differs from reviewed project")
    for name, spec in files.items():
        safe_name(name)
        if not re.fullmatch(r"[0-9a-f]{64}", spec.get("sha256", "")) or not re.fullmatch(r"[0-9a-f]{40}", spec.get("git_blob", "")) or not isinstance(spec.get("size"), int) or not 0 <= spec["size"] <= 8 * MIB:
            raise ValueError("Invalid source fingerprint")
        if "/d3d12/" in name or name.endswith((".dylib", ".a", ".dll", ".exe", ".sh", ".py")):
            raise ValueError("Out-of-scope source input")
    for key in ("main_swift_sources", "helper_swift_sources", "bridging_header_closure", "framework_files"):
        names = lock[key]
        if len(names) != len(set(names)) or any(name not in files for name in names):
            raise ValueError("Missing or duplicate source-set member")
    if lock["bridging_header"] != "app/Madeira/Madeira-Bridging-Header.h" or lock["framework_parent"] != "app/Frameworks/StikJIT.xcframework/ios-arm64":
        raise ValueError("Unexpected compiler input paths")
    if lock["helper_swift_sources"] != ["app/MadeiraJITHelper/MadeiraJITHelper.swift", "app/Madeira/JITBuiltInMessages.swift"]:
        raise ValueError("Unexpected helper files")
    return lock


def unpack(archive, lock, destination):
    regular(archive, 8 * MIB)
    if sha(archive.read_bytes()) != lock["archive_sha256"]:
        raise ValueError("Input ZIP fingerprint mismatch")
    if destination.exists() or any(part.is_symlink() for part in (destination, *destination.parents)):
        raise ValueError("Extraction destination must not exist")
    checked = []
    with zipfile.ZipFile(archive) as z:
        infos = z.infolist()
        if len(infos) != len(lock["files"]) or len({i.filename for i in infos}) != len(infos):
            raise ValueError("Missing, duplicate or extra ZIP entries")
        if {i.filename for i in infos} != set(lock["files"]):
            raise ValueError("Unexpected ZIP entries")
        if sum(i.file_size for i in infos) > 20 * MIB:
            raise ValueError("Input ZIP exceeds uncompressed bound")
        for info in infos:
            name = safe_name(info.filename)
            mode = info.external_attr >> 16
            if info.is_dir() or stat.S_ISLNK(mode) or (stat.S_IFMT(mode) not in (0, stat.S_IFREG)) or info.flag_bits & 1:
                raise ValueError("Only unencrypted regular ZIP files are allowed")
            spec = lock["files"][name]
            if info.file_size != spec["size"]:
                raise ValueError("Source size mismatch")
            data = z.read(info)
            if sha(data) != spec["sha256"]:
                raise ValueError("Source content mismatch")
            checked.append((name, data))
    destination.mkdir(parents=True)
    for name, data in checked:
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        path.chmod(0o644)  # Even the tracked framework binary remains inert data.


def verify_membership(source, lock):
    project = (source / PROJECT).read_text()
    phase = re.search(r"A3000002 /\* Sources \*/ = \{.*?files = \((.*?)\);", project, re.S).group(1)
    names = ["app/Madeira/" + n for n in re.findall(r"/\* (.*?) in Sources \*/", phase) if n.endswith(".swift")]
    if names != lock["main_swift_sources"]:
        raise ValueError("Main Swift membership does not match the real pinned project")
    headers = set()

    def visit(name):
        if name in headers:
            return
        headers.add(name)
        text = (source / name).read_text()
        for include in re.findall(r'^\s*#\s*(?:include|import)\s*"([^"]+)"', text, re.M):
            child = (PurePosixPath(name).parent / include).as_posix()
            safe_name(child)
            if child not in lock["files"]:
                raise ValueError("Missing real bridging-header dependency")
            visit(child)

    visit(lock["bridging_header"])
    if headers != set(lock["bridging_header_closure"]):
        raise ValueError("Bridge closure differs from reviewed files")


def compiler_commands(source, work, sdk, lock):
    common = ["/usr/bin/xcrun", "--sdk", "iphoneos", "swiftc", "-swift-version", "5", "-sdk", sdk,
              "-module-cache-path", str(work / "module-cache"), "-parse-as-library", "-D", "DEBUG", "-Onone"]
    framework = ["-F", str(source / lock["framework_parent"])]
    return [
        ("stikjit-import", common + ["-target", "arm64-apple-ios26.0"] + framework +
         ["-module-name", "IdeckStikImport", "-c", str(work / "ImportStikJIT.swift"), "-o", str(work / "ImportStikJIT.o")], 90),
        ("helper-typecheck", common + ["-target", "arm64-apple-ios26.0"] + framework +
         ["-module-name", "MadeiraJITHelper", "-application-extension", "-typecheck"] + [str(source / n) for n in lock["helper_swift_sources"]], 120),
        ("main-typecheck", common + ["-target", "arm64-apple-ios17.0", "-module-name", "Madeira", "-typecheck",
         "-import-objc-header", str(source / lock["bridging_header"]), "-I", str(source / "app/Madeira"),
         "-Xcc", "-fmodules", "-Xcc", "-fobjc-arc"] + [str(source / n) for n in lock["main_swift_sources"]], 240),
    ]


def validate_object(path):
    data = regular(path, MIB).read_bytes()
    if len(data) < 32:
        raise ValueError("Import probe has no Mach-O object")
    magic, cpu, subtype, kind, commands, length, flags, reserved = struct.unpack_from("<8I", data)
    if magic != 0xFEEDFACF or cpu != 0x0100000C or subtype != 0 or kind != 1 or 32 + length > len(data):
        raise ValueError("Import output is not an arm64 Mach-O relocatable object")
    offset = 32
    platforms = []
    for _ in range(commands):
        if offset + 8 > 32 + length:
            raise ValueError("Truncated Mach-O commands")
        command, size = struct.unpack_from("<II", data, offset)
        if size < 8 or offset + size > 32 + length:
            raise ValueError("Invalid Mach-O command size")
        if command in FORBIDDEN_OBJECT_COMMANDS:
            raise ValueError("Import object contains a forbidden signature or runtime load command")
        if command == 0x32:
            if size < 24:
                raise ValueError("Truncated build-version command")
            platforms.append(struct.unpack_from("<III", data, offset + 8))
        offset += size
    if offset != 32 + length or platforms != [(2, 26 << 16, 27 << 16)]:
        raise ValueError("Import output must be an iOS device object, minimum OS 26.0, SDK exactly 27.0")
    return {"sha256": sha(data), "bytes": len(data), "cpu": "arm64", "filetype": "MH_OBJECT", "platform": "iOS", "minimum_os": "26.0", "sdk_version_encoded": platforms[0][2]}


class Runner:
    def __init__(self, work):
        self.work = work
        self.deadline = time.monotonic() + SECONDS
        self.records = []
        self.env = {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "HOME": str(work / "home"),
                    "TMPDIR": str(work / "tmp"), "DEVELOPER_DIR": DEVELOPER,
                    "LANG": "en_US.UTF-8", "LC_ALL": "en_US.UTF-8"}
        for name in ("home", "tmp", "module-cache"):
            (work / name).mkdir()

    def output_violation(self, log):
        if log.stat().st_size > LOG_LIMIT:
            return "output_limit"
        for name in ("ImportStikJIT.o", "OwnMetalProbe.air"):
            product = self.work / name
            if product.is_symlink() or (product.exists() and product.stat().st_size > PRODUCT_LIMIT):
                return "product_output_limit"
        total = 0
        # Include compiler module caches and temporary outputs; never follow links.
        for directory, _, files in os.walk(self.work, followlinks=False):
            for name in files:
                path = Path(directory) / name
                try:
                    if not path.is_symlink():
                        total += path.stat().st_size
                except FileNotFoundError:
                    continue  # Compiler temporary files may disappear during observation.
                if total > WORK_LIMIT:
                    return "work_output_limit"
        return None

    def run(self, name, command, limit=10, deadline=None):
        remaining = min(self.deadline, deadline if deadline is not None else self.deadline) - time.monotonic()
        if remaining < 1:
            record = {"stage": name, "status": "not_run_budget_exhausted", "argv": command}
            self.records.append(record)
            return record, ""
        log = self.work / (name + ".log")
        start = time.monotonic()
        reason = None
        with log.open("wb") as stream:
            process = subprocess.Popen(command, cwd=self.work, env=self.env, stdin=subprocess.DEVNULL,
                                       stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
            stop = start + min(limit, remaining)
            next_output_check = start
            while process.poll() is None:
                now = time.monotonic()
                if now >= next_output_check:
                    reason = self.output_violation(log)
                    next_output_check = now + 1
                if now >= stop or reason:
                    reason = reason or "timeout"
                    try:
                        os.killpg(process.pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                    try:
                        process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait()
                    break
                time.sleep(0.05)
        reason = reason or self.output_violation(log)
        # A child can exit between polling intervals after a large burst. Keep the
        # bounded diagnostic prefix and mark failure instead of losing all evidence.
        if log.stat().st_size > LOG_LIMIT:
            with log.open("r+b") as stream:
                stream.truncate(LOG_LIMIT)
        status = reason or ("passed" if process.returncode == 0 else "failed")
        record = {"stage": name, "status": status, "returncode": process.returncode,
                  "elapsed_seconds": round(time.monotonic() - start, 3), "argv": command, "log": log.name}
        self.records.append(record)
        return record, log.read_text(errors="replace")


def optional_metal(runner, work, sdk):
    """All optional outcomes stay local and preserve the primary Swift status."""
    metal = {"status": "not_run_insufficient_optional_budget"}
    if runner.deadline - time.monotonic() < OPTIONAL_SECONDS + OPTIONAL_RESERVE:
        return metal
    deadline = min(time.monotonic() + OPTIONAL_SECONDS, runner.deadline - OPTIONAL_RESERVE)
    metal["status"] = "observed"
    try:
        for sdk_name in ("iphoneos", "macosx"):
            for tool in ("metal", "metallib"):
                name = f"{sdk_name}-{tool}-find"
                record, output = runner.run(name, ["/usr/bin/xcrun", "--sdk", sdk_name, "--find", tool], 5, deadline=deadline)
                metal[name] = {"status": record["status"], "output": output.strip()[:4096], "output_truncated": len(output.strip()) > 4096}
        if metal["iphoneos-metal-find"]["status"] == "passed":
            record, _ = runner.run("own-metal-air", ["/usr/bin/xcrun", "--sdk", "iphoneos", "metal", "-c",
                                   "-target", "air64-apple-ios17.0", "-isysroot", str(sdk), str(work / "OwnMetalProbe.metal"),
                                   "-o", str(work / "OwnMetalProbe.air")], 25, deadline=deadline)
            metal["own_air_compile"] = record["status"]
            if record["status"] == "passed":
                air = regular(work / "OwnMetalProbe.air", PRODUCT_LIMIT).read_bytes()
                if not air:
                    raise ValueError("Metal compiler produced no AIR")
                metal["own_air_sha256"] = sha(air)
                metal["own_air_bytes"] = len(air)
    except Exception as error:
        metal["status"] = "optional_probe_failed"
        metal["error"] = str(error)
    return metal


def main():
    # Fail before any provider compiler action unless operator supplied exact reviewed pins.
    for key in ("FREE_QUOTA_VERIFIED", "PRIVATE_SOURCE_VERIFIED", "APP_PREFLIGHT_REVIEWED"):
        if os.environ.get(key) != "true":
            raise ValueError(f"Missing manual prerequisite: {key}")
    for key, path in (("EXPECTED_RUNNER_SHA256", Path(__file__)), ("EXPECTED_SOURCE_LOCK_SHA256", ROOT / "ci/app-preflight-source-lock.json")):
        expected = os.environ.get(key, "")
        if not re.fullmatch(r"[0-9a-f]{64}", expected) or sha(regular(path, MIB).read_bytes()) != expected:
            raise ValueError(f"Missing or mismatched reviewed fingerprint: {key}")
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise ValueError("This provider stage requires an Apple-silicon Mac")
    lock = validate_lock(json.loads((ROOT / "ci/app-preflight-source-lock.json").read_text()))
    work = ROOT / ".work/app-preflight"
    if work.exists() or any(part.is_symlink() for part in (work, *work.parents)):
        raise ValueError("Refusing to reuse an existing preflight work directory")
    work.mkdir(parents=True)
    runner = Runner(work)
    result = {"status": "failed", "madeira_commit": PIN, "limitations": LIMITATIONS,
              "stages": runner.records, "native_link_inputs_not_supplied": lock["native_link_inputs_not_supplied"]}
    try:
        source = work / "source"
        unpack(ROOT / "ci/inputs/app-preflight-inputs.zip", lock, source)
        verify_membership(source, lock)
        (work / "ImportStikJIT.swift").write_text(IMPORT_SOURCE)
        (work / "OwnMetalProbe.metal").write_text(METAL_SOURCE)
        details = {}
        metadata = [
            ("host-os", ["/usr/bin/sw_vers"]),
            ("host-chip", ["/usr/sbin/sysctl", "-n", "machdep.cpu.brand_string"]),
            ("xcode-version", ["/usr/bin/xcodebuild", "-version"]),
            ("swift-version", ["/usr/bin/xcrun", "--sdk", "iphoneos", "swiftc", "--version"]),
            ("sdk-path", ["/usr/bin/xcrun", "--sdk", "iphoneos", "--show-sdk-path"]),
            ("sdk-version", ["/usr/bin/xcrun", "--sdk", "iphoneos", "--show-sdk-version"]),
            ("sdk-build", ["/usr/bin/xcrun", "--sdk", "iphoneos", "--show-sdk-build-version"]),
            ("sdk-clang", ["/usr/bin/xcrun", "--sdk", "iphoneos", "clang", "--version"]),
        ]
        for name, argv in metadata:
            record, output = runner.run(name, argv)
            if len(output) > 16384:
                raise ValueError(f"Unexpectedly large metadata output: {name}")
            details[name] = output.strip()
            if record["status"] != "passed":
                raise ValueError(f"Metadata lookup failed: {name}")
        result["toolchain"] = details
        validate_toolchain(details)
        sdk = Path(details["sdk-path"])
        if not sdk.is_dir() or not sdk.resolve().is_relative_to(Path(DEVELOPER).resolve()):
            raise ValueError("SDK is not inside the selected official Xcode installation")
        for name, command, limit in compiler_commands(source, work, str(sdk), lock):
            record, _ = runner.run(name, command, limit)
            if name == "stikjit-import" and record["status"] == "passed":
                result["import_object"] = validate_object(work / "ImportStikJIT.o")
        results = {r["stage"]: r["status"] for r in runner.records}
        required = ["stikjit-import", "helper-typecheck", "main-typecheck"]
        result["status"] = "compiler_checks_passed" if all(results.get(n) == "passed" for n in required) else "compiler_checks_incomplete_or_failed"
        result["source_input_archive_sha256"] = lock["archive_sha256"]
        # Set the required outcome first; optional lookup/compilation cannot erase it.
        result["metal_toolchain"] = optional_metal(runner, work, sdk)
    except Exception as error:
        result["error"] = str(error)
    finally:
        # Only explicit logs, our own object and compact metadata are deliverable.
        # Never archive source/, SDK/module caches, HOME, TMPDIR or framework data.
        (work / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        (work / "source-manifest.json").write_text(json.dumps(lock, indent=2) + "\n")
        output = ROOT / ".work/app-preflight-artifacts"
        output.mkdir(exist_ok=False)
        names = {"result.json", "source-manifest.json"}
        names.update(r["log"] for r in runner.records if "log" in r)
        if "import_object" in result:
            names.add("ImportStikJIT.o")
        with zipfile.ZipFile(output / "app-preflight-evidence.zip", "w", zipfile.ZIP_DEFLATED) as z:
            for name in sorted(names):
                z.write(regular(work / safe_name(name), 9 * MIB), name)
        print(json.dumps({"status": result["status"], "stages": [{"stage": r["stage"], "status": r["status"]} for r in runner.records], "error": result.get("error"), "limitations": LIMITATIONS}, indent=2))
    return 0 if result["status"] == "compiler_checks_passed" else 1


if __name__ == "__main__":
    sys.exit(main())
