set -eu
python3 - <<'PY'
from pathlib import Path
import json,os,select,signal,time
out=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-guarded-v2')
def info(pid):
    p=Path('/proc')/str(pid);status=dict(x.split(':',1) for x in (p/'status').read_text().splitlines() if ':' in x);fields=(p/'stat').read_text().rsplit(') ',1)[1].split()
    return {'pid':pid,'starttime':fields[19],'state':fields[0],'uid':status['Uid'].split(),'tracer':int(status['TracerPid']),'ppid':int(status['PPid']),'exe':os.readlink(p/'exe')}
browser=info(2295);handler=info(2479)
if browser['starttime']!='119356' or browser['tracer']!=2479 or handler['starttime']!='124528' or handler['tracer'] or handler['ppid']!=2295:raise RuntimeError('crash ownership changed')
if any(r['uid']!=['1000']*4 or r['exe']!='/home/ideck/.local/share/Steam/steamrtarm64/steamwebhelper' for r in (browser,handler)):raise RuntimeError('unexpected owner/executable')
bfd=os.pidfd_open(2295);hfd=os.pidfd_open(2479)
result={'before':{'browser':browser,'handler':handler},'signalled_traced_target':False}
try:
    signal.pidfd_send_signal(hfd,signal.SIGCONT)
    poll=select.poll();poll.register(hfd,select.POLLIN)
    end=time.monotonic()+25
    while time.monotonic()<end:
        if poll.poll(5):
            result['handler_exited']=True
            try:
                now=info(2295)
                if now['starttime']!=browser['starttime'] or now['uid']!=['1000']*4:raise RuntimeError('browser identity changed')
                if now['tracer']:result['new_tracer']=now['tracer'];break
                signal.pidfd_send_signal(bfd,signal.SIGSTOP)
                result['browser_stopped_after_detach']=True
                frozen=json.loads((out/'freeze-identities.json').read_text())
                if not any(r['pid']==2295 for r in frozen):frozen.append({k:now[k] for k in ('pid','starttime','exe')})
                (out/'freeze-identities.json').write_text(json.dumps(frozen,indent=2)+'\n')
                result['after']=info(2295)
            except FileNotFoundError:result['browser_exited']=True
            break
        time.sleep(.005)
    else:result['handler_timeout']=True
    p=Path('/tmp/dumps/assert_20261017181345_5.dmp')
    with p.open('rb') as f:result['header_hex']=f.read(32).hex()
    result['size']=p.stat().st_size;v=os.statvfs('/dev/shm');result['shm_free_bytes']=v.f_bavail*v.f_frsize
    (out/'crash-handler-completion.json').write_text(json.dumps(result,indent=2)+'\n')
    print('IDECK_CRASH_HANDLER='+json.dumps(result),flush=True)
finally:os.close(bfd);os.close(hfd)
PY