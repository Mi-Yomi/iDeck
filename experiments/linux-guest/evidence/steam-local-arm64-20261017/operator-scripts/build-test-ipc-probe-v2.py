import os,sys,json,subprocess,hashlib,resource
from pathlib import Path
resource.setrlimit(resource.RLIMIT_CORE,(0,0))
base=Path(__file__).resolve().parent;top=base.parent;sys.path.insert(0,str(top/'source/experiments/linux-guest/tools'));import gui_host_tools
out=base/'ipc-probe-tests-build-v2';out.mkdir(exist_ok=False);root=base/'private-cross-v5/root';wrappers=base/'ipc-probe-build-v2/wrappers'
flags=['-std=gnu11','-O2','-fno-omit-frame-pointer','-fno-optimize-sibling-calls','-fstack-protector-strong','-D_FORTIFY_SOURCE=3','-Wall','-Wextra','-Werror','-Wl,-z,relro,-z,now,-z,noexecstack']
env={**os.environ,'TMPDIR':str(base/'tmp'),'HOME':str(base/'tmp')}
def run(name,args,extra=None,timeout=30):
    r=subprocess.run(args,capture_output=True,text=True,timeout=timeout,env={**env,**(extra or {})},cwd=out);result={'arguments':list(map(str,args)),'exit':r.returncode,'stdout':r.stdout,'stderr':r.stderr};(out/(name+'.json')).write_text(json.dumps(result,indent=2)+'\n');print(name+': '+r.stdout+r.stderr,flush=True);assert r.returncode==0 and not r.stderr,name;return result
run('native-library',['gcc',*flags,'-fPIC','-fvisibility=hidden','-shared',str(base/'ipc-connect-wait.c'),'-ldl','-o',str(out/'libnative-probe.so')])
for kind,source in (('unit','ipc-probe-unit.c'),('abi','ipc-probe-abi.c')):
    run('native-build-'+kind,['gcc',*flags,str(base/source),'-ldl','-o',str(out/('native-'+kind))])
    prefix=gui_host_tools.command(root,[root/'usr/bin/aarch64-linux-gnu-gcc-14'])+['-B'+str(wrappers)+'/', '-B'+str(root/'usr/aarch64-linux-gnu/lib')+'/', '-B'+str(root/'usr/lib/gcc-cross/aarch64-linux-gnu/14')+'/', '--sysroot='+str(root),'-isystem',str(root/'usr/aarch64-linux-gnu/include'),'-fno-use-linker-plugin']
    run('arm64-build-'+kind,[*prefix,*flags,str(base/source),'-ldl','-o',str(out/('arm64-'+kind))],{'GCC_EXEC_PREFIX':str(root/'usr/lib/gcc-cross')+'/','COMPILER_PATH':str(wrappers)})
for name,extra in (('native-unit',[]),('native-abi-baseline',[]),('native-abi-preload',['LD_PRELOAD=./libnative-probe.so','IDECK_EXPECT_PRELOAD_LEAF=libnative-probe.so'])):
    binary=out/('native-unit' if name=='native-unit' else 'native-abi')
    run(name,['setpriv','--reuid=1000','--regid=1000','--clear-groups','env','IDECK_IPC_WAIT_MODE=extend-5000',*extra,str(binary)],timeout=15)
files={p.name:{'size':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in out.iterdir() if p.is_file() and p.suffix!='.json'}
result={'source_sha256':hashlib.sha256((base/'ipc-connect-wait.c').read_bytes()).hexdigest(),'native_unit_and_preload_abi':'pass','arm64_runtime_tests':'not yet run','files':files};(out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)