#!/usr/bin/env python3
"""Pinned outer supervisor: bounded child session, exact evidence, success-only reuse."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
import zipfile

SELF_PIN = 'fc3c4db2be6b3a9463a26b8fb6061e0e558a3b6ddee5b3c90218d19a4b976e9c'
LOCK_PIN = '9466ed56786ad238db47d5d483aadee543873e03518f346f1e5be00f66e4c156'
ROOT = Path(__file__).resolve().parents[1]
MIB = 1024 * 1024
AGGREGATE_SECONDS = 1380
FINALIZATION_RESERVE_SECONDS = 60
EVIDENCE_NAMES = {
    'pairing-source-lock.json', 'commands.json', 'result.json', 'tool-downloads.json',
    'installed-toolchain-provenance.json', 'rust-std-members.json', 'crate-downloads.json',
    'build-environment.json', 'rustc-wrapper-source.py', 'rustc-argv.jsonl',
    'archive-raw-members.json', 'archive-members.json', 'archive-raw-symbols.json', 'ring-members.json',
    'ring-prevalidation-diagnostics.json', 'validation-failure-context.json',
    'own-rust-object-binding.json', 'api_probe.c', 'api_probe.dylib',
    'native-link-closure.json', 'all-crate-notices.json', 'output-manifest.json',
}


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(MIB), b''):
            h.update(b)
    return h.hexdigest()


def require(value, message):
    if not value:
        raise RuntimeError(message)


def self_digest(raw):
    normal, count = re.subn(rb"(?m)^SELF_PIN = '[^']*'$", b"SELF_PIN = 'SELF_SHA256'", raw)
    require(count == 1, 'ambiguous supervisor self pin')
    return hashlib.sha256(normal).hexdigest()


def remove_reusable(work, out):
    for p in (out / 'pairing-ios-prefix.zip', out / 'pairing-ios-prefix.zip.part'):
        p.unlink(missing_ok=True)
    p = work / 'output'
    if p.is_symlink():
        p.unlink()
    elif p.exists():
        shutil.rmtree(p)


def stop_owned_session(process):
    # Child commands create new process groups but keep this uniquely owned session.
    try:
        pids = subprocess.check_output(['/bin/ps', '-ax', '-o', 'pid='], timeout=5, text=True)
        groups = set()
        for value in pids.split():
            try:
                pid = int(value)
                if os.getsid(pid) == process.pid:
                    groups.add(os.getpgid(pid))
            except ProcessLookupError:
                pass
        for pgid in groups:
            try:
                os.killpg(pgid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=5)


def exact_output(work):
    manifest = json.loads((work / 'evidence/output-manifest.json').read_text())
    output = work / 'output'
    actual = {str(p.relative_to(output)) for p in output.rglob('*') if p.is_file() or p.is_symlink()}
    require(actual == set(manifest), 'output inventory differs from validated manifest')
    require('libmadeira_rppairing.a' in actual and 'MadeiraRPPairing.h' in actual,
            'missing genuine reusable library/header')
    total = 0
    for name, row in manifest.items():
        p = output / name
        require(not p.is_symlink() and p.resolve().is_relative_to(output.resolve()) and p.is_file(),
                'unsafe output path/type')
        require(p.stat().st_size == row['size'] and digest(p) == row['sha256'], 'output bytes changed')
        total += row['size']
    require(total <= 768 * MIB, 'reusable output cap')
    return manifest


def package_success(work, out, report, deadline):
    manifest = exact_output(work)
    temporary = out / 'pairing-ios-prefix.zip.part'
    with zipfile.ZipFile(temporary, 'x', zipfile.ZIP_DEFLATED) as z:
        for name in sorted(manifest):
            require(time.monotonic() < deadline, 'aggregate packaging deadline')
            z.write(work / 'output' / name, name)
        z.writestr('validated-output-manifest.json', json.dumps(manifest, indent=2) + '\n')
    require(time.monotonic() < deadline and temporary.stat().st_size <= 768 * MIB, 'packaged output cap/deadline')
    # Keep the reusable ZIP unpublished until evidence and all success gates finish.
    report['reusable_archive'] = dict(name='pairing-ios-prefix.zip',
                                      sha256=digest(temporary),
                                      size=temporary.stat().st_size)


def package_evidence(work, out, report):
    # Exact allowlist; never collect arbitrary HOME/cache/build output or credentials.
    candidates = []
    for name in EVIDENCE_NAMES:
        candidates.append((work / 'evidence' / name, 'Evidence/' + name, 128 * MIB if name == 'api_probe.dylib' else 8 * MIB))
    commands = work / 'evidence/commands.json'
    if commands.is_file() and not commands.is_symlink() and commands.stat().st_size <= MIB:
        for row in json.loads(commands.read_text()):
            name = row.get('log', '')
            require(re.fullmatch(r'[0-9]{3}-[a-z0-9-]+\.log', name), 'unsafe evidence log name')
            candidates.append((work / 'evidence' / name, 'Logs/' + name, 8 * MIB))
    candidates.append((out / 'supervisor.log', 'Logs/supervisor.log', 8 * MIB))
    for name in ('run_pairing_control.py', 'pairing_control.py', 'pairing_validate.py',
                 'tool_provenance.py', 'rustc_wrapper.py', 'pairing-source-lock.json'):
        candidates.append((ROOT / 'ci' / name, 'Control/' + name, MIB))
    omitted, total = [], 0
    with zipfile.ZipFile(out / 'pairing-evidence.zip.part', 'x', zipfile.ZIP_DEFLATED) as z:
        for p, name, cap in sorted(candidates, key=lambda x: x[1]):
            if not p.exists() and not p.is_symlink():
                continue
            if p.is_symlink() or not p.is_file() or not p.resolve().is_relative_to(ROOT.resolve()):
                omitted.append(dict(path=name, reason='unsafe file type/path')); continue
            size = p.stat().st_size
            if size > cap or total + size > 256 * MIB:
                omitted.append(dict(path=name, reason='evidence size cap')); continue
            total += size
            z.write(p, name)
        z.writestr('result.json', json.dumps(report, indent=2) + '\n')
        z.writestr('evidence-omissions.json', json.dumps(omitted, indent=2) + '\n')
    (out / 'pairing-evidence.zip.part').replace(out / 'pairing-evidence.zip')
    (out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')


def main():
    require(sys.platform == 'darwin', 'approved macOS runner required')
    raw = Path(__file__).read_bytes()
    require(self_digest(raw) == SELF_PIN, 'supervisor source self pin mismatch')
    require(os.environ.get('EXPECTED_SUPERVISOR_SHA256') == hashlib.sha256(raw).hexdigest(),
            'manual supervisor digest mismatch')
    require(os.environ.get('EXPECTED_LOCK_SHA256') == LOCK_PIN and
            digest(ROOT / 'ci/pairing-source-lock.json') == LOCK_PIN, 'manual lock digest mismatch')
    require(all(os.environ.get(k) == 'true' for k in ('FREE_QUOTA_VERIFIED', 'PRIVATE_SOURCE_VERIFIED')),
            'fresh free-quota/private-source verification required')
    stage = os.environ.get('PAIRING_STAGE', 'preflight')
    require(stage in ('preflight', 'rust', 'pairing'), 'unreviewed stage')
    lock = json.loads((ROOT / 'ci/pairing-source-lock.json').read_text())
    for name, expected in lock['control_hashes'].items():
        require(digest(ROOT / 'ci' / name) == expected, 'inner source pin mismatch')
    work, out = ROOT / '.work/pairing-control', ROOT / '.work/pairing-control-artifacts'
    require(not work.exists() and not work.is_symlink() and not out.exists() and not out.is_symlink(),
            'fresh control/artifact roots required')
    require(work.parent.resolve() == work.parent, 'symlink work parent')
    out.mkdir(parents=True)
    started, process = time.monotonic(), None
    def interrupted(signum, frame):
        raise TimeoutError('outer deadline or termination signal ' + str(signum))
    for sig in (signal.SIGALRM, signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, interrupted)
    signal.setitimer(signal.ITIMER_REAL, AGGREGATE_SECONDS)
    deadline = started + AGGREGATE_SECONDS
    report = dict(status='failed', stage=stage, target_executed=False, pairing_called=False,
                  supervisor_sha256=hashlib.sha256(raw).hexdigest(), lock_sha256=LOCK_PIN,
                  aggregate_seconds=1380, child_seconds=1320, finalization_reserve_seconds=60, provider_minutes=25,
                  python_version=sys.version, python_executable=sys.executable)
    try:
        env = dict(PATH='/usr/bin:/bin:/usr/sbin:/sbin', LC_ALL='C', LANG='C', PAIRING_SUPERVISED='1')
        if os.environ.get('DEVELOPER_DIR'):
            env['DEVELOPER_DIR'] = os.environ['DEVELOPER_DIR']
        argv = [sys.executable, ROOT / 'ci/pairing_control.py', stage,
                '--source-zip', ROOT / 'pairing-source-inputs.zip', '--work', work,
                '--expected-lock-sha256', LOCK_PIN, '--aggregate-deadline', str(deadline - FINALIZATION_RESERVE_SECONDS)]
        report['argv'] = list(map(str, argv))
        with (out / 'supervisor.log').open('xb') as log:
            process = subprocess.Popen(argv, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                                       stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            report['owned_session'] = process.pid
            while process.poll() is None:
                require(time.monotonic() < deadline, 'outer 23-minute deadline')
                require((out / 'supervisor.log').stat().st_size <= 8 * MIB, 'outer log cap')
                time.sleep(0.25)
        require((out / 'supervisor.log').stat().st_size <= 8 * MIB, 'outer fast-exit log cap')
        require(process.returncode == 0, 'inner control failed')
        inner = json.loads((work / 'evidence/result.json').read_text())
        require(inner['status'] == 'passed' and inner['stage'] == stage, 'inner result mismatch')
        report['inner'] = inner
        if stage == 'pairing':
            package_success(work, out, report, deadline)
        require(time.monotonic() < deadline, 'aggregate deadline before success')
        report['status'] = 'passed-source-control-only'
    except BaseException as error:
        report['failure'] = str(error)
    finally:
        # Keep the outer deadline armed through cleanup, evidence and publication.
        if process:
            try:
                stop_owned_session(process)
            except Exception as error:
                report.update(status='failed', cleanup_failure=str(error))
        if report['status'] != 'passed-source-control-only':
            remove_reusable(work, out)
        report['elapsed_seconds'] = round(time.monotonic() - started, 3)
        try:
            require(time.monotonic() < deadline, 'no remaining evidence-finalization budget')
            package_evidence(work, out, report)
            require(report['status'] != 'passed-source-control-only' or time.monotonic() < deadline,
                    'aggregate evidence-packaging deadline')
            if report['status'] == 'passed-source-control-only' and stage == 'pairing':
                (out / 'pairing-ios-prefix.zip.part').replace(out / 'pairing-ios-prefix.zip')
        except BaseException as error:
            report.update(status='failed', evidence_failure=str(error))
            remove_reusable(work, out)
            (out / 'pairing-evidence.zip.part').unlink(missing_ok=True)
            (out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
            with zipfile.ZipFile(out / 'pairing-evidence.zip', 'w', zipfile.ZIP_DEFLATED) as z:
                z.writestr('result.json', json.dumps(report, indent=2) + '\n')
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
    print('PAIRING_CONTROL_RESULT=' + json.dumps(report, sort_keys=True), flush=True)
    return 0 if report['status'] == 'passed-source-control-only' else 1


if __name__ == '__main__':
    raise SystemExit(main())
