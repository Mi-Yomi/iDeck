#!/usr/bin/env python3
"""Manual, bounded source-only ntdll control; no dispatch, install or target execution.

The only public CLI is no arguments. --worker and --finalize are internal stages
launched in separate supervised process groups under one 23-minute deadline.
"""
from __future__ import annotations
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import signal
import stat
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / '.work/ntdll-control-run'
OUT = ROOT / '.work/ntdll-control-artifacts'
MADEIRA = '279fd0f83170425db002fe25d6bd62f6355f497d'
WINE = '9129e9684daaeae70da9435e7c6060e59392634e'
REMOTES = {'madeira': 'https://github.com/willfaust/Madeira.git', 'wine': 'https://github.com/willfaust/wine.git'}
MIB = 1024 * 1024
AGGREGATE_SECONDS = 23 * 60
FINALIZE_RESERVE = 60
ARTIFACT_KINDS = frozenset(('wine-headers', 'freetype', 'ffmpeg', 'crypto-prefix', 'crypto-proof'))
PINS = {
    'ci/build_ntdll_control.py': 'a37622ec50e659604ff32c93c9758fd2be4f3cdb3d5c33817fc4ef8dfc7ff2fb',
    'ntdll-source-manifest.json': '8d487906f5bf8c402456584631bf8cb142242c2f6193eb30f1257f48a0dc1b6d',
    'ci/prove_crypto_features.py': '6d3a662a0760a17d329675bea3d3445959f9e85ed7d0d37ff7e608f3a055af9f',
    'gnutls-symbol-lock.json': 'cc8924fdaef69921bbe27a2cfc7323ed22fbd2f1ca969a48dcc0b55aeb75bae4',
    'gnutls-api-link-probe.c': 'cbfff4cd0888a2849282f38253b4839afc4a9064dfc042932c0896ad59314e09',
}
TRANSPORT_SHA256 = 'd7b3116c6a4649060c91b8467a7a05c923611b3fcf36b51bc2b78a94dfd5d3db'
TRANSPORT_PATHS = frozenset(('ci/reassemble_ntdll_artifact.py',))
NOTICE_ROOTS = {
    'madeira': ('COPYING', 'LICENSE', 'LICENSE-EXCEPTION.md', 'THIRD-PARTY-NOTICES.md', 'docs/LICENSING.md', 'docs/wine-lgpl-provenance.md'),
    'wine': ('COPYING.LIB', 'LICENSE'),
}
PROOF_LOGS = ('host-architecture', 'developer-directory', 'xcode-version', 'sdk-version', 'sdk-path', 'find-clang', 'find-nm', 'find-otool', 'clang-version', 'symbols-libgnutls.a', 'symbols-libhogweed.a', 'symbols-libnettle.a', 'symbols-libgmp.a', 'target-api-link', 'probe-load-commands', 'probe-symbols')

class WrapperError(ValueError):
    pass

def require(ok, message):
    if not ok:
        raise WrapperError(message)

def safe_name(name):
    require(isinstance(name, str), 'Path must be text')
    p = PurePosixPath(name)
    require(name and p.as_posix() == name and not p.is_absolute() and '..' not in p.parts
            and not any(ord(c) < 32 or ord(c) == 127 or c in '\\:#$' for c in name), 'Unsafe relative path')
    return name

def safe(path, *, directory=False, fresh=False, cap=256*MIB):
    p = Path(path).absolute()
    require('..' not in p.parts and p.resolve(strict=False) == p, 'Noncanonical path')
    require(not any(q.is_symlink() for q in (p, *p.parents)), 'Symlink path')
    if fresh:
        require(not p.exists(), 'Fresh destination required')
    elif directory:
        require(p.is_dir(), 'Missing directory: ' + str(p))
    else:
        info = p.stat()
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= cap, 'Unsafe/oversized regular file')
    return p

def digest(path):
    h = hashlib.sha256()
    with safe(path).open('rb') as stream:
        for data in iter(lambda: stream.read(MIB), b''):
            h.update(data)
    return h.hexdigest()

def unique(pairs):
    out = {}
    for key, value in pairs:
        require(key not in out, 'Duplicate JSON key')
        out[key] = value
    return out

def read_json(path, cap=16*MIB):
    return json.loads(safe(path, cap=cap).read_text(), object_pairs_hook=unique)

def write_json(path, value):
    p = Path(path)
    temporary = safe(p.with_name(p.name + '.pending'), fresh=True)
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    temporary.replace(p)

def verify_hash(path, expected):
    require(isinstance(expected, str) and re.fullmatch(r'[0-9a-f]{64}', expected), 'Exact reviewed SHA256 required')
    require(digest(path) == expected, 'Reviewed input changed: ' + str(path))

