#!/usr/bin/env python3
"""Bounded Mac-only pairing build proposal; no device action or target execution."""
import argparse
import concurrent.futures
import errno
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import shlex
import signal
import stat
import subprocess
import sys
import tarfile
import threading
import time
import tomllib
import urllib.parse
import urllib.request
import zipfile

from pairing_validate import (Rejected, ar_members, macho, native_flags, require,
                              safe_relative, sha, shipped_crates, source_members,
                              validate_member, bind_own_rust, bind_ring_native, final_definitions, raw_macho_metadata)
from tool_provenance import component_payload, verify_installed

CI = Path(__file__).resolve().parent
PROFILE = "(version 1)(allow default)(deny network*)"


class Control:
    def __init__(self, args):
        raw = (CI / "pairing-source-lock.json").read_bytes()
        require(sha(raw) == args.expected_lock_sha256, "reviewed lock hash mismatch")
        self.lock = json.loads(raw)
        for name, digest in self.lock.get("control_hashes", {}).items():
            require(sha((CI / name).read_bytes()) == digest, "control source changed: " + name)
        require(self.lock.get("control_hashes"), "control sources have not been frozen")
        self.args, self.started = args, time.monotonic()
        self.deadline = min(self.started + self.lock["aggregate_seconds"],
                            getattr(args, "aggregate_deadline", None) or float("inf"))
        self.work = args.work.absolute()
        require(not self.work.exists() and not self.work.is_symlink(), "work directory must be fresh")
        require(self.work.parent.resolve() == self.work.parent, "work parent must not be a symlink")
        self.work.mkdir(mode=0o700)
        for name in ("evidence", "home", "tmp", "cargo", "rustup", "source", "vendor", "downloads", "output"):
            (self.work / name).mkdir(mode=0o700)
        self.evidence = self.work / "evidence"
        (self.evidence / "pairing-source-lock.json").write_bytes(raw)
        self.commands = []
        self.active_processes = set()
        self.cancelled = threading.Event()
        self.env = dict(PATH="/usr/bin:/bin:/usr/sbin:/sbin", HOME=str(self.work / "home"),
                        TMPDIR=str(self.work / "tmp"), LC_ALL="C", LANG="C",
                        CARGO_HOME=str(self.work / "cargo"), RUSTUP_HOME=str(self.work / "rustup"))
        if os.environ.get("DEVELOPER_DIR"):
            dev = Path(os.environ["DEVELOPER_DIR"])
            require(dev.is_absolute() and dev.is_dir(), "invalid provider DEVELOPER_DIR")
            self.env["DEVELOPER_DIR"] = str(dev)
        self.counter = 0

    def check(self):
        require(time.monotonic() < self.deadline, "inner stage deadline within 23-minute aggregate")
        total = 0
        for root, dirs, files in os.walk(self.work):
            for name in files:
                try:
                    total += (Path(root) / name).lstat().st_size
                except FileNotFoundError:
                    pass
        require(total <= self.lock["work_cap_bytes"], "6 GiB work cap")

    def run(self, argv, name, *, cwd=None, env=None, offline=False, cap=None):
        self.check()
        if offline:
            protected = [self.work / "source", self.work / "vendor", self.work / "rust-mirror", CI]
            if getattr(self, "toolchain_verified", False):
                protected += [self.work / "rustup/toolchains", self.work / "cargo/bin"]
            profile = PROFILE + "(deny file-write* " + " ".join("(subpath " + json.dumps(str(p)) + ")" for p in protected) + ")"
            argv = ["/usr/bin/sandbox-exec", "-p", profile, *map(str, argv)]
        else:
            argv = list(map(str, argv))
        self.counter += 1
        log = self.evidence / f"{self.counter:03d}-{name}.log"
        row = dict(argv=argv, cwd=str(cwd or self.work), log=log.name,
                   offline_sandbox=offline, started_seconds=round(time.monotonic() - self.started, 3))
        self.commands.append(row)
        (self.evidence / "commands.json").write_text(json.dumps(self.commands, indent=2) + "\n")
        limit = min(self.deadline, time.monotonic() + (cap or 1200))
        process = None
        try:
            with log.open("wb") as stream:
                process = subprocess.Popen(argv, cwd=cwd or self.work, env=env or self.env,
                                           stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT,
                                           start_new_session=os.environ.get("PAIRING_SUPERVISED") != "1",
                                           process_group=0 if os.environ.get("PAIRING_SUPERVISED") == "1" else None)
                self.active_processes.add(process.pid)
                row["pid"] = process.pid
                (self.evidence / "commands.json").write_text(json.dumps(self.commands, indent=2) + "\n")
                while process.poll() is None:
                    time.sleep(0.2)
                    require(time.monotonic() < limit, "command timeout: " + name)
                    require(log.stat().st_size <= self.lock["log_cap_bytes"], "command log cap: " + name)
                    self.check()
            self.check()
            require(log.stat().st_size <= self.lock["log_cap_bytes"], "fast-exit command log cap")
            row["returncode"] = process.returncode
            require(process.returncode == 0, "command failed: " + name)
            return log.read_text(errors="replace")
        finally:
            if process and process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
                row["terminated"] = True
            if process:
                self.active_processes.discard(process.pid)
            row["finished_seconds"] = round(time.monotonic() - self.started, 3)
            (self.evidence / "commands.json").write_text(json.dumps(self.commands, indent=2) + "\n")

    def fetch(self, url, digest, destination, maximum):
        require(time.monotonic() < self.deadline, "download deadline")
        require(not self.cancelled.is_set(), "materialization cancelled")
        require(urllib.parse.urlsplit(url).scheme == "https", "non-HTTPS input")
        require(urllib.parse.urlsplit(url).netloc in ("static.rust-lang.org", "static.crates.io"),
                "unrecognized source host")
        require(not destination.exists(), "download destination reuse")
        part = destination.with_name(destination.name + ".partial")
        digestor, size = hashlib.sha256(), 0
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(url, timeout=40) as response, part.open("xb") as out:
            require(response.url == url, "unreviewed redirect")
            while True:
                require(time.monotonic() < self.deadline, "download deadline")
                require(not self.cancelled.is_set(), "materialization cancelled")
                b = response.read(1024 * 1024)
                if not b:
                    break
                size += len(b)
                require(size <= maximum, "download cap")
                digestor.update(b)
                out.write(b)
        require(digestor.hexdigest() == digest, "download checksum mismatch: " + url)
        part.rename(destination)
        return dict(url=url, sha256=digest, size=size)

    def inputs(self):
        expected = self.lock["source_zip"]
        require(self.args.source_zip.stat().st_size == expected["size"], "source ZIP size mismatch")
        raw = self.args.source_zip.read_bytes()
        require(len(raw) == expected["size"] and sha(raw) == expected["sha256"], "source ZIP mismatch")
        expected_files = {x["path"]: x for x in self.lock["files"]}
        with zipfile.ZipFile(self.args.source_zip) as z:
            names = [i.filename for i in z.infolist()]
            require(len(set(names)) == len(names) and set(names) == set(expected_files), "source ZIP inventory mismatch")
            for i in z.infolist():
                safe_relative(i.filename)
                require(not i.flag_bits & 1 and stat.S_IFMT(i.external_attr >> 16) == stat.S_IFREG,
                        "source ZIP type/encryption")
                row = expected_files[i.filename]
                require(i.file_size == row["size"], "source member size")
                b = z.read(i)
                require(sha(b) == row["sha256"], "source member hash")
                target = self.work / "source" / i.filename
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b)
                target.chmod(0o644)
        self.source = self.work / "source/build/rppairing-ios"

    def preflight(self):
        require(platform.system() == "Darwin" and platform.machine() == "arm64", "Apple Silicon Mac required")
        require(shutil.disk_usage(self.work).free >= 8 * 1024**3, "8 GiB free space required")
        xcode = self.run(["/usr/bin/xcodebuild", "-version"], "xcode", cap=30)
        require(xcode.splitlines()[0] == "Xcode 26.6", "exact Xcode 26.6 required")
        version = self.run(["/usr/bin/xcrun", "--sdk", "iphoneos", "--show-sdk-version"], "ios-sdk-version", cap=30).strip()
        require(version == "26.5", "exact iPhoneOS SDK 26.5 required")
        default_dev = self.run(["/usr/bin/xcode-select", "-p"], "developer-dir", cap=30).strip()
        dev = self.env.get("DEVELOPER_DIR", default_dev)
        require(Path(dev).is_absolute() and Path(dev).is_dir(), "invalid selected developer directory")
        self.env["DEVELOPER_DIR"] = dev
        self.ios_sdk = self.run(["/usr/bin/xcrun", "--sdk", "iphoneos", "--show-sdk-path"], "ios-sdk-path", cap=30).strip()
        self.host_sdk = self.run(["/usr/bin/xcrun", "--sdk", "macosx", "--show-sdk-path"], "host-sdk-path", cap=30).strip()
        for value in (self.ios_sdk, self.host_sdk):
            require(Path(value).is_dir() and Path(value).resolve().is_relative_to(Path(dev).resolve()), "SDK escapes selected Xcode")
        self.tools = {}
        for tool in ("clang", "ar", "nm", "otool", "lipo"):
            value = self.run(["/usr/bin/xcrun", "--sdk", "iphoneos", "--find", tool], "find-" + tool, cap=30).strip()
            require(Path(value).is_file() and Path(value).resolve().is_relative_to(Path(dev).resolve()), "tool escapes selected Xcode")
            self.tools[tool] = value
        self.run([self.tools["clang"], "--version"], "clang-version", cap=30)
        self.run(["/usr/bin/sw_vers"], "macos-version", cap=30)
        cpu = self.run(["/usr/sbin/sysctl", "-n", "machdep.cpu.brand_string"], "cpu", cap=30).strip()
        require(cpu in ("Apple M2", "Apple M2 (Virtual)"), "reviewed M2 runner required")
        require(Path("/usr/bin/sandbox-exec").is_file(), "no supported process network sandbox")
        probe = self.work / "network_probe.py"
        probe.write_text("import errno,socket\nfor family,address in [(socket.AF_INET,('127.0.0.1',9)),(socket.AF_INET6,('::1',9))]:\n s=socket.socket(family,socket.SOCK_STREAM)\n try: s.connect(address)\n except OSError as e:\n  assert e.errno in (errno.EPERM,errno.EACCES), ('network sandbox not enforced',e.errno)\n else: raise AssertionError('network permitted')\n finally: s.close()\nprint('NETWORK_DENY_ENFORCED')\n")
        result = self.run([sys.executable, probe], "network-sandbox-probe", offline=True, cap=30)
        require(result.strip() == "NETWORK_DENY_ENFORCED", "network sandbox probe failed")

    def install_rust(self):
        fetched = []
        manifest = self.lock["rust_manifest"]
        fetched.append(self.fetch(manifest["url"], manifest["sha256"], self.work / "downloads/rust-manifest.toml", 2 * 1024**2))
        # Preserve the unchanged reviewed manifest and exact packages in an immutable local mirror.
        mirror = self.work / "rust-mirror"
        dist = mirror / "dist"
        dist.mkdir(parents=True)
        raw_manifest = (self.work / "downloads/rust-manifest.toml").read_bytes()
        parsed = tomllib.loads(raw_manifest.decode())
        require(parsed["date"] == "2026-10-01", "Rust manifest release date changed")
        (dist / "channel-rust-1.99.0.toml").write_bytes(raw_manifest)
        (dist / "channel-rust-1.99.0.toml.sha256").write_text(manifest["sha256"] + "  channel-rust-1.99.0.toml\n")
        self.env["RUSTUP_DIST_SERVER"] = mirror.as_uri()
        self.env["RUSTUP_UPDATE_ROOT"] = (mirror / "rustup").as_uri()
        payloads = {}
        for item in self.lock["components"]:
            entry = parsed["pkg"][item["package"]]["target"][item["target"]]
            require(entry["available"] and entry["xz_url"] == item["url"] and
                    entry["xz_hash"] == item["sha256"], "reviewed component disagrees with original manifest")
            relative = urllib.parse.urlsplit(item["url"]).path.lstrip("/")
            safe_relative(relative)
            package = mirror / relative
            package.parent.mkdir(parents=True, exist_ok=True)
            fetched.append(self.fetch(item["url"], item["sha256"], package, 512 * 1024**2))
            component = item["package"] + "-" + item["target"]
            payloads[component] = component_payload(package, item["package"], item["target"])
            with tarfile.open(package, "r:xz") as tar:
                for m in tar:
                    if m.isfile() and Path(m.name).name.upper().startswith(("LICENSE", "LICENCE", "COPYING", "COPYRIGHT", "NOTICE")):
                        safe_relative(m.name)
                        require(m.size <= 32 * 1024**2, "tool notice cap")
                        dest = self.work / "output/rust-component-notices" / m.name
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        dest.write_bytes(tar.extractfile(m).read())
            if item["package"] == "rust-std" and item["target"] == "aarch64-apple-ios":
                self.std_package = package
        installer = self.work / "downloads/rustup-init"
        rp = self.lock["rustup"]
        fetched.append(self.fetch(rp["url"], rp["sha256"], installer, 64 * 1024**2))
        (self.evidence / "tool-downloads.json").write_text(json.dumps(fetched, indent=2) + "\n")
        installer.chmod(0o700)
        self.run([installer, "-y", "--no-modify-path", "--default-host", "aarch64-apple-darwin",
                  "--default-toolchain", "none", "--profile", "minimal"], "rustup-install", offline=True, cap=180)
        self.rustup = self.work / "cargo/bin/rustup"
        require(self.rustup.is_file() and not self.rustup.is_symlink() and
                sha(self.rustup.read_bytes()) == rp["sha256"], "installed rustup bytes differ from verified installer")
        for proxy in (self.work / "cargo/bin").iterdir():
            require(proxy.is_file() and proxy.resolve().is_relative_to(self.work / "cargo/bin") and
                    sha(proxy.read_bytes()) == rp["sha256"], "unverified rustup proxy")
        self.env["PATH"] = str(self.work / "cargo/bin") + ":" + self.env["PATH"]
        v = self.run([self.rustup, "--version"], "rustup-version", offline=True, cap=30)
        require(re.search(r"^rustup 1\.29\.1 ", v, re.M), "rustup version mismatch")
        self.run([self.rustup, "set", "auto-self-update", "disable"], "rustup-disable-self-update", offline=True, cap=30)
        self.run([self.rustup, "toolchain", "install", "1.99.0-aarch64-apple-darwin", "--profile", "minimal",
                  "--target", "aarch64-apple-ios"], "rust-toolchain-install", offline=True, cap=300)
        toolchain = self.work / "rustup/toolchains/1.99.0-aarch64-apple-darwin"
        require(toolchain.is_dir(), "missing exact isolated toolchain")
        installed = verify_installed(toolchain, payloads)
        (self.evidence / "installed-toolchain-provenance.json").write_text(json.dumps(installed, indent=2) + "\n")
        self.toolchain_verified = True
        self.rustc, self.cargo = toolchain / "bin/rustc", toolchain / "bin/cargo"
        v = self.run([self.rustc, "-vV"], "rustc-version", offline=True, cap=30)
        require("release: 1.99.0\n" in v and "host: aarch64-apple-darwin\n" in v,
                "compiler version/host mismatch")
        require("commit-hash: " + self.lock["rust_commit"] + "\n" in v, "compiler commit mismatch")
        cargo_version = self.run([self.cargo, "--version"], "cargo-version", offline=True, cap=30)
        require(cargo_version.startswith("cargo 1.99.0 "), "Cargo version mismatch")
        sysroot = self.run([self.rustc, "--print", "sysroot"], "rust-sysroot", offline=True, cap=30).strip()
        require(Path(sysroot).resolve() == toolchain.resolve(), "unexpected Rust sysroot")
        targets = self.run([self.rustup, "target", "list", "--installed", "--toolchain", "1.99.0"],
                           "rust-targets", offline=True, cap=30)
        require(set(targets.split()) == {"aarch64-apple-darwin", "aarch64-apple-ios"}, "installed targets mismatch")
        components = self.run([self.rustup, "component", "list", "--installed", "--toolchain", "1.99.0"],
                              "rust-components", offline=True, cap=30)
        require(set(components.split()) == {"cargo-aarch64-apple-darwin", "rustc-aarch64-apple-darwin",
                "rust-std-aarch64-apple-darwin", "rust-std-aarch64-apple-ios"}, "unexpected Rust component set")
        self.std_dir = toolchain / "lib/rustlib/aarch64-apple-ios/lib"
        require(self.std_dir.is_dir() and list(self.std_dir.glob("libstd-*.rlib")), "device standard library missing")
        self.std_hashes = set()
        standard = []
        packaged = {}
        with tarfile.open(self.std_package, "r:xz") as tar:
            for m in tar:
                if m.isfile() and "/lib/rustlib/aarch64-apple-ios/lib/" in m.name and m.name.endswith(".rlib"):
                    require(m.size <= 256 * 1024**2, "Rust std archive cap")
                    require(Path(m.name).name not in packaged, "duplicate packaged std archive")
                    packaged[Path(m.name).name] = sha(tar.extractfile(m).read())
        require(set(packaged) == {p.name for p in self.std_dir.glob("*.rlib")}, "installed std archive inventory differs from official package")
        for p in sorted(self.std_dir.glob("*.rlib")):
            require(sha(p.read_bytes()) == packaged[p.name], "installed std bytes differ from official package")
            members = []
            for name, b in ar_members(p.read_bytes()):
                if name.endswith(".o"):
                    self.std_hashes.add(sha(b))
                    members.append(dict(name=name, sha256=sha(b), size=len(b)))
            standard.append(dict(name=p.name, sha256=sha(p.read_bytes()), size=p.stat().st_size, members=members))
        (self.evidence / "rust-std-members.json").write_text(json.dumps(standard, indent=2) + "\n")

    def materialize(self):
        require(len(self.lock["crates"]) == 152, "registry package count changed")
        def one(item):
            filename = item["name"] + "-" + item["version"]
            archive = self.work / "downloads" / (filename + ".crate")
            result = self.fetch(item["url"], item["sha256"], archive, 32 * 1024**2)
            rows = source_members(archive.read_bytes(), filename)
            folder = self.work / "vendor" / filename
            folder.mkdir()
            hashes = {}
            for name, b, mode in rows:
                require(not self.cancelled.is_set(), "materialization cancelled")
                require(name != ".cargo-checksum.json", "crate unexpectedly supplies vendor checksum file")
                dest = folder / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(b)
                dest.chmod(mode)
                hashes[name] = sha(b)
            (folder / ".cargo-checksum.json").write_text(json.dumps(dict(files=hashes, package=item["sha256"]), sort_keys=True))
            require(not (folder / ".git").exists(), "published source unexpectedly contains Git directory")
            result.update(package=filename, files=len(rows), unpacked_bytes=sum(len(b) for _, b, _ in rows))
            return result
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            pending = [pool.submit(one, item) for item in self.lock["crates"]]
            try:
                while any(not f.done() for f in pending):
                    time.sleep(0.25)
                    self.check()
                    for f in pending:
                        if f.done() and f.exception():
                            raise f.exception()
                records = [f.result() for f in pending]
            except BaseException:
                self.cancelled.set()
                for f in pending:
                    f.cancel()
                raise
        self.check()
        (self.evidence / "crate-downloads.json").write_text(json.dumps(records, indent=2) + "\n")
        config = '[source.crates-io]\nreplace-with = "vendored-sources"\n[source.vendored-sources]\ndirectory = ' + json.dumps(str(self.work / "vendor")) + '\n[net]\noffline = true\n'
        (self.work / "cargo/config.toml").write_text(config)
        self.env.update(CARGO_NET_OFFLINE="true", CARGO_TARGET_DIR=str(self.work / "target"),
                        CARGO_BUILD_JOBS="4", CARGO_INCREMENTAL="0", RUSTC=str(self.rustc),
                        PAIRING_RUSTC=str(self.rustc), PAIRING_IOS_SDK=self.ios_sdk,
                        PAIRING_HOST_SDK=self.host_sdk, PAIRING_OWN_SOURCE=str(self.source / "src/lib.rs"),
                        PAIRING_OWN_OUT_DIR=str(self.work / "target/aarch64-apple-ios/release/deps"),
                        PAIRING_RUSTC_LOG=str(self.evidence / "rustc-argv.jsonl"),
                        IPHONEOS_DEPLOYMENT_TARGET="18.0")
        wrapper = self.work / "rustc-wrapper"
        require(" " not in sys.executable, "Python interpreter path unsupported")
        content = (CI / "rustc_wrapper.py").read_text().splitlines(keepends=True)
        wrapper.write_text("#!" + sys.executable + "\n" + "".join(content[1:]))
        wrapper.chmod(0o700)
        shutil.copyfile(wrapper, self.evidence / "rustc-wrapper-source.py")
        self.env["RUSTC_WRAPPER"] = str(wrapper)
        self.env["CARGO_TARGET_AARCH64_APPLE_IOS_LINKER"] = self.tools["clang"]
        self.env["CARGO_TARGET_AARCH64_APPLE_DARWIN_LINKER"] = self.tools["clang"]
        self.env["CC_aarch64_apple_ios"] = self.tools["clang"]
        self.env["AR_aarch64_apple_ios"] = self.tools["ar"]
        self.env["CFLAGS_aarch64_apple_ios"] = "-isysroot " + self.ios_sdk + " -miphoneos-version-min=18.0"
        self.env["CC_ENABLE_DEBUG_OUTPUT"] = "1"
        self.env["CARGO_TERM_COLOR"] = "never"
        self.env["RUST_BACKTRACE"] = "0"
        (self.evidence / "build-environment.json").write_text(json.dumps(self.env, indent=2) + "\n")

    def build(self):
        metadata_text = self.run([self.cargo, "metadata", "--format-version", "1", "--offline", "--locked",
                                  "--filter-platform", "aarch64-apple-ios"], "cargo-metadata", cwd=self.source,
                                 offline=True, cap=90)
        metadata = json.loads(metadata_text)
        known = {(x["name"], x["version"]) for x in self.lock["crates"]}
        for p in metadata["packages"]:
            if p["name"] == "madeira_rppairing":
                require(p["source"] is None and Path(p["manifest_path"]).parent == self.source, "wrapper source substituted")
            else:
                require((p["name"], p["version"]) in known and p["source"] == "registry+https://github.com/rust-lang/crates.io-index",
                        "unexpected Cargo dependency source")
                require(Path(p["manifest_path"]).resolve().is_relative_to(self.work / "vendor"), "dependency escapes vendor")
        shipped = shipped_crates(metadata)
        expected = {(x["name"], x["version"]) for x in self.lock["crates"] if x["in_target_notices"]}
        require({(p["name"], p["version"]) for p in shipped} == expected, "target notice dependency closure changed")
        self.metadata = metadata
        output = self.run([self.cargo, "rustc", "--release", "--offline", "--locked", "--lib", "--target",
                           "aarch64-apple-ios", "-j4", "-vv", "--", "-C", "save-temps", "--print", "native-static-libs"],
                          "cargo-build", cwd=self.source, offline=True, cap=900)
        self.native = native_flags(output, self.lock["native_library_allowlist"], self.lock["native_framework_allowlist"])
        self.archive = self.work / "target/aarch64-apple-ios/release/libmadeira_rppairing.a"
        require(self.archive.is_file() and self.archive.stat().st_size <= 512 * 1024**2, "archive missing/oversized")
        data = self.archive.read_bytes()
        raw_members = [dict(name=name, sha256=sha(b), size=len(b), magic=b[:16].hex(), raw_macho=raw_macho_metadata(b))
                       for name, b in ar_members(data)]
        raw_report = json.dumps(dict(archive_sha256=sha(data), archive_size=len(data), members=raw_members), indent=2) + "\n"
        require(len(raw_report.encode()) <= self.lock["log_cap_bytes"], "raw archive diagnostic evidence cap")
        (self.evidence / "archive-raw-members.json").write_text(raw_report)
        self.capture_ring_diagnostics(raw_members)
        self.validate_archive()
        self.link_proof()
        self.verify_inputs()
        self.notices(shipped)

    def verify_inputs(self):
        for row in self.lock["files"]:
            require(sha((self.work / "source" / row["path"]).read_bytes()) == row["sha256"], "source input changed during build")
        for item in self.lock["crates"]:
            folder = self.work / "vendor" / (item["name"] + "-" + item["version"])
            checksum = json.loads((folder / ".cargo-checksum.json").read_text())
            require(checksum["package"] == item["sha256"], "vendor package checksum changed")
            actual_names = {str(p.relative_to(folder)) for p in folder.rglob("*") if p.is_file() and p.name != ".cargo-checksum.json"}
            require(actual_names == set(checksum["files"]), "vendor file inventory changed")
            for name, expected in checksum["files"].items():
                require(sha((folder / name).read_bytes()) == expected, "vendor source changed during build")

    def capture_ring_diagnostics(self, final_members):
        # Diagnostics precede every native member policy guard and never accept objects.
        target = self.work / "target/aarch64-apple-ios/release"
        package = next(x for x in self.lock["crates"] if x["name"] == "ring" and x["version"] == "0.17.14")
        vendor = self.work / "vendor/ring-0.17.14"
        checksum = json.loads((vendor / ".cargo-checksum.json").read_text())
        log_row = next(x for x in self.commands if x["log"].endswith("-cargo-build.log"))
        text = (self.evidence / log_row["log"]).read_text()
        compiles, issues = [], []
        final_by_hash = {}
        for member in final_members:
            final_by_hash.setdefault(member["sha256"], []).append(member["name"])
        for line_number, line in enumerate(text.splitlines(), 1):
            if not line.startswith("[ring 0.17.14] running: "):
                continue
            try:
                args = shlex.split(line.split("running: ", 1)[1])
                if "-c" not in args or "-o" not in args:
                    continue
                require(len(compiles) < 256, "native diagnostic command count cap")
                source = Path(args[args.index("-c") + 1])
                obj = Path(args[args.index("-o") + 1])
                row = dict(log=log_row["log"], log_line=line_number, argv=args,
                           source=str(source), object=str(obj), language_suffix=source.suffix)
                compiles.append(row)
                require(source.resolve().is_relative_to(vendor.resolve()) and not source.is_symlink(),
                        "native diagnostic source outside exact ring package")
                require(obj.resolve().is_relative_to(target / "build") and not obj.is_symlink(),
                        "native diagnostic object outside fresh target build")
                relative = str(source.relative_to(vendor))
                require(source.stat().st_size <= 4 * 1024**2 and obj.stat().st_size <= 16 * 1024**2,
                        "native diagnostic input size cap")
                row.update(source_relative=relative, source_sha256=sha(source.read_bytes()),
                           vendor_manifest_sha256=checksum["files"].get(relative),
                           object_sha256=sha(obj.read_bytes()), object_size=obj.stat().st_size,
                           raw_macho=raw_macho_metadata(obj.read_bytes()))
                row["source_matches_materialized_package"] = row["source_sha256"] == row["vendor_manifest_sha256"]
                row["final_member_names"] = final_by_hash.get(row["object_sha256"], [])
            except Exception as error:
                issues.append(dict(log_line=line_number, error=str(error)))
        self.native_diagnostic_paths = list((target / "build").rglob("*.a"))
        archives = []
        for p in self.native_diagnostic_paths:
            archive_row = dict(path=str(p.relative_to(self.work)), members=[])
            archives.append(archive_row)
            try:
                require(p.is_file() and not p.is_symlink() and p.stat().st_size <= 512 * 1024**2,
                        "native diagnostic archive cap/type")
                content = p.read_bytes()
                archive_row.update(sha256=sha(content), size=len(content))
                for ordinal, (name, data) in enumerate(ar_members(content)):
                    matches = [i for i, row in enumerate(compiles)
                               if row.get("object_sha256") == sha(data) and
                               Path(row["object"]).name == name and Path(row["object"]).parent == p.parent]
                    archive_row["members"].append(dict(ordinal=ordinal, name=name, size=len(data),
                            sha256=sha(data), raw_macho=raw_macho_metadata(data),
                            compile_rows=matches, final_member_names=final_by_hash.get(sha(data), [])))
            except Exception as error:
                archive_row["diagnostic_error"] = str(error)
        result = dict(package=package, materialized_package_checksum=checksum["package"],
                      source_checksum_manifest_sha256=sha((vendor / ".cargo-checksum.json").read_bytes()),
                      compile_count=len(compiles), compilation_rows=compiles, archives=archives,
                      diagnostic_issues=issues, diagnostic_capture_accepts_objects=False)
        diagnostic_report = json.dumps(result, indent=2) + "\n"
        require(len(diagnostic_report.encode()) <= self.lock["log_cap_bytes"], "native diagnostic evidence cap")
        (self.evidence / "ring-prevalidation-diagnostics.json").write_text(diagnostic_report)
        self.ring_diagnostics = result

    def validate_archive(self):
        target = self.work / "target/aarch64-apple-ios/release"
        rust_hashes = set()
        for p in target.rglob("*.rlib"):
            for name, b in ar_members(p.read_bytes()):
                if name.endswith(".o"):
                    rust_hashes.add(sha(b))
        native_data = {}
        for p in self.native_diagnostic_paths:
            require(p.is_file() and not p.is_symlink() and p.resolve().is_relative_to(target / "build"),
                    "native archive path/type changed")
            native_data[str(p.relative_to(self.work))] = p.read_bytes()
        # Native objects are also bundled inside ring's rlib. They cannot fall back to Rust SDK0 rules.
        native_hashes = {sha(b) for data in native_data.values() for _, b in ar_members(data)}
        rust_hashes.difference_update(native_hashes)
        source_hashes, object_hashes = {}, {}
        vendor = self.work / "vendor/ring-0.17.14"
        for row in self.ring_diagnostics["compilation_rows"]:
            source, obj = Path(row["source"]), Path(row["object"])
            require(source.is_file() and not source.is_symlink() and source.resolve().is_relative_to(vendor) and
                    obj.is_file() and not obj.is_symlink() and obj.resolve().is_relative_to(target / "build"),
                    "ring source/object path/type changed")
            require(source.stat().st_size <= 4 * 1024**2 and obj.stat().st_size <= 16 * 1024**2,
                    "ring source/object byte cap")
            source_hashes[str(source)], object_hashes[str(obj)] = sha(source.read_bytes()), sha(obj.read_bytes())
        log = next(x for x in self.commands if x["log"].endswith("-cargo-build.log"))
        try:
            checksum_bytes = (vendor / ".cargo-checksum.json").read_bytes()
            require(sha(checksum_bytes) == self.ring_diagnostics["source_checksum_manifest_sha256"],
                    "ring materialized source checksum manifest changed")
            native_origins = bind_ring_native(self.lock["ring_native_policy"], self.ring_diagnostics,
                    work=str(self.work), compiler=self.tools["clang"], sdk=self.ios_sdk,
                    archive_data=native_data, final_data=self.archive.read_bytes(),
                    source_hashes=source_hashes, object_hashes=object_hashes,
                    checksum=json.loads(checksum_bytes),
                    cargo_record=log, cargo_log=(self.evidence / log["log"]).read_text())
        except Exception as error:
            context = getattr(error, "context", dict(stage="native-ring-binding", error=str(error)))
            (self.evidence / "validation-failure-context.json").write_text(json.dumps(context, indent=2) + "\n")
            raise
        (self.evidence / "ring-members.json").write_text(json.dumps(
            [dict(**origin.evidence(), **macho(next(b for n, b in ar_members(native_data[origin.archive])
                                                   if n == origin.member)))
             for origin in native_origins.values()], indent=2) + "\n")
        logs = [json.loads(line) for line in (self.evidence / "rustc-argv.jsonl").read_text().splitlines()]
        source_row = next(x for x in self.lock["files"] if x["path"] == "build/rppairing-ios/src/lib.rs")
        binding = bind_own_rust(logs, compiler=str(self.rustc), source=str(self.source / "src/lib.rs"),
                               source_sha256=source_row["sha256"], out_dir=str(target / "deps"),
                               archive_data=self.archive.read_bytes())
        for obj in binding["invocation"]["fresh_objects"]:
            path = Path(obj["path"])
            require(path.is_file() and not path.is_symlink() and
                    path.stat().st_size == obj["size"] and sha(path.read_bytes()) == obj["sha256"],
                    "recorded own object bytes changed")
        (self.evidence / "own-rust-object-binding.json").write_text(json.dumps(binding, indent=2) + "\n")
        rows = [validate_member(name, b, self.std_hashes, rust_hashes, native_origins, binding,
                                known_native_hashes=native_hashes)
                for name, b in ar_members(self.archive.read_bytes())]
        require(rows and any(r["origin"] == "fresh-rust-codegen-output" for r in rows), "no fresh Rust code")
        (self.evidence / "archive-members.json").write_text(json.dumps(rows, indent=2) + "\n")
        symbols = self.run([self.tools["nm"], "-g", self.archive], "archive-symbols", offline=True, cap=90)
        defined = set(re.findall(r"^[0-9a-fA-F]+ [TDSB] (_\S+)$", symbols, re.M))
        require({"_" + x for x in self.lock["exports"]} == {x for x in defined if x.startswith("_madeira_rppairing_")}, "C export namespace mismatch")
        self.run([self.tools["ar"], "-t", self.archive], "archive-member-names", offline=True, cap=90)
        self.run([self.tools["otool"], "-l", self.archive], "archive-load-commands", offline=True, cap=90)
        self.run([self.tools["lipo"], "-info", self.archive], "archive-architecture", offline=True, cap=30)

    def link_proof(self):
        header = self.work / "source/app/Madeira/MadeiraRPPairing.h"
        probe = self.work / "api_probe.c"
        names = self.lock["exports"]
        probe.write_text('#include "MadeiraRPPairing.h"\n__attribute__((used)) static void (*volatile api[])(void) = {\n' +
                         ',\n'.join('(void (*)(void)) &' + name for name in names) +
                         '\n};\n__attribute__((visibility("default"))) void *madeira_pairing_link_proof(void) { return (void *)api; }\n')
        shutil.copyfile(probe, self.evidence / "api_probe.c")
        dylib = self.work / "api_probe.dylib"
        cmd = [self.tools["clang"], "-target", "arm64-apple-ios18.0", "-isysroot", self.ios_sdk,
               "-dynamiclib", "-I", header.parent, probe, self.archive, "-Wl,-no_adhoc_codesign",
               "-Wl,-undefined,error", "-Wl,-install_name,@rpath/PairingLinkProof.dylib", "-o", dylib,
               *self.native]
        self.run(cmd, "target-link-proof", offline=True, cap=120)
        info = macho(dylib.read_bytes(), 6)
        require(info["minimum"] == 0x120000 and info["sdk"] == 0x1A0500, "target link metadata mismatch")
        loads = self.run([self.tools["otool"], "-L", dylib], "target-link-dependencies", offline=True, cap=30)
        paths = [line.strip().split(" (", 1)[0] for line in loads.splitlines()[1:] if " (" in line]
        require(paths and paths[0] == "@rpath/PairingLinkProof.dylib", "proof install name changed")
        allowed_paths = {"/usr/lib/libSystem.B.dylib", "/usr/lib/libobjc.A.dylib",
                         "/usr/lib/libiconv.2.dylib", "/usr/lib/libresolv.9.dylib",
                         "/System/Library/Frameworks/Security.framework/Security",
                         "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation"}
        for path in paths[1:]:
            require(path in allowed_paths, "unreviewed dynamic dependency")
        symbols = self.run([self.tools["nm"], "-g", dylib], "target-link-symbols", offline=True, cap=30)
        definitions = final_definitions(symbols, self.lock["exports"])
        shutil.copyfile(dylib, self.evidence / "api_probe.dylib")
        (self.evidence / "api_probe.dylib").chmod(0o644)
        (self.evidence / "native-link-closure.json").write_text(json.dumps(dict(flags=self.native, linked_paths=paths,
                    proof_sha256=sha(dylib.read_bytes()), proof_size=dylib.stat().st_size,
                    final_c_definitions=definitions, probe_executed=False, **info), indent=2) + "\n")

    def notices(self, shipped):
        # Same target normal-edge selection as upstream notices.py; all nested notices retained too.
        notices, seen, inventory = [], {}, []
        for p in sorted(shipped, key=lambda x: (x["name"], x["version"])):
            folder = Path(p["manifest_path"]).parent
            notices += ["=" * 78, f'{p["name"]} {p["version"]} ({p.get("license") or "see files"})']
            if p.get("repository"):
                notices.append(p["repository"])
            files = sorted(f for f in folder.iterdir() if f.is_file() and f.name.upper().startswith(("LICENSE", "LICENCE", "COPYING", "NOTICE")))
            if not files:
                notices.append("(no licence file in the published crate; licence as declared above)")
            for f in files:
                content = f.read_text(errors="replace").rstrip()
                if content in seen:
                    notices.append(f'--- {f.name}: same text as {seen[content]} above ---')
                else:
                    seen[content] = f'{p["name"]} {f.name}'
                    notices += ["", f"--- {f.name} ---", content]
            notices.append("")
        preamble = ['Third-party notices for libmadeira_rppairing.a (build/rppairing-ios), generated',
                    'by build/rppairing-ios/notices.py from Cargo.lock. Each crate is listed with the',
                    'licence it declares and the licence files it ships.', '']
        text = "\n".join(preamble + notices) + "\n"
        expected = self.work / "source/app/Madeira/legal/LICENSES-rppairing-crates.txt"
        require(text.encode() == expected.read_bytes(), "regenerated target notices changed")
        output = self.work / "output"
        shutil.copyfile(self.archive, output / self.archive.name)
        shutil.copyfile(self.work / "source/app/Madeira/MadeiraRPPairing.h", output / "MadeiraRPPairing.h")
        (output / "LICENSES-rppairing-crates.txt").write_text(text)
        for f in sorted((self.work / "vendor").rglob("*")):
            if f.is_file() and f.name.upper().startswith(("LICENSE", "LICENCE", "COPYING", "NOTICE")):
                relative = f.relative_to(self.work / "vendor")
                dest = output / "crate-notices" / relative
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(f, dest)
                inventory.append(dict(path=str(relative), sha256=sha(f.read_bytes()), size=f.stat().st_size))
        for name in ("LICENSE", "LICENSE-EXCEPTION.md", "THIRD-PARTY-NOTICES.md", "LICENSES/MIT-idevice.txt"):
            dest = output / "madeira-notices" / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(self.work / "source" / name, dest)
        toolchain = self.rustc.parent.parent
        for f in sorted(toolchain.rglob("*")):
            if f.is_file() and f.name.upper().startswith(("LICENSE", "LICENCE", "COPYING", "NOTICE", "COPYRIGHT")):
                dest = output / "rust-notices" / f.relative_to(toolchain)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(f, dest)
        (self.evidence / "all-crate-notices.json").write_text(json.dumps(inventory, indent=2) + "\n")
        # Keep exact source crates and source subset for later compliance/rebuild review, not Rust tool binaries.
        with tarfile.open(output / "pairing-source-inputs.tar.gz", "w:gz") as tar:
            for p in sorted((self.work / "downloads").glob("*.crate")):
                tar.add(p, arcname="crates/" + p.name, recursive=False)
            for row in self.lock["files"]:
                tar.add(self.work / "source" / row["path"], arcname="madeira/" + row["path"], recursive=False)
        for p in sorted(output.rglob("*")):
            if p.is_file():
                p.chmod(0o644)
        hashes = {str(p.relative_to(output)): dict(size=p.stat().st_size, sha256=sha(p.read_bytes()))
                  for p in sorted(output.rglob("*")) if p.is_file()}
        (self.evidence / "output-manifest.json").write_text(json.dumps(hashes, indent=2) + "\n")


