"""Pure, host-testable validation. Never loads or executes an input artifact."""
import hashlib
from dataclasses import dataclass, asdict
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


@dataclass(frozen=True)
class NativeOrigin:
    """Created only after current source, argv, object and archive binding succeeds."""
    member: str
    sha256: str
    archive: str
    archive_sha256: str
    source: str
    source_sha256: str
    object: str
    compiler_argv: tuple
    log_line: int
    log_sha256: str
    policy_sha256: str
    sdk0_exception: str | None

    def evidence(self):
        return asdict(self)


def bind_ring_native(policy, diagnostics, *, work, compiler, sdk, archive_data,
                     final_data, source_hashes, object_hashes, checksum, cargo_record, cargo_log):
    """Qualify exact current native bytes; no filename/hash-only SDK0 allowance."""
    require(policy.get("schema") == 1 and len(policy.get("sdk0_assembly", [])) == 11,
            "missing/excess ring SDK0 policy entries")
    exceptions = policy["sdk0_assembly"]
    for key in ("id", "source", "member"):
        require(len({e[key] for e in exceptions}) == 11, "duplicate ring exception identity")
    for e in exceptions:
        require(re.fullmatch(r"pregenerated/[A-Za-z0-9_-]+-ios64\.S", e["source"]) and
                re.fullmatch(r"[0-9a-f]{64}", e["source_sha256"]) and
                e["archive"] == "libring_core_0_17_14_.a" and
                e["id"] == "ring-0.17.14:" + e["source"], "invalid ring assembly exception")
    package = policy["package"]
    require(all(diagnostics["package"].get(k) == v for k, v in package.items()) and
            checksum["package"] == package["sha256"] == diagnostics["materialized_package_checksum"],
            "ring package provenance mismatch")
    require(not diagnostics["diagnostic_issues"] and cargo_record.get("returncode") == 0 and
            cargo_record.get("offline_sandbox") is True, "ring compilation incomplete/unproven")
    compiles = diagnostics["compilation_rows"]
    require(len(compiles) == diagnostics["compile_count"] == policy["compile_count"] == 24,
            "ring compile inventory changed")
    require(len({r["object"] for r in compiles}) == len(compiles) and
            len({r["source"] for r in compiles}) == len(compiles), "duplicate ring compilation provenance")
    require(sum(r["language_suffix"] == ".c" for r in compiles) == policy["c_source_count"] == 13,
            "ring C/assembly source inventory changed")
    lines = cargo_log.splitlines()
    logged = {}
    for number, line in enumerate(lines, 1):
        if line.startswith("[ring 0.17.14] running: "):
            argv = shlex.split(line.split("running: ", 1)[1])
            if "-c" in argv and "-o" in argv:
                logged[number] = argv
    require(set(logged) == {r["log_line"] for r in compiles} and len(logged) == len(compiles),
            "missing/duplicate ring compiler log rows")
    final_rows = list(ar_members(final_data))
    require(len({n for n, _ in final_rows}) == len(final_rows), "duplicate final archive member")
    final = {n: sha(b) for n, b in final_rows}
    archives = diagnostics["archives"]
    require(len(archives) == len(policy["archives"]) == len(archive_data) and
            {a["path"] for a in archives} == set(archive_data) and
            {PurePosixPath(a["path"]).name for a in archives} == set(policy["archives"]),
            "ring native archive inventory changed")
    origins, used_rows, seen_exceptions = {}, set(), set()
    vendor = work + "/vendor/ring-0.17.14"
    policy_hash = sha(json.dumps(policy, sort_keys=True, separators=(",", ":")).encode())
    for archive in archives:
        path = archive["path"]
        require(re.fullmatch(r"target/aarch64-apple-ios/release/build/ring-[0-9a-f]{16}/out/[^/]+\.a", path),
                "ring archive outside exact fresh target output")
        content = archive_data[path]
        require(archive.get("diagnostic_error") is None and archive["sha256"] == sha(content) and
                archive["size"] == len(content), "ring native archive bytes changed")
        members = list(ar_members(content))
        require(len(members) == len(archive["members"]) == policy["archives"][PurePosixPath(path).name],
                "ring native archive member inventory changed")
        for ordinal, ((name, data), recorded) in enumerate(zip(members, archive["members"])):
            digest = sha(data)
            try:
                require(recorded["ordinal"] == ordinal and recorded["name"] == name and
                        recorded["sha256"] == digest and recorded["size"] == len(data),
                        "ring recorded member identity mismatch")
                object_path = work + "/" + str(PurePosixPath(path).parent / name)
                matches = [i for i, r in enumerate(compiles) if r["object"] == object_path and
                           r.get("object_sha256") == digest]
                require(len(matches) == 1 and recorded["compile_rows"] == matches and
                        matches[0] not in used_rows, "missing/ambiguous ring object provenance")
                index = matches[0]; row = compiles[index]; used_rows.add(index)
                relative = row["source_relative"]; safe_relative(relative)
                source = vendor + "/" + relative
                require(row["source"] == source and row["language_suffix"] == PurePosixPath(source).suffix and
                        row["source_matches_materialized_package"] is True and
                        row["source_sha256"] == row["vendor_manifest_sha256"] == checksum["files"].get(relative) ==
                        source_hashes.get(source), "ring source provenance mismatch")
                require(row["object_size"] == len(data) and object_hashes.get(object_path) == digest,
                        "ring current object bytes changed")
                expected = [a.format(compiler=compiler, sdk=sdk, vendor=vendor,
                                    source=source, object=object_path) for a in policy["compiler_argv_template"]]
                require(row["argv"] == expected == logged[row["log_line"]] and
                        row["log"] == cargo_record["log"], "ring selected compiler/SDK/target argv mismatch")
                require(name not in origins and final.get(name) == digest, "ring final member propagation mismatch")
                candidates = [e for e in exceptions if e["source"] == relative or e["member"] == name]
                exception = None
                if candidates:
                    require(len(candidates) == 1, "ambiguous ring exception")
                    e = candidates[0]
                    require(e["source"] == relative and e["source_sha256"] == row["source_sha256"] and
                            e["archive"] == PurePosixPath(path).name and e["member"] == name and
                            row["language_suffix"] == ".S", "ring SDK0 exception identity mismatch")
                    exception = e["id"]; seen_exceptions.add(exception)
                info = macho(data)
                require(info["minimum"] == 0x120000 and
                        (info["sdk"] == 0x1A0500 or (info["sdk"] == 0 and exception is not None)),
                        "ring target flags mismatch: " + path + " : " + name +
                        " minimum=" + hex(info["minimum"]) + " sdk=" + hex(info["sdk"]))
                origins[name] = NativeOrigin(name, digest, path, sha(content), relative, row["source_sha256"],
                        object_path, tuple(expected), row["log_line"], sha(cargo_log.encode()), policy_hash,
                        exception if info["sdk"] == 0 else None)
            except Rejected as error:
                error.context = dict(stage="native-ring-member", archive=path, member=name,
                                     sha256=digest, error=str(error), raw_macho=raw_macho_metadata(data))
                raise
    require(used_rows == set(range(len(compiles))) and seen_exceptions == {e["id"] for e in exceptions},
            "incomplete ring native/exception binding")
    return origins


