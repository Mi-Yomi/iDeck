#!/usr/bin/env python3
"""Bounded native llvm-tblgen control and strict portable artifact verification."""
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

MADEIRA = "279fd0f83170425db002fe25d6bd62f6355f497d"
LLVM = "8dfdcc7b7bf66834a761bd8de445840ef68e4d1a"
VERSION = "15.0.7"
LLVM_SPARSE = ("/llvm/*", "!/llvm/*/", "/llvm/cmake/", "/llvm/include/", "/llvm/lib/",
               "/llvm/utils/TableGen/", "/llvm/projects/CMakeLists.txt", "/cmake/")
ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / ".work/llvm-native-source"
BUILD = SOURCE / ".work/llvm-native-control"
OUT = ROOT / ".work/llvm-control-artifacts"
MIB = 1024 * 1024
MAX_FILE = 64 * MIB
MAX_BUNDLE = 192 * MIB
RECIPE_PINS = {
    "llvm-core-control.sh": "eba4f906412aa883ee37ed9257a83f9872f719fa705fe36b4a209bd34a7a46a5",
    "llvm_control_support.py": "872247fd633e950846533d0548d19c553dd799125bbeaf1c65d704cbddf97989",
    "llvm-source-lock.json": "90b59a3cd553e394a32f361e8493aaaa799d7de83beb1a9df9b33ef7216f6479",
}
EXPECTED_DYLIBS = frozenset(("/usr/lib/libSystem.B.dylib", "/usr/lib/libc++.1.dylib"))
MANIFESTS = ("manifest.json", "manifests/source.json", "manifests/commands.json",
             "manifests/preflight.json", "manifests/native-macho.json", "manifests/outputs.json",
             "manifests/configuration.json", "manifests/compiled-sources.json",
             "manifests/notices.json", "manifests/source-lock.json")
CONFIGURATION = ("evidence/CMakeCache.txt", "evidence/compile_commands.json",
                 "evidence/CMakeFiles/CMakeConfigureLog.yaml", "evidence/include/llvm/Config/config.h",
                 "evidence/include/llvm/Config/llvm-config.h", "evidence/include/llvm/Config/abi-breaking.h")
OPTIONAL_CONFIGURATION = tuple("evidence/CMakeFiles/4.3.4/" + name for name in
                               ("CMakeCCompiler.cmake", "CMakeCXXCompiler.cmake", "CMakeASMCompiler.cmake", "CMakeSystem.cmake"))
LOG_LABELS = frozenset("host-arch host-cpu host-os developer-dir xcode-version macosx-version macosx-path iphoneos-version iphoneos-path find-clang find-clangxx find-ar find-ranlib find-ld find-libtool clang-version make-version cmake-version python-version linker-version madeira-root madeira-pin madeira-clean llvm-root llvm-pin llvm-clean llvm-untracked llvm-ignored disk-space llvm-source-tree configure build built-tblgen-version".split())
EXTRA_EVIDENCE = ("failure.json",)
SCOPE = ("Native macOS arm64 LLVM 15.0.7 llvm-tblgen build-control only. No iOS target "
         "archives, converter, runtime link, app, IPA, signing action or device test. "
         "SDK/toolchain files are not exported. Fresh jobs must verify both ZIP and "
         "artifact-manifest hashes before importing this native generator.")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(MIB), b""):
            result.update(block)
    return result.hexdigest()


def safe_name(name):
    p = PurePosixPath(name)
    if not name or not p.parts or p.as_posix() != name or p.is_absolute() or ".." in p.parts or "\\" in name or ":" in name or any(ord(c) < 32 for c in name):
        raise ValueError("Unsafe artifact member path")
    return name


def regular(path, cap=MAX_FILE, root=None):
    path = Path(path).absolute()
    if root is not None:
        root = Path(root).absolute()
        relative = path.relative_to(root)
        current = root
        if current.is_symlink():
            raise ValueError("Symlink artifact root")
        for part in relative.parts:
            current /= part
            if current.is_symlink():
                raise ValueError("Symlink artifact path")
    if path.is_symlink() or not path.is_file() or path.stat().st_size > cap:
        raise ValueError("Missing, unsafe or oversized file: " + path.name)
    return path


