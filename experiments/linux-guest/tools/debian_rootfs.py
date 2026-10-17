#!/usr/bin/env python3
"""Prepare a separate, offline Debian ARM64 experiment. Never opens legacy userdata.

lock authenticates Debian InRelease with the existing archive keyring, verifies
the by-hash Packages indexes, and asks isolated APT to solve required+POSIX deps.
download verifies every locked blob; no APT install or host system mutation.
Host image preparation is deliberately separate from a successful VM boot gate.
"""
import argparse
import datetime as dt
import email.utils
import hashlib
import json
import lzma
import os
from pathlib import Path
from pathlib import PurePosixPath
import re
import shutil
import shlex
import struct
import subprocess
import tarfile
import tempfile
import gzip
import stat
import urllib.parse
import urllib.request
import uuid

BASE = "https://deb.debian.org/debian/"
RELEASE_URL = BASE + "dists/trixie/InRelease"
KEYRING = Path("/usr/share/keyrings/debian-archive-keyring.gpg")
SIGNERS = {"04B54C3CDCA79751B16BC6B5225629DF75B188BD",
           "41587F7DB8C774BCCF131416762F67A0B2C39DE4"}
POSIX = ["apt", "ca-certificates", "e2fsprogs", "util-linux", "passwd", "procps", "kmod"]
DEFERRED = ["udev", "systemd-standalone-sysusers", "libsystemd-shared"]
HOST_TOOLS = ["e2fsprogs", "libext2fs2t64", "libcom-err2", "libss2", "logsave",
              "proot", "libtalloc2"]
IMAGE_UUID = "29c758bc-0416-4d87-b1ba-a922238a07f5"
FEATURES = {"compat": 44, "incompat": 194, "ro_compat": 1091}
FEATURE_NAMES = "none,has_journal,ext_attr,dir_index,filetype,extent,64bit,sparse_super,large_file,extra_isize,metadata_csum"
OFFLINE = False
DPKG_AUDIT_CHECK = """audit_output=$(dpkg --audit) || { echo 'dpkg audit command failed' >&2; exit 1; }
test -z "$audit_output" || { printf '%s\\n' "$audit_output" >&2; exit 1; }
"""


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def fetch(url, destination, size=None, digest=None, limit=128 * 1024 * 1024):
    """TLS required, bounded, atomic cache writes; cached files are rehashed."""
    p = Path(destination)
    if urllib.parse.urlparse(url).scheme != "https":
        raise ValueError("HTTPS required")
    if p.exists() and size is not None and p.stat().st_size == size and sha256(p) == digest:
        return p
    if OFFLINE:
        raise ValueError("offline cache missing or invalid: " + p.name)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".fetch-", dir=p.parent)
    try:
        with os.fdopen(fd, "wb") as out, urllib.request.urlopen(url, timeout=60) as response:
            total = 0
            for b in iter(lambda: response.read(1024 * 1024), b""):
                total += len(b)
                if total > min(limit, size if size is not None else limit):
                    raise ValueError("download exceeds bound")
                out.write(b)
        if size is not None and total != size:
            raise ValueError("download size mismatch")
        if digest is not None and sha256(tmp) != digest:
            raise ValueError("download digest mismatch")
        os.replace(tmp, p)
        return p
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def run(args, **kwargs):
    return subprocess.run([str(a) for a in args], check=True, text=True,
                          capture_output=True, **kwargs)


def paragraphs(text):
    for paragraph in text.split("\n\n"):
        result, key = {}, None
        for line in paragraph.splitlines():
            if line.startswith(" ") and key:
                result[key] += "\n" + line[1:]
            elif ":" in line:
                key, value = line.split(":", 1)
                result[key] = value.lstrip(" ")
        if result:
            yield result


def release_fields(text):
    # Only called AFTER successful GPG verification of the full clearsigned bytes.
    body = text.split("\n\n", 1)[1].split("-----BEGIN PGP SIGNATURE-----", 1)[0]
    return next(paragraphs(body))


