"""Pure, host-testable validation. Never loads or executes an input artifact."""
import hashlib
import io
import json
from pathlib import PurePosixPath
import re
import shlex
import struct
import tarfile

BSD_INDEX_NAMES = {"__.SYMDEF", "__.SYMDEF SORTED", "__.SYMDEF_64", "__.SYMDEF_64 SORTED"}


class Rejected(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise Rejected(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def safe_relative(value):
    require(isinstance(value, str) and value and "\\" not in value and "\x00" not in value,
            "unsafe path")
    p = PurePosixPath(value)
    require(not p.is_absolute() and all(v not in ("", ".", "..") for v in value.split("/")),
            "unsafe path")
    return p


def source_members(data, root, max_bytes=256 * 1024 * 1024, max_members=40000):
    """Check the complete tar before caller writes any contents; files/directories only."""
    rows, names, total = [], set(), 0
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        for m in tar:
            name = m.name.rstrip("/") if m.isdir() else m.name
            safe_relative(name)
            require(name not in names, "duplicate tar path")
            names.add(name)
            require(len(names) <= max_members, "tar member cap")
            require(name == root or name.startswith(root + "/"), "tar root mismatch")
            require(m.isdir() or m.isfile(), "links/special tar entries prohibited")
            require(not m.pax_headers.get("linkpath"), "pax link prohibited")
            if m.isfile():
                relative = name[len(root) + 1:]
                safe_relative(relative)
                total += m.size
                require(m.size <= max_bytes and total <= max_bytes, "tar byte cap")
                b = tar.extractfile(m).read(m.size + 1)
                require(len(b) == m.size, "tar length mismatch")
                rows.append((relative, b, 0o755 if m.mode & 0o111 else 0o644))
    require(rows, "empty crate")
    return rows


def ar_members(data):
    require(data.startswith(b"!<arch>\n"), "not a regular archive")
    offset, longnames = 8, b""
    while offset < len(data):
        require(offset + 60 <= len(data), "truncated ar header")
        h = data[offset:offset + 60]
        require(h[58:60] == b"`\n", "invalid ar header")
        try:
            size = int(h[48:58].decode("ascii").strip())
            name = h[:16].decode("ascii").strip()
        except (ValueError, UnicodeError) as error:
            raise Rejected("invalid ar field") from error
        start = offset + 60
        require(0 <= size <= len(data) - start, "truncated ar payload")
        payload = data[start:start + size]
        offset = start + size + (size % 2)
        require(offset <= len(data), "truncated ar alignment")
        if name == "//":
            longnames = payload
            continue
        if name in ("/", "/SYM64/"):
            continue
        if name.startswith("#1/"):
            try:
                n = int(name[3:])
            except ValueError as error:
                raise Rejected("invalid BSD ar name") from error
            require(0 < n <= len(payload), "truncated BSD ar name")
            name = payload[:n].rstrip(b"\x00").decode("utf-8")
            payload = payload[n:]
        elif name.startswith("/"):
            require(name[1:].isdigit(), "invalid GNU ar name")
            n = int(name[1:])
            require(n < len(longnames), "invalid GNU ar name offset")
            end = longnames.find(b"/\n", n)
            require(end >= n, "unterminated GNU ar name")
            name = longnames[n:end].decode("utf-8")
        else:
            name = name.removesuffix("/")
        if name in BSD_INDEX_NAMES:
            continue
        require(not name.startswith("__.SYMDEF"), "misleading BSD archive index name")
        require(name and "/" not in name and "\\" not in name, "unsafe ar member")
        yield name, payload
    require(offset == len(data), "ar trailing bytes")


def macho(data, filetype=1):
    require(len(data) >= 32 and data[:4] == b"\xcf\xfa\xed\xfe", "not raw little-endian Mach-O 64")
    magic, cpu, subtype, typ, ncmds, size, flags, reserved = struct.unpack_from("<8I", data)
    require(cpu == 0x0100000C and subtype & 0xFFFFFF in (0, 1), "not plain arm64")
    require(typ == filetype, "unexpected Mach-O type")
    require(ncmds <= 10000 and size <= len(data) - 32, "invalid load-command bounds")
    offset, platforms, commands = 32, [], []
    forbidden = {0x1D, 0x8000001C}  # code signature and rpath
    loads = {0xC, 0x18 | 0x80000000, 0x1F | 0x80000000, 0x20, 0x23 | 0x80000000}
    for _ in range(ncmds):
        require(offset + 8 <= 32 + size, "truncated load command")
        cmd, length = struct.unpack_from("<II", data, offset)
        require(length >= 8 and length % 4 == 0 and offset + length <= 32 + size,
                "invalid load command")
        require(cmd not in forbidden, "signature/rpath prohibited")
        if filetype == 1:
            require(cmd not in loads, "runtime library in object")
        if cmd == 0x32:
            require(length >= 24, "short build version")
            platform, minimum, sdk, count = struct.unpack_from("<4I", data, offset + 8)
            require(length == 24 + 8 * count, "invalid build-version tools")
            platforms.append((platform, minimum, sdk))
        elif cmd == 0x25:
            require(length == 16, "short iOS version")
            minimum, sdk = struct.unpack_from("<II", data, offset + 8)
            platforms.append((2, minimum, sdk))
        elif cmd in (0x24, 0x2F, 0x30):
            raise Rejected("non-iOS legacy platform")
        commands.append(cmd)
        offset += length
    require(offset == 32 + size and len(platforms) == 1, "missing/ambiguous platform")
    platform, minimum, sdk = platforms[0]
    require(platform == 2, "not device iOS")
    return dict(cpu=cpu, subtype=subtype, filetype=typ, minimum=minimum, sdk=sdk,
                load_commands=commands)


def raw_macho_metadata(data):
    """Diagnostic only: record all header/platform fields without accepting any object."""
    result = dict(header_hex=data[:32].hex(), magic=data[:4].hex(), load_commands=[])
    if len(data) < 32 or data[:4] != b"\xcf\xfa\xed\xfe":
        result["parse_error"] = "not little-endian Mach-O 64"
        return result
    keys = ("magic_number", "cpu", "subtype", "filetype", "ncmds", "sizeofcmds", "flags", "reserved")
    result.update(zip(keys, struct.unpack_from("<8I", data)))
    size, count = result["sizeofcmds"], result["ncmds"]
    if count > 10000 or size > len(data) - 32:
        result["parse_error"] = "load-command bounds invalid"
        return result
    result["load_command_bytes_hex"] = data[32:32 + min(size, 65536)].hex()
    result["load_command_bytes_truncated"] = size > 65536
    offset = 32
    for index in range(count):
        if offset + 8 > 32 + size:
            result["parse_error"] = "truncated load-command header"
            break
        cmd, length = struct.unpack_from("<II", data, offset)
        row = dict(index=index, offset=offset, command=cmd, length=length)
        result["load_commands"].append(row)
        if length < 8 or length % 4 or offset + length > 32 + size:
            result["parse_error"] = "load-command length invalid"
            break
        if cmd == 0x32 and length >= 24:
            row.update(zip(("platform", "minimum", "sdk", "tool_count"),
                           struct.unpack_from("<4I", data, offset + 8)))
        elif cmd in (0x24, 0x25, 0x2F, 0x30) and length >= 16:
            row.update(zip(("minimum", "sdk"), struct.unpack_from("<II", data, offset + 8)))
        offset += length
    if offset != 32 + size and "parse_error" not in result:
        result["parse_error"] = "load-command extent mismatch"
    return result


def validate_member(name, data, std_hashes, rust_hashes, native_hashes, own_binding):
    info = macho(data)
    digest = sha(data)
    is_std = digest in std_hashes
    is_native = digest in native_hashes
    is_own = bool(own_binding and name in own_binding["members"] and
                  own_binding["members"][name] == digest)
    is_rust = digest in rust_hashes or is_own
    require(is_std or is_native or is_rust, "unattributed archive object: " + name)
    if is_std:
        require(0 < info["minimum"] <= 0x120000, "Rust std minimum exceeds iOS 18")
        origin = "pinned-rust-standard-library"
    else:
        require(info["minimum"] == 0x120000, "fresh object minimum must be iOS 18")
        if is_native:
            require(info["sdk"] == 0x1A0500, "native C/asm SDK must be 26.5")
            origin = "fresh-native-crate-output"
        else:
            require(info["sdk"] in (0, 0x1A0500), "unrecognized Rust object SDK")
            origin = "fresh-rust-codegen-output"
    return dict(name=name, size=len(data), sha256=digest, origin=origin, **info)


def bind_own_rust(rows, *, compiler, source, source_sha256, out_dir, archive_data):
    """Bind own codegen names to a successful recorded exact rustc staticlib invocation."""
    candidates = [r for r in rows if r.get("kind") == "completed-staticlib"]
    require(len(candidates) == 1, "missing/ambiguous completed own rustc invocation")
    row = candidates[0]
    require(row.get("returncode") == 0 and row.get("compiler") == compiler,
            "own rustc execution did not complete with reviewed compiler")
    require(row.get("source") == source and row.get("source_sha256") == source_sha256,
            "own Rust source identity mismatch")
    require(row.get("target") == "aarch64-apple-ios" and row.get("deployment") == "18.0",
            "own Rust target identity mismatch")
    args = row["argv"]
    def values(flag):
        result = []
        for i, a in enumerate(args):
            if a == flag:
                require(i + 1 < len(args), "missing rustc option")
                result.append(args[i + 1])
            elif a.startswith(flag + "="):
                result.append(a[len(flag) + 1:])
        return result
    require(values("--crate-name") == ["madeira_rppairing"] and
            values("--crate-type") == ["staticlib"] and
            values("--target") == ["aarch64-apple-ios"] and
            values("--out-dir") == [out_dir], "own rustc crate/output identity mismatch")
    codegen = values("-C")
    suffixes = [v.split("=", 1)[1] for v in codegen if v.startswith("extra-filename=")]
    require(len(suffixes) == 1 and re.fullmatch(r"-[0-9a-f]{16}", suffixes[0]),
            "unrecognized own rustc output suffix")
    require("save-temps" in codegen or "save-temps=yes" in codegen, "own object retention missing")
    stem = "madeira_rppairing" + suffixes[0]
    require(row.get("output") == out_dir + "/lib" + stem + ".a" and
            row.get("output_sha256") == sha(archive_data), "own rustc archive identity mismatch")
    objects = row.get("fresh_objects", [])
    require(objects and len({x["path"] for x in objects}) == len(objects), "missing/duplicate fresh own objects")
    for obj in objects:
        require(obj["path"].startswith(out_dir + "/") and
                ".." not in PurePosixPath(obj["path"]).parts and obj["path"].endswith(".o") and
                re.fullmatch(r"[0-9a-f]{64}", obj["sha256"]), "unbound own object path/hash")
    hashes = {o["sha256"] for o in objects}
    members = {n: sha(b) for n, b in ar_members(archive_data) if sha(b) in hashes}
    require(members, "no own codegen members bound to exact rustc invocation")
    return dict(invocation=row, archive_sha256=sha(archive_data), members=members)


def final_definitions(output, exports):
    rows = re.findall(r"^([0-9a-fA-F]+) ([TDSB]) (_\S+)$", output, re.M)
    wanted = {"_" + name for name in exports}
    actual = [(address, kind, name) for address, kind, name in rows
              if name.startswith("_madeira_rppairing_")]
    require(len(actual) == len(wanted) and {x[2] for x in actual} == wanted,
            "final proof missing/duplicate C definitions")
    return [dict(address=a, kind=k, name=n) for a, k, n in actual]


def native_flags(output, libraries, frameworks):
    matches = re.findall(r"(?:^|\n)(?:note: )?native-static-libs:\s*([^\n]+)", output)
    require(len(matches) == 1, "missing/ambiguous native-static-libs")
    tokens = shlex.split(matches[0])
    require(0 < len(tokens) <= 64, "empty/oversized native library metadata")
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token == "-framework":
            require(i + 1 < len(tokens) and tokens[i + 1] in frameworks, "unknown framework")
            i += 2
        else:
            require(token.startswith("-l") and token[2:] in libraries, "unknown native linker token")
            i += 1
    return tokens


def shipped_crates(metadata):
    packages = {p["id"]: p for p in metadata["packages"]}
    nodes = {n["id"]: n for n in metadata["resolve"]["nodes"]}
    root = metadata["resolve"]["root"]
    require(root in nodes, "missing Cargo root")
    visited, todo = set(), [root]
    while todo:
        for dep in nodes[todo.pop()]["deps"]:
            if not any(k["kind"] is None for k in dep["dep_kinds"]):
                continue
            p = packages[dep["pkg"]]
            if any("proc-macro" in t["kind"] for t in p["targets"]):
                continue
            if dep["pkg"] not in visited:
                visited.add(dep["pkg"])
                todo.append(dep["pkg"])
    return [packages[i] for i in sorted(visited)]