def load_module(path, expected, name):
    verify_hash(path, expected)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    old = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = old
    return module

def reviewed_inputs(root=ROOT, environ=None):
    environ = os.environ if environ is None else environ
    verify_hash(root / 'ci/run_ntdll_control.py', environ.get('EXPECTED_NTDLL_WRAPPER_SHA256'))
    verify_hash(root / 'ci/ntdll-dependency-artifacts-lock.json', environ.get('EXPECTED_NTDLL_DEPENDENCY_LOCK_SHA256'))
    lock = read_json(root / 'ci/ntdll-dependency-artifacts-lock.json')
    require(lock.get('schema') == 1 and lock.get('madeira') == MADEIRA and lock.get('wine') == WINE
            and lock.get('source_remotes') == REMOTES, 'Wrong dependency/source lock')
    require(set(lock.get('artifacts', {})) == ARTIFACT_KINDS, 'Exactly five original dependency envelopes required')
    require(lock.get('crypto', {}).get('fresh_relocated_target_link_proof_required') is True
            and lock['crypto'].get('original_proof_rewritten') is False, 'Fresh proof and original evidence preservation required')
    for name, sha in PINS.items():
        verify_hash(root / name, sha)
    helpers = lock.get('consumer_helpers', {})
    require(set(helpers) == {'ci/import_ntdll_dependencies.py'}, 'Exact importer helper pin required')
    verify_hash(root / 'ci/import_ntdll_dependencies.py', helpers['ci/import_ntdll_dependencies.py'])
    transport = lock.get('transport', {})
    require(set(transport) == {'helper_path', 'helper_sha256', 'packages', 'originals'}, 'Incomplete transport map')
    require(transport['helper_path'] in TRANSPORT_PATHS and transport['helper_sha256'] == TRANSPORT_SHA256, 'Unreviewed reassembler')
    verify_hash(root / transport['helper_path'], TRANSPORT_SHA256)
    require(set(transport['packages']).isdisjoint(transport['originals'])
            and set(transport['packages']) | set(transport['originals']) == ARTIFACT_KINDS, 'Missing/duplicate transport route')
    for kind, spec in lock['artifacts'].items():
        require(spec.get('status') == 'verified-original-producer' and spec.get('producer', {}).get('madeira') == MADEIRA, 'Unverified producer envelope')
    return lock

def clean_environment(home, tmp, environ=None):
    original = os.environ if environ is None else environ
    env = {'PATH': '/usr/bin:/bin:/usr/sbin:/sbin', 'HOME': str(home), 'TMPDIR': str(tmp),
           'LC_ALL': 'C', 'LANG': 'C', 'TZ': 'UTC', 'JOBS': '4', 'ZERO_AR_DATE': '1',
           'GIT_TERMINAL_PROMPT': '0', 'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null',
           'GIT_LFS_SKIP_SMUDGE': '1', 'PYTHONNOUSERSITE': '1', 'PYTHONDONTWRITEBYTECODE': '1'}
    for name in ('DEVELOPER_DIR', 'EXPECTED_NTDLL_WRAPPER_SHA256', 'EXPECTED_NTDLL_DEPENDENCY_LOCK_SHA256'):
        if name in original:
            env[name] = original[name]
    return env

class Commands:
    """Children stay in their outer supervisor's group; source commands never execute."""
    def __init__(self, run=RUN):
        self.run_root = run
        self.records = []
        self.env = clean_environment(run/'home', run/'tmp')

    def run(self, label, argv, cwd=None, input_data=None):
        require(re.fullmatch(r'[a-z0-9-]+', label) and label not in {r['step'] for r in self.records}, 'Unsafe/duplicate command label')
        require(Path(argv[0]).is_absolute(), 'Executable must have an explicit path')
        log = self.run_root / 'logs' / (label + '.log')
        started = time.monotonic()
        record = {'step': label, 'argv': [str(a) for a in argv], 'exit_code': None,
                  'seconds': None, 'log': 'logs/'+log.name, 'log_sha256': None}
        self.records.append(record)
        # Record the attempted step first so timeout evidence includes its partial log.
        with log.open('xb') as stream:
            write_json(self.run_root/'commands.json', self.records)
            result = subprocess.run([str(a) for a in argv], cwd=cwd or self.run_root, env=self.env,
                                    input=input_data, stdout=stream, stderr=subprocess.STDOUT, check=False)
        require(log.stat().st_size <= 64*MIB, 'Command log exceeds bound')
        record.update(exit_code=result.returncode, seconds=round(time.monotonic()-started, 3), log_sha256=digest(log))
        write_json(self.run_root/'commands.json', self.records)
        require(result.returncode == 0, label + ' failed: exit ' + str(result.returncode))
        return log.read_bytes()

    def git(self, label, repository, *args, input_data=None):
        return self.run(label, ['/usr/bin/git', '-c', 'core.hooksPath=/dev/null', '-c', 'core.fsmonitor=false', '-C', repository, *args], input_data=input_data)

