#!/usr/bin/env python3
"""Import only reviewed Wine source headers from an already-local ZIP.

No download, environment access, subprocess, tool install or compilation occurs.
The caller must separately review producer evidence and pin the exact lock bytes.
A valid lock asserts that review; this module cannot establish provenance from a
hash alone. Synthetic host fixtures are not evidence of a real producer success.

The destination's existing parent must be exclusively controlled by the caller.
A private sibling stage is verified before publication. An exclusive mkdir
reserves the fresh destination, then a rename replaces that owned empty directory.
No pre-existing destination is reused, including an empty directory or symlink.
Only .h files are published. The returned JSON-safe license records preserve the
exact notice bytes as content_base64; callers must retain them in their outputs.
"""
import argparse
import base64
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import struct
import tempfile
import zipfile
import zlib

MIB = 1024 * 1024
MAX_ARCHIVE_BYTES = 160 * MIB
MAX_HEADER_BYTES = 128 * MIB
MAX_LICENSE_BYTES = 16 * MIB
MAX_ENTRY_BYTES = 16 * MIB
MAX_METADATA_BYTES = 4 * MIB
MAX_HEADERS = 5000
MAX_LICENSES = 128
MAX_ENTRIES = MAX_HEADERS + MAX_LICENSES + 2
MAX_RATIO = 200
FAILED_PRODUCER_BUILDS = frozenset(("6ad052c8546ce6236ceebbaa", "6ad055de546ce6236ceebc3a"))
MANIFEST = "source-and-header-manifest.json"
REQUIRED_HEADERS = frozenset(("config.h", "dwrite.h", "dwrite_3.h", "mfobjects.h", "mftransform.h"))
REQUIRED_LICENSES = frozenset(("Licenses/Madeira/COPYING", "Licenses/Wine/COPYING.LIB"))
SOURCE = {
    "madeira": "279fd0f83170425db002fe25d6bd62f6355f497d",
    "wine": "9129e9684daaeae70da9435e7c6060e59392634e",
    "recipe_sha256": "c31e77940f4ed7ce45b9bcda507aa30ac3cc0e8cff413e494400233930287f03",
    "wrapper_sha256": "9a7107f2bac23755450b77784d2c15b2ab404e662b5674c98e40a6b28046e2d7",
}
SCOPE = (
    "Source-only control: native generated Wine headers and one arm64 iOS wineserver "
    "static archive. No full runtime link, FEX, DXMT, converter, Steam, IPA, signing "
    "or device test. Wine config.h is unchanged from --without-gnutls configuration; "
    "later ntdll/win32u work needs deliberate TLS configuration/prefix integration."
)


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _keys(value, keys, label):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError(f"Unexpected {label} schema")


def _hash(value, label, length=64):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{%d}" % length, value) or value == "0" * length:
        raise ValueError(f"Missing real {label} pin (PIN_PENDING is not importable)")
    return value


def _size(value, limit, label, allow_zero=False):
    if type(value) is not int or not (0 if allow_zero else 1) <= value <= limit:
        raise ValueError(f"Invalid or oversized {label}")
    return value


def _safe_name(name):
    if not isinstance(name, str) or len(name) > 512 or not re.fullmatch(r"[A-Za-z0-9_./+@-]+", name):
        raise ValueError("Unsafe ZIP or manifest path")
    path = PurePosixPath(name)
    if (path.is_absolute() or path.as_posix() != name or
            any(p in (".", "..") or p.endswith(".") for p in name.split("/"))):
        raise ValueError("Noncanonical ZIP or manifest path")
    return name


def _json(data, label):
    def unique(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:
                raise ValueError(f"Duplicate JSON key in {label}")
            obj[key] = value
        return obj

    def invalid_constant(unused):
        raise ValueError(f"Nonfinite JSON number in {label}")

    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=unique,
                          parse_constant=invalid_constant)
    except (UnicodeError, RecursionError, json.JSONDecodeError) as error:
        raise ValueError(f"Invalid {label} JSON") from error


def _no_symlinks(path):
    path = Path(path).absolute()
    current = Path(path.anchor)
    for part in path.parts[1:]:
        if part in (".", ".."):
            raise ValueError("Noncanonical local path")
        current /= part
        if current.is_symlink():
            raise ValueError("Symlink local path component refused")
    return path


