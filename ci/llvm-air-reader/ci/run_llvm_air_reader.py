#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded proposed native LLVM15 AIR-reader producer. No Metal or target run."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import signal
import stat
import sys
import time
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RECIPE = HERE / 'reader-recipe-lock.json'
STATE = ROOT / '.work/reader-producer'
OUT = STATE / 'artifacts'
SOURCE = STATE / 'source'
BUILD = SOURCE / '.work/reader-build'
NATIVE = SOURCE / '.work/native-generator'
MIB = 1024**2
MAX_FILE = 64*MIB
MAX_ZIP = 256*MIB
MAX_FILES = 10000
TOTAL_SECONDS = 1380
SOURCE_SECONDS = 480
DIAGNOSTIC_SECONDS = 10
MADEIRA = '279fd0f83170425db002fe25d6bd62f6355f497d'
LLVM = '8dfdcc7b7bf66834a761bd8de445840ef68e4d1a'
LLVM_SPARSE = ('/llvm/*','!/llvm/*/','/llvm/cmake/','/llvm/include/',
               '/llvm/lib/','/llvm/utils/TableGen/','/llvm/projects/CMakeLists.txt','/cmake/')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(path):
    value=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(MIB),b''):
            value.update(block)
    return value.hexdigest()


def write(path,value):
    path=Path(path)
    temporary=path.with_name(path.name+'.part')
    try:
        temporary.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def safe_name(name):
    value=PurePosixPath(name)
    require(name and value.as_posix()==name and not value.is_absolute() and '..' not in value.parts
            and not any(ord(x)<32 or x in '\\:' for x in name),'Unsafe portable path')
    return name


def regular(path, root=None, cap=MAX_FILE):
    path=Path(path).absolute()
    require(path.is_file() and path.stat().st_size<=cap,'Missing/oversized regular file')
    require(not any(p.is_symlink() for p in (path,*path.parents)),'Symlink file/ancestor')
    if root is not None:
        require(path.is_relative_to(Path(root).absolute()),'File outside allowed root')
    return path


def fresh(path):
    path=Path(path).absolute()
    require(not path.exists() and not any(p.is_symlink() for p in (path,*path.parents)),
            'Fresh non-symlink destination required')


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def recipe_guards(expected):
    require(re.fullmatch('[0-9a-f]{64}',expected or '') and digest(regular(RECIPE,ROOT))==expected,
            'Explicit reviewed reader recipe-lock SHA required')
    lock=json.loads(RECIPE.read_text())
    require(lock.get('schema')==1 and lock.get('kind')=='llvm15-air-reader-producer-recipe',
            'Wrong recipe identity')
    for name,pin in lock['files'].items():
        require(re.fullmatch('[0-9a-f]{64}',pin),'Invalid recipe pin')
        require(digest(regular(ROOT/safe_name(name),ROOT))==pin,'Changed recipe input: '+name)
    needed={'ci/run_llvm_air_reader.py','ci/llvm_air_probe.py','ci/air_reader.cpp',
            'ci/probe-source-lock.json','ci/frozen/llvm_control_support.py',
            'ci/frozen/llvm-source-lock.json','ci/frozen/run_llvm_control.py','research/PROJECT-LICENSE'}
    require(set(lock['files'])==needed,'Recipe must cover exact executable/source dependency closure')
    return lock