def parse_tree(data):
    entries = {}
    for row in data.split(b'\0'):
        if not row:
            continue
        metadata, raw_name = row.split(b'\t', 1)
        mode, kind, identity = metadata.decode('ascii').split()
        name = safe_name(raw_name.decode('utf-8'))
        require(name not in entries and re.fullmatch(r'[0-9a-f]{40}', identity), 'Invalid tracked source entry')
        entries[name] = {'mode': mode, 'kind': kind, 'git_blob': identity}
    return entries

def git_blob(path):
    data = safe(path).read_bytes()
    return hashlib.sha1(b'blob ' + str(len(data)).encode('ascii') + b'\0' + data).hexdigest()

def verify_materialized(repository, expected):
    actual = set()
    for current, dirs, files in os.walk(repository, followlinks=False):
        parent = Path(current)
        if parent == repository:
            dirs[:] = [d for d in dirs if d not in ('.git', 'wine')]
        for d in dirs:
            safe(parent/d, directory=True)
        for name in files:
            p = safe(parent/name)
            actual.add(p.relative_to(repository).as_posix())
    require(actual == set(expected), 'Sparse source has extra/missing materialized files')
    return [{'path': name, 'sha256': digest(repository/name), 'size': safe(repository/name).stat().st_size,
             'git_blob': git_blob(repository/name)} for name in sorted(actual)]

def verify_checkout(commands, tag, repository, pin, manifest_records, expected_names=None):
    require(commands.git(tag+'-head', repository, 'rev-parse', 'HEAD').decode().strip() == pin, 'Wrong full source pin')
    tree_bytes = commands.git(tag+'-tree', repository, 'ls-tree', '-r', '-z', 'HEAD')
    tree = parse_tree(tree_bytes)
    records = {r['path']: r for r in manifest_records}
    names = set(expected_names if expected_names is not None else records)
    require(set(records).issubset(names), 'Manifest source omitted')
    for name in names:
        require(name in tree and tree[name]['kind'] == 'blob' and tree[name]['mode'] in ('100644', '100755'), 'Source is not a regular tracked blob')
        if name in records:
            row = records[name]
            require(row['source_commit'] == pin and tree[name]['git_blob'] == row['git_blob'], 'Manifest differs from pinned source tree')
            require(safe(repository/name).stat().st_size == row['size'] and digest(repository/name) == row['sha256'], 'Source bytes differ from reviewed manifest')
    materialized = verify_materialized(repository, names)
    require(all(r['git_blob'] == tree[r['path']]['git_blob'] for r in materialized), 'Tracked source content drift')
    # Check both worktree and index across the entire tracked tree, not only selected source paths.
    require(not commands.git(tag+'-diff', repository, 'diff', '--no-ext-diff', '--no-textconv', 'HEAD', '--').strip(), 'Tracked source changed')
    require(not commands.git(tag+'-index-diff', repository, 'diff', '--cached', '--no-ext-diff', '--no-textconv', 'HEAD', '--').strip(), 'Tracked source index changed')
    require(not commands.git(tag+'-untracked', repository, 'ls-files', '--others', '--exclude-standard', '-z').strip(), 'Untracked source additions')
    return {'commit': pin, 'remote': REMOTES[tag.split('-')[0]], 'full_tree_sha256': hashlib.sha256(tree_bytes).hexdigest(),
            'full_tree_entries': len(tree), 'materialized': materialized, 'clean_tracked_diff': True}

