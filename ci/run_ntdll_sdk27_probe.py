#!/usr/bin/env python3
"""Own SDK field/offset compile only. No native link, SDK export or target run."""
import hashlib,json,os,platform,signal,stat,struct,subprocess,sys,time,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.work/ntdll-sdk27-probe'
FIELDS=('ri_billed_energy','ri_cycles','ri_diskio_bytesread','ri_energy_nj','ri_instructions','ri_page_wait_time_mach','ri_pageins','ri_pcycles','ri_phys_footprint','ri_runnable_time','ri_serviced_energy','ri_system_ptime','ri_system_time','ri_user_ptime','ri_user_time')
SOURCE_PIN='279fd0f83170425db002fe25d6bd62f6355f497d'
SOURCE_SHA='f29ba42ac8f4f416ecbfb82b055faecba0d955135eb6d0de4ffef0c207d4eb51'
MIB=1024*1024

def require(ok,message):
    if not ok:raise ValueError(message)
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):Path(path).write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
def source():
    return ('/* Own SDK availability/layout probe; no system call or execution. */\n'
      '#include <TargetConditionals.h>\n#include <stddef.h>\n#include <stdint.h>\n#include <sys/resource.h>\n'
      '#if !defined(__aarch64__) || !defined(__LP64__) || !TARGET_OS_IPHONE || TARGET_OS_SIMULATOR\n#error Device arm64 iOS required\n#endif\n'
      '_Static_assert(__ENVIRONMENT_IPHONE_OS_VERSION_MIN_REQUIRED__ == 170000, "iOS17 minimum");\n'+
      ''.join('_Static_assert(sizeof(((struct rusage_info_v6 *)0)->'+f+') == 8, "64-bit '+f+'");\n' for f in FIELDS)+
      '__attribute__((used)) const uint64_t sdk27_rusage_layout[] = {\n sizeof(struct rusage_info_v6),\n'+
      ',\n'.join(' offsetof(struct rusage_info_v6, '+f+'), sizeof(((struct rusage_info_v6 *)0)->'+f+')' for f in FIELDS)+'\n};\n')

def object_layout(data):
    require(len(data)>=32,'Short own probe object')
    magic,cpu,subtype,kind,ncmds,cmdsize,flags,reserved=struct.unpack_from('<8I',data)
    require((magic,cpu,subtype,kind)==(0xfeedfacf,0x100000c,0,1),'Own probe must be plain arm64 MH_OBJECT')
    require(ncmds<=128 and 32+cmdsize<=len(data),'Invalid command bounds')
    pos=32;versions=[];sections=[];symbols=None
    for _ in range(ncmds):
        require(pos+8<=32+cmdsize,'Short command');cmd,size=struct.unpack_from('<II',data,pos)
        require(size>=8 and pos+size<=32+cmdsize,'Invalid command')
        require(cmd not in (0x1d,0xc,0xe,0x80000018,0x8000001c,0x8000001f,0x80000023),'Signature/loader/dylib/RPATH prohibited')
        if cmd==0x32:
            require(size==24,'Unexpected build-version command');versions.append(struct.unpack_from('<4I',data,pos+8))
        elif cmd in (0x24,0x25,0x2f,0x30):raise ValueError('Unexpected legacy version')
        elif cmd==0x19:
            require(size>=72,'Short segment');count=struct.unpack_from('<I',data,pos+64)[0]
            require(size==72+count*80,'Invalid section count')
            for i in range(count):
                at=pos+72+i*80;addr,length,offset=struct.unpack_from('<QQI',data,at+32)
                sections.append((addr,length,offset))
        elif cmd==2:
            require(size==24 and symbols is None,'Duplicate/invalid symbol table');symbols=struct.unpack_from('<4I',data,pos+8)
        pos+=size
    require(pos==32+cmdsize and versions==[(2,0x110000,0x1b0000,0)],'Exact iOS17 / SDK27 metadata required')
    require(symbols is not None,'Missing own layout symbol')
    off,count,stroff,strsize=symbols
    require(count<=10000 and off+16*count<=len(data) and stroff+strsize<=len(data),'Invalid symbol bounds')
    values=[]
    for i in range(count):
        index,typ,section,desc,value=struct.unpack_from('<IBBHQ',data,off+16*i)
        require(index<strsize,'Invalid symbol string')
        end=data.find(b'\0',stroff+index,stroff+strsize);require(end>=0,'Unterminated symbol')
        if data[stroff+index:end]!=b'_sdk27_rusage_layout':continue
        require(typ==0xf and 1<=section<=len(sections),'Own symbol is not an external section definition')
        addr,length,fileoff=sections[section-1];size=(1+2*len(FIELDS))*8
        require(value>=addr and value-addr+size<=length and fileoff+value-addr+size<=len(data),'Own data outside section')
        values.append(struct.unpack_from('<'+'Q'*(1+2*len(FIELDS)),data,fileoff+value-addr))
    require(len(values)==1,'Exactly one own layout symbol required');v=values[0]
    result={'struct_size':v[0],'fields':{f:{'offset':v[1+2*i],'bytes':v[2+2*i]} for i,f in enumerate(FIELDS)}}
    require(0<v[0]<=4096 and all(r['bytes']==8 and r['offset']+8<=v[0] for r in result['fields'].values()),'Invalid real compiler layout')
    return result

