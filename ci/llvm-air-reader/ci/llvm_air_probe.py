#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Proposal: build a pinned native LLVM15 reader, or parse three locked DXMT AIRs.
No source acquisition, installation, dispatch, Metal/GPU/MSC API, or target run.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import selectors
import threading
import shutil
import signal
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
LOCK_PATH = HERE / 'probe-source-lock.json'
LOCK = json.loads(LOCK_PATH.read_text())
SUPPORT = HERE / 'frozen/llvm_control_support.py'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def load_core():
    require(sha(SUPPORT) == LOCK['frozen_support_sha256'], 'Frozen LLVM support changed')
    require(sha(SUPPORT.with_name('llvm-source-lock.json')) == LOCK['frozen_lock_sha256'],
            'Frozen LLVM source lock changed')
    spec = importlib.util.spec_from_file_location('frozen_llvm_support', SUPPORT)
    core = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(core)
    return core


core = load_core()


def strict_reader_macho(data):
    proof = core.macho(data, 1, '26.0', '26.5', True)
    count, size = core.struct.unpack_from('<2I', data, 16)
    cursor = 32
    for _ in range(count):
        command, length = core.struct.unpack_from('<2I', data, cursor)
        require(command not in (0x6, 0x7, 0x80000018, 0x8000001f, 0x80000023, 0x20),
                'Weak/reexport/lazy/prebound reader dependency forbidden')
        cursor += length
    return proof


class ProcessInterrupted(Exception):
    def __init__(self, signum):
        self.status = 128 + signum
        super().__init__('Interrupted by signal ' + str(signum))


def bounded_run(argv, cwd, env, log, seconds, new_session=True, max_log_bytes=32 * 1024**2):
    """Record before launch; cap output; cancel every owned process on exceptions."""
    require(seconds > 0, 'Aggregate time budget exhausted')
    log = Path(log)
    sidecar = log.with_name(log.name + '.command.json')
    require(not sidecar.exists(), 'Fresh attempted-command sidecar required')
    attempted = {'argv': list(map(str, argv)), 'cwd': str(cwd), 'status': 'attempted',
                 'timeout_seconds': seconds, 'log_limit_bytes': max_log_bytes,
                 'new_session': new_session, 'stdin': 'DEVNULL', 'exit_code': None}
    write(sidecar, attempted)
    started, proc, selector, old_handler = time.monotonic(), None, None, None
    def cancel():
        if proc is None:
            return
        try:
            if new_session:
                os.killpg(proc.pid, signal.SIGTERM)
            elif proc.poll() is None:
                proc.terminate()
        except ProcessLookupError:
            pass
        try:
            proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            try:
                if new_session:
                    os.killpg(proc.pid, signal.SIGKILL)
                else:
                    proc.kill()
            except ProcessLookupError:
                pass
            proc.wait(timeout=5)
        # The main child may have exited while a grandchild retained stdout.
        if new_session:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    try:
        if threading.current_thread() is threading.main_thread():
            old_handler = signal.getsignal(signal.SIGTERM)
            def interrupted(signum, frame):
                raise ProcessInterrupted(signum)
            signal.signal(signal.SIGTERM, interrupted)
        with log.open('xb') as stream:
            proc = subprocess.Popen(list(map(str, argv)), cwd=cwd, env=env,
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, start_new_session=new_session)
            attempted.update(status='running', pid=proc.pid)
            write(sidecar, attempted)
            selector = selectors.DefaultSelector()
            os.set_blocking(proc.stdout.fileno(), False)
            selector.register(proc.stdout, selectors.EVENT_READ)
            amount, code = 0, None
            while selector.get_map() or proc.poll() is None:
                if time.monotonic() - started >= seconds:
                    code = 124
                    attempted['failure_reason'] = 'timeout'
                    cancel()
                    break
                for key, events in selector.select(min(.1, max(.001, seconds-(time.monotonic()-started)))):
                    data = os.read(key.fileobj.fileno(), 65536)
                    if not data:
                        selector.unregister(key.fileobj)
                        continue
                    room = max_log_bytes - amount
                    stream.write(data[:room])
                    amount += min(room, len(data))
                    if len(data) > room:
                        code = 125
                        attempted['failure_reason'] = 'log_limit'
                        cancel()
                        break
                if code is not None:
                    break
            if code is None:
                code = proc.wait(timeout=5)
            attempted.update(status='finished', exit_code=code, log_bytes=amount,
                             seconds=round(time.monotonic()-started,3))
            write(sidecar, attempted)
            return code
    except BaseException as exc:
        cancel()
        attempted.update(status='exception', error=str(exc),
                         exit_code=exc.status if isinstance(exc, ProcessInterrupted) else 1,
                         seconds=round(time.monotonic()-started,3))
        write(sidecar, attempted)
        raise
    finally:
        if selector is not None:
            selector.close()
        if proc is not None and proc.stdout is not None:
            proc.stdout.close()
        if old_handler is not None:
            signal.signal(signal.SIGTERM, old_handler)