def _local_bytes(path, limit):
    path = _no_symlinks(path)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    descriptor = os.open(path, flags)
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("Input must be a local regular file")
        _size(info.st_size, limit, "local input")
        data = stream.read(limit + 1)
        if len(data) != info.st_size or len(data) > limit:
            raise ValueError("Local input changed or exceeded its size bound")
    return data


def _inventory(entries, kind):
    if not isinstance(entries, list) or not 0 < len(entries) <= (MAX_HEADERS if kind == "headers" else MAX_LICENSES):
        raise ValueError(f"Invalid {kind} inventory")
    result, folded, total = {}, set(), 0
    for entry in entries:
        _keys(entry, ("path", "sha256", "size"), kind + " entry")
        name = _safe_name(entry["path"])
        if name in result or name.lower() in folded:
            raise ValueError(f"Duplicate or case-colliding {kind} entry")
        if kind == "headers":
            if not name.endswith(".h") or name.startswith(("include/", "Licenses/")):
                raise ValueError("Header inventory must use relative .h names")
            cap = 4 * MIB if name == "config.h" else MAX_ENTRY_BYTES
        else:
            if not name.startswith(("Licenses/Madeira/", "Licenses/Wine/")):
                raise ValueError("Unexpected license path")
            cap = 4 * MIB
        _hash(entry["sha256"], kind + " entry SHA256")
        total += _size(entry["size"], cap, kind + " entry",
                       allow_zero=kind == "headers" and name not in REQUIRED_HEADERS)
        result[name] = entry
        folded.add(name.lower())
    required = REQUIRED_HEADERS if kind == "headers" else REQUIRED_LICENSES
    if not required <= set(result):
        raise ValueError(f"Required {kind} missing")
    if total > (MAX_HEADER_BYTES if kind == "headers" else MAX_LICENSE_BYTES):
        raise ValueError(f"Aggregate {kind} size exceeded")
    # File/directory conflicts must fail even on case-insensitive macOS filesystems.
    for name in folded:
        if any(parent.as_posix() in folded for parent in PurePosixPath(name).parents if parent.as_posix() != "."):
            raise ValueError(f"File/directory collision in {kind}")
    return result


def load_lock(lock_path, *, expected_lock_sha256):
    """Verify exact reviewed lock bytes and fail before any source/build operation."""
    _hash(expected_lock_sha256, "reviewed lock SHA256")
    data = _local_bytes(lock_path, MAX_METADATA_BYTES)
    if _sha(data) != expected_lock_sha256:
        raise ValueError("Reviewed lock SHA256 mismatch")
    lock = _json(data, "lock")
    _keys(lock, ("schema_version", "status", "producer", "source", "artifact", "headers", "licenses",
                 "scope", "source_only", "runtime_linked", "device_tested"), "lock")
    if type(lock["schema_version"]) is not int or lock["schema_version"] != 1 or lock["status"] != "VERIFIED":
        raise ValueError("Header artifact is PIN_PENDING or its schema is unsupported")
    producer = lock["producer"]
    _keys(producer, ("build_id", "bootstrap_commit", "sdk_version", "xcode_version", "evidence_sha256", "result"), "producer")
    _hash(producer["build_id"], "producer build id", 24)
    if producer["build_id"] in FAILED_PRODUCER_BUILDS or producer["result"] != "passed-source-control-only":
        raise ValueError("Producer must have independently verified source-control success")
    _hash(producer["bootstrap_commit"], "producer bootstrap commit", 40)
    _hash(producer["evidence_sha256"], "externally verified producer evidence SHA256")
    if producer["sdk_version"] != "26.5" or producer["xcode_version"] != "26.6":
        raise ValueError("Producer SDK/Xcode must be exactly 26.5/26.6")
    if lock["source"] != SOURCE:
        raise ValueError("Source commits or reviewed recipe/wrapper pins mismatch")
    if (lock["scope"] != SCOPE or lock["source_only"] is not True or
            lock["runtime_linked"] is not False or lock["device_tested"] is not False):
        raise ValueError("Lock must preserve the frozen source-only scope")
    artifact = lock["artifact"]
    _keys(artifact, ("filename", "sha256", "size", "manifest_sha256", "config_sha256"), "artifact")
    if artifact["filename"] != "wine-headers.zip":
        raise ValueError("Unexpected artifact identity")
    for field in ("sha256", "manifest_sha256", "config_sha256"):
        _hash(artifact[field], "artifact " + field)
    _size(artifact["size"], MAX_ARCHIVE_BYTES, "artifact")
    headers = _inventory(lock["headers"], "headers")
    _inventory(lock["licenses"], "licenses")
    if headers["config.h"]["sha256"] != artifact["config_sha256"]:
        raise ValueError("Config pin differs from locked config.h")
    return lock