def check_freshness(fields, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    issued = email.utils.parsedate_to_datetime(fields["Date"])
    if issued > now + dt.timedelta(hours=1) or now - issued > dt.timedelta(days=90):
        raise ValueError("release outside 90-day freshness window")
    if "Valid-Until" in fields and now > email.utils.parsedate_to_datetime(fields["Valid-Until"]):
        raise ValueError("expired release")
    if fields.get("Codename") != "trixie" or fields.get("Origin") != "Debian":
        raise ValueError("wrong Debian release")


def verify_release(path, keyring=KEYRING):
    with tempfile.TemporaryDirectory(prefix="ideck-gpg-") as home:
        result = run(["gpg", "--batch", "--no-options", "--homedir", home,
                      "--no-default-keyring", "--keyring", keyring,
                      "--status-fd", "1", "--verify", path])
    valid = []
    for line in result.stdout.splitlines():
        words = line.split()
        if len(words) > 3 and words[1] == "VALIDSIG":
            valid.append(words[-1])
    if not SIGNERS.intersection(valid):
        raise ValueError("missing accepted Debian trixie signature")
    fields = release_fields(Path(path).read_text())
    check_freshness(fields)
    return fields, sorted(set(valid))


def index_descriptor(fields, arch):
    target = f"main/binary-{arch}/Packages.xz"
    rows = [r.split() for r in fields["SHA256"].splitlines() if r.strip()]
    matching = [r for r in rows if r[2] == target]
    if len(matching) != 1:
        raise ValueError("missing/ambiguous package index")
    digest, size, _ = matching[0]
    return {"architecture": arch, "size": int(size), "sha256": digest,
            "url": BASE + f"dists/trixie/main/binary-{arch}/by-hash/SHA256/{digest}"}


def load_index(cache, descriptor):
    arch = descriptor["architecture"]
    xz = fetch(descriptor["url"], cache / f"Packages-{arch}.xz",
               descriptor["size"], descriptor["sha256"])
    # Compressed size is authenticated, and decompression is independently bounded.
    plain = cache / f"Packages-{arch}"
    with lzma.open(xz, "rb") as src, plain.open("wb") as out:
        count = 0
        for b in iter(lambda: src.read(1024 * 1024), b""):
            count += len(b)
            if count > 128 * 1024 * 1024:
                raise ValueError("package index decompression bound")
            out.write(b)
    return list(paragraphs(plain.read_text())), plain


def package_pin(record):
    filename = record["Filename"]
    if not re.fullmatch(r"pool/[A-Za-z0-9+._~/-]+\.deb", filename) or ".." in filename.split("/"):
        raise ValueError("unsafe Debian pool filename")
    return {"name": record["Package"], "version": record["Version"],
            "architecture": record["Architecture"], "filename": filename,
            "sha256": record["SHA256"], "size": int(record["Size"]),
            "installed_size_kib": int(record.get("Installed-Size", "0"))}


def resolve(records, plain, seeds, cache, architecture="arm64"):
    """APT solver only. It cannot install/download; all trust is verified above."""
    if architecture not in {"arm64", "amd64"}:
        raise ValueError("unsupported resolver architecture")
    plain = Path(plain).resolve()
    with tempfile.TemporaryDirectory(prefix="resolver-", dir=cache) as temporary:
        p = Path(temporary)
        (p / "lists/partial").mkdir(parents=True)
        (p / "archives/partial").mkdir(parents=True)
        (p / "status").touch()
        (p / "sources").write_text(f"deb [arch={architecture}] https://deb.debian.org/debian trixie main\n")
        (p / f"lists/deb.debian.org_debian_dists_trixie_main_binary-{architecture}_Packages").symlink_to(plain)
        (p / "apt.conf").write_text('Dir::Etc::parts "-"; Dir::Etc::main "-";\n')
        options = {"Dir::State::status": p / "status", "Dir::State::lists": p / "lists",
                   "Dir::Cache::archives": p / "archives", "Dir::Etc::sourcelist": p / "sources",
                   "Dir::Etc::sourceparts": "-", "APT::Architecture": architecture,
                   "APT::Architectures": architecture, "APT::Install-Recommends": "false",
                   "Debug::NoLocking": "true"}
        args = ["apt-get"]
        for key, value in options.items():
            args += ["-o", f"{key}={value}"]
        result = run(args + ["--simulate", "install", *sorted(seeds)],
                     env={**os.environ, "APT_CONFIG": str(p / "apt.conf"), "LC_ALL": "C"})
        selected = re.findall(r"^Inst ([^ :]+)(?::" + architecture + r")? \((\S+) ", result.stdout, re.M)
    by_identity = {(r["Package"], r["Version"]): r for r in records if "Package" in r}
    if not selected or len({n for n, _ in selected}) != len(selected):
        raise ValueError("APT resolver returned empty/ambiguous closure")
    return sorted([package_pin(by_identity[key]) for key in selected], key=lambda x: x["name"])


def create_lock(cache, output, keyring):
    cache.mkdir(parents=True, exist_ok=True)
    release = fetch(RELEASE_URL, cache / "InRelease", limit=1024 * 1024)
    fields, signatures = verify_release(release, keyring)
    indexes = [index_descriptor(fields, arch) for arch in ("arm64", "amd64")]
    records, plain = load_index(cache, indexes[0])
    seeds = sorted(set(POSIX + [r["Package"] for r in records if r.get("Priority") == "required" or r.get("Essential") == "yes"]))
    packages = resolve(records, plain, seeds, cache)
    host_records, _ = load_index(cache, indexes[1])
    host = {r["Package"]: r for r in host_records}
    tools = [package_pin(host[name]) for name in HOST_TOOLS]
    lock = {"schema": 1, "distribution": "debian", "suite": "trixie", "architecture": "arm64",
            "release": {"url": RELEASE_URL, "sha256": sha256(release), "size": release.stat().st_size,
                        "date": fields["Date"], "valid_until": fields.get("Valid-Until"),
                        "max_age_days": 90, "signer_fingerprints": signatures,
                        "keyring_sha256": sha256(keyring), "indexes": indexes},
            "selection": {"variant": "minbase-plus-posix", "install_recommends": False, "direct": seeds},
            "packages": packages, "host_tools": tools,
            "deferred_desktop_packages": [package_pin(next(r for r in records if r["Package"] == name)) for name in DEFERRED],
            "totals": {"package_count": len(packages), "download_bytes": sum(p["size"] for p in packages),
                       "installed_size_bytes": sum(p["installed_size_kib"] * 1024 for p in packages)},
            "image": {"size_bytes": 512 * 1024 * 1024, "budget_bytes": 4 * 1024**3,
                      "uuid": IMAGE_UUID, "block_size": 4096, "inode_size": 256,
                      "descriptor_size": 64, "features": FEATURES},
            "boundaries": {"gui_packages": False, "guest_boot_verified": False,
                           "legacy_userdata_accessed": False, "payload_published": False}}
    Path(output).write_text(json.dumps(lock, indent=2) + "\n")
    return lock


def authenticate_lock(lock, cache, keyring):
    validate_lock(lock)
    release = lock["release"]
    if release["url"] != RELEASE_URL or lock["architecture"] != "arm64":
        raise ValueError("unexpected lock distribution")
    p = fetch(release["url"], cache / "InRelease", release["size"], release["sha256"], limit=1024 * 1024)
    fields, signers = verify_release(p, keyring)
    if not set(release["signer_fingerprints"]).issubset(signers):
        raise ValueError("release signer mismatch")
    for descriptor in release["indexes"]:
        if descriptor != index_descriptor(fields, descriptor["architecture"]):
            raise ValueError("index is not authenticated by release")
        records, _ = load_index(cache, descriptor)
        pins = {p["Filename"]: package_pin(p) for p in records if "Filename" in p}
        locked = lock["packages"] + lock.get("deferred_desktop_packages", []) if descriptor["architecture"] == "arm64" else lock["host_tools"]
        if any(pins.get(p["filename"]) != p for p in locked):
            raise ValueError("package pin is not authenticated by index")


def validate_lock(lock):
    if (lock.get("schema"), lock.get("distribution"), lock.get("suite"), lock.get("architecture")) != (1, "debian", "trixie", "arm64"):
        raise ValueError("unexpected lock schema")
    image = lock["image"]
    if (not isinstance(image["size_bytes"], int) or isinstance(image["size_bytes"], bool)
            or not 64 * 1024**2 <= image["size_bytes"] <= 4 * 1024**3
            or image["size_bytes"] % 4096):
        raise ValueError("image size outside bounded experiment")
    if (image["uuid"] != IMAGE_UUID or image["block_size"] != 4096 or image["inode_size"] != 256
            or image["descriptor_size"] != 64 or image["features"] != FEATURES):
        raise ValueError("unexpected ext4 contract")
    if [p["architecture"] for p in lock["release"]["indexes"]] != ["arm64", "amd64"]:
        raise ValueError("unexpected package indexes")
    for key, architectures in (("packages", {"arm64", "all"}), ("host_tools", {"amd64", "all"})):
        packages = lock[key]
        if not packages or len({p["name"] for p in packages}) != len(packages):
            raise ValueError("empty/duplicate package pins")
        for package in packages:
            if (package["architecture"] not in architectures or not re.fullmatch(r"[0-9a-f]{64}", package["sha256"])
                    or not 0 < package["size"] <= 128 * 1024**2):
                raise ValueError("invalid package pin")
    if {p["name"] for p in lock["host_tools"]} != set(HOST_TOOLS):
        raise ValueError("unexpected host tool selection")
    if not set(lock["selection"]["direct"]).issubset({p["name"] for p in lock["packages"]}):
        raise ValueError("missing direct package")


def download(lock, cache, keyring):
    authenticate_lock(lock, cache / "metadata", keyring)
    paths = {}
    for package in lock["packages"] + lock["host_tools"]:
        p = cache / "debs" / Path(package["filename"]).name
        paths[package["name"], package["architecture"]] = fetch(
            BASE + urllib.parse.quote(package["filename"], safe="/+"), p,
            package["size"], package["sha256"])
    return paths


def ext4_header(path):
    with Path(path).open("rb") as f:
        f.seek(1024)
        sb = f.read(1024)
    if len(sb) != 1024 or struct.unpack_from("<H", sb, 56)[0] != 0xEF53:
        raise ValueError("not ext4")
    return {"uuid": str(uuid.UUID(bytes=sb[104:120])), "block_size": 1024 << struct.unpack_from("<I", sb, 24)[0],
            "features": dict(zip(("compat", "incompat", "ro_compat"), struct.unpack_from("<III", sb, 92))),
            "inode_size": struct.unpack_from("<H", sb, 88)[0], "descriptor_size": struct.unpack_from("<H", sb, 254)[0]}


def normalized_member(name):
    name = name.removeprefix("./").strip("/")
    if any(c in name for c in '\n\r\0"\\') or ".." in name.split("/"):
        raise ValueError("unsupported package filename")
    # Debian trixie uses merged-/usr. Package metadata addresses canonical paths.
    head, _, tail = name.partition("/")
    if head in {"bin", "sbin", "lib"} and tail:
        name = "usr/" + name
    return name


def package_ownership(deb):
    result = {}
    process = subprocess.Popen(["dpkg-deb", "--fsys-tarfile", str(deb)], stdout=subprocess.PIPE)
    try:
        with tarfile.open(fileobj=process.stdout, mode="r|") as archive:
            for member in archive:
                result[normalized_member(member.name)] = [member.uid, member.gid]
    finally:
        process.stdout.close()
    if process.wait() != 0:
        raise ValueError("package ownership extraction failed")
    return result


def debugfs_quote(path):
    if any(c in str(path) for c in '\n\r\0"\\'):
        raise ValueError("unsafe debugfs path")
    return '"' + str(path) + '"'


def rooted_path(root, guest_path):
    """Resolve guest symlinks without letting an absolute target escape root."""
    pending = list(PurePosixPath(guest_path).parts)
    resolved, links = [], 0
    while pending:
        part = pending.pop(0)
        if part in ("/", ".", ""):
            continue
        if part == "..":
            if resolved:
                resolved.pop()
            continue
        candidate = root.joinpath(*resolved, part)
        if candidate.is_symlink():
            links += 1
            if links > 40:
                raise ValueError("guest symlink loop")
            target = os.readlink(candidate)
            if target.startswith("/"):
                resolved = []
            pending = list(PurePosixPath(target).parts) + pending
        else:
            resolved.append(part)
    return root.joinpath(*resolved)


def elf_dependencies(path):
    data = path.read_bytes()
    if data[:4] != b"\x7fELF":
        return None
    if len(data) < 64 or data[4:6] != b"\x02\x01" or struct.unpack_from("<H", data, 18)[0] != 183:
        raise ValueError("rootfs contains non-ARM64 ELF: " + str(path))
    offset = struct.unpack_from("<Q", data, 32)[0]
    stride, count = struct.unpack_from("<HH", data, 54)
    segments, dynamic, interpreter = [], None, None
    for i in range(count):
        kind, _flags, at, virtual, _physical, size, _memsize, _align = struct.unpack_from("<IIQQQQQQ", data, offset + stride * i)
        if kind == 1:
            segments.append((virtual, size, at))
        elif kind == 2:
            dynamic = (at, size)
        elif kind == 3:
            interpreter = data[at:at + size].rstrip(b"\0").decode()
    needed, search, string_address = [], [], None
    if dynamic:
        tags = []
        for at in range(dynamic[0], sum(dynamic), 16):
            tag, value = struct.unpack_from("<qQ", data, at)
            if tag == 0:
                break
            tags.append((tag, value))
            if tag == 5:
                string_address = value
        if string_address is None:
            raise ValueError("ELF dynamic table without string table")
        tables = [at + string_address - virtual for virtual, size, at in segments if virtual <= string_address < virtual + size]
        if len(tables) != 1:
            raise ValueError("ELF string table mapping")
        for tag, value in tags:
            if tag in (1, 15, 29):
                start = tables[0] + value
                text = data[start:data.index(b"\0", start)].decode()
                if tag == 1:
                    needed.append(text)
                else:
                    search.extend(text.split(":"))
    return interpreter, needed, search


def check_elf_closure(root):
    count, edges = 0, 0
    parsed = {}
    def parse(path):
        if path not in parsed:
            parsed[path] = elf_dependencies(path)
        return parsed[path]
    defaults = ["/lib/aarch64-linux-gnu", "/usr/lib/aarch64-linux-gnu", "/lib", "/usr/lib"]
    for directory, _names, files in os.walk(root):
        for name in files:
            path = Path(directory) / name
            if path.is_symlink():
                continue
            entry = parse(path)
            if entry is None:
                continue
            count += 1
            interpreter, needed, search = entry
            if interpreter and (interpreter != "/lib/ld-linux-aarch64.so.1" or not rooted_path(root, interpreter).is_file()):
                raise ValueError("missing/unexpected ELF interpreter")
            origin = "/" + str(path.parent.relative_to(root))
            search = [s.replace("${ORIGIN}", origin).replace("$ORIGIN", origin) for s in search]
            if any("$" in s or not s.startswith("/") for s in search):
                raise ValueError("unsupported ELF dynamic search path")
            for dependency in needed:
                candidates = [rooted_path(root, p + "/" + dependency) for p in search + defaults]
                if "/" in dependency or not any(p.is_file() and parse(p) is not None for p in candidates):
                    raise ValueError("unresolved ELF DT_NEEDED: " + str(path.relative_to(root)) + ":" + dependency)
                edges += 1
    if not count:
        raise ValueError("empty ELF closure")
    return {"arm64_elf_files": count, "dt_needed_edges": edges, "result": "pass"}


def verify_image_ownership(host, env, raw, manifest, output, source_tree=None, expected_epoch=None):
    batch = output / "ownership-verify.debugfs"
    batch.write_text("".join("stat " + debugfs_quote("/" if p == "." else "/" + p) + "\n" for p in manifest))
    result = run([host / "usr/sbin/debugfs", "-f", batch, raw], env=env)
    records = result.stdout.split("debugfs: stat ")[1:]
    if len(records) != len(manifest):
        raise ValueError("incomplete persisted ownership audit")
    for (name, expected), record in zip(manifest.items(), records):
        actual = re.search(r"User:\s+(\d+)\s+Group:\s+(\d+)\b", record)
        if not actual or [int(actual[1]), int(actual[2])] != expected:
            raise ValueError("persisted ownership mismatch: " + name)
        if expected_epoch is not None:
            times = re.findall(r"\b(atime|mtime|ctime|crtime):\s+0x([0-9a-f]+):([0-9a-f]+)", record)
            if (len(times) != 4 or {field for field, _, _ in times} != {"atime", "mtime", "ctime", "crtime"}
                    or any(int(seconds, 16) != expected_epoch or int(extra, 16) != 0 for _, seconds, extra in times)):
                raise ValueError("noncanonical persisted inode timestamp: " + name)
        if source_tree:
            actual_mode = re.search(r"Mode:\s+([0-7]+)", record)
            source_mode = stat.S_IMODE((source_tree / name).lstat().st_mode)
            if not actual_mode or int(actual_mode[1], 8) != source_mode:
                raise ValueError("persisted mode mismatch: " + name)
    return len(records)


def canonical_guest_modes(root):
    # Output/cache remain private. Guest public directories/config need exact
    # modes independently of a restrictive host umask (normally 0077 here).
    for directory in ("dev", "proc", "sys", "run", "data"):
        (root / directory).chmod(0o755)
    (root / "tmp").chmod(0o1777)
    for name in ("etc/hostname", "etc/hosts", "etc/machine-id", "etc/apt/sources.list", "etc/fstab"):
        (root / name).chmod(0o644)


def canonical_seed_content(root, epoch):
    """Normalize generated installation state in this fresh seed, never live data."""
    log = root / "var/log/alternatives.log"
    if log.exists() and stat.S_ISREG(log.lstat().st_mode):
        log.write_bytes(b"")
    # Package account setup uses the current UTC day, including system users.
    # All fresh-seed accounts must be locked. Retain every password field and
    # account while fixing only last-change day, including the backup copy.
    for name in ("etc/shadow", "etc/shadow-"):
        path = root / name
        if not path.exists():
            continue
        lines = []
        for line in path.read_text().splitlines():
            fields = line.split(":")
            if len(fields) != 9 or not fields[1].startswith(("!", "*")):
                raise ValueError("expected locked seed account")
            fields[2] = str(epoch // 86400)
            lines.append(":".join(fields))
        path.write_text("\n".join(lines) + "\n")


def inode_publication_commands(manifest, epoch):
    # This exact source pin is from 2026. Refuse an unsupported extended epoch
    # rather than silently truncating ext4 signed seconds/extra epoch bits.
    if not 0 <= epoch <= 0x7fffffff:
        raise ValueError("unsupported seed epoch")
    commands = []
    for name, (uid, gid) in sorted(manifest.items()):
        target = debugfs_quote("/" if name == "." else "/" + name)
        commands += [f"set_inode_field {target} uid {uid}", f"set_inode_field {target} gid {gid}"]
        # os.utime cannot set source ctime; mke2fs traversal may update atime.
        # Canonicalize the resulting ext4 inodes, including nanosecond fields.
        for field in ("atime", "mtime", "ctime", "crtime"):
            commands += [f"set_inode_field {target} {field} @{epoch}",
                         f"set_inode_field {target} {field}_extra 0"]
    return commands


def stage_qemu_helper(qemu, output, expected_digest):
    # PRoot 5.1 splits -q on spaces without shell quoting. Resolve a relative
    # filename from a controlled cwd, then let PRoot canonicalize it itself.
    # The staged copy is still the exact reviewed executable, not a wrapper.
    helper = output / "qemu-user"
    shutil.copyfile(qemu, helper)
    helper.chmod(0o755)
    if sha256(helper) != expected_digest:
        raise ValueError("staged QEMU helper digest mismatch")
    return "./qemu-user"


def build(lock, cache, output, keyring, qemu, qemu_digest):
    """Rootless configured ARM64 tree -> unmounted ext4 using pinned host tools.

    PRoot is a host preparation convenience, NOT a security boundary or a VM.
    Actual ownership is written by debugfs from authenticated .deb tar headers,
    configured statoverrides, and explicit user/shadow metadata, not fake stat.
    """
    builder_source = Path(__file__).resolve()
    builder_digest = sha256(builder_source)
    validate_lock(lock)
    if sha256(qemu) != qemu_digest:
        raise ValueError("QEMU user-mode helper digest mismatch")
    # Never resume/overwrite an existing image or tree, including interrupted runs.
    output.mkdir(parents=True, exist_ok=False)
    qemu_command = stage_qemu_helper(qemu, output, qemu_digest)
    paths = download(lock, cache, keyring)
    host = output / "host-tools"
    for package in lock["host_tools"]:
        run(["dpkg-deb", "--extract", paths[package["name"], package["architecture"]], host])
    # Do not expose host HOME/proxy/credentials through the bound /proc environ.
    private_tmp = output / "tmp"
    private_tmp.mkdir(mode=0o700)
    env = {"PATH": os.defpath, "LD_LIBRARY_PATH": str(host / "usr/lib/x86_64-linux-gnu"),
           "LC_ALL": "C", "TMPDIR": str(private_tmp), "PROOT_TMP_DIR": str(private_tmp)}
    compat = output / "proot-compat"
    compat_source = Path(__file__).with_name("debian_proot_compat.c")
    run(["cc", "-O2", "-Wall", "-Wextra", "-Werror", compat_source, "-o", compat])
    root = output / "tree"
    for name in ("bin", "sbin", "lib"):
        (root / "usr" / name).mkdir(parents=True, exist_ok=True)
        (root / name).symlink_to("usr/" + name)
    ownership = {}
    for package in lock["packages"]:
        deb = paths[package["name"], package["architecture"]]
        ownership.update(package_ownership(deb))
        run(["dpkg-deb", "--extract", deb, root])
    for name in ("proc", "sys", "dev", "run", "tmp", "var/lib/dpkg", "home", "data"):
        (root / name).mkdir(parents=True, exist_ok=True)
    (root / "var/lib/dpkg/status").touch()
    policy = root / "usr/sbin/policy-rc.d"
    policy.write_text("#!/bin/sh\nexit 101\n")
    policy.chmod(0o755)
    proot = [compat, host / "usr/bin/proot", "-0", "-q", qemu_command, "-r", root,
             "-b", "/proc", "-b", "/dev", "-b", str(cache / "debs") + ":/packages", "-w", "/",
             "/usr/bin/env", "-i", "DEBIAN_FRONTEND=noninteractive", "LC_ALL=C",
             "PATH=/usr/sbin:/usr/bin:/sbin:/bin", "HOME=/root", "TERM=dumb"]
    debs = ["/packages/" + Path(p["filename"]).name for p in lock["packages"]]
    # Pre-extraction breaks bootstrap pre-dependency cycles. Final configure,
    # audit, exact dpkg state/version list are mandatory, without force flags.
    script = ("set -eu\n" + "dpkg --force-depends --unpack " + shlex.join(debs)
              + "\ndpkg --configure -a\n" + DPKG_AUDIT_CHECK + """useradd --uid 1000 --user-group --create-home --shell /bin/bash ideck
chmod 0700 /home/ideck
passwd --lock root
passwd --lock ideck
test -x /lib/ld-linux-aarch64.so.1
getconf GNU_LIBC_VERSION
dpkg-query -W '-f=${Package}\t${Version}\t${Architecture}\t${Status}\n'
""")
    with (output / "configure.log").open("w") as log:
        subprocess.run([str(a) for a in proot] + ["/bin/sh", "-ec", script],
                       check=True, env=env, cwd=output, stdout=log, stderr=subprocess.STDOUT, timeout=1200)
    query = run(proot + ["dpkg-query", "-W", "-f=${Package}\t${Version}\t${Architecture}\t${Status}\n"], env=env, cwd=output).stdout
    installed = {tuple(line.split("\t")[:3]): line.split("\t")[3] for line in query.splitlines()}
    expected = {(p["name"], p["version"], p["architecture"]) for p in lock["packages"]}
    if set(installed) != expected or set(installed.values()) != {"install ok installed"}:
        raise ValueError("configured package identity/status mismatch")
    (output / "package-manifest.tsv").write_text(query)
    elf_report = check_elf_closure(root)
    # PRoot binds are process-local; clear all placeholders before image creation.
    for directory in ("dev", "proc", "sys", "run", "tmp"):
        shutil.rmtree(root / directory)
        (root / directory).mkdir(mode=0o1777 if directory == "tmp" else 0o755)
    for name in ("host-rootfs", "packages"):
        placeholder = root / name
        if placeholder.exists():
            placeholder.chmod(0o700)
            shutil.rmtree(placeholder)
    policy.unlink()
    (root / "etc/hostname").write_text("ideck\n")
    (root / "etc/hosts").write_text("127.0.0.1 localhost ideck\n::1 localhost\n")
    (root / "etc/machine-id").write_text("")
    # No guest network/apt source is enabled by this offline milestone.
    (root / "etc/apt/sources.list").write_text("# iDeck offline rootfs; networking not configured.\n")
    (root / "etc/fstab").write_text("# Filesystems are mounted by the iDeck bootstrap supervisor.\n")
    canonical_guest_modes(root)
    (root / "var/log/dpkg.log").unlink(missing_ok=True)
    for path in (root / "var/cache/ldconfig").glob("*"):
        path.unlink()
    group_ids = {line.split(":")[0]: int(line.split(":")[2]) for line in (root / "etc/group").read_text().splitlines()}
    for path in ("etc/shadow", "etc/gshadow", "etc/shadow-", "etc/gshadow-"):
        ownership[path] = [0, group_ids["shadow"]]
    for path in ("var/log/btmp", "var/log/wtmp", "var/log/lastlog"):
        ownership[path] = [0, group_ids["utmp"]]
    ownership["var/mail"] = [0, group_ids["mail"]]
    # APT creates/repairs these sandbox directories when first used. Set them
    # explicitly now so the offline seed is ready for a later reviewed network gate.
    uid_map = {l.split(":")[0]: int(l.split(":")[2]) for l in (root / "etc/passwd").read_text().splitlines()}
    for path in ("var/cache/apt/archives/partial", "var/lib/apt/lists/partial", "var/lib/apt/mirrors/partial"):
        ownership[path] = [uid_map["_apt"], group_ids["root"]]
        (root / path).chmod(0o700)
    override = root / "var/lib/dpkg/statoverride"
    if override.exists():
        for line in override.read_text().splitlines():
            user, group, mode, path = line.split(" ", 3)
            ownership[normalized_member(path)] = [int(user) if user.isdigit() else uid_map[user],
                                                 int(group) if group.isdigit() else group_ids[group]]
            rooted_path(root, path).chmod(int(mode, 8))
    epoch = int(email.utils.parsedate_to_datetime(lock["release"]["date"]).timestamp())
    canonical_seed_content(root, epoch)
    # Final inode timestamps are pinned again after mke2fs, since host ctime
    # cannot be set here and file/directory reads can change source atime.
    all_paths = [root]
    for directory, names, files in os.walk(root):
        all_paths += [Path(directory) / name for name in sorted(names + files)]
    all_paths.sort(key=lambda path: str(path.relative_to(root)))
    for path in all_paths:
        os.utime(path, (epoch, epoch), follow_symlinks=False)
    ownership_manifest = {}
    for path in all_paths:
        relative = str(path.relative_to(root))
        pair = [1000, 1000] if relative == "home/ideck" or relative.startswith("home/ideck/") else ownership.get(relative, [0, 0])
        ownership_manifest[relative] = pair
    (output / "ownership.json").write_text(json.dumps(ownership_manifest, sort_keys=True) + "\n")
    config = output / "mke2fs.conf"
    config.write_text("[defaults]\nblocksize = 4096\ninode_size = 256\n")
    env.update(MKE2FS_CONFIG=str(config), E2FSPROGS_FAKE_TIME=str(epoch))
    raw = output / "rootfs-v1.raw"
    with raw.open("xb") as f:
        f.truncate(lock["image"]["size_bytes"])
    run([host / "usr/sbin/mke2fs", "-q", "-F", "-t", "ext4", "-b", "4096", "-I", "256",
         "-O", FEATURE_NAMES, "-E", "hash_seed=" + IMAGE_UUID + ",lazy_itable_init=0,lazy_journal_init=0,root_owner=0:0",
         "-e", "remount-ro", "-m", "0", "-U", IMAGE_UUID, "-L", "ideck-root-v1", "-d", root, raw], env=env)
    commands = inode_publication_commands(ownership_manifest, epoch)
    command_file = output / "ownership.debugfs"
    command_file.write_text("\n".join(commands) + "\n")
    result = run([host / "usr/sbin/debugfs", "-w", "-f", command_file, raw], env=env)
    if any(token in result.stderr for token in ("not found", "Usage:", "File not found", "Command not found")):
        raise ValueError("ext4 ownership publication failed")
    ownership_checked = verify_image_ownership(host, env, raw, ownership_manifest, output, root, expected_epoch=epoch)
    header = ext4_header(raw)
    expected_header = {k: lock["image"][k] for k in header}
    if header != expected_header:
        raise ValueError("ext4 feature/geometry mismatch")
    fsck = run([host / "usr/sbin/e2fsck", "-fn", raw], env=env)
    (output / "e2fsck.txt").write_text(fsck.stdout + fsck.stderr)
    stats = run([host / "usr/sbin/dumpe2fs", "-h", raw], env=env).stdout
    (output / "dumpe2fs.txt").write_text(stats)
    minimum = run([host / "usr/sbin/resize2fs", "-P", raw], env=env)
    (output / "minimum-estimate.txt").write_text(minimum.stdout + minimum.stderr)
    fields = dict(line.split(":", 1) for line in stats.splitlines() if ":" in line)
    blocks, free, block_size = (int(fields[key]) for key in ("Block count", "Free blocks", "Block size"))
    match = re.search(r"Estimated minimum size of the filesystem: (\d+)", minimum.stdout + minimum.stderr)
    if not match or not 0 < free < blocks or block_size != 4096:
        raise ValueError("incomplete filesystem sizing report")
    for path, uid, gid, mode in [("/", 0, 0, "0755"), ("/home/ideck", 1000, 1000, "0700"),
                                ("/etc/shadow", 0, group_ids["shadow"], "0640")]:
        info = run([host / "usr/sbin/debugfs", "-R", "stat " + debugfs_quote(path), raw], env=env).stdout
        if not re.search(rf"User:\s+{uid}\s+Group:\s+{gid}\b", info) or "Mode:  " + mode not in info:
            raise ValueError("persisted ext4 uid/gid/mode mismatch: " + path)
    compressed = output / "rootfs-v1.raw.gz"
    with raw.open("rb") as src, compressed.open("xb") as dst, gzip.GzipFile(filename="", mode="wb", fileobj=dst, mtime=0) as gz:
        shutil.copyfileobj(src, gz, 1024 * 1024)
    if sha256(builder_source) != builder_digest:
        raise ValueError("builder source changed during execution; no accepted profile/receipt")
    profile = {"schema": 1, "mode": "desktop-rootfs", "filesystem": "ext4",
               "rootfs": {"file": raw.name, "size": raw.stat().st_size, "sha256": sha256(raw)},
               "image": {k: lock["image"][k] for k in ("size_bytes", "uuid", "block_size", "features")}}
    (output / "desktop-rootfs-profile.json").write_text(json.dumps(profile, indent=2) + "\n")
    receipt = {"schema": 1, "lock_sha256": None,
               "builder_source_sha256": builder_digest,
               "end_to_end_replay_of_final_source": True,
               "network_mode": "verified cache only" if OFFLINE else "verified HTTPS inputs",
               "network_namespace_isolation": "not provided; offline restricts builder fetches",
               "keyring_sha256": sha256(keyring),
               "qemu_user_sha256": qemu_digest, "compat_source_sha256": sha256(compat_source),
               "compat_executable_sha256": sha256(compat),
               "host_tools": lock["host_tools"],
               "package_count": len(installed), "configured_package_audit": "pass", "glibc_execution": "pass",
               "elf_closure": elf_report, "persisted_ownership_inodes_checked": ownership_checked,
               "package_manifest_sha256": sha256(output / "package-manifest.tsv"),
               "ownership_manifest_sha256": sha256(output / "ownership.json"),
               "filesystem_bytes": {"allocated_blocks_bytes": (blocks - free) * block_size,
                                    "free_blocks_bytes": free * block_size,
                                    "minimum_estimate_bytes": int(match[1]) * block_size,
                                    "minimum_is_estimate_only": True},
               "directory_hash_seed": IMAGE_UUID,
               "canonical_seed_epoch": epoch,
               "canonical_inode_timestamps": "all manifest atime/mtime/ctime/crtime and nanoseconds audited",
               "canonical_seed_content": "generated alternatives installation log cleared; all locked seed account last-change days pinned",
               "image": profile, "compressed": {"size": compressed.stat().st_size, "sha256": sha256(compressed)},
               "filesystem_tool_check": "e2fsck -fn pass", "ownership_sample_check": "pass",
               "reproducibility": "signed exact inputs; canonical seed content/inode timestamps/hash seed; independent byte comparison required",
               "replay_requires_retained_authenticated_cache": True,
               "future_mirror_availability": "not guaranteed; snapshot endpoint blocked in this executor",
               "replay_freshness": "all replay rechecks release expiry and 90-day maximum age; repin afterwards",
               "guest_boot": "not tested", "vm_posix_persistence": "not tested", "legacy_userdata_accessed": False}
    (output / "build-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def main():
    global OFFLINE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["lock", "download", "build"])
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--keyring", type=Path, default=KEYRING)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--qemu", type=Path)
    parser.add_argument("--qemu-sha256")
    parser.add_argument("--offline", action="store_true", help="require exact verified cache; never fetch missing/invalid inputs")
    args = parser.parse_args()
    OFFLINE = args.offline
    if args.command == "lock" and OFFLINE:
        parser.error("offline mode requires an existing reviewed lock; cannot create a new lock")
    if args.command == "lock":
        lock = create_lock(args.cache / "metadata", args.lock, args.keyring)
        print(json.dumps(lock["totals"], sort_keys=True))
    elif args.command == "download":
        lock = json.loads(args.lock.read_text())
        paths = download(lock, args.cache, args.keyring)
        print(json.dumps({"verified_blobs": len(paths), **lock["totals"]}, sort_keys=True))
    else:
        if not all((args.output, args.qemu, args.qemu_sha256)):
            parser.error("build requires --output, --qemu, --qemu-sha256")
        lock = json.loads(args.lock.read_text())
        receipt = build(lock, args.cache.resolve(), args.output.resolve(), args.keyring,
                        args.qemu.resolve(), args.qemu_sha256)
        receipt["lock_sha256"] = sha256(args.lock)
        (args.output / "build-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
        print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