def validate_member(name, data, std_hashes, rust_hashes, native_origins, own_binding, *, known_native_hashes=frozenset()):
    info = macho(data)
    digest = sha(data)
    is_std = digest in std_hashes
    require(isinstance(native_origins, dict) and all(isinstance(v, NativeOrigin) for v in native_origins.values()),
            "typed native origin map required")
    native = native_origins.get(name)
    native_hashes = {v.sha256 for v in native_origins.values()} | set(known_native_hashes)
    is_native = native is not None or digest in native_hashes
    if is_native:
        require(native is not None and native.member == name and native.sha256 == digest,
                "native member lacks exact typed identity")
    is_own = bool(own_binding and name in own_binding["members"] and
                  own_binding["members"][name] == digest)
    is_rust = digest in rust_hashes or is_own
    require(is_std or is_native or is_rust, "unattributed archive object: " + name)
    if is_std and not is_native:
        require(0 < info["minimum"] <= 0x120000, "Rust std minimum exceeds iOS 18")
        origin = "pinned-rust-standard-library"
    else:
        require(info["minimum"] == 0x120000, "fresh object minimum must be iOS 18")
        if is_native:
            require(info["sdk"] == 0x1A0500 or (info["sdk"] == 0 and native.sdk0_exception is not None),
                    "native SDK0 lacks exact qualified assembly origin")
            origin = "qualified-ring-ios64-assembly" if info["sdk"] == 0 else "fresh-native-crate-output"
        else:
            require(info["sdk"] in (0, 0x1A0500), "unrecognized Rust object SDK")
            origin = "fresh-rust-codegen-output"
    result = dict(name=name, size=len(data), sha256=digest, origin=origin, **info)
    if is_native:
        result["native_binding"] = native.evidence()
    return result


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