def acquire_sources(commands, manifest):
    source = RUN/'source'
    source.mkdir()
    result = {}
    for tag, repository, pin in (('madeira', source, MADEIRA), ('wine', source/'wine', WINE)):
        if tag == 'wine':
            require(not repository.exists() or (repository.is_dir() and not list(repository.iterdir())), 'Wine subtree is not fresh')
            repository.mkdir(exist_ok=True)
        commands.git(tag+'-init', repository, 'init', '--quiet')
        commands.git(tag+'-remote', repository, 'remote', 'add', 'origin', REMOTES[tag])
        commands.git(tag+'-fetch', repository, 'fetch', '--depth=1', '--filter=blob:none', 'origin', pin)
        tree = parse_tree(commands.git(tag+'-fetched-tree', repository, 'ls-tree', '-r', '-z', 'FETCH_HEAD'))
        records = [dict(row, path=row['path'][5:] if tag == 'wine' else row['path']) for row in manifest['sources']
                   if row['path'].startswith('wine/') == (tag == 'wine')]
        required = {row['path'] for row in records}
        notices = {name for name in tree if name in NOTICE_ROOTS[tag] or name.startswith('LICENSES/')}
        require(('COPYING' if tag == 'madeira' else 'COPYING.LIB') in notices, 'Pinned source license missing')
        names = required | notices | ({'.gitmodules'} if tag == 'madeira' else set())
        if tag == 'madeira':
            require(tree.get('wine') == {'mode': '160000', 'kind': 'commit', 'git_blob': WINE}, 'Madeira Wine gitlink mismatch')
        require(all(name in tree for name in names), 'Missing tracked source closure')
        # Exact file patterns, not directory cones; no source configure/build scripts are run.
        commands.git(tag+'-sparse-init', repository, 'sparse-checkout', 'init', '--no-cone')
        patterns = ''.join('/'+name+'\n' for name in sorted(names)).encode()
        commands.git(tag+'-sparse-set', repository, 'sparse-checkout', 'set', '--no-cone', '--stdin', input_data=patterns)
        commands.git(tag+'-checkout', repository, 'checkout', '--detach', 'FETCH_HEAD')
        if tag == 'madeira':
            value = commands.git('madeira-wine-url', repository, 'config', '-f', '.gitmodules', '--get', 'submodule.wine.url')
            require(value.decode().strip() == REMOTES['wine'], 'Pinned Wine source URL mismatch')
        result[tag] = verify_checkout(commands, tag+'-before', repository, pin, records, names)
        result[tag]['notices'] = sorted(notices)
    write_json(RUN/'ntdll-source-identity.json', result)
    return source, result

def recheck_sources(commands, manifest, before):
    after = {}
    for tag, pin in (('madeira', MADEIRA), ('wine', WINE)):
        repository = RUN/'source' if tag == 'madeira' else RUN/'source/wine'
        records = [dict(row, path=row['path'][5:] if tag == 'wine' else row['path']) for row in manifest['sources']
                   if row['path'].startswith('wine/') == (tag == 'wine')]
        names = {row['path'] for row in before[tag]['materialized']}
        value = verify_checkout(commands, tag+'-after', repository, pin, records, names)
        value['notices'] = before[tag]['notices']
        require(value == before[tag], 'Source identity changed during build')
        after[tag] = value
    write_json(RUN/'ntdll-source-postcheck.json', after)

def route_direct_path(kind):
    require(kind in ('wine-headers', 'freetype'), 'Unexpected direct original kind')
    return {'wine-headers': 'ci/inputs/wine-headers.zip', 'freetype': 'ci/artifacts/ntdll-freetype-prefix.zip'}[kind]

def transport_inputs(lock, importer, transport):
    paths = {}
    for kind in sorted(ARTIFACT_KINDS):
        spec = lock['artifacts'][kind]
        destination = RUN/'original-zips'/(kind+'.zip')
        if kind in lock['transport']['packages']:
            route = lock['transport']['packages'][kind]
            package = ROOT/safe_name(route['path'])
            expected_packages = {'ffmpeg': 'ci/artifacts/ntdll-ffmpeg-prefix', 'crypto-prefix': 'ci/artifacts/ntdll-crypto-prefix', 'crypto-proof': 'ci/artifacts/ntdll-crypto-proof'}
            require(route['path'] == expected_packages.get(kind), 'Transport package outside exact approved directory')
            info = transport.reassemble(package, route['manifest_sha256'], destination)
            require(info['original']['size'] == spec['bytes'] and info['original']['sha256'] == spec['sha256'], 'Transport original identity mismatch')
            require(info['provenance']['build_id'] == spec['producer']['build_id'] and info['provenance']['source_commit'] == MADEIRA, 'Transport producer identity mismatch')
            write_json(RUN/'transport'/(kind+'.json'), info)
        else:
            path = ROOT/safe_name(lock['transport']['originals'][kind]['path'])
            require(route_direct_path(kind) == lock['transport']['originals'][kind]['path'], 'Direct original outside exact approved path')
            require(safe(path).stat().st_size == spec['bytes'], 'Original ZIP size mismatch')
            verify_hash(path, spec['sha256'])
            destination.write_bytes(path.read_bytes())
        verify_hash(destination, spec['sha256'])
        importer.import_artifact(destination, spec, RUN/'imports'/kind)
        paths[kind] = RUN/'imports'/kind
    return paths

