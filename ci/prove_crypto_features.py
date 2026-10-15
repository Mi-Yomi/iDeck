#!/usr/bin/env python3
"""Future Mac-only, nonexecuting iOS GnuTLS API proof. Never launches target code.

CLI: prove_crypto_features.py PREFIX PROOF_OUTPUT
The caller owns the process-group/aggregate timeout. This helper installs nothing,
uses no network, changes no source/config, and signs nothing. Host tests exercise
parsers with labelled synthetic fixtures, never certify a target proof.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import struct
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
LOCK_SHA256 = "cc8924fdaef69921bbe27a2cfc7323ed22fbd2f1ca969a48dcc0b55aeb75bae4"
PROBE_SHA256 = "cbfff4cd0888a2849282f38253b4839afc4a9064dfc042932c0896ad59314e09"
CONFIG_SHA256 = "22332cb47937d006792e911322c2978a953d25fb5c883837c952b05e7e4077e4"
ARCHIVES = ("libgnutls.a", "libhogweed.a", "libnettle.a", "libgmp.a")
IOS_VERSION = 0x00110000
SDK_VERSION = 0x001A0500
HEADERS = frozenset("x509.h pkcs12.h compat.h openpgp.h crypto.h pkcs11.h abstract.h dtls.h ocsp.h tpm.h x509-ext.h self-test.h system-keys.h urls.h pkcs7.h socket.h gnutls.h".split())
# Exact headers from pinned GnuTLS3.8.9 source tarball. gnutls.h is the
# unchanged template with configure's real iovec-present/version substitutions;
# this expected byte identity does not preseed any configure result.
PUBLIC_HEADER_SHA256 = {'abstract.h': '3854e085de5fe83991173648c3d114f238d05483a4b4d38c688a1bd7fb9828c0', 'compat.h': '74514d5dcfdd40598d5c2c63c1d4afa1bfcc7acac745c0fdb493886ff709c0b1', 'crypto.h': '7ff7c90b487905003c06353dcd41953a52c1dd8d7e85b9178785ed13ce422308', 'dtls.h': 'e2ce062cf599dc13d9be1907d2908294065fd75bcf819dae5ad8456da9f98758', 'gnutls.h': '41e3f1692d8d989e4daa727aee6efc33b297a30abf521b0147d46b615abba247', 'ocsp.h': '8adaadbfd8f8482978c12ffdeda2c14220a7386e700a7ed055cd963f9e75c0c8', 'openpgp.h': '2e700674ddba6081c649de8e6c7c4a4cacd45f4afef05d8a4d0209f6b0f78de8', 'pkcs11.h': 'd54259907abc1920b74c42fafb210c3eb0d72bbddbdc34b0c2eeb007dbfa2a65', 'pkcs12.h': '726d1dadab84994043bc50c792f1764a306866885952ab070a815c45e8ded0e1', 'pkcs7.h': '9cb5c52b9fa16436e07159a18666c0f0334c705ee0f9606993e77501a165b667', 'self-test.h': '52edb58a874ebb7c78f06a4fe9a358b76050604584fc459c76780102889a42b0', 'socket.h': 'a511b4dbbb7d415c7a87c2740dd16098acc0bb0c2ab2c7200a0a6a3a92cb9a25', 'system-keys.h': 'd958661473709961933ceb52a1ef10921f04c809cc3151a18ecf4a5e76c9f310', 'tpm.h': 'c2994177ad7cc5b45d5ff6f7972e7751fe58425e37737dbafbf248e8c744bc23', 'urls.h': '5d23fc23e7582cf32872c575f25dd9579d889261dd910f939277579e648c0a24', 'x509-ext.h': '5ffeae33b6cbd6da539a470787505cc37babb82477f1d55cd31926e0a6252d3c', 'x509.h': '472bd24f5d03715bc6d52852112bcafdcee06ed1c0ffc72aa2f0da292b9dfb5a'}
SYSTEM_DYLIBS = frozenset(("/usr/lib/libSystem.B.dylib", "/System/Library/Frameworks/Security.framework/Security", "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation"))
INDEX_NAMES = frozenset(("__.SYMDEF", "__.SYMDEF SORTED", "__.SYMDEF_64", "__.SYMDEF_64 SORTED"))
MIB = 1024 * 1024

class ProofError(Exception):
    pass

def require(condition, message):
    if not condition:
        raise ProofError(str(message))

def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for data in iter(lambda: stream.read(MIB), b""):
            h.update(data)
    return h.hexdigest()

def atomic_json(path, data):
    path = Path(path)
    temporary = path.with_name(path.name + ".pending")
    require(not temporary.exists() and not temporary.is_symlink(), "Unexpected pending result file")
    temporary.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)

def canonical(path, exists=True, directory=False):
    p = Path(path).absolute()
    require(".." not in p.parts, "Parent traversal forbidden")
    require(not any(ord(c) < 32 or ord(c) == 127 for c in str(p)), "Control character in path")
    for q in (p, *p.parents):
        require(not q.is_symlink(), f"Symlink input/output path: {q}")
    require(p.resolve(strict=False) == p, "Canonical path required")
    if exists:
        require(p.is_dir() if directory else p.is_file(), f"Missing regular {'directory' if directory else 'file'}: {p}")
    return p

def checked_file(path, bound=64 * MIB, allow_empty=False):
    p = canonical(path)
    require((0 if allow_empty else 1) <= p.stat().st_size <= bound, f"Empty/oversized file: {p}")
    return p

def load_contract():
    lockpath = checked_file(PACKAGE / "gnutls-symbol-lock.json", MIB)
    source = checked_file(PACKAGE / "gnutls-api-link-probe.c", MIB)
    require(sha256(lockpath) == LOCK_SHA256 and sha256(source) == PROBE_SHA256, "Reviewed lock/probe source hash drift")
    lock = json.loads(lockpath.read_text())
    symbols = [x["symbol"] for x in lock["symbols"]]
    require(len(symbols) == 106 and len(set(symbols)) == 106, "Exactly106 distinct symbols required")
    require(all(re.fullmatch(r"gnutls_[a-z0-9_]+", s) for s in symbols), "Invalid symbol in lock")
    require(sum(x["wine_requirement"] == "required" for x in lock["symbols"]) == 69, "Required/optional labels drift")
    require(sum(x["wine_requirement"] == "optional_with_existing_fallback" for x in lock["symbols"]) == 37, "Required/optional labels drift")
    return lock, frozenset(symbols), source

def inspect_headers(prefix):
    directory = canonical(prefix / "include/gnutls", directory=True)
    entries = list(directory.iterdir())
    require({p.name for p in entries} == HEADERS, "Expected exact17 GnuTLS public headers")
    record = []
    for path in sorted(entries):
        checked_file(path, 4 * MIB)
        text = path.read_text()
        require(sha256(path) == PUBLIC_HEADER_SHA256[path.name], f"Pinned GnuTLS public header identity drift: {path.name}")
        require(not re.search(r"@[A-Z][A-Z0-9_]*@", text), f"Unexpanded generated header token: {path.name}")
        record.append({"path": str(path.relative_to(prefix)), "sha256": sha256(path), "size": path.stat().st_size})
    s = (directory / "gnutls.h").read_text()
    for macro, value in {"GNUTLS_VERSION": '"3.8.9"', "GNUTLS_VERSION_MAJOR": "3", "GNUTLS_VERSION_MINOR": "8", "GNUTLS_VERSION_PATCH": "9", "GNUTLS_VERSION_NUMBER": "0x030809"}.items():
        values = re.findall(r"^\s*#\s*define\s+" + macro + r"\s+(\S+)\s*$", s, re.M)
        require(values == [value], f"Generated GnuTLS3.8.9 macro mismatch: {macro}")
    return record

def validate_link_tokens(value, prefix):
    """Parse data only, never execute/evaluate/forward metadata to a command."""
    require(not any(c in value for c in ("`", "\n", "\r", "\0", ";", "|", "&", "<", ">")), "Unsafe library metadata")
    for variable, replacement in (("${libdir}", str(prefix / "lib")), ("${exec_prefix}", str(prefix)), ("${prefix}", str(prefix))):
        value = value.replace(variable, replacement)
    require("$" not in value, "Unknown/interpolated library variable")
    try:
        tokens = shlex.split(value, posix=True)
    except ValueError as error:
        raise ProofError("Malformed library metadata") from error
    allowed = {"-lgnutls", "-lhogweed", "-lnettle", "-lgmp", "-lpthread", "-L" + str(prefix / "lib")}
    allowed.update(str(prefix / "lib" / name.replace(".a", ".la")) for name in ARCHIVES)
    allowed.update(str(prefix / "lib" / name) for name in ARCHIVES)
    i = 0
    while i < len(tokens):
        if tokens[i] == "-framework":
            require(i + 1 < len(tokens) and tokens[i + 1] in ("Security", "CoreFoundation"), "Unapproved SDK framework")
            i += 2
        else:
            require(tokens[i] in allowed, f"Unapproved static link dependency: {tokens[i]}")
            i += 1
    return tokens

def inspect_link_metadata(prefix):
    records = []
    pc = checked_file(prefix / "lib/pkgconfig/gnutls.pc", MIB)
    text = pc.read_text()
    require(re.findall(r"^Version:\s*(\S+)\s*$", text, re.M) == ["3.8.9"], "Wrong pkg-config version")
    for key in ("prefix", "exec_prefix", "libdir", "includedir"):
        values = re.findall(r"^" + key + r"=(.*)$", text, re.M)
        require(len(values) == 1, f"Missing/duplicate pkg-config variable: {key}")
        allowed = {"prefix": {str(prefix)}, "exec_prefix": {"${prefix}", str(prefix)}, "libdir": {"${exec_prefix}/lib", "${prefix}/lib", str(prefix / "lib")}, "includedir": {"${prefix}/include", str(prefix / "include")}}[key]
        require(values[0] in allowed, f"Unexpected pkg-config root: {key}")
    for key in ("Libs", "Libs.private"):
        values = re.findall(r"^" + re.escape(key) + r":[ \t]*(.*)$", text, re.M)
        require(len(values) == 1, f"Missing/duplicate pkg-config field: {key}")
        records.append({"file": str(pc.relative_to(prefix)), "field": key, "tokens": validate_link_tokens(values[0], prefix)})
    for key in ("Requires", "Requires.private"):
        values = re.findall(r"^" + re.escape(key) + r":[ \t]*(.*)$", text, re.M)
        require(len(values) <= 1, f"Duplicate pkg-config field: {key}")
        if key == "Requires.private":
            require(len(values) == 1 and sorted(x.strip() for x in values[0].split(",")) == ["hogweed", "nettle"], "Expected exactly nettle, hogweed pkg-config private dependencies")
        elif values:
            require(not values[0].strip(), "Unexpected public pkg-config package dependency")
    la = checked_file(prefix / "lib/libgnutls.la", MIB)
    text = la.read_text()
    for key, expected in (("dlname", ""), ("library_names", ""), ("old_library", "libgnutls.a"), ("libdir", str(prefix / "lib"))):
        require(re.findall(r"^" + key + r"='([^'\n]*)'$", text, re.M) == [expected], f"Unexpected libtool metadata: {key}")
    values = re.findall(r"^dependency_libs='([^'\n]*)'$", text, re.M)
    require(len(values) == 1, "Missing/duplicate libtool dependency_libs")
    records.append({"file": str(la.relative_to(prefix)), "field": "dependency_libs", "tokens": validate_link_tokens(values[0], prefix)})
    return {"records": records, "files": [{"path": str(p.relative_to(prefix)), "sha256": sha256(p), "size": p.stat().st_size} for p in (pc, la)], "forwarded_to_link_command": False}

def cstring(data, offset, end, label):
    require(0 <= offset < end <= len(data), f"Invalid {label} string bounds")
    stop = data.find(b"\0", offset, end)
    require(stop >= 0, f"Unterminated {label}")
    try:
        result = data[offset:stop].decode("ascii")
    except UnicodeDecodeError as error:
        raise ProofError(f"Non-ASCII {label}") from error
    require(result and not any(ord(c) < 32 or ord(c) == 127 for c in result), f"Unsafe {label}")
    return result

# The actual reviewed 6ad06461546ce6236ceebeac build emits SDK=0 only
# for these pinned .s inputs. CPU/platform/minimum remain strict; SDK=0
# means unspecified metadata, never an encoded claim of SDK26.5.
SDK_UNSPECIFIED_ASSEMBLY = {
    "libnettle.a": frozenset((
        "chacha-core-internal.o", "aes128-encrypt-2.o", "aes128-decrypt-2.o",
        "aes192-encrypt-2.o", "aes192-decrypt-2.o", "aes256-encrypt-2.o",
        "aes256-decrypt-2.o", "chacha-2core.o", "chacha-4core.o",
        "ghash-set-key-2.o", "ghash-update-2.o", "sha1-compress-2.o",
        "sha256-compress-n-2.o",
    )),
    "libgnutls.a": frozenset(("aes-aarch64.o", "ghash-aarch64.o",
        "sha1-armv8.o", "sha256-armv8.o", "sha512-armv8.o")),
}

def inspect_macho(data, label, kind=1, wanted=frozenset(), archive=None):
    require(len(data) >= 32, f"Truncated Mach-O: {label}")
    magic, cpu, subtype, ftype, ncmds, size, flags, reserved = struct.unpack_from("<8I", data)
    require((magic, cpu, subtype, ftype, reserved) == (0xFEEDFACF, 0x0100000C, 0, kind, 0), f"Expected thin arm64 Mach-O kind{kind}: {label}")
    require(0 < ncmds <= 4096 and 8 * ncmds <= size <= len(data) - 32, "Invalid Mach-O command bounds")
    offset = 32
    versions, dependencies, symtabs, sections = [], [], [], []
    platform_command_types = []
    dylinkers = []
    for _ in range(ncmds):
        require(offset + 8 <= 32 + size, "Truncated Mach-O command")
        cmd, length = struct.unpack_from("<2I", data, offset)
        require(length >= 8 and length % 8 == 0 and offset + length <= 32 + size, "Invalid Mach-O command size")
        require(cmd not in (0x1D, 0x8000001C, 0x27), "Signature/rpath/dyld-environment forbidden")
        if cmd == 0x32:
            require(length >= 24, "Truncated LC_BUILD_VERSION")
            platform, minimum, sdk, ntools = struct.unpack_from("<4I", data, offset + 8)
            require(length == 24 + ntools * 8, "Malformed LC_BUILD_VERSION tool list")
            versions.append((platform, minimum, sdk))
            platform_command_types.append(cmd)
        elif cmd in (0x24, 0x25, 0x2F, 0x30):
            require(length == 16, "Malformed legacy version command")
            minimum, sdk = struct.unpack_from("<2I", data, offset + 8)
            versions.append((2 if cmd == 0x25 else -1, minimum, sdk))
            platform_command_types.append(cmd)
        elif cmd in (0xC, 0xD, 0x80000018, 0x8000001F, 0x20, 0x80000023):
            require(kind == 2 and cmd == 0xC and length >= 24, "Unexpected dylib load command")
            nameoff = struct.unpack_from("<I", data, offset + 8)[0]
            require(24 <= nameoff < length, "Invalid dylib name offset")
            name = cstring(data, offset + nameoff, offset + length, "dylib")
            require(name in SYSTEM_DYLIBS, f"Unapproved dylib: {name}")
            dependencies.append(name)
        elif cmd == 0xE:
            require(kind == 2 and length >= 16, "Unexpected dynamic linker")
            nameoff = struct.unpack_from("<I", data, offset + 8)[0]
            require(12 <= nameoff < length, "Invalid dyld offset")
            dylinkers.append(cstring(data, offset + nameoff, offset + length, "dyld"))
        elif cmd == 2:
            require(length == 24, "Malformed LC_SYMTAB")
            symtabs.append(struct.unpack_from("<4I", data, offset + 8))
        elif cmd == 0x19:
            require(length >= 72, "Truncated segment command")
            nsects = struct.unpack_from("<I", data, offset + 64)[0]
            require(length == 72 + 80 * nsects, "Malformed segment sections")
            for n in range(nsects):
                section = offset + 72 + 80 * n
                section_name = data[section:section + 16].rstrip(b"\0").decode("ascii")
                segment_name = data[section + 16:section + 32].rstrip(b"\0").decode("ascii")
                sections.append((segment_name, section_name))
        offset += length
    unspecified_assembly = kind == 1 and platform_command_types == [0x32] and label in SDK_UNSPECIFIED_ASSEMBLY.get(archive, ()) and versions == [(2, IOS_VERSION, 0)]
    require(offset == 32 + size and (versions == [(2, IOS_VERSION, SDK_VERSION)] or unspecified_assembly), f"Exactly one reviewed iOS17.0 platform/SDK command required: {label}")
    require(len(dependencies) == len(set(dependencies)), "Duplicate dylib command")
    if kind == 2:
        require("/usr/lib/libSystem.B.dylib" in dependencies, "Expected SDK libSystem dependency")
        require(dylinkers == ["/usr/lib/dyld"], "Expected only system dyld")
    else:
        require(not dependencies and not dylinkers, "Object has dynamic dependency")
    defined = {}
    if wanted:
        require(len(symtabs) == 1, "One linked symbol table required")
        symoff, nsyms, stroff, strsize = symtabs[0]
        require(nsyms <= 1000000 and symoff + nsyms * 16 <= len(data) and stroff + strsize <= len(data) and strsize > 0, "Invalid symbol table bounds")
        for i in range(nsyms):
            strx, ntype, nsect, desc, value = struct.unpack_from("<IBBHQ", data, symoff + 16 * i)
            if strx == 0 or ntype & 0xE0:
                continue
            require(strx < strsize, "Invalid symbol string offset")
            name = cstring(data, stroff + strx, stroff + strsize, "symbol")
            if name.startswith("_") and name[1:] in wanted:
                require(ntype & 1 and ntype & 0x0E == 0x0E, f"API not a real defined external symbol: {name}")
                require(0 < nsect <= len(sections) and sections[nsect - 1] == ("__TEXT", "__text"), f"API is not a text definition: {name}")
                require(name[1:] not in defined, f"Duplicate linked API: {name}")
                defined[name[1:]] = {"section": nsect, "address": value}
        require(set(defined) == set(wanted), "Linked image is missing retained API definitions")
    return {"architecture": "arm64", "platform": "iOS", "minimum": "17.0", "sdk": "unspecified" if unspecified_assembly else "26.5", "sdk_encoded": versions[0][2], "sdk_unspecified_assembly_exception": unspecified_assembly, "code_signature": False, "dependencies": sorted(dependencies), "retained_api_definitions": sorted(defined)}

def inspect_archive(path):
    path = checked_file(path, 256 * MIB)
    inventory, indexes = [], []
    with path.open("rb") as stream:
        require(stream.read(8) == b"!<arch>\n", "Only regular BSD/SysV ar accepted")
        while True:
            header = stream.read(60)
            if not header:
                break
            require(len(header) == 60 and header[58:] == b"`\n", "Malformed ar header")
            try:
                length = int(header[48:58].decode("ascii").strip())
                name = header[:16].decode("ascii").strip()
            except (ValueError, UnicodeError) as error:
                raise ProofError("Malformed ar member metadata") from error
            require(0 <= length <= 32 * MIB, "Invalid ar member size")
            data = stream.read(length)
            require(len(data) == length, "Truncated ar member")
            if length % 2:
                require(stream.read(1) == b"\n", "Invalid ar padding")
            if name.startswith("#1/"):
                require(re.fullmatch(r"#1/[0-9]+", name), "Invalid BSD ar name")
                count = int(name[3:])
                require(0 < count <= min(length, 4096), "Invalid BSD name length")
                try:
                    name = data[:count].rstrip(b"\0").decode("ascii")
                except UnicodeError as error:
                    raise ProofError("Non-ASCII ar name") from error
                data = data[count:]
            else:
                name = name.rstrip("/")
            if name in INDEX_NAMES:
                indexes.append(name)
                require(len(indexes) == 1, "Duplicate archive index")
                continue
            require(re.fullmatch(r"[A-Za-z0-9_.+-]+\.o", name), f"Unexpected ar object name: {name}")
            metadata = inspect_macho(data, name, archive=Path(path).name)
            inventory.append({"index": len(inventory), "member": name, "sha256": hashlib.sha256(data).hexdigest(), "size": len(data), **metadata})
            require(len(inventory) <= 20000, "Too many archive members")
    require(inventory, "Empty target archive")
    return {"path": str(path), "sha256": sha256(path), "size": path.stat().st_size, "member_count": len(inventory), "members": inventory}

def parse_nm_definitions(output):
    definitions = {}
    for line in output.splitlines():
        line = line.strip()
        if not line or line.endswith(":") or line.endswith(": no symbols"):
            continue
        match = re.fullmatch(r"([0-9a-fA-F]{8,16})\s+([A-Za-z?])\s+(\S+)", line)
        require(match is not None, f"Unrecognized nm output: {line[:160]}")
        address, kind, name = match.groups()
        require(kind.isupper() and kind != "U", "nm must report real external definitions only")
        definitions.setdefault(name, []).append({"kind": kind, "address": address})
    return definitions

def verify_api_definitions(per_archive, wanted):
    provenance = {}
    for symbol in sorted(wanted):
        found = [(archive, entry) for archive, definitions in per_archive.items() for entry in definitions.get("_" + symbol, [])]
        require(len(found) == 1 and found[0][0] == "libgnutls.a" and found[0][1]["kind"] == "T", f"Expected one real libgnutls text definition for {symbol}")
        provenance[symbol] = found[0][1]
    return provenance

def link_command(clang, sdk, prefix, source, output):
    # No shell, no flags copied from metadata; exactly4 real archive paths.
    return [str(clang), "-arch", "arm64", "-isysroot", str(sdk), "-miphoneos-version-min=17.0", "-std=gnu11", "-O2", "-fno-stack-protector", "-Werror=implicit-function-declaration", "-Werror=incompatible-function-pointer-types", "-I" + str(prefix / "include"), str(source), *[str(prefix / "lib" / name) for name in ARCHIVES], "-framework", "Security", "-framework", "CoreFoundation", "-Wl,-undefined,error", "-Wl,-no_adhoc_codesign", "-Wl,-map," + str(output / "api-link.map"), "-o", str(output / "gnutls-api-link-probe")]

class Proof:
    def __init__(self, prefix, output):
        self.prefix, self.output = prefix, output
        self.commands = []
        self.env = {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "HOME": str(output / "home"), "TMPDIR": str(output / "tmp"), "LC_ALL": "C", "LANG": "C", "TZ": "UTC"}
        self.stage = "preflight"
        self.requested_developer = os.environ.get("DEVELOPER_DIR", "")

    def run(self, name, argv):
        require(name not in {x["step"] for x in self.commands}, "Duplicate command label")
        require(Path(argv[0]) != self.output / "gnutls-api-link-probe", "Never execute target probe")
        log = self.output / "logs" / (name + ".log")
        start = time.monotonic()
        with log.open("xb") as stream:
            proc = subprocess.run([str(x) for x in argv], cwd=self.output, env=self.env, stdout=stream, stderr=subprocess.STDOUT, check=False)
        record = {"step": name, "argv": [str(x) for x in argv], "exit_code": proc.returncode, "seconds": round(time.monotonic() - start, 3), "log": str(log.relative_to(self.output)), "log_sha256": sha256(log)}
        self.commands.append(record)
        atomic_json(self.output / "commands.json", self.commands)
        require(proc.returncode == 0, f"{name} failed: status{proc.returncode}; see{log.name}")
        return log.read_text(errors="strict").strip()

    def select_developer(self):
        selected = self.requested_developer or self.run("developer-directory", ["/usr/bin/xcode-select", "-p"])
        path = Path(selected)
        require(path.is_absolute() and ".." not in path.parts and not any(ord(c) < 32 or ord(c) == 127 for c in selected), "Invalid selected Developer path")
        # Apple/provider installation aliases may resolve inside the selected Xcode.
        path = path.resolve(strict=True)
        require(path.is_dir() and path.parts[-2:] == ("Contents", "Developer"), "Full Xcode Contents/Developer directory required")
        self.env["DEVELOPER_DIR"] = str(path)
        self.developer_selection = {"source": "inherited provider DEVELOPER_DIR" if self.requested_developer else "xcode-select default", "path": str(path)}
        return path

    def selected_xcode_path(self, value, developer, directory=False):
        path = Path(value)
        require(path.is_absolute() and ".." not in path.parts and not any(ord(c) < 32 or ord(c) == 127 for c in value), "Invalid Xcode tool/SDK path")
        path = path.resolve(strict=True)
        require(path.is_relative_to(developer) and (path.is_dir() if directory else path.is_file()), "Selected tool/SDK must belong to reviewed Xcode")
        return path

    def execute(self):
        require(sys.platform == "darwin", "Target proof runs only on the reviewed Mac; no Linux fallback")
        require(self.run("host-architecture", ["/usr/bin/uname", "-m"]) == "arm64", "arm64 host required")
        developer = self.select_developer()
        require("Xcode 26.6" in self.run("xcode-version", ["/usr/bin/xcodebuild", "-version"]).splitlines(), "Xcode26.6 required")
        require(self.run("sdk-version", ["/usr/bin/xcrun", "--sdk", "iphoneos", "--show-sdk-version"]) == "26.5", "iPhoneOS SDK26.5 required")
        sdk = self.selected_xcode_path(self.run("sdk-path", ["/usr/bin/xcrun", "--sdk", "iphoneos", "--show-sdk-path"]), developer, directory=True)
        tools = {}
        for name in ("clang", "nm", "otool"):
            tools[name] = self.selected_xcode_path(self.run("find-" + name, ["/usr/bin/xcrun", "--sdk", "iphoneos", "--find", name]), developer)
            require(tools[name].is_relative_to(developer) and os.access(tools[name], os.X_OK), "Selected tool must belong to reviewed Xcode")
        require(self.run("clang-version", [tools["clang"], "--version"]).startswith("Apple clang version "), "Apple clang required")
        lock, wanted, source = load_contract()
        self.stage = "inputs"
        headers = inspect_headers(self.prefix)
        metadata = inspect_link_metadata(self.prefix)
        archives = {}
        symbols = {}
        for name in ARCHIVES:
            archives[name] = inspect_archive(self.prefix / "lib" / name)
            symbols[name] = parse_nm_definitions(self.run("symbols-" + name, [tools["nm"], "-gU", str(self.prefix / "lib" / name)]))
        api = verify_api_definitions(symbols, wanted)
        atomic_json(self.output / "input-evidence.json", {"headers": headers, "archives": archives, "link_metadata": metadata, "api_definitions": api, "developer_selection": self.developer_selection})
        self.stage = "target-link"
        self.run("target-api-link", link_command(tools["clang"], sdk, self.prefix, source, self.output))
        image = checked_file(self.output / "gnutls-api-link-probe", 256 * MIB)
        linkmap = checked_file(self.output / "api-link.map", 64 * MIB)
        # This is the strict binary check; text tools are supplemental evidence.
        binary = inspect_macho(image.read_bytes(), image.name, kind=2, wanted=wanted)
        self.run("probe-load-commands", [tools["otool"], "-l", image])
        self.run("probe-symbols", [tools["nm"], "-gU", image])
        require(inspect_headers(self.prefix) == headers, "Headers changed during proof")
        require(all(sha256(self.prefix / "lib" / name) == archives[name]["sha256"] for name in ARCHIVES), "Archive changed during proof")
        require(sha256(source) == PROBE_SHA256, "Probe source changed during proof")
        self.stage = "complete"
        record = {"schema": 1, "result": "passed-target-link-proof", "status": "passed-target-api-link", "developer_selection": self.developer_selection, "target_binaries_run": False, "package_install_performed": False, "signed": False, "feature_overlay_generated": False, "lock_sha256": LOCK_SHA256, "probe_source_sha256": PROBE_SHA256, "proof_helper_sha256": sha256(HERE / "prove_crypto_features.py"), "madeira": lock["madeira"], "wine": lock["wine"], "prefix": str(self.prefix), "target": binary, "api_count": len(api), "required_wine_count": 69, "optional_wine_count": 37, "headers": headers, "archives": {k: {key: value for key, value in v.items() if key != "members"} for k, v in archives.items()}, "image": {"path": image.name, "sha256": sha256(image), "size": image.stat().st_size}, "linkmap": {"path": linkmap.name, "sha256": sha256(linkmap)}, "tools": {k: {"path": str(v), "sha256": sha256(v)} for k, v in tools.items()}, "sdk": str(sdk), "sdk_version": "26.5", "xcode_version": "26.6", "commands_sha256": sha256(self.output / "commands.json"), "input_evidence_sha256": sha256(self.output / "input-evidence.json"), "timeout_owner": "outer reviewed process-group wrapper"}
        atomic_json(self.output / "proof.json", record)
        return record

def verify_command_logs(output, commands):
    for command in commands:
        path = Path(command["log"])
        require(not path.is_absolute() and len(path.parts) == 2 and path.parts[0] == "logs" and path.suffix == ".log", "Invalid command log path")
        # A successful compiler may emit no diagnostic text. Empty logs still
        # require exact bytes, a safe regular path, and the recorded SHA256.
        require(sha256(checked_file(output / path, 64 * MIB, allow_empty=True)) == command["log_sha256"], "Command log hash mismatch")


def verify_passed_proof(prefix, output, config):
    """Recheck immutable proof inputs before a caller may enable Wine features."""
    prefix = canonical(prefix, directory=True)
    output = canonical(output, directory=True)
    config = checked_file(config, MIB)
    require(sha256(config) == CONFIG_SHA256, "Original Wine config identity mismatch")
    base = config.read_text()
    require("#ifndef __WINE_CONFIG_H" in base and "#define __WINE_CONFIG_H" in base, "Expected original Wine config guard")
    require(not re.search(r"^\s*#\s*define\s+(?:HAVE_GNUTLS_CIPHER_INIT|SONAME_LIBGNUTLS)\b", base, re.M), "Original TLS feature state changed")
    proof = json.loads(checked_file(output / "proof.json", 8 * MIB).read_text())
    lock, wanted, source = load_contract()
    require(proof.get("result") == "passed-target-link-proof" and proof.get("status") == "passed-target-api-link" and proof.get("target_binaries_run") is False and proof.get("signed") is False, "Passed nonexecuting unsigned target proof required")
    require(proof.get("prefix") == str(prefix) and proof.get("lock_sha256") == LOCK_SHA256 and proof.get("probe_source_sha256") == PROBE_SHA256, "Proof identity mismatch")
    require(proof.get("proof_helper_sha256") == sha256(HERE / "prove_crypto_features.py") and proof.get("madeira") == lock["madeira"] and proof.get("wine") == lock["wine"], "Proof helper/source provenance changed")
    require(proof.get("api_count") == 106 and proof.get("required_wine_count") == 69 and proof.get("optional_wine_count") == 37 and proof.get("sdk_version") == "26.5" and proof.get("xcode_version") == "26.6" and proof.get("package_install_performed") is False, "Incomplete target proof")
    require(inspect_headers(prefix) == proof["headers"], "Target headers no longer match proof")
    require(set(proof["archives"]) == set(ARCHIVES), "Archive closure changed")
    for name in ARCHIVES:
        require(sha256(checked_file(prefix / "lib" / name, 256 * MIB)) == proof["archives"][name]["sha256"], "Target archive changed after proof")
    require(proof["image"]["path"] == "gnutls-api-link-probe", "Unexpected proof image")
    image = checked_file(output / "gnutls-api-link-probe", 256 * MIB)
    require(sha256(image) == proof["image"]["sha256"], "Proof image hash mismatch")
    require(inspect_macho(image.read_bytes(), image.name, kind=2, wanted=wanted) == proof["target"], "Proof image metadata drift")
    require(proof["linkmap"]["path"] == "api-link.map" and sha256(checked_file(output / "api-link.map", 64 * MIB)) == proof["linkmap"]["sha256"], "Proof link map hash mismatch")
    for name, field in (("commands.json", "commands_sha256"), ("input-evidence.json", "input_evidence_sha256")):
        require(sha256(checked_file(output / name, 64 * MIB)) == proof[field], "Proof evidence hash mismatch")
    evidence = json.loads((output / "input-evidence.json").read_text())
    require(inspect_link_metadata(prefix) == evidence["link_metadata"], "Link metadata changed after proof")
    commands = json.loads((output / "commands.json").read_text())
    require(commands and all(c["exit_code"] == 0 for c in commands), "Incomplete command proof")
    links = [c for c in commands if c["step"] == "target-api-link"]
    require(len(links) == 1, "Missing unique target link")
    expected = link_command(proof["tools"]["clang"]["path"], proof["sdk"], prefix, source, output)
    require(links[0]["argv"] == expected, "Target link command changed")
    verify_command_logs(output, commands)
    return proof

def generate_feature_overlay(prefix, proof_output, original_config, destination):
    """Future integration only. Tests never call the success/write branch."""
    proof = verify_passed_proof(prefix, proof_output, original_config)
    output = canonical(proof_output, directory=True)
    destination = canonical(destination, exists=False)
    require(destination.parent == output and not destination.exists(), "New overlay must live directly inside proof output")
    contents = ("/* Generated only after passed real iOS GnuTLS API/link proof. */\n"
                "#ifndef MADEIRA_VALIDATED_GNUTLS_FEATURES_H\n#define MADEIRA_VALIDATED_GNUTLS_FEATURES_H\n"
                "#ifndef __WINE_CONFIG_H\n#error Original immutable Wine config must be included first\n#endif\n"
                "#if defined(HAVE_GNUTLS_CIPHER_INIT) || defined(SONAME_LIBGNUTLS)\n#error Unexpected base TLS feature macros\n#endif\n"
                "#define HAVE_GNUTLS_CIPHER_INIT 1\n"
                "/* Static-provider token consumed by the existing iOS GnuTLS shim. */\n"
                "#define SONAME_LIBGNUTLS \"libgnutls.a\"\n#endif\n")
    destination.write_text(contents)
    evidence = {"path": destination.name, "sha256": sha256(destination), "base_config_sha256": CONFIG_SHA256, "proof_sha256": sha256(output / "proof.json"), "apply_only_to": ["bcrypt/gnutls.c", "secur32/schannel_gnutls.c", "Madeira crypt32_unixlib_ios.c"]}
    atomic_json(output / "feature-overlay.json", evidence)
    return evidence

def prepare_paths(prefix_arg, output_arg):
    prefix = canonical(prefix_arg, directory=True)
    output = canonical(output_arg, exists=False)
    require(".work" in prefix.parts and output.is_relative_to(prefix.parent) and not output.is_relative_to(prefix), "Proof output must stay beside target prefix in its .work build")
    require(output != prefix.parent and not output.exists(), "Fresh nonexistent proof output required")
    require(output.parent.is_dir(), "Proof output parent must already exist")
    return prefix, output

def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 2:
        print("usage: prove_crypto_features.py PREFIX PROOF_OUTPUT", file=sys.stderr)
        return 2
    proof = None
    try:
        prefix, output = prepare_paths(*argv)
        output.mkdir()
        for name in ("logs", "home", "tmp"):
            (output / name).mkdir()
        proof = Proof(prefix, output)
        proof.execute()
        print("Target API/link proof passed; no target image was executed and no feature overlay was emitted.")
        return 0
    except (ProofError, OSError, ValueError, KeyError, struct.error) as error:
        if proof is not None:
            atomic_json(proof.output / "failure.json", {"status": "failed", "stage": proof.stage, "error": str(error), "target_binaries_run": False, "feature_overlay_generated": False})
        print(f"crypto target proof failed: {error}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