class Runner:
    def __init__(self,probe):
        self.probe=probe
        self.deadline=time.monotonic()+TOTAL_SECONDS
        self.source_deadline=min(self.deadline-60,time.monotonic()+SOURCE_SECONDS)
        self.steps=[]
        self.env=probe.core.base_environment(STATE,os.environ.get('DEVELOPER_DIR') or None)
        (STATE/'home').mkdir();(STATE/'tmp').mkdir()

    def run(self,label,args,cwd=ROOT,seconds=90,source=False):
        require(re.fullmatch('[a-z0-9-]+',label) and label not in [x['label'] for x in self.steps],
                'Unsafe/duplicate wrapper step')
        end=self.source_deadline if source else self.deadline
        budget=min(seconds,end-time.monotonic())
        require(budget>0,'Producer aggregate budget exhausted')
        record={'label':label,'argv':list(map(str,args)),'cwd':str(cwd),'status':'attempted',
                'exit_code':None,'timeout_seconds':budget}
        self.steps.append(record);write(OUT/'steps.json',self.steps)
        log=OUT/(label+'.log')
        try:
            code=self.probe.bounded_run(args,cwd,self.env,log,budget)
            record.update(status='finished',exit_code=code)
        except BaseException as exc:
            record.update(status='exception',error=str(exc));raise
        finally:
            write(OUT/'steps.json',self.steps)
        require(code==0,f'{label} failed with exit {code}')
        return log.read_text(errors='replace').strip() if log.stat().st_size<=MIB else ''

    def acquire(self):
        SOURCE.mkdir()
        repositories=[('madeira',SOURCE,'https://github.com/willfaust/Madeira.git',MADEIRA,
                       ('/.gitmodules','/COPYING','/LICENSE-EXCEPTION.md','/LICENSES/')),
                      ('llvm',SOURCE/'toolchains/llvm-project','https://github.com/llvm/llvm-project.git',LLVM,LLVM_SPARSE)]
        for label,root,url,pin,sparse in repositories:
            root.mkdir(parents=True,exist_ok=True)
            def git(suffix,*args,seconds=90):
                return self.run(label+'-'+suffix,['/usr/bin/git',*args],root,seconds,source=True)
            git('init','init','--quiet')
            git('origin','remote','add','origin',url)
            git('fetch','fetch','--depth=1','--filter=blob:none','origin',pin,seconds=240)
            git('sparse','sparse-checkout','set','--no-cone','--',*sparse)
            git('checkout','checkout','--detach','FETCH_HEAD',seconds=240)
            require(git('pin','rev-parse','HEAD')==pin,'Acquired source pin mismatch')
            require(Path(git('top','rev-parse','--show-toplevel'))==root,'Source is not independent checkout')
            files,total=0,0
            for current,dirs,names in os.walk(root,followlinks=False):
                require(not any((Path(current)/n).is_symlink() for n in dirs),'Symlink source directory')
                for name in names:
                    path=Path(current)/name
                    if path.is_symlink():
                        continue  # Frozen selected-source validator rejects any selected symlink.
                    require(time.monotonic()<self.source_deadline,'Source acquisition aggregate budget exhausted')
                    total+=path.stat().st_size;files+=1
                    require(total<=4*1024*MIB and files<=150000,'Source checkout exceeds4GiB/150000 files')
            write(OUT/(label+'-source-bounds.json'),{'files':files,'bytes':total,'pin':pin,'url':url})


def allowed_payload_name(name):
    safe_name(name)
    if name in ('manifest.json','manifests/outputs.json','reader/bin/llvm15-air-reader'):
        return True
    if name.startswith('manifests/'):
        return bool(re.fullmatch(r'manifests/[a-z0-9-]+\.json',name))
    if name.startswith('logs/'):
        return bool(re.fullmatch(r'logs/[A-Za-z0-9_.-]+\.log(?:\.command\.json)?',name))
    if name.startswith('reader-source/'):
        return name.split('/',1)[1] in ('air_reader.cpp','air_reader.d','llvm_air_probe.py',
                'probe-source-lock.json','llvm_control_support.py','llvm-source-lock.json')
    if name.startswith('notices/'):
        return True  # Must also equal the complete separately checked notices inventory.
    if name.startswith('evidence/'):
        return (name in {'evidence/CMakeCache.txt','evidence/compile_commands.json',
                'evidence/CMakeFiles/CMakeConfigureLog.yaml','evidence/include/llvm/Config/config.h',
                'evidence/include/llvm/Config/llvm-config.h','evidence/include/llvm/Config/abi-breaking.h'} or
            bool(re.fullmatch(r'evidence/CMakeFiles/4\.3\.4/CMake(?:C|CXX|ASM)Compiler\.cmake',name)) or
            name=='evidence/CMakeFiles/4.3.4/CMakeSystem.cmake' or
            bool(re.fullmatch(r'evidence/(?:[A-Za-z0-9_.+-]+/)*CMakeFiles/(?:llvm-tblgen|LLVM[A-Za-z0-9_]+)\.dir/(?:link\.txt|flags\.make|build\.make)',name)))
    return False