def _zip_envelope(data):
    """Bound record allocation before constructing Python's ZIP central directory."""
    if len(data) < 22:
        raise ValueError("Truncated ZIP")
    end = struct.unpack_from("<4s4H2IH", data, len(data) - 22)
    signature, disk, start_disk, count_here, count, directory_size, directory_offset, comment_length = end
    if (signature != b"PK\x05\x06" or disk or start_disk or comment_length or count_here != count or
            not 0 < count <= MAX_ENTRIES or directory_offset + directory_size != len(data) - 22 or
            not count * 47 <= directory_size <= count * (46 + 512)):
        raise ValueError("ZIP must have one bounded central directory and no prefix/trailing data")
    cursor = directory_offset
    for unused in range(count):
        if cursor + 46 > len(data) - 22:
            raise ValueError("Truncated ZIP central directory")
        fields = struct.unpack_from("<4s6H3I5H2I", data, cursor)
        name_size, extra_size, entry_comment, start_disk = fields[10:14]
        if (fields[0] != b"PK\x01\x02" or not 0 < name_size <= 512 or
                extra_size or entry_comment or start_disk):
            raise ValueError("Unbounded or unsupported ZIP central record")
        cursor += 46 + name_size
    if cursor != len(data) - 22:
        raise ValueError("ZIP central directory count/size mismatch")
    return count, directory_offset


def _zip_members(archive, data):
    """Accept only the producer's ordinary, single-disk, non-ZIP64 ZIP layout.

    The contiguous local records and exact central directory prohibit prefixes,
    suffixes, hidden/unreferenced records, overlapping data and concatenated ZIPs.
    No data descriptors, comments or extra fields are produced by the frozen writer.
    """
    count, directory_offset = _zip_envelope(data)
    members = archive.infolist()
    if len(members) != count or archive.start_dir != directory_offset or archive.comment:
        raise ValueError("ZIP central directory mismatch")
    names, folded, total, cursor, central = {}, set(), 0, 0, directory_offset
    for info in members:
        name = _safe_name(info.orig_filename)
        if info.filename != name or name in names or name.lower() in folded:
            raise ValueError("Duplicate, truncated or case-colliding ZIP name")
        mode = info.external_attr >> 16
        kind = stat.S_IFMT(mode)
        metadata = name in (MANIFEST, "SHA256SUMS")
        if (info.create_system != 3 or kind not in ((0, stat.S_IFREG) if metadata else (stat.S_IFREG,)) or
                info.external_attr & 0x10 or info.is_dir() or mode & 0o7000 or mode & 0o111):
            raise ValueError("ZIP entry is not an ordinary non-executable regular file")
        if info.flag_bits not in (0, 0x800):
            raise ValueError("Encrypted or unsupported ZIP flags")
        if (info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED) or
                info.extra or info.comment or info.internal_attr or info.volume or info.extract_version > 20):
            raise ValueError("Unsupported ZIP method or metadata")
        if name.startswith("include/") and name.endswith(".h"):
            cap = 4 * MIB if name == "include/config.h" else MAX_ENTRY_BYTES
        elif name.startswith(("Licenses/Madeira/", "Licenses/Wine/")) or metadata:
            cap = MAX_METADATA_BYTES
        else:
            raise ValueError("Unexpected non-header artifact entry")
        total += _size(info.file_size, cap, "ZIP entry",
                       allow_zero=name.startswith("include/") and name[8:] not in REQUIRED_HEADERS)
        if (info.compress_size < 0 or info.file_size > MAX_RATIO * info.compress_size or
                info.compress_size > MAX_ARCHIVE_BYTES or total > MAX_HEADER_BYTES + MAX_LICENSE_BYTES + 2 * MAX_METADATA_BYTES):
            raise ValueError("ZIP bomb, excessive ratio or aggregate size")
        if info.header_offset != cursor or cursor + 30 > directory_offset:
            raise ValueError("ZIP local records must be contiguous without a prefix")
        local = struct.unpack_from("<4s5H3I2H", data, cursor)
        sig, version, flags, method, unused_time, unused_date, crc, compressed, size, name_size, extra_size = local
        encoded = name.encode("utf-8" if info.flag_bits & 0x800 else "cp437")
        if (sig != b"PK\x03\x04" or version != info.extract_version or flags != info.flag_bits or
                method != info.compress_type or crc != info.CRC or compressed != info.compress_size or
                size != info.file_size or name_size != len(encoded) or extra_size or
                data[cursor + 30:cursor + 30 + name_size] != encoded):
            raise ValueError("ZIP local/central record mismatch")
        cursor += 30 + name_size + compressed
        if cursor > directory_offset or central + 46 > len(data) - 22:
            raise ValueError("ZIP record outside bounds")
        fields = struct.unpack_from("<4s6H3I5H2I", data, central)
        central_name, central_extra, central_comment, central_disk = fields[10:14]
        if (fields[0] != b"PK\x01\x02" or central_extra or central_comment or central_disk or
                central_name != len(encoded) or data[central + 46:central + 46 + central_name] != encoded):
            raise ValueError("Malformed central record")
        central += 46 + central_name
        names[name] = info
        folded.add(name.lower())
    if cursor != directory_offset or central != len(data) - 22:
        raise ValueError("Unreferenced or trailing ZIP data")
    return names


