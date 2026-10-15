#!/usr/bin/env python3
"""Two independent, fresh source-only LLVM 15 controls. No network or installs.

Native emits a transferable llvm-tblgen. Target imports a verified native tool
and emits the exact 34 DXMT archives and LLVM public headers. Never executes a
target binary. This proposal is not an Apple build-success claim.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import stat
import struct
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
LOCK_PATH = HERE / "llvm-source-lock.json"
LOCK = json.loads(LOCK_PATH.read_text())
JOBS = 4
HOST_MIN = "26.0"
TARGET_MIN = "18.0"
SYSTEM_PATH = "/usr/bin:/bin:/usr/sbin:/sbin"
DYLIBS = {"/usr/lib/libSystem.B.dylib", "/usr/lib/libc++.1.dylib"}
AR_INDEXES = {"__.SYMDEF", "__.SYMDEF SORTED", "__.SYMDEF_64", "__.SYMDEF_64 SORTED"}
OFF = (
    "BUILD_SHARED_LIBS", "LLVM_BUILD_LLVM_DYLIB", "LLVM_LINK_LLVM_DYLIB",
    "LLVM_BUILD_LLVM_C_DYLIB", "LLVM_BUILD_STATIC", "LLVM_ENABLE_ASSERTIONS",
    "LLVM_ENABLE_EH", "LLVM_ENABLE_RTTI", "LLVM_ENABLE_LTO", "LLVM_ENABLE_FFI",
    "LLVM_ENABLE_ZLIB", "LLVM_ENABLE_ZSTD", "LLVM_ENABLE_LIBXML2",
    "LLVM_ENABLE_TERMINFO", "LLVM_ENABLE_LIBEDIT", "LLVM_ENABLE_LIBPFM",
    "LLVM_ENABLE_CURL", "LLVM_ENABLE_HTTPLIB", "LLVM_ENABLE_Z3_SOLVER",
    "LLVM_INCLUDE_TESTS", "LLVM_INCLUDE_EXAMPLES", "LLVM_INCLUDE_BENCHMARKS",
    "LLVM_INCLUDE_DOCS", "LLVM_BUILD_TOOLS", "LLVM_INCLUDE_TOOLS",
    "LLVM_BUILD_UTILS", "LLVM_INCLUDE_UTILS", "LLVM_BUILD_RUNTIME",
    "LLVM_BUILD_RUNTIMES", "LLVM_INCLUDE_RUNTIMES", "LLVM_ENABLE_BINDINGS",
    "LLVM_ENABLE_DOXYGEN", "LLVM_ENABLE_SPHINX", "LLVM_APPEND_VC_REV",
    "LLVM_ENABLE_OCAMLDOC", "LLVM_ENABLE_IDE", "LLVM_ENABLE_PLUGINS",
)


class ContractError(Exception):
    pass


class CommandFailure(Exception):
    def __init__(self, name, status):
        self.status = status if status >= 0 else 128 - status
        super().__init__(f"{name} failed with exit status {self.status}")


def require(condition, message):
    if not condition:
        raise ContractError(str(message))


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def blob_hash(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def safe_relative(value):
    p = PurePosixPath(value)
    require(value and str(p) == value and not p.is_absolute(), "Noncanonical relative path")
    require(all(x not in ("", ".", "..") for x in p.parts), "Unsafe relative path")
    require(not any(ord(c) < 32 or c in "\\;" for c in value), "Unsafe path characters")
    return p


def real_path(path, root=None, file=False):
    path = Path(path).absolute()
    require(".." not in path.parts and not any(c in str(path) for c in "\n\r;"), "Unsafe path")
    for parent in (path, *path.parents):
        require(not parent.is_symlink(), f"Symlink path: {parent}")
    require(path.exists(), f"Missing path: {path}")
    require(not file or path.is_file(), f"Not a regular file: {path}")
    if root is not None:
        require(path.is_relative_to(root), f"Path outside approved root: {path}")
    return path


def apple_tool_path(value, developer, name):
    """Keep the driver spelling; clang++ may be a symlink to the clang binary."""
    path = Path(value)
    require(path.is_absolute() and '..' not in path.parts and path.name == name,
            'Unexpected xcrun tool invocation path')
    root = Path(developer).resolve()
    resolved = path.resolve(strict=True)
    require(path.is_relative_to(root) and resolved.is_relative_to(root) and
            resolved.is_file() and os.access(path, os.X_OK), 'Apple tool outside selected Xcode')
    return str(path), str(resolved)


def base_environment(build, developer=None):
    env = {"PATH": SYSTEM_PATH, "HOME": str(build / "home"), "TMPDIR": str(build / "tmp"),
           "LC_ALL": "C", "LANG": "C", "TZ": "UTC", "PYTHONNOUSERSITE": "1",
           "PYTHONDONTWRITEBYTECODE": "1", "PYTHONOPTIMIZE": "0",
           "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
           "GIT_TERMINAL_PROMPT": "0"}
    if developer:
        env["DEVELOPER_DIR"] = str(developer)
    return env


def selected_source(name):
    p = safe_relative(name)
    return (p.parts[0] == "cmake" or
            (p.parts[0] == "llvm" and len(p.parts) == 2) or
            name.startswith(("llvm/cmake/", "llvm/include/", "llvm/lib/", "llvm/utils/TableGen/")) or
            name == "llvm/projects/CMakeLists.txt")


def patch_addllvm(data):
    patch = LOCK["patch"]
    require(hashlib.sha256(data).hexdigest() == patch["before_sha256"], "AddLLVM input hash mismatch")
    old, new = patch["old"].encode(), patch["new"].encode()
    require(data.count(old) == 1, "AddLLVM patch context is not unique")
    result = data.replace(old, new)
    require(hashlib.sha256(result).hexdigest() == patch["after_sha256"], "AddLLVM patched hash mismatch")
    return result


def version_number(value):
    require(re.fullmatch(r"\d+\.\d+(?:\.\d+)?", value), "Malformed platform version")
    values = [int(x) for x in value.split(".")]
    values += [0] * (3 - len(values))
    require(values[0] < 65536 and all(x < 256 for x in values[1:]), "Platform version overflow")
    return (values[0] << 16) | (values[1] << 8) | values[2]


def macho(data, platform, minimum, sdk, executable=False, assembly_sdk_unspecified=False):
    require(len(data) >= 32, "Truncated Mach-O")
    magic, cpu, subtype, kind, count, size, flags, reserved = struct.unpack_from("<8I", data)
    require(magic == 0xFEEDFACF and cpu == 0x0100000C and subtype == 0, "Expected thin arm64 Mach-O")
    require(kind == (2 if executable else 1), "Wrong Mach-O file type")
    require(0 < count <= 4096 and 32 + size <= len(data), "Invalid Mach-O command envelope")
    cursor, versions, libraries, loaders, signature = 32, [], [], [], False
    for _ in range(count):
        require(cursor + 8 <= 32 + size, "Truncated load command")
        cmd, length = struct.unpack_from("<2I", data, cursor)
        require(length >= 8 and length % 8 == 0 and cursor + length <= 32 + size, "Invalid load command")
        if cmd == 0x32:
            require(length >= 24, "Truncated build-version command")
            plat, minos, sdkver, ntools = struct.unpack_from("<4I", data, cursor + 8)
            require(length == 24 + 8 * ntools, "Bad build-version tool count")
            versions.append({"platform": plat, "minimum": minos, "sdk": sdkver})
        if cmd in (0x24, 0x25, 0x2F, 0x30):
            raise ContractError("Legacy version command is not accepted on this pinned modern toolchain")
        if cmd in (0xC, 0x80000018, 0x8000001F, 0x80000023, 0x20):
            require(length >= 24, "Truncated dylib command")
            offset = struct.unpack_from("<I", data, cursor + 8)[0]
            require(24 <= offset < length, "Invalid dylib-name offset")
            raw = data[cursor + offset:cursor + length]
            require(b"\0" in raw, "Unterminated dylib name")
            libraries.append(raw.split(b"\0", 1)[0].decode("utf-8"))
        require(cmd != 0x8000001C, "Runtime search path is forbidden")
        require(cmd not in (0xD, 0xF, 0x10, 0x27), "Dylib identity, prebound dependency or loader environment is forbidden")
        if cmd == 0xE:
            require(executable and length >= 16, "Invalid dynamic loader command")
            offset = struct.unpack_from("<I", data, cursor + 8)[0]
            require(12 <= offset < length, "Invalid dynamic loader name offset")
            raw = data[cursor + offset:cursor + length]
            require(b"\0" in raw, "Unterminated dynamic loader name")
            loaders.append(raw.split(b"\0", 1)[0].decode("utf-8"))
        if cmd == 0x1D:
            signature = True
            require(executable, "Target object signature is forbidden")
            require(length == 16, "Malformed signature command")
            start, amount = struct.unpack_from("<2I", data, cursor + 8)
            require(start + amount <= len(data), "Signature outside file")
        cursor += length
    require(cursor == 32 + size and len(versions) == 1, "Missing/ambiguous platform metadata")
    expected = {"platform": platform, "minimum": version_number(minimum), "sdk": version_number(sdk)}
    unspecified = not executable and assembly_sdk_unspecified and versions[0]["sdk"] == 0
    if unspecified:
        expected["sdk"] = 0
    require(versions[0] == expected, f"Wrong build version: {versions[0]} != {expected}")
    if executable:
        require(set(libraries) == DYLIBS and len(libraries) == len(DYLIBS), f"Unexpected native dylibs: {libraries}")
        require(loaders == ["/usr/lib/dyld"], "Unexpected native dynamic loader")
    else:
        require(not libraries, "Target archive object has dynamic dependencies")
    return {"arch": "arm64", "file_type": kind, "build_version": versions[0],
            "sdk_provenance": "unspecified-in-audited-assembly-object" if unspecified else "encoded-sdk",
            "dylibs": libraries, "dynamic_loaders": loaders, "implicit_host_signature_present": signature}


def archive_members(path, sdk="26.5"):
    result, names, indexes = [], set(), []
    with Path(path).open("rb") as stream:
        require(stream.read(8) == b"!<arch>\n", "Not a regular ar archive")
        while True:
            offset = stream.tell()
            header = stream.read(60)
            if not header:
                break
            require(len(header) == 60 and header[-2:] == b"`\n", "Malformed archive header")
            try:
                amount = int(header[48:58].decode("ascii").strip())
            except ValueError as exc:
                raise ContractError("Invalid archive size") from exc
            require(0 < amount <= 256 * 1024 * 1024, "Archive member size exceeds bound")
            data = stream.read(amount)
            require(len(data) == amount, "Truncated archive member")
            name = header[:16].decode("ascii").strip()
            if name.startswith("#1/"):
                n = int(name[3:])
                require(0 < n < amount and n <= 4096, "Bad BSD name length")
                name = data[:n].rstrip(b"\0").decode("utf-8")
                data = data[n:]
            else:
                name = name.removesuffix("/")
            if amount % 2:
                require(stream.read(1) == b"\n", "Invalid archive padding")
            if name in AR_INDEXES:
                require(name not in indexes, "Repeated archive index")
                indexes.append(name)
                continue
            require(re.fullmatch(r"[A-Za-z0-9_.+-]+\.o", name), f"Unreviewed archive member name: {name}")
            require(name not in names, f"Repeated archive basename: {name}")
            names.add(name)
            allowed_assembly = any(row["archive"] == Path(path).name and row["member"] == name
                                   for row in LOCK["assembly_unspecified_sdk"])
            proof = macho(data, 2, TARGET_MIN, sdk, assembly_sdk_unspecified=allowed_assembly)
            result.append({"ordinal": len(result), "offset": offset, "name": name,
                           "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), **proof})
            require(len(result) <= 30000, "Archive member count exceeds bound")
    require(result and indexes, "Archive has no real members or index")
    return {"path": Path(path).name, "sha256": sha256(path), "indexes": indexes, "members": result}


def cmake_definitions(stage, tools, sdk, prefix, native=None):
    result = {key: "OFF" for key in OFF}
    result.update({"CMAKE_BUILD_TYPE": "Release", "CMAKE_C_COMPILER": tools["clang"],
        "CMAKE_CXX_COMPILER": tools["clang++"], "CMAKE_ASM_COMPILER": tools["clang"], "CMAKE_MAKE_PROGRAM": tools["make"],
        "CMAKE_AR": tools["ar"], "CMAKE_RANLIB": tools["ranlib"], "CMAKE_LIBTOOL": tools["libtool"],
        "CMAKE_INSTALL_PREFIX": str(prefix), "CMAKE_OSX_SYSROOT": str(sdk),
        "CMAKE_OSX_ARCHITECTURES": "arm64", "CMAKE_OSX_DEPLOYMENT_TARGET": HOST_MIN if stage == "native" else TARGET_MIN,
        "CMAKE_C_FLAGS": "", "CMAKE_CXX_FLAGS": "", "CMAKE_ASM_FLAGS": "", "CMAKE_C_FLAGS_RELEASE": "-O2 -DNDEBUG",
        "CMAKE_CXX_FLAGS_RELEASE": "-O2 -DNDEBUG", "CMAKE_EXPORT_COMPILE_COMMANDS": "ON",
        "CMAKE_SKIP_RPATH": "ON", "CMAKE_FIND_ROOT_PATH": str(sdk),
        "CMAKE_FIND_ROOT_PATH_MODE_LIBRARY": "ONLY", "CMAKE_FIND_ROOT_PATH_MODE_INCLUDE": "ONLY",
        "CMAKE_FIND_ROOT_PATH_MODE_PACKAGE": "ONLY", "CMAKE_FIND_ROOT_PATH_MODE_PROGRAM": "NEVER",
        "CMAKE_FIND_USE_SYSTEM_ENVIRONMENT_PATH": "OFF", "CMAKE_FIND_USE_PACKAGE_REGISTRY": "OFF",
        "CMAKE_FIND_USE_SYSTEM_PACKAGE_REGISTRY": "OFF", "CMAKE_PREFIX_PATH": "",
        "CMAKE_SYSTEM_PREFIX_PATH": "", "CMAKE_PROGRAM_PATH": SYSTEM_PATH.replace(":", ";"),
        "Python3_EXECUTABLE": str(Path(sys.executable).resolve()), "LLVM_ENABLE_PIC": "ON",
        "LLVM_ENABLE_THREADS": "ON", "LLVM_ENABLE_UNWIND_TABLES": "ON", "LLVM_TARGETS_TO_BUILD": "",
        "LLVM_EXPERIMENTAL_TARGETS_TO_BUILD": "", "LLVM_ENABLE_PROJECTS": "", "LLVM_EXTERNAL_PROJECTS": "",
        "LLVM_ENABLE_RUNTIMES": "", "LLVM_BINDINGS_LIST": "", "LLVM_USE_SANITIZER": "",
        "LLVM_TARGET_ARCH": "AArch64", "LLVM_PARALLEL_COMPILE_JOBS": "4", "LLVM_PARALLEL_LINK_JOBS": "4"})
    if stage == "target":
        require(native is not None, "Target requires imported native llvm-tblgen")
        result.update({"CMAKE_SYSTEM_NAME": "iOS", "CMAKE_SYSTEM_PROCESSOR": "arm64",
            "CMAKE_C_COMPILER_TARGET": "arm64-apple-ios18.0", "CMAKE_CXX_COMPILER_TARGET": "arm64-apple-ios18.0",
            "CMAKE_ASM_COMPILER_TARGET": "arm64-apple-ios18.0",
            "CMAKE_EXE_LINKER_FLAGS": "-Wl,-no_adhoc_codesign", "CMAKE_SHARED_LINKER_FLAGS": "-Wl,-no_adhoc_codesign",
            "CMAKE_MODULE_LINKER_FLAGS": "-Wl,-no_adhoc_codesign", "LLVM_HOST_TRIPLE": "arm64-apple-ios18.0",
            "LLVM_DEFAULT_TARGET_TRIPLE": "arm64-apple-ios18.0", "LLVM_TABLEGEN": str(native),
            "CMAKE_CROSSCOMPILING_EMULATOR": ""})
    else:
        result.update({"CMAKE_EXE_LINKER_FLAGS": "", "CMAKE_SHARED_LINKER_FLAGS": "", "CMAKE_MODULE_LINKER_FLAGS": "",
                       "LLVM_HOST_TRIPLE": "arm64-apple-darwin", "LLVM_DEFAULT_TARGET_TRIPLE": "arm64-apple-darwin"})
    return result


def file_record(path, root):
    real_path(path, root, file=True)
    return {"path": str(path.relative_to(root)), "sha256": sha256(path), "bytes": path.stat().st_size}


def validate_native(root):
    root = real_path(root)
    manifest = json.loads(real_path(root / "manifest.json", root, True).read_text())
    require(manifest.get("schema") == 1 and manifest.get("stage") == "native" and manifest.get("status") == "complete", "Incomplete native control")
    require(manifest.get("llvm_commit") == LOCK["llvm_commit"] and manifest.get("source_lock_sha256") == sha256(LOCK_PATH), "Native source identity mismatch")
    require(manifest.get("helper_sha256") == sha256(Path(__file__)), "Native helper identity mismatch")
    require(manifest.get("jobs") == JOBS and manifest.get("deployment_target") == HOST_MIN, "Native configuration mismatch")
    require(manifest.get("cmake_version") == "4.3.4" and manifest.get("xcode_version") == "26.6", "Native toolchain mismatch")
    require(manifest.get("target_binaries_run") is False and manifest.get("sdk_copied") is False and manifest.get("explicit_signing_performed") is False, "Native control scope mismatch")
    outputs = json.loads(real_path(root / "manifests/outputs.json", root, True).read_text())
    require(sha256(root / "manifests/outputs.json") == manifest["outputs_sha256"], "Native output inventory changed")
    names = set()
    for row in outputs:
        rel = str(safe_relative(row["path"]))
        require(rel not in names, "Duplicate native output path")
        names.add(rel)
        require(file_record(root / rel, root) == row, f"Native exported file changed: {rel}")
    require({"native/bin/llvm-tblgen", "manifests/source.json", "manifests/preflight.json", "evidence/CMakeCache.txt", "notices/LLVM-LICENSE.TXT"} <= names, "Native evidence incomplete")
    require(sha256(root / "manifests/configuration.json") == manifest["configuration_sha256"], "Native configuration hash mismatch")
    require(sha256(root / "manifests/source.json") == manifest["source_manifest_sha256"], "Native source manifest mismatch")
    config = json.loads((root / "manifests/configuration.json").read_text())
    require(all(config.get(key) == "OFF" for key in OFF), "Native feature scope differs")
    require(config.get("CMAKE_OSX_DEPLOYMENT_TARGET") == HOST_MIN and config.get("LLVM_TARGETS_TO_BUILD") == "" and
            config.get("CMAKE_SKIP_RPATH") == "ON" and config.get("CMAKE_BUILD_TYPE") == "Release", "Native configuration differs")
    require(not any(k in config for k in ("CMAKE_SYSTEM_NAME", "CMAKE_TOOLCHAIN_FILE", "CMAKE_C_COMPILER_WORKS", "CMAKE_CXX_COMPILER_WORKS", "CMAKE_TRY_COMPILE_TARGET_TYPE")), "Native configuration hides compiler checks")
    binary = real_path(root / "native/bin/llvm-tblgen", root, True)
    require(file_record(binary, root) == manifest["binary"], "Native binary mismatch")
    proof = macho(binary.read_bytes(), 1, HOST_MIN, manifest["sdk_version"], True)
    require(proof == json.loads((root / "manifests/native-macho.json").read_text()), "Native Mach-O proof mismatch")
    return manifest, binary


class Control:
    def __init__(self, source, build, stage, native=None):
        require(stage in ("native", "target") and (native is None) == (stage == "native"), "Wrong stage/import arguments")
        self.source = real_path(source)
        self.build = Path(build).absolute()
        require(not self.build.exists() and not self.build.is_symlink(), "BUILD_ROOT must be fresh")
        real_path(self.build.parent, self.source / ".work")
        require(self.build.parent.is_relative_to(self.source / ".work"), "BUILD_ROOT must be under SOURCE_ROOT/.work")
        self.build.mkdir()
        for name in ("home", "tmp", "logs", "manifests", "evidence", "notices"):
            (self.build / name).mkdir()
        self.stage, self.native = stage, native
        self.requested_developer = os.environ.get("DEVELOPER_DIR") or None
        self.env = base_environment(self.build, self.requested_developer)
        self.llvm = self.source / "toolchains/llvm-project"
        self.obj = self.build / "build"
        self.prefix = self.build / ("native" if stage == "native" else "prefix")
        self.commands, self.tools, self.versions, self.resolved_tools = [], {}, {}, {}

    def run(self, name, argv, cwd=None, binary=False):
        require(re.fullmatch(r"[A-Za-z0-9_.-]+", name), "Invalid command label")
        output = self.build / "logs" / (name + ".log")
        require(not output.exists(), "Duplicate command label")
        record = {"name": name, "argv": [str(x) for x in argv], "cwd": str(cwd or self.build)}
        print(f"=== {name} ===", flush=True)
        start = time.monotonic()
        with output.open("wb") as stream:
            proc = subprocess.run(record["argv"], cwd=record["cwd"], env=self.env,
                                  stdout=stream, stderr=subprocess.STDOUT, check=False)
        record.update(exit_code=proc.returncode, seconds=round(time.monotonic() - start, 3))
        self.commands.append(record)
        write_json(self.build / "manifests/commands.json", self.commands)
        if proc.returncode:
            print(output.read_bytes()[-16000:].decode(errors="replace"), file=sys.stderr)
            raise CommandFailure(name, proc.returncode)
        return output.read_bytes() if binary else output.read_text(errors="replace").strip()

    def git(self, label, root, *args, binary=False):
        return self.run(label, ["/usr/bin/git", "-C", root, *args], binary=binary)

    def preflight(self):
        require(sys.platform == "darwin" and sys.version_info[:3] == (3, 12, 7), "macOS with Python3.12.7 required")
        require(self.run("host-arch", ["/usr/bin/uname", "-m"]) == "arm64", "arm64 host required")
        cpu = self.run("host-cpu", ["/usr/sbin/sysctl", "-n", "machdep.cpu.brand_string"])
        require(cpu in ("Apple M2", "Apple M2 (Virtual)"), "Unreviewed host CPU")
        osver = self.run("host-os", ["/usr/bin/sw_vers", "-productVersion"])
        require(version_number(osver) >= version_number(HOST_MIN), "Host older than native minimum")
        developer = self.requested_developer or self.run("developer-dir", ["/usr/bin/xcode-select", "-p"])
        dev = Path(developer).resolve()
        require(dev.is_absolute() and dev.is_dir() and dev.parts[-2:] == ("Contents", "Developer"), "Full Xcode Developer directory required")
        self.env = base_environment(self.build, dev)
        self.versions["xcode"] = self.run("xcode-version", ["/usr/bin/xcodebuild", "-version"])
        require(re.search(r"^Xcode 26\.6$", self.versions["xcode"], re.M), "Xcode26.6 required")
        self.sdks = {}
        for sdk in ("macosx", "iphoneos"):
            version = self.run(sdk + "-version", ["/usr/bin/xcrun", "--sdk", sdk, "--show-sdk-version"])
            version_number(version)
            self.versions[sdk] = version
            path = Path(self.run(sdk + "-path", ["/usr/bin/xcrun", "--sdk", sdk, "--show-sdk-path"])).resolve()
            require(path.is_dir() and path.is_relative_to(dev), "SDK outside selected Xcode")
            self.sdks[sdk] = str(path)
        require(self.versions["iphoneos"] == "26.5", "iPhoneOS SDK26.5 required")
        for name in ("clang", "clang++", "ar", "ranlib", "ld", "libtool"):
            value = self.run("find-" + name.replace("+", "x"), ["/usr/bin/xcrun", "--sdk", "macosx", "--find", name])
            self.tools[name], self.resolved_tools[name] = apple_tool_path(value, dev, name)
        self.tools["make"] = "/usr/bin/make"
        cmake = shutil.which("cmake", path="/opt/homebrew/bin:" + SYSTEM_PATH)
        require(cmake, "Existing CMake required; no package install allowed")
        self.tools["cmake"] = str(Path(cmake).resolve())
        for name, command in (("clang", [self.tools["clang"], "--version"]), ("make", [self.tools["make"], "--version"]),
                              ("cmake", [self.tools["cmake"], "--version"]), ("python", [sys.executable, "-I", "--version"]),
                              ("linker", [self.tools["ld"], "-v"])):
            self.versions[name] = self.run(name + "-version", command)
        require(re.search(r"^Apple clang version ", self.versions["clang"], re.M), "Real Apple clang required")
        require(re.search(r"^GNU Make 3\.81(?:\s|$)", self.versions["make"]), "Apple make3.81 required")
        require(self.versions["cmake"].splitlines()[0] == "cmake version 4.3.4", "CMake4.3.4 required")
        self.env["PATH"] = str(Path(self.tools["clang"]).parent) + ":" + SYSTEM_PATH
        for label, root, pin in (("madeira", self.source, LOCK["madeira_commit"]), ("llvm", self.llvm, LOCK["llvm_commit"])):
            real_path(root, self.source)
            require(Path(self.git(label + "-root", root, "rev-parse", "--show-toplevel")).resolve() == root, "Missing independent checkout: " + label)
            require(self.git(label + "-pin", root, "rev-parse", "HEAD") == pin, "Wrong source pin: " + label)
            self.git(label + "-clean", root, "diff", "--exit-code", "HEAD", "--", ".")
        require(not self.git("llvm-untracked", self.llvm, "ls-files", "--others", "--exclude-standard"), "Untracked LLVM source inputs")
        require(not self.git("llvm-ignored", self.llvm, "ls-files", "--others", "--ignored", "--exclude-standard"), "Ignored LLVM source inputs")
        require(shutil.disk_usage(self.build).free >= 6 * 1024**3, "At least6GiB fresh build capacity required")
        self.run("disk-space", ["/bin/df", "-h", self.build])
        write_json(self.build / "manifests/preflight.json", {"schema": 1, "status": "passed", "cpu": cpu,
            "os_version": osver, "developer_dir": str(dev), "developer_selection": "provider" if self.requested_developer else "xcode-select",
            "tools": self.tools, "resolved_apple_tools": self.resolved_tools,
            "tool_sha256": {name: sha256(path) for name, path in self.tools.items()},
            "python_path": str(Path(sys.executable).resolve()), "python_sha256": sha256(Path(sys.executable).resolve()),
            "versions": self.versions, "sdk_paths": self.sdks, "environment": self.env})

    def sources(self):
        rows, total, folded = [], 0, set()
        raw = self.git("llvm-source-tree", self.llvm, "ls-tree", "-r", "-z", "HEAD", "--", "llvm", "cmake", binary=True)
        for entry in raw.split(b"\0"):
            if not entry:
                continue
            meta, encoded = entry.split(b"\t", 1)
            name = encoded.decode("utf-8")
            if not selected_source(name):
                continue
            mode, kind, blob = meta.decode().split()
            require(mode in ("100644", "100755") and kind == "blob", "Source closure contains nonregular file")
            require(name.casefold() not in folded, "Source path case collision")
            folded.add(name.casefold())
            path = real_path(self.llvm / name, self.llvm, True)
            data = path.read_bytes()
            require(blob_hash(data) == blob, f"Tracked source byte mismatch: {name}")
            total += len(data)
            rows.append({"path": name, "git_blob_sha1": blob, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data), "mode": mode})
            require(len(rows) <= LOCK["source_copy_limit_files"] and total <= LOCK["source_copy_limit_bytes"], "Source closure exceeds cap")
        require(rows and any(r["path"].startswith("cmake/") for r in rows), "Incomplete LLVM/top-level cmake closure")
        mapped = {r["path"]: r for r in rows}
        for guard in LOCK["source_guards"]:
            require(mapped.get(guard["path"], {}).get("sha256") == guard["sha256"], "Reviewed source guard mismatch: " + guard["path"])
        write_json(self.build / "manifests/source.json", {"schema": 1, "llvm_commit": LOCK["llvm_commit"],
                   "official_source": "https://github.com/llvm/llvm-project/tree/" + LOCK["llvm_commit"], "bytes": total, "files": rows})
        shutil.copyfile(LOCK_PATH, self.build / "manifests/source-lock.json")
        if self.stage == "native":
            self.cmake_source = self.llvm / "llvm"
        else:
            root = self.build / "source"
            root.mkdir()
            for row in rows:
                out = root / row["path"]
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(self.llvm / row["path"], out)
                os.chmod(out, 0o755 if row["mode"] == "100755" else 0o644)
                require(sha256(out) == row["sha256"], "Source copy hash mismatch")
            patch_path = root / LOCK["patch"]["path"]
            patch_path.write_bytes(patch_addllvm(patch_path.read_bytes()))
            write_json(self.build / "manifests/source-overlay.json", LOCK["patch"])
            self.cmake_source = root / "llvm"
            self.env["GIT_CEILING_DIRECTORIES"] = str(root)
        self.copy_notices(rows)

    def copy_notices(self, rows):
        # Full notice-bearing source files preserve embedded upstream notices.
        # Additional exact audited paths are in source-lock.json.
        names = {r["path"] for r in rows if re.fullmatch(r"(?:LICENSE|COPYING|COPYRIGHT|NOTICE)(?:[._-].*)?", PurePosixPath(r["path"]).name, re.I)}
        names.update(LOCK.get("notice_sources", []))
        names.add("llvm/LICENSE.TXT")
        for name in sorted(names):
            src = real_path(self.llvm / name, self.llvm, True)
            out = self.build / "notices" / ("LLVM-LICENSE.TXT" if name == "llvm/LICENSE.TXT" else "source/" + name)
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, out)
        write_json(self.build / "manifests/notices.json", [file_record(p, self.build) for p in sorted((self.build / "notices").rglob("*")) if p.is_file()])

    def import_native(self):
        root = real_path(self.native, self.source / ".work")
        manifest, binary = validate_native(root)
        require(manifest["sdk_version"] == self.versions["macosx"], "Imported host SDK mismatch")
        destination = self.build / "host-tools/llvm-tblgen"
        destination.parent.mkdir()
        shutil.copyfile(binary, destination)
        os.chmod(destination, 0o755)
        require(sha256(destination) == manifest["binary"]["sha256"], "Native import copy changed")
        self.check_tblgen(destination, "imported-tblgen")
        write_json(self.build / "manifests/native-import.json", {"manifest_sha256": sha256(root / "manifest.json"),
                   "binary_sha256": sha256(destination), "llvm_commit": manifest["llvm_commit"]})
        return destination

    def check_tblgen(self, binary, name):
        proof = macho(binary.read_bytes(), 1, HOST_MIN, self.versions["macosx"], True)
        output = self.run(name + "-version", [binary, "--version"])
        require(re.search(r"\bLLVM version 15\.0\.7\b", output), "Wrong native llvm-tblgen version")
        return proof

    def configure_build(self):
        native = self.import_native() if self.stage == "target" else None
        self.sdk = self.sdks["macosx" if self.stage == "native" else "iphoneos"]
        self.definitions = cmake_definitions(self.stage, self.tools, self.sdk, self.prefix, native)
        write_json(self.build / "manifests/configuration.json", self.definitions)
        self.run("configure", [self.tools["cmake"], "-S", self.cmake_source, "-B", self.obj,
                 "-G", "Unix Makefiles", *["-D" + k + "=" + v for k, v in sorted(self.definitions.items())]])
        self.check_cache()
        targets = ["llvm-tblgen"] if self.stage == "native" else [*LOCK["target_libraries"], "llvm-headers"]
        self.run("build", [self.tools["cmake"], "--build", self.obj, "--parallel", "4", "--target", *targets, "--", "VERBOSE=1"])
        self.check_cache()

    def check_cache(self):
        cache = (self.obj / "CMakeCache.txt").read_text()
        entries = {}
        for line in cache.splitlines():
            match = re.fullmatch(r"([^#/:][^:]*):[^=]+=(.*)", line)
            if match:
                entries[match[1]] = match[2]
        for key, value in self.definitions.items():
            require(entries.get(key) == value, f"CMake changed requested setting {key}: {entries.get(key)!r}")
        require(not any(k.startswith("CMAKE_POLICY_") for k in entries), "Unexpected CMake policy override")
        for key in ("HAVE_CXX_ATOMICS_WITHOUT_LIB", "HAVE_CXX_ATOMICS64_WITHOUT_LIB"):
            require(entries.get(key) == "1", "Real native compiler atomic check failed: " + key)
        for key, value in entries.items():
            if key.endswith(("_LIBRARY", "_LIBRARIES", "_INCLUDE_DIR", "_INCLUDE_DIRS")) and ("/opt/homebrew/" in value or "/usr/local/" in value):
                raise ContractError("Host package leaked into CMake: " + key)
        config = (self.obj / "include/llvm/Config/config.h").read_text()
        require(not re.search(r"^#define (?:HAVE_LIBEDIT|HAVE_LIBPFM|HAVE_LIBXML2|LLVM_ENABLE_ZLIB|LLVM_ENABLE_ZSTD|HAVE_FFI_CALL) 1$", config, re.M), "Optional host dependency enabled")
        systems = list((self.obj / "CMakeFiles").glob("*/CMakeSystem.cmake"))
        require(len(systems) == 1, "Missing generated CMake system evidence")
        expected = "TRUE" if self.stage == "target" else "FALSE"
        require('set(CMAKE_CROSSCOMPILING "' + expected + '")' in systems[0].read_text(), "Wrong cross-compiling state")

    def evidence(self):
        required = ["CMakeCache.txt", "compile_commands.json", "CMakeFiles/CMakeConfigureLog.yaml",
                    "include/llvm/Config/config.h", "include/llvm/Config/llvm-config.h", "include/llvm/Config/abi-breaking.h"]
        extra = []
        extra.extend(str(p.relative_to(self.obj)) for p in (self.obj / "CMakeFiles").glob("*/CMake*Compiler.cmake"))
        extra.extend(str(p.relative_to(self.obj)) for p in (self.obj / "CMakeFiles").glob("*/CMakeSystem.cmake"))
        for pattern in ("**/link.txt", "**/flags.make", "**/build.make"):
            for path in self.obj.glob(pattern):
                rel = path.relative_to(self.obj)
                if "CMakeFiles" in rel.parts and ("llvm-tblgen.dir" in rel.parts or any(lib + ".dir" in rel.parts for lib in LOCK["target_libraries"])):
                    extra.append(str(rel))
        require(extra, "Missing generated command evidence")
        for name in sorted(set(required + extra)):
            src = real_path(self.obj / name, self.obj, True)
            require(src.stat().st_size <= 64 * 1024**2, "Evidence file exceeds cap")
            out = self.build / "evidence" / name
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, out)
        self.compiled_sources()

    def compiled_sources(self):
        rows, seen = [], set()
        used_sources = {}
        for command in json.loads((self.obj / "compile_commands.json").read_text()):
            args = command.get("arguments") or shlex.split(command["command"])
            require("-o" in args and args.index("-o") + 1 < len(args), "Missing compile output")
            obj = Path(command["directory"]) / args[args.index("-o") + 1]
            if not obj.exists():
                continue
            obj = real_path(obj, self.obj, True)
            require(str(obj) not in seen, "Repeated compiled object")
            seen.add(str(obj))
            require("-isysroot" in args and args[args.index("-isysroot") + 1] == self.sdk and
                    "-arch" in args and args[args.index("-arch") + 1] == "arm64", "Object compile flags lost SDK/architecture")
            require(not any("/opt/homebrew/" in a or "/usr/local/" in a for a in args), "Host package leaked into compile flags")
            src = Path(command["file"])
            base = self.cmake_source.parent if src.is_relative_to(self.cmake_source.parent) else self.obj
            src = real_path(src, base, True)
            rel = str(src.relative_to(base))
            allowed_assembly = any(row["source"] == rel and row["sha256"] == sha256(src)
                                   for row in LOCK["assembly_unspecified_sdk"])
            proof = macho(obj.read_bytes(), 1 if self.stage == "native" else 2,
                          HOST_MIN if self.stage == "native" else TARGET_MIN,
                          self.versions["macosx" if self.stage == "native" else "iphoneos"],
                          assembly_sdk_unspecified=allowed_assembly)
            out = self.build / "notices/compiled-source" / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, out)
            used_sources[rel] = src
            # Preserve complete inline notices in actually included upstream
            # headers/inc files. Dependency listings contain SDK paths, but
            # those paths are never opened or copied.
            if "-MF" in args:
                dep = Path(command["directory"]) / args[args.index("-MF") + 1]
                real_path(dep, self.obj, True)
                deptext = dep.read_text().replace("\\\n", " ")
                require(": " in deptext, "Malformed compiler dependency list")
                for value in shlex.split(deptext.split(": ", 1)[1]):
                    included = (Path(command["directory"]) / value).resolve()
                    if included.is_relative_to(self.cmake_source.parent):
                        included = real_path(included, self.cmake_source.parent, True)
                        used_sources[str(included.relative_to(self.cmake_source.parent))] = included
            rows.append({"source": rel, "source_sha256": sha256(src), "object": str(obj.relative_to(self.obj)),
                         "object_sha256": sha256(obj), "arguments": args, "macho": proof})
        require(rows, "No actual compiled source evidence")
        require(len(used_sources) <= 5000 and sum(p.stat().st_size for p in used_sources.values()) <= 128 * 1024**2,
                "Compiled source/notice dependency closure exceeds cap")
        for rel, source in sorted(used_sources.items()):
            out = self.build / "notices/compiled-source" / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            if out.exists():
                require(sha256(out) == sha256(source), "Compiled source notice collision")
            else:
                shutil.copyfile(source, out)
        write_json(self.build / "manifests/compiled-sources.json", rows)
        write_json(self.build / "manifests/notices.json", [file_record(p, self.build) for p in sorted((self.build / "notices").rglob("*")) if p.is_file()])

    def export(self):
        self.prefix.mkdir(exist_ok=True)
        if self.stage == "native":
            source = real_path(self.obj / "bin/llvm-tblgen", self.obj, True)
            proof = self.check_tblgen(source, "built-tblgen")
            binary = self.prefix / "bin/llvm-tblgen"
            binary.parent.mkdir()
            shutil.copyfile(source, binary)
            os.chmod(binary, 0o755)
            write_json(self.build / "manifests/native-macho.json", proof)
        else:
            (self.prefix / "lib").mkdir()
            proofs = []
            for name in LOCK["target_libraries"]:
                source = real_path(self.obj / "lib" / ("lib" + name + ".a"), self.obj, True)
                proofs.append(archive_members(source))
                shutil.copyfile(source, self.prefix / "lib" / source.name)
            write_json(self.build / "manifests/archive-members.json", proofs)
            self.export_headers()
        self.evidence()
        outputs = []
        for directory in (self.prefix.name, "logs", "manifests", "evidence", "notices"):
            outputs.extend(file_record(p, self.build) for p in sorted((self.build / directory).rglob("*")) if p.is_file())
        write_json(self.build / "manifests/outputs.json", outputs)
        manifest = {"schema": 1, "status": "complete", "stage": self.stage, "llvm_commit": LOCK["llvm_commit"],
            "madeira_commit": LOCK["madeira_commit"], "source_lock_sha256": sha256(LOCK_PATH), "helper_sha256": sha256(Path(__file__)),
            "jobs": JOBS, "deployment_target": HOST_MIN if self.stage == "native" else TARGET_MIN,
            "sdk_version": self.versions["macosx" if self.stage == "native" else "iphoneos"], "xcode_version": "26.6", "cmake_version": "4.3.4",
            "configuration_sha256": sha256(self.build / "manifests/configuration.json"),
            "source_manifest_sha256": sha256(self.build / "manifests/source.json"),
            "outputs_sha256": sha256(self.build / "manifests/outputs.json"),
            "target_binaries_run": False, "sdk_copied": False, "package_install_performed": False,
            "explicit_signing_performed": False, "target_libraries": LOCK["target_libraries"] if self.stage == "target" else []}
        if self.stage == "native":
            manifest["binary"] = file_record(binary, self.build)
        write_json(self.build / "manifest.json", manifest)

    def export_headers(self):
        inventory = {}
        for label, base, suffixes in (("source", self.cmake_source / "include", {".def", ".h", ".td", ".inc"}),
                                      ("generated", self.obj / "include", {".def", ".h", ".gen", ".inc"})):
            for subtree in ("llvm", "llvm-c"):
                for path in sorted((base / subtree).rglob("*")):
                    if not path.is_file() or "CMakeFiles" in path.parts or path.name == "config.h":
                        continue
                    if path.suffix not in suffixes and not (label == "source" and path.name == "LICENSE.TXT"):
                        continue
                    real_path(path, base, True)
                    rel = path.relative_to(base)
                    out = self.prefix / "include" / rel
                    require(str(rel) not in inventory, "Source/generated public header collision")
                    out.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(path, out)
                    inventory[str(rel)] = {"origin": label, **file_record(out, self.build)}
        require("llvm/Config/llvm-config.h" in inventory and "llvm/IR/Intrinsics.inc" in inventory and "llvm-c/Core.h" in inventory, "Incomplete LLVM public header export")
        write_json(self.build / "manifests/public-headers.json", list(inventory.values()))


def main(argv):
    require(len(argv) in (3, 4), "Expected SOURCE_ROOT BUILD_ROOT native|target [NATIVE_CONTROL_ROOT]")
    control = Control(*argv)
    try:
        control.preflight()
        control.sources()
        control.configure_build()
        control.export()
    except Exception as exc:
        write_json(control.build / "failure.json", {"status": "failed", "stage": control.stage, "error": str(exc),
                   "exit_code": exc.status if isinstance(exc, CommandFailure) else 1})
        raise
    print(json.dumps({"status": "complete", "stage": control.stage, "manifest": str(control.build / "manifest.json")}))


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except (ContractError, CommandFailure, OSError, ValueError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(exc.status if isinstance(exc, CommandFailure) else 1)
