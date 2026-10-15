#!/usr/bin/env python3
"""Bounded fresh-job LLVM 15 target prefix; no target execution or installation."""
from __future__ import annotations
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shlex
import shutil
import signal
import stat
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / '.work/llvm-target-source'
BUILD = SOURCE / '.work/llvm-target-control'
IMPORT = SOURCE / '.work/imported-llvm-native'
OUT = ROOT / '.work/llvm-target-artifacts'
RUN = ROOT / '.work/llvm-target-run'
MADEIRA = '279fd0f83170425db002fe25d6bd62f6355f497d'
LLVM = '8dfdcc7b7bf66834a761bd8de445840ef68e4d1a'
MIB = 1024 * 1024
MAX_FILE = 256 * MIB
MAX_BUNDLE = 768 * MIB
MAX_ZIP = 512 * MIB
MAX_FILES = 16000
AGGREGATE_SECONDS = 1380
FINALIZE_RESERVE = 60
PINS = {
    'llvm-core-control.sh': 'eba4f906412aa883ee37ed9257a83f9872f719fa705fe36b4a209bd34a7a46a5',
    'llvm_control_support.py': '872247fd633e950846533d0548d19c553dd799125bbeaf1c65d704cbddf97989',
    'llvm-source-lock.json': '90b59a3cd553e394a32f361e8493aaaa799d7de83beb1a9df9b33ef7216f6479',
    'run_llvm_control.py': '324dd3d8bc30c716c9d12caf656730639930d4a49d7534156add2e732cbd581e',
    'reassemble_llvm_target_artifact.py': 'd7b3116c6a4649060c91b8467a7a05c923611b3fcf36b51bc2b78a94dfd5d3db',
}
LOCK_NAME = 'llvm-target-input-lock.json'
SCOPE = ('LLVM 15.0.7 static-library control only: the exact 34 LLVM archives and public headers '
         'for arm64 iOS 18.0 / SDK 26.5. The verified macOS llvm-tblgen runs only for host generation. '
         'No iOS executable is run. No converter/MSC validation, DXMT combined link, app, runtime, '
         'IPA, device test, package installation, explicit signing or SDK export is claimed.')
MANIFESTS = ('manifest.json', 'manifests/source.json', 'manifests/source-lock.json',
    'manifests/source-overlay.json', 'manifests/commands.json', 'manifests/preflight.json',
    'manifests/configuration.json', 'manifests/native-import.json', 'manifests/outputs.json',
    'manifests/archive-members.json', 'manifests/public-headers.json',
    'manifests/compiled-sources.json', 'manifests/notices.json')
CONFIGURATION = ('evidence/CMakeCache.txt', 'evidence/compile_commands.json',
    'evidence/CMakeFiles/CMakeConfigureLog.yaml', 'evidence/include/llvm/Config/config.h',
    'evidence/include/llvm/Config/llvm-config.h', 'evidence/include/llvm/Config/abi-breaking.h')
COMPILER_EVIDENCE = tuple('evidence/CMakeFiles/4.3.4/' + s for s in
    ('CMakeCCompiler.cmake', 'CMakeCXXCompiler.cmake', 'CMakeASMCompiler.cmake', 'CMakeSystem.cmake'))
LOG_LABELS = frozenset(('host-arch host-cpu host-os developer-dir xcode-version macosx-version '
    'macosx-path iphoneos-version iphoneos-path find-clang find-clangxx find-ar find-ranlib find-ld '
    'find-libtool clang-version make-version cmake-version python-version linker-version madeira-root '
    'madeira-pin madeira-clean llvm-root llvm-pin llvm-clean llvm-untracked llvm-ignored disk-space '
    'llvm-source-tree configure build imported-tblgen-version').split())
PROVENANCE = ('artifact-manifest.json', 'manifest.json', 'manifests/source.json',
    'manifests/preflight.json', 'manifests/native-macho.json', 'manifests/configuration.json')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def safe_name(name):
    require(isinstance(name, str), 'Path must be text')
    p = PurePosixPath(name)
    require(name and str(p) == name and not p.is_absolute() and '..' not in p.parts
            and not any(ord(c) < 32 or ord(c) == 127 or c in '\\:;$' for c in name), 'Unsafe member path')
    return name


def safe(path, cap=MAX_FILE, directory=False, fresh=False):
    p = Path(path).absolute()
    require('..' not in p.parts and not any(q.is_symlink() for q in (p, *p.parents)), 'Unsafe/symlink path')
    if fresh:
        require(not p.exists(), 'Fresh destination required: ' + p.name)
    elif directory:
        require(p.is_dir(), 'Missing directory')
    else:
        s = p.stat()
        require(stat.S_ISREG(s.st_mode) and s.st_nlink == 1 and s.st_size <= cap, 'Unsafe/oversized regular file')
    return p


def digest(path, cap=MAX_FILE):
    h = hashlib.sha256()
    with safe(path, cap).open('rb') as stream:
        for data in iter(lambda: stream.read(MIB), b''):
            h.update(data)
    return h.hexdigest()


def unique(pairs):
    obj = {}
    for k, v in pairs:
        require(k not in obj, 'Duplicate JSON key')
        obj[k] = v
    return obj


def read_json(path, cap=64*MIB):
    return json.loads(safe(path, cap).read_text(), object_pairs_hook=unique)


def write_json(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, sort_keys=True) + '\n')


def hex64(value):
    require(isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value), 'Exact independently verified SHA256 required')
    return value


