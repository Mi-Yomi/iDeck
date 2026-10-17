#!/usr/bin/env python3
"""Offline native regression of the archive-pinned QEMU RCU registry/TLS.

No download, configure, install, payload, or VM. Compile exact registry/grace
period functions and headers from the reviewed release archive with a small
pthread adapter. This does NOT execute the Swift helper or the QEMU backend.
The mandatory Apple gate separately executes the production Foundation wait.
"""
import argparse
import hashlib
import json
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MEMBERS = ("util/rcu.c", "include/qemu/rcu.h", "include/qemu/queue.h",
           "include/qemu/coroutine-tls.h", "include/qemu/notify.h")


def function(source, signature):
    start = source.index(signature)
    begin = source.index("{", start)
    depth = 1
    end = begin + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end] + "\n"


def check(archive, output, cc="cc"):
    lock = json.loads((ROOT / "ipa/native-sources.lock.json").read_text())["archives"][0]
    assert lock["name"] == "QEMU"
    digest = hashlib.sha256()
    with archive.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    if archive.stat().st_size != lock["size"] or digest.hexdigest() != lock["sha256"]:
        raise ValueError("QEMU source archive integrity mismatch")
    output.mkdir(parents=True, exist_ok=False)
    members = {}
    prefix = "qemu-10.0.12-utm/"
    with tarfile.open(archive, "r|xz") as stream:
        for entry in stream:
            name = entry.name.removeprefix(prefix)
            if name not in MEMBERS:
                continue
            if name in members or not entry.isfile() or not 0 < entry.size < 1024 * 1024:
                raise ValueError("invalid source member")
            members[name] = stream.extractfile(entry).read()
    if set(members) != set(MEMBERS):
        raise ValueError("missing QEMU source members")
    for name, data in members.items():
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    source = members["util/rcu.c"].decode()
    header = members["include/qemu/rcu.h"].decode()
    # Preserve the exact TLS definition, registry, wait_for_readers and
    # synchronize_rcu; omit unrelated call_rcu queue/GLib/init/fork machinery.
    algorithm = source[source.index("#define RCU_GP_LOCKED"):source.index("#define RCU_CALL_MIN_SIZE")]
    reader = header[header.index("struct rcu_reader_data {"):header.index("QEMU_DECLARE_CO_TLS")]
    pieces = [algorithm, function(source, "void rcu_register_thread(void)"),
              function(source, "void rcu_unregister_thread(void)"),
              function(header, "static inline void rcu_read_lock(void)"),
              function(header, "static inline void rcu_read_unlock(void)")]
    adapter = ROOT / "tests/native/qemu_rcu_adapter.h"
    harness = ROOT / "tests/native/qemu_rcu_lifetime.c"
    generated = (source[:source.index('#include "qemu/osdep.h"')] +
                 '#include "qemu_rcu_adapter.h"\n' + reader +
                 "QEMU_DECLARE_CO_TLS(struct rcu_reader_data, rcu_reader)\n" +
                 "\n".join(pieces) + '\n#include "qemu_rcu_lifetime.c"\n')
    unit = output / "rcu-regression.c"
    unit.write_text(generated)
    executable = output / "rcu-regression"
    command = [cc, "-std=gnu11", "-O2", "-Wall", "-Wextra", "-Werror", "-pthread",
               "-I", str(output / "include"), "-I", str(adapter.parent), str(unit), "-o", str(executable)]
    subprocess.run(command, check=True, capture_output=True, text=True, timeout=30)
    results = []
    for mode in ("exit-without-unregister", "unregister-control", "retained"):
        done = subprocess.run([str(executable.resolve()), mode], check=True,
                              capture_output=True, text=True, timeout=30)
        results.append({"mode": mode, "exit_code": done.returncode, "output": done.stdout.strip()})
    receipt = {"status": "PASS", "qemu_archive_sha256": digest.hexdigest(),
               "source_sha256": {name: hashlib.sha256(data).hexdigest() for name, data in members.items()},
               "compiled_slice_sha256": hashlib.sha256("\n".join(pieces).encode()).hexdigest(),
               "adapter_sha256": hashlib.sha256(adapter.read_bytes()).hexdigest(),
               "harness_sha256": hashlib.sha256(harness.read_bytes()).hexdigest(), "results": results,
               "scope": "native pinned RCU registry/TLS slice with pthread adapters; not full QEMU/Swift/iOS/device"}
    (output / "result.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--cc", default="cc")
    args = parser.parse_args()
    print(json.dumps(check(args.archive, args.out, args.cc), indent=2))