def host_archive(path, compiled):
    """Validate every actual member as macOS; target archives cannot slip in."""
    names, indexes, rows = set(), [], []
    object_hashes = {row['object_sha256'] for row in compiled}
    with Path(path).open('rb') as stream:
        require(stream.read(8) == b'!<arch>\n', 'Regular native ar archive required')
        while True:
            header = stream.read(60)
            if not header:
                break
            require(len(header) == 60 and header[-2:] == b'`\n', 'Malformed ar header')
            amount = int(header[48:58].decode('ascii').strip())
            require(0 < amount <= 256 * 1024**2, 'Archive member size outside bound')
            data = stream.read(amount)
            require(len(data) == amount, 'Truncated archive')
            name = header[:16].decode('ascii').strip()
            if name.startswith('#1/'):
                length = int(name[3:])
                require(0 < length < amount and length <= 4096, 'Bad BSD archive name')
                name, data = data[:length].rstrip(b'\0').decode('utf-8'), data[length:]
            else:
                name = name.removesuffix('/')
            if amount % 2:
                require(stream.read(1) == b'\n', 'Invalid ar padding')
            if name in core.AR_INDEXES:
                require(name not in indexes, 'Repeated ar index')
                indexes.append(name)
                continue
            require(re.fullmatch(r'[A-Za-z0-9_.+-]+\.o', name) and name not in names,
                    'Unexpected/duplicate native member')
            names.add(name)
            digest = hashlib.sha256(data).hexdigest()
            require(digest in object_hashes, 'Archive member lacks verified compile evidence')
            allowed = any(x['archive'] == Path(path).name and x['member'] == name
                          for x in core.LOCK['assembly_unspecified_sdk'])
            proof = core.macho(data, 1, '26.0', '26.5', assembly_sdk_unspecified=allowed)
            rows.append({'name': name, 'sha256': digest, 'bytes': len(data), 'macho': proof})
            require(len(rows) <= 30000, 'Too many archive members')
    require(rows and indexes, 'Native archive has no objects/index')
    return {'path': Path(path).name, 'sha256': sha(path), 'members': rows, 'indexes': indexes}