def verify_hash(path, expected):
    require(digest(path) == hex64(expected), 'Reviewed file hash mismatch: ' + Path(path).name)


def load_module(name):
    path = ROOT / 'ci' / name
    verify_hash(path, PINS[name])
    if name == 'llvm_control_support.py':
        verify_hash(ROOT / 'ci/llvm-source-lock.json', PINS['llvm-source-lock.json'])
    spec = importlib.util.spec_from_file_location('target_' + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    before = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = before
    return module


def reviewed_inputs(environ=None):
    env = os.environ if environ is None else environ
    for name, pin in PINS.items():
        verify_hash(ROOT / 'ci' / name, pin)
    verify_hash(Path(__file__), env.get('EXPECTED_LLVM_TARGET_WRAPPER_SHA256'))
    verify_hash(ROOT / 'ci' / LOCK_NAME, env.get('EXPECTED_LLVM_TARGET_INPUT_LOCK_SHA256'))
    lock = read_json(ROOT / 'ci' / LOCK_NAME, MIB)
    require(lock.get('schema') == 1 and lock.get('llvm_commit') == LLVM and lock.get('madeira_commit') == MADEIRA,
            'Wrong target input source identity')
    require(lock.get('status') == 'verified-original-native-producer',
            'BLOCKED: worker-verified successful original native ZIP and manifest identities are not frozen')
    native = lock.get('native', {})
    require(native.get('name') == 'llvm-tblgen-native.zip' and native.get('producer_manifest_path') == 'artifact-manifest.json',
            'Wrong native artifact contract')
    for k in ('zip_sha256', 'artifact_manifest_sha256', 'evidence_zip_sha256'):
        hex64(native.get(k))
    require(type(native.get('zip_bytes')) is int and 0 < native['zip_bytes'] <= 192*MIB, 'Invalid native ZIP size')
    require(re.fullmatch('[0-9a-f]{24}', native.get('build_id', '')) and
            re.fullmatch('[0-9a-f]{40}', native.get('bootstrap_commit', '')) and
            re.fullmatch('[0-9a-f]{24}', native.get('app_id', '')) and native.get('source_lock_sha256') == PINS['llvm-source-lock.json'],
            'Exact successful producer identity required')
    route = lock.get('transport', {})
    if route.get('kind') == 'original':
        require(route == {'kind': 'original', 'path': 'ci/llvm-target-native-input/llvm-tblgen-native.zip'}, 'Wrong original transport path')
    else:
        require(route.get('kind') == 'schema2-chunks' and route.get('path') == 'ci/llvm-target-native-chunks'
                and set(route) == {'kind', 'path', 'manifest_sha256'}, 'Unsupported transport route')
        hex64(route['manifest_sha256'])
        require(native['zip_bytes'] <= 128*MIB, 'Reviewed chunk transport caps original ZIPs at 128 MiB')
    return lock


def environment():
    env = {'PATH': '/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin', 'HOME': str(RUN / 'home'),
        'TMPDIR': str(RUN / 'tmp'), 'LC_ALL': 'C', 'LANG': 'C', 'TZ': 'UTC', 'JOBS': '4',
        'GIT_TERMINAL_PROMPT': '0', 'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null',
        'GIT_LFS_SKIP_SMUDGE': '1', 'PYTHONNOUSERSITE': '1', 'PYTHONDONTWRITEBYTECODE': '1'}
    for key in ('DEVELOPER_DIR', 'EXPECTED_LLVM_TARGET_WRAPPER_SHA256', 'EXPECTED_LLVM_TARGET_INPUT_LOCK_SHA256'):
        if os.environ.get(key):
            env[key] = os.environ[key]
    return env


def target_python_invocation():
    """Preserve the already running provider interpreter; never resolve a second python3."""
    selected = safe(Path(sys.executable).resolve(strict=True))
    candidate = shutil.which('python3', path=environment()['PATH'])
    argv = [str(selected), '-I', str(ROOT / 'ci/llvm_control_support.py'),
            str(SOURCE), str(BUILD), 'target', str(IMPORT)]
    accepted = sys.platform == 'darwin' and sys.version_info[:3] == (3, 12, 7)
    record = {'schema': 1, 'status': 'passed' if accepted else 'rejected',
        'invoked_interpreter': sys.executable, 'resolved_interpreter': str(selected),
        'interpreter_sha256': digest(selected), 'observed_version': sys.version,
        'observed_version_info': list(sys.version_info[:3]), 'observed_platform': sys.platform,
        'required_version': [3, 12, 7], 'sanitized_path': environment()['PATH'],
        'sanitized_path_python3_candidate': candidate, 'path_candidate_executed': False,
        'helper_argv': argv,
        'selection': 'running-wrapper-sys.executable; no shell PATH re-resolution'}
    write_json(OUT / 'python-selection.json', record)
    require(accepted, 'macOS with Python3.12.7 required for wrapper and unchanged helper')
    return argv


class Commands:
    def __init__(self):
        self.steps = []

    def run(self, label, *args, cwd=ROOT, seconds=None):
        require(re.fullmatch('[a-z0-9-]+', label) and label not in [x['label'] for x in self.steps], 'Unsafe/duplicate step')
        path = OUT / (label + '.log')
        started = time.monotonic()
        record = {'label': label, 'argv': [str(a) for a in args], 'cwd': str(cwd), 'status': 'attempted', 'exit_code': None}
        self.steps.append(record)
        write_json(OUT / 'steps.json', self.steps)
        proc = None
        try:
            with path.open('xb') as stream:
                # Same process group as the bounded worker. The supervisor cleans up
                # remaining group members; independently detached sessions are not covered.
                proc = subprocess.Popen(args, cwd=cwd, env=environment(), stdin=subprocess.DEVNULL,
                                        stdout=stream, stderr=subprocess.STDOUT)
                while proc.poll() is None:
                    if time.monotonic() - started > (seconds or AGGREGATE_SECONDS) or path.stat().st_size > 64*MIB:
                        record['exit_code'] = 124
                        proc.kill()
                        proc.wait()
                        raise ValueError('Step timeout/log cap: ' + label)
                    time.sleep(.1)
            record['exit_code'] = proc.returncode
            require(path.stat().st_size <= 64*MIB, 'Step log exceeds cap after completion: ' + label)
            require(proc.returncode == 0, label + ' failed: exit ' + str(proc.returncode))
            record['status'] = 'passed'
            return path.read_text(errors='replace') if path.stat().st_size < MIB else ''
        except BaseException as error:
            record['status'] = 'failed'
            record['failure'] = str(error)
            if record['exit_code'] is None:
                record['exit_code'] = proc.poll() if proc else None
            if proc is not None and proc.poll() is None:
                proc.kill()
                proc.wait()
            raise
        finally:
            record['seconds'] = round(time.monotonic()-started, 3)
            write_json(OUT / 'steps.json', self.steps)


def transport_native(lock):
    route, native = lock['transport'], lock['native']
    if route['kind'] == 'original':
        source = safe(ROOT / route['path'], 192*MIB)
        target = safe(RUN / native['name'], fresh=True)
        shutil.copyfile(source, target)
    else:
        transport = load_module('reassemble_llvm_target_artifact.py')
        target = RUN / native['name']
        obj = transport.reassemble(ROOT / route['path'], route['manifest_sha256'], target)
        require(obj['original'] == {'name': native['name'], 'size': native['zip_bytes'], 'sha256': native['zip_sha256']},
                'Chunk original identity differs from independent native lock')
        provenance = obj['provenance']
        require(provenance['stage'] == 'llvm-native' and provenance['app_id'] == native['app_id']
                and provenance['input_lock_sha256'] == native['source_lock_sha256']
                and provenance['build_id'] == native['build_id'] and provenance['bootstrap_commit'] == native['bootstrap_commit']
                and provenance['source_commit'] == LLVM and provenance['producer_manifest_path'] == 'artifact-manifest.json'
                and provenance['producer_manifest_sha256'] == native['artifact_manifest_sha256']
                and provenance['evidence_zip_sha256'] == native['evidence_zip_sha256'], 'Chunk provenance mismatch')
    require(target.stat().st_size == native['zip_bytes'], 'Native ZIP size mismatch')
    verify_hash(target, native['zip_sha256'])
    return target


def allowed(name, libraries):
    safe_name(name)
    if name in MANIFESTS + CONFIGURATION + COMPILER_EVIDENCE:
        return True
    if name in {'prefix/lib/lib' + lib + '.a' for lib in libraries}:
        return True
    if re.fullmatch(r'prefix/include/(?:llvm|llvm-c)/(?:[A-Za-z0-9_.+-]+/)*[A-Za-z0-9_.+-]+', name):
        return True  # Exact independently linked public-header inventory required below.
    if name.startswith('notices/'):
        return True  # Exact full notice inventory and source linkage required below.
    if name.startswith('logs/') and name.endswith('.log') and name[5:-4] in LOG_LABELS:
        return True
    return bool(re.fullmatch(r'evidence/(?:[A-Za-z0-9_.+-]+/)*CMakeFiles/(?:llvm-tblgen|LLVM[A-Za-z0-9_]+)\.dir/(?:link\.txt|flags\.make|build\.make)', name))


def file_row(root, name):
    path = safe(root / safe_name(name))
    return {'path': name, 'bytes': path.stat().st_size, 'sha256': digest(path)}


def inventory(root, rows, predicate):
    require(isinstance(rows, list) and 0 < len(rows) <= MAX_FILES, 'Invalid inventory count')
    names, folded = set(), set()
    for row in rows:
        name = safe_name(row['path'])
        require(name.casefold() not in folded and predicate(name), 'Duplicate or disallowed inventory file: ' + name)
        folded.add(name.casefold())
        names.add(name)
        actual = file_row(root, name)
        require(all(row.get(k) == v for k, v in actual.items()), 'Inventory hash/size mismatch: ' + name)
    return names


def validate_target(root, support=None):
    root = safe(root, directory=True)
    support = support or load_module('llvm_control_support.py')
    libraries = support.LOCK['target_libraries']
    require(len(libraries) == 34 and len(set(libraries)) == 34, 'Exactly 34 pinned libraries required')
    manifest = read_json(root / 'manifest.json')
    expected = {'schema': 1, 'stage': 'target', 'status': 'complete', 'llvm_commit': LLVM,
        'madeira_commit': MADEIRA, 'source_lock_sha256': PINS['llvm-source-lock.json'],
        'helper_sha256': PINS['llvm_control_support.py'], 'jobs': 4, 'deployment_target': '18.0',
        'sdk_version': '26.5', 'xcode_version': '26.6', 'cmake_version': '4.3.4', 'target_libraries': libraries}
    require(all(manifest.get(k) == v for k, v in expected.items()), 'Target helper identity/configuration mismatch')
    require(all(manifest.get(k) is False for k in ('target_binaries_run', 'sdk_copied',
        'package_install_performed', 'explicit_signing_performed')), 'Target scope mismatch')
    for name, key in (('outputs', 'outputs_sha256'), ('source', 'source_manifest_sha256'), ('configuration', 'configuration_sha256')):
        verify_hash(root / ('manifests/' + name + '.json'), manifest[key])
    names = inventory(root, read_json(root / 'manifests/outputs.json'), lambda n: allowed(n, libraries))
    names |= {'manifest.json', 'manifests/outputs.json'}
    require(set(MANIFESTS + CONFIGURATION + COMPILER_EVIDENCE) <= names, 'Missing target/source/compiler evidence')
    verify_hash(root / 'manifests/source-lock.json', PINS['llvm-source-lock.json'])
    require(read_json(root / 'manifests/source-overlay.json') == support.LOCK['patch'], 'Wrong target-only source overlay')
    preflight = read_json(root / 'manifests/preflight.json')
    require(preflight.get('status') == 'passed' and preflight['versions']['iphoneos'] == '26.5', 'Incomplete real toolchain preflight')
    configuration = read_json(root / 'manifests/configuration.json')
    expected_config = support.cmake_definitions('target', preflight['tools'], preflight['sdk_paths']['iphoneos'],
                                               configuration.get('CMAKE_INSTALL_PREFIX'), configuration.get('LLVM_TABLEGEN'))
    # Python interpreter paths may differ in the consuming verifier; producer identity is already hashed.
    expected_config['Python3_EXECUTABLE'] = preflight['python_path']
    require(configuration == expected_config, 'Target configuration drift or bypass')
    require(Path(configuration['CMAKE_CXX_COMPILER']).name == 'clang++', 'C++ driver identity lost')
    system = (root / 'evidence/CMakeFiles/4.3.4/CMakeSystem.cmake').read_text()
    require('set(CMAKE_CROSSCOMPILING "TRUE")' in system and 'set(CMAKE_SYSTEM_NAME "iOS")' in system,
            'Actual configure did not establish iOS cross-compilation')
    cache = (root / 'evidence/CMakeCache.txt').read_text()
    entries = dict(re.findall(r'^([^#/:][^:]*):[^=]+=(.*)$', cache, re.M))
    require(all(entries.get(k) == v for k, v in configuration.items()), 'Actual cache differs from requested configuration')
    require(all(entries.get(k) == '1' for k in ('HAVE_CXX_ATOMICS_WITHOUT_LIB', 'HAVE_CXX_ATOMICS64_WITHOUT_LIB')),
            'Actual compiler/link atomic checks missing')
    require(not any(k.startswith('CMAKE_POLICY_') or k.endswith('_COMPILER_WORKS') and v not in ('1', 'TRUE')
                    for k, v in configuration.items()), 'Compiler/policy bypass')
    headers = inventory(root, read_json(root / 'manifests/public-headers.json'), lambda n: n.startswith('prefix/include/'))
    require(headers == {n for n in names if n.startswith('prefix/include/')}, 'Undeclared/missing public header')
    require({'prefix/include/llvm/Config/llvm-config.h', 'prefix/include/llvm/IR/Intrinsics.inc',
             'prefix/include/llvm-c/Core.h'} <= headers, 'Incomplete public headers')
    require(all(r.get('origin') in ('source', 'generated') for r in read_json(root / 'manifests/public-headers.json')), 'Missing header origin')
    notices = inventory(root, read_json(root / 'manifests/notices.json'), lambda n: n.startswith('notices/'))
    require(notices == {n for n in names if n.startswith('notices/')} and 'notices/LLVM-LICENSE.TXT' in notices,
            'Undeclared/missing notice')
    sources = read_json(root / 'manifests/source.json')
    require(sources.get('schema') == 1 and sources.get('llvm_commit') == LLVM, 'Wrong source closure')
    source_rows = sources['files']
    require(isinstance(source_rows, list) and 0 < len(source_rows) <= support.LOCK['source_copy_limit_files'], 'Invalid source closure count')
    source_map = {safe_name(r['path']): r for r in source_rows}
    require(len(source_map) == len(source_rows), 'Duplicate source provenance')
    for guard in support.LOCK['source_guards']:
        require(source_map.get(guard['path'], {}).get('sha256') == guard['sha256'], 'Pinned source configuration/notice drift')
    for header in read_json(root / 'manifests/public-headers.json'):
        rel = header['path'][len('prefix/include/'):]
        require(Path(rel).name != 'config.h', 'Private config.h is not a public header')
        if header['origin'] == 'source':
            require(source_map.get('llvm/include/' + rel, {}).get('sha256') == header['sha256'],
                    'Public source header differs from exact upstream source')
        else:
            require(Path(rel).suffix in ('.h', '.def', '.inc', '.gen'), 'Unreviewed generated header type')
            evidence = 'evidence/include/' + rel
            if evidence in names:
                require(digest(root / evidence) == header['sha256'], 'Generated public config differs from actual configure evidence')
    compiled = read_json(root / 'manifests/compiled-sources.json')
    require(isinstance(compiled, list) and 0 < len(compiled) <= 10000, 'Missing actual compiled sources')
    compile_commands = read_json(root / 'evidence/compile_commands.json')
    require(isinstance(compile_commands, list) and len(compile_commands) <= 40000, 'Invalid compile commands')
    commands = {}
    for item in compile_commands:
        args = item.get('arguments') or shlex.split(item['command'])
        if '-o' in args and args.index('-o') + 1 < len(args):
            key = str((Path(item['directory']) / args[args.index('-o')+1]).absolute())
            require(key not in commands, 'Repeated actual compile command output')
            commands[key] = (args, item['file'])
    objects, object_paths = {}, set()
    for row in compiled:
        source = safe_name(row['source'])
        object_path = safe_name(row['object'])
        require(object_path not in object_paths, 'Repeated compiled object')
        object_paths.add(object_path)
        notice = 'notices/compiled-source/' + source
        require(notice in notices and digest(root / notice) == row['source_sha256'], 'Missing complete compiled source')
        # Unchanged translation units must match source inventory; generated units remain separately identified.
        if source in source_map:
            require(row['source_sha256'] == source_map[source]['sha256'], 'Compiled source differs from pinned source')
        args = row['arguments']
        require(isinstance(args, list) and '-o' in args and '-isysroot' in args and '-arch' in args,
                'Missing actual compiler argv')
        require(args[args.index('-isysroot')+1] == preflight['sdk_paths']['iphoneos'] and args[args.index('-arch')+1] == 'arm64', 'Wrong compile SDK/architecture')
        require(not any('/opt/homebrew/' in a or '/usr/local/' in a for a in args), 'Host headers/libraries leaked into compile')
        require(args[0] in (preflight['tools']['clang'], preflight['tools']['clang++']), 'Unreviewed compile driver')
        matches = [(key, item) for key, item in commands.items() if key.endswith('/' + object_path) and item[0] == args]
        require(len(matches) == 1 and matches[0][1][1].endswith('/' + source), 'Compiled object lacks exact compile_commands linkage')
        proof = row['macho']
        sdk = proof.get('build_version', {}).get('sdk')
        allowed_zero = any(a['source'] == source and a['sha256'] == row['source_sha256'] for a in support.LOCK['assembly_unspecified_sdk'])
        require(proof.get('arch') == 'arm64' and proof.get('file_type') == 1 and
                proof.get('build_version') == {'platform': 2, 'minimum': 0x120000, 'sdk': 0 if allowed_zero and sdk == 0 else 0x1a0500}
                and not proof.get('dylibs') and not proof.get('dynamic_loaders') and proof.get('implicit_host_signature_present') is False,
                'Compiled-object platform/SDK proof mismatch')
        hex64(row['object_sha256'])
        objects.setdefault(row['object_sha256'], []).append(row)
    compiled_sources = {r['source']: r['source_sha256'] for r in compiled}
    for notice in notices:
        if notice == 'notices/LLVM-LICENSE.TXT':
            source = 'llvm/LICENSE.TXT'
        elif notice.startswith('notices/source/'):
            source = notice[len('notices/source/'):]
        elif notice.startswith('notices/compiled-source/'):
            source = notice[len('notices/compiled-source/'):]
        else:
            raise ValueError('Notice is outside exact upstream/compiled source roots')
        expected_sha = source_map.get(source, {}).get('sha256') or compiled_sources.get(source)
        require(expected_sha and digest(root / notice) == expected_sha, 'Notice content lacks exact source/compilation provenance')
    archive_proofs = read_json(root / 'manifests/archive-members.json')
    require(isinstance(archive_proofs, list) and len(archive_proofs) == 34, 'Missing archive member proofs')
    proof_map = {x['path']: x for x in archive_proofs}
    expected_archives = {'lib' + lib + '.a' for lib in libraries}
    require(set(proof_map) == expected_archives and len(proof_map) == 34, 'Wrong archive set')
    require({n for n in names if n.startswith('prefix/lib/')} == {'prefix/lib/' + n for n in expected_archives}, 'Wrong prefix library set')
    covered = set()
    member_count = 0
    for name in sorted(expected_archives):
        actual = support.archive_members(root / 'prefix/lib' / name)
        require(actual == proof_map[name], 'Raw archive bytes differ from all-member proof')
        for member in actual['members']:
            matching = [r for r in objects.get(member['sha256'], []) if Path(r['object']).name == member['name'] and r['macho'] == {k: member[k] for k in r['macho']}]
            require(matching, 'Archive member not linked to actual compiled source: ' + name + ':' + member['name'])
            if member['build_version']['sdk'] == 0:
                require(any(a['archive'] == name and a['member'] == member['name'] and
                    any(r['source'] == a['source'] and r['source_sha256'] == a['sha256'] for r in matching)
                    for a in support.LOCK['assembly_unspecified_sdk']), 'SDK0 exception lacks exact archive/member/source SHA binding')
            covered.update(r['object'] for r in matching)
            member_count += 1
    require(covered == object_paths, 'Actual compiled object closure differs from exported archives')
    commands_log = read_json(root / 'manifests/commands.json')
    require(isinstance(commands_log, list) and commands_log and all(x['exit_code'] == 0 for x in commands_log), 'Unsuccessful helper command')
    build_rows = [x for x in commands_log if x['name'] == 'build']
    require(len(build_rows) == 1, 'Missing actual build invocation')
    argv = build_rows[0]['argv']
    require(argv[argv.index('--target')+1:argv.index('--')] == libraries + ['llvm-headers']
            and argv[argv.index('--parallel')+1] == '4', 'Wrong actual library/header targets or jobs')
    return names, {'libraries': 34, 'archive_members': member_count, 'compiled_translation_units': len(compiled),
                   'public_headers': len(headers), 'notice_files': len(notices)}


def source_availability():
    return ('LLVM 15.0.7 exact upstream source: https://github.com/llvm/llvm-project/tree/' + LLVM + '\n'
        'Exact source archive: https://github.com/llvm/llvm-project/archive/' + LLVM + '.tar.gz\n'
        'The target source copy changes only the locked AddLLVM.cmake Darwin|iOS condition.\n'
        'Full compiled translation units and upstream dependency headers with notices are under notices/.\n'
        'Public headers, actual compile argv, per-object and per-archive proofs, source/configuration manifests,\n'
        'complete selected notices, native generator provenance and exact recipes are included.\n'
        'No SDK/compiler binaries or target executables are included.\n' + SCOPE + '\n')


def package_prefix(lock, native_manifest):
    names, proof = validate_target(BUILD)
    staging = safe(RUN / 'package-extra', fresh=True)
    staging.mkdir()
    extras = {}
    for name in (*PINS, LOCK_NAME, 'run_llvm_target_control.py'):
        extras['Recipe/' + name] = ROOT / 'ci' / name
    for name in PROVENANCE:
        extras['NativeProvenance/' + name] = IMPORT / name
    (staging / 'SOURCE-AVAILABILITY.txt').write_text(source_availability())
    extras['SOURCE-AVAILABILITY.txt'] = staging / 'SOURCE-AVAILABILITY.txt'
    files = {name: BUILD / name for name in names} | extras
    require(len(files) <= MAX_FILES, 'Target bundle file count exceeds bound')
    require(sum(safe(p).stat().st_size for p in files.values()) <= MAX_BUNDLE, 'Target payload exceeds 768 MiB')
    entries = {name: {'sha256': digest(path), 'size': path.stat().st_size, 'mode': 0o644} for name, path in sorted(files.items())}
    manifest = {'schema': 1, 'kind': 'llvm-target-prefix-arm64-ios18', 'llvm_commit': LLVM, 'llvm_version': '15.0.7',
        'madeira_commit': MADEIRA, 'sdk_version': '26.5', 'minimum_ios': '18.0', 'recipe_pins': PINS,
        'native_input': lock['native'], 'wrapper_sha256': digest(Path(__file__)),
        'input_lock_sha256': digest(ROOT / 'ci' / LOCK_NAME), 'validation': proof, 'scope': SCOPE,
        'target_binaries_run': False, 'converter_validated': False, 'runtime_linked': False, 'device_tested': False, 'files': entries}
    raw = (json.dumps(manifest, indent=2, sort_keys=True) + '\n').encode()
    temporary = safe(OUT / 'llvm-target-prefix.zip.part', fresh=True)
    with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name, path in sorted(files.items()):
            info = zipfile.ZipInfo(safe_name(name))
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            with archive.open(info, 'w', force_zip64=True) as target, safe(path).open('rb') as source:
                shutil.copyfileobj(source, target, MIB)
        info = zipfile.ZipInfo('artifact-manifest.json')
        info.create_system = 3
        info.external_attr = (stat.S_IFREG | 0o644) << 16
        archive.writestr(info, raw)
    safe(temporary, MAX_ZIP)
    final = safe(OUT / 'llvm-target-prefix.zip', fresh=True)
    temporary.replace(final)
    artifact = {'path': final.name, 'sha256': digest(final, MAX_ZIP), 'size': final.stat().st_size,
                'manifest_sha256': hashlib.sha256(raw).hexdigest(), 'validation': proof}
    # Exercise actual transport bytes using the same no-execution consumer gate.
    verify_prefix(final, artifact['sha256'], artifact['manifest_sha256'], RUN / 'verified-prefix')
    return artifact


def verify_prefix(path, zip_sha, manifest_sha, destination):
    require(digest(path, MAX_ZIP) == hex64(zip_sha), 'Target ZIP SHA mismatch')
    hex64(manifest_sha)
    destination = safe(destination, fresh=True)
    safe(destination.parent, directory=True)
    staging = safe(destination.with_name(destination.name + '.importing'), fresh=True)
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            require(0 < len(infos) <= MAX_FILES and len({i.filename.casefold() for i in infos}) == len(infos), 'Duplicate/excessive ZIP members')
            require(sum(i.file_size for i in infos) <= MAX_BUNDLE, 'Oversized target ZIP content')
            for info in infos:
                safe_name(info.filename)
                require(not info.is_dir() and stat.S_IFMT(info.external_attr >> 16) == stat.S_IFREG
                    and stat.S_IMODE(info.external_attr >> 16) == 0o644 and not info.flag_bits & 1
                    and info.file_size <= MAX_FILE, 'Unsafe target ZIP type/mode/size')
            info = archive.getinfo('artifact-manifest.json')
            require(info.file_size <= 8*MIB, 'Target artifact manifest exceeds cap')
            raw = archive.read(info)
            require(hashlib.sha256(raw).hexdigest() == manifest_sha, 'Target artifact manifest SHA mismatch')
            manifest = json.loads(raw, object_pairs_hook=unique)
            require(manifest.get('schema') == 1 and manifest.get('kind') == 'llvm-target-prefix-arm64-ios18'
                    and manifest.get('llvm_commit') == LLVM and manifest.get('llvm_version') == '15.0.7'
                    and manifest.get('madeira_commit') == MADEIRA and manifest.get('recipe_pins') == PINS
                    and manifest.get('sdk_version') == '26.5' and manifest.get('minimum_ios') == '18.0', 'Wrong target artifact identity')
            require(all(manifest.get(k) is False for k in ('target_binaries_run', 'converter_validated', 'runtime_linked', 'device_tested')), 'Invalid target artifact scope')
            entries = manifest['files']
            require(set(entries) | {'artifact-manifest.json'} == {i.filename for i in infos}, 'Missing/undeclared target ZIP member')
            staging.mkdir()
            for info in infos:
                target = staging / info.filename
                target.parent.mkdir(parents=True, exist_ok=True)
                h = hashlib.sha256()
                written = 0
                with archive.open(info) as source, target.open('xb') as output:
                    while data := source.read(MIB):
                        written += len(data)
                        require(written <= info.file_size, 'Decompression exceeded declared file size')
                        output.write(data)
                        h.update(data)
                target.chmod(0o644)
                if info.filename != 'artifact-manifest.json':
                    require(entries[info.filename] == {'sha256': h.hexdigest(), 'size': written, 'mode': 0o644}, 'Target file digest/size/mode mismatch')
        helper_names, proof = validate_target(staging)
        allowed_extras = {'Recipe/' + x for x in (*PINS, LOCK_NAME, 'run_llvm_target_control.py')} | {'NativeProvenance/' + x for x in PROVENANCE} | {'SOURCE-AVAILABILITY.txt'}
        require(set(entries) == helper_names | allowed_extras, 'Target payload exceeds exact prefix/evidence allowlist')
        require(proof == manifest['validation'], 'Recomputed target proof differs')
        for name, pin in PINS.items():
            verify_hash(staging / 'Recipe' / name, pin)
        require(manifest['wrapper_sha256'] == digest(Path(__file__)), 'Target producer wrapper differs from this reviewed verifier')
        verify_hash(staging / 'Recipe/run_llvm_target_control.py', manifest['wrapper_sha256'])
        verify_hash(staging / 'Recipe' / LOCK_NAME, manifest['input_lock_sha256'])
        input_lock = read_json(staging / 'Recipe' / LOCK_NAME)
        require(input_lock.get('status') == 'verified-original-native-producer' and input_lock.get('native') == manifest['native_input'], 'Native dependency identity mismatch')
        verify_hash(staging / 'NativeProvenance/artifact-manifest.json', manifest['native_input']['artifact_manifest_sha256'])
        native = read_json(staging / 'NativeProvenance/manifest.json')
        original = read_json(staging / 'NativeProvenance/artifact-manifest.json')
        require(original.get('kind') == 'llvm-tblgen-native-arm64-macos' and original.get('recipe_pins') == {k: PINS[k] for k in ('llvm-core-control.sh', 'llvm_control_support.py', 'llvm-source-lock.json')}, 'Wrong original native recipe')
        for name in PROVENANCE[1:]:
            path = staging / 'NativeProvenance' / name
            declared = original['files'][name]
            require(declared['sha256'] == digest(path) and declared['size'] == path.stat().st_size, 'Native provenance changed')
        imported = read_json(staging / 'manifests/native-import.json')
        require(imported == {'manifest_sha256': digest(staging / 'NativeProvenance/manifest.json'),
                            'binary_sha256': native['binary']['sha256'], 'llvm_commit': LLVM}, 'Target native import not tied to original')
        staging.replace(destination)
        return manifest
    except BaseException:
        if staging.is_dir() and not staging.is_symlink():
            shutil.rmtree(staging)
        raise


def worker():
    lock = reviewed_inputs()
    commands = Commands()
    report = {'result': 'failed', 'scope': SCOPE, 'llvm_commit': LLVM, 'madeira_commit': MADEIRA,
              'jobs': 4, 'aggregate_budget_seconds': AGGREGATE_SECONDS, 'native_input': lock['native'],
              'target_binaries_run': False, 'converter_validated': False, 'runtime_linked': False, 'device_tested': False}
    try:
        helper_argv = target_python_invocation()
        report['python_selection_sha256'] = digest(OUT / 'python-selection.json')
        native = load_module('run_llvm_control.py')
        native.SOURCE = SOURCE
        original = transport_native(lock)
        # Frozen native importer performs no execution. Validate once before source network activity.
        original_manifest = native.verify_import(original, lock['native']['zip_sha256'], lock['native']['artifact_manifest_sha256'])
        report['checkout'] = native.checkout(commands)
        BUILD.parent.mkdir(parents=True)
        native.verify_import(original, lock['native']['zip_sha256'], lock['native']['artifact_manifest_sha256'], IMPORT)
        commands.run('target-build', *helper_argv)
        report['artifact'] = package_prefix(lock, original_manifest)
        report['result'] = 'passed-target-llvm-prefix-only'
    except Exception as error:
        report['failure'] = str(error)
    finally:
        write_json(OUT / 'result.json', report)
    return 0 if report['result'] == 'passed-target-llvm-prefix-only' else 1


def finalize():
    result = read_json(OUT / 'result.json') if (OUT / 'result.json').exists() else {'result': 'failed', 'scope': SCOPE}
    supervisor = read_json(OUT / 'supervisor.json')
    if supervisor['worker_exit_code'] != 0 or result.get('result') != 'passed-target-llvm-prefix-only':
        result.update(result='failed', failure=result.get('failure', 'Worker failed or exhausted aggregate budget'))
        result.pop('artifact', None)
        (OUT / 'llvm-target-prefix.zip').unlink(missing_ok=True)
    (OUT / 'llvm-target-prefix.zip.part').unlink(missing_ok=True)
    result['supervisor'] = supervisor
    write_json(OUT / 'result.json', result)
    labels = ('madeira-init madeira-origin madeira-fetch madeira-sparse madeira-checkout madeira-pin '
              'llvm-init llvm-origin llvm-fetch llvm-sparse llvm-checkout llvm-pin llvm-toplevel target-build').split()
    candidates = [(OUT / n, n) for n in ('result.json', 'supervisor.json', 'steps.json', 'worker.log', 'python-selection.json')]
    candidates += [(OUT / (n + '.log'), 'Logs/' + n + '.log') for n in labels]
    candidates += [(BUILD / n, 'Build/' + n) for n in MANIFESTS + CONFIGURATION + COMPILER_EVIDENCE + ('failure.json',)]
    candidates += [(BUILD / 'logs' / (n + '.log'), 'Build/logs/' + n + '.log') for n in sorted(LOG_LABELS)]
    for name in CONFIGURATION + COMPILER_EVIDENCE:
        if not (BUILD / name).exists():
            candidates.append((BUILD / 'build' / name[len('evidence/'):], 'Build/' + name))
    candidates += [(ROOT / 'ci' / n, 'Recipe/' + n) for n in (*PINS, LOCK_NAME, 'run_llvm_target_control.py')]
    total, omissions = 0, []
    evidence = OUT / 'llvm-target-evidence.zip.part'
    with zipfile.ZipFile(evidence, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path, name in candidates:
            if not path.exists() and not path.is_symlink():
                continue
            try:
                safe(path)
                amount = min(path.stat().st_size, 12*MIB)
                require(total + amount <= 96*MIB, '96 MiB evidence cap')
                with path.open('rb') as stream:
                    if path.stat().st_size > amount:
                        stream.seek(path.stat().st_size-amount)
                        name += '.tail'
                    archive.writestr(name, stream.read(amount))
                total += amount
            except (ValueError, OSError) as error:
                omissions.append({'path': name, 'reason': str(error)})
        archive.writestr('evidence-omissions.json', json.dumps(omissions, indent=2))
    evidence.replace(OUT / 'llvm-target-evidence.zip')
    print('LLVM_TARGET_CONTROL_RESULT=' + json.dumps(result, sort_keys=True), flush=True)
    return 0 if result['result'] == 'passed-target-llvm-prefix-only' else 1


def supervise(args, deadline, log):
    with log.open('xb') as stream:
        proc = subprocess.Popen(args, cwd=ROOT, env=environment(), stdout=stream, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)
        code = 124
        try:
            while time.monotonic() < deadline and log.stat().st_size <= 64*MIB:
                try:
                    code = proc.wait(timeout=min(.2, max(.01, deadline-time.monotonic())))
                    if log.stat().st_size > 64*MIB:
                        code = 124
                    break
                except subprocess.TimeoutExpired:
                    pass
        finally:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait()
    return code


def main():
    if sys.argv[1:2] == ['--verify-prefix']:
        require(len(sys.argv) == 6, 'Usage: --verify-prefix ZIP ZIP_SHA256 MANIFEST_SHA256 FRESH_DESTINATION')
        m = verify_prefix(Path(sys.argv[2]), sys.argv[3], sys.argv[4], Path(sys.argv[5]))
        print(json.dumps({'result': 'verified-prefix-no-execution', 'validation': m['validation']}))
        return 0
    if sys.argv[1:] == ['--worker']:
        return worker()
    if sys.argv[1:] == ['--finalize']:
        return finalize()
    require(len(sys.argv) == 1, 'No public build arguments supported')
    started = time.monotonic()
    deadline = started + AGGREGATE_SECONDS
    require(sys.platform == 'darwin' and platform.machine() == 'arm64', 'Approved arm64 macOS runner required')
    require(os.environ.get('FREE_QUOTA_VERIFIED') == 'true' and os.environ.get('PRIVATE_SOURCE_VERIFIED') == 'true',
            'Manual free/private guards must be exactly true')
    reviewed_inputs()
    for path in (SOURCE, OUT, RUN):
        safe(path, fresh=True)
    for path in (OUT, RUN / 'home', RUN / 'tmp'):
        path.mkdir(parents=True)
    code = finish = None
    successful = False
    failure = 'Worker/finalizer did not complete successfully'
    previous_term = signal.getsignal(signal.SIGTERM)
    def terminate(signum, frame):
        raise InterruptedError('Control interrupted by SIGTERM')
    signal.signal(signal.SIGTERM, terminate)
    try:
        code = supervise([sys.executable, '-I', str(Path(__file__)), '--worker'], deadline-FINALIZE_RESERVE, OUT / 'worker.log')
        write_json(OUT / 'supervisor.json', {'worker_exit_code': code, 'elapsed_seconds': round(time.monotonic()-started, 3),
                                          'aggregate_budget_seconds': AGGREGATE_SECONDS, 'finalization_reserve_seconds': FINALIZE_RESERVE})
        finish = supervise([sys.executable, '-I', str(Path(__file__)), '--finalize'], deadline, OUT / 'finalize.log')
        successful = code == finish == 0
        return 0 if successful else 1
    except BaseException as error:
        failure = type(error).__name__ + ': ' + str(error)
        raise
    finally:
        signal.signal(signal.SIGTERM, previous_term)
        if not successful:
            (OUT / 'llvm-target-prefix.zip').unlink(missing_ok=True)
            (OUT / 'llvm-target-prefix.zip.part').unlink(missing_ok=True)
            (OUT / 'llvm-target-evidence.zip.part').unlink(missing_ok=True)
            try:
                failed = read_json(OUT / 'result.json') if (OUT / 'result.json').exists() else {'scope': SCOPE}
            except (OSError, ValueError):
                failed = {'scope': SCOPE}
            failed.update(result='failed', supervisor_failure=failure,
                          supervisor_worker_exit=code, supervisor_finalize_exit=finish)
            failed.pop('artifact', None)
            write_json(OUT / 'result.json', failed)



if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