def raw_archive_check(output, manifest, proof_module, helper_module=None):
    helper_module = helper_module or load_module(ROOT/'ci/build_ntdll_control.py', PINS['ci/build_ntdll_control.py'], 'reviewed_ntdll_binary_checks')
    require(not (output/'failure.json').exists(), 'Failure marker forbids reusable archive')
    result = read_json(output/'result.json')
    require(result.get('result') == 'passed-source-ntdll-archive-control' and result.get('madeira') == MADEIRA
            and result.get('wine') == WINE and result.get('member_count') == 37 and result.get('table_symbol_count') == 19,
            'Complete source-only ntdll success required')
    require(all(result.get(key) is False for key in ('target_binaries_run', 'native_link_performed', 'signed', 'installed', 'source_modified')), 'Unexpected execution/link/install/source mutation claim')
    require(result.get('helper_sha256') == PINS['ci/build_ntdll_control.py']
            and result.get('source_manifest_sha256') == PINS['ntdll-source-manifest.json'], 'Helper/source provenance mismatch')
    for name in ('inputs.json', 'generated-source-record.json', 'units.json', 'commands.json'):
        verify_hash(output/name, result.get('evidence', {}).get(name))
    units = read_json(output/'units.json')
    expected = [unit['member'] for unit in manifest['units']]
    require(len(expected) == 37 and [u['member'] for u in units] == expected, 'Exact 37-unit member order required')
    archive = proof_module.inspect_archive(safe(output/'libntdll_unix.a'))
    require(archive == result['archive'] and [r['member'] for r in archive['members']] == expected, 'Raw archive differs from helper result')
    for member, unit in zip(archive['members'], units):
        path = output/'objects'/safe_name(unit['member'])
        require(safe(path).stat().st_size == unit['bytes'] == member['size'], 'Raw member size mismatch')
        require(digest(path) == unit['sha256'] == member['sha256'], 'Raw member byte mismatch')
        metadata = proof_module.inspect_macho(path.read_bytes(), unit['member'])
        require(metadata == unit['target'] and metadata['sdk'] == '26.5' and not metadata['sdk_unspecified_assembly_exception'], 'ntdll requires strict SDK26.5 C objects')
        definitions = helper_module.read_external_sections(path.read_bytes())
        require(helper_module.verify_tables(unit['member'], definitions) == unit['tables'], 'Raw ordinary/WoW64 table evidence mismatch')
        anchors = helper_module.ANCHORS.get(unit['member'], ())
        require(all('_'+name in definitions for name in anchors), 'Missing source-backed raw symbol anchor')
    require(sum(len(u['tables']) for u in units) == 19, 'Missing table evidence')
    commands = read_json(output/'commands.json')
    require(commands and all(row['exit_code'] == 0 for row in commands), 'Failed/incomplete helper command evidence')
    proof_module.verify_command_logs(output, commands)
    return result

def helper_evidence(manifest):
    names = {'inputs.json', 'generated-source-record.json', 'units.json', 'commands.json', 'result.json', 'failure.json'}
    logs = {'host-architecture', 'developer-directory', 'xcode-version', 'sdk-version', 'sdk-path', 'find-clang', 'find-nm', 'find-ar', 'clang-version', 'clang-resource-dir', 'madeira-source-pin', 'wine-source-pin', 'archive', 'archive-members', 'archive-defined', 'archive-undefined'}
    for unit in manifest['units']:
        member = safe_name(unit['member'])
        names.update(('objects/'+member, 'dependencies/'+member+'.d'))
        logs.update(prefix+'-'+member[:-2] for prefix in ('compile', 'defined', 'undefined'))
        if unit['crypto_overlay']:
            logs.add('macros-'+member[:-2])
    names.update('logs/'+name+'.log' for name in logs)
    names.update(('generated/gnutls_symtab_ios.c', 'generated/target_contract.h'))
    return sorted(names)

def proof_evidence():
    return ['proof.json', 'failure.json', 'commands.json', 'input-evidence.json', 'api-link.map', 'gnutls-api-link-probe', 'feature-overlay.json', 'validated-gnutls-features.h'] + ['logs/'+name+'.log' for name in PROOF_LOGS]

def checked_candidates(candidates, *, optional=False, total_cap=512*MIB):
    selected, seen, total = [], set(), 0
    for path, name in candidates:
        safe_name(name)
        require(name not in ('artifact-manifest.json', 'SHA256SUMS') and name.casefold() not in seen, 'Duplicate/reserved/case-colliding packaged member')
        seen.add(name.casefold())
        if optional and not path.exists() and not path.is_symlink():
            continue
        path = safe(path)
        total += path.stat().st_size
        require(len(selected) < 20000 and total <= total_cap, 'Package inventory bound exceeded')
        selected.append((path, name))
    return selected