class Build(core.Control):
    def __init__(self, source, out, native):
        super().__init__(source, out, 'native')
        self.native = native
        self.deadline = time.monotonic() + LOCK['build_total_seconds']

    def run(self, name, argv, cwd=None, binary=False):
        require(re.fullmatch(r'[A-Za-z0-9_.-]+', name), 'Invalid command name')
        log = self.build / 'logs' / (name + '.log')
        limit = {'configure': LOCK['configure_seconds'],
                 'build-host-reader-libraries': LOCK['library_build_seconds'],
                 'compile-link-reader': LOCK['probe_compile_seconds']}.get(name, 90)
        limit = min(limit, self.deadline - time.monotonic())
        start = time.monotonic()
        record = {'name': name, 'argv': list(map(str, argv)), 'cwd': str(cwd or self.build),
                  'status': 'attempted', 'exit_code': None, 'timeout_seconds': limit}
        self.commands.append(record)
        write(self.build / 'manifests/commands.json', self.commands)
        try:
            code = bounded_run(argv, cwd or self.build, self.env, log, limit)
            record.update(status='finished', exit_code=code, seconds=round(time.monotonic()-start,3))
        except BaseException as exc:
            record.update(status='exception', error=str(exc),
                          exit_code=exc.status if isinstance(exc, ProcessInterrupted) else 1)
            raise
        finally:
            write(self.build / 'manifests/commands.json', self.commands)
        if code:
            raise core.CommandFailure(name, code)
        return log.read_bytes() if binary else log.read_text(errors='replace').strip()

    def reader_build(self):
        self.preflight()
        require(self.versions['macosx'] == '26.5', 'Exact native SDK26.5 required')
        self.sources()
        for row in LOCK['source_guards']:
            require(sha(core.real_path(self.llvm / row['path'], self.llvm, True)) == row['sha256'],
                    'Parser closure source guard changed: ' + row['path'])
        require(sha(HERE / 'air_reader.cpp') == LOCK['probe_source_sha256'], 'Own probe source changed')
        native_root = core.real_path(self.native, self.source / '.work')
        require(sha(native_root / 'manifest.json') == LOCK['native_generator_input']['inner_manifest_sha256'],
                'Exact native generator manifest pin required')
        require(sha(native_root / 'artifact-manifest.json') == LOCK['native_generator_input']['schema2_transport']['provenance']['producer_manifest_sha256'],
                'Exact outer native artifact manifest pin required')
        require(sha(native_root / 'native/bin/llvm-tblgen') == LOCK['native_generator_input']['binary_sha256'],
                'Exact native generator binary pin required')
        native = self.import_native()  # Full frozen provenance + raw Mach-O before --version.
        self.sdk = self.sdks['macosx']
        self.definitions = core.cmake_definitions('native', self.tools, self.sdk, self.prefix)
        self.definitions['LLVM_TABLEGEN'] = str(native)
        write(self.build / 'manifests/configuration.json', self.definitions)
        write(self.build / 'manifests/configuration-delta.json', {
            'base': 'frozen native llvm-tblgen configuration',
            'LLVM_TABLEGEN': str(native), 'build_targets': LOCK['build_targets'],
            'export': 'one native LLVM15 AIR reader; no LLVM libraries/headers exported'})
        self.run('configure', [self.tools['cmake'], '-S', self.cmake_source, '-B', self.obj,
            '-G', 'Unix Makefiles', *['-D' + k + '=' + v for k, v in sorted(self.definitions.items())]])
        self.check_cache()
        self.run('build-host-reader-libraries', [self.tools['cmake'], '--build', self.obj,
            '--parallel', '4', '--target', *LOCK['build_targets'], '--', 'VERBOSE=1'])
        self.check_cache()
        # No renamed tblgen manifest and no mutation of the frozen target list.
        self.evidence()
        compiled = json.loads((self.build / 'manifests/compiled-sources.json').read_text())
        archives = [core.real_path(self.obj / 'lib' / ('lib' + n + '.a'), self.obj, True)
                    for n in LOCK['libraries']]
        write(self.build / 'manifests/host-archives.json', [host_archive(p, compiled) for p in archives])
        self.prefix = self.build / 'reader'
        (self.prefix / 'bin').mkdir(parents=True)
        source = self.build / 'reader-source/air_reader.cpp'
        source.parent.mkdir()
        shutil.copyfile(HERE / 'air_reader.cpp', source)
        binary = self.prefix / 'bin/llvm15-air-reader'
        command = [self.tools['clang++'], '-std=c++17', '-O2', '-DNDEBUG', '-fno-exceptions',
            '-fno-rtti', '-funwind-tables', '-arch', 'arm64', '-mmacosx-version-min=26.0',
            '-isysroot', self.sdk, '-I' + str(self.obj / 'include'),
            '-I' + str(self.cmake_source / 'include'), '-MD', '-MF', source.with_suffix('.d'), source, *archives, '-lm', '-o', binary]
        self.run('compile-link-reader', command)
        deptext = source.with_suffix('.d').read_text().replace('\\\n', ' ')
        require(': ' in deptext, 'Malformed probe compiler depfile')
        for value in core.shlex.split(deptext.split(': ', 1)[1]):
            included = (self.build / value).resolve()
            if included.is_relative_to(self.llvm):
                included = core.real_path(included, self.llvm, True)
                destination = self.build / 'notices/compiled-source' / included.relative_to(self.llvm)
                destination.parent.mkdir(parents=True, exist_ok=True)
                if destination.exists():
                    require(sha(destination) == sha(included), 'Probe source notice collision')
                else:
                    shutil.copyfile(included, destination)
        copied_sources = [p for p in (self.build / 'notices/compiled-source').rglob('*') if p.is_file()]
        require(len(copied_sources) <= 5000 and sum(p.stat().st_size for p in copied_sources) <= 128 * 1024**2,
                'Probe source/notice closure exceeds bound')
        # SDK/toolchain depfile paths are provenance only; never opened or copied.
        # This is checked BEFORE any execution; build stage does not run the reader.
        proof = strict_reader_macho(binary.read_bytes())
        write(self.build / 'manifests/reader-macho.json', proof)
        for src in (HERE / 'air_reader.cpp', HERE / 'llvm_air_probe.py', LOCK_PATH):
            shutil.copyfile(src, self.build / 'reader-source' / src.name)
        shutil.copyfile(SUPPORT, self.build / 'reader-source/llvm_control_support.py')
        shutil.copyfile(SUPPORT.with_name('llvm-source-lock.json'), self.build / 'reader-source/llvm-source-lock.json')
        license_file = HERE.parent / 'research/PROJECT-LICENSE'
        shutil.copyfile(license_file, self.build / 'notices/PROJECT-LICENSE')
        write(self.build / 'manifests/notices.json', [core.file_record(p, self.build)
            for p in sorted((self.build / 'notices').rglob('*')) if p.is_file()])
        files = []
        for directory in ('reader', 'reader-source', 'manifests', 'notices', 'evidence', 'logs'):
            files.extend(core.file_record(p, self.build)
                         for p in sorted((self.build / directory).rglob('*')) if p.is_file())
        write(self.build / 'manifests/outputs.json', files)
        write(self.build / 'manifest.json', {'schema': 1, 'artifact_kind': LOCK['artifact_kind'],
            'status': 'reader_built_not_air_tested', 'llvm_commit': LOCK['llvm_commit'],
            'probe_source_sha256': LOCK['probe_source_sha256'], 'probe_lock_sha256': sha(LOCK_PATH),
            'helper_sha256': sha(HERE / 'llvm_air_probe.py'),
            'frozen_support_sha256': LOCK['frozen_support_sha256'], 'frozen_lock_sha256': LOCK['frozen_lock_sha256'],
            'binary': core.file_record(binary, self.build), 'outputs_sha256': sha(self.build / 'manifests/outputs.json'),
            'build_targets': LOCK['build_targets'], 'native_minimum': '26.0', 'sdk_version': '26.5',
            'xcode_version': '26.6', 'cmake_version': '4.3.4', 'jobs': 4,
            'air_parsed': False, 'target_executed': False, 'gpu_run': False,
            'sdk_copied': False, 'explicit_signing_performed': False,
            'package_install_performed': False, 'converter_opened_or_run': False})


