#!/usr/bin/env python3
"""Bounded real iOS crypto-prefix source control. No target execution or installs."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import signal
import struct
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / '.work/madeira-crypto-control'
BUILD = SOURCE / '.work/crypto-control'
OUT = ROOT / '.work/crypto-control-artifacts'
MADEIRA = '279fd0f83170425db002fe25d6bd62f6355f497d'
MIB = 1024*1024
AGGREGATE_SECONDS = 23*60
BSD_INDEX_MEMBERS = frozenset(('__.SYMDEF','__.SYMDEF SORTED','__.SYMDEF_64','__.SYMDEF_64 SORTED'))
SPARSE = ('/.gitmodules','/COPYING','/LICENSE','/LICENSE-EXCEPTION.md','/LICENSES/',
 '/THIRD-PARTY-NOTICES.md','/docs/LICENSING.md','/docs/wine-lgpl-provenance.md',
 '/build/gnutls-ios/','/build/crypto-unix/ios_gnutls_shim.h',
 '/build/crypto-unix/gen_gnutls_symtab.sh')
LIBRARIES = ('libgmp.a','libnettle.a','libhogweed.a','libgnutls.a')
PROOF_FILES = ('proof.json','failure.json','commands.json','input-evidence.json','api-link.map')
PROOF_LOGS = ('host-architecture','developer-directory','xcode-version','sdk-version','sdk-path',
 'find-clang','find-nm','find-otool','clang-version','symbols-libgnutls.a','symbols-libhogweed.a',
 'symbols-libnettle.a','symbols-libgmp.a','target-api-link','probe-load-commands','probe-symbols')


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(MIB), b""):
            h.update(block)
    return h.hexdigest()

def checked_file(path, cap, root=None):
    path = Path(path)
    if root is not None:
        root = Path(root).absolute()
        try:
            relative = path.absolute().relative_to(root)
            if ".." in relative.parts:
                raise ValueError("Parent traversal in artifact path")
        except ValueError as error:
            raise ValueError("Artifact outside permitted root") from error
        current = root
        if current.is_symlink():
            raise ValueError("Symlink artifact root")
        for part in relative.parts:
            current /= part
            if current.is_symlink():
                raise ValueError("Symlink artifact component")
    if path.is_symlink() or not path.is_file() or path.stat().st_size > cap:
        raise ValueError(f"Unsafe, absent or oversized artifact: {path.name}")
    return path

def safe_name(name):
    path = PurePosixPath(name)
    if not name or not path.parts or path.as_posix() != name or path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name or any(ord(c) < 32 or ord(c)==127 for c in name):
        raise ValueError("Unsafe ZIP member name")
    return name

def add_file(archive, path, name, cap, root=None):
    archive.write(checked_file(path, cap, root), safe_name(name))

def validate_macho(data, name):
    if len(data) < 32:
        raise ValueError(f"Truncated Mach-O object: {name}")
    magic, cpu, subtype, kind, ncmds, size, flags, reserved = struct.unpack_from("<8I", data)
    if magic != 0xFEEDFACF or cpu != 0x0100000C or subtype != 0 or kind != 1 or reserved != 0:
        raise ValueError(f"Member must be a thin arm64 Mach-O object: {name}")
    if ncmds > 4096 or size > len(data) - 32:
        raise ValueError("Invalid Mach-O load-command bounds")
    offset, platforms, minima = 32, [], []
    for unused in range(ncmds):
        if offset + 8 > 32 + size:
            raise ValueError("Truncated Mach-O command")
        command, length = struct.unpack_from("<2I", data, offset)
        if length < 8 or length % 8 or offset + length > 32 + size:
            raise ValueError("Invalid Mach-O command size")
        if command in (0x1D, 0x8000001C, 0x27):
            raise ValueError("Signature/rpath/dyld-environment forbidden in target object")
        if command == 0x32:  # LC_BUILD_VERSION
            if length < 24:
                raise ValueError("Truncated build-version command")
            ntools = struct.unpack_from("<I", data, offset + 20)[0]
            if length != 24 + 8 * ntools:
                raise ValueError("Invalid build-version tool count")
            if struct.unpack_from("<I", data, offset + 16)[0] != 0x001A0500:
                raise ValueError("Unexpected target SDK in archive object")
            platforms.append(struct.unpack_from("<I", data, offset + 8)[0])
            minima.append(struct.unpack_from("<I", data, offset + 12)[0])
        elif command in (0x24, 0x25, 0x2F, 0x30):
            if length != 16:
                raise ValueError("Invalid legacy platform command size")
            if struct.unpack_from("<I", data, offset + 12)[0] != 0x001A0500:
                raise ValueError("Unexpected target SDK in legacy object")
            platforms.append(2 if command == 0x25 else -1)
            minima.append(struct.unpack_from("<I", data, offset + 8)[0])
        offset += length
    if offset != 32 + size or platforms != [2] or minima != [0x00110000]:
        raise ValueError(f"Member must contain exactly one iOS 17.0 platform command: {name}")

def validate_archive(path):
    """Check actual bytes; never infer every object's CPU/platform from lipo alone."""
    checked_file(path, 256 * MIB)
    names, inventory, indexes = [], [], []
    with Path(path).open("rb") as stream:
        if stream.read(8) != b"!<arch>\n":
            raise ValueError("Only regular ar archives are permitted")
        while True:
            header = stream.read(60)
            if not header:
                break
            if len(header) != 60 or header[58:] != b"`\n":
                raise ValueError("Malformed ar header")
            try:
                length = int(header[48:58].decode("ascii").strip())
                raw_name = header[:16].decode("ascii").strip()
            except (ValueError, UnicodeError) as error:
                raise ValueError("Invalid ar member header") from error
            if length < 0 or length > 32 * MIB:
                raise ValueError("Oversized ar member")
            data = stream.read(length)
            if len(data) != length:
                raise ValueError("Truncated ar member")
            if length % 2 and stream.read(1) != b"\n":
                raise ValueError("Invalid ar alignment padding")
            if raw_name.startswith("#1/"):
                if not re.fullmatch(r"#1/[0-9]+", raw_name):
                    raise ValueError("Malformed BSD ar name length")
                name_length = int(raw_name[3:])
                if name_length <= 0 or name_length > min(length, 4096):
                    raise ValueError("Invalid BSD ar name length")
                try:
                    name = data[:name_length].rstrip(b"\0").decode("ascii")
                except UnicodeError as error:
                    raise ValueError("Non-ASCII archive member name") from error
                if "\0" in name:
                    raise ValueError("Embedded NUL archive member name")
                data = data[name_length:]
            else:
                name = raw_name.rstrip("/")
            if name in BSD_INDEX_MEMBERS:
                indexes.append(name)
                if len(indexes) > 1:
                    raise ValueError("Duplicate archive index metadata")
                continue
            if name in names or not re.fullmatch(r"[A-Za-z0-9_.+-]+\.o", name):
                raise ValueError("Invalid or duplicate real archive member")
            validate_macho(data, name)
            names.append(name)
            inventory.append({"index":len(inventory),"member": name, "sha256": hashlib.sha256(data).hexdigest(),
                              "size": len(data), "architecture": "arm64", "platform": "iOS"})
    if not names or len(names) > 10000:
        raise ValueError("Missing or excessive archive objects")
    return inventory

