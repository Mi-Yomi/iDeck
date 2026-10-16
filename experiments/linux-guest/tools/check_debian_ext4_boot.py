#!/usr/bin/env python3
"""Two offline system-QEMU boots on a fresh copy of an authenticated Debian seed.

Windows can use an existing WSL distribution for read-only e2fsck. No installs,
mounts, user disk access, networking or production bundle changes are performed.
"""
import argparse
import gzip
import json
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import time

import desktop_modules as modules
import prepare_guest
from debian_rootfs import sha256

EXPERIMENT = Path(__file__).resolve().parents[1]


def metadata(path):
    return {"size": path.stat().st_size, "sha256": sha256(path)}


def checked(path, expected):
    if path.is_symlink() or not path.is_file() or metadata(path) != expected:
        raise ValueError("input integrity mismatch: " + str(path))
    return path.read_bytes()


def cpio_suffix(files):
    # Alpine uses merged-/usr symlinks. Creating /lib as a directory in a later
    # CPIO replaces the symlink and makes the real musl interpreter disappear.
    if any(name.split("/", 1)[0] in {"lib", "bin", "sbin"} for name in files):
        raise ValueError("suffix would replace an Alpine merged-/usr alias")
    directories = {"ideck"}
    for name in files:
        directories.update(str(p) for p in Path(name).parents if str(p) != ".")
    records = [(name.replace("\\", "/"), b"", stat.S_IFDIR | 0o755) for name in sorted(directories)]
    records += [(name, content, stat.S_IFREG | mode) for name, (content, mode) in sorted(files.items())]
    records.append(("TRAILER!!!", b"", 0))
    return b"".join(prepare_guest.entry(n, d, m, i + 1) for i, (n, d, m) in enumerate(records))


def prepare_boot(out, module_dir):
    lock = json.loads((EXPERIMENT / "ipa/guest.lock.json").read_text())
    archive = EXPERIMENT / lock["archive"]
    # The normal restore helper verifies this archive and all three members.
    sys.path.insert(0, str(EXPERIMENT.parents[1] / "ci"))
    from build_linux_probe_ipa import restore_guest
    from stage_bundle import verify
    restore_guest(out / "probe")
    guest = verify(out / "probe")
    manifest = json.loads((module_dir / "manifest.json").read_text())
    if (manifest["modloop_sha256"] != modules.MODLOOP_SHA256
            or manifest["kernel_release"] != modules.KERNEL
            or manifest["expected_kernel_sha256"] != modules.KERNEL_SHA256):
        raise ValueError("module manifest kernel mismatch")
    dep_bytes = checked(module_dir / modules.MODULE_PREFIX / "modules.dep", manifest["metadata"]["modules.dep"])
    soft_bytes = checked(module_dir / modules.MODULE_PREFIX / "modules.softdep", manifest["metadata"]["modules.softdep"])
    builtin_bytes = checked(module_dir / modules.MODULE_PREFIX / "modules.builtin", manifest["metadata"]["modules.builtin"])
    order = modules.closure(modules.dependencies(dep_bytes),
                            modules.soft_dependencies(soft_bytes, reachable_only=True), builtin_bytes)
    if order != manifest["load_order"] or order != [m["path"] for m in manifest["modules"]]:
        raise ValueError("module load order differs from dependency metadata")
    files = {"ideck-ext4-test-init": ((EXPERIMENT / "guest/ideck-ext4-test-init").read_bytes().replace(b"\r\n", b"\n"), 0o755),
             "ideck/posix-check": ((EXPERIMENT / "guest/ideck-ext4-posix-check").read_bytes().replace(b"\r\n", b"\n"), 0o755),
             "ideck/ext4-load-order": (("\n".join(order) + "\n").encode(), 0o644)}
    rootfs_lock = json.loads((EXPERIMENT / "ipa/desktop-rootfs.lock.json").read_text())
    rows = ["\t".join([p["name"], p["version"], p["architecture"], "install ok installed"])
            for p in rootfs_lock["packages"]]
    files["ideck/expected-packages.tsv"] = (("\n".join(sorted(rows)) + "\n").encode(), 0o644)
    for item in manifest["modules"]:
        path = modules.module_path(item["path"])
        content = checked(module_dir / modules.MODULE_PREFIX / path,
                          {k: item[k] for k in ("size", "sha256")})
        modules.module_metadata(content)
        files["usr/lib/modules/" + modules.KERNEL + "/" + path] = (content, 0o644)
    suffix = cpio_suffix(files)
    (out / "vmlinuz-virt").write_bytes(guest["vmlinuz-virt"])
    (out / "initramfs-ext4-test.gz").write_bytes(guest["initramfs-ideck.gz"] + gzip.compress(suffix, mtime=0))
    return {"module_manifest": metadata(module_dir / "manifest.json"),
            "guest_archive": metadata(archive), "load_order": order,
            "rootfs_lock": metadata(EXPERIMENT / "ipa/desktop-rootfs.lock.json"),
            "kernel": metadata(out / "vmlinuz-virt"),
            "initramfs": metadata(out / "initramfs-ext4-test.gz")}


def boot_pass(log, phase, code):
    required = [f"IDECK_EXT4_BOOT:{phase}", "IDECK_EXT4_MOUNTED", "IDECK_DEBIAN_GLIBC:glibc ",
                "IDECK_DEBIAN_PACKAGE_AUDIT_PASS", f"IDECK_POSIX_PASS:{phase}",
                f"IDECK_EXT4_CLEAN_UNMOUNT:{phase}"]
    return code == 0 and all(s in log for s in required) and not any(
        s in log for s in ("IDECK_EXT4_FAILED:", "Kernel panic", "EXT4-fs error"))


