#!/usr/bin/env python3
"""Manual, pinned FreeType + win32u iOS archive control; never a runtime claim."""
import base64
import hashlib
import importlib.util
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
FREETYPE = "42608f77f20749dd6ddc9e0536788eaad70ea4b5"
# Review and replace only after the exact helper/importer/producer input are frozen.
RECIPE = "05e97762b7502197bc70d02a7423f14427dc6ee571646cea380c0220853fbcfc"
IMPORTER = "6e2b8cae1e902398e6020e0eaae07b67acf5c6da194c458a2f42ec53f7d70d48"
HEADER_LOCK = "2a09ed86bad836a7c86e83bd032b2c1652a2eb93735e73cb33db7f79b6bb8055"
SOURCE_LOCK = "7b3c9c889dcd039cb3c7f8b09b600ad4bc418899e6ac62661705179bf05f51cc"
# The exact pinned Madeira recipe uses this upstream mirror. No fallback is allowed.
FREETYPE_URL = "https://github.com/freetype/freetype.git"
ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / ".work/madeira-win32u-control"
OUT = ROOT / ".work/win32u-control-artifacts"
EVIDENCE = SOURCE / "build/win32u-control-evidence"
FT_ARCHIVE = SOURCE / "build/freetype-ios/build/libfreetype.a"
RAW_ARCHIVE = SOURCE / "build/win32u-unix/control-unmerged.a"
ARCHIVE = SOURCE / "app/Madeira/libwin32u_unix.a"
MIB = 1024 * 1024
AGGREGATE_SECONDS = 23 * 60
SPARSE_PATHS = (
    "/.gitmodules", "/COPYING", "/LICENSE", "/LICENSE-EXCEPTION.md", "/THIRD-PARTY-NOTICES.md", "/LICENSES/",
    "/docs/LICENSING.md", "/docs/wine-lgpl-provenance.md",
    "/build/win32u-unix/", "/build/freetype-ios/", "/build/ntdll-unix/shims/",
    "/build/madeira_cfg.h", "/app/Madeira/Winios/WiniosGamepad.h",
)
WINE_SPARSE_PATHS = ("/include/", "/dlls/win32u/", "/COPYING.LIB", "/LICENSE", "/LICENSE-MADEIRA.md", "/LICENSE.OLD", "/LICENSES/", "/AUTHORS")
BSD_INDEX_MEMBERS = frozenset(("__.SYMDEF", "__.SYMDEF SORTED", "__.SYMDEF_64", "__.SYMDEF_64 SORTED"))
FT_NAMES = 'autofit bdf cff ftbase ftbbox ftbdf ftbitmap ftbzip2 ftcache ftcid ftdebug ftfstype ftgasp ftglyph ftgxval ftgzip ftinit ftlzw ftmm ftotval ftpatent ftpfr ftstroke ftsynth ftsystem fttype1 ftwinfnt pcf pfr psaux pshinter psnames raster sdf sfnt smooth svg truetype type1 type1cid type42 winfnt'
FT_MEMBERS = frozenset(name + ".c.o" for name in FT_NAMES.split())
WIN32U_SOURCES = {'bitblt.o': 'wine/dlls/win32u/bitblt.c',
 'bitmap.o': 'wine/dlls/win32u/bitmap.c',
 'brush.o': 'wine/dlls/win32u/brush.c',
 'class.o': 'build/win32u-unix/class_ios.c',
 'clipboard.o': 'wine/dlls/win32u/clipboard.c',
 'clipping.o': 'wine/dlls/win32u/clipping.c',
 'cursoricon.o': 'wine/dlls/win32u/cursoricon.c',
 'd3dkmt.o': 'build/win32u-unix/d3dkmt_ios.c',
 'dc.o': 'wine/dlls/win32u/dc.c',
 'dce.o': 'wine/dlls/win32u/dce.c',
 'defwnd.o': 'build/win32u-unix/defwnd_ios.c',
 'dib.o': 'wine/dlls/win32u/dib.c',
 'dibdrv_bitblt.o': 'wine/dlls/win32u/dibdrv/bitblt.c',
 'dibdrv_dc.o': 'wine/dlls/win32u/dibdrv/dc.c',
 'dibdrv_graphics.o': 'wine/dlls/win32u/dibdrv/graphics.c',
 'dibdrv_objects.o': 'wine/dlls/win32u/dibdrv/objects.c',
 'dibdrv_primitives.o': 'wine/dlls/win32u/dibdrv/primitives.c',
 'driver.o': 'build/win32u-unix/driver_ios.c',
 'emfdrv.o': 'wine/dlls/win32u/emfdrv.c',
 'font.o': 'wine/dlls/win32u/font.c',
 'freetype.o': 'build/win32u-unix/freetype_ios.c',
 'gdiobj.o': 'wine/dlls/win32u/gdiobj.c',
 'hook.o': 'wine/dlls/win32u/hook.c',
 'imm.o': 'wine/dlls/win32u/imm.c',
 'input.o': 'wine/dlls/win32u/input.c',
 'mapping.o': 'wine/dlls/win32u/mapping.c',
 'menu.o': 'wine/dlls/win32u/menu.c',
 'message.o': 'build/win32u-unix/message_ios.c',
 'opengl.o': 'wine/dlls/win32u/opengl.c',
 'opentype.o': 'wine/dlls/win32u/opentype.c',
 'painting.o': 'wine/dlls/win32u/painting.c',
 'palette.o': 'wine/dlls/win32u/palette.c',
 'path.o': 'wine/dlls/win32u/path.c',
 'pen.o': 'wine/dlls/win32u/pen.c',
 'printdrv.o': 'wine/dlls/win32u/printdrv.c',
 'rawinput.o': 'wine/dlls/win32u/rawinput.c',
 'region.o': 'wine/dlls/win32u/region.c',
 'scroll.o': 'wine/dlls/win32u/scroll.c',
 'spy.o': 'wine/dlls/win32u/spy.c',
 'syscall.o': 'build/win32u-unix/syscall_ios.c',
 'sysparams.o': 'build/win32u-unix/sysparams_ios.c',
 'systray.o': 'wine/dlls/win32u/systray.c',
 'vertical.o': 'wine/dlls/win32u/vertical.c',
 'vulkan.o': 'wine/dlls/win32u/vulkan.c',
 'window.o': 'wine/dlls/win32u/window.c',
 'winstation.o': 'build/win32u-unix/winstation_ios.c'}