def write_zip(destination, candidates, report):
    safe(destination, fresh=True)
    temporary = safe(destination.with_name(destination.name+'.part'), fresh=True)
    inventory = [{'path': name, 'size': path.stat().st_size, 'sha256': digest(path)} for path, name in candidates]
    with zipfile.ZipFile(temporary, 'x', zipfile.ZIP_DEFLATED, compresslevel=1) as archive:
        for (path, name), row in zip(candidates, inventory):
            require(digest(path) == row['sha256'], 'Packaging input changed')
            archive.write(path, name)
        archive.writestr('artifact-manifest.json', json.dumps(dict(report, files=inventory), indent=2, sort_keys=True)+'\n')
        archive.writestr('SHA256SUMS', ''.join(row['sha256']+'  '+row['path']+'\n' for row in inventory))
    safe(temporary, cap=512*MIB)
    with zipfile.ZipFile(temporary) as archive:
        require(archive.testzip() is None, 'Packaged ZIP integrity failure')
    temporary.replace(destination)
    return {'path': destination.name, 'size': destination.stat().st_size, 'sha256': digest(destination)}

def preflight(commands):
    architecture = commands.run('preflight-architecture', ['/usr/bin/uname', '-m']).decode().strip()
    cpu = commands.run('preflight-cpu', ['/usr/sbin/sysctl', '-n', 'machdep.cpu.brand_string']).decode().strip()
    require(architecture == 'arm64' and cpu in ('Apple M2', 'Apple M2 (Virtual)'), 'Reviewed arm64 Apple M2 provider required')
    provider = commands.env.get('DEVELOPER_DIR')
    developer = provider or commands.run('preflight-developer', ['/usr/bin/xcode-select', '-p']).decode().strip()
    require(Path(developer).is_absolute() and Path(developer).is_dir(), 'Selected Xcode developer directory unavailable')
    commands.env['DEVELOPER_DIR'] = developer
    xcode = commands.run('preflight-xcode', ['/usr/bin/xcodebuild', '-version']).decode().strip()
    sdk = commands.run('preflight-sdk', ['/usr/bin/xcrun', '--sdk', 'iphoneos', '--show-sdk-version']).decode().strip()
    require(xcode.splitlines()[0] == 'Xcode 26.6' and sdk == '26.5', 'Exact Xcode26.6/iPhoneOS26.5 required')
    disk = os.statvfs(commands.run_root)
    available = disk.f_bavail * disk.f_frsize
    require(available >= 4*1024*MIB, 'At least 4GiB free required before input/source acquisition')
    record = {'architecture': architecture, 'cpu': cpu, 'xcode_version_output': xcode, 'sdk': sdk,
              'developer_directory': developer, 'developer_selection': 'provider-DEVELOPER_DIR' if provider else 'xcode-select',
              'python_version': '.'.join(str(x) for x in sys.version_info[:3]), 'free_bytes': available, 'jobs_ceiling': 4}
    write_json(commands.run_root/'preflight.json', record)
    return record


def worker():
    lock = reviewed_inputs()
    manifest = read_json(ROOT/'ntdll-source-manifest.json')
    importer = load_module(ROOT/'ci/import_ntdll_dependencies.py', lock['consumer_helpers']['ci/import_ntdll_dependencies.py'], 'reviewed_ntdll_importer')
    transport = load_module(ROOT/lock['transport']['helper_path'], TRANSPORT_SHA256, 'reviewed_ntdll_transport')
    commands = Commands()
    preflight(commands)
    source, before = acquire_sources(commands, manifest)
    imports = transport_inputs(lock, importer, transport)
    crypto = imports['crypto-prefix']
    importer.relocate_crypto_metadata(crypto, lock['artifacts']['crypto-prefix'], imports['crypto-proof'], lock['artifacts']['crypto-proof'])
    proof_dir = crypto/'target-proof'
    proof_helper = ROOT/'ci/prove_crypto_features.py'
    commands.run('fresh-crypto-proof', [sys.executable, '-I', proof_helper, crypto/'prefix', proof_dir])
    importer.emit_validated_overlay(proof_helper, crypto/'prefix', proof_dir, imports['wine-headers']/'prefix/include/config.h')
    commands.run('source-ntdll-build', [sys.executable, '-I', ROOT/'ci/build_ntdll_control.py', source,
                 imports['wine-headers']/'prefix', imports['freetype']/'prefix', imports['ffmpeg']/'prefix',
                 crypto/'prefix', proof_dir, proof_helper, RUN/'build'])
    recheck_sources(commands, manifest, before)
    proof_module = load_module(proof_helper, PINS['ci/prove_crypto_features.py'], 'reviewed_ntdll_proof')
    raw_archive_check(RUN/'build', manifest, proof_module)
    reviewed_inputs()
    write_json(RUN/'worker-result.json', {'result': 'validated-awaiting-packaging', 'source_modified': False,
               'target_binaries_run': False, 'native_link_performed': False, 'signed': False, 'installed': False})