def cleanup_output(work):
    output = work / "output"
    if output.is_symlink():
        output.unlink()
    elif output.exists():
        shutil.rmtree(output)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("stage", choices=("preflight", "rust", "pairing"))
    p.add_argument("--source-zip", type=Path, required=True)
    p.add_argument("--work", type=Path, required=True)
    p.add_argument("--expected-lock-sha256", required=True)
    p.add_argument("--aggregate-deadline", type=float)
    a = p.parse_args()
    control = None
    status = dict(status="failed", stage=a.stage, target_executed=False, pairing_called=False)
    try:
        control = Control(a)
        def hard_deadline(signum, frame):
            # Covers blocked download threads too. Kill only this control's owned process groups.
            for pid in tuple(control.active_processes):
                try:
                    os.killpg(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            result = dict(status="failed", stage=a.stage, error="hard inner deadline with reserved outer finalization",
                          target_executed=False, pairing_called=False,
                          elapsed_seconds=round(time.monotonic() - control.started, 3))
            (control.evidence / "result.json").write_text(json.dumps(result, indent=2) + "\n")
            cleanup_output(control.work)
            os._exit(124)
        signal.signal(signal.SIGALRM, hard_deadline)
        signal.setitimer(signal.ITIMER_REAL, max(0.001, control.deadline - time.monotonic()))
        control.inputs()
        control.preflight()
        if a.stage in ("rust", "pairing"):
            control.install_rust()
        if a.stage == "pairing":
            control.materialize()
            control.build()
        control.check()
        status["status"] = "passed"
    except Exception as error:
        status["error"] = str(error)
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        if control:
            if status["status"] != "passed":
                cleanup_output(control.work)
            status["elapsed_seconds"] = round(time.monotonic() - control.started, 3)
            (control.evidence / "result.json").write_text(json.dumps(status, indent=2) + "\n")


if __name__ == "__main__":
    main()