FT_SOURCES = {'autofit.c.o': 'research/freetype/src/autofit/autofit.c',
 'bdf.c.o': 'research/freetype/src/bdf/bdf.c',
 'cff.c.o': 'research/freetype/src/cff/cff.c',
 'ftbase.c.o': 'research/freetype/src/base/ftbase.c',
 'ftbbox.c.o': 'research/freetype/src/base/ftbbox.c',
 'ftbdf.c.o': 'research/freetype/src/base/ftbdf.c',
 'ftbitmap.c.o': 'research/freetype/src/base/ftbitmap.c',
 'ftbzip2.c.o': 'research/freetype/src/bzip2/ftbzip2.c',
 'ftcache.c.o': 'research/freetype/src/cache/ftcache.c',
 'ftcid.c.o': 'research/freetype/src/base/ftcid.c',
 'ftdebug.c.o': 'research/freetype/src/base/ftdebug.c',
 'ftfstype.c.o': 'research/freetype/src/base/ftfstype.c',
 'ftgasp.c.o': 'research/freetype/src/base/ftgasp.c',
 'ftglyph.c.o': 'research/freetype/src/base/ftglyph.c',
 'ftgxval.c.o': 'research/freetype/src/base/ftgxval.c',
 'ftgzip.c.o': 'research/freetype/src/gzip/ftgzip.c',
 'ftinit.c.o': 'research/freetype/src/base/ftinit.c',
 'ftlzw.c.o': 'research/freetype/src/lzw/ftlzw.c',
 'ftmm.c.o': 'research/freetype/src/base/ftmm.c',
 'ftotval.c.o': 'research/freetype/src/base/ftotval.c',
 'ftpatent.c.o': 'research/freetype/src/base/ftpatent.c',
 'ftpfr.c.o': 'research/freetype/src/base/ftpfr.c',
 'ftstroke.c.o': 'research/freetype/src/base/ftstroke.c',
 'ftsynth.c.o': 'research/freetype/src/base/ftsynth.c',
 'ftsystem.c.o': 'research/freetype/builds/unix/ftsystem.c',
 'fttype1.c.o': 'research/freetype/src/base/fttype1.c',
 'ftwinfnt.c.o': 'research/freetype/src/base/ftwinfnt.c',
 'pcf.c.o': 'research/freetype/src/pcf/pcf.c',
 'pfr.c.o': 'research/freetype/src/pfr/pfr.c',
 'psaux.c.o': 'research/freetype/src/psaux/psaux.c',
 'pshinter.c.o': 'research/freetype/src/pshinter/pshinter.c',
 'psnames.c.o': 'research/freetype/src/psnames/psnames.c',
 'raster.c.o': 'research/freetype/src/raster/raster.c',
 'sdf.c.o': 'research/freetype/src/sdf/sdf.c',
 'sfnt.c.o': 'research/freetype/src/sfnt/sfnt.c',
 'smooth.c.o': 'research/freetype/src/smooth/smooth.c',
 'svg.c.o': 'research/freetype/src/svg/svg.c',
 'truetype.c.o': 'research/freetype/src/truetype/truetype.c',
 'type1.c.o': 'research/freetype/src/type1/type1.c',
 'type1cid.c.o': 'research/freetype/src/cid/type1cid.c',
 'type42.c.o': 'research/freetype/src/type42/type42.c',
 'winfnt.c.o': 'research/freetype/src/winfonts/winfnt.c'}
FT_NOTICES = ('LICENSE.TXT',
 'docs/FTL.TXT',
 'docs/GPLv2.TXT',
 'src/bdf/README',
 'src/pcf/README',
 'src/base/fthash.c',
 'include/freetype/internal/fthash.h',
 'src/gzip/zlib.h',
 'src/autofit/ft-hb.c',
 'src/autofit/ft-hb.h')