class Control:
    def __init__(self):
        self.deadline = time.monotonic() + AGGREGATE_SECONDS
        self.steps = []

    def ensure_budget(self):
        if time.monotonic() >= self.deadline:
            raise RuntimeError("Aggregate 23-minute source control budget exhausted")

    def run(self, label, *args, cwd=ROOT, seconds=None):
        if not re.fullmatch(r"[a-z0-9-]+", label) or any(s["label"] == label for s in self.steps):
            raise ValueError("Unsafe or reused step label")
        if seconds is not None and seconds <= 0:
            raise ValueError("Nonpositive step budget")
        self.ensure_budget()
        timeout = min(self.deadline - time.monotonic(), seconds or AGGREGATE_SECONDS)
        log, started = OUT / (label + ".log"), time.monotonic()
        env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_CONFIG_NOSYSTEM="1",
                   GIT_CONFIG_GLOBAL=os.devnull, JOBS="4", LC_ALL="C", PYTHONOPTIMIZE="0", PYTHONNOUSERSITE="1")
        step = {"label": label, "exit_code": None}
        self.steps.append(step)
        with log.open("xb") as stream:
            proc = subprocess.Popen(args, cwd=cwd, env=env, stdout=stream,
                                    stderr=subprocess.STDOUT, start_new_session=True)
            try:
                while True:
                    if time.monotonic() - started >= timeout or log.stat().st_size > 64 * MIB:
                        try:
                            os.killpg(proc.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                        proc.wait()
                        code = 124
                        break
                    try:
                        code = proc.wait(timeout=min(0.25, max(0.01, timeout - (time.monotonic() - started))))
                        if log.stat().st_size > 64 * MIB or time.monotonic() - started >= timeout:
                            try:
                                os.killpg(proc.pid, signal.SIGKILL)
                            except ProcessLookupError:
                                pass
                            code = 124
                        break
                    except subprocess.TimeoutExpired:
                        pass
            except BaseException:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.wait()
                raise
        step.update(exit_code=code, elapsed_seconds=round(time.monotonic() - started, 3))
        print(f"[{label}] exit={code}", flush=True)
        if code:
            # Only explicitly started command output, never a whole environment dump.
            with log.open("rb") as stream:
                stream.seek(max(0, log.stat().st_size - 24000))
                print(stream.read().decode("utf-8", errors="replace"), flush=True)
            raise RuntimeError(f"{label} failed with exit {code}")
        return log.read_text(errors="replace") if log.stat().st_size < MIB else ""

def require_fresh(paths, root=ROOT):
    root = Path(root).absolute()
    if root.is_symlink():
        raise ValueError("Symlink work root")
    for path in paths:
        path = Path(path).absolute()
        try:
            parts = path.relative_to(root).parts
            if not parts or ".." in parts:
                raise ValueError("Invalid work directory path")
        except ValueError as error:
            raise ValueError("Work directory outside root") from error
        current = root
        for part in parts:
            current /= part
            if current.is_symlink():
                raise ValueError("Symlink work directory refused")
        if path.exists():
            raise ValueError("Fresh source and evidence directories required")

def source_bounds(root):
    total = count = 0
    for current, dirs, files in os.walk(root, followlinks=False):
        if any((Path(current) / d).is_symlink() for d in dirs):
            raise ValueError("Symlink source directory")
        for name in files:
            path = Path(current) / name
            if path.is_symlink():
                continue
            if not path.is_file():
                raise ValueError("Non-regular source file")
            total += path.stat().st_size
            count += 1
            if total > 4 * 1024 * MIB or count > 200000:
                raise ValueError("Source checkout exceeds 4 GiB/200000-file control bound")
    return {"files": count, "bytes": total}

def verify_pin(actual, expected):
    if not re.fullmatch(r"[0-9a-f]{40}", expected) or actual.strip() != expected:
        raise ValueError("Checkout does not match exact pinned source commit")
    return expected

def checkout(control, tag, path, url, commit, sparse=()):
    if path != SOURCE:
        require_fresh((path,), SOURCE)
        path.mkdir(parents=True)
    control.run(tag + "-init", "git", "init", "--quiet", cwd=path)
    control.run(tag + "-remote", "git", "remote", "add", "origin", url, cwd=path)
    control.run(tag + "-fetch", "git", "fetch", "--depth=1", "--filter=blob:none", "origin", commit, cwd=path, seconds=300)
    if sparse:
        control.run(tag + "-sparse-init", "git", "sparse-checkout", "init", "--no-cone", cwd=path)
        control.run(tag + "-sparse-paths", "git", "sparse-checkout", "set", "--no-cone", "--", *sparse, cwd=path)
    control.run(tag + "-checkout", "git", "checkout", "--detach", "FETCH_HEAD", cwd=path, seconds=180)
    verify_pin(control.run(tag + "-pin", "git", "rev-parse", "HEAD", cwd=path), commit)
    return source_bounds(path)

INPUT_LOCK = 'dd75b9aab4a4ac0da56ec42bb0a05ed9f8f63cd7252dc00ef98e8555768d4199'
INPUT_FILES = frozenset(('ci/crypto-core-control.sh','ci/crypto_control_support.py',
 'ci/prove_crypto_features.py','gnutls-api-link-probe.c','gnutls-symbol-lock.json'))


def reviewed_inputs():
    path=checked_file(ROOT/'ci/crypto-inputs-lock.json', MIB, ROOT)
    if not re.fullmatch(r'[0-9a-f]{64}',INPUT_LOCK) or os.environ.get('EXPECTED_CRYPTO_INPUTS_SHA256') != INPUT_LOCK or digest(path)!=INPUT_LOCK:
        raise ValueError('Exact reviewed crypto input lock required')
    lock=json.loads(path.read_text())
    if lock.get('madeira')!=MADEIRA or lock.get('status')!='REVIEWED' or set(lock.get('files',{})) != INPUT_FILES:
        raise ValueError('Incomplete or unreviewed crypto input closure')
    for name,sha in lock['files'].items():
        if not re.fullmatch(r'[0-9a-f]{64}',sha) or digest(checked_file(ROOT/name,4*MIB,ROOT))!=sha:
            raise ValueError('Changed reviewed input: '+name)
    return lock


def prefix_inventory():
    manifest=json.loads(checked_file(BUILD/'prefix-manifest.json',4*MIB,SOURCE).read_text())
    names=set();total=0;headers=[];archives=[];metadata=[]
    for entry in manifest['files']:
        name=safe_name(entry['path'])
        if name in names:
            raise ValueError('Duplicate prefix inventory')
        names.add(name)
        path=checked_file(BUILD/'prefix'/name,256*MIB,SOURCE)
        if path.stat().st_size != entry['size'] or digest(path)!=entry['sha256']:
            raise ValueError('Changed built prefix file')
        total+=entry['size']
        if name.startswith('include/') and name.endswith('.h'):
            headers.append((path,'Prefix/'+name,entry))
        elif name in {'lib/'+n for n in LIBRARIES}:
            archives.append((path,'Prefix/'+name,entry))
        elif name in {'lib/pkgconfig/'+n+'.pc' for n in ('gmp','nettle','hogweed','gnutls')} | {'lib/libgmp.la','lib/libgnutls.la'}:
            metadata.append((path,'Prefix/'+name,entry))
        else:
            raise ValueError('Unexpected installed prefix content: '+name)
    if len(headers)!=91 or len(archives)!=4 or len(metadata)!=6 or total>256*MIB:
        raise ValueError('Incomplete or oversized crypto prefix')
    actual={p.relative_to(BUILD/'prefix').as_posix() for p in (BUILD/'prefix').rglob('*') if p.is_file()}
    if actual!=names:
        raise ValueError('Prefix content differs from its exact source-built inventory')
    results={}
    for path,name,entry in archives:
        members=validate_archive(path)
        results[path.name]={'sha256':entry['sha256'],'size':entry['size'],'member_count':len(members),'members':members}
    return headers+archives+metadata,results


def source_notices():
    result=[]
    root_files=('COPYING','LICENSE','LICENSE-EXCEPTION.md','THIRD-PARTY-NOTICES.md',
                'docs/LICENSING.md','docs/wine-lgpl-provenance.md')
    for name in root_files:
        result.append((checked_file(SOURCE/name,4*MIB,SOURCE),'Notices/Madeira/'+name))
    for path in sorted((SOURCE/'LICENSES').rglob('*')):
        if path.is_dir() and not path.is_symlink(): continue
        result.append((checked_file(path,4*MIB,SOURCE),'Notices/Madeira/'+path.relative_to(SOURCE).as_posix()))
    manifest=json.loads(checked_file(BUILD/'notices-manifest.json',4*MIB,SOURCE).read_text())
    for entry in manifest:
        name=safe_name(entry['path'])
        if not name.startswith(('notices/','source-archives/')):
            raise ValueError('Unapproved dependency notice/source path')
        path=checked_file(BUILD/name,16*MIB,SOURCE)
        if digest(path)!=entry['sha256']:
            raise ValueError('Changed source/notice content')
        result.append((path,'DependencySources/'+name))
    if len(result)>512 or sum(p.stat().st_size for p,n in result)>64*MIB or len({n for p,n in result})!=len(result):
        raise ValueError('Source/notice artifact cap or duplicate exceeded')
    return result


def package_prefix(report,files,notices):
    temporary=OUT/'crypto-prefix.zip.part'
    with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED) as archive:
        inventory=[]
        for path,name,entry in files:
            add_file(archive,path,name,256*MIB,SOURCE)
            inventory.append({'path':name,'sha256':digest(path),'size':path.stat().st_size})
        for path,name in notices:
            add_file(archive,path,name,16*MIB,SOURCE)
            inventory.append({'path':name,'sha256':digest(path),'size':path.stat().st_size})
        for name in ('prefix-manifest.json','source-lock.json','qualification.json','native-generators.json','preflight.json','commands.json','manifest.json'):
            path=checked_file(BUILD/name,4*MIB,SOURCE)
            add_file(archive,path,'BuildMetadata/'+name,4*MIB,SOURCE)
            inventory.append({'path':'BuildMetadata/'+name,'sha256':digest(path),'size':path.stat().st_size})
        for name in sorted(INPUT_FILES):
            path=checked_file(ROOT/name,4*MIB,ROOT)
            add_file(archive,path,'ControlSources/'+name,4*MIB,ROOT)
            inventory.append({'path':'ControlSources/'+name,'sha256':digest(path),'size':path.stat().st_size})
        archive.writestr('source-and-prefix-manifest.json',json.dumps(dict(report,
            result='passed-source-prefix-only',files=inventory,tls_feature_proof='not claimed by prefix-only product'),indent=2)+'\n')
        archive.writestr('SHA256SUMS',''.join(e['sha256']+'  '+e['path']+'\n' for e in inventory))
    temporary.replace(OUT/'crypto-prefix.zip')