def fresh(path, root):
    path = Path(path)
    current = Path(root)
    for part in path.relative_to(root).parts:
        current /= part
        if current.is_symlink():
            raise ValueError("Symlink work path")
    if path.exists():
        raise ValueError("Fresh work path required: " + path.name)


def sdk_number(value):
    if not re.fullmatch(r"\d{1,3}\.\d{1,3}(?:\.\d{1,3})?", value):
        raise ValueError("Invalid SDK version")
    pieces = [int(p) for p in value.split(".")]
    pieces += [0] * (3 - len(pieces))
    if any(p > 255 for p in pieces):
        raise ValueError("Invalid SDK version component")
    return pieces[0] << 16 | pieces[1] << 8 | pieces[2]


def validate_native(data, expected_sdk):
    """Validate source-built bytes before executing even a version-only probe."""
    if len(data) < 32 or len(data) > MAX_FILE:
        raise ValueError("Native tool is truncated or oversized")
    magic, cpu, subtype, kind, ncmds, sizeofcmds, flags, reserved = struct.unpack_from("<8I", data)
    if magic != 0xFEEDFACF or cpu != 0x0100000C or subtype != 0 or kind != 2:
        raise ValueError("Expected thin arm64 Mach-O MH_EXECUTE, not a target/fat/archive object")
    if not ncmds or ncmds > 4096 or sizeofcmds > len(data) - 32:
        raise ValueError("Invalid Mach-O load-command bounds")
    offset, platforms, dylibs, linkers = 32, [], [], []
    for index in range(ncmds):
        if offset + 8 > 32 + sizeofcmds:
            raise ValueError("Truncated load command")
        command, size = struct.unpack_from("<2I", data, offset)
        if size < 8 or size % 8 or offset + size > 32 + sizeofcmds:
            raise ValueError("Invalid load-command size")
        if command == 0x32:
            if size < 24:
                raise ValueError("Truncated build-version command")
            system, minimum, sdk, tools = struct.unpack_from("<4I", data, offset + 8)
            if size != 24 + tools * 8:
                raise ValueError("Invalid build-version tool count")
            platforms.append((system, minimum, sdk))
        elif command in (0x24, 0x25, 0x2F, 0x30):
            raise ValueError("Native control requires explicit macOS LC_BUILD_VERSION")
        elif command in (0xC, 0x80000018, 0x8000001F, 0x80000023, 0x20):
            if size < 24:
                raise ValueError("Truncated dylib command")
            start = struct.unpack_from("<I", data, offset + 8)[0]
            if start < 24 or start >= size:
                raise ValueError("Invalid dylib-name offset")
            raw = data[offset + start:offset + size]
            if b"\0" not in raw:
                raise ValueError("Unterminated dylib name")
            name = raw.split(b"\0", 1)[0].decode("utf-8", errors="strict")
            if command != 0xC or name not in EXPECTED_DYLIBS:
                raise ValueError("Unexpected linked library or load kind: " + name)
            dylibs.append(name)
        elif command == 0xE:
            if size < 16:
                raise ValueError("Truncated dynamic-loader command")
            start = struct.unpack_from("<I", data, offset + 8)[0]
            if start < 12 or start >= size:
                raise ValueError("Invalid dynamic-loader name offset")
            raw = data[offset + start:offset + size]
            if b"\0" not in raw:
                raise ValueError("Unterminated dynamic-loader name")
            linkers.append(raw.split(b"\0", 1)[0].decode("utf-8", errors="strict"))
        elif command == 0x1D:
            if size != 16:
                raise ValueError("Malformed implicit native signature command")
            start, length = struct.unpack_from("<2I", data, offset + 8)
            if start + length > len(data):
                raise ValueError("Implicit native signature is outside file")
        elif command in (0x8000001C, 0xD, 0x6, 0x7, 0xF, 0x10, 0x27):
            raise ValueError("RPATH, dylib identity or prelinked executable dependency is not allowed")
        offset += size
    if offset != 32 + sizeofcmds or platforms != [(1, 0x001A0000, expected_sdk)]:
        raise ValueError("Expected exactly one macOS 26.0 build command with the recorded SDK")
    if linkers != ["/usr/lib/dyld"]:
        raise ValueError("Expected exactly the Apple system dynamic loader")
    if len(dylibs) != len(EXPECTED_DYLIBS) or set(dylibs) != EXPECTED_DYLIBS:
        raise ValueError("Native generator must link exactly the two reviewed macOS system libraries")
    return {"architecture": "arm64", "platform": "macOS", "minimum_os": "26.0",
            "sdk_encoded": expected_sdk, "dylibs": sorted(dylibs), "dynamic_loader": "/usr/lib/dyld", "filetype": "MH_EXECUTE"}