WIN32U_MEMBERS = frozenset(WIN32U_SOURCES)
EXPECTED_MEMBERS = WIN32U_MEMBERS | FT_MEMBERS
FT_SYMBOLS = frozenset(("_FT_Init_FreeType", "_FT_Load_Glyph"))
WIN32U_SYMBOLS = frozenset(("_win32u_unix_lib_init", "_win32u_zero_bits"))
REQUIRED_SYMBOLS = FT_SYMBOLS | WIN32U_SYMBOLS
EVIDENCE_FILES = (
    "preflight.txt", "toolchain.txt", "source-manifest.json", "freetype-source-manifest.json", "CMakeCache.txt", "compile_commands.json",
    "libfreetype.a.members.txt", "libfreetype.a.arch.txt", "libfreetype.a.load-commands.txt", "libfreetype.a.symbols.txt",
    "libwin32u-core.a.members.txt", "libwin32u-core.a.arch.txt", "libwin32u-core.a.load-commands.txt", "libwin32u-core.a.symbols.txt",
    "libwin32u_unix.a.members.txt", "libwin32u_unix.a.arch.txt", "libwin32u_unix.a.load-commands.txt", "libwin32u_unix.a.symbols.txt",
    "libfreetype.a.sha256.txt", "libwin32u-core.a.sha256.txt", "libwin32u_unix.a.sha256.txt",
)
LIMITATIONS = (
    "Source-only FreeType and Wine win32u static archive control for arm64 iOS 17.0. "
    "Generated Wine headers/configuration come only from the verified locked producer artifact. "
    "Unresolved Winios/ntdll/system references remain expected; archive creation is not a link test. "
    "No runtime link, runtime feature patch, added stubs, FEX, DXMT, converter, Steam, IPA, signing or device test."
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
            if ".." in relative.parts:
                raise ValueError("Parent traversal in artifact path")
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
    if not name or not path.parts or path.as_posix() != name or path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name or any(ord(c) < 32 for c in name):
        raise ValueError("Unsafe ZIP member name")
    return name


def add_file(archive, path, name, cap, root=None):
    archive.write(checked_file(path, cap, root), safe_name(name))


def validate_members(members, expected=EXPECTED_MEMBERS):
    lines = [line.strip() for line in members.splitlines() if line.strip()]
    if sum(name in BSD_INDEX_MEMBERS for name in lines) > 1:
        raise ValueError("Duplicate archive index metadata")
    names = [name for name in lines if name not in BSD_INDEX_MEMBERS]
    if len(names) != len(expected) or len(set(names)) != len(names) or set(names) != set(expected):
        raise ValueError("Archive members must match the exact pinned object set, once each")
    return names


def validate_platform(arch, members, commands, expected=EXPECTED_MEMBERS):
    if arch.strip() != "arm64" and not re.fullmatch(r"(?:Non-fat file: [^\n]+ is architecture:|Architectures in the fat file: [^\n]+ are:)\s+arm64", arch.strip()):
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
    if magic != 0xFEEDFACF or cpu != 0x0100000C or subtype != 0 or kind != 1 or reserved != 0:
        raise ValueError(f"Member must be a thin arm64 Mach-O object: {name}")
    if ncmds > 4096 or size > len(data) - 32:
        raise ValueError("Invalid Mach-O load-command bounds")
    offset, platforms, minima = 32, [], []
    for unused in range(ncmds):
        if offset + 8 > 32 + size:
            raise ValueError("Truncated Mach-O command")
        command, length = struct.unpack_from("<2I", data, offset)
        if length < 8 or length % 8 or offset + length > 32 + size:
            raise ValueError("Invalid Mach-O command size")
        if command == 0x32:  # LC_BUILD_VERSION
            if length < 24:
                raise ValueError("Truncated build-version command")
            ntools = struct.unpack_from("<I", data, offset + 20)[0]
            if length != 24 + 8 * ntools:
                raise ValueError("Invalid build-version tool count")
            platforms.append(struct.unpack_from("<I", data, offset + 8)[0])
            minima.append(struct.unpack_from("<I", data, offset + 12)[0])
        elif command in (0x24, 0x25, 0x2F, 0x30):
            if length != 16:
                raise ValueError("Invalid legacy platform command size")
            platforms.append(2 if command == 0x25 else -1)
            minima.append(struct.unpack_from("<I", data, offset + 8)[0])
        offset += length
    if offset != 32 + size or platforms != [2] or minima != [0x00110000]:
        raise ValueError(f"Member must contain exactly one iOS 17.0 platform command: {name}")


def validate_archive(path, expected=EXPECTED_MEMBERS):
    """Check actual bytes; never infer every object's CPU/platform from lipo alone."""
    checked_file(path, 256 * MIB)
    names, inventory, indexes = [], [], []
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
                if not re.fullmatch(r"#1/[0-9]+", raw_name):
                    raise ValueError("Malformed BSD ar name length")
                name_length = int(raw_name[3:])
                if name_length <= 0 or name_length > min(length, 4096):
                    raise ValueError("Invalid BSD ar name length")
                try:
                    name = data[:name_length].rstrip(b"\0").decode("ascii")
                except UnicodeError as error:
                    raise ValueError("Non-ASCII archive member name") from error
                if "\0" in name:
                    raise ValueError("Embedded NUL archive member name")
                data = data[name_length:]
            else:
                name = raw_name.rstrip("/")
            if name in BSD_INDEX_MEMBERS:
                indexes.append(name)
                if len(indexes) > 1:
                    raise ValueError("Duplicate archive index metadata")
                continue
            if name not in expected or name in names:
                raise ValueError("Unknown or duplicate real archive member")
            validate_macho(data, name)
            names.append(name)
            inventory.append({"member": name, "sha256": hashlib.sha256(data).hexdigest(),
                              "size": len(data), "architecture": "arm64", "platform": "iOS"})
    validate_members("\n".join(names), expected)
    return inventory


def validate_symbols(symbols, required=REQUIRED_SYMBOLS):
    defined, undefined = set(), set()
    for line in symbols.splitlines():
        match = re.fullmatch(r"\s*(?:[0-9a-fA-F]+\s+)?([A-Za-z?])\s+(\S+)\s*", line)
        if not match:
            continue
        kind, name = match.groups()
        if kind in ("U", "u"):
            undefined.add(name)
        elif kind in "ABCDGIRSTVW":
            defined.add(name)
    if not required <= defined:
        raise ValueError("Required symbols must be global definitions: " + ", ".join(sorted(required - defined)))
    return {"required_global_definitions": sorted(required), "undefined_references": sorted(undefined),
            "undefined_references_are_not_a_link_failure": True, "runtime_linked": False}


class Control:
    def __init__(self):
        self.deadline = time.monotonic() + AGGREGATE_SECONDS
        self.steps = []

    def ensure_budget(self):
        if time.monotonic() >= self.deadline:
            raise RuntimeError("Aggregate 23-minute source control budget exhausted")

    def run(self, label, *args, cwd=ROOT, seconds=None):
        if not re.fullmatch(r"[a-z0-9-]+", label) or any(s["label"] == label for s in self.steps):
            raise ValueError("Unsafe or reused step label")
        if seconds is not None and seconds <= 0:
            raise ValueError("Nonpositive step budget")
        self.ensure_budget()
        timeout = min(self.deadline - time.monotonic(), seconds or AGGREGATE_SECONDS)
        log, started = OUT / (label + ".log"), time.monotonic()
        env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_CONFIG_NOSYSTEM="1",
                   GIT_CONFIG_GLOBAL=os.devnull, JOBS="4", LC_ALL="C", PYTHONOPTIMIZE="0", PYTHONNOUSERSITE="1")
        step = {"label": label, "exit_code": None}
        self.steps.append(step)
        with log.open("xb") as stream:
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
                        if log.stat().st_size > 64 * MIB or time.monotonic() - started >= timeout:
                            try:
                                os.killpg(proc.pid, signal.SIGKILL)
                            except ProcessLookupError:
                                pass
                            code = 124
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
        step.update(exit_code=code, elapsed_seconds=round(time.monotonic() - started, 3))
        print(f"[{label}] exit={code}", flush=True)
        if code:
            # Only explicitly started command output, never a whole environment dump.
            with log.open("rb") as stream:
                stream.seek(max(0, log.stat().st_size - 24000))
                print(stream.read().decode("utf-8", errors="replace"), flush=True)
            raise RuntimeError(f"{label} failed with exit {code}")
        return log.read_text(errors="replace") if log.stat().st_size < MIB else ""


