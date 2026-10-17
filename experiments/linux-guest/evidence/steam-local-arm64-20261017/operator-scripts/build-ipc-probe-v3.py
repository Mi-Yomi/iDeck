import os,sys,json,shlex,subprocess,hashlib,re
from pathlib import Path
base=Path(__file__).resolve().parent;top=base.parent;sys.path.insert(0,str(top/'source/experiments/linux-guest/tools'))
import gui_host_tools
cross=base/'private-cross-v5';root=cross/'root';receipt=json.loads((cross/'extraction.json').read_text());assert receipt['package_count']==33
out=base/'ipc-probe-build-v3';out.mkdir(exist_ok=False);wrappers=out/'wrappers';wrappers.mkdir()
lib=root/'usr/lib/x86_64-linux-gnu';loader=lib/'ld-linux-x86-64.so.2'
paths={'gcc':root/'usr/bin/aarch64-linux-gnu-gcc-14','cc1':root/'usr/libexec/gcc-cross/aarch64-linux-gnu/14/cc1','collect2':root/'usr/libexec/gcc-cross/aarch64-linux-gnu/14/collect2','as':root/'usr/bin/aarch64-linux-gnu-as','ld':root/'usr/bin/aarch64-linux-gnu-ld'}
for name in ('cc1','collect2'):
    if not paths[name].is_file():paths[name]=root/'usr/lib/gcc-cross/aarch64-linux-gnu/14'/name
records={}
for name,p in paths.items():
    assert p.is_file(),str(p)
    linked=subprocess.run([str(loader),'--library-path',str(lib),'--list',str(p)],capture_output=True,text=True)
    assert linked.returncode==0 and 'not found' not in linked.stdout,(name,linked.stderr,linked.stdout)
    for line in linked.stdout.splitlines():
        value=line.split('=>',1)[-1].strip().split(' (0x',1)[0]
        if value.startswith('/'):assert Path(value).resolve().is_relative_to(root.resolve()),(name,value)
    records[name]={'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'link_list':linked.stdout}
    if name!='gcc':
        argv=gui_host_tools.command(root,[p]);script='#!/bin/sh\nset -eu\nexec '+' '.join(shlex.quote(x) for x in argv)+' "$@"\n'
        for alias in (name,'aarch64-linux-gnu-'+name):
            f=wrappers/alias;f.write_text(script);f.chmod(0o755)
(out/'compiler-runtime.json').write_text(json.dumps({'extracted_lock_sha256':hashlib.sha256((cross/'lock.json').read_bytes()).hexdigest(),'all_used_tools_link_with_private_loader_and_libraries':True,'tools':records},indent=2)+'\n')
source=base/'ipc-connect-wait-v3.c';library=out/'libideck-ipc-connect.so'
flags=['-std=gnu11','-O2','-fPIC','-fvisibility=hidden','-fno-omit-frame-pointer','-fno-optimize-sibling-calls','-fstack-protector-strong','-D_FORTIFY_SOURCE=3','-Wall','-Wextra','-Werror','-fno-use-linker-plugin']
args=gui_host_tools.command(root,[paths['gcc']])+['-B'+str(wrappers)+'/', '--sysroot='+str(root),'-isystem',str(root/'usr/aarch64-linux-gnu/include'),*flags,'-shared','-nostdlib','-Wl,-z,relro,-z,now,-z,noexecstack,--no-undefined','-Wl,-soname,libideck-ipc-connect.so','-L'+str(root/'usr/aarch64-linux-gnu/lib'),'-L'+str(root/'usr/lib/gcc-cross/aarch64-linux-gnu/14'),str(source),'-lc','-o',str(library)]
env={**os.environ,'GCC_EXEC_PREFIX':str(root/'usr/lib/gcc-cross')+'/','COMPILER_PATH':str(wrappers)}
r=subprocess.run(args,capture_output=True,text=True,env=env);(out/'compile.json').write_text(json.dumps({'arguments':args,'exit':r.returncode,'stdout':r.stdout,'stderr':r.stderr,'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest()},indent=2)+'\n');print(r.stdout+r.stderr,flush=True);assert r.returncode==0
readelf=subprocess.run(['/usr/bin/readelf','-h','-l','-d','-W',str(library)],capture_output=True,text=True,check=True);(out/'readelf.txt').write_text(readelf.stdout)
assert 'AArch64' in readelf.stdout and 'GNU_RELRO' in readelf.stdout and 'BIND_NOW' in readelf.stdout
header=library.read_bytes()[:64];assert header[:6]==b'\x7fELF\x02\x01' and int.from_bytes(header[18:20],'little')==183
result={'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'library_sha256':hashlib.sha256(library.read_bytes()).hexdigest(),'library_bytes':library.stat().st_size,'target':'AArch64 Linux glibc','system_install':False,'compiled_with_test_override':False}
(out/'build.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)