class Control:
    def __init__(self):
        self.deadline = time.monotonic() + 23 * 60
        self.steps = []

    def check(self):
        if time.monotonic() >= self.deadline:
            raise RuntimeError("Aggregate 23-minute control budget exhausted")

    def run(self, label, *args, cwd=ROOT, seconds=None):
        self.check()
        if not re.fullmatch(r"[a-z0-9-]+", label) or any(s["label"] == label for s in self.steps):
            raise ValueError("Unsafe or duplicate step label")
        timeout = min(self.deadline - time.monotonic(), seconds or 23 * 60)
        started, path = time.monotonic(), OUT / (label + ".log")
        env = dict(os.environ, GIT_TERMINAL_PROMPT="0", LC_ALL="C", JOBS="4")
        with path.open("wb") as stream:
            proc = subprocess.Popen(args, cwd=cwd, env=env, stdout=stream,
                                    stderr=subprocess.STDOUT, start_new_session=True)
            try:
                while True:
                    if time.monotonic() - started >= timeout or path.stat().st_size > MAX_FILE:
                        try:
                            os.killpg(proc.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                        proc.wait()
                        code = 124
                        break
                    try:
                        code = proc.wait(timeout=min(.25, max(.01, timeout - (time.monotonic() - started))))
                        break
                    except subprocess.TimeoutExpired:
                        pass
            except BaseException:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.wait()
                raise
        self.steps.append({"label": label, "exit_code": code,
                           "elapsed_seconds": round(time.monotonic() - started, 3)})
        print(f"[{label}] exit={code}", flush=True)
        if code:
            with path.open("rb") as stream:
                stream.seek(max(0, path.stat().st_size - 24000))
                print(stream.read().decode(errors="replace"), flush=True)
            raise RuntimeError(f"{label} failed with exit {code}")
        return path.read_text(errors="replace") if path.stat().st_size < MIB else ""


def bounds(root):
    size = count = 0
    for current, dirs, files in os.walk(root, followlinks=False):
        if any((Path(current) / n).is_symlink() for n in dirs):
            raise ValueError("Symlink checkout directory")
        for name in files:
            path = Path(current) / name
            if path.is_symlink():
                continue
            size += path.stat().st_size
            count += 1
            if size > 4 * 1024 * MIB or count > 150000:
                raise ValueError("Checkout exceeds 4 GiB/150000-file bound")
    return {"files": count, "bytes": size}


def checkout(control):
    SOURCE.mkdir(parents=True)
    control.run("madeira-init", "git", "init", "--quiet", cwd=SOURCE)
    control.run("madeira-origin", "git", "remote", "add", "origin", "https://github.com/willfaust/Madeira.git", cwd=SOURCE)
    control.run("madeira-fetch", "git", "fetch", "--depth=1", "--filter=blob:none", "origin", MADEIRA, cwd=SOURCE, seconds=180)
    control.run("madeira-sparse", "git", "sparse-checkout", "set", "--no-cone", "--", "/.gitmodules", "/COPYING", "/LICENSE-EXCEPTION.md", "/LICENSES/", cwd=SOURCE)
    control.run("madeira-checkout", "git", "checkout", "--detach", "FETCH_HEAD", cwd=SOURCE, seconds=120)
    if control.run("madeira-pin", "git", "rev-parse", "HEAD", cwd=SOURCE).strip() != MADEIRA:
        raise ValueError("Madeira pin mismatch")
    llvm = SOURCE / "toolchains/llvm-project"
    llvm.mkdir(parents=True)
    control.run("llvm-init", "git", "init", "--quiet", cwd=llvm)
    control.run("llvm-origin", "git", "remote", "add", "origin", "https://github.com/llvm/llvm-project.git", cwd=llvm)
    control.run("llvm-fetch", "git", "fetch", "--depth=1", "--filter=blob:none", "origin", LLVM, cwd=llvm, seconds=300)
    control.run("llvm-sparse", "git", "sparse-checkout", "set", "--no-cone", "--", *LLVM_SPARSE, cwd=llvm)
    control.run("llvm-checkout", "git", "checkout", "--detach", "FETCH_HEAD", cwd=llvm, seconds=300)
    if control.run("llvm-pin", "git", "rev-parse", "HEAD", cwd=llvm).strip() != LLVM:
        raise ValueError("LLVM pin mismatch")
    if Path(control.run("llvm-toplevel", "git", "rev-parse", "--show-toplevel", cwd=llvm).strip()).resolve() != llvm.resolve():
        raise ValueError("LLVM must be its own exact source checkout")
    return bounds(SOURCE)


def recipe_guards():
    for name, pin in RECIPE_PINS.items():
        path = regular(ROOT / "ci" / name, 4 * MIB, ROOT)
        if not re.fullmatch(r"[a-f0-9]{64}", pin) or digest(path) != pin:
            raise ValueError("Recipe/support/source lock is not the reviewed byte sequence: " + name)
    lock = json.loads((ROOT / "ci/llvm-source-lock.json").read_text())
    if lock.get("llvm_commit") != LLVM or lock.get("llvm_version") != VERSION or lock.get("madeira_commit") != MADEIRA:
        raise ValueError("Source lock identity mismatch")
    if os.environ.get("EXPECTED_RECIPE_SHA256") != RECIPE_PINS["llvm-core-control.sh"] or os.environ.get("EXPECTED_LLVM_SOURCE_LOCK_SHA256") != RECIPE_PINS["llvm-source-lock.json"]:
        raise ValueError("Manual recipe/source-lock hash inputs must match")


def source_availability():
    return ("Exact upstream source: https://github.com/llvm/llvm-project/tree/" + LLVM + "\n"
            "Source archive: https://github.com/llvm/llvm-project/archive/" + LLVM + ".tar.gz\n"
            "LLVM version: " + VERSION + "\n"
            "The reviewed recipe, source lock, source/command manifests, and complete selected notices "
            "are included. Native compilation uses the unchanged pinned LLVM source. A later "
            "target-only CMake compatibility edit is described in the source lock but is not applied here.\n"
            "No SDK, Xcode, Homebrew, compiler binaries, or arbitrary workspace files are included.\n")


def allowed_build_output(name):
    safe_name(name)
    if name in MANIFESTS or name in CONFIGURATION or name in OPTIONAL_CONFIGURATION or name == "native/bin/llvm-tblgen":
        return True
    if name.startswith("logs/") and name.endswith(".log") and name[5:-4] in LOG_LABELS:
        return True
    if name.startswith("notices/"):
        return True  # Must also match the exact independently hashed notices inventory.
    return bool(re.fullmatch(r"evidence/(?:[A-Za-z0-9_.+-]+/)*CMakeFiles/(?:llvm-tblgen|LLVM[A-Za-z0-9_]+)\.dir/(?:link\.txt|flags\.make|build\.make)", name))


def validate_helper_payload(payload):
    manifest = json.loads(payload["manifest.json"])
    if manifest.get("schema") != 1 or manifest.get("stage") != "native" or manifest.get("status") != "complete":
        raise ValueError("Helper manifest is not a complete native result")
    if (manifest.get("llvm_commit") != LLVM or manifest.get("madeira_commit") != MADEIRA or
        manifest.get("source_lock_sha256") != RECIPE_PINS["llvm-source-lock.json"] or
        manifest.get("helper_sha256") != RECIPE_PINS["llvm_control_support.py"]):
        raise ValueError("Helper recipe/source identity mismatch")
    if (manifest.get("jobs") != 4 or manifest.get("deployment_target") != "26.0" or
        manifest.get("xcode_version") != "26.6" or manifest.get("cmake_version") != "4.3.4"):
        raise ValueError("Helper host/configuration mismatch")
    if manifest.get("target_libraries") != [] or any(manifest.get(key) is not False for key in
            ("target_binaries_run", "sdk_copied", "package_install_performed", "explicit_signing_performed")):
        raise ValueError("Unexpected native control scope")
    for name, key in (("manifests/outputs.json", "outputs_sha256"),
                      ("manifests/source.json", "source_manifest_sha256"),
                      ("manifests/configuration.json", "configuration_sha256")):
        if sha(payload[name]) != manifest.get(key):
            raise ValueError("Helper linked provenance hash mismatch")
    outputs = json.loads(payload["manifests/outputs.json"])
    if not isinstance(outputs, list) or len(outputs) > 7000:
        raise ValueError("Invalid/excessive helper output inventory")
    names = set()
    for row in outputs:
        name = row["path"]
        if name in names or not allowed_build_output(name) or name not in payload:
            raise ValueError("Duplicate, unsafe, or missing helper output")
        names.add(name)
        if row.get("sha256") != sha(payload[name]) or row.get("bytes") != len(payload[name]):
            raise ValueError("Helper output hash/size mismatch")
    required = set(MANIFESTS) | set(CONFIGURATION) | {"native/bin/llvm-tblgen", "notices/LLVM-LICENSE.TXT"}
    if not required <= names | {"manifest.json", "manifests/outputs.json"}:
        raise ValueError("Portable native helper evidence is incomplete")
    notices = json.loads(payload["manifests/notices.json"])
    if not isinstance(notices, list) or not notices:
        raise ValueError("Missing complete notice inventory")
    notice_names = set()
    for row in notices:
        name = row["path"]
        if name in notice_names or not name.startswith("notices/") or name not in names:
            raise ValueError("Invalid notice inventory")
        notice_names.add(name)
        if row.get("sha256") != sha(payload[name]) or row.get("bytes") != len(payload[name]):
            raise ValueError("Notice hash/size mismatch")
    if notice_names != {n for n in names if n.startswith("notices/")}:
        raise ValueError("Undeclared notice payload")
    binary = manifest.get("binary", {})
    if binary != {"path": "native/bin/llvm-tblgen", "sha256": sha(payload["native/bin/llvm-tblgen"]), "bytes": len(payload["native/bin/llvm-tblgen"])}:
        raise ValueError("Helper native binary identity mismatch")
    validate_native(payload["native/bin/llvm-tblgen"], sdk_number(manifest["sdk_version"]))
    compiled = json.loads(payload["manifests/compiled-sources.json"])
    if not isinstance(compiled, list) or not compiled:
        raise ValueError("Missing actual compiled-source provenance")
    for entry in compiled:
        name = "notices/compiled-source/" + safe_name(entry["source"])
        if name not in notice_names or sha(payload[name]) != entry.get("source_sha256"):
            raise ValueError("Compiled source notice/provenance mismatch")
        if not re.fullmatch(r"[a-f0-9]{64}", entry.get("object_sha256", "")):
            raise ValueError("Compiled object identity missing")
    return names | {"manifest.json", "manifests/outputs.json"}


def build_payload(report):
    outputs = json.loads(regular(BUILD / "manifests/outputs.json", 8 * MIB, BUILD).read_text())
    names = ["manifest.json", "manifests/outputs.json"]
    for row in outputs:
        if not allowed_build_output(row["path"]):
            raise ValueError("Helper output is outside the portable artifact allowlist")
        names.append(row["path"])
    if len(names) != len({name.casefold() for name in names}):
        raise ValueError("Duplicate helper inventory entry")
    if len(names) > 7002:
        raise ValueError("Excessive portable output count")
    payload, total = {}, 0
    for name in names:
        path = regular(BUILD / name, MAX_FILE, BUILD)
        total += path.stat().st_size
        if total > MAX_BUNDLE:
            raise ValueError("Portable payload exceeds 192 MiB")
        payload[name] = path.read_bytes()
    validate_helper_payload(payload)
    for name in RECIPE_PINS:
        payload["Recipe/" + name] = regular(ROOT / "ci" / name, 4 * MIB, ROOT).read_bytes()
    payload["Recipe/run_llvm_control.py"] = Path(__file__).read_bytes()
    payload["SOURCE-AVAILABILITY.txt"] = source_availability().encode()
    return payload


def package_native(report):
    payload = build_payload(report)
    if sum(map(len, payload.values())) > MAX_BUNDLE:
        raise ValueError("Native bundle exceeds 192 MiB")
    entries = {name: {"sha256": sha(data), "size": len(data), "mode": 0o755 if name == "native/bin/llvm-tblgen" else 0o644}
               for name, data in sorted(payload.items())}
    manifest = {"schema": 1, "kind": "llvm-tblgen-native-arm64-macos", "llvm_commit": LLVM,
                "llvm_version": VERSION, "madeira_commit": MADEIRA, "recipe_pins": RECIPE_PINS,
                "native": report["native"], "version_output": report["version_output"], "scope": SCOPE,
                "target_archives_built": False, "converter_built": False, "device_tested": False,
                "files": entries}
    raw = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    temporary = OUT / "llvm-tblgen-native.zip.part"
    with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in {**payload, "artifact-manifest.json": raw}.items():
            info = zipfile.ZipInfo(safe_name(name))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | entries.get(name, {"mode": 0o644})["mode"]) << 16
            archive.writestr(info, data)
    final = OUT / "llvm-tblgen-native.zip"
    temporary.replace(final)
    report["artifact"] = {"path": final.name, "sha256": digest(final), "size": final.stat().st_size,
                          "manifest_sha256": sha(raw), "payload_files": len(payload)}
    # Exercise the exact import gate against bytes actually written, without extraction or execution.
    verify_import(final, report["artifact"]["sha256"], sha(raw))