def require_fresh(paths, root=ROOT):
    root = Path(root).absolute()
    if root.is_symlink():
        raise ValueError("Symlink work root")
    for path in paths:
        path = Path(path).absolute()
        try:
            parts = path.relative_to(root).parts
            if not parts or ".." in parts:
                raise ValueError("Invalid work directory path")
        except ValueError as error:
            raise ValueError("Work directory outside root") from error
        current = root
        for part in parts:
            current /= part
            if current.is_symlink():
                raise ValueError("Symlink work directory refused")
        if path.exists():
            raise ValueError("Fresh source and evidence directories required")


def source_bounds(root):
    total = count = 0
    for current, dirs, files in os.walk(root, followlinks=False):
        if any((Path(current) / d).is_symlink() for d in dirs):
            raise ValueError("Symlink source directory")
        for name in files:
            path = Path(current) / name
            if path.is_symlink():
                continue
            if not path.is_file():
                raise ValueError("Non-regular source file")
            total += path.stat().st_size
            count += 1
            if total > 4 * 1024 * MIB or count > 200000:
                raise ValueError("Source checkout exceeds 4 GiB/200000-file control bound")
    return {"files": count, "bytes": total}


def verify_pin(actual, expected):
    if not re.fullmatch(r"[0-9a-f]{40}", expected) or actual.strip() != expected:
        raise ValueError("Checkout does not match exact pinned source commit")
    return expected