def proof_candidates(include_image=False):
    result=[(BUILD/'target-proof'/n,'TargetProof/'+n) for n in PROOF_FILES]
    result += [(BUILD/'target-proof/logs'/(n+'.log'),'TargetProof/logs/'+n+'.log') for n in PROOF_LOGS]
    if include_image:
        result.append((BUILD/'target-proof/gnutls-api-link-probe','TargetProof/gnutls-api-link-probe'))
    return result


def validate_proof(proof,libraries):
    if (proof.get('result')!='passed-target-link-proof' or proof.get('api_count')!=106
        or proof.get('required_wine_count')!=69 or proof.get('optional_wine_count')!=37
        or proof.get('target_binaries_run') is not False or proof.get('signed') is not False
        or proof.get('feature_overlay_generated') is not False
        or proof.get('sdk_version')!='26.5' or proof.get('xcode_version')!='26.6'
        or proof.get('prefix')!=str(BUILD/'prefix') or set(proof.get('archives',{}))!=set(LIBRARIES)):
        raise ValueError('Incomplete or mismatched target proof')
    for name,entry in libraries.items():
        other=proof['archives'][name]
        if any(other.get(k)!=entry[k] for k in ('sha256','size','member_count')):
            raise ValueError('Proof used different target archive: '+name)
    expected={'commands.json':proof.get('commands_sha256'),'input-evidence.json':proof.get('input_evidence_sha256'),
              'gnutls-api-link-probe':proof.get('image',{}).get('sha256'),'api-link.map':proof.get('linkmap',{}).get('sha256')}
    if proof.get('image',{}).get('path')!='gnutls-api-link-probe' or proof.get('linkmap',{}).get('path')!='api-link.map':
        raise ValueError('Unexpected proof output path')
    for name,sha in expected.items():
        if not isinstance(sha,str) or not re.fullmatch(r'[0-9a-f]{64}',sha) or digest(checked_file(BUILD/'target-proof'/name,256*MIB,SOURCE))!=sha:
            raise ValueError('Changed target proof output: '+name)
    return proof


