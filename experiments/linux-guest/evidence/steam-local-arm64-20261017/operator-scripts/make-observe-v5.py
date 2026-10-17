from pathlib import Path
import hashlib,json,ast
b=Path(__file__).resolve().parent
original=(b/'009-background-big-picture-v3.sh').read_text()
s=original.replace('resume-local-20261017-big-picture-v3','resume-local-20261017-connect-observe-v5').replace('local-guarded-v3','local-guarded-v5-observe')
s=s.replace('# Only lsof/dependencies differ from the prior baseline; preserve resource profile.','# Observer baseline: the verified library leaves every IPC deadline unchanged.')
s=s.replace("['python3','/opt/ideck-steam/namespace-check.py','launch','big-picture']","['python3','/run/ideck/namespace-connect-observe.py','launch','big-picture']")
s=s.replace("while time.monotonic()-started < 360:","while time.monotonic()-started < 600:\n    control=out/'finish-monitor'\n    if control.is_file():\n        assert not control.is_symlink() and control.stat().st_uid==0 and control.read_text().strip()=='stop'\n        reason='operator_requested_stop';break")
s=s.replace("                reason='ui_candidate_requires_screenshot_review'; break","                candidate_file=out/'ui-candidate.json'\n                if not candidate_file.exists():candidate_file.write_text(json.dumps({'seconds':time.monotonic()-started,'requires_real_screenshot_review':True})+'\\n')")
needle="    ps=processes();pin_seen(ps);memory=read('/proc/meminfo');shared=shm()"
addition='''
    for probe in Path('/run/user/1000').glob('ideck-ipc-connect-*.jsonl'):
        st=probe.lstat()
        if not stat.S_ISREG(st.st_mode) or st.st_uid!=1000 or st.st_nlink!=1 or st.st_size>131072 or (st.st_mode&0o777)!=0o600:raise RuntimeError('unsafe probe log')
        fd=os.open(probe,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
        try:
            current=os.fstat(fd)
            if (current.st_dev,current.st_ino,current.st_uid)!=(st.st_dev,st.st_ino,st.st_uid):raise RuntimeError('probe log identity changed')
            data=os.read(fd,131073);assert len(data)<=131072
        finally:os.close(fd)
        (out/probe.name).write_bytes(data)
'''
assert needle in s;s=s.replace(needle,needle+addition)
s=s.replace('import os, time, json, subprocess, signal, hashlib, threading, select','import os, time, json, subprocess, signal, hashlib, threading, select, stat')
s=s.replace("logs = root/'logs'","profile=json.loads(Path('/run/ideck/ipc-observe-profile.json').read_text());assert hashlib.sha256(Path('/run/ideck/namespace-connect-observe.py').read_bytes()).hexdigest()==profile['private_helper_sha256'];assert hashlib.sha256(Path('/opt/ideck-ipc-probe/libideck-ipc-connect.so').read_bytes()).hexdigest()==profile['library_sha256'];(out/'launch-profile.json').write_text(json.dumps(profile,indent=2)+'\\n')\nlogs = root/'logs'")
prefix="""set -eu
export PYTHONDONTWRITEBYTECODE=1
python3 - <<'PROFILE_SOURCE'
from pathlib import Path
import os,json,hashlib,stat
result=json.loads(Path('/home/ideck/steam-experiment-logs/resume-local-20261017-connect-5000-preflight/runtime-tests.json').read_text());assert result['passed'] and all(t['exit']==0 and not t['stderr'] for t in result['tests'])
assert result['source_sha256']=='9a45229272c8832fc247414dc6cb3de39db2a4a76629664157deaa01b652d873'
library=Path('/opt/ideck-ipc-probe/libideck-ipc-connect.so');st=library.lstat();assert stat.S_ISREG(st.st_mode) and st.st_uid==0 and not st.st_mode&0o022
library_sha=hashlib.sha256(library.read_bytes()).hexdigest();assert library_sha=='0bafcde8555281d433e9537e5bbdce669d932b9aa7e77323b924093f928f9339'
p=Path('/opt/ideck-steam/namespace-check.py');original=p.read_bytes();assert hashlib.sha256(original).hexdigest()=='96c929eafefb2f76aa7751fb1869baa6def54e5e31be2a0e6620a486bca64b0d'
needle=b"'/usr/local/bin/ideck-steam', mode], env)";assert original.count(needle)==1
replacement=b"'/usr/bin/env', 'LD_PRELOAD=/opt/ideck-ipc-probe/libideck-ipc-connect.so', 'IDECK_IPC_WAIT_MODE=observe', '/usr/local/bin/ideck-steam', mode], env)"
modified=original.replace(needle,replacement);helper=Path('/run/ideck/namespace-connect-observe.py');fd=os.open(helper,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o700)
with os.fdopen(fd,'wb') as f:f.write(modified)
assert p.read_bytes()==original
profile={'mode':'observe','original_deadline_ms':500,'effective_deadline_ms':500,'library_sha256':library_sha,'library_source_sha256':result['source_sha256'],'original_helper_sha256':hashlib.sha256(original).hexdigest(),'private_helper_sha256':hashlib.sha256(modified).hexdigest(),'only_helper_change':'env arguments after setpriv UID1000 drop','original_helper_unchanged':True,'sandbox_preserved':True,'resource_profile_changed':False}
p=Path('/run/ideck/ipc-observe-profile.json');fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
with os.fdopen(fd,'w') as f:json.dump(profile,f,indent=2);f.write('\\n')
print('IDECK_OBSERVER_PROFILE='+json.dumps(profile),flush=True)
PROFILE_SOURCE
"""
s=prefix+s
code=s.split("<<'IDECKPY'\n",1)[1].split('\nIDECKPY',1)[0];ast.parse(code)
(b/'011-background-observe-v5.sh').write_text(s)
(b/'commands13/003-start-observer.sh').write_text(s)
print(json.dumps({'script_sha256':hashlib.sha256(s.encode()).hexdigest(),'command_bytes':len(s.encode()),'deadline_changed':False}))