def finalizer():
    lock = reviewed_inputs()
    manifest = read_json(ROOT/'ntdll-source-manifest.json')
    outcome = read_json(OUT/'worker-exit.json')
    success = outcome['exit_code'] == 0 and (RUN/'worker-result.json').exists()
    proof_dir = RUN/'imports/crypto-prefix/target-proof'
    if success:
        try:
            proof_module = load_module(ROOT/'ci/prove_crypto_features.py', PINS['ci/prove_crypto_features.py'], 'reviewed_ntdll_final_proof')
            raw_archive_check(RUN/'build', manifest, proof_module)
            proof_module.verify_passed_proof(RUN/'imports/crypto-prefix/prefix', proof_dir, RUN/'imports/wine-headers/prefix/include/config.h')
            require(read_json(RUN/'ntdll-source-identity.json') == read_json(RUN/'ntdll-source-postcheck.json'), 'Source postcheck missing or changed')
        except Exception as error:
            success = False
            write_json(RUN/'finalization-failure.json', {'result': 'failed-final-verification', 'error': str(error)})
    controls = sorted(set(PINS) | {'ci/run_ntdll_control.py', 'ci/import_ntdll_dependencies.py', 'ci/ntdll-dependency-artifacts-lock.json', lock['transport']['helper_path']})
    candidates = [(ROOT/name, 'ControlSources/'+name) for name in controls]
    candidates += [(RUN/name, 'Wrapper/'+name) for name in ('commands.json', 'preflight.json', 'ntdll-source-identity.json', 'ntdll-source-postcheck.json', 'worker-result.json', 'failure.json', 'finalization-failure.json')]
    candidates += [(OUT/name, 'Wrapper/'+name) for name in ('worker.log', 'worker-exit.json')]
    if (RUN/'commands.json').exists():
        for record in read_json(RUN/'commands.json'):
            name = safe_name(record['log'])
            require(re.fullmatch(r'logs/[a-z0-9-]+\.log', name), 'Unapproved wrapper log')
            candidates.append((RUN/name, 'Wrapper/'+name))
    candidates += [(RUN/'build'/name, 'NtdllEvidence/'+name) for name in helper_evidence(manifest)]
    candidates += [(proof_dir/name, 'FreshCryptoProof/'+name) for name in proof_evidence()]
    for kind in sorted(ARTIFACT_KINDS):
        candidates += [(RUN/'imports'/kind/'import-manifest.json', 'Imports/'+kind+'/import-manifest.json'),
                       (RUN/'transport'/(kind+'.json'), 'Transport/'+kind+'.json')]
    candidates.append((RUN/'imports/crypto-prefix/relocation-manifest.json', 'Imports/crypto-prefix/relocation-manifest.json'))
    report = {'result': 'passed-source-ntdll-archive-control' if success else 'failed-source-ntdll-control',
              'madeira': MADEIRA, 'wine': WINE, 'target_binaries_run': False, 'signed': False, 'installed': False,
              'native_link_performed': False, 'dependency_lock_sha256': digest(ROOT/'ci/ntdll-dependency-artifacts-lock.json'),
              'wrapper_sha256': digest(ROOT/'ci/run_ntdll_control.py'), 'worker_exit': outcome,
              'qualification': 'Static 37-object source archive only; unresolved native/app providers and existing upstream limits remain.'}
    evidence = write_zip(OUT/'ntdll-evidence.zip', checked_candidates(candidates, optional=True), report)
    products = {'evidence': evidence}
    if success:
        source_record = read_json(RUN/'ntdll-source-identity.json')
        files = [(RUN/'build/libntdll_unix.a', 'Library/libntdll_unix.a'), (OUT/'ntdll-evidence.zip', 'Evidence/ntdll-evidence.zip')]
        for tag, prefix in (('madeira', ''), ('wine', 'wine/')):
            for row in source_record[tag]['materialized']:
                path = RUN/'source'/prefix/safe_name(row['path'])
                verify_hash(path, row['sha256'])
                files.append((path, 'Sources/Madeira/'+prefix+row['path']))
        files += [(RUN/'original-zips'/(kind+'.zip'), 'OriginalDependencyArchives/'+kind+'.zip') for kind in sorted(ARTIFACT_KINDS)]
        for kind in sorted(ARTIFACT_KINDS):
            verify_hash(RUN/'original-zips'/(kind+'.zip'), lock['artifacts'][kind]['sha256'])
        for name in lock['artifacts']['crypto-prefix']['metadata_relocation']['files']:
            files.append((RUN/'imports/crypto-prefix/prefix'/safe_name(name), 'RelocatedCryptoMetadata/'+name))
        products['archive'] = write_zip(OUT/'ntdll-archive.zip', checked_candidates(files), report)
    write_json(OUT/'result.json', dict(report, products=products))
    return 0 if success else 1

