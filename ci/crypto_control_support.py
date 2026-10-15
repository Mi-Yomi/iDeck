#!/usr/bin/env python3
"""One fresh source-only GMP/Nettle/GnuTLS control; never import target code.

This file is a local proposal, not evidence of a successful Apple build. It has
no network, package-install, SDK-copy, signing, conversion or runtime-stub path.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import time

MADEIRA_PIN = "279fd0f83170425db002fe25d6bd62f6355f497d"
HOST = "aarch64-apple-darwin"
JOBS = 4
PACKAGES = {
    "gmp": {"root": "gmp-6.3.0", "archive": "gmp-6.3.0.tar.xz",
            "sha256": "a3c2b80201b89e68616f4ad30bc66aee4927c3ce50e33929ca819d5c43538898",
            "members": 2343, "bytes": 16998222},
    "nettle": {"root": "nettle-3.10.1", "archive": "nettle-3.10.1.tar.gz",
               "sha256": "b0fcdd7fc0cdea6e80dcf1dd85ba794af0d5b4a57e26397eee3bc193272d9132",
               "members": 973, "bytes": 8055769},
    "gnutls": {"root": "gnutls-3.8.9", "archive": "gnutls-3.8.9.tar.xz",
               "sha256": "69e113d802d1670c4d5ac1b99040b1f2d5c7c05daec5003813c049b5184820ed",
               "members": 7245, "bytes": 62091244},
}
EXPECTED_PREFIX_FILES = ('include/gmp.h',
 'include/gnutls/abstract.h',
 'include/gnutls/compat.h',
 'include/gnutls/crypto.h',
 'include/gnutls/dtls.h',
 'include/gnutls/gnutls.h',
 'include/gnutls/ocsp.h',
 'include/gnutls/openpgp.h',
 'include/gnutls/pkcs11.h',
 'include/gnutls/pkcs12.h',
 'include/gnutls/pkcs7.h',
 'include/gnutls/self-test.h',
 'include/gnutls/socket.h',
 'include/gnutls/system-keys.h',
 'include/gnutls/tpm.h',
 'include/gnutls/urls.h',
 'include/gnutls/x509-ext.h',
 'include/gnutls/x509.h',
 'include/nettle/aes.h',
 'include/nettle/arcfour.h',
 'include/nettle/arctwo.h',
 'include/nettle/asn1.h',
 'include/nettle/balloon.h',
 'include/nettle/base16.h',
 'include/nettle/base64.h',
 'include/nettle/bignum.h',
 'include/nettle/blowfish.h',
 'include/nettle/buffer.h',
 'include/nettle/camellia.h',
 'include/nettle/cast128.h',
 'include/nettle/cbc.h',
 'include/nettle/ccm.h',
 'include/nettle/cfb.h',
 'include/nettle/chacha-poly1305.h',
 'include/nettle/chacha.h',
 'include/nettle/cmac.h',
 'include/nettle/ctr.h',
 'include/nettle/curve25519.h',
 'include/nettle/curve448.h',
 'include/nettle/des.h',
 'include/nettle/drbg-ctr.h',
 'include/nettle/dsa-compat.h',
 'include/nettle/dsa.h',
 'include/nettle/eax.h',
 'include/nettle/ecc-curve.h',
 'include/nettle/ecc.h',
 'include/nettle/ecdsa.h',
 'include/nettle/eddsa.h',
 'include/nettle/gcm.h',
 'include/nettle/gostdsa.h',
 'include/nettle/gosthash94.h',
 'include/nettle/hkdf.h',
 'include/nettle/hmac.h',
 'include/nettle/knuth-lfib.h',
 'include/nettle/macros.h',
 'include/nettle/md2.h',
 'include/nettle/md4.h',
 'include/nettle/md5-compat.h',
 'include/nettle/md5.h',
 'include/nettle/memops.h',
 'include/nettle/memxor.h',
 'include/nettle/nettle-meta.h',
 'include/nettle/nettle-types.h',
 'include/nettle/nist-keywrap.h',
 'include/nettle/ocb.h',
 'include/nettle/pbkdf2.h',
 'include/nettle/pgp.h',
 'include/nettle/pkcs1.h',
 'include/nettle/poly1305.h',
 'include/nettle/pss-mgf1.h',
 'include/nettle/pss.h',
 'include/nettle/realloc.h',
 'include/nettle/ripemd160.h',
 'include/nettle/rsa.h',
 'include/nettle/salsa20.h',
 'include/nettle/serpent.h',
 'include/nettle/sexp.h',
 'include/nettle/sha.h',
 'include/nettle/sha1.h',
 'include/nettle/sha2.h',
 'include/nettle/sha3.h',
 'include/nettle/siv-cmac.h',
 'include/nettle/siv-gcm.h',
 'include/nettle/sm3.h',
 'include/nettle/sm4.h',
 'include/nettle/streebog.h',
 'include/nettle/twofish.h',
 'include/nettle/umac.h',
 'include/nettle/version.h',
 'include/nettle/xts.h',
 'include/nettle/yarrow.h',
 'lib/libgmp.a',
 'lib/libgmp.la',
 'lib/libgnutls.a',
 'lib/libgnutls.la',
 'lib/libhogweed.a',
 'lib/libnettle.a',
 'lib/pkgconfig/gmp.pc',
 'lib/pkgconfig/gnutls.pc',
 'lib/pkgconfig/hogweed.pc',
 'lib/pkgconfig/nettle.pc')
NETTLE_ASM_LINKS = [{'class': 'asm_replace_list',
  'output_link': 'chacha-core-internal.asm',
  'sha256': 'b51dfcc94d4627fe4b27d0938415ac42084d18e33b72dddbcf4ffd0deebf3dcc',
  'source': 'arm64/chacha-core-internal.asm'},
 {'class': 'asm_replace_list',
  'output_link': 'machine.m4',
  'sha256': '623a5f6ae94cdb93a049d653be234097fb5e61738f57b33a9fff226ebcffe15b',
  'source': 'arm64/machine.m4'},
 {'class': 'asm_nettle_optional_list',
  'output_link': 'aes128-encrypt-2.asm',
  'sha256': '747ad3b2edc518bfb5a8a528b5001a25f0dc8b4d06f6b2fd695424585ac0ddab',
  'source': 'arm64/fat/aes128-encrypt-2.asm'},
 {'class': 'asm_nettle_optional_list',
  'output_link': 'aes128-decrypt-2.asm',
  'sha256': '3116fa97a63538e5c9b1caf6901184e6415c3d9db76f5d00ec19c75e8381d9c5',
  'source': 'arm64/fat/aes128-decrypt-2.asm'},
 {'class': 'asm_nettle_optional_list',
  'output_link': 'aes192-encrypt-2.asm',
  'sha256': '273fd928f790989fe3a079cb72d89c94e55ae382575425db7e6d9aba49b68377',
  'source': 'arm64/fat/aes192-encrypt-2.asm'},
 {'class': 'asm_nettle_optional_list',
  'output_link': 'aes192-decrypt-2.asm',
  'sha256': '6a311598f42a1de3c3fa3b92b7fae8897bce10eba30d132e20e905806396c18c',
  'source': 'arm64/fat/aes192-decrypt-2.asm'},
 {'class': 'asm_nettle_optional_list',
  'output_link': 'aes256-encrypt-2.asm',
  'sha256': '9f1d32fc325cdab61d3e77ffc525c49239286df556122a067cd7378990e1394a',
  'source': 'arm64/fat/aes256-encrypt-2.asm'},
 {'class': 'asm_nettle_optional_list',
  'output_link': 'aes256-decrypt-2.asm',
  'sha256': '350bf4e3cb64f31ccf45ff7868bb48b226a9b0ae93da2fa8260d3ae6f184f09c',
  'source': 'arm64/fat/aes256-decrypt-2.asm'},
 {'class': 'asm_nettle_optional_list',
  'output_link': 'chacha-2core.asm',
  'sha256': '47c28b0db0ba270a0c2a6ef38b565f247618a75ed956e05fb2844227e5c2b2ce',
  'source': 'arm64/chacha-2core.asm'},
 {'class': 'asm_nettle_optional_list',
  'output_link': 'chacha-4core.asm',
  'sha256': '45574e6349a05ab0e7730cfadf3ad55490230f354ce982eb73168ef23bf466f8',
  'source': 'arm64/chacha-4core.asm'},
 {'class': 'asm_nettle_optional_list',
  'output_link': 'ghash-set-key-2.asm',
  'sha256': '07706facd116068e5caa90a421c8e8c12ef9d2edb9e933212fb19ef4bc32936b',
  'source': 'arm64/fat/ghash-set-key-2.asm'},
 {'class': 'asm_nettle_optional_list',
  'output_link': 'ghash-update-2.asm',
  'sha256': '560161aaf330331720f3a57e9e66e795d3110225a4c8ab0a995cae0392471ac1',
  'source': 'arm64/fat/ghash-update-2.asm'},
 {'class': 'asm_nettle_optional_list',
  'output_link': 'sha1-compress-2.asm',
  'sha256': '7f1d823a88e315ddb1fd01600eceec5359aeae9984b0a33ce1ae5d340463e69a',
  'source': 'arm64/fat/sha1-compress-2.asm'},
 {'class': 'asm_nettle_optional_list',
  'output_link': 'sha256-compress-n-2.asm',
  'sha256': 'c8e2be78ef01c5690b1e7c980845265d501f81b8247429f3cf332cf22c8b692a',
  'source': 'arm64/fat/sha256-compress-n-2.asm'}]
NETTLE_ECC_HEADERS = ('ecc-secp192r1.h',
 'ecc-secp224r1.h',
 'ecc-secp256r1.h',
 'ecc-secp384r1.h',
 'ecc-secp521r1.h',
 'ecc-curve25519.h',
 'ecc-curve448.h',
 'ecc-gost-gc256b.h',
 'ecc-gost-gc512a.h')
SYSTEM_PATH = "/usr/bin:/bin:/usr/sbin:/sbin"
TARGET_LIBS = ("libgmp.a", "libnettle.a", "libhogweed.a", "libgnutls.a")


class ContractError(Exception):
    pass


class CommandFailure(Exception):
    def __init__(self, step: str, status: int):
        self.step, self.status = step, status if status >= 0 else 128 - status
        super().__init__(f"{step} failed with exit status {self.status}")


def require(condition, message):
    if not condition:
        raise ContractError(str(message))


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(data)
    return h.hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def fresh_output(source_arg, build_arg):
    """Validate every lexical ancestor before creating any output."""
    source = Path(source_arg).absolute()
    build = Path(build_arg).absolute()
    require(".." not in source.parts and ".." not in build.parts, "No parent traversal in roots")
    require(source.is_dir() and source.resolve() == source, "Source root must be a real canonical directory")
    require(re.fullmatch(r"[A-Za-z0-9_./+-]+", str(source)), "Source root contains unsupported shell/make path characters")
    require(re.fullmatch(r"[A-Za-z0-9_./+-]+", str(build)), "Build root contains unsupported shell/make path characters")
    require(build.is_relative_to(source / ".work") and build != source / ".work", "Build root must be below SOURCE_ROOT/.work")
    cursor = source
    for part in build.relative_to(source).parts:
        cursor /= part
        require(not cursor.is_symlink(), f"Symlink output ancestor: {cursor}")
        require(not cursor.exists() or cursor.is_dir(), f"Non-directory output ancestor: {cursor}")
    require(not build.exists(), "Fresh, nonexistent build root required; no reuse or stage markers")
    return source, build


def validate_tar(members, expected_root, count_limit, byte_limit):
    require(len(members) <= count_limit, "Archive member count exceeds bound")
    require(sum(m.size for m in members) <= byte_limit, "Archive size exceeds bound")
    seen, folded, files = set(), set(), set()
    for m in members:
        name = m.name
        p = PurePosixPath(name)
        require(name and not name.startswith("/") and "\\" not in name and not any(ord(c) < 32 or ord(c) == 127 for c in name), f"Unsafe archive name: {name!r}")
        require(p.as_posix() == name.rstrip("/") and all(v not in ("", ".", "..") for v in name.rstrip("/").split("/")), f"Noncanonical archive name: {name!r}")
        require(p.parts[0] == expected_root, f"Unexpected archive root: {name}")
        require(m.isfile() or m.isdir(), f"Archive links/special files forbidden: {name}")
        require(m.size >= 0 and (m.isfile() or m.size == 0), f"Invalid member size: {name}")
        require(p.as_posix() not in seen and p.as_posix().casefold() not in folded, f"Duplicate/case-colliding archive member: {name}")
        seen.add(p.as_posix()); folded.add(p.as_posix().casefold())
        if m.isfile():
            files.add(p.as_posix())
    for name in seen:
        require(not any(parent.as_posix() in files for parent in PurePosixPath(name).parents), f"Archive file used as parent: {name}")
    require(expected_root in seen and any(m.name.rstrip("/") == expected_root and m.isdir() for m in members), "Archive top-level directory missing")


def safe_extract(archive, destination, spec):
    """Verify all metadata before writing; never use extract/extractall."""
    require(digest(archive) == spec["sha256"], f"Archive SHA256 mismatch: {archive}")
    destination = Path(destination)
    require(destination.is_dir() and not destination.is_symlink() and destination.resolve() == destination, "Real canonical extraction destination required")
    require(not (destination / spec["root"]).exists() and not (destination / spec["root"]).is_symlink(), "Fresh extracted source required")
    with tarfile.open(archive, mode="r:*") as tf:
        members = tf.getmembers()
        validate_tar(members, spec["root"], spec["members"], spec["bytes"])
        require(len(members) == spec["members"] and sum(m.size for m in members) == spec["bytes"], "Pinned archive metadata drift")
        directories = []
        manifest = []
        for m in members:
            out = destination / m.name
            if m.isdir():
                out.mkdir(parents=True, exist_ok=True, mode=0o755)
                directories.append((out, m.mtime))
                continue
            out.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
            stream = tf.extractfile(m)
            require(stream is not None, f"Unreadable member: {m.name}")
            with stream, out.open("xb") as target:
                shutil.copyfileobj(stream, target)
            require(out.stat().st_size == m.size, f"Truncated member: {m.name}")
            # Release archives mark scripts executable; a GnuTLS x86 license
            # text also has stray executable bits. Only shebang scripts retain
            # executable permission; never preserve setuid/setgid/sticky bits.
            with out.open("rb") as header:
                shebang = header.read(2) == b"#!"
            out.chmod(0o755 if m.mode & 0o111 and shebang else 0o644)
            os.utime(out, (m.mtime, m.mtime))
            manifest.append({"path": m.name, "sha256": digest(out), "size": m.size,
                             "archived_mtime": m.mtime, "archived_mode": oct(m.mode), "effective_mode": oct(out.stat().st_mode & 0o7777)})
        for out, mtime in reversed(directories):
            os.utime(out, (mtime, mtime))
    return manifest


def base_environment(build, developer_dir=None):
    # An allowlist is stronger than unsetting a few known variables. It drops
    # CPATH/*FLAGS/LIBRARY_PATH, make flags, config caches, SDK overrides,
    # compiler launchers, pkg-config defaults, DYLD/LD injection and shell hooks.
    env = {"PATH": SYSTEM_PATH, "HOME": str(build / "home"), "TMPDIR": str(build / "tmp"),
           "LC_ALL": "C", "LANG": "C", "TZ": "UTC", "SHELL": "/bin/bash",
           "CONFIG_SHELL": "/bin/bash", "CONFIG_SITE": "/dev/null"}
    if developer_dir:
        env["DEVELOPER_DIR"] = str(developer_dir)
    return env


def validate_version(name, output):
    first = output.splitlines()[0] if output.splitlines() else ""
    checks = {
        "xcode": "Xcode 26.6" in output.splitlines(),
        "sdk": output.strip() == "26.5",
        "python": first == "Python 3.12.7",
        "make": first == "GNU Make 3.81",
        "clang": first.startswith("Apple clang version "),
        "m4": bool(output.strip()),
        "pkg-config": bool(re.fullmatch(r"[0-9]+(?:\.[0-9]+)+(?:[-+].*)?", output.strip())),
    }
    require(checks[name], f"Unreviewed {name} version output:\n{output}")


class Control:
    def __init__(self, source, build, pkg_config):
        self.source, self.build = source, build
        self.logs = build / "logs"
        self.prefix = build / "prefix"
        self.pkg_config = pkg_config
        self.requested_developer = os.environ.get("DEVELOPER_DIR", "")
        self.env = base_environment(build, self.requested_developer)
        self.commands = []
        self.tools = {}

    def run(self, name, command, cwd=None, env=None, capture=False):
        """No output pipes; failure retains actual tool status and full log."""
        path = self.logs / (name + ".log")
        record = {"step": name, "argv": [str(v) for v in command], "cwd": str(cwd or self.build), "log": str(path.relative_to(self.build))}
        start = time.monotonic()
        print(f"=== {name} ===", flush=True)
        with path.open("wb") as stream:
            proc = subprocess.run(record["argv"], cwd=cwd or self.build, env=env or self.env,
                                  stdout=stream, stderr=subprocess.STDOUT, check=False)
        record.update(exit_code=proc.returncode, seconds=round(time.monotonic() - start, 3))
        self.commands.append(record)
        write_json(self.build / "commands.json", self.commands)
        if proc.returncode:
            print(path.read_text(errors="replace")[-16000:], file=sys.stderr)
            raise CommandFailure(name, proc.returncode)
        return path.read_text(errors="replace") if capture else None

    def capture(self, name, command):
        return self.run(name, command, capture=True).strip()

    def tool(self, name, sdk="iphoneos"):
        value = self.capture("find-" + name, ["/usr/bin/xcrun", "--sdk", sdk, "--find", name])
        require(Path(value).is_file() and os.access(value, os.X_OK), f"Missing selected Apple tool: {value}")
        self.tools[name] = value
        return value

    def preflight(self):
        require(sys.version_info[:3] == (3, 12, 7), "Python 3.12.7 required")
        require(sys.platform == "darwin", "arm64 macOS required")
        require(self.capture("host-arch", ["/usr/bin/uname", "-m"]) == "arm64", "arm64 macOS required")
        brand = self.capture("host-cpu", ["/usr/sbin/sysctl", "-n", "machdep.cpu.brand_string"])
        require(brand in ("Apple M2", "Apple M2 (Virtual)"), f"Unreviewed runner CPU: {brand}")
        require(self.capture("madeira-pin", ["/usr/bin/git", "-C", str(self.source), "rev-parse", "HEAD"]) == MADEIRA_PIN, "Wrong Madeira pin")
        self.run("tracked-source-clean", ["/usr/bin/git", "-C", str(self.source), "diff", "--exit-code", "HEAD", "--", "build/gnutls-ios"])
        # Codemagic selects its requested Xcode through DEVELOPER_DIR; the
        # system xcode-select default may be a different installed version.
        developer = self.requested_developer or self.capture("developer-dir", ["/usr/bin/xcode-select", "-p"])
        developer_path = Path(developer)
        require(developer_path.is_absolute() and ".." not in developer_path.parts and developer_path.is_dir(), "Selected Developer directory is invalid")
        developer_path = developer_path.resolve()
        require(developer_path.parts[-2:] == ("Contents", "Developer"), "Full Xcode Developer directory required")
        self.env = base_environment(self.build, developer_path)
        write_json(self.build / "developer-selection.json", {"source": "inherited provider DEVELOPER_DIR" if self.requested_developer else "xcode-select default", "path": str(developer_path)})
        for name, command in [("xcode", ["/usr/bin/xcodebuild", "-version"]),
                              ("sdk", ["/usr/bin/xcrun", "--sdk", "iphoneos", "--show-sdk-version"]),
                              ("python", [sys.executable, "-I", "--version"])]:
            validate_version(name, self.capture(name + "-version", command))
        self.sdk = self.capture("iphoneos-sdk-path", ["/usr/bin/xcrun", "--sdk", "iphoneos", "--show-sdk-path"])
        self.host_sdk = self.capture("macosx-sdk-path", ["/usr/bin/xcrun", "--sdk", "macosx", "--show-sdk-path"])
        for sdk in (self.sdk, self.host_sdk):
            require(Path(sdk).is_dir(), f"Missing SDK: {sdk}")
        for name in ("clang", "clang++", "ar", "ranlib", "strip", "nm", "ld", "lipo", "otool", "make"):
            self.tool(name)
        for name in ("clang", "make"):
            validate_version(name, self.capture(name + "-version", [self.tools[name], "--version"]))
        for name in ("m4", "perl", "awk", "sed", "grep", "install", "file"):
            path = Path("/usr/bin") / name
            require(path.is_file() and os.access(path, os.X_OK), f"Missing existing system tool: {path}; no install allowed")
            self.tools[name] = str(path)
        validate_version("m4", self.capture("m4-version", [self.tools["m4"], "--version"]))
        probe = self.build / "m4-probe.m4"
        probe.write_text("define(`CRYPTO_CONTROL_PROBE', `m4-capability-ok')CRYPTO_CONTROL_PROBE\n")
        require(self.capture("m4-capability", [self.tools["m4"], str(probe)]) == "m4-capability-ok", "m4 expansion failed")
        self.capture("perl-version", [self.tools["perl"], "-v"])
        require(self.pkg_config and Path(self.pkg_config).is_file() and os.access(self.pkg_config, os.X_OK), "Existing pkg-config required by GnuTLS configure; no install allowed")
        self.pkg_config = str(Path(self.pkg_config).resolve())
        self.tools["pkg-config"] = self.pkg_config
        validate_version("pkg-config", self.capture("pkg-config-version", [self.pkg_config, "--version"]))
        self.run("pkg-config-minimum", [self.pkg_config, "--atleast-pkgconfig-version=0.9.0"])
        self.capture("host-os", ["/usr/bin/sw_vers"])
        self.capture("disk-space", ["/bin/df", "-h", str(self.build)])
        self.check_sources()
        self.configure_environment()
        write_json(self.build / "preflight.json", {"status": "passed", "tools": self.tools,
                   "jobs": JOBS, "madeira_commit": MADEIRA_PIN, "sdk": self.sdk,
                   "macosx_sdk": self.host_sdk, "environment": self.env,
                   "package_install_performed": False, "target_binaries_run": False})

    def check_sources(self):
        src = self.source / "build/gnutls-ios/src"
        sums = src / "SHA256SUMS"
        require(sums.is_file() and not sums.is_symlink(), "Missing real tracked SHA256SUMS")
        rows = {}
        for line in sums.read_text().splitlines():
            match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9.-]+)", line)
            require(match, "Malformed SHA256SUMS")
            require(match[2] not in rows, "Duplicate SHA256SUMS row")
            rows[match[2]] = match[1]
        require(rows == {v["archive"]: v["sha256"] for v in PACKAGES.values()}, "Tracked hash list differs from reviewed lock")
        for spec in PACKAGES.values():
            archive = src / spec["archive"]
            require(archive.is_file() and not archive.is_symlink() and archive.resolve().is_relative_to(self.source), "Unsafe source archive")
            require(digest(archive) == spec["sha256"], f"Source SHA256 mismatch: {archive.name}")
        write_json(self.build / "source-lock.json", {"madeira_commit": MADEIRA_PIN, "packages": PACKAGES,
                   "upstream_recipe_sha256": digest(self.source / "build/gnutls-ios/build.sh"),
                   "sha256sums_sha256": digest(sums)})

    def configure_environment(self):
        target = shlex.join([self.tools["clang"], "-arch", "arm64", "-isysroot", self.sdk, "-miphoneos-version-min=17.0"])
        host_cc = shlex.join([self.tools["clang"], "-arch", "arm64", "-isysroot", self.host_sdk])
        self.env.update(CC=target, CXX=shlex.join([self.tools["clang++"], "-arch", "arm64", "-isysroot", self.sdk, "-miphoneos-version-min=17.0"]),
                        CFLAGS="-O2", CXXFLAGS="-O2", CPPFLAGS="", LDFLAGS="-Wl,-no_adhoc_codesign", LIBS="",
                        CC_FOR_BUILD=host_cc, CFLAGS_FOR_BUILD="-O2", CPPFLAGS_FOR_BUILD="", LDFLAGS_FOR_BUILD="",
                        AR=self.tools["ar"], RANLIB=self.tools["ranlib"], STRIP=self.tools["strip"], NM=self.tools["nm"], LD=self.tools["ld"],
                        MAKE=self.tools["make"], M4=self.tools["m4"], PERL=self.tools["perl"],
                        PKG_CONFIG=self.pkg_config, PKG_CONFIG_PATH=str(self.prefix / "lib/pkgconfig"),
                        PKG_CONFIG_LIBDIR=str(self.prefix / "lib/pkgconfig"), PKG_CONFIG_SYSROOT_DIR="",
                        # Release archives already contain configure/Makefile.in;
                        # an unexpected regeneration must fail, never install tools.
                        ACLOCAL="/usr/bin/false", AUTOCONF="/usr/bin/false", AUTOHEADER="/usr/bin/false",
                        AUTOMAKE="/usr/bin/false", MAKEINFO="/usr/bin/false")

    def prepare_source(self, package):
        spec = PACKAGES[package]
        manifest = safe_extract(self.source / "build/gnutls-ios/src" / spec["archive"], self.build / "src", spec)
        write_json(self.build / "manifests" / (package + "-source.json"), manifest)
        src = self.build / "src" / spec["root"]
        obj = self.build / "build" / package
        obj.mkdir()
        return src, obj

    def configure(self, package, source, obj, flags, extra_env=None):
        guesses = [source / "config.guess", source / "build-aux/config.guess"]
        guess = next((p for p in guesses if p.is_file()), None)
        require(guess is not None, f"No release config.guess for {package}")
        build = self.run(package + "-config-guess", ["/bin/bash", str(guess)], cwd=obj, capture=True).strip()
        require(re.fullmatch(r"[A-Za-z0-9_.+-]+", build) and build != HOST, "Distinct explicit build alias required to force cross-compilation")
        env = dict(self.env); env.update(extra_env or {})
        output = self.run(package + "-configure", ["/bin/bash", str(source / "configure"), "--build=" + build,
                 "--host=" + HOST, "--prefix=" + str(self.prefix), *flags], cwd=obj, env=env, capture=True)
        require("checking whether we are cross compiling... yes" in output, f"{package} did not confirm cross-compilation")
        return env

    def make(self, package, obj, *targets, env=None):
        self.run(package + "-" + "-".join(t.replace("/", "_") for t in targets),
                 [self.tools["make"], "-j4", *targets], cwd=obj, env=env)

    def build_stack(self):
        src, obj = self.prepare_source("gmp")
        self.configure("gmp", src, obj, ["--enable-static", "--disable-shared", "--disable-assembly", "--with-pic"])
        # Explicit generated-source and library targets avoid docs, CLI and tests.
        # Never use command-line SUBDIRS=, which leaks to recursive MAKEFLAGS.
        self.make("gmp-generated", obj, "gmp.h", "fac_table.h", "sieve_table.h", "fib_table.h",
                  "mpn/fib_table.c", "mp_bases.h", "mpn/mp_bases.c", "trialdivtab.h", "mpn/jacobitab.h", "mpn/perfsqr.h", "config.h")
        for subdir in ("mpn", "mpz", "mpq", "mpf", "printf", "scanf", "rand"):
            self.make("gmp-" + subdir, obj / subdir, "all")
        self.make("gmp-library", obj, "libgmp.la")
        self.make("gmp-install", obj, "install-libLTLIBRARIES", "install-nodist_includeexecHEADERS", "install-pkgconfigDATA")
        require((self.prefix / "lib/libgmp.a").is_file() and (self.prefix / "include/gmp.h").is_file(), "Incomplete GMP prefix")

        src, obj = self.prepare_source("nettle")
        self.configure("nettle", src, obj, ["--enable-static", "--disable-shared", "--disable-documentation",
                       "--with-include-path=" + str(self.prefix / "include"), "--with-lib-path=" + str(self.prefix / "lib")])
        # Keep upstream's real arm64/fat assembly. Missing assembly is a failure,
        # never a silent portable-code feature reduction to get a green control.
        cfg = (obj / "config.log").read_text(errors="replace")
        require(re.search(r"Assembly files:\s+arm64/fat arm64(?:\s|$)", cfg), "Nettle arm64/fat assembly was not preserved")
        makefile = (obj / "Makefile").read_text(errors="replace")
        require(re.search(r"^OPT_NETTLE_SOURCES\s*=.*fat-arm64\.c", makefile, re.MULTILINE), "Nettle fat-arm64.c source is required")
        require(re.search(r"^FAT_TEST_LIST\s*=\s*none aes pmull sha1 sha2\s*$", makefile, re.MULTILINE), "Nettle arm64 fat feature set drift")
        m4_config = (obj / "config.m4").read_text(errors="replace")
        for selector in ("define(`SYMBOL_PREFIX', `_'`$1')", "define(`ELF_STYLE', `no')",
                         "define(`COFF_STYLE', `no')", "define(`RODATA', `.section __TEXT,__const')",
                         "define(`ALIGN_LOG', `yes')"):
            require(selector in m4_config, f"Nettle Apple assembly selector missing: {selector}")
        for row in NETTLE_ASM_LINKS:
            linked = obj / row["output_link"]
            expected = src / row["source"]
            require(linked.is_file() and linked.resolve() == expected.resolve() and digest(linked) == row["sha256"], f"Nettle assembly selection drift: {row['output_link']}")
        self.make("nettle-libraries", obj, "libnettle.a", "libhogweed.a")
        for name in NETTLE_ECC_HEADERS:
            require((obj / name).is_file() and (obj / name).stat().st_size, f"Missing native-generated ECC table: {name}")
        self.make("nettle-install", obj, "install-static", "install-headers", "install-pkgconfig")
        require((self.prefix / "lib/libnettle.a").is_file() and (self.prefix / "lib/libhogweed.a").is_file(), "Incomplete Nettle prefix")

        src, obj = self.prepare_source("gnutls")
        extra = {name + "_CFLAGS": "-I" + str(self.prefix / "include") for name in ("NETTLE", "HOGWEED", "GMP")}
        extra.update(NETTLE_LIBS="-L" + str(self.prefix / "lib") + " -lnettle",
                     HOGWEED_LIBS="-L" + str(self.prefix / "lib") + " -lhogweed -lgmp",
                     GMP_LIBS="-L" + str(self.prefix / "lib") + " -lgmp")
        env = self.configure("gnutls", src, obj, ["--enable-static", "--disable-shared",
                "--with-included-libtasn1", "--with-included-unistring", "--without-p11-kit",
                "--without-tpm", "--without-tpm2", "--without-idn", "--without-brotli", "--without-zstd",
                "--disable-doc", "--disable-tests", "--disable-tools", "--disable-cxx",
                "--disable-libdane", "--disable-nls", "--disable-guile", "--with-nettle-mini=no"], extra)
        config_h = (obj / "config.h").read_text(errors="replace")
        require(not re.search(r"^\s*#\s*define\s+ENABLE_FIPS140(?:\s|$)", config_h, re.MULTILINE), "GnuTLS FIPS140 must remain disabled")
        libmake = (obj / "lib/Makefile").read_text(errors="replace")
        require(re.search(r"^all-local:\s*$", libmake, re.MULTILINE), "GnuTLS FIPS140 all-local must be disabled")
        require(not re.search(r"^noinst_PROGRAMS\s*=.*fipshmac", libmake, re.MULTILINE), "FIPS140 target executable is forbidden")
        archmake = (obj / "lib/accelerated/aarch64/Makefile").read_text(errors="replace")
        require(re.search(r"^am__append_2\s*=\s*macosx/sha1-armv8\.s", archmake, re.MULTILINE), "GnuTLS must select real Darwin arm64 assembly")
        require(not re.search(r"^am__append_3\s*=\s*elf/", archmake, re.MULTILINE), "GnuTLS incorrectly selected ELF assembly")
        self.make("gnutls-gl", obj / "gl", "all", env=env)
        self.make("gnutls-lib", obj / "lib", "all", env=env)
        self.make("gnutls-install", obj / "lib", "install-libLTLIBRARIES", "install-pkgconfigDATA", env=env)
        self.make("gnutls-headers", obj / "lib/includes", "install-nobase_includeHEADERS", "install-nobase_nodist_includeHEADERS", env=env)

    def audit(self):
        libraries = []
        for name in TARGET_LIBS:
            path = self.prefix / "lib" / name
            require(path.is_file() and not path.is_symlink() and path.stat().st_size > 8, f"Missing real target archive: {name}")
            members = self.capture(name + "-members", [self.tools["ar"], "-t", str(path)]).splitlines()
            members = [m for m in members if m not in ("__.SYMDEF", "__.SYMDEF SORTED", "__.SYMDEF_64", "__.SYMDEF_64 SORTED")]
            require(members and all(m.endswith(".o") for m in members), f"Unexpected archive members: {name}")
            require(self.capture(name + "-architecture", [self.tools["lipo"], "-archs", str(path)]) == "arm64", f"Wrong target archive architecture: {name}")
            load = self.capture(name + "-load-commands", [self.tools["otool"], "-l", str(path)])
            validate_ios_load_commands(load, len(members), name)
            self.run(name + "-symbols", [self.tools["nm"], "-g", str(path)])
            libraries.append({"path": str(path.relative_to(self.build)), "sha256": digest(path), "size": path.stat().st_size, "member_count": len(members)})
        generated = []
        for package, names in {"gmp": ["gen-fac", "gen-sieve", "gen-fib", "gen-bases", "gen-trialdivtab", "gen-jacobitab", "gen-psqr"], "nettle": ["eccdata"]}.items():
            for name in names:
                path = self.build / "build" / package / name
                require(path.is_file() and not path.is_symlink(), f"Missing native source-built generator: {package}/{name}")
                kind = self.capture(package + "-" + name + "-file", [self.tools["file"], str(path)])
                require("Mach-O 64-bit executable arm64" in kind, f"Unexpected native generator kind: {kind}")
                load = self.capture(package + "-" + name + "-load-commands", [self.tools["otool"], "-l", str(path)])
                require("LC_VERSION_MIN_MACOSX" in load or re.search(r"^\s*platform\s+(?:MACOS|1)\s*$", load, re.MULTILINE), f"Native generator is not macOS: {package}/{name}")
                require(not re.search(r"^\s*platform\s+(?:IOS|2)\s*$", load, re.MULTILINE), "iOS target executable may not be treated as host generator")
                generated.append({"path": str(path.relative_to(self.build)), "sha256": digest(path), "size": path.stat().st_size,
                                  "purpose": "native macOS source-table generator", "compiler": self.env["CC_FOR_BUILD"]})
        files = []
        for path in sorted(self.prefix.rglob("*")):
            require(not path.is_symlink(), f"Prefix symlink is not an exportable file: {path}")
            require(path.is_file() or path.is_dir(), f"Prefix special file is forbidden: {path}")
            if path.is_file():
                require(path.suffix not in (".dylib", ".so"), "Unexpected shared target library")
                files.append({"path": str(path.relative_to(self.prefix)), "sha256": digest(path), "size": path.stat().st_size})
        require(sorted(f["path"] for f in files) == list(EXPECTED_PREFIX_FILES), "Installed prefix differs from exact reviewed libraries/headers/pkgconfig/libtool metadata closure")
        headers = [f for f in files if f["path"].startswith("include/")]
        require(len(headers) == 91, "Expected exactly 1 GMP + 73 Nettle + 17 GnuTLS public headers")
        require(len([f for f in headers if f["path"].startswith("include/nettle/")]) == 73, "Unexpected Nettle public header count")
        require(any(f["path"] == "include/gmp.h" for f in headers), "GMP public header missing")
        require(any(f["path"] == "include/nettle/nettle-meta.h" for f in headers), "Nettle public headers missing")
        require(len([f for f in headers if f["path"].startswith("include/gnutls/")]) == 17, "Unexpected GnuTLS public header count")
        notices = self.build / "notices"
        notices.mkdir()
        notice_files = []
        source_archives = self.build / "source-archives"
        source_archives.mkdir()
        embedded_notices = {
            "gmp": [],
            "nettle": ["gosthash94.c", "gosthash94.h", "gost28147.c", "poly1305-internal.c", "blowfish-bcrypt.c"],
            "gnutls": ["lib/inih/LICENSE.txt", "lib/extras/randomart.c", *["lib/nettle/gost/" + n for n in
                       ("cmac-kuznyechik.c", "cmac-magma.c", "gost-wrap.c", "gost28147.c", "magma.c")]],
        }
        for package, spec in PACKAGES.items():
            src = self.build / "src" / spec["root"]
            destination = notices / package
            destination.mkdir()
            candidates = {p for pattern in ("COPYING*", "LICENSE*", "AUTHORS", "README*") for p in src.glob(pattern) if p.is_file()}
            candidates.update(src / path for path in embedded_notices[package])
            if package == "gnutls":
                candidates.update((src / "lib/accelerated/aarch64/macosx").glob("*.s"))
            candidates = sorted(candidates)
            archive = source_archives / spec["archive"]
            shutil.copy2(self.source / "build/gnutls-ios/src" / spec["archive"], archive)
            require(digest(archive) == spec["sha256"], "Preserved source archive hash mismatch")
            notice_files.append({"path": str(archive.relative_to(self.build)), "sha256": spec["sha256"],
                                 "purpose": "Complete release source and all per-file copyright/license notices"})
            require(candidates, f"No source notices found for {package}")
            for path in candidates:
                require(path.is_file() and not path.is_symlink(), f"Missing embedded notice source: {path}")
                target = destination / path.relative_to(src)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
                notice_files.append({"path": str(target.relative_to(self.build)), "sha256": digest(target), "source": str(path.relative_to(self.build))})
        write_json(self.build / "prefix-manifest.json", {"files": files, "header_count": len(headers), "libraries": libraries})
        write_json(self.build / "native-generators.json", generated)
        write_json(self.build / "notices-manifest.json", notice_files)
        qualification = {
            "status": "source-only-archives-and-public-headers-built", "madeira_commit": MADEIRA_PIN,
            "jobs": JOBS, "target": "arm64-apple-ios17.0", "sdk_version": "26.5", "xcode_version": "26.6",
            "upstream_recipe": "build/gnutls-ios/build.sh", "same_target_library_feature_flags": True,
            "qualified_differences": ["fresh isolated out-of-tree release source/build/prefix paths, no done-marker reuse",
                "exact tracked archive hashes checked before extraction; regular files/directories only",
                "explicit build alias forces cross-compiling and forbids configure running iOS target probes",
                "native source-built generators use Apple clang with macOS SDK; target uses iPhoneOS SDK",
                "target configure/link tests disable automatic ad-hoc signing; native source-table generator link behavior remains unchanged",
                "explicit library/generated-source/header/pkgconfig targets omit command-line tools, tests and documentation",
                "hard limit make -j4, selected Apple tools, inherited injection variables discarded",
                "existing real pkg-config constrained to fresh target prefix; no Homebrew install",
                "release generated build system retained; unexpected autoreconf/document regeneration fails"],
            "sdk_copied": False, "target_binaries_run": False, "package_install_performed": False,
            "runtime_linked": False, "device_tested": False,
            "gnutls_106_symbol_contract": "not checked here; required separate typed target link probe before Wine feature enablement",
            "libraries": libraries, "public_header_count": len(headers),
            "timeout_owner": "reviewed outer wrapper; aggregate 23-minute stage budget / 25-minute provider cap"}
        # The extraction inventories are immutable source identity, not stamps:
        # reject any unexpected configure/build write into release source copies.
        for package in PACKAGES:
            inventory = json.loads((self.build / "manifests" / (package + "-source.json")).read_text())
            for row in inventory:
                path = self.build / "src" / row["path"]
                require(path.is_file() and not path.is_symlink() and digest(path) == row["sha256"], f"Release source copy changed: {row['path']}")
        write_json(self.build / "qualification.json", qualification)
        write_json(self.build / "manifest.json", {
            "schema": 1, "status": "complete-source-only-control", "madeira_commit": MADEIRA_PIN,
            "target": "arm64-apple-ios17.0", "sdk_version": "26.5", "xcode_version": "26.6", "jobs": JOBS,
            "prefix": "prefix", "libraries": libraries, "prefix_files": files,
            "source_lock": "source-lock.json", "source_inventories": ["manifests/" + p + "-source.json" for p in PACKAGES],
            "command_evidence": "commands.json", "preflight": "preflight.json", "logs": "logs",
            "configuration_evidence": ["build/" + p + "/" + n for p in PACKAGES for n in ("config.log", "config.status", "Makefile", "config.h")],
            "native_generators": "native-generators.json", "notices": "notices-manifest.json", "qualification": "qualification.json",
            "target_binaries_run": False, "runtime_linked": False, "device_tested": False,
            "helper_sha256": digest(Path(__file__)), "source_archives": ["source-archives/" + v["archive"] for v in PACKAGES.values()]})


def validate_ios_load_commands(output, member_count, name):
    # otool prints one LC_BUILD_VERSION for each Mach-O object in these archives.
    # Arm64 alone is insufficient: a host macOS archive is the wrong target.
    blocks = re.findall(r"cmd LC_BUILD_VERSION\n(.*?)(?=Load command |$)", output, re.DOTALL)
    require(len(blocks) == member_count, f"Missing per-member platform metadata: {name}")
    for block in blocks:
        require(re.search(r"^\s*platform\s+(?:IOS|2)\s*$", block, re.MULTILINE), f"Non-iOS archive member: {name}")
        require(re.search(r"^\s*minos\s+17\.0(?:\.0)?\s*$", block, re.MULTILINE), f"Wrong deployment target: {name}")


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2:
        raise ContractError("Usage: crypto_control_support.py SOURCE_ROOT BUILD_ROOT")
    source, build = fresh_output(*args)
    pkg_config = shutil.which("pkg-config")
    build.mkdir(parents=True)
    for name in ("logs", "manifests", "src", "build", "prefix", "home", "tmp"):
        (build / name).mkdir()
    control = Control(source, build, pkg_config)
    try:
        control.preflight()
        control.build_stack()
        control.audit()
    except (ContractError, CommandFailure, OSError) as exc:
        write_json(build / "failure.json", {"error": str(exc), "status": getattr(exc, "status", 2),
                   "step": getattr(exc, "step", None), "build_complete": False})
        raise
    print("GMP/Nettle/GnuTLS source-only archives and headers complete; no runtime link or device test", flush=True)


if __name__ == "__main__":
    try:
        main()
    except (ContractError, CommandFailure, OSError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(getattr(exc, "status", 2))
