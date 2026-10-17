set -eu
export PYTHONDONTWRITEBYTECODE=1
python3 - <<'PY'
from pathlib import Path
import os,sys,json,time,signal,subprocess
out=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-guarded-v2')
sys.path.insert(0,'/run/ideck')
import importlib.util
s=importlib.util.spec_from_file_location('trace','/run/ideck/trace-ipc-parent.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
items=json.loads((out/'freeze-identities.json').read_text());pins=[];rows=[]
for initial in items:
    try:i=m.proc_info(initial['pid'])
    except FileNotFoundError:continue
    assert i['starttime']==initial['starttime'] and i['exe']==initial['exe'] and i['uid']==[1000]*4 and i['tracer_pid']==0 and i['state'].startswith('T'),i
    fd=os.pidfd_open(i['pid']);pins.append((i,fd))
assert {2192,2295}<={i['pid'] for i,fd in pins}
probe=subprocess.Popen(['python3','/run/ideck/trace-ipc-parent.py','--main-pid','2192','--browser-pid','2295','--seconds','15','--output',str(out/'post-pause-trace')],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
reason='attach_timeout';started=time.monotonic();resumed=False
try:
    while time.monotonic()-started<8 and probe.poll() is None:
        info=m.proc_info(2295)
        if info['tracer_pid']:
            tr=m.proc_info(info['tracer_pid']);assert tr['exe']=='/opt/ideck-diagnostic-strace/usr/bin/strace'
            for old,fd in pins:
                cur=m.proc_info(old['pid']);assert cur['starttime']==old['starttime'] and cur['exe']==old['exe']
                signal.pidfd_send_signal(fd,signal.SIGCONT)
            resumed=True;reason='duration_limit';break
        time.sleep(.05)
    if not resumed:probe.send_signal(signal.SIGINT)
    while probe.poll() is None:
        st=os.statvfs('/dev/shm');free=st.f_bavail*st.f_frsize
        if free<384*1024**2 or time.monotonic()-started>35:
            reason='resource_guard' if free<384*1024**2 else 'wall_guard';probe.send_signal(signal.SIGINT);break
        time.sleep(.05)
    stdout,stderr=probe.communicate(timeout=15)
finally:
    for old,fd in pins:
        try:
            cur=m.proc_info(old['pid'])
            if cur['starttime']==old['starttime'] and cur['exe']==old['exe'] and cur['uid']==[1000]*4 and cur['tracer_pid']==0:
                signal.pidfd_send_signal(fd,signal.SIGSTOP);rows.append({'pid':cur['pid'],'stopped':True})
            else:rows.append({'pid':old['pid'],'stopped':False,'reason':'identity_or_tracer_changed'})
        except FileNotFoundError:rows.append({'pid':old['pid'],'exited':True})
        finally:os.close(fd)
result={'kind':'separate_post_pause_instrumented_probe','baseline_timing':False,'prior_long_group_pause':True,'resumed':resumed,'reason':reason,'elapsed':time.monotonic()-started,'probe_exit':probe.returncode,'stdout':stdout.decode(),'stderr':stderr.decode(),'groups':rows,'free_shm':os.statvfs('/dev/shm').f_bavail*os.statvfs('/dev/shm').f_frsize}
(out/'post-pause-probe.json').write_text(json.dumps(result,indent=2)+'\n');print('IDECK_POST_PAUSE='+json.dumps(result),flush=True)
PY