def supervise(argv, log, timeout, env, cwd=ROOT, poll=0.1):
    """Always kill the started process group, including remaining children in the started process group."""
    require(timeout > 0, 'Aggregate process budget exhausted')
    start = time.monotonic()
    timed_out = False
    with safe(log, fresh=True).open('xb') as stream:
        proc = subprocess.Popen([str(x) for x in argv], cwd=cwd, env=env, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            while True:
                elapsed = time.monotonic()-start
                if elapsed >= timeout or log.stat().st_size > 64*MIB:
                    timed_out = True
                    break
                if proc.poll() is not None:
                    break
                time.sleep(min(poll, max(0.001, timeout-elapsed)))
        finally:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait()
    return {'exit_code': 124 if timed_out else proc.returncode, 'timed_out': timed_out,
            'elapsed_seconds': round(time.monotonic()-start, 3), 'process_group_terminated': True}

def initialize():
    require(sys.platform == 'darwin' and sys.version_info[:3] == (3, 12, 7), 'Reviewed Apple host and existing Python3.12.7 required')
    require(os.environ.get('FREE_QUOTA_VERIFIED') == 'true' and os.environ.get('PRIVATE_SOURCE_VERIFIED') == 'true', 'Manual free-quota/private-source confirmations required')
    reviewed_inputs()
    safe(ROOT, directory=True)
    (ROOT/'.work').mkdir(exist_ok=True)
    safe(ROOT/'.work', directory=True)
    for p in (RUN, OUT):
        safe(p, fresh=True)
    RUN.mkdir()
    OUT.mkdir()
    for name in ('home', 'tmp', 'logs', 'imports', 'original-zips', 'transport'):
        (RUN/name).mkdir()

def discard_reusable(out=OUT, reason='Worker/finalizer did not complete successfully'):
    """A failed/terminated run may retain diagnostics, never a reusable product."""
    safe(out, directory=True)
    for name in ('ntdll-archive.zip', 'ntdll-archive.zip.part', 'result.json', 'result.json.pending'):
        path = out/name
        if path.exists() or path.is_symlink():
            require(not path.is_dir(), 'Unexpected product directory')
            path.unlink()
    write_json(out/'result.json', {'result': 'failed-source-ntdll-control', 'reuse_permitted': False,
               'error': reason, 'target_binaries_run': False, 'signed': False, 'installed': False})


def enforce_outcome(worker_result, final_result, out=OUT):
    success = worker_result['exit_code'] == final_result['exit_code'] == 0
    if not success:
        discard_reusable(out)
    return 0 if success else 1


def main():
    if sys.argv[1:] == ['--worker']:
        try:
            worker()
            return 0
        except Exception as error:
            write_json(RUN/'failure.json', {'result': 'failed', 'error': str(error), 'target_binaries_run': False})
            print('ntdll control failed: '+str(error), file=sys.stderr)
            return 1
    if sys.argv[1:] == ['--finalize']:
        return finalizer()
    require(not sys.argv[1:], 'No public CLI arguments accepted')
    start = time.monotonic()
    initialize()
    env = clean_environment(RUN/'home', RUN/'tmp')
    command = [sys.executable, '-I', ROOT/'ci/run_ntdll_control.py']
    left = AGGREGATE_SECONDS-(time.monotonic()-start)
    try:
        outcome = supervise(command+['--worker'], OUT/'worker.log', left-FINALIZE_RESERVE, env)
        write_json(OUT/'worker-exit.json', outcome)
        left = AGGREGATE_SECONDS-(time.monotonic()-start)
        final = supervise(command+['--finalize'], OUT/'finalize.log', left, env)
        code = enforce_outcome(outcome, final)
        write_json(OUT/'wrapper-exit.json', {'worker': outcome, 'finalizer': final, 'aggregate_seconds': round(time.monotonic()-start, 3), 'budget_seconds': AGGREGATE_SECONDS})
        return code
    except BaseException:
        discard_reusable(reason='Supervisor interrupted or failed')
        raise

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        print('ntdll wrapper refused: '+str(error), file=sys.stderr)
        raise SystemExit(1)
