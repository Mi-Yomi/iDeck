#!/usr/bin/env python3
"""Bounded manual Apple compiler check. No downloads, signing, SDK install or IPA."""
import hashlib
import json
import os
import platform
import re
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    if platform.system() != "Darwin":
        raise SystemExit("Apple SDK required; this check cannot run on Windows")
    if os.environ.get("FREE_QUOTA_VERIFIED") != "true" or os.environ.get("PRIVATE_SOURCE_VERIFIED") != "true":
        raise SystemExit("Manual free-quota/private-repository attestations required")
    expected = os.environ.get("EXPECTED_COMMIT", "")
    if not re.fullmatch(r"[0-9a-f]{40}", expected):
        raise SystemExit("Expected a full reviewed Git commit")
    actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if actual != expected or subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT).strip():
        raise SystemExit("Checkout must be the exact clean reviewed commit")
    out = ROOT / ".work/linux-profile-apple"
    out.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ, TMPDIR=str(out), CLANG_MODULE_CACHE_PATH=str(out / "clang-cache"),
               SWIFT_MODULECACHE_PATH=str(out / "swift-cache"))
    started = time.monotonic()
    steps = []
    def run(label, command):
        remaining = 240 - (time.monotonic() - started)
        if remaining <= 0:
            raise TimeoutError("aggregate compiler budget exhausted")
        done = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, timeout=remaining)
        (out / (label + ".log")).write_text(done.stdout + done.stderr)
        steps.append({"name": label, "exit_code": done.returncode})
        if done.returncode:
            print((done.stdout + done.stderr)[-12000:])
            raise RuntimeError(label + " failed")
        return done.stdout.strip()
    report = {"status": "failed", "commit": actual, "steps": steps,
              "runtime_linked": False, "ipa_created": False, "device_tested": False}
    try:
        report["xcode"] = run("xcode", ["xcodebuild", "-version"])
        report["swift"] = run("swift", ["xcrun", "swiftc", "--version"])
        sdk = run("ios-sdk-path", ["xcrun", "--sdk", "iphoneos", "--show-sdk-path"])
        report["ios_sdk"] = run("ios-sdk-version", ["xcrun", "--sdk", "iphoneos", "--show-sdk-version"])
        source = ROOT / "experiments/linux-guest/ios/LinuxGuestProfile.swift"
        report["source_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
        run("ios-typecheck", ["xcrun", "swiftc", "-typecheck", "-sdk", sdk, "-target", "arm64-apple-ios16.0", str(source)])
        macsdk = run("mac-sdk", ["xcrun", "--sdk", "macosx", "--show-sdk-path"])
        executable = out / "profile-tests"
        run("mac-compile", ["xcrun", "swiftc", "-sdk", macsdk, str(source),
                            str(source.parent / "tests/main.swift"), "-o", str(executable)])
        report["host_test_output"] = run("mac-tests", [str(executable), str(out / "fixtures")])
        report["status"] = "apple_profile_compiler_and_host_checks_pass"
    finally:
        report["elapsed_seconds"] = round(time.monotonic() - started, 3)
        (out / "result.json").write_text(json.dumps(report, indent=2) + "\n")
        print("LINUX_PROFILE_CHECK_RESULT=" + json.dumps(report))


if __name__ == "__main__":
    main()