def checkout(control, tag, path, url, commit, sparse=()):
    if path != SOURCE:
        require_fresh((path,), SOURCE)
        path.mkdir(parents=True)
    control.run(tag + "-init", "git", "init", "--quiet", cwd=path)
    control.run(tag + "-remote", "git", "remote", "add", "origin", url, cwd=path)
    control.run(tag + "-fetch", "git", "fetch", "--depth=1", "--filter=blob:none", "origin", commit, cwd=path, seconds=300)
    if sparse:
        control.run(tag + "-sparse-init", "git", "sparse-checkout", "init", "--no-cone", cwd=path)
        control.run(tag + "-sparse-paths", "git", "sparse-checkout", "set", "--no-cone", "--", *sparse, cwd=path)
    control.run(tag + "-checkout", "git", "checkout", "--detach", "FETCH_HEAD", cwd=path, seconds=180)
    verify_pin(control.run(tag + "-pin", "git", "rev-parse", "HEAD", cwd=path), commit)
    return source_bounds(path)


def collect_licenses(source=SOURCE):
    selected = []
    for tag, repo in (("Madeira", source), ("Wine", source / "wine")):
        candidates = [p for p in repo.iterdir() if re.fullmatch(r"(?:LICENSE|COPYING|NOTICE)(?:[._-].*)?", p.name, re.I)]
        if tag == "Madeira":
            candidates += [repo / name for name in ("THIRD-PARTY-NOTICES.md", "docs/LICENSING.md", "docs/wine-lgpl-provenance.md")]
        if (repo / "LICENSES").is_dir():
            candidates += list((repo / "LICENSES").rglob("*"))
        for path in sorted(set(candidates)):
            if path.is_dir() and not path.is_symlink():
                continue
            checked_file(path, 4 * MIB, repo)
            selected.append((path, "Licenses/" + tag + "/" + path.relative_to(repo).as_posix()))
    for name in FT_NOTICES:
        path = checked_file(source / "research/freetype" / name, 4 * MIB, source)
        selected.append((path, "Licenses/FreeType/" + name))
    for name in ("COPYING", "LICENSE", "LICENSE-EXCEPTION.md", "THIRD-PARTY-NOTICES.md",
                 "docs/LICENSING.md", "docs/wine-lgpl-provenance.md",
                 "wine/COPYING.LIB", "wine/LICENSE", "wine/LICENSE-MADEIRA.md", "wine/LICENSE.OLD"):
        checked_file(source / name, 4 * MIB, source)
    validate_license_bounds([(name, p.stat().st_size) for p, name in selected])
    return selected


def validate_license_bounds(entries):
    if len(entries) > 128 or len({name for name, size in entries}) != len(entries):
        raise ValueError("License count or duplicate-name bound exceeded")
    if any(size < 0 or size > 4 * MIB for name, size in entries) or sum(size for name, size in entries) > 16 * MIB:
        raise ValueError("License size bounds exceeded")
    for name, size in entries:
        safe_name(name)


def producer_notices(import_report):
    result = []
    for notice in import_report["licenses"]:
        name = safe_name("Producer/" + notice["path"])
        data = base64.b64decode(notice["content_base64"], validate=True)
        if len(data) != notice["size"] or hashlib.sha256(data).hexdigest() != notice["sha256"]:
            raise ValueError("Imported notice payload mismatch")
        result.append((name, data))
    validate_license_bounds([(name, len(data)) for name, data in result])
    return result


def validate_source_manifest(manifest, source=SOURCE):
    for key, expected in (("madeira_commit", MADEIRA), ("wine_commit", WINE), ("freetype_commit", FREETYPE)):
        verify_pin(manifest.get(key, ""), expected)
    if manifest.get("archive_only") is not True or manifest.get("runtime_linked") is not False:
        raise ValueError("Source manifest must be archive-only")
    validate_members("\n".join(manifest.get("win32u_members", [])), WIN32U_MEMBERS)
    validate_members("\n".join(manifest.get("freetype_members", [])), FT_MEMBERS)
    entries = manifest.get("source_files", [])
    paths = [entry.get("path") for entry in entries]
    required = set(WIN32U_SOURCES.values()) | set(FT_SOURCES.values()) | {
        "wine/dlls/win32u/d3dkmt.c", "wine/dlls/win32u/syscall.c", "wine/dlls/win32u/freetype.c"}
    if not required <= set(paths) or len(set(paths)) != len(paths) or len(paths) > 5000:
        raise ValueError("Missing or duplicate source manifest paths")
    for entry in entries:
        path = checked_file(source / safe_name(entry["path"]), 16 * MIB, source)
        if not re.fullmatch(r"[0-9a-f]{64}", entry.get("sha256", "")) or digest(path) != entry["sha256"]:
            raise ValueError("Source manifest content hash mismatch")
    return manifest


def freetype_headers(root):
    files, total = [], 0
    for current, dirs, names in os.walk(root, followlinks=False):
        if any((Path(current) / name).is_symlink() for name in dirs):
            raise ValueError("FreeType header directory symlink")
        for name in names:
            path = Path(current) / name
            if path.suffix != ".h":
                continue
            checked_file(path, 4 * MIB, root)
            total += path.stat().st_size
            files.append(path)
    if not files or len(files) > 1000 or total > 32 * MIB:
        raise ValueError("FreeType header bounds exceeded")
    return sorted(files)