def verify_import(path, expected_zip_sha256, expected_manifest_sha256, destination=None):
    for value in (expected_zip_sha256, expected_manifest_sha256):
        if not re.fullmatch(r"[a-f0-9]{64}", value):
            raise ValueError("Independent ZIP and artifact-manifest SHA256 values are required")
    regular(path, MAX_BUNDLE)
    if digest(path) != expected_zip_sha256:
        raise ValueError("Imported ZIP SHA256 mismatch")
    payload = {}
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        if len(infos) > 8192 or len({i.filename.casefold() for i in infos}) != len(infos):
            raise ValueError("Duplicate or excessive ZIP entries")
        if sum(i.file_size for i in infos) > MAX_BUNDLE:
            raise ValueError("Oversized uncompressed ZIP")
        for info in infos:
            safe_name(info.filename)
            mode = info.external_attr >> 16
            if info.is_dir() or stat.S_IFMT(mode) != stat.S_IFREG or info.file_size > MAX_FILE or info.flag_bits & 1:
                raise ValueError("Unsafe ZIP member type, encryption, or size")
        raw = archive.read("artifact-manifest.json")
        if sha(raw) != expected_manifest_sha256:
            raise ValueError("Imported artifact-manifest SHA256 mismatch")
        manifest = json.loads(raw)
        if manifest.get("schema") != 1 or manifest.get("kind") != "llvm-tblgen-native-arm64-macos" or manifest.get("llvm_commit") != LLVM or manifest.get("llvm_version") != VERSION:
            raise ValueError("Wrong native artifact source identity")
        if manifest.get("madeira_commit") != MADEIRA or any(manifest.get(key) is not False for key in ("target_archives_built", "converter_built", "device_tested")):
            raise ValueError("Imported native artifact has the wrong scope")
        if manifest.get("recipe_pins") != RECIPE_PINS:
            raise ValueError("Imported artifact uses a different reviewed recipe/source lock")
        declared = manifest.get("files", {})
        if set(declared) | {"artifact-manifest.json"} != {i.filename for i in infos}:
            raise ValueError("Undeclared or missing ZIP member")
        if not set(MANIFESTS) | set(CONFIGURATION) | {"native/bin/llvm-tblgen", "notices/LLVM-LICENSE.TXT", "SOURCE-AVAILABILITY.txt"} <= set(declared):
            raise ValueError("Required portable provenance is missing")
        for info in infos:
            if info.filename == "artifact-manifest.json":
                continue
            entry = declared[info.filename]
            data = archive.read(info)
            expected_mode = 0o755 if info.filename == "native/bin/llvm-tblgen" else 0o644
            if entry.get("size") != len(data) or entry.get("sha256") != sha(data) or entry.get("mode") != expected_mode or stat.S_IMODE(info.external_attr >> 16) != expected_mode:
                raise ValueError("ZIP member hash, size, or mode mismatch")
            payload[info.filename] = data
        for name, pin in RECIPE_PINS.items():
            if sha(payload.get("Recipe/" + name, b"")) != pin:
                raise ValueError("Imported recipe bytes differ from reviewed hash")
        helper_names = validate_helper_payload(payload)
        recipe_names = {"Recipe/" + name for name in RECIPE_PINS} | {"Recipe/run_llvm_control.py", "SOURCE-AVAILABILITY.txt"}
        if set(payload) != helper_names | recipe_names:
            raise ValueError("Payload exceeds exact helper/recipe/notice allowlist")
        native = validate_native(payload["native/bin/llvm-tblgen"], manifest["native"]["sdk_encoded"])
        if native != manifest["native"]:
            raise ValueError("Native binary differs from artifact platform/library manifest")
    if destination is not None:
        destination = Path(destination)
        fresh(destination, destination.parent)
        if any(p.is_symlink() for p in destination.parents):
            raise ValueError("Symlink import parent")
        staging = destination.with_name(destination.name + ".importing")
        fresh(staging, staging.parent)
        staging.mkdir(parents=True)
        for name, data in payload.items():
            target = staging / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            target.chmod(declared[name]["mode"])
        (staging / "artifact-manifest.json").write_bytes(raw)
        staging.replace(destination)
    return manifest


