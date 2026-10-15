#!/usr/bin/env python3
"""Bounded source-only FFmpeg iOS prefix control; no target execution or signing."""
import hashlib,json,os,re,shlex,signal,struct,subprocess,sys,tarfile,time,zipfile
from pathlib import Path,PurePosixPath
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'.work/madeira-ffmpeg-control'
OUT=ROOT/'.work/ffmpeg-control-artifacts'
MIB=1024*1024
MADEIRA='279fd0f83170425db002fe25d6bd62f6355f497d'
RECIPE='6ba3ceb7c7bd956a36bd02aa06d697c33ff8ef67252b5d78385896b7ead4fe95'
LOCK_HASH='4f6e6cce93b69b66edfc35a1e9329db166ee1e6c02703871fc23ad242656f51a'
BSD_INDEX_MEMBERS=frozenset(('__.SYMDEF','__.SYMDEF SORTED','__.SYMDEF_64','__.SYMDEF_64 SORTED'))
LIBS=('libavformat','libavcodec','libswresample','libavutil')


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
    if not name or not path.parts or path.as_posix() != name or path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name or any(ord(c) < 32 for c in name):
        raise ValueError("Unsafe ZIP member name")
    return name

def add_file(archive, path, name, cap, root=None):
    archive.write(checked_file(path, cap, root), safe_name(name))

def validate_members(members, expected):
    lines = [line.strip() for line in members.splitlines() if line.strip()]
    if sum(name in BSD_INDEX_MEMBERS for name in lines) > 1:
        raise ValueError("Duplicate archive index metadata")
    names = [name for name in lines if name not in BSD_INDEX_MEMBERS]
    if len(names) != len(expected) or len(set(names)) != len(names) or set(names) != set(expected):
        raise ValueError("Archive members must match the exact pinned object set, once each")
    return names

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
        if command == 0x32:  # LC_BUILD_VERSION
            if length < 24:
                raise ValueError("Truncated build-version command")
            ntools = struct.unpack_from("<I", data, offset + 20)[0]
            if length != 24 + 8 * ntools:
                raise ValueError("Invalid build-version tool count")
            platforms.append(struct.unpack_from("<I", data, offset + 8)[0])
            minima.append(struct.unpack_from("<I", data, offset + 12)[0])
        elif command in (0x24, 0x25, 0x2F, 0x30):
            if length != 16:
                raise ValueError("Invalid legacy platform command size")
            platforms.append(2 if command == 0x25 else -1)
            minima.append(struct.unpack_from("<I", data, offset + 8)[0])
        offset += length
    if offset != 32 + size or platforms != [2] or minima != [0x00110000]:
        raise ValueError(f"Member must contain exactly one iOS 17.0 platform command: {name}")

def validate_archive(path, expected):
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
            if name not in expected or name in names:
                raise ValueError("Unknown or duplicate real archive member")
            validate_macho(data, name)
            names.append(name)
            inventory.append({"member": name, "sha256": hashlib.sha256(data).hexdigest(),
                              "size": len(data), "architecture": "arm64", "platform": "iOS"})
    validate_members("\n".join(names), expected)
    return inventory

class Control:
    def __init__(self):
        self.deadline = time.monotonic() + 1380
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
        timeout = min(self.deadline - time.monotonic(), seconds or 1380)
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

def safe_extract(archive, target, expected_hash):
    checked_file(archive,16*MIB)
    if digest(archive)!=expected_hash: raise ValueError('Source tarball digest mismatch')
    if target.exists() or target.is_symlink(): raise ValueError('Fresh extraction destination required')
    with tarfile.open(archive,'r:xz') as tar:
        members=tar.getmembers();seen=set();folded=set();total=0;byname={}
        if len(members)>10000: raise ValueError('Too many source entries')
        for item in members:
            name=item.name.rstrip('/')
            safe_name(name)
            if PurePosixPath(name).parts[0]!='ffmpeg-7.1.1': raise ValueError('Wrong source root')
            if not (item.isfile() or item.isdir()) or name in seen or name.lower() in folded:
                raise ValueError('Duplicate, linked or special source entry')
            seen.add(name);folded.add(name.lower());byname[name]=item;total+=item.size
            if item.size<0 or item.size>16*MIB or total>128*MIB:raise ValueError('Source expansion limit')
        # Path/file collisions fail before extraction. Preserve official source mtimes.
        for item in members:
            for parent in PurePosixPath(item.name).parents:
                if parent.as_posix() in seen and not byname[parent.as_posix()].isdir():
                    raise ValueError('Source file/directory collision')
        target.mkdir(parents=True)
        tar.extractall(target,members=members,filter='data')
    return {'entries':len(members),'unpacked_bytes':total,'sha256':expected_hash}