def raw_symbol_table(data, maximum_bytes):
    """Read native Mach-O nlist64 only; never interpret embedded LLVM bitcode."""
    macho(data)
    count, command_bytes = struct.unpack_from("<II", data, 16)
    end_commands = 32 + command_bytes
    offset, sections, symtab = 32, [], None
    for _ in range(count):
        cmd, length = struct.unpack_from("<II", data, offset)
        if cmd == 0x19:
            require(length >= 72, "truncated symbol-proof segment")
            values = struct.unpack_from("<II16sQQQQiiII", data, offset)
            file_offset, file_size, nsects = values[5], values[6], values[9]
            require(length == 72 + 80 * nsects and len(sections) + nsects <= 255,
                    "invalid symbol-proof section count/command")
            require(file_offset <= len(data) and file_size <= len(data) - file_offset,
                    "symbol-proof segment file bounds")
            for index in range(nsects):
                position = offset + 72 + index * 80
                name, segment, address, size, start, align, reloc, nreloc, flags, r1, r2, r3 = \
                    struct.unpack_from("<16s16sQQ8I", data, position)
                section = dict(index=len(sections) + 1,
                    name=name.split(b"\0", 1)[0].decode("ascii"),
                    segment=segment.split(b"\0", 1)[0].decode("ascii"),
                    address=address, size=size, file_offset=start, flags=flags,
                    relocation_offset=reloc, relocation_count=nreloc)
                require(address + size <= 1 << 64 and reloc + nreloc * 8 <= len(data),
                        "symbol-proof section address/relocation bounds")
                zerofill = flags & 0xFF in (1, 0xC, 0x12)
                if size and not zerofill:
                    require(start >= end_commands and start >= file_offset and
                            size <= len(data) - start and start + size <= file_offset + file_size,
                            "symbol-proof section file bounds")
                section["file_backed"] = not zerofill
                sections.append(section)
        elif cmd == 2:
            require(length == 24 and symtab is None, "missing/duplicate/malformed LC_SYMTAB")
            symtab = struct.unpack_from("<4I", data, offset + 8)
        offset += length
    require(offset == end_commands and symtab is not None, "missing symbol table")
    symoff, nsyms, stroff, strsize = symtab
    raw_bytes = nsyms * 16 + strsize
    require(nsyms <= 1000000 and 0 < strsize and raw_bytes <= maximum_bytes,
            "raw symbol/string table cap")
    require(symoff >= end_commands and nsyms * 16 <= len(data) - symoff and
            stroff >= symoff + nsyms * 16 and strsize <= len(data) - stroff,
            "symbol/string bounds or overlap")
    require(all(not s["size"] or not s["file_backed"] or
                s["file_offset"] + s["size"] <= symoff for s in sections),
            "symbol table overlaps file-backed section")
    nlists, strings = data[symoff:symoff + nsyms * 16], data[stroff:stroff + strsize]
    api = []
    for index in range(nsyms):
        raw = nlists[index * 16:(index + 1) * 16]
        strx, kind, section_index, desc, value = struct.unpack("<IBBHQ", raw)
        require(strx < len(strings), "symbol string index outside table")
        stop = strings.find(b"\0", strx)
        require(stop >= strx, "unterminated symbol string")
        name = strings[strx:stop]
        if not kind & 0xE0 and kind & 0x0E == 0x0E:
            require(0 < section_index <= len(sections), "nlist section index outside table")
        if not name.startswith(b"_madeira_rppairing_"):
            continue
        require(kind == 0x0F and not desc & 0xC0,
                "pairing API is not a strong external N_SECT definition")
        require(0 < section_index <= len(sections), "API section index outside table")
        section = sections[section_index - 1]
        require(section["segment"] == "__TEXT" and section["name"] == "__text" and
                section["file_backed"] and section["flags"] & 0xFF == 0 and
                section["flags"] & 0x80000400 == 0x80000400,
                "pairing API is not file-backed instruction text")
        require(section["address"] <= value < section["address"] + section["size"] and value % 4 == 0,
                "pairing API address outside/alignment of text")
        position = section["file_offset"] + value - section["address"]
        require(position + 4 <= section["file_offset"] + section["size"] and position + 4 <= len(data),
                "pairing API instruction storage truncated")
        api.append(dict(symbol=name.decode("ascii"), nlist_index=index, raw_nlist_hex=raw.hex(),
                        string_index=strx, n_type=kind, n_sect=section_index, n_desc=desc, n_value=value,
                        section=section, file_offset=position,
                        first_instruction_bytes_hex=data[position:position + 4].hex()))
    return dict(raw_table_bytes=raw_bytes, header_hex=data[:32].hex(),
                load_command_bytes_hex=data[32:end_commands].hex(), sections=sections,
                symbol_offset=symoff, symbol_count=nsyms, string_offset=stroff, string_size=strsize,
                nlist_sha256=sha(nlists), nlist_hex=nlists.hex(),
                strings_sha256=sha(strings), strings_hex=strings.hex(), api_definitions=api)