def header_bytes(path, ident):
    text = Path(path).read_text('ascii')
    match = re.fullmatch(r'\s*(?:const\s+)?unsigned char ' + re.escape(ident) +
        r'\[\]\s*=\s*\{([\s\S]*?)\};\s*(?:const\s+)?unsigned int ' +
        re.escape(ident) + r'_len\s*=\s*(\d+)\s*;\s*', text)
    require(match is not None, 'Header must be exactly xxd-style array and length')
    body = match[1]
    require(re.fullmatch(r'\s*(?:0x[0-9a-fA-F]{2}\s*,\s*)*(?:0x[0-9a-fA-F]{2}\s*,?\s*)?', body),
            'Unexpected header array tokens')
    raw = bytes(int(x, 16) for x in re.findall(r'0x([0-9a-fA-F]{2})', body))
    require(len(raw) == int(match[2]), 'Header byte length mismatch')
    return raw


def generation_sdk(root, argv_sdk):
    evidence_path = core.real_path(root / 'manifests/preflight.json', root, True)
    evidence = json.loads(evidence_path.read_text())
    require(evidence.get('xcode') == 'Xcode 26.6\nBuild version 17F113' and
            evidence.get('sdk', {}).get('macosx_version') == '26.5',
            'Producer selected Xcode/macOS SDK identity differs')
    developer = Path(evidence.get('environment', {}).get('DEVELOPER_DIR', '')).resolve(strict=True)
    require(developer.parts[-2:] == ('Contents', 'Developer'), 'Full selected Xcode required')
    lookup = Path(evidence['sdk']['macosx'])
    require(lookup.is_absolute(), 'Absolute producer SDK root required')
    canonical = lookup.resolve(strict=True)
    require(canonical.is_dir() and canonical.is_relative_to(developer / 'Platforms/MacOSX.platform/Developer/SDKs'),
            'Producer SDK outside selected macOS platform')
    require(Path(argv_sdk).is_absolute() and Path(argv_sdk).resolve(strict=True) == canonical,
            'Generator SDK alias differs from exact selected canonical root')
    alias = canonical.parent / 'MacOSX26.5.sdk'
    if alias.exists() or alias.is_symlink():
        require(alias.resolve(strict=True) == canonical, 'Versioned SDK alias points outside selected root')
    return {'preflight_path': 'manifests/preflight.json', 'preflight_sha256': sha(evidence_path),
            'xcode': evidence['xcode'], 'sdk_version': '26.5', 'lookup_path': str(lookup),
            'canonical_path': str(canonical), 'developer_dir': str(developer),
            'versioned_alias_present': alias.exists()}