def _entry(archive, info, expected=None):
    # The structural pass established that local names agree and extras are absent.
    # Validate the whole compressed stream too: ZipExtFile alone accepts unused
    # trailing deflate bytes and some truncated streams with matching size/CRC.
    encoded = info.filename.encode("utf-8" if info.flag_bits & 0x800 else "cp437")
    archive.fp.seek(info.header_offset + 30 + len(encoded))
    compressed = archive.fp.read(info.compress_size)
    if len(compressed) != info.compress_size:
        raise ValueError("Truncated compressed ZIP entry")
    if info.compress_type == zipfile.ZIP_DEFLATED:
        decoder = zlib.decompressobj(-15)
        try:
            data = decoder.decompress(compressed, info.file_size + 1)
        except zlib.error as error:
            raise ValueError("Invalid deflate stream") from error
        if not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
            raise ValueError("ZIP deflate stream is truncated, oversized or has trailing data")
    else:
        data = compressed
    if len(data) != info.file_size or zlib.crc32(data) != info.CRC:
        raise ValueError("ZIP entry length/CRC mismatch")
    if expected is not None and (len(data) != expected["size"] or _sha(data) != expected["sha256"]):
        raise ValueError("ZIP entry differs from reviewed manifest hash/size")
    return data


def _publish(stage, destination):
    # mkdir is exclusive, even when an existing directory is empty.
    destination.mkdir(mode=0o700)
    owned = destination.stat()
    try:
        os.replace(stage, destination)
    except BaseException:
        # Do not delete a destination another actor substituted after reservation.
        current = destination.lstat()
        if (current.st_dev, current.st_ino) == (owned.st_dev, owned.st_ino):
            destination.rmdir()
        raise


