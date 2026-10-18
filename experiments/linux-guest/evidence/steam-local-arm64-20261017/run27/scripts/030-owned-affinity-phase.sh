set -eu
python3 - <<'PY'
from pathlib import Path
import os,json,time
out=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-desktop-zero-watchdog-v22')
root=Path('/home/ideck/.local/share/Steam')
assert not (out/'summary.json').exists(),'original monitor finished'
rows=[json.loads(line.split('=',1)[1]) for line in (out/'launcher.log').read_text().splitlines() if line.startswith('IDECK_NAMESPACE_ROOT_READY=')]
assert len(rows)==1
private_ns=rows[0]['rooted']['mount_namespace']
assert private_ns!=os.readlink('/proc/self/ns/mnt')
pins={};events=[]
def emit(kind,**data):events.append({'kind':kind,'wall_ns':time.time_ns(),**data})

def read(path):
    try: return Path(path).read_text(errors='replace')
    except OSError as e: return 'UNAVAILABLE:'+str(e.errno)

def link(path):
    try: return os.readlink(path)
    except OSError: return None

def fd_links(path):
    try: return {f.name:link(f) for f in path.iterdir()}
    except OSError: return {}

def processes():
    found={}
    for p in Path('/proc').iterdir():
        if not p.name.isdigit(): continue
        comm=read(p/'comm').strip()
        if comm not in ('steam','steamwebhelper','steamerrorreport','steamsysinfo'): continue
        st=read(p/'status'); fields={}
        for line in st.splitlines():
            if ':' in line:
                k,v=line.split(':',1)
                if k in ('Name','State','PPid','Uid','Gid','VmRSS','VmSwap','Threads','NSpid','NoNewPrivs','TracerPid','Seccomp','Cpus_allowed_list'): fields[k]=v.strip()
        fields.update(exe=link(p/'exe'),cmdline=read(p/'cmdline').replace('\x00',' '),stat=read(p/'stat'),wchan=read(p/'wchan'),syscall=read(p/'syscall'),ns={n:link(p/'ns'/n) for n in ('mnt','pid','user','ipc')})
        found[p.name]=fields
    return found

def identity(pid):
    p=Path('/proc')/str(pid)
    fields=(p/'stat').read_text().rsplit(') ',1)[1].split()
    status=dict(x.split(':',1) for x in (p/'status').read_text().splitlines() if ':' in x)
    return {'pid':int(pid),'starttime':fields[19],'exe':os.readlink(p/'exe'),
            'uid':status['Uid'].split(),'state':fields[0],'tracer':int(status['TracerPid']),'ppid':int(status['PPid'])}

def affinity_owner_matches(now,row):
    return (now['uid']==['1000']*4 and now['exe']==row.get('exe')==str(root/'steamrtarm64/steamwebhelper')
            and now['starttime']==row['stat'].rsplit(') ',1)[1].split()[19] and not now['tracer'])

def widen_owned_browser_affinity(ps):
    assert os.sched_getaffinity(0)=={0,1,2,3}, 'unexpected guest CPU budget'
    changed=[]
    for pid,row in ps.items():
        if pid not in pins or row.get('exe')!=str(root/'steamrtarm64/steamwebhelper'):continue
        try:
            now=identity(pid)
            if not affinity_owner_matches(now,row):continue
            for task in (Path('/proc')/pid/'task').iterdir():
                status=dict(line.split(':',1) for line in (task/'status').read_text().splitlines() if ':' in line)
                assert status['Uid'].split()==['1000']*4 and status['Tgid'].strip()==pid
                before=(task/'stat').read_text().rsplit(') ',1)[1].split()[19]
                tid=int(task.name);mask=os.sched_getaffinity(tid)
                if mask!={2,3}:continue
                assert affinity_owner_matches(identity(pid),row)
                os.sched_setaffinity(tid,{0,1,2,3})
                assert (task/'stat').read_text().rsplit(') ',1)[1].split()[19]==before
                assert os.sched_getaffinity(tid)=={0,1,2,3}
                changed.append({'pid':int(pid),'tid':tid,'starttime':before,'before':[2,3],'after':[0,1,2,3]})
        except (FileNotFoundError,ProcessLookupError):continue
    if changed:emit('affinity_expanded',threads=changed)

fixture={'uid':['1000']*4,'exe':str(root/'steamrtarm64/steamwebhelper'),'starttime':'123','tracer':0}
fixture_row={'exe':fixture['exe'],'stat':'1 (test) '+' '.join(['S']+['0']*18+['123'])}
assert affinity_owner_matches(fixture,fixture_row)
for key,value in [('uid',['0']*4),('starttime','124'),('tracer',1),('exe','/unrelated')]:
    assert not affinity_owner_matches(dict(fixture,**{key:value}),fixture_row)


ps=processes()
try:
 for pid,row in ps.items():
  if row.get('exe')!=str(root/'steamrtarm64/steamwebhelper') or row.get('Uid','').split()!=['1000']*4:continue
  if row['ns']['mnt']!=private_ns:continue
  fd=os.pidfd_open(int(pid))
  now=identity(pid)
  if not affinity_owner_matches(now,row) or os.readlink('/proc/'+pid+'/ns/mnt')!=private_ns:
   os.close(fd);continue
  pins[pid]={'fd':fd}
 assert pins,'no owned live browsers'
 assert not (out/'summary.json').exists(),'monitor finished before action'
 widen_owned_browser_affinity(ps)
 result={'phase':'one-shot additional affinity experiment after029 black navigation','original_helper_source':'prepare-run23.py literal function unchanged','owned_pids':sorted(map(int,pins)),'private_namespace_verified':True,'events':events,'original_guards_and_deadlines_unchanged':True,'signals_sent':False,'no_ui_success_claim':True}
 (out/'affinity-phase27.json').write_text(json.dumps(result,indent=2)+'\n')
 print('AFFINITY_PHASE='+json.dumps(result))
finally:
 for pin in pins.values():os.close(pin['fd'])

PY