def validate_config(build, lock):
    h=(build/'config.h').read_text();c=(build/'config_components.h').read_text()
    def defines(text):
        pairs=re.findall(r'^#define\s+(\w+)\s+([01])\s*$',text,re.M)
        if len(dict(pairs))!=len(pairs):raise ValueError('Duplicate feature macro')
        return dict(pairs)
    config=defines(h);components=defines(c)
    for name in lock['config_one']:
        if config.get(name)!='1':raise ValueError('Required feature missing: '+name)
    for name in lock['config_zero']:
        if config.get(name)!='0':raise ValueError('Forbidden or unrecorded feature: '+name)
    for kind,expected in lock['components'].items():
        actual=sorted(k[len('CONFIG_'):-len('_'+kind)].lower() for k,v in components.items() if k.startswith('CONFIG_') and k.endswith('_'+kind) and v=='1')
        if actual!=sorted(expected):raise ValueError('Component set mismatch: '+kind)
    if '#define FFMPEG_LICENSE "LGPL version 2.1 or later"' not in h:raise ValueError('Unexpected FFmpeg license config')
    if not re.search(r'^ARCH=c\s*$',(build/'ffbuild/config.mak').read_text(),re.M):raise ValueError('Unexpected assembly architecture setting')
    if any(v=='1' for k,v in config.items() if k.startswith('ARCH_') or k in ('HAVE_NEON','HAVE_ARMV8')):
        raise ValueError('Unexpected architecture assembly feature')
    if any(config.get(k)=='1' for k in ('CONFIG_GPLV3','CONFIG_LGPLV3')):raise ValueError('Unexpected version3 code')
    return {'components':lock['components'],'license':'LGPL version 2.1 or later','internal_arch':'c','autodetect_disabled':True}

def global_definitions(text):
    defined=set()
    for line in text.splitlines():
        match=re.fullmatch(r'\s*(?:[0-9a-fA-F]+\s+)?([A-Za-z?])\s+(\S+)\s*',line)
        if match and match[1] not in ('U','u','?'):defined.add(match[2])
    return defined

def validate_headers(prefix, lock):
    root=prefix/'include';found=[]
    for current,dirs,files in os.walk(root,followlinks=False):
        if any((Path(current)/d).is_symlink() for d in dirs):raise ValueError('Header directory symlink')
        for name in files:
            p=checked_file(Path(current)/name,4*MIB,root)
            found.append({'path':p.relative_to(root).as_posix(),'sha256':digest(p),'size':p.stat().st_size})
    if sorted(x['path'] for x in found)!=lock['headers']:raise ValueError('Expected exactly 127 public headers')
    return sorted(found,key=lambda x:x['path'])