def make_input_lock(dxmt_source_root, input_root, generation_records):
    """Call after the producer generates all3; retain returned lock and its SHA.
    generation_records maps IDs to actual successful command records, not plans.
    The caller must persist this JSON BEFORE parsing and pass the file SHA to run.
    """
    source_root, root = core.real_path(dxmt_source_root), core.real_path(input_root)
    require(set(generation_records) == {x['id'] for x in LOCK['inputs']}, 'Exactly three generation records required')
    rows = []
    for expected in LOCK['inputs']:
        source = core.real_path(source_root / expected['source'], source_root, True)
        require(sha(source) == expected['source_sha256'], 'DXMT shader source hash mismatch')
        record = generation_records[expected['id']]
        require(record.get('exit_status') == 0, 'Metal generation did not succeed')
        argv = record.get('argv')
        require(isinstance(argv, list) and len(argv) == 12, 'Exact Metal generation argv required')
        require(argv[:6] == ['/usr/bin/xcrun', '--sdk', 'macosx', 'metal', '-std=metal3.1',
                '--target=air64-apple-macos14.0'] and argv[6:8] == ['-c', str(source)] and
                argv[8] == '-o' and argv[10] == '-isysroot', 'Metal generator arguments differ')
        air = core.real_path(root / expected['air_path'], root, True)
        header = core.real_path(root / expected['header_path'], root, True)
        require(argv[9] == str(air), 'Metal output path differs')
        sdk = generation_sdk(root, argv[11])
        require(4 <= air.stat().st_size <= LOCK['max_air_bytes'], 'AIR size outside bound')
        require(header.stat().st_size <= LOCK['max_air_bytes'] * 7, 'Header size outside bound')
        require(header_bytes(header, expected['id']) == air.read_bytes(), 'AIR/header payload mismatch')
        rows.append({**expected, 'air_sha256': sha(air), 'air_bytes': air.stat().st_size,
                     'header_sha256': sha(header), 'header_bytes': header.stat().st_size,
                     'generator': record, 'generation_toolchain': sdk})
    return {'schema': 1, 'kind': 'dxmt-air-input-lock', 'dxmt_commit': LOCK['dxmt_commit'],
            'probe_source_lock_sha256': sha(LOCK_PATH), 'inputs': rows}


