#!/usr/bin/env python3
"""Manual source-only Wine header/server control. No runtime link or device test."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import signal
import struct
import subprocess
import sys
import time
import zipfile

MADEIRA = "279fd0f83170425db002fe25d6bd62f6355f497d"
WINE = "9129e9684daaeae70da9435e7c6060e59392634e"
# Executable recipes and prerequisite metadata are pinned to reviewed byte hashes.
RECIPE = "3ccb07ef0eea6fd1f7d3ed3316d09dba8fd6161d4f9e345980e512e19029848e"
PREPARE_RECIPE = "0baf7016b30e2bb8f65bd636cd4eb5c434e121957c9d96d904789799bf301e15"
TOOLS_LOCK = "376d136f4d7f6d4e7d4edc2b329e355686cb0c4aadd239517928f9ba8db228fe"
ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / ".work/madeira-wine-control"
OUT = ROOT / ".work/wine-control-artifacts"
EVIDENCE = SOURCE / "build/control-evidence"
ARCHIVE = SOURCE / "app/Madeira/libwineserver.a"
MIB = 1024 * 1024
SPARSE_PATHS = (
    "/.gitmodules", "/COPYING", "/LICENSE-EXCEPTION.md", "/LICENSES/", "/wine",
    "/build/wineserver/", "/build/ntdll-unix/shims/", "/build/hidpad/",
    "/build/madsync/", "/build/madeira_cfg.h",
    "/app/Madeira/Winios/WiniosGamepad.h", "/app/Madeira/Winios/WiniosPadEffects.h",
)
BASE_NAMES = "atom change clipboard completion console d3dkmt debugger device directory file hook mailslot mutex named_pipe procfs ptrace registry serial signal symlink timer token trace".split()
REPLACEMENT_NAMES = "wine_log_ios request_ios main_ios mach_ios unicode_ios fd_ios process_ios wineserver_ios_kill window user class region queue mapping winstation thread sock object async event semaphore handle inproc_sync hidpad_ios hidparse_ios storage_device_ios".split()
EXPECTED_MEMBERS = frozenset(name + ".o" for name in BASE_NAMES + REPLACEMENT_NAMES)
BSD_INDEX_MEMBERS = frozenset(("__.SYMDEF", "__.SYMDEF SORTED", "__.SYMDEF_64", "__.SYMDEF_64 SORTED"))
COLLISIONS = frozenset("_" + name for name in "alloc_user_handle free_user_handle get_virtual_screen_rect destroy_thread_windows get_window_thread is_desktop_class is_message_class is_window_visible mirror_region send_notify_message shared_session user_shared_data".split())
REQUIRED_SYMBOLS = frozenset({"_wineserver_main"} | {"_ws" + name for name in COLLISIONS})
REQUIRED_HEADERS = ("config.h", "dwrite.h", "dwrite_3.h", "mfobjects.h", "mftransform.h")
EVIDENCE_FILES = (
    "preflight.txt", "toolchain.txt", "objcopy-probe.c", "objcopy-probe.nm.txt",
    "objcopy-probe.load-commands.txt", "wine-configure.log", "wine-headers.log",
    "wine-config.h", "wine-config-sha256.txt", "server-source-manifest.json", "server-build.log",
    "libwineserver.a.arch.txt", "libwineserver.a.members.txt",
    "libwineserver.a.load-commands.txt", "libwineserver.a.symbols.txt", "archive-sha256.txt",
)
LIMITATIONS = (
    "Source-only control: native generated Wine headers and one arm64 iOS wineserver "
    "static archive. No full runtime link, FEX, DXMT, converter, Steam, IPA, signing "
    "or device test. Wine config.h is unchanged from --without-gnutls configuration; "
    "later ntdll/win32u work needs deliberate TLS configuration/prefix integration."
)


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(MIB), b""):
            h.update(block)
    return h.hexdigest()


def checked_file(path, cap, root=None):
    path = Path(path)
    if root is not None:
        root = Path(root).absolute()
        try:
            relative = path.absolute().relative_to(root)
        except ValueError as error:
            raise ValueError("Artifact outside permitted root") from error
        current = root
        if current.is_symlink():
            raise ValueError("Symlink artifact root")
        for part in relative.parts:
            current /= part
            if current.is_symlink():
                raise ValueError("Symlink artifact component")
    if path.is_symlink() or not path.is_file() or path.stat().st_size > cap:
        raise ValueError(f"Unsafe, absent or oversized artifact: {path.name}")
    return path


def safe_name(name):
    path = PurePosixPath(name)
    if not name or not path.parts or path.as_posix() != name or path.is_absolute() or ".." in path.parts or "\\" in name:
        raise ValueError("Unsafe ZIP member name")
    return name


def add_file(archive, path, name, cap, root=None):
    archive.write(checked_file(path, cap, root), safe_name(name))


def validate_members(members, expected=EXPECTED_MEMBERS):
    names = [line.strip() for line in members.splitlines() if line.strip() and line.strip() not in BSD_INDEX_MEMBERS]
    if len(names) != len(expected) or len(set(names)) != len(names) or set(names) != set(expected):
        raise ValueError("Archive members must be exactly the 49 pinned source objects, once each")
    return names


def validate_platform(arch, members, commands, expected=EXPECTED_MEMBERS):
    if not re.search(r"(?:architecture:|are:)\s+arm64\s*$", arch.strip()):
        raise ValueError("Archive is not exactly arm64")
    names = validate_members(members, expected)
    # otool -l emits a separate archive(member.o): section for each real object.
    sections = re.split(r"^.*\(([^()\n]+\.o)\)(?: \(architecture arm64\))?:\s*$", commands, flags=re.M)
    found = {}
    for index in range(1, len(sections), 2):
        name, block = sections[index:index + 2]
        if name in found:
            raise ValueError("Duplicate member platform section")
        modern = len(re.findall(r"^\s*cmd LC_BUILD_VERSION\s*$", block, re.M))
        legacy = len(re.findall(r"^\s*cmd LC_VERSION_MIN_IPHONEOS\s*$", block, re.M))
        platforms = re.findall(r"^\s*platform (\S+)\s*$", block, re.M)
        if modern + legacy != 1 or len(platforms) != modern or any(p not in ("IOS", "2") for p in platforms):
            raise ValueError(f"Object {name} lacks exactly one iOS platform command")
        if re.search(r"\bcmd LC_VERSION_MIN_(?:MACOSX|TVOS|WATCHOS)\b", block):
            raise ValueError("Conflicting object platform metadata")
        command_block = re.search(r"^\s*cmd LC_(?:BUILD_VERSION|VERSION_MIN_IPHONEOS)\s*$([\s\S]*?)(?=^\s*cmd |\Z)", block, re.M)
        key = "minos" if modern else "version"
        minima = re.findall(r"^\s*" + key + r" (\S+)\s*$", command_block[1], re.M)
        if minima not in (["17.0"], ["17.0.0"]):
            raise ValueError("Object deployment target must be exactly iOS 17.0")
        found[name] = True
    if set(found) != set(names):
        raise ValueError("Missing or unexpected per-member platform evidence")
    return len(names)


def validate_macho(data, name):
    if len(data) < 32:
        raise ValueError(f"Truncated Mach-O object: {name}")
    magic, cpu, subtype, kind, ncmds, size, flags, reserved = struct.unpack_from("<8I", data)
    if magic != 0xFEEDFACF or cpu != 0x0100000C or kind != 1:
        raise ValueError(f"Member must be a thin arm64 Mach-O object: {name}")
    if ncmds > 4096 or size > len(data) - 32:
        raise ValueError("Invalid Mach-O load-command bounds")
    offset, platforms, minima = 32, [], []
    for unused in range(ncmds):
        if offset + 8 > 32 + size:
            raise ValueError("Truncated Mach-O command")
        command, length = struct.unpack_from("<2I", data, offset)
        if length < 8 or length % 4 or offset + length > 32 + size:
            raise ValueError("Invalid Mach-O command size")
        if command == 0x32:  # LC_BUILD_VERSION
            if length < 24:
                raise ValueError("Truncated build-version command")
            platforms.append(struct.unpack_from("<I", data, offset + 8)[0])
            minima.append(struct.unpack_from("<I", data, offset + 12)[0])
        elif command in (0x24, 0x25, 0x2F, 0x30):
            if length < 16:
                raise ValueError("Truncated legacy platform command")
            platforms.append(2 if command == 0x25 else -1)
            minima.append(struct.unpack_from("<I", data, offset + 8)[0])
        offset += length
    if offset != 32 + size or platforms != [2] or minima != [0x00110000]:
        raise ValueError(f"Member must contain exactly one iOS 17.0 platform command: {name}")


def validate_archive(path, expected=EXPECTED_MEMBERS):
    """Check actual bytes; never infer every object's CPU/platform from lipo alone."""
    checked_file(path, 256 * MIB)
    names, inventory = [], []
    with Path(path).open("rb") as stream:
        if stream.read(8) != b"!<arch>\n":
            raise ValueError("Only regular ar archives are permitted")
        while True:
            header = stream.read(60)
            if not header:
                break
            if len(header) != 60 or header[58:] != b"`\n":
                raise ValueError("Malformed ar header")
            try:
                length = int(header[48:58].decode("ascii").strip())
                raw_name = header[:16].decode("ascii").strip()
            except (ValueError, UnicodeError) as error:
                raise ValueError("Invalid ar member header") from error
            if length < 0 or length > 32 * MIB:
                raise ValueError("Oversized ar member")
            data = stream.read(length)
            if len(data) != length:
                raise ValueError("Truncated ar member")
            if length % 2 and stream.read(1) != b"\n":
                raise ValueError("Invalid ar alignment padding")
            if raw_name.startswith("#1/"):
                name_length = int(raw_name[3:])
                if name_length <= 0 or name_length > min(length, 4096):
                    raise ValueError("Invalid BSD ar name length")
                name = data[:name_length].rstrip(b"\0").decode("ascii")
                data = data[name_length:]
            else:
                name = raw_name.rstrip("/")
            if name in BSD_INDEX_MEMBERS:
                continue
            if name not in expected or name in names:
                raise ValueError("Unknown or duplicate real archive member")
            validate_macho(data, name)
            names.append(name)
            inventory.append({"member": name, "sha256": hashlib.sha256(data).hexdigest(),
                              "size": len(data), "architecture": "arm64", "platform": "iOS"})
    validate_members("\n".join(names), expected)
    return inventory