def write_evidence(report, control):
    (OUT / "result.json").write_text(json.dumps(report, indent=2) + "\n")
    candidates = [(OUT / "result.json", "result.json")]
    candidates += [(OUT / (s["label"] + ".log"), "Logs/" + s["label"] + ".log") for s in control.steps]
    candidates += [(BUILD / name, "Build/" + name) for name in (*MANIFESTS, *CONFIGURATION, *OPTIONAL_CONFIGURATION, *EXTRA_EVIDENCE)]
    candidates += [(BUILD / "logs" / (name + ".log"), "Build/logs/" + name + ".log") for name in sorted(LOG_LABELS)]
    for name in (*CONFIGURATION, *OPTIONAL_CONFIGURATION):
        fallback = BUILD / "build" / name[len("evidence/"):]
        if not (BUILD / name).exists():
            candidates.append((fallback, "Build/" + name))
    candidates += [(ROOT / "ci" / name, "Recipe/" + name) for name in RECIPE_PINS]
    candidates += [(Path(__file__), "Recipe/run_llvm_control.py")]
    total, omissions = 0, []
    with zipfile.ZipFile(OUT / "llvm-native-evidence.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for path, name in candidates:
            if not path.exists() and not path.is_symlink():
                continue
            try:
                regular(path, MAX_FILE, ROOT)
                size = min(path.stat().st_size, 12 * MIB)
                if total + size > 96 * MIB:
                    raise ValueError("96 MiB evidence cap")
                with path.open("rb") as stream:
                    if path.stat().st_size > size:
                        stream.seek(path.stat().st_size - size)
                        name += ".tail"
                    archive.writestr(name, stream.read(size))
                total += size
            except ValueError as error:
                omissions.append({"path": name, "reason": str(error)})
        archive.writestr("evidence-omissions.json", json.dumps(omissions, indent=2))
    print("LLVM_NATIVE_CONTROL_RESULT=" + json.dumps(report, sort_keys=True), flush=True)


def main():
    if len(sys.argv) > 1:
        if len(sys.argv) != 6 or sys.argv[1] != "--verify-import":
            raise SystemExit("Usage: run_llvm_control.py [--verify-import ZIP ZIP_SHA256 MANIFEST_SHA256 FRESH_DESTINATION]")
        manifest = verify_import(Path(sys.argv[2]), sys.argv[3], sys.argv[4], Path(sys.argv[5]))
        print(json.dumps({"result": "verified-import-no-execution", "llvm_commit": manifest["llvm_commit"]}))
        return 0
    if sys.platform != "darwin" or platform.machine() != "arm64":
        raise SystemExit("Approved native arm64 macOS runner required")
    if os.environ.get("FREE_QUOTA_VERIFIED") != "true" or os.environ.get("PRIVATE_SOURCE_VERIFIED") != "true":
        raise SystemExit("Manual free/private guards must be exactly true")
    recipe_guards()
    fresh(SOURCE, ROOT)
    fresh(OUT, ROOT)
    OUT.mkdir(parents=True)
    control = Control()
    report = {"result": "failed", "scope": SCOPE, "llvm_commit": LLVM, "llvm_version": VERSION,
              "madeira_commit": MADEIRA, "recipe_pins": RECIPE_PINS, "wrapper_sha256": digest(Path(__file__)),
              "jobs": 4, "aggregate_budget_seconds": 1380, "target_archives_built": False,
              "converter_built": False, "runtime_linked": False, "device_tested": False, "steps": control.steps}
    try:
        cpu = control.run("cpu", "sysctl", "-n", "machdep.cpu.brand_string", seconds=10).strip()
        if cpu not in ("Apple M2", "Apple M2 (Virtual)"):
            raise ValueError("Unreviewed CPU label")
        xcode = control.run("xcode", "xcodebuild", "-version", seconds=20)
        if not xcode.startswith("Xcode 26.6\n"):
            raise ValueError("Xcode 26.6 required")
        cmake = control.run("cmake", "cmake", "--version", seconds=10)
        if not cmake.startswith("cmake version 4.3.4\n"):
            raise ValueError("CMake 4.3.4 required")
        sdk = control.run("sdk", "xcrun", "--sdk", "macosx", "--show-sdk-version", seconds=10).strip()
        report["host"] = {"cpu": cpu, "xcode": xcode.strip(), "cmake": "4.3.4", "macos_sdk": sdk}
        report["checkout"] = checkout(control)
        BUILD.parent.mkdir(parents=True, exist_ok=True)
        control.run("native-build", "bash", str(ROOT / "ci/llvm-core-control.sh"), str(SOURCE), str(BUILD), "native")
        native_path = regular(BUILD / "native/bin/llvm-tblgen", MAX_FILE, BUILD)
        report["native"] = validate_native(native_path.read_bytes(), sdk_number(sdk))
        report["version_output"] = control.run("native-version", str(native_path), "--version", seconds=10).strip()
        if not re.search(r"\bLLVM version 15\.0\.7\b", report["version_output"]):
            raise ValueError("Native generator version differs from pinned LLVM 15.0.7")
        control.check()
        package_native(report)
        control.check()
        report["result"] = "passed-native-generator-only"
    except Exception as error:
        report["failure"] = str(error)
        (OUT / "llvm-tblgen-native.zip").unlink(missing_ok=True)
        report.pop("artifact", None)
        print(str(error), file=sys.stderr, flush=True)
    finally:
        (OUT / "llvm-tblgen-native.zip.part").unlink(missing_ok=True)
        write_evidence(report, control)
    return 0 if report["result"] == "passed-native-generator-only" else 1


if __name__ == "__main__":
    raise SystemExit(main())