def payload_files(root,probe):
    root=Path(root)
    manifest_sha=digest(regular(root/'manifest.json',root))
    probe.validate_export(root,manifest_sha)
    rows=json.loads((root/'manifests/outputs.json').read_text())
    names=['manifest.json','manifests/outputs.json']+[r['path'] for r in rows]
    require(len(names)<=MAX_FILES and len({n.casefold() for n in names})==len(names),'Duplicate/excessive reader outputs')
    require(all(allowed_payload_name(n) for n in names),'Unreviewed reader output path')
    notices=json.loads((root/'manifests/notices.json').read_text())
    require({r['path'] for r in notices}=={n for n in names if n.startswith('notices/')},'Incomplete notices inventory')
    for row in notices:
        require(probe.core.file_record(root/row['path'],root)==row,'Notice bytes changed')
    total=sum(regular(root/n,root).stat().st_size for n in names)
    require(total<=MAX_ZIP,'Uncompressed reader export exceeds256MiB')
    return names,manifest_sha


def verify_reader_zip(path,zip_sha,manifest_sha,destination,probe):
    require(all(re.fullmatch('[0-9a-f]{64}',v or '') for v in (zip_sha,manifest_sha)),
            'Independent reader ZIP/manifest SHA256 required')
    path=regular(path,cap=MAX_ZIP)
    require(digest(path)==zip_sha,'Reader ZIP hash mismatch')
    destination=Path(destination).absolute();fresh(destination)
    staging=destination.with_name(destination.name+'.importing');fresh(staging)
    require(staging.parent.is_dir(),'Existing import parent required')
    extracting=False
    try:
        with zipfile.ZipFile(path) as archive:
            infos=archive.infolist()
            require(len(infos)<=MAX_FILES and len({i.filename.casefold() for i in infos})==len(infos),
                    'Duplicate/excessive reader ZIP entries')
            require(sum(i.file_size for i in infos)<=MAX_ZIP,'Oversized reader ZIP payload')
            for info in infos:
                require(allowed_payload_name(info.filename),'Reader ZIP member outside allowlist')
                mode=info.external_attr>>16
                wanted=0o755 if info.filename=='reader/bin/llvm15-air-reader' else 0o644
                require(not info.is_dir() and stat.S_IFMT(mode)==stat.S_IFREG and stat.S_IMODE(mode)==wanted
                        and not info.flag_bits&1 and info.file_size<=MAX_FILE,'Unsafe reader ZIP member')
            raw=archive.read('manifest.json')
            require(hashlib.sha256(raw).hexdigest()==manifest_sha,'Reader manifest pin mismatch')
            inventory=json.loads(archive.read('manifests/outputs.json'))
            require({r['path'] for r in inventory}|{'manifest.json','manifests/outputs.json'}=={i.filename for i in infos},
                    'Reader ZIP exact inventory differs')
            extracting=True
            staging.mkdir()
            for info in infos:
                target=staging/info.filename;target.parent.mkdir(parents=True,exist_ok=True)
                data=archive.read(info);require(len(data)==info.file_size,'Reader ZIP byte count changed')
                target.write_bytes(data);target.chmod(0o755 if info.filename=='reader/bin/llvm15-air-reader' else 0o644)
        payload_files(staging,probe)
        result=json.loads((staging/'manifest.json').read_text())
        staging.replace(destination)
        return result
    except BaseException:
        if extracting:
            # Both paths were fresh at entry and are owned by this import. Also
            # cover interruption immediately after the final atomic rename.
            for partial in (staging,destination):
                if partial.exists():shutil.rmtree(partial)
        raise


