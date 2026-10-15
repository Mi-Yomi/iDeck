#!/usr/bin/env python3
"""Fail early on omitted inputs or an unintended Linux branch/checkout."""
import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINUX_BRANCH = "codex/linux-guest-feasibility-20261015"


def validate(env, head, dirty):
    errors = []
    workflow = env.get("IDECK_WORKFLOW_ID", "")
    for key, value in sorted(env.items()):
        if key.startswith("EXPECTED_"):
            length = 40 if key.endswith("COMMIT") else 64
            if not re.fullmatch(r"[0-9a-f]{%d}" % length, value):
                errors.append(f"{key}: enter the reviewed {length}-character lowercase Git SHA/hash; it is required")
    for key in ("FREE_QUOTA_VERIFIED", "PRIVATE_SOURCE_VERIFIED"):
        if env.get(key) != "true":
            errors.append(f"{key}: current manual verification is required")
    if workflow.startswith("ideck-linux-"):
        if env.get("CM_BRANCH") != LINUX_BRANCH:
            errors.append(f"Select branch {LINUX_BRANCH} before selecting the Linux workflow; main is not the Linux source")
        if env.get("CM_REPO_SLUG", "").lower() != "mi-yomi/ideck":
            errors.append("Expected the private Mi-Yomi/iDeck repository")
        if env.get("CM_COMMIT") != head or env.get("EXPECTED_COMMIT") != head:
            errors.append("CM_COMMIT and EXPECTED_COMMIT must both match the actual checkout HEAD")
        if dirty:
            errors.append("The iDeck transport checkout must be clean")
    return errors


def main():
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT).strip())
    errors = validate(os.environ, head, dirty)
    report = {"status": "rejected" if errors else "accepted", "workflow": os.environ.get("IDECK_WORKFLOW_ID"),
              "branch": os.environ.get("CM_BRANCH"), "checkout_commit": head, "errors": errors}
    out = ROOT / ".work/build-request"
    out.mkdir(parents=True, exist_ok=True)
    (out / "result.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("IDECK_BUILD_REQUEST=" + json.dumps(report))
    if errors:
        raise SystemExit("Build request rejected before compilation/downloads; correct branch, workflow and inputs")


if __name__ == "__main__":
    main()