def import_headers(archive_path, lock_path, destination, *, expected_lock_sha256):
    """Verify a local reviewed ZIP; publish headers and return preserved notices.

    A successful return verifies only the header import, not a runtime or build.
    The destination parent must exist; no remote URLs are accepted or opened.
    """
    lock = load_lock(lock_path, expected_lock_sha256=expected_lock_sha256)
    destination = _no_symlinks(destination)
    if destination.exists() or destination.is_symlink():
        raise ValueError("Fresh header destination required")
    if not destination.parent.is_dir():
        raise ValueError("Destination parent must already exist")
    data = _local_bytes(archive_path, MAX_ARCHIVE_BYTES)
    if len(data) != lock["artifact"]["size"] or _sha(data) != lock["artifact"]["sha256"]:
        raise ValueError("Artifact archive SHA256/size mismatch")
    stage = None
    try:
        _zip_envelope(data)
        with zipfile.ZipFile(io.BytesIO(data), "r") as archive:
            members = _zip_members(archive, data)
            if MANIFEST not in members or "SHA256SUMS" not in members:
                raise ValueError("Required artifact manifests missing")
            manifest_bytes = _entry(archive, members[MANIFEST])
            if _sha(manifest_bytes) != lock["artifact"]["manifest_sha256"]:
                raise ValueError("Artifact manifest SHA256 mismatch")
            manifest = _json(manifest_bytes, "artifact manifest")
            _keys(manifest, (*SOURCE, "headers", "licenses", "scope", "runtime_linked", "device_tested"), "artifact manifest")
            if {key: manifest[key] for key in SOURCE} != SOURCE:
                raise ValueError("Artifact source/recipe/wrapper pins mismatch")
            if (manifest["scope"] != SCOPE or manifest["runtime_linked"] is not False or
                    manifest["device_tested"] is not False):
                raise ValueError("Artifact does not preserve frozen source-only scope")
            headers = _inventory(manifest["headers"], "headers")
            licenses = _inventory(manifest["licenses"], "licenses")
            if headers != _inventory(lock["headers"], "headers") or licenses != _inventory(lock["licenses"], "licenses"):
                raise ValueError("Artifact header/license inventory differs from exact reviewed lock")
            expected_names = {"include/" + name for name in headers} | set(licenses) | {MANIFEST, "SHA256SUMS"}
            if set(members) != expected_names:
                raise ValueError("ZIP entries must match exact header/license manifest set")
            for name, entry in [*(('include/' + name, item) for name, item in headers.items()), *licenses.items()]:
                if members[name].file_size != entry["size"]:
                    raise ValueError("ZIP/manifest entry size mismatch")
            checksum_bytes = "".join(item["sha256"] + "  include/" + item["path"] + "\n" for item in manifest["headers"]).encode("ascii")
            if _entry(archive, members["SHA256SUMS"]) != checksum_bytes:
                raise ValueError("SHA256SUMS must match the complete exact header inventory")
            notices = []
            for name, expected in licenses.items():
                content = _entry(archive, members[name], expected)
                notices.append(dict(expected, content_base64=base64.b64encode(content).decode("ascii")))
            stage = Path(tempfile.mkdtemp(prefix="." + destination.name + ".headers-", dir=destination.parent))
            for name, expected in headers.items():
                content = _entry(archive, members["include/" + name], expected)
                if name == "config.h" and _sha(content) != lock["artifact"]["config_sha256"]:
                    raise ValueError("Generated config.h pin mismatch")
                path = stage / name
                path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
                with path.open("xb") as stream:
                    stream.write(content)
                path.chmod(0o644)
            stage.chmod(0o755)
            _no_symlinks(destination.parent)
            _publish(stage, destination)
            stage = None
    except (zipfile.BadZipFile, NotImplementedError, RuntimeError, struct.error) as error:
        raise ValueError("Malformed or unsupported ZIP artifact") from error
    finally:
        if stage is not None:
            shutil.rmtree(stage)
    return {
        "result": "verified-source-headers-only", "source": dict(SOURCE), "producer": lock["producer"],
        "archive_sha256": lock["artifact"]["sha256"], "archive_bytes": len(data),
        "lock_sha256": expected_lock_sha256, "manifest_sha256": lock["artifact"]["manifest_sha256"],
        "config_sha256": lock["artifact"]["config_sha256"], "header_count": len(headers),
        "header_bytes": sum(entry["size"] for entry in headers.values()), "headers": manifest["headers"],
        "licenses": notices, "scope": SCOPE, "source_only": True, "runtime_linked": False, "device_tested": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("lock", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--expected-lock-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        report = import_headers(args.archive, args.lock, args.destination,
                                expected_lock_sha256=args.expected_lock_sha256)
    except (ValueError, OSError) as error:
        parser.exit(1, "Header import refused: " + str(error) + "\n")
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