def package_proof(report,notices):
    temporary=OUT/'crypto-target-proof.zip.part'
    with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED) as archive:
        inventory=[]
        candidates=proof_candidates(True)+notices
        candidates += [(ROOT/name,'ControlSources/'+name) for name in sorted(INPUT_FILES|{'ci/run_crypto_control.py','ci/crypto-inputs-lock.json'})]
        total=0
        for path,name in candidates:
            if name=='TargetProof/failure.json':
                if path.exists() or path.is_symlink(): raise ValueError('Failure marker in passed target proof')
                continue
            if name=='TargetProof/logs/developer-directory.log' and not path.exists() and not path.is_symlink():
                # Provider DEVELOPER_DIR takes precedence; xcode-select fallback
                # is then deliberately not run. Selection remains in proof.json.
                continue
            checked_file(path,256*MIB,ROOT)
            total+=path.stat().st_size
            if total>384*MIB: raise ValueError('Proof product exceeds bound')
            add_file(archive,path,name,256*MIB,ROOT)
            inventory.append({'path':name,'sha256':digest(path),'size':path.stat().st_size})
        archive.writestr('artifact-manifest.json',json.dumps(dict(report,files=inventory),indent=2)+'\n')
        archive.writestr('SHA256SUMS',''.join(e['sha256']+'  '+e['path']+'\n' for e in inventory))
    temporary.replace(OUT/'crypto-target-proof.zip')