def validate_prefix(prefix, lock):
    expected={'include/'+n for n in lock['headers']}|{'lib/'+n+'.a' for n in LIBS}|{'lib/pkgconfig/'+n+'.pc' for n in LIBS}
    actual=set()
    for current,dirs,files in os.walk(prefix,followlinks=False):
        if any((Path(current)/d).is_symlink() for d in dirs):raise ValueError('Prefix directory symlink')
        for name in files:
            p=checked_file(Path(current)/name,256*MIB,prefix);actual.add(p.relative_to(prefix).as_posix())
    if actual!=expected:raise ValueError('Installed prefix contains missing or unexpected files: '+str(sorted(actual^expected)))
    packages=[]
    for lib in LIBS:
        p=prefix/'lib/pkgconfig'/(lib+'.pc');fields={}
        for line in p.read_text().splitlines():
            if not line.strip() or line.lstrip().startswith('#'):continue
            match=re.fullmatch(r'([A-Za-z_.]+)([:=])(.*)',line)
            if not match or match[1] in fields:raise ValueError('Malformed pkg-config metadata')
            fields[match[1]]=match[3].strip()
        def expand(value):
            for unused in range(3):
                value=value.replace('${prefix}',str(prefix)).replace('${exec_prefix}',str(prefix))
            return value
        if fields.get('prefix')!=str(prefix) or expand(fields.get('exec_prefix',''))!=str(prefix):raise ValueError('Unexpected pkg-config build prefix')
        if expand(fields.get('libdir',''))!=str(prefix/'lib') or expand(fields.get('includedir',''))!=str(prefix/'include'):raise ValueError('Unexpected pkg-config library/include location')
        if fields.get('Name')!=lib or fields.get('Version')!=lock['versions'][lib]:raise ValueError('Package version mismatch')
        normalize=lambda value: sorted(x.strip() for x in value.split(',') if x.strip())
        if normalize(fields.get('Requires',''))!=normalize(lock['pkgconfig_requires'][lib]):raise ValueError('Unexpected package dependency closure')
        if any(fields.get(k) for k in ('Requires.private','Libs.private','Conflicts')):raise ValueError('Unexpected private/shared pkg-config metadata')
        if fields.get('Cflags')!='-I${includedir}':raise ValueError('Unexpected pkg-config header flags')
        tokens=shlex.split(fields.get('Libs',''));i=0
        allowed={'-L${libdir}','-lavformat','-lavcodec','-lswresample','-lavutil','-lm','-pthread','-lpthread','-lSystem'}
        while i<len(tokens):
            if tokens[i]=='-framework':
                i+=1
                if i>=len(tokens) or tokens[i] not in ('CoreFoundation','CoreMedia','CoreVideo'):raise ValueError('Unexpected system framework')
            elif tokens[i] not in allowed:raise ValueError('Unexpected pkg-config library flag: '+tokens[i])
            i+=1
        if '-L${libdir}' not in tokens or '-l'+lib[3:] not in tokens:raise ValueError('Required own package library missing')
        packages.append({'path':'lib/pkgconfig/'+lib+'.pc','sha256':digest(p),'version':fields['Version'],'original_prefix':str(prefix),'relocation':'Consumer must use verified explicit include/library paths or regenerate metadata; original prefix is evidence, not relocatable.'})
    return packages

def notices(source):
    # Include whole exact source files when attribution occurs beyond first comment.
    paths=['COPYING.LGPLv2.1','LICENSE.md','libavcodec/jfdctfst.c','libavcodec/jfdctint_template.c',
           'libavcodec/jrevdct.c','libavcodec/faandct.c','libavutil/avsscanf.c',
           'libavutil/fixed_dsp.c','libavutil/fixed_dsp.h','libavutil/uuid.c',
           'libavutil/mathematics.c','libavutil/libm.h']
    result=[]
    for name in paths:
        p=checked_file(source/name,2*MIB,source)
        result.append((p,'Licenses/FFmpeg/'+name))
    for name in ('COPYING','LICENSE','LICENSE-EXCEPTION.md','THIRD-PARTY-NOTICES.md'):
        p=checked_file(SOURCE/name,2*MIB,SOURCE);result.append((p,'Licenses/Madeira/'+name))
    return result