def package_reader(probe):
    names,manifest_sha=payload_files(BUILD,probe)
    temporary=OUT/'llvm15-air-reader-native.zip.part';fresh(temporary)
    with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED) as archive:
        for name in names:
            path=regular(BUILD/name,BUILD)
            info=zipfile.ZipInfo(safe_name(name));info.create_system=3;info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=(stat.S_IFREG|(0o755 if name=='reader/bin/llvm15-air-reader' else 0o644))<<16
            archive.writestr(info,path.read_bytes())
    pin=digest(temporary)
    verify_reader_zip(temporary,pin,manifest_sha,STATE/'reader-export-replay',probe)
    final=OUT/'llvm15-air-reader-native.zip';fresh(final);temporary.replace(final)
    return {'path':final.name,'sha256':pin,'bytes':final.stat().st_size,
            'manifest_path':'manifest.json','manifest_sha256':manifest_sha,'payload_files':len(names),
            'kind':'llvm15-air-reader-native','air_parsed':False}


def check_deadline(deadline):
    if time.monotonic()>=deadline:
        raise TimeoutError('Producer finalization budget exhausted')


def evidence(report,deadline):
    check_deadline(deadline)
    write(OUT/'result.json',report)
    entries={}
    for base,prefix in ((OUT,'Wrapper/'),(BUILD/'logs','Build/logs/'),(BUILD/'manifests','Build/manifests/')):
        if not base.is_dir():continue
        for path in sorted(base.glob('*')):
            check_deadline(deadline)
            if path.is_file() and path.suffix in ('.json','.log'):
                entries[prefix+path.name]=path
                require(len(entries)<=MAX_FILES,'Excessive evidence file count')
    if (BUILD/'failure.json').exists():entries['Build/failure.json']=BUILD/'failure.json'
    for name in json.loads(RECIPE.read_text())['files']:
        entries['Recipe/'+name]=ROOT/name
    entries['Recipe/reader-recipe-lock.json']=RECIPE
    total,omissions=0,[]
    temporary=OUT/'llvm15-air-reader-evidence.zip.part'
    fresh(temporary)
    with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED) as archive:
        for name,path in entries.items():
            check_deadline(deadline)
            try:
                regular(path,ROOT)
                size=min(path.stat().st_size,16*MIB)
                require(total+size<=128*MIB,'Evidence128MiB cap')
                with path.open('rb') as stream:
                    if path.stat().st_size>size:stream.seek(path.stat().st_size-size);name+='.tail'
                    data=stream.read(size)
            except (TimeoutError,InterruptedError):
                # These inherit OSError, but a deadline/cancellation is a
                # transaction failure, never an optional evidence omission.
                raise
            except (ValueError,OSError) as exc:
                omissions.append({'path':name,'reason':str(exc)})
                continue
            # Output-write/compression failures cannot be downgraded to a
            # missing optional input. The complete transaction must fail.
            archive.writestr(name,data)
            total+=size
        archive.writestr('evidence-omissions.json',json.dumps(omissions,indent=2))
    check_deadline(deadline)
    temporary.replace(OUT/'llvm15-air-reader-evidence.zip')


def revoke_artifacts(report,exc):
    """Small, interruption-shielded failure transition; never keep a reusable ZIP."""
    report.update(status='failed',error=(str(exc) or type(exc).__name__)[:4096])
    report.pop('artifact',None)
    errors=[]
    for name in ('llvm15-air-reader-native.zip','llvm15-air-reader-native.zip.part',
                 'llvm15-air-reader-evidence.zip','llvm15-air-reader-evidence.zip.part'):
        try:(OUT/name).unlink(missing_ok=True)
        except OSError as error:errors.append(name+': '+str(error))
    if errors:report['cleanup_errors']=errors
    try:write(OUT/'result.json',report)
    except OSError as error:report['result_write_error']=str(error)
    if BUILD.exists():
        try:write(BUILD/'failure.json',{'status':'failed','error':report['error'],'air_parsed':False})
        except OSError as error:report['failure_write_error']=str(error)