def evidence_candidates(control):
    result=[(OUT/(step['label']+'.log'),'Logs/'+step['label']+'.log') for step in control.steps]
    for name in ('source-lock.json','preflight.json','commands.json','prefix-manifest.json',
                 'native-generators.json','notices-manifest.json','qualification.json','manifest.json','failure.json','developer-selection.json'):
        result.append((BUILD/name,'BuildMetadata/'+name))
    for path in sorted((BUILD/'logs').glob('*.log')):
        result.append((path,'BuildLogs/'+path.name))
    for package in ('gmp','nettle','gnutls'):
        for name in ('config.log','config.status','config.h','Makefile'):
            result.append((BUILD/'build'/package/name,'Configuration/'+package+'/'+name))
    for name in ('config.make','config.m4'):
        result.append((BUILD/'build/nettle'/name,'Configuration/nettle/'+name))
    for name in ('gl/Makefile','lib/Makefile','lib/includes/Makefile','lib/gnutls.pc','lib/libgnutls.la'):
        result.append((BUILD/'build/gnutls'/name,'Configuration/gnutls/'+name))
    for name in ('gmp','nettle','gnutls'):
        result.append((BUILD/'manifests'/(name+'-source.json'),'SourceManifests/'+name+'.json'))
    for name in sorted(INPUT_FILES|{'ci/run_crypto_control.py','ci/crypto-inputs-lock.json'}):
        result.append((ROOT/name,'ControlSources/'+name))
    for name in LIBRARIES:
        result.append((BUILD/'prefix/lib'/name.replace('.a','.la'),'PrefixMetadata/'+name.replace('.a','.la')))
    for path in sorted((BUILD/'prefix/lib/pkgconfig').glob('*.pc')):
        result.append((path,'PrefixMetadata/'+path.name))
    result.extend(proof_candidates(False))
    return result