def check(args):
    out, seed = args.out.resolve(), args.seed.resolve()
    if args.seed.is_symlink() or not seed.is_file():
        raise ValueError("seed must be a regular file")
    profile = json.loads(args.profile.read_text())
    expected = {k: profile["rootfs"][k] for k in ("size", "sha256")}
    if not 64 * 1024**2 <= expected["size"] <= 4 * 1024**3 or metadata(seed) != expected:
        raise ValueError("seed/profile mismatch")
    out.mkdir(parents=True, exist_ok=False)
    report = {"schema": 1, "status": "failed", "scope": "host system-QEMU Debian/ext4 two-boot acceptance",
              "seed": expected, "boots": [], "legacy_userdata_accessed": False,
              "iphone_debian_tested": False, "network": "-nic none", "checks_passed": [],
              "checks_failed": [], "checks_not_run": ["iPhone Debian/ext4", "GUI", "Steam"]}
    started = time.monotonic()
    try:
        report["inputs"] = prepare_boot(out, args.modules.resolve())
        report["qemu"] = {**metadata(args.qemu), "version": subprocess.check_output(
            [str(args.qemu), "--version"], text=True).strip()}
        disk = out / "disposable.raw"
        shutil.copyfile(seed, disk)
        if metadata(disk) != expected:
            raise ValueError("disposable copy differs")
        for phase in (1, 2):
            command = [str(args.qemu), "-machine", "virt", "-cpu", "cortex-a72", "-smp", "4",
                       "-m", "1024", "-accel", "tcg,tb-size=256", "-nodefaults", "-display", "none",
                       "-monitor", "none", "-serial", "stdio", "-nic", "none", "-no-reboot",
                       "-kernel", str(out / "vmlinuz-virt"), "-initrd", str(out / "initramfs-ext4-test.gz"),
                       "-append", f"console=ttyAMA0 rdinit=/ideck-ext4-test-init ideck.phase={phase}",
                       "-drive", f"if=none,id=debian,file={disk},format=raw,cache=writeback",
                       "-device", "virtio-blk-device,drive=debian"]
            item = {"phase": phase, "command": command, "exit_code": None, "status": "failed"}
            report["boots"].append(item)
            before = time.monotonic()
            log_path = out / f"boot-{phase}.log"
            with log_path.open("wb") as log:
                process = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=log,
                                         stderr=subprocess.STDOUT, timeout=240)
            item.update(exit_code=process.returncode, elapsed_seconds=round(time.monotonic() - before, 3),
                        log=metadata(log_path))
            if not boot_pass(log_path.read_text(errors="replace"), phase, process.returncode):
                raise ValueError(f"boot {phase} failed; inspect full serial log")
            item["status"] = "pass"
            report["checks_passed"].append(f"boot {phase}: kernel, ext4 mount, glibc, exact package DB, POSIX properties, clean unmount")
        command = [str(args.e2fsck), "-fn", str(disk)]
        if args.wsl_distribution:
            prefix = ["wsl", "-d", args.wsl_distribution, "--exec"]
            linux_path = subprocess.check_output(prefix + ["wslpath", "-u", str(disk)], text=True).strip()
            command = prefix + [str(args.e2fsck), "-fn", linux_path]
        before_fsck = metadata(disk)
        result = subprocess.run(command, capture_output=True, timeout=120)
        (out / "fsck.log").write_bytes(result.stdout + result.stderr)
        report["fsck"] = {"command": command, "exit_code": result.returncode,
                          "log": metadata(out / "fsck.log"), "image_unchanged": metadata(disk) == before_fsck}
        if result.returncode != 0 or not report["fsck"]["image_unchanged"]:
            raise ValueError("read-only fsck failed or changed disk")
        report["checks_passed"].append("read-only e2fsck -fn; test image unchanged by check")
        report["disposable_image"] = before_fsck
        report["status"] = "pass"
    except Exception as error:
        report["checks_failed"].append(f"{type(error).__name__}: {error}")
        raise
    finally:
        report["seed_unchanged"] = metadata(seed) == expected
        if not report["seed_unchanged"]:
            report["status"] = "failed"
            report["checks_failed"].append("original seed changed")
        else:
            report["checks_passed"].append("original seed size/SHA-256 unchanged")
        report["elapsed_seconds"] = round(time.monotonic() - started, 3)
        text = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
        (out / "result.json").write_text(text, encoding="utf-8")
        summary = ("# Debian/ext4 host acceptance\n\nStatus: **" + report["status"]
                   + "**. Scope: real Linux inside host system-QEMU; no iPhone claim.\n\n")
        summary += "| Boot | Status | QEMU exit | Seconds |\n|---|---|---|---|\n"
        for boot in report["boots"]:
            summary += f"| {boot['phase']} | {boot['status']} | {boot['exit_code']} | {boot.get('elapsed_seconds', 'not completed')} |\n"
        for label, key in (("Passed", "checks_passed"), ("Failed", "checks_failed"), ("Not run", "checks_not_run")):
            summary += "\n## " + label + "\n\n" + "\n".join("- " + c for c in report[key] or ["None"]) + "\n"
        summary += "\n## Complete commands, versions and hashes\n\n```json\n" + text + "```\n"
        (out / "result.md").write_text(summary, encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("seed", "profile", "modules", "qemu", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--e2fsck", default="e2fsck")
    parser.add_argument("--wsl-distribution", help="existing distribution for read-only fsck on Windows")
    args = parser.parse_args()
    result = check(args)
    print(json.dumps(result))
    raise SystemExit(0 if result["status"] == "pass" else 1)