def validate_symbols(symbols):
    seen, defined = set(), set()
    for line in symbols.splitlines():
        if line.split() and line.split()[-1] in COLLISIONS:
            raise ValueError("Original colliding symbol survives in global nm evidence")
        # nm -g: both definitions and undefined references are deliberately retained.
        match = re.match(r"^\s*(?:[0-9a-fA-F]+\s+)?([A-Za-z?])\s+(\S+)\s*$", line)
        if not match:
            continue
        kind, name = match.groups()
        seen.add(name)
        if kind not in ("U", "u", "?"):
            defined.add(name)
    if seen & COLLISIONS:
        raise ValueError("Original colliding symbols survive as definitions or references")
    if not REQUIRED_SYMBOLS <= defined:
        raise ValueError("Required server/renamed symbols must be global definitions")
    return sorted(REQUIRED_SYMBOLS)


class Control:
    def __init__(self):
        self.deadline = time.monotonic() + 41 * 60
        self.steps = []

    def ensure_budget(self):
        if time.monotonic() >= self.deadline:
            raise RuntimeError("Aggregate tool/source control budget exhausted")

    def run(self, label, *args, cwd=ROOT, seconds=None):
        if not re.fullmatch(r"[a-z0-9-]+", label) or any(s["label"] == label for s in self.steps):
            raise ValueError("Unsafe or reused step label")
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeError("Aggregate tool/source control budget exhausted")
        timeout = min(remaining, seconds or remaining)
        log, started = OUT / (label + ".log"), time.monotonic()
        # Nothing enumerates or uploads the environment. CI log has no credential commands.
        env = dict(os.environ, GIT_TERMINAL_PROMPT="0", JOBS="4", LC_ALL="C")
        with log.open("wb") as stream:
            proc = subprocess.Popen(args, cwd=cwd, env=env, stdout=stream,
                                    stderr=subprocess.STDOUT, start_new_session=True)
            try:
                while True:
                    if time.monotonic() - started >= timeout or log.stat().st_size > 64 * MIB:
                        try:
                            os.killpg(proc.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                        proc.wait()
                        code = 124
                        break
                    try:
                        code = proc.wait(timeout=min(0.25, max(0.01, timeout - (time.monotonic() - started))))
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
            with log.open("rb") as stream:
                stream.seek(max(0, log.stat().st_size - 24000))
                print(stream.read().decode("utf-8", errors="replace"), flush=True)
            raise RuntimeError(f"{label} failed with exit {code}")
        return log.read_text(errors="replace") if log.stat().st_size < MIB else ""


def source_bounds(root):
    """Do not recurse through symlinks; include git object storage in the disk bound."""
    total = count = 0
    for current, dirs, files in os.walk(root, followlinks=False):
        if any((Path(current) / d).is_symlink() for d in dirs):
            raise ValueError("Symlink source directory")
        for name in files:
            path = Path(current) / name
            if path.is_symlink():
                continue  # Source symlinks are never packaged or followed.
            total += path.stat().st_size
            count += 1
            if total > 4 * 1024 * MIB or count > 200000:
                raise ValueError("Source checkout exceeds 4 GiB/200000-file control bound")
    return {"files": count, "bytes": total}


def collect_licenses():
    selected = []
    for tag, repo in (("Madeira", SOURCE), ("Wine", SOURCE / "wine")):
        candidates = [p for p in repo.iterdir() if re.fullmatch(r"(?:LICENSE|COPYING|NOTICE)(?:[._-].*)?", p.name, re.I)]
        if tag == "Madeira":
            candidates += list((repo / "LICENSES").rglob("*"))
        else:
            candidates += [p for p in (repo / "libs").rglob("*") if re.fullmatch(r"(?:LICENSE|COPYING|NOTICE)(?:[._-].*)?", p.name, re.I)]
        for path in sorted(set(candidates)):
            if path.is_dir() and not path.is_symlink():
                continue
            checked_file(path, 4 * MIB, repo)
            selected.append((path, "Licenses/" + tag + "/" + path.relative_to(repo).as_posix()))
    if not (SOURCE / "COPYING").is_file() or not (SOURCE / "wine/COPYING.LIB").is_file():
        raise ValueError("Required source license notices missing")
    if len(selected) > 128 or sum(p.stat().st_size for p, unused in selected) > 16 * MIB:
        raise ValueError("License bundle bounds exceeded")
    return selected


def generated_headers(root):
    checked_file(root / "config.h", 4 * MIB, root)
    files, total = [], 0
    for current, dirs, names in os.walk(root, followlinks=False):
        if any((Path(current) / name).is_symlink() for name in dirs):
            raise ValueError("Generated header directory symlink")
        for name in names:
            path = Path(current) / name
            if path.is_symlink():
                raise ValueError("Generated header symlink")
            if path.suffix != ".h":
                continue
            checked_file(path, 16 * MIB, root)
            total += path.stat().st_size
            files.append(path)
    if len(files) > 5000 or total > 128 * MIB:
        raise ValueError("Generated headers exceed 5000 files/128 MiB")
    if not all((root / name).is_file() and (root / name).stat().st_size for name in REQUIRED_HEADERS):
        raise ValueError("Required real generated Wine headers missing")
    return sorted(files)


def write_headers(report, licenses):
    root = SOURCE / "wine/build-macos/include"
    files = generated_headers(root)
    config_evidence = checked_file(EVIDENCE / "wine-config.h", 4 * MIB, SOURCE)
    if digest(config_evidence) != digest(root / "config.h"):
        raise ValueError("Generated config.h differs from recorded unmodified configuration")
    manifest = [{"path": p.relative_to(root).as_posix(), "sha256": digest(p), "size": p.stat().st_size} for p in files]
    report["headers"] = {"result": "running", "count": len(files), "bytes": sum(i["size"] for i in manifest),
                         "config_sha256": digest(root / "config.h")}
    temporary = OUT / "wine-headers.zip.part"
    with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            add_file(archive, path, "include/" + path.relative_to(root).as_posix(), 16 * MIB, root)
        for path, name in licenses:
            add_file(archive, path, name, 4 * MIB, SOURCE)
        archive.writestr("SHA256SUMS", "".join(i["sha256"] + "  include/" + i["path"] + "\n" for i in manifest))
        archive.writestr("source-and-header-manifest.json", json.dumps({"madeira": MADEIRA, "wine": WINE,
            "recipe_sha256": RECIPE, "wrapper_sha256": report["wrapper_sha256"], "headers": manifest,
            "licenses": report.get("licenses", []),
            "scope": LIMITATIONS, "runtime_linked": False, "device_tested": False}, indent=2))
    temporary.replace(OUT / "wine-headers.zip")
    report["headers"]["result"] = "passed"


def validate_source_manifest(manifest):
    if manifest.get("madeira_commit") != MADEIRA or manifest.get("wine_commit") != WINE:
        raise ValueError("Source manifest pins do not match")
    if manifest.get("archive_only") is not True or manifest.get("runtime_linked") is not False:
        raise ValueError("Source manifest scope does not match")
    if len(manifest.get("expected_members", [])) != 49 or set(manifest["expected_members"]) != EXPECTED_MEMBERS:
        raise ValueError("Source manifest expected members do not match exactly")
    validate_members("\n".join(manifest["expected_members"]))
    if sorted(manifest.get("base_units", [])) != sorted(BASE_NAMES):
        raise ValueError("Source manifest base units do not match")
    if {"_" + name for name in manifest.get("collisions", [])} != COLLISIONS:
        raise ValueError("Source manifest collisions do not match")
    entries = manifest.get("source_files", [])
    if len(entries) != 51 or len({entry.get("path") for entry in entries}) != 51:
        raise ValueError("Expected 49 compilation sources plus included HID parser and server main sources")
    for entry in entries:
        name = safe_name(entry["path"])
        path = checked_file(SOURCE / name, 16 * MIB, SOURCE)
        if not re.fullmatch(r"[0-9a-f]{64}", entry.get("sha256", "")) or digest(path) != entry["sha256"]:
            raise ValueError("Source manifest hash mismatch")
    return manifest


def write_server(report, licenses):
    inventory = validate_archive(ARCHIVE)
    names = (EVIDENCE / "libwineserver.a.members.txt").read_text()
    validate_platform((EVIDENCE / "libwineserver.a.arch.txt").read_text(), names,
                      (EVIDENCE / "libwineserver.a.load-commands.txt").read_text())
    symbols = validate_symbols((EVIDENCE / "libwineserver.a.symbols.txt").read_text())
    manifest_path = checked_file(EVIDENCE / "server-source-manifest.json", 4 * MIB, SOURCE)
    validate_source_manifest(json.loads(manifest_path.read_text()))
    recorded_hash = (EVIDENCE / "archive-sha256.txt").read_text().split()[0]
    if recorded_hash != digest(ARCHIVE):
        raise ValueError("Archive differs from recorded source-stage hash")
    report["wineserver"] = {"result": "running", "sha256": digest(ARCHIVE), "size": ARCHIVE.stat().st_size,
                            "members": inventory, "required_global_definitions": symbols}
    temporary = OUT / "wineserver-ios-archive.zip.part"
    with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
        add_file(archive, ARCHIVE, "Archives/libwineserver.a", 256 * MIB, SOURCE)
        add_file(archive, manifest_path, "server-source-manifest.json", 4 * MIB, SOURCE)
        for path, name in licenses:
            add_file(archive, path, name, 4 * MIB, SOURCE)
        archive.writestr("SHA256SUMS", digest(ARCHIVE) + "  Archives/libwineserver.a\n")
        final_report = dict(report, result="passed-source-control-only",
                            wineserver=dict(report["wineserver"], result="passed"))
        archive.writestr("source-and-archive-manifest.json", json.dumps(final_report, indent=2))
    temporary.replace(OUT / "wineserver-ios-archive.zip")
    report["wineserver"]["result"] = "passed"


def write_evidence(report, control, helper):
    (OUT / "result.json").write_text(json.dumps(report, indent=2) + "\n")
    total = 0
    with zipfile.ZipFile(OUT / "wine-evidence.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        add_file(archive, OUT / "result.json", "result.json", 4 * MIB, OUT)
        candidates = [(OUT / (s["label"] + ".log"), "Logs/" + s["label"] + ".log") for s in control.steps]
        candidates += [(EVIDENCE / name, "Evidence/" + name) for name in EVIDENCE_FILES]
        candidates += [(OUT / "ToolSetup" / name, "ToolSetup/" + name) for name in
                       ("homebrew-before.json", "homebrew-after.json", "homebrew-install.log", "homebrew-tools.json")]
        candidates += [(SOURCE / "wine/build-macos/config.log", "Configuration/config.log"),
                       (SOURCE / "wine/build-macos/Makefile", "Configuration/Makefile"),
                       (SOURCE / "build/wineserver/build.sh", "Source/upstream-wineserver-build.sh"),
                       (SOURCE / "build/wineserver/config_ios.h", "Source/config_ios.h"),
                       (SOURCE / "wine/server/Makefile.in", "Source/wine-server-Makefile.in"),
                       (helper, "Source/wine-core-control.sh"),
                       (ROOT / "ci/prepare_wine_tools.py", "Source/prepare_wine_tools.py"),
                       (ROOT / "ci/homebrew-wine-tools-lock.json", "Source/homebrew-wine-tools-lock.json"),
                       (Path(__file__), "Source/run_wine_control.py")]
        omissions = []
        for path, name in candidates:
            if not path.exists() and not path.is_symlink():
                continue
            try:
                checked_file(path, 64 * MIB, ROOT)
                size = min(path.stat().st_size, 8 * MIB)
                if total + size > 96 * MIB:
                    omissions.append({"path": name, "reason": "96 MiB total evidence cap"})
                    continue
                with path.open("rb") as stream:
                    if path.stat().st_size > size:
                        stream.seek(path.stat().st_size - size)
                        name += ".tail"
                    archive.writestr(safe_name(name), stream.read(size))
                total += size
            except ValueError as error:
                omissions.append({"path": name, "reason": str(error)})
        archive.writestr("evidence-omissions.json", json.dumps(omissions, indent=2))
    print("WINE_CONTROL_RESULT=" + json.dumps(report, sort_keys=True), flush=True)


def main():
    if sys.platform != "darwin":
        raise SystemExit("Approved macOS runner required")
    if os.environ.get("FREE_QUOTA_VERIFIED") != "true" or os.environ.get("PRIVATE_SOURCE_VERIFIED") != "true":
        raise SystemExit("Manual free/private checks must be exactly true")
    if os.environ.get("WINE_TOOLS_INSTALL_APPROVED") != "true":
        raise SystemExit("Explicit prerequisite installation approval must be exactly true")
    helper = checked_file(ROOT / "ci/wine-core-control.sh", MIB, ROOT)
    if not re.fullmatch(r"[0-9a-f]{64}", RECIPE) or os.environ.get("EXPECTED_RECIPE_SHA256") != RECIPE or digest(helper) != RECIPE:
        raise SystemExit("Helper is not the exact reviewed recipe; proposal is fail-closed until pinned")
    prepare = checked_file(ROOT / "ci/prepare_wine_tools.py", MIB, ROOT)
    lock = checked_file(ROOT / "ci/homebrew-wine-tools-lock.json", MIB, ROOT)
    for pin, path, variable in ((PREPARE_RECIPE, prepare, "EXPECTED_TOOLS_PREPARE_SHA256"),
                                (TOOLS_LOCK, lock, "EXPECTED_TOOLS_LOCK_SHA256")):
        if not re.fullmatch(r"[0-9a-f]{64}", pin) or os.environ.get(variable) != pin or digest(path) != pin:
            raise SystemExit("Tool preparation or lock is not the exact reviewed proposal")
    for path in (SOURCE, OUT):
        current = ROOT
        for part in path.relative_to(ROOT).parts[:-1]:
            current /= part
            if current.is_symlink():
                raise SystemExit("Symlink work directory refused")
    if SOURCE.exists() or SOURCE.is_symlink() or OUT.exists() or OUT.is_symlink():
        raise SystemExit("Fresh source and evidence directories required")
    OUT.mkdir(parents=True)
    SOURCE.mkdir(parents=True)
    control = Control()
    report = {"result": "failed", "scope": LIMITATIONS, "madeira": MADEIRA, "wine": WINE,
              "recipe_sha256": RECIPE, "tool_prepare_sha256": PREPARE_RECIPE, "tools_lock_sha256": TOOLS_LOCK,
              "wrapper_sha256": digest(Path(__file__)), "jobs": 4,
              "aggregate_budget_seconds": 2460, "tool_setup_budget_seconds": 480, "source_budget_seconds": 1980,
              "headers": {"result": "not-run"}, "wineserver": {"result": "not-run"},
              "runtime_linked": False, "ipa_created": False, "device_tested": False,
              "source_only": True, "steps": control.steps}
    try:
        control.run("prepare-tools", sys.executable, str(prepare), str(OUT / "ToolSetup"), seconds=480)
        control.deadline = min(control.deadline, time.monotonic() + 33 * 60)
        control.run("git-init", "git", "init", "--quiet", cwd=SOURCE)
        control.run("git-remote", "git", "remote", "add", "origin", "https://github.com/willfaust/Madeira.git", cwd=SOURCE)
        control.run("git-fetch", "git", "fetch", "--depth=1", "--filter=blob:none", "origin", MADEIRA, cwd=SOURCE, seconds=180)
        control.run("sparse-init", "git", "sparse-checkout", "init", "--no-cone", cwd=SOURCE)
        control.run("sparse-paths", "git", "sparse-checkout", "set", "--no-cone", "--", *SPARSE_PATHS, cwd=SOURCE)
        control.run("git-checkout", "git", "checkout", "--detach", "FETCH_HEAD", cwd=SOURCE, seconds=180)
        actual = control.run("madeira-pin", "git", "rev-parse", "HEAD", cwd=SOURCE).strip()
        if actual != MADEIRA:
            raise ValueError("Unexpected Madeira pin")
        report["madeira_checkout"] = source_bounds(SOURCE)
        # Tool/Bison/objcopy/SDK checks deliberately precede the large Wine checkout.
        control.run("preflight", "bash", str(helper), str(SOURCE), "preflight", seconds=180)
        control.run("wine-fetch", "git", "-c", "submodule.wine.url=https://github.com/willfaust/wine.git", "submodule", "update", "--init", "--depth=1", "--", "wine", cwd=SOURCE, seconds=480)
        actual = control.run("wine-pin", "git", "rev-parse", "HEAD", cwd=SOURCE / "wine").strip()
        if actual != WINE:
            raise ValueError("Unexpected Wine pin")
        report["source_checkout"] = source_bounds(SOURCE)
        licenses = collect_licenses()
        report["licenses"] = [{"path": name, "sha256": digest(path), "size": path.stat().st_size}
                              for path, name in licenses]
        report["headers"]["result"] = "running"
        control.run("wine-headers", "bash", str(helper), str(SOURCE), "wine-headers")
        write_headers(report, licenses)
        report["wineserver"]["result"] = "running"
        control.run("wineserver", "bash", str(helper), str(SOURCE), "wineserver")
        control.run("madeira-final-diff", "git", "diff", "--exit-code", "HEAD", "--", ".", cwd=SOURCE)
        control.run("wine-final-diff", "git", "diff", "--exit-code", "HEAD", "--", ".", cwd=SOURCE / "wine")
        control.ensure_budget()
        write_server(report, licenses)
        control.ensure_budget()
        report["result"] = "passed-source-control-only"
    except Exception as error:
        report["failure"] = str(error)
        for stage in ("headers", "wineserver"):
            if report[stage]["result"] == "running":
                report[stage]["result"] = "failed"
        if report["wineserver"]["result"] == "passed":
            report["wineserver"]["result"] = "failed"
        (OUT / "wineserver-ios-archive.zip").unlink(missing_ok=True)
        print(str(error), file=sys.stderr, flush=True)
    finally:
        for partial in (OUT / "wine-headers.zip.part", OUT / "wineserver-ios-archive.zip.part"):
            partial.unlink(missing_ok=True)
        write_evidence(report, control, helper)
    return 0 if report["result"] == "passed-source-control-only" else 1


if __name__ == "__main__":
    raise SystemExit(main())