def validate_inputs(root, lock):
    root = core.real_path(root)
    require(lock.get('schema') == 1 and lock.get('kind') == 'dxmt-air-input-lock' and
            lock.get('dxmt_commit') == LOCK['dxmt_commit'] and
            lock.get('probe_source_lock_sha256') == sha(LOCK_PATH), 'Input lock identity differs')
    require(isinstance(lock.get('inputs'), list) and len(lock['inputs']) == 3, 'Exactly three locked AIRs required')
    result = []
    for expected, row in zip(LOCK['inputs'], lock['inputs']):
        require(all(row.get(k) == v for k, v in expected.items()), 'AIR input identity/order changed')
        air = core.real_path(root / row['air_path'], root, True)
        header = core.real_path(root / row['header_path'], root, True)
        for name, path, cap in (('air', air, LOCK['max_air_bytes']),
                                ('header', header, LOCK['max_air_bytes'] * 7)):
            require(4 <= path.stat().st_size <= cap and path.stat().st_size == row[name + '_bytes'] and
                    sha(path) == row[name + '_sha256'], 'Locked input bytes changed: ' + name)
        require(header_bytes(header, row['id']) == air.read_bytes(), 'AIR/header payload mismatch')
        generator = row.get('generator', {})
        require(generator.get('exit_status') == 0 and isinstance(generator.get('argv'), list),
                'Missing successful generation evidence')
        argv = generator['argv']
        require(len(argv) == 12 and argv[:6] == ['/usr/bin/xcrun', '--sdk', 'macosx', 'metal',
                '-std=metal3.1', '--target=air64-apple-macos14.0'] and argv[6] == '-c' and
                argv[8] == '-o' and argv[10] == '-isysroot', 'Locked generation command differs')
        require(Path(argv[7]).name == row['id'] + '.metal' and
                Path(argv[9]).name == row['id'] + '.air', 'Generation input/output identity differs')
        require(row.get('generation_toolchain') == generation_sdk(root, argv[11]),
                'Generation toolchain evidence changed')
        result.append((row, air, header))
    return result


def validate_export(root, expected_manifest_sha256):
    require(re.fullmatch('[0-9a-f]{64}', expected_manifest_sha256), 'Exact reader manifest hash required')
    root = core.real_path(root)
    require(sha(core.real_path(root / 'manifest.json', root, True)) == expected_manifest_sha256,
            'Reader manifest pin mismatch')
    manifest = json.loads(core.real_path(root / 'manifest.json', root, True).read_text())
    require(manifest.get('artifact_kind') == LOCK['artifact_kind'] and
            manifest.get('status') == 'reader_built_not_air_tested', 'Wrong reader artifact kind/status')
    for key, value in {'schema': 1, 'llvm_commit': LOCK['llvm_commit'],
                      'probe_source_sha256': LOCK['probe_source_sha256'],
                      'probe_lock_sha256': sha(LOCK_PATH), 'helper_sha256': sha(HERE / 'llvm_air_probe.py'),
                      'frozen_support_sha256': LOCK['frozen_support_sha256'],
                      'frozen_lock_sha256': LOCK['frozen_lock_sha256'],
                      'build_targets': LOCK['build_targets'], 'native_minimum': '26.0',
                      'sdk_version': '26.5', 'jobs': 4, 'xcode_version': '26.6',
                      'cmake_version': '4.3.4', 'air_parsed': False,
                      'target_executed': False, 'gpu_run': False, 'sdk_copied': False,
                      'explicit_signing_performed': False, 'package_install_performed': False,
                      'converter_opened_or_run': False}.items():
        require(manifest.get(key) == value, 'Reader artifact identity changed: ' + key)
    outputs = core.real_path(root / 'manifests/outputs.json', root, True)
    require(sha(outputs) == manifest['outputs_sha256'], 'Reader inventory hash changed')
    names = set()
    for row in json.loads(outputs.read_text()):
        relative = str(core.safe_relative(row['path']))
        require(relative not in names, 'Duplicate exported path')
        names.add(relative)
        require(core.file_record(root / relative, root) == row, 'Reader export changed: ' + relative)
    require({'reader/bin/llvm15-air-reader', 'reader-source/air_reader.cpp',
             'reader-source/llvm_air_probe.py', 'reader-source/probe-source-lock.json',
             'reader-source/llvm_control_support.py', 'reader-source/llvm-source-lock.json',
             'manifests/source.json', 'manifests/host-archives.json', 'manifests/compiled-sources.json',
             'manifests/native-import.json', 'manifests/reader-macho.json',
             'manifests/commands.json', 'notices/LLVM-LICENSE.TXT', 'notices/PROJECT-LICENSE'} <= names,
            'Reader export provenance incomplete')
    binary = core.real_path(root / 'reader/bin/llvm15-air-reader', root, True)
    require(core.file_record(binary, root) == manifest['binary'], 'Reader binary identity changed')
    proof = strict_reader_macho(binary.read_bytes())
    require(proof == json.loads((root / 'manifests/reader-macho.json').read_text()), 'Reader Mach-O witness changed')
    return manifest, binary


