#!/usr/bin/env python3
"""Own Cargo wrapper: no source transformation; separate host/target SDK selection."""
import json
import hashlib
import os
from pathlib import Path
import subprocess
import sys


def select_target(args):
    targets = []
    for i, arg in enumerate(args):
        if arg == "--target":
            if i + 1 == len(args):
                raise ValueError("missing --target")
            targets.append(args[i + 1])
        elif arg.startswith("--target="):
            targets.append(arg.split("=", 1)[1])
    if len(targets) > 1 or any(t not in ("aarch64-apple-ios", "aarch64-apple-darwin") for t in targets):
        raise ValueError("unreviewed Rust target")
    return targets[0] if targets else "aarch64-apple-darwin"


def append_record(row, env):
    line = (json.dumps(row, sort_keys=True) + "\n").encode()
    if len(line) > 262144:
        raise ValueError("rustc argv log cap")
    fd = os.open(env["PAIRING_RUSTC_LOG"], os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        if os.fstat(fd).st_size + len(line) > 8 * 1024 * 1024:
            raise ValueError("rustc log cap")
        os.write(fd, line)
    finally:
        os.close(fd)


def option(args, flag):
    values = []
    for i, arg in enumerate(args):
        if arg == flag:
            values.append(args[i + 1])
        elif arg.startswith(flag + "="):
            values.append(arg[len(flag) + 1:])
    return values


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    compiler, *args = sys.argv[1:]
    if Path(compiler).resolve() != Path(os.environ["PAIRING_RUSTC"]).resolve():
        raise ValueError("unexpected compiler passed to wrapper")
    target = select_target(args)
    env = os.environ.copy()
    for name in ("SDKROOT", "MACOSX_DEPLOYMENT_TARGET", "IPHONEOS_DEPLOYMENT_TARGET",
                 "TVOS_DEPLOYMENT_TARGET", "XROS_DEPLOYMENT_TARGET", "WATCHOS_DEPLOYMENT_TARGET"):
        env.pop(name, None)
    env["SDKROOT"] = env["PAIRING_IOS_SDK"] if target == "aarch64-apple-ios" else env["PAIRING_HOST_SDK"]
    if target == "aarch64-apple-ios":
        env["IPHONEOS_DEPLOYMENT_TARGET"] = "18.0"
    row = dict(kind="invocation", compiler=compiler, argv=args, target=target, sdk=env["SDKROOT"],
               cwd=os.getcwd(), deployment=env.get("IPHONEOS_DEPLOYMENT_TARGET"))
    own = option(args, "--crate-name") == ["madeira_rppairing"]
    if own:
        if option(args, "--crate-type") != ["staticlib"] or target != "aarch64-apple-ios":
            raise ValueError("unreviewed own crate invocation")
        sources = [Path(a).resolve() for a in args if a.endswith(".rs")]
        if sources != [Path(env["PAIRING_OWN_SOURCE"])]:
            raise ValueError("unexpected own Rust source")
        out_dir = Path(option(args, "--out-dir")[0])
        if out_dir != Path(env["PAIRING_OWN_OUT_DIR"]):
            raise ValueError("unexpected own Rust output directory")
        cg = option(args, "-C")
        if "save-temps" not in cg and "save-temps=yes" not in cg:
            raise ValueError("own codegen object retention required")
        suffix = [c.split("=", 1)[1] for c in cg if c.startswith("extra-filename=")]
        if len(suffix) != 1 or "/" in suffix[0] or "\\" in suffix[0]:
            raise ValueError("ambiguous own output suffix")
        output = out_dir / ("libmadeira_rppairing" + suffix[0] + ".a")
        if output.exists():
            raise ValueError("own staticlib output was not fresh")
        before = {str(p): digest(p) for p in out_dir.rglob("*.o") if p.is_file()}
        row.update(source=str(sources[0]), source_sha256=digest(sources[0]), output=str(output))
    append_record(row, env)
    if not own:
        os.execve(compiler, [compiler, *args], env)
    result = subprocess.run([compiler, *args], env=env, check=False)
    row.update(kind="completed-staticlib", returncode=result.returncode)
    if result.returncode == 0:
        row["output_sha256"] = digest(output)
        row["fresh_objects"] = [dict(path=str(p), sha256=digest(p), size=p.stat().st_size)
                                for p in sorted(out_dir.rglob("*.o"))
                                if p.is_file() and not p.is_symlink() and
                                before.get(str(p)) != digest(p)]
    append_record(row, env)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