def verify_imported_headers(imported, root):
    expected = {entry["path"]: entry for entry in imported["headers"]}
    actual = set()
    for current, dirs, files in os.walk(root, followlinks=False):
        if any((Path(current) / d).is_symlink() for d in dirs):
            raise ValueError("Imported header directory changed to symlink")
        for name in files:
            path = Path(current) / name
            relative = path.relative_to(root).as_posix()
            if relative not in expected:
                raise ValueError("Unexpected imported header file")
            checked_file(path, 16 * MIB, root)
            entry = expected[relative]
            if path.stat().st_size != entry["size"] or digest(path) != entry["sha256"]:
                raise ValueError("Imported header was modified after verification")
            actual.add(relative)
    if actual != set(expected):
        raise ValueError("Imported header disappeared after verification")


def validate_product(path, prefix, members, required):
    inventory = validate_archive(checked_file(path, 256 * MIB, SOURCE), members)
    def evidence(suffix):
        return checked_file(EVIDENCE / (prefix + suffix), 32 * MIB, SOURCE).read_text()
    validate_platform(evidence(".arch.txt"), evidence(".members.txt"), evidence(".load-commands.txt"), members)
    symbols = validate_symbols(evidence(".symbols.txt"), required)
    recorded = evidence(".sha256.txt").split()
    if len(recorded) < 2 or recorded[0] != digest(path):
        raise ValueError("Archive content differs from recorded helper hash")
    return dict(result="passed", sha256=digest(path), size=path.stat().st_size, members=inventory, **symbols)


def validate_products(report):
    results = {
        "freetype_archive": validate_product(FT_ARCHIVE, "libfreetype.a", FT_MEMBERS, FT_SYMBOLS),
        "win32u_core": validate_product(RAW_ARCHIVE, "libwin32u-core.a", WIN32U_MEMBERS, WIN32U_SYMBOLS),
        "win32u_merged": validate_product(ARCHIVE, "libwin32u_unix.a", EXPECTED_MEMBERS, REQUIRED_SYMBOLS),
    }
    inputs = {m["member"]: m["sha256"] for tag in ("freetype_archive", "win32u_core") for m in results[tag]["members"]}
    merged = {m["member"]: m["sha256"] for m in results["win32u_merged"]["members"]}
    if inputs != merged:
        raise ValueError("Merged archive objects differ from validated input archive bytes")
    validate_source_manifest(json.loads(checked_file(EVIDENCE / "source-manifest.json", 4 * MIB, SOURCE).read_text()))
    report.update(results)


def freetype_source_manifest():
    names = sorted(set(FT_SOURCES.values()) | {"research/freetype/CMakeLists.txt", "build/freetype-ios/build.sh"})
    files = []
    for name in names:
        path = checked_file(SOURCE / name, 16 * MIB, SOURCE)
        files.append({"path": name, "sha256": digest(path), "size": path.stat().st_size})
    manifest = {"madeira_commit": MADEIRA, "freetype_commit": FREETYPE, "source_files": files,
                "expected_members": sorted(FT_MEMBERS), "archive_only": True, "runtime_linked": False,
                "win32u_built": False, "device_tested": False,
                "feature_scope": "External optional libraries disabled; bundled internal zlib remains active."}
    path = EVIDENCE / "freetype-source-manifest.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    return path


def write_product(report, licenses, notices, *, freetype_only=False):
    validate_license_bounds([(name, p.stat().st_size) for p, name in licenses] + [(name, len(data)) for name, data in notices])
    if freetype_only:
        output, path, manifest_path = "freetype-ios-archive.zip", FT_ARCHIVE, freetype_source_manifest()
        result = "passed-freetype-source-control-only"
    else:
        output, path, manifest_path = "win32u-ios-archive.zip", ARCHIVE, EVIDENCE / "source-manifest.json"
        result = "passed-source-control-only"
    temporary = OUT / (output + ".part")
    with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
        add_file(archive, path, "Archives/" + path.name, 256 * MIB, SOURCE)
        header_inventory = []
        if freetype_only:
            roots = (("Headers/source/", SOURCE / "research/freetype/include"),
                     ("Headers/generated/", SOURCE / "build/freetype-ios/build/include"))
            for prefix, root in roots:
                for header in freetype_headers(root):
                    name = prefix + header.relative_to(root).as_posix()
                    add_file(archive, header, name, 4 * MIB, root)
                    header_inventory.append({"path": name, "sha256": digest(header), "size": header.stat().st_size})
        for file, name in licenses:
            add_file(archive, file, name, 4 * MIB, SOURCE)
        for name, data in notices:
            archive.writestr(name, data)
        archive.writestr("NOTICE.txt", "This software is based in part on the work of the FreeType Team.\n" + LIMITATIONS + "\n")
        add_file(archive, manifest_path, "source-manifest.json", 4 * MIB, SOURCE)
        artifact_report = dict(report, result=result, packaged_headers=header_inventory,
                               win32u_built=not freetype_only, runtime_linked=False)
        archive.writestr("source-and-archive-manifest.json", json.dumps(artifact_report, indent=2))
        sums = digest(path) + "  Archives/" + path.name + "\n"
        sums += "".join(entry["sha256"] + "  " + entry["path"] + "\n" for entry in header_inventory)
        archive.writestr("SHA256SUMS", sums)
    temporary.replace(OUT / output)
    return OUT / output


