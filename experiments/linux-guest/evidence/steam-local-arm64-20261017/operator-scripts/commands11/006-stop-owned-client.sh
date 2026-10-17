set -eu
python3 - <<'PY'
from pathlib import Path
import json,os,select,signal,time
out=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-guarded-attempt-11')
def scan():
    result=[]
    for p in Path('/proc').iterdir():
        if not p.name.isdecimal():continue
        try:
            status=dict(x.split(':',1) for x in (p/'status').read_text().splitlines() if ':' in x)
            fields=(p/'stat').read_text().rsplit(') ',1)[1].split()
            if status['Uid'].split()!=['1000']*4 or fields[0]=='Z':continue
            argv=(p/'cmdline').read_bytes()
            if not (b'/home/ideck/.local/share/Steam/' in argv or b'/usr/local/bin/ideck-steam' in argv):continue
            if int(status['TracerPid']):raise RuntimeError('diagnostic still attached')
            result.append({'pid':int(p.name),'starttime':fields[19],'uid':status['Uid'].split(),'state':fields[0]})
        except FileNotFoundError:pass
    return result
captured=[];sent=[]
for attempt in range(3):
    rows=scan()
    if not rows:break
    pins=[]
    for row in rows:
        try:
            fd=os.pidfd_open(row['pid']);p=Path('/proc')/str(row['pid'])
            fields=(p/'stat').read_text().rsplit(') ',1)[1].split()
            status=dict(x.split(':',1) for x in (p/'status').read_text().splitlines() if ':' in x)
            if fields[19]!=row['starttime'] or status['Uid'].split()!=['1000']*4 or int(status['TracerPid']):os.close(fd);raise RuntimeError('owned identity changed before stop')
            captured.append(row);pins.append((row,fd))
            signal.pidfd_send_signal(fd,signal.SIGTERM);sent.append({'pid':row['pid'],'signal':'SIGTERM'})
            if row['state']=='T':signal.pidfd_send_signal(fd,signal.SIGCONT)
        except ProcessLookupError:pass
        except FileNotFoundError:pass
    time.sleep(2)
    for row,fd in pins:
        poll=select.poll();poll.register(fd,select.POLLIN)
        if not poll.poll(0):signal.pidfd_send_signal(fd,signal.SIGKILL);sent.append({'pid':row['pid'],'signal':'SIGKILL'})
        os.close(fd)
    time.sleep(.25)
remaining=scan()
result={'captured':captured,'signals':sent,'remaining':remaining,'application_stop':'unclean owned-process termination after failed initialization','ready_for_orphan_check':not remaining,'time_ns':time.time_ns()}
(out/'owned-stop.json').write_text(json.dumps(result,indent=2)+'\n')
print('IDECK_OWNED_STOP='+json.dumps(result),flush=True)
if remaining:raise RuntimeError('Steam remains alive; no cleanup authorized')
PY