def validate_witness(witness, row):
    require(witness.get('schema') == 1 and witness.get('status') == 'parsed' and
            witness.get('llvm_version') == '15.0.7' and witness.get('id') == row['id'] and
            witness.get('input_bytes') == row['air_bytes'], 'Invalid parse witness')
    require(witness.get('target_triple') in ('air64-apple-macosx14.0.0', 'air64-apple-macos14.0.0',
            'air64-apple-macosx14.0', 'air64-apple-macos14.0'), 'Wrong actual AIR target')
    require(Path(witness.get('source_filename', '')).name == row['id'] + '.metal' and
            isinstance(witness.get('module_identifier'), str) and bool(witness.get('data_layout')),
            'Missing/wrong module identity')
    functions = witness.get('functions', [])
    require([x.get('name') for x in functions] == row['required_functions'], 'Required functions differ')
    for fn in functions:
        require(fn.get('declaration') is False and fn.get('external_linkage') is True and
                isinstance(fn.get('type'), str) and bool(fn['type']) and
                isinstance(fn.get('basic_blocks'), int) and fn['basic_blocks'] > 0,
                'Required function lacks a real body/type')
    require(all(witness.get(key) is False for key in ('linker_run', 'gpu_run', 'target_executed')),
            'Parse witness exceeded scope')