def remove_failed_outputs():
    # Independently validated FreeType is a reusable result even if win32u fails.
    for name in ("win32u-ios-archive.zip", "win32u-ios-archive.zip.part", "freetype-ios-archive.zip.part"):
        (OUT / name).unlink(missing_ok=True)


def diagnostic_evidence_candidates(source=SOURCE):
    # Upstream redirects each compiler's stderr into its exact per-object file.
    # Derive only the reviewed 46 names; never sweep an output directory.
    result = [(source / "build/win32u-unix/obj" / (name[:-2] + ".err"),
               "CompilerErrors/" + name[:-2] + ".err") for name in sorted(WIN32U_MEMBERS)]
    result.append((source / "build/freetype-ios/build/CMakeFiles/CMakeConfigureLog.yaml",
                   "Configuration/FreeType-CMakeConfigureLog.yaml"))
    return result


def write_evidence(report, control, helper):
    (OUT / "result.json").write_text(json.dumps(report, indent=2) + "\n")
    total, omissions = 0, []
    with zipfile.ZipFile(OUT / "win32u-evidence.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        add_file(archive, OUT / "result.json", "result.json", 8 * MIB, OUT)
        candidates = [(OUT / (s["label"] + ".log"), "Logs/" + s["label"] + ".log") for s in control.steps]
        candidates += [(EVIDENCE / name, "Evidence/" + name) for name in EVIDENCE_FILES]
        candidates += diagnostic_evidence_candidates(SOURCE)
        candidates += [(helper, "Source/win32u-core-control.sh"), (Path(__file__), "Source/run_win32u_control.py"),
                       (ROOT / "ci/import_wine_headers.py", "Source/import_wine_headers.py"),
                       (ROOT / "ci/source-lock.json", "Source/source-lock.json"),
                       (ROOT / "ci/header-artifact-lock.json", "Source/header-artifact-lock.json"),
                       (OUT / "header-import.json", "Evidence/header-import.json")]
        for path, name in candidates:
            if not path.exists() and not path.is_symlink():
                continue
            try:
                checked_file(path, 64 * MIB, ROOT)
                size = min(path.stat().st_size, 8 * MIB)
                if total + size > 96 * MIB:
                    raise ValueError("96 MiB total evidence cap")
                with path.open("rb") as stream:
                    if path.stat().st_size > size:
                        stream.seek(path.stat().st_size - size)
                        name += ".tail"
                    archive.writestr(safe_name(name), stream.read(size))
                total += size
            except ValueError as error:
                omissions.append({"path": name, "reason": str(error)})
        archive.writestr("evidence-omissions.json", json.dumps(omissions, indent=2))
    print("WIN32U_CONTROL_RESULT=" + json.dumps(report, sort_keys=True), flush=True)


def reviewed_file(path, pin, variable):
    checked_file(path, 4 * MIB, ROOT)
    if not re.fullmatch(r"[0-9a-f]{64}", pin) or os.environ.get(variable) != pin or digest(path) != pin:
        raise ValueError("Unpinned or changed reviewed input: " + path.name)
    return path


def checked_build_environment():
    # Refuse header/toolchain injection without ever logging environment values.
    denied = ("CPATH", "C_INCLUDE_PATH", "CPLUS_INCLUDE_PATH", "OBJC_INCLUDE_PATH",
              "CMAKE_TOOLCHAIN_FILE", "CMAKE_PREFIX_PATH", "CMAKE_INCLUDE_PATH", "CMAKE_LIBRARY_PATH")
    found = [name for name in denied if os.environ.get(name)]
    if found:
        raise ValueError("Inherited compiler/CMake injection variable(s): " + ", ".join(found))


def main():
    if sys.platform != "darwin":
        raise SystemExit("Approved macOS runner required")
    if os.environ.get("FREE_QUOTA_VERIFIED") != "true" or os.environ.get("PRIVATE_SOURCE_VERIFIED") != "true":
        raise SystemExit("Manual free/private checks must be exactly true")
    checked_build_environment()
    control = Control()
    helper = reviewed_file(ROOT / "ci/win32u-core-control.sh", RECIPE, "EXPECTED_RECIPE_SHA256")
    importer = reviewed_file(ROOT / "ci/import_wine_headers.py", IMPORTER, "EXPECTED_IMPORTER_SHA256")
    reviewed_file(ROOT / "ci/source-lock.json", SOURCE_LOCK, "EXPECTED_SOURCE_LOCK_SHA256")
    lock = reviewed_file(ROOT / "ci/header-artifact-lock.json", HEADER_LOCK, "EXPECTED_HEADER_LOCK_SHA256")
    if FREETYPE_URL not in ("https://gitlab.freedesktop.org/freetype/freetype.git", "https://github.com/freetype/freetype.git"):
        raise ValueError("FreeType canonical or recipe mirror URL remains unreviewed")
    if len(FT_MEMBERS) != 42 or len(WIN32U_MEMBERS) != 46 or len(EXPECTED_MEMBERS) != 88:
        raise ValueError("Expected reviewed archive member closure is incomplete")
    spec = importlib.util.spec_from_file_location("verified_wine_header_importer", importer)
    header_importer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(header_importer)
    header_importer.load_lock(lock, expected_lock_sha256=HEADER_LOCK)
    input_archive = checked_file(ROOT / "ci/inputs/wine-headers.zip", 160 * MIB, ROOT)
    require_fresh((SOURCE, OUT))
    OUT.mkdir(parents=True)
    SOURCE.mkdir(parents=True)
    report = {"result": "failed", "scope": LIMITATIONS, "madeira": MADEIRA, "wine": WINE, "freetype": FREETYPE,
              "recipe_sha256": RECIPE, "importer_sha256": IMPORTER, "header_lock_sha256": HEADER_LOCK,
              "source_lock_sha256": SOURCE_LOCK, "wrapper_sha256": digest(Path(__file__)), "freetype_source_url": FREETYPE_URL,
              "freetype_source_origin": "exact pinned Madeira recipe upstream GitHub mirror; canonical GitLab equality unverified; no fallback",
              "jobs": 4, "aggregate_budget_seconds": AGGREGATE_SECONDS, "provider_budget_minutes": 25,
              "tool_installation": False, "runtime_linked": False, "ipa_created": False, "device_tested": False,
              "source_only": True, "steps": control.steps}
    try:
        report["madeira_checkout"] = checkout(control, "madeira", SOURCE, "https://github.com/willfaust/Madeira.git", MADEIRA, SPARSE_PATHS)
        # Check existing tools before large dependency checkouts; never install.
        control.run("preflight", "bash", str(helper), str(SOURCE), "preflight", seconds=90)
        report["wine_checkout"] = checkout(control, "wine", SOURCE / "wine", "https://github.com/willfaust/wine.git", WINE, WINE_SPARSE_PATHS)
        report["freetype_checkout"] = checkout(control, "freetype", SOURCE / "research/freetype", FREETYPE_URL, FREETYPE)
        control.ensure_budget()
        (SOURCE / "wine/build-macos").mkdir()
        imported = header_importer.import_headers(input_archive, lock, SOURCE / "wine/build-macos/include", expected_lock_sha256=HEADER_LOCK)
        notices = producer_notices(imported)
        imported = dict(imported, licenses=[{k: v for k, v in n.items() if k != "content_base64"} for n in imported["licenses"]])
        report["header_import"] = imported
        (OUT / "header-import.json").write_text(json.dumps(imported, indent=2) + "\n")
        licenses = collect_licenses()
        report["licenses"] = [{"path": name, "sha256": digest(path), "size": path.stat().st_size} for path, name in licenses]
        control.run("freetype-build", "bash", str(helper), str(SOURCE), "freetype")
        verify_pin(control.run("freetype-built-pin", "git", "rev-parse", "HEAD", cwd=SOURCE / "research/freetype"), FREETYPE)
        control.run("freetype-built-diff", "git", "diff", "--exit-code", "HEAD", "--", ".", cwd=SOURCE / "research/freetype")
        control.ensure_budget()
        report["freetype_archive"] = validate_product(FT_ARCHIVE, "libfreetype.a", FT_MEMBERS, FT_SYMBOLS)
        report["win32u_merged"] = {"result": "not-run"}
        write_product(report, licenses, notices, freetype_only=True)
        control.ensure_budget()
        report["win32u_merged"]["result"] = "running"
        control.run("win32u-build", "bash", str(helper), str(SOURCE), "win32u")
        for tag, path, pin in (("madeira", SOURCE, MADEIRA), ("wine", SOURCE / "wine", WINE), ("freetype", SOURCE / "research/freetype", FREETYPE)):
            verify_pin(control.run(tag + "-final-pin", "git", "rev-parse", "HEAD", cwd=path), pin)
            control.run(tag + "-final-diff", "git", "diff", "--exit-code", "HEAD", "--", ".", cwd=path)
        control.ensure_budget()
        verify_imported_headers(imported, SOURCE / "wine/build-macos/include")
        validate_products(report)
        write_product(report, licenses, notices)
        control.ensure_budget()
        report["result"] = "passed-source-control-only"
    except Exception as error:
        report["failure"] = str(error)
        remove_failed_outputs()
        if report.get("win32u_merged", {}).get("result") in ("running", "passed"):
            report["win32u_merged"]["result"] = "failed"
        print(str(error), file=sys.stderr, flush=True)
    finally:
        for name in ("freetype-ios-archive.zip.part", "win32u-ios-archive.zip.part"):
            (OUT / name).unlink(missing_ok=True)
        write_evidence(report, control, helper)
    return 0 if report["result"] == "passed-source-control-only" else 1


if __name__ == "__main__":
    raise SystemExit(main())
