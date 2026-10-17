"""Bounded first untraced attempt; no SHM removal or client modifications."""
import json,os,signal,subprocess,time
from pathlib import Path
ROOT=Path('/home/ideck/.local/share/Steam')
OUT=Path('/tmp/ideck-first-attempt')
OUT.mkdir(exist_ok=False)
started=time.monotonic()
first_browser=None; browser_started=None
def processes():
 out=[]
 for p in Path('/proc').iterdir():
  if not p.name.isdecimal():continue
  try:
   exe=os.readlink(p/'exe')
   if not exe.startswith(str(ROOT)+'/'):continue
   status=dict(x.split(':',1) for x in (p/'status').read_text().splitlines() if ':' in x)
   if status['Uid'].split()!=['1000']*4:continue
   fields=(p/'stat').read_text().rsplit(') ',1)[1].split()
   argv=(p/'cmdline').read_bytes().split(b'\0')
   tasks=[]
   for t in (p/'task').iterdir():
    try:tasks.append({'tid':int(t.name),'name':(t/'comm').read_text().strip(),'wchan':(t/'wchan').read_text().strip()})
    except OSError:pass
   out.append({'pid':int(p.name),'starttime':fields[19],'ppid':int(fields[1]),'exe':exe,
     'state':status['State'].strip(),'rss':status.get('VmRSS','').strip(),
     'no_new_privs':status.get('NoNewPrivs','').strip(),'seccomp':status.get('Seccomp','').strip(),
     'nspid':status.get('NSpid','').strip(),'tasks':tasks,
     'browser':exe==str(ROOT/'steamrtarm64/steamwebhelper') and not any(a.startswith(b'--type=') for a in argv),
     'sandbox_flags':[a.decode() for a in argv if a in [b'-cef-force-sandbox',b'-force-sandbox',b'--force-sandbox',b'--no-sandbox']],
     'child_type':[a.decode() for a in argv if a.startswith(b'--type=')]})
  except (OSError,ValueError,KeyError):continue
 return out
reason='observation_bound';frozen=[]
with (OUT/'timeline.jsonl').open('x') as log:
 while True:
  procs=processes(); elapsed=time.monotonic()-started
  stat=os.statvfs('/dev/shm');free=stat.f_bavail*stat.f_frsize
  objects=[]
  for p in Path('/dev/shm').iterdir():
   try:
    s=p.lstat();objects.append({'name':p.name,'size':s.st_size,'allocated':s.st_blocks*512,'inode':s.st_ino,'uid':s.st_uid})
   except OSError:pass
  row={'elapsed':round(elapsed,3),'processes':procs,'shm_free':free,'shm_capacity':stat.f_blocks*stat.f_frsize,'shm':objects}
  log.write(json.dumps(row)+'\n');log.flush()
  browsers=[p for p in procs if p['browser']]
  if browsers and first_browser is None:
   first_browser=(browsers[0]['pid'],browsers[0]['starttime']);browser_started=time.monotonic()
  if first_browser and not any((p['pid'],p['starttime'])==first_browser for p in browsers):
   reason='first_browser_ended_or_restarted';break
  if free<128*1024**2:reason='shm_128MiB_reserve';break
  if browser_started is not None and time.monotonic()-browser_started>90:
   reason='first_browser_90s_observation_bound';break
  if elapsed>420:reason='total_420s_observation_bound';break
  if elapsed>10 and not procs:reason='all_client_processes_exited';break
  time.sleep(1)
 # Freeze existing exact Steam executables only, preserving their SHM for capture.
 # No debugger is attached in this baseline, so no concurrent ptrace/signal work.
 for _ in range(2):
  procs=processes()
  procs.sort(key=lambda p:p['exe']!=str(ROOT/'steamrtarm64/steam'))
  for p in procs:
   try:
    fd=os.pidfd_open(p['pid'])
    current=next((x for x in processes() if x['pid']==p['pid']),None)
    if current and current['starttime']==p['starttime']:
     signal.pidfd_send_signal(fd,signal.SIGSTOP);frozen.append(p['pid'])
    os.close(fd)
   except (OSError,ProcessLookupError):pass
  time.sleep(.2)
 result={'reason':reason,'elapsed':round(time.monotonic()-started,3),'first_browser':first_browser,
   'baseline_ptrace_used':False,'shm_deleted':False,'frozen_pids':sorted(set(frozen)),
   'processes':processes(),'shm_free':os.statvfs('/dev/shm').f_bavail*os.statvfs('/dev/shm').f_frsize}
 (OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n')
