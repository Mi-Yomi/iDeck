from pathlib import Path
import base64,gzip,json,hashlib
task=Path(__file__).parent
files={'libideck-ipc-connect.so':task/'ipc-probe-build-v3/libideck-ipc-connect.so','arm64-unit':task/'ipc-probe-tests-build-v3/arm64-unit','arm64-abi':task/'ipc-probe-tests-build-v3/arm64-abi','arm64-clone':task/'clone-stack-tests/arm64-clone'}
records={k:{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'base64_gzip':base64.b64encode(gzip.compress(p.read_bytes(),mtime=0)).decode()} for k,p in files.items()}
script="""set -eu
ulimit -c 0
python3 - <<'PY'
from pathlib import Path
import os,json,hashlib,gzip,base64,subprocess,time
root=Path('/opt/ideck-ipc-probe-v3');assert not root.exists();root.mkdir(mode=0o755)
records=RECORDS
for name,row in records.items():
 p=root/name;b=gzip.decompress(base64.b64decode(row['base64_gzip']));assert hashlib.sha256(b).hexdigest()==row['sha256'];p.write_bytes(b);p.chmod(0o555)
cases=[('clone-baseline',root/'arm64-clone',[]),('clone-old-v2',root/'arm64-clone',['LD_PRELOAD=/opt/ideck-ipc-probe/libideck-ipc-connect.so','IDECK_EXPECT_PRELOAD_LEAF=libideck-ipc-connect.so']),('clone-new-v3',root/'arm64-clone',['LD_PRELOAD='+str(root/'libideck-ipc-connect.so'),'IDECK_EXPECT_PRELOAD_LEAF=libideck-ipc-connect.so']),('unit-v3-real-and-raw-clone',root/'arm64-unit',[]),('abi-v3-baseline',root/'arm64-abi',[]),('abi-v3-preload',root/'arm64-abi',['LD_PRELOAD='+str(root/'libideck-ipc-connect.so'),'IDECK_EXPECT_PRELOAD_LEAF=libideck-ipc-connect.so'])]
tests=[]
for name,binary,extra in cases:
 r=subprocess.run(['setpriv','--reuid=1000','--regid=1000','--clear-groups','env','-i','PATH=/usr/bin:/bin',*extra,str(binary)],capture_output=True,text=True,timeout=20)
 row={'case':name,'exit':r.returncode,'stdout':r.stdout,'stderr':r.stderr};tests.append(row);print('ARM_V3_TEST='+json.dumps(row),flush=True)
result={'time_ns':time.time_ns(),'source_sha256':'dd7a19b8531294772b3b11e1742c12341d1df2bd77186fdbf042accdb9c9b4c6','library_sha256':records['libideck-ipc-connect.so']['sha256'],'tests':tests,'corrected_cases_pass':all(x['exit']==0 and not x['stderr'] for x in tests if x['case']!='clone-old-v2'),'old_stack_bug_reproduced':tests[1]['exit']!=0 and tests[0]['exit']==0}
out=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-connect-5000-v7');(out/'v3-runtime-tests.json').write_text(json.dumps(result,indent=2)+'\\n');print('ARM_V3_RESULT='+json.dumps(result),flush=True)
assert result['corrected_cases_pass']
PY
""".replace('RECORDS',repr(records))
assert len(script.encode())<65536
(task/'commands15/026-validate-stack-safe-probe.sh').write_text(script)
(task/'v3-stage-receipt.json').write_text(json.dumps({'script_sha256':hashlib.sha256(script.encode()).hexdigest(),'files':{k:{'sha256':r['sha256']} for k,r in records.items()}},indent=2)+'\n')
print(json.dumps({'queued':True,'bytes':len(script.encode())}))
