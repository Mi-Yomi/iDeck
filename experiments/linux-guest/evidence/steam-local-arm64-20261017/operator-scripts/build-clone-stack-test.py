from pathlib import Path
import os,sys,subprocess,json,hashlib,base64,gzip
task=Path(__file__).parent;sys.path.insert(0,str(task.parent/'source/experiments/linux-guest/tools'))
import gui_host_tools
root=task/'private-cross-v5/root';wrappers=task/'ipc-probe-build-v2/wrappers';out=task/'clone-stack-tests';out.mkdir(exist_ok=False)
args=gui_host_tools.command(root,[root/'usr/bin/aarch64-linux-gnu-gcc-14'])+['-B'+str(wrappers)+'/', '-B'+str(root/'usr/aarch64-linux-gnu/lib')+'/', '-B'+str(root/'usr/lib/gcc-cross/aarch64-linux-gnu/14')+'/', '--sysroot='+str(root),'-isystem',str(root/'usr/aarch64-linux-gnu/include'),'-fno-use-linker-plugin','-O2','-fno-omit-frame-pointer','-fno-optimize-sibling-calls','-fstack-protector-strong','-D_FORTIFY_SOURCE=3','-Wall','-Wextra','-Werror',str(task/'ipc-clone-stack.c'),'-ldl','-Wl,-z,relro,-z,now,-z,noexecstack','-o',str(out/'arm64-clone')]
env={**os.environ,'GCC_EXEC_PREFIX':str(root/'usr/lib/gcc-cross')+'/','COMPILER_PATH':str(wrappers),'TMPDIR':str(task/'tmp'),'HOME':str(task/'tmp'),'PYTHONDONTWRITEBYTECODE':'1'}
r=subprocess.run(args,capture_output=True,text=True,env=env);assert r.returncode==0,(r.stdout,r.stderr)
b=(out/'arm64-clone').read_bytes();record={'arguments':args,'source_sha256':hashlib.sha256((task/'ipc-clone-stack.c').read_bytes()).hexdigest(),'elf_sha256':hashlib.sha256(b).hexdigest(),'exit':r.returncode,'stdout':r.stdout,'stderr':r.stderr};(out/'build.json').write_text(json.dumps(record,indent=2)+'\n')
payload=base64.b64encode(gzip.compress(b,mtime=0)).decode()
script="""set -eu
python3 - <<'PY'
from pathlib import Path
import base64,gzip,hashlib,subprocess,json,os,time
p=Path('/run/ideck/arm64-clone-stack-test');assert not p.exists()
b=gzip.decompress(base64.b64decode(PAYLOAD));assert hashlib.sha256(b).hexdigest()==DIGEST
p.write_bytes(b);p.chmod(0o555)
results=[]
for name,extra in (('baseline',[]),('old-v2-preload',['LD_PRELOAD=/opt/ideck-ipc-probe/libideck-ipc-connect.so','IDECK_EXPECT_PRELOAD_LEAF=libideck-ipc-connect.so'])):
 argv=['setpriv','--reuid=1000','--regid=1000','--clear-groups','env','-i','PATH=/usr/bin:/bin',*extra,str(p)]
 r=subprocess.run(argv,capture_output=True,text=True,timeout=15);row={'case':name,'exit':r.returncode,'stdout':r.stdout,'stderr':r.stderr};results.append(row);print('CLONE_STACK='+json.dumps(row),flush=True)
out=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-connect-5000-v7');(out/'clone-stack-old-v2.json').write_text(json.dumps({'elf_sha256':DIGEST,'tests':results,'time_ns':time.time_ns()},indent=2)+'\\n')
assert results[0]['exit']==0,'baseline itself failed; no inference about interposer'
PY
""".replace('PAYLOAD',repr(payload)).replace('DIGEST',repr(record['elf_sha256']))
assert len(script)<65536;(task/'commands15/025-test-clone-stack-abi.sh').write_text(script)
print(json.dumps({'built':True,'elf_sha256':record['elf_sha256'],'script_bytes':len(script)}))