def parse_all(export, expected_reader_manifest_sha256, input_root, input_lock, expected_lock_sha256, output, externally_supervised=False):
    require(isinstance(externally_supervised, bool), 'Explicit boolean supervision mode required')
    require(re.fullmatch('[0-9a-f]{64}', expected_lock_sha256), 'Exact input lock hash required')
    input_lock = core.real_path(input_lock, file=True)
    require(sha(input_lock) == expected_lock_sha256, 'Input lock hash mismatch')
    lock = json.loads(input_lock.read_text())
    inputs = validate_inputs(input_root, lock)
    manifest, binary = validate_export(export, expected_reader_manifest_sha256)  # Inspect before running imported code.
    output = Path(output).absolute()
    core.real_path(output.parent)
    require(not output.exists() and not output.is_symlink() and '.work' in output.parts,
            'Fresh output beneath a .work directory required')
    output.mkdir()
    for name in ('home', 'tmp', 'logs', 'inputs'):
        (output / name).mkdir()
    deadline = time.monotonic() + LOCK['parse_total_seconds']
    env = core.base_environment(output)
    try:
        require(sys.platform == 'darwin', 'Native macOS parse host required')
        for label, args, pattern in (
            ('arch', ['/usr/bin/uname', '-m'], r'arm64'),
            ('cpu', ['/usr/sbin/sysctl', '-n', 'machdep.cpu.brand_string'], r'Apple M2(?: \(Virtual\))?'),
            ('os', ['/usr/bin/sw_vers', '-productVersion'], r'\d+\.\d+(?:\.\d+)?')):
            log = output / 'logs' / (label + '.log')
            code = bounded_run(args, output, env, log, min(10, deadline - time.monotonic()),
                               new_session=not externally_supervised)
            require(code == 0 and re.fullmatch(pattern, log.read_text().strip()), 'Native runtime host mismatch: ' + label)
        require(core.version_number((output / 'logs/os.log').read_text().strip()) >= core.version_number('26.0'),
                'Runtime macOS older than reader minimum')
        local_binary = output / 'llvm15-air-reader'
        shutil.copyfile(binary, local_binary)
        os.chmod(local_binary, 0o755)
        require(sha(local_binary) == manifest['binary']['sha256'], 'Reader import copy changed')
        strict_reader_macho(local_binary.read_bytes())
        shutil.copyfile(input_lock, output / 'air-inputs.lock.json')
        witnesses = []
        for row, air, header in inputs:
            local = output / 'inputs' / air.name
            shutil.copyfile(air, local)
            require(sha(local) == row['air_sha256'], 'AIR copy changed')
            log = output / 'logs' / (row['id'] + '.json')
            command = [local_binary, row['id'], local]
            code = bounded_run(command, output, env, log,
                               min(LOCK['parse_each_seconds'], deadline - time.monotonic()),
                               new_session=not externally_supervised)
            require(code == 0, f"Real LLVM15 parse failed for {row['id']} (exit {code}); see {log.name}")
            witness = json.loads(log.read_text())
            validate_witness(witness, row)
            require(sha(local) == row['air_sha256'], 'AIR changed while parser ran')
            witnesses.append({'air_sha256': row['air_sha256'], 'header_sha256': row['header_sha256'],
                'probe_sha256': sha(local_binary), 'argv': list(map(str, command)), 'exit_code': code,
                'witness': witness})
        validate_inputs(input_root, lock)
        require(sha(input_lock) == expected_lock_sha256 and sha(local_binary) == manifest['binary']['sha256'],
                'Input lock or reader changed during run')
        write(output / 'result.json', {'schema': 1, 'status': 'all_three_air_parsed',
            'llvm_commit': LOCK['llvm_commit'], 'dxmt_commit': LOCK['dxmt_commit'],
            'input_lock_sha256': expected_lock_sha256,
            'reader_manifest_sha256': sha(Path(export) / 'manifest.json'), 'modules': witnesses,
            'externally_supervised': externally_supervised,
            'linker_compatibility_proven': False, 'gpu_compatibility_proven': False,
            'app_link_proven': False, 'ios_execution_proven': False})
    except Exception as exc:
        write(output / 'failure.json', {'status': 'failed', 'error': str(exc),
                                       'compatibility_pass': False})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    build = sub.add_parser('build')
    for arg in ('source', 'out', 'native'):
        build.add_argument(arg)
    run = sub.add_parser('run')
    for arg in ('export', 'reader_manifest_sha256', 'inputs', 'input_lock', 'input_lock_sha256', 'out'):
        run.add_argument(arg)
    run.add_argument('--externally-supervised', action='store_true')
    args = parser.parse_args()
    if args.action == 'build':
        control = Build(args.source, args.out, args.native)
        try:
            control.reader_build()
        except Exception as exc:
            write(control.build / 'failure.json', {'status': 'failed', 'error': str(exc),
                                                  'air_parsed': False})
            raise
    else:
        parse_all(args.export, args.reader_manifest_sha256, args.inputs, args.input_lock, args.input_lock_sha256, args.out,
                  externally_supervised=args.externally_supervised)


if __name__ == '__main__':
    try:
        main()
    except ProcessInterrupted as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(exc.status)
    except core.CommandFailure as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(exc.status)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(2)
