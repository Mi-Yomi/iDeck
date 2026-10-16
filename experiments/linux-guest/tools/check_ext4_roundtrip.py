#!/usr/bin/env python3
"""Offline ext4 tool roundtrip on a fresh disposable copy, never a guest PASS.

Separate debugfs opens write/read a file, hard link, symlink, UID/GID and mode.
This checks persisted image representation, not Linux POSIX syscall semantics,
rename/fsync ordering, a mount, two boots, or power-loss durability.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil

from debian_rootfs import debugfs_quote, run, sha256


def check(image, output, debugfs, e2fsck, library_path):
    if image.is_symlink() or not image.is_file() or not 64 * 1024**2 <= image.stat().st_size <= 4 * 1024**3:
        raise ValueError("expected existing bounded regular seed image")
    original_hash = sha256(image)
    output.mkdir(parents=True, exist_ok=False)
    if shutil.disk_usage(output).free < image.stat().st_size + 32 * 1024**2:
        raise ValueError("insufficient space for disposable copy")
    copy = output / "roundtrip.raw"
    shutil.copyfile(image, copy)
    payload = output / "payload.txt"
    payload.write_bytes(b"ideck-ext4-host-roundtrip\n")
    env = {"PATH": os.defpath, "LC_ALL": "C", "LD_LIBRARY_PATH": str(library_path)}
    directory = "/home/ideck/.ideck-host-roundtrip"
    primary, alias, symbolic = (directory + "/" + name for name in ("file", "hard", "symbolic"))
    commands = output / "write.debugfs"
    commands.write_text("\n".join([
        "mkdir " + directory,
        "write " + debugfs_quote(str(payload)) + " " + primary,
        "set_inode_field " + primary + " uid 1000",
        "set_inode_field " + primary + " gid 1000",
        "set_inode_field " + primary + " mode 0100700",
        "ln " + primary + " " + alias,
        "set_inode_field " + primary + " links_count 2",
        "symlink " + symbolic + " file",
    ]) + "\n")
    run([debugfs, "-w", "-f", commands, copy], env=env)
    # Each following command opens/closes the persisted image independently.
    def read(command):
        return run([debugfs, "-R", command, copy], env=env).stdout
    if read("cat " + primary) != payload.read_text() or read("cat " + alias) != payload.read_text():
        raise ValueError("persisted file/hardlink content differs")
    first, second = read("stat " + primary), read("stat " + alias)
    if (re.search(r"Inode:\s+(\d+)", first).group(1) != re.search(r"Inode:\s+(\d+)", second).group(1)
            or not re.search(r"User:\s+1000\s+Group:\s+1000\b", first)
            or not re.search(r"Mode:\s+0700\b", first)
            or not re.search(r"Links:\s+2\b", first)
            or 'Fast link dest: "file"' not in read("stat " + symbolic)):
        raise ValueError("persisted link/UID/GID/mode differs")
    run([e2fsck, "-fn", copy], env=env)
    if sha256(image) != original_hash:
        raise ValueError("seed changed during host roundtrip")
    receipt = {"schema": 1, "seed_sha256": original_hash,
               "result": "pass", "seed_unchanged": True,
               "checks": ["file content across tool reopen", "hardlink same inode/content/link count",
                          "symlink target", "UID/GID1000 mode0700", "e2fsck -fn"],
               "scope": "unmounted disposable ext4 image tool roundtrip",
               "guest_mount_boot_posix_syscalls_and_power_loss": "not tested"}
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("image", "output", "debugfs", "e2fsck", "library-path"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(check(args.image.absolute(), args.output.absolute(), args.debugfs.absolute(),
                           args.e2fsck.absolute(), args.library_path.absolute()), indent=2))