class Probe:
    def __init__(self):
        require(sys.platform=='darwin' and platform.machine()=='arm64','Actual arm64 Mac required')
        require(os.environ.get('FREE_QUOTA_VERIFIED')=='true' and os.environ.get('PRIVATE_SOURCE_VERIFIED')=='true','Manual free/private review required')
        require(sha(__file__)==os.environ.get('EXPECTED_NTDLL_SDK27_PROBE_SHA256'),'Exact runner digest required')
        require(not OUT.exists() and not any(p.is_symlink() for p in (OUT,*OUT.parents)),'Fresh symlink-free output required')
        OUT.mkdir(parents=True);(OUT/'home').mkdir();(OUT/'tmp').mkdir()
        self.deadline=time.monotonic()+240;self.active=None;self.commands=[]
        self.env={'PATH':'/usr/bin:/bin:/usr/sbin:/sbin','HOME':str(OUT/'home'),'TMPDIR':str(OUT/'tmp'),'LC_ALL':'C','LANG':'C'}
        if os.environ.get('DEVELOPER_DIR'):self.env['DEVELOPER_DIR']=os.environ['DEVELOPER_DIR']
    def run(self,label,argv):
        require(time.monotonic()<self.deadline,'Aggregate deadline before command')
        log=OUT/(label+'.log');row={'label':label,'argv':list(map(str,argv)),'exit_code':None,'log':log.name}
        self.commands.append(row);write(OUT/'commands.json',self.commands)
        try:
            with log.open('xb') as stream:
                self.active=subprocess.Popen(list(map(str,argv)),env=self.env,cwd=OUT,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
                deadline=min(self.deadline,time.monotonic()+35)
                while self.active.poll() is None:
                    require(time.monotonic()<deadline,'Command/aggregate timeout: '+label)
                    require(log.stat().st_size<=MIB,'Command log cap: '+label);time.sleep(.05)
                row['exit_code']=self.active.returncode
            require(time.monotonic()<self.deadline,'Aggregate deadline after command')
            require(log.stat().st_size<=MIB,'Fast-exit log cap')
            require(row['exit_code']==0,'Command failed: '+label)
            return log.read_text().strip()
        finally:
            if self.active:
                try:os.killpg(self.active.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                self.active.wait();self.active=None
            row['log_sha256']=sha(log) if log.exists() else None;write(OUT/'commands.json',self.commands)
    def execute(self):
        require(self.run('xcode',['/usr/bin/xcodebuild','-version'])=='Xcode 27.0\nBuild version 27A266a','Reviewed Xcode27 required')
        require(self.run('cpu',['/usr/sbin/sysctl','-n','machdep.cpu.brand_string']) in ('Apple M2','Apple M2 (Virtual)'),'Reviewed M2 required')
        require(self.run('sdk-version',['/usr/bin/xcrun','--sdk','iphoneos','--show-sdk-version'])=='27.0','Exact SDK27 required')
        dev=Path(self.env.get('DEVELOPER_DIR') or self.run('developer',['/usr/bin/xcode-select','-p'])).resolve(strict=True)
        require(dev.parts[-2:]==('Contents','Developer'),'Full selected Xcode required');self.env['DEVELOPER_DIR']=str(dev)
        sdk=Path(self.run('sdk-path',['/usr/bin/xcrun','--sdk','iphoneos','--show-sdk-path'])).resolve(strict=True)
        clang=Path(self.run('find-clang',['/usr/bin/xcrun','--sdk','iphoneos','--find','clang']))
        require(sdk.is_dir() and sdk.is_relative_to(dev) and clang.is_file() and clang.resolve().is_relative_to(dev),'Selected Xcode containment')
        self.run('clang-version',[clang,'--version'])
        header=(sdk/'usr/include/sys/resource.h').resolve(strict=True)
        require(header.is_relative_to(sdk) and header.is_file() and header.stat().st_size<=MIB,'Selected SDK resource header required')
        write(OUT/'sdk-header-identity.json',{'reported':str(sdk/'usr/include/sys/resource.h'),'resolved':str(header),'bytes':header.stat().st_size,'sha256':sha(header),'contents_exported':False,'sdk':str(sdk),'clang':str(clang),'clang_sha256':sha(clang)})
        own=OUT/'rusage_field_probe.c';own.write_text(source())
        write(OUT/'source-identity.json',{'madeira':SOURCE_PIN,'upstream_path':'build/ntdll-unix/server_ios.c','upstream_sha256':SOURCE_SHA,'function':'ios_xprobe_main','fields':FIELDS,'own_source_sha256':sha(own),'upstream_source_modified':False})
        self.run('compile',[clang,'-target','arm64-apple-ios17.0','-isysroot',sdk,'-std=gnu17','-Werror','-fno-common','-c',own,'-o',OUT/'rusage_field_probe.o'])
        obj=OUT/'rusage_field_probe.o';require(obj.stat().st_size<=MIB,'Own object bound')
        layout=object_layout(obj.read_bytes());write(OUT/'layout.json',dict(layout,object_sha256=sha(obj),object_bytes=obj.stat().st_size,own_source_sha256=sha(own)))
        return {'status':'all-15-fields-compiled','sdk':'27.0','minimum':'17.0','layout':layout}

def main():
    probe=None;result={'status':'failed','target_executed':False,'linked':False,'sdk_copied':False,'source_modified':False}
    try:
        probe=Probe();signal.signal(signal.SIGTERM,lambda *_:(_ for _ in ()).throw(KeyboardInterrupt('termination')))
        result.update(probe.execute());return 0
    except BaseException as error:
        result['error']=str(error);print('SDK27 field probe failed: '+str(error),file=sys.stderr);return 1
    finally:
        if probe:
            write(OUT/'result.json',result)
            allowed={'result.json','commands.json','sdk-header-identity.json','source-identity.json','rusage_field_probe.c','rusage_field_probe.o','layout.json'}|{r['log'] for r in probe.commands}
            rows=[];total=0
            with zipfile.ZipFile(OUT/'ntdll-sdk27-evidence.zip.part','x',zipfile.ZIP_DEFLATED) as z:
                for name in sorted(allowed):
                    p=OUT/name
                    if not p.exists():continue
                    info=p.stat();require(not p.is_symlink() and stat.S_ISREG(info.st_mode) and info.st_size<=MIB,'Evidence path/type/cap')
                    total+=info.st_size;require(total<=16*MIB,'Evidence aggregate cap')
                    z.write(p,name);rows.append({'path':name,'size':info.st_size,'sha256':sha(p)})
                z.writestr('inventory.json',json.dumps(rows,indent=2)+'\n')
            (OUT/'ntdll-sdk27-evidence.zip.part').replace(OUT/'ntdll-sdk27-evidence.zip')
            print(json.dumps(result,sort_keys=True))
if __name__=='__main__':raise SystemExit(main())