def run_transaction(runner,report,produce):
    """The reusable package, evidence and result succeed or fail as one unit."""
    phase='active'
    def interrupted(signum,frame):
        # Repeated signals must not interrupt the short unlink/status reset.
        # Diagnostics remain interruptible and never renew the total budget.
        if phase=='cleanup':return
        if signum==signal.SIGALRM:
            raise TimeoutError('Producer aggregate23-minute budget exhausted')
        if signum==signal.SIGINT:raise KeyboardInterrupt()
        error=InterruptedError('Producer interrupted by SIGTERM')
        error.status=128+signum
        raise error
    old={signum:signal.signal(signum,interrupted)
         for signum in (signal.SIGALRM,signal.SIGTERM,signal.SIGINT)}
    signal.setitimer(signal.ITIMER_REAL,max(.001,runner.deadline-time.monotonic()))
    try:
        report['artifact']=produce()
        report['status']='reader_built_not_air_tested'
        evidence(report,runner.deadline)
        check_deadline(runner.deadline)
        print('LLVM15_AIR_READER_RESULT='+json.dumps(report,sort_keys=True),flush=True)
    except BaseException as exc:
        phase='cleanup'
        revoke_artifacts(report,exc)
        # Diagnostic evidence gets at most ten seconds of the *remaining*
        # aggregate budget. No retry of a build, package, or successful result.
        remaining=runner.deadline-time.monotonic()
        if remaining>0:
            diagnostic_deadline=min(runner.deadline,time.monotonic()+DIAGNOSTIC_SECONDS)
            phase='diagnostics'
            signal.setitimer(signal.ITIMER_REAL,max(.001,diagnostic_deadline-time.monotonic()))
            try:evidence(report,diagnostic_deadline)
            except BaseException as diagnostic_error:
                phase='cleanup'
                report['diagnostic_error']=(str(diagnostic_error) or type(diagnostic_error).__name__)[:4096]
                revoke_artifacts(report,exc)
        phase='cleanup'
        raise
    finally:
        # Finalization and diagnostic evidence have already finished or failed.
        signal.setitimer(signal.ITIMER_REAL,0)
        for signum,handler in old.items():signal.signal(signum,handler)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-chunks',required=True);parser.add_argument('--reassembler',required=True)
    args=parser.parse_args()
    require(sys.platform=='darwin' and platform.machine()=='arm64','Approved native arm64 macOS host required')
    require(os.environ.get('FREE_QUOTA_VERIFIED')=='true' and os.environ.get('PRIVATE_SOURCE_VERIFIED')=='true',
            'Explicit current free/private manual guards required')
    recipes=recipe_guards(os.environ.get('EXPECTED_READER_RECIPE_SHA256'))
    probe=module('air_reader_helper',HERE/'llvm_air_probe.py')
    original=module('verified_native_importer',HERE/'frozen/run_llvm_control.py')
    transport_pin=probe.LOCK['native_generator_input']['schema2_transport']
    require(digest(regular(args.reassembler))==transport_pin['reassembler_sha256'],'Shared reassembler hash differs')
    transport=module('shared_schema2_transport',Path(args.reassembler))
    fresh(STATE);STATE.mkdir(parents=True);OUT.mkdir()
    runner=Runner(probe)
    report={'schema':1,'status':'failed','artifact_kind':'llvm15-air-reader-native',
            'llvm_commit':LLVM,'madeira_commit':MADEIRA,'recipe_lock_sha256':digest(RECIPE),
            'aggregate_budget_seconds':TOTAL_SECONDS,'source_budget_seconds':SOURCE_SECONDS,
            'air_parsed':False,'target_run':False,'gpu_run':False,'package_install':False,
            'converter_opened_or_run':False,'explicit_signing':False,'steps':runner.steps}
    def produce():
        runner.acquire()
        (SOURCE/'.work').mkdir()
        archive=STATE/'native-generator.zip'
        obj=transport.reassemble(Path(args.native_chunks),transport_pin['manifest_sha256'],archive)
        require(obj['provenance']==transport_pin['provenance'] and obj['original']==transport_pin['original'],
                'Shared native transport provenance differs')
        pin=probe.LOCK['native_generator_input']
        original.verify_import(archive,pin['archive_sha256'],
                               transport_pin['provenance']['producer_manifest_sha256'],NATIVE)
        report['native_generator_input']=pin
        build=probe.Build(SOURCE,BUILD,NATIVE)
        build.deadline=min(build.deadline,runner.deadline-60)
        build.reader_build()
        require(time.monotonic()<runner.deadline-60,'No remaining verified packaging budget')
        return package_reader(probe)
    run_transaction(runner,report,produce)


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print(str(exc),file=sys.stderr)
        sys.exit(getattr(exc,'status',1))