def archive_api_symbols(data, exports, own_binding, maximum_bytes=2 * 1024**2):
    require(own_binding and own_binding.get("archive_sha256") == sha(data),
            "raw API symbols lack exact own archive binding")
    require(len(exports) == 11 and len(set(exports)) == 11, "exact eleven C exports required")
    expected = {"_" + name for name in exports}
    rows, definitions, seen, total = [], {}, set(), 0
    for ordinal, (name, body) in enumerate(ar_members(data)):
        digest = sha(body)
        require(name not in seen, "duplicate archive member in symbol proof")
        seen.add(name)
        try:
            symbols = raw_symbol_table(body, maximum_bytes - total)
            total += symbols["raw_table_bytes"]
            row = dict(member_ordinal=ordinal, member=name, member_sha256=digest,
                       member_size=len(body), **symbols)
            rows.append(row)
            for symbol in symbols["api_definitions"]:
                api = symbol["symbol"]
                require(api in expected and api not in definitions, "extra/duplicate pairing API definition")
                require(own_binding["members"].get(name) == digest,
                        "pairing API definition is not bound to own successful rustc output")
                definitions[api] = dict(archive="libmadeira_rppairing.a", archive_sha256=sha(data), member_ordinal=ordinal, member=name,
                                        member_sha256=digest, **symbol)
        except Rejected as error:
            error.context = dict(stage="raw-archive-symbols", member_ordinal=ordinal, member=name,
                                 member_sha256=digest, error=str(error), raw_macho=raw_macho_metadata(body))
            raise
    require(set(definitions) == expected, "missing strong pairing API definitions")
    return dict(method="raw-Mach-O-nlist64", archive="libmadeira_rppairing.a", archive_sha256=sha(data), archive_size=len(data),
                member_count=len(rows), raw_table_bytes=total, raw_table_cap_bytes=maximum_bytes,
                definitions=[definitions[n] for n in sorted(definitions)], members=rows,
                llvm_bitcode_interpreted=False, target_link_established=False)


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