def evidence(report,control):
    (OUT/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    e=SOURCE/'build/ffmpeg/control-evidence';b=SOURCE/'build/ffmpeg/control-build'
    candidates=[(OUT/'result.json','result.json')]+[(OUT/(s['label']+'.log'),'Logs/'+s['label']+'.log') for s in control.steps]
    for name in ('toolchain.txt','configure-arguments.txt'):
        candidates.append((e/name,'Evidence/'+name))
    for lib in LIBS:
        for ext in ('members.txt','load-commands.txt','symbols.txt','arch.txt'):
            candidates.append((e/(lib+'.'+ext),'Evidence/'+lib+'.'+ext))
    for name in ('config.h','config_components.h','ffbuild/config.log','ffbuild/config.mak','ffbuild/config.sh'):
        candidates.append((b/name,'Configuration/'+name))
    for name in ('ffmpeg-core-control.sh','run_ffmpeg_control.py','ffmpeg-lock.json'):
        candidates.append((ROOT/'ci'/name,'Source/'+name))
    omissions=[];total=0
    with zipfile.ZipFile(OUT/'ffmpeg-evidence.zip','w',zipfile.ZIP_DEFLATED) as z:
        for p,name in candidates:
            if not p.exists() and not p.is_symlink():continue
            try:
                checked_file(p,64*MIB,ROOT);size=min(p.stat().st_size,8*MIB)
                if total+size>96*MIB:raise ValueError('Total evidence limit')
                with p.open('rb') as f:
                    if p.stat().st_size>size:f.seek(-size,2);name+='.tail'
                    z.writestr(safe_name(name),f.read(size))
                total+=size
            except ValueError as ex:omissions.append({'path':name,'reason':str(ex)})
        z.writestr('evidence-omissions.json',json.dumps(omissions))
    print('FFMPEG_CONTROL_RESULT='+json.dumps(report,sort_keys=True),flush=True)

def main():
    if sys.platform!='darwin':raise SystemExit('Approved macOS runner required')
    if any(os.environ.get(k)!='true' for k in ('FREE_QUOTA_VERIFIED','PRIVATE_SOURCE_VERIFIED')):
        raise SystemExit('Fresh free/private verification required')
    for name,pin,var in [('ffmpeg-core-control.sh',RECIPE,'EXPECTED_RECIPE_SHA256'),('ffmpeg-lock.json',LOCK_HASH,'EXPECTED_LOCK_SHA256')]:
        p=checked_file(ROOT/'ci'/name,MIB,ROOT)
        if not re.fullmatch('[a-f0-9]{64}',pin) or digest(p)!=pin or os.environ.get(var)!=pin:raise SystemExit('Unreviewed recipe or lock')
    for path in (SOURCE,OUT):
        if path.exists() or path.is_symlink():raise SystemExit('Fresh control directories required')
        if path.parent.is_symlink():raise SystemExit('Symlink work root')
        path.mkdir(parents=True)
    control=Control();lock=json.loads((ROOT/'ci/ffmpeg-lock.json').read_text())
    report={'result':'failed','madeira':MADEIRA,'source_tarball_sha256':lock['tarball_sha256'],
            'recipe_sha256':RECIPE,'lock_sha256':LOCK_HASH,'wrapper_sha256':digest(Path(__file__)),
            'jobs':4,'budget_seconds':1380,'source_only':True,'runtime_linked':False,'ipa_created':False,
            'device_tested':False,'target_executed':False,'host_packages_installed':False,'steps':control.steps}
    try:
        control.run('git-init','git','init','--quiet',cwd=SOURCE)
        control.run('git-remote','git','remote','add','origin','https://github.com/willfaust/Madeira.git',cwd=SOURCE)
        control.run('git-fetch','git','fetch','--depth=1','--filter=blob:none','origin',MADEIRA,cwd=SOURCE,seconds=180)
        control.run('sparse-init','git','sparse-checkout','init','--no-cone',cwd=SOURCE)
        control.run('sparse-paths','git','sparse-checkout','set','--no-cone','--','/build/ffmpeg/','/COPYING','/LICENSE','/LICENSE-EXCEPTION.md','/THIRD-PARTY-NOTICES.md',cwd=SOURCE)
        control.run('git-checkout','git','checkout','--detach','FETCH_HEAD',cwd=SOURCE,seconds=180)
        if control.run('pin','git','rev-parse','HEAD',cwd=SOURCE).strip()!=MADEIRA:raise ValueError('Wrong source pin')
        tarball=SOURCE/'build/ffmpeg/src/ffmpeg-7.1.1.tar.xz'
        report['extraction']=safe_extract(tarball,SOURCE/'build/ffmpeg/control-source',lock['tarball_sha256'])
        control.run('ffmpeg-build','bash',str(ROOT/'ci/ffmpeg-core-control.sh'),str(SOURCE))
        b=SOURCE/'build/ffmpeg/control-build';prefix=SOURCE/'build/ffmpeg/control-prefix';e=SOURCE/'build/ffmpeg/control-evidence'
        report['configuration']=validate_config(b,lock);report['headers']=validate_headers(prefix,lock);report['pkgconfig']=validate_prefix(prefix,lock)
        report['archives']=[]
        for lib in LIBS:
            p=prefix/'lib'/(lib+'.a')
            names=[n.strip() for n in (e/(lib+'.members.txt')).read_text().splitlines() if n.strip() not in BSD_INDEX_MEMBERS]
            if not names or len(names)!=len(set(names)):raise ValueError('Invalid archive inventory')
            inventory=validate_archive(p,set(names))
            # Each actual archive member must match a real freshly compiled object.
            disk={}
            for obj in (b/lib).rglob('*.o'):
                if obj.name in disk:raise ValueError('Ambiguous compiled member basename')
                disk[obj.name]=obj
            for item in inventory:
                obj=disk.get(item['member'])
                if obj is None or digest(obj)!=item['sha256']:raise ValueError('Archive member does not match fresh compiler output')
            defined=global_definitions((e/(lib+'.symbols.txt')).read_text())
            wanted={'_'+n for n in lock['symbols'][lib]}
            if not wanted<=defined:raise ValueError('Missing real consumer APIs: '+str(sorted(wanted-defined)))
            report['archives'].append({'name':p.name,'sha256':digest(p),'size':p.stat().st_size,'members':inventory,'verified_consumer_apis':sorted(wanted)})
        licenses=notices(SOURCE/'build/ffmpeg/control-source/ffmpeg-7.1.1')
        control.ensure_budget()
        report['result']='passed-source-control-only'
        with zipfile.ZipFile(OUT/'ffmpeg-ios-prefix.zip.part','w',zipfile.ZIP_DEFLATED) as z:
            for a in report['archives']:add_file(z,prefix/'lib'/a['name'],'lib/'+a['name'],256*MIB,SOURCE)
            for h in report['headers']:add_file(z,prefix/'include'/h['path'],'include/'+h['path'],4*MIB,SOURCE)
            for p,name in licenses:add_file(z,p,name,2*MIB,SOURCE)
            add_file(z,tarball,'Sources/ffmpeg-7.1.1.tar.xz',16*MIB,SOURCE)
            for lib in LIBS:add_file(z,prefix/'lib/pkgconfig'/(lib+'.pc'),'lib/pkgconfig/'+lib+'.pc',MIB,SOURCE)
            for name in ('config.h','config_components.h','ffbuild/config.mak'):
                add_file(z,b/name,'Configuration/'+name,4*MIB,SOURCE)
            add_file(z,e/'configure-arguments.txt','Configuration/configure-arguments.txt',MIB,SOURCE)
            z.writestr('NOTICE.txt','This software is based in part on the work of the Independent JPEG Group.\nUnmodified FFmpeg 7.1.1 source is included. Archive/source control only; no target execution or app linkage.\n')
            z.writestr('manifest.json',json.dumps(report,indent=2))
        control.ensure_budget();(OUT/'ffmpeg-ios-prefix.zip.part').replace(OUT/'ffmpeg-ios-prefix.zip')
    except Exception as error:
        report['result']='failed';report['failure']=str(error)
        (OUT/'ffmpeg-ios-prefix.zip').unlink(missing_ok=True)
        print(str(error),file=sys.stderr,flush=True)
    finally:
        (OUT/'ffmpeg-ios-prefix.zip.part').unlink(missing_ok=True)
        evidence(report,control)
    return 0 if report['result']=='passed-source-control-only' else 1

if __name__=='__main__':raise SystemExit(main())