def write_evidence(report,control):
    (OUT/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    omissions=[];total=0;names=set()
    with zipfile.ZipFile(OUT/'crypto-evidence.zip','w',zipfile.ZIP_DEFLATED) as archive:
        add_file(archive,OUT/'result.json','result.json',16*MIB,OUT)
        for path,name in evidence_candidates(control):
            if not path.exists() and not path.is_symlink(): continue
            if name in names: raise ValueError('Duplicate evidence name')
            names.add(name)
            try:
                checked_file(path,128*MIB,ROOT)
                size=min(path.stat().st_size,16*MIB)
                if total+size>128*MIB: raise ValueError('Total evidence bound exceeded')
                with path.open('rb') as stream:
                    if path.stat().st_size>size:
                        stream.seek(path.stat().st_size-size);name+='.tail'
                    archive.writestr(safe_name(name),stream.read(size))
                total+=size
            except ValueError as error:
                omissions.append({'path':name,'reason':str(error)})
        archive.writestr('evidence-omissions.json',json.dumps(omissions,indent=2)+'\n')
    print('CRYPTO_CONTROL_RESULT='+json.dumps(report,sort_keys=True),flush=True)


def main():
    if sys.platform!='darwin': raise SystemExit('Approved macOS runner required')
    if os.environ.get('FREE_QUOTA_VERIFIED')!='true' or os.environ.get('PRIVATE_SOURCE_VERIFIED')!='true':
        raise SystemExit('Manual free/private checks must be exactly true')
    lock=reviewed_inputs()
    require_fresh((SOURCE,OUT))
    SOURCE.mkdir(parents=True);OUT.mkdir(parents=True)
    control=Control()
    report={'result':'failed','scope':'Real source-built iOS crypto prefix and inert target API/link proof; no runtime crypto/device claim',
            'madeira':MADEIRA,'inputs_lock_sha256':INPUT_LOCK,'wrapper_sha256':digest(Path(__file__)),
            'source_only':True,'target_binaries_executed':False,'package_installation':False,
            'provider_budget_minutes':25,'aggregate_budget_seconds':AGGREGATE_SECONDS,'jobs':4,'steps':control.steps}
    try:
        report['checkout']=checkout(control,'madeira',SOURCE,'https://github.com/willfaust/Madeira.git',MADEIRA,SPARSE)
        control.run('crypto-build','bash',str(ROOT/'ci/crypto-core-control.sh'),str(SOURCE),str(BUILD))
        verify_pin(control.run('final-source-pin','git','rev-parse','HEAD',cwd=SOURCE),MADEIRA)
        control.run('final-source-diff','git','diff','--exit-code','HEAD','--','.',cwd=SOURCE)
        control.ensure_budget()
        files,libraries=prefix_inventory();notices=source_notices()
        report['prefix']={'result':'passed','libraries':libraries,'headers':91}
        package_prefix(report,files,notices)
        control.ensure_budget()
        control.run('crypto-target-proof',sys.executable,'-I',str(ROOT/'ci/prove_crypto_features.py'),str(BUILD/'prefix'),str(BUILD/'target-proof'))
        proof=json.loads(checked_file(BUILD/'target-proof/proof.json',8*MIB,SOURCE).read_text())
        report['target_proof']=validate_proof(proof,libraries)
        control.ensure_budget()
        report['result']='passed-source-prefix-and-target-link-proof'
        package_proof(report,notices)
        control.ensure_budget()
    except Exception as error:
        report['result']='failed'
        report['failure']=str(error)
        (OUT/'crypto-target-proof.zip').unlink(missing_ok=True)
        print(str(error),file=sys.stderr,flush=True)
    finally:
        (OUT/'crypto-prefix.zip.part').unlink(missing_ok=True)
        (OUT/'crypto-target-proof.zip.part').unlink(missing_ok=True)
        write_evidence(report,control)
    return 0 if report['result']=='passed-source-prefix-and-target-link-proof' else 1


if __name__=='__main__':
    raise SystemExit(main())
