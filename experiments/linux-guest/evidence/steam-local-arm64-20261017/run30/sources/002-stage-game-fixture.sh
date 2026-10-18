set -eu
export PYTHONDONTWRITEBYTECODE=1
python3 - <<'STAGE'
from pathlib import Path
import importlib.util,hashlib,json,os,subprocess
source=Path('/opt/ideck-steam/namespace-check.py')
assert hashlib.sha256(source.read_bytes()).hexdigest()=='96c929eafefb2f76aa7751fb1869baa6def54e5e31be2a0e6620a486bca64b0d'
spec=importlib.util.spec_from_file_location('original_namespace',source);ns=importlib.util.module_from_spec(spec);spec.loader.exec_module(ns);ns.guard()
out=Path('/home/ideck/steam-experiment-logs/game-run30');out.mkdir(mode=0o700,exist_ok=False)
names=set()
for p in Path('/proc').iterdir():
 if not p.name.isdecimal():continue
 try:
  exe=os.readlink(p/'exe')
  assert not exe.endswith(('/steamrtarm64/steam','/steamrtarm64/steamwebhelper'))
  names.add(os.readlink(p/'ns/mnt'))
 except (FileNotFoundError,ProcessLookupError):pass
(out/'baseline-namespaces.json').write_text(json.dumps(sorted(names))+'\n')
shared=Path('/opt/ideck-tools-probe29/variables/game30-shared');shared.mkdir(mode=0o700,exist_ok=False);os.chown(shared,1000,1000)
compat=shared/'compatdata';compat.mkdir(mode=0o700);os.chown(compat,1000,1000)
assert os.statvfs(shared).f_bavail*os.statvfs(shared).f_frsize>1024**3
proton=Path('/opt/ideck-tools-probe29/tool-install/compatibilitytools.d/GE-Proton11-9-aarch64')
assert '"require_tool_appid" "4185400"' in (proton/'toolmanifest.vdf').read_text()

STAGE
cat > /run/ideck/game-namespace30.py <<'SOURCE'
from pathlib import Path
import importlib.util,json,os,sys
source=Path('/opt/ideck-steam/namespace-check.py')
spec=importlib.util.spec_from_file_location('original_namespace',source)
ns=importlib.util.module_from_spec(spec);spec.loader.exec_module(ns)
ns.guard();operations=[];before=ns.snapshot();ns.private_root(operations);rooted=ns.snapshot()
pre=ns.exec_preflight('inherited-private-real-root')
pidpre=ns.exec_preflight('inherited-private-real-root',True)
assert pre.get('status')==pidpre.get('status')=='pass'
print('IDECK_TOOL_NAMESPACE='+json.dumps({'rooted':rooted,'preflight':pre,'pid_preflight':pidpre}),flush=True)
case=json.loads(sys.argv[1]);assert set(case)=={'argv','seconds','variable'}
record=Path('/home/ideck/steam-experiment-logs/game-run30')/('namespace-'+Path(case['variable']).name+'.json')
with record.open('x') as f:json.dump({'rooted':rooted,'preflight':pre,'pid_preflight':pidpre},f)
env={'PATH':'/usr/bin:/bin','HOME':'/home/ideck','USER':'ideck','LOGNAME':'ideck','LANG':'C.UTF-8',
     'DISPLAY':':0','XAUTHORITY':'/run/user/1000/Xauthority','XDG_RUNTIME_DIR':'/run/user/1000',
     'PRESSURE_VESSEL_VARIABLE_DIR':case['variable'],'WINEPREFIX':case['variable']+'/wineprefix'}
env.pop('WINEPREFIX',None)
env.update({'PYTHONDONTWRITEBYTECODE': '1', 'SteamAppId': '0', 'SteamGameId': '0', 'UMU_ID': 'umu-default', 'UMU_USE_STEAM': '0', 'STEAM_COMPAT_CLIENT_INSTALL_PATH': '/home/ideck/.local/share/Steam', 'STEAM_COMPAT_DATA_PATH': '/opt/ideck-tools-probe29/variables/game30-shared/compatdata', 'PROTON_LOG': '1', 'PROTONFIXES_DISABLE': '1', 'PROTON_LOCAL_SHADER_CACHE': '0', 'PROTON_FSR3_UPGRADE': '0', 'PROTON_FSR4_UPGRADE': '0', 'PROTON_MLFG_UPGRADE': '0', 'PROTON_DLSS_UPGRADE': '0', 'PROTON_XESS_UPGRADE': '0', 'PROTON_USE_OPTISCALER': '0', 'WINEDLLOVERRIDES': 'mscoree,mshtml='})
env.update({'PROTON_LOG_DIR':case['variable']+'/proton-logs','XDG_CACHE_HOME':case['variable']+'/cache','XDG_CONFIG_HOME':case['variable']+'/config'})
os.closerange(3,65536)
os.execve('/usr/bin/setpriv',['setpriv','--reuid=1000','--regid=1000','--init-groups',
          'timeout','--kill-after=5s',str(case['seconds'])+'s','dbus-run-session','--',*case['argv']],env)

SOURCE
chmod 600 /run/ideck/game-namespace30.py
cat > /run/ideck/game-guardian30.py <<'SOURCE'
from pathlib import Path
import hashlib,json,os,re,signal,subprocess,sys,time

out=Path('/home/ideck/steam-experiment-logs/game-run30')
case=sys.argv[1];assert case in ('arm64','x64','x64-repeat')
folder=out/case;folder.mkdir(mode=0o700,exist_ok=False)
stage=Path('/opt/ideck-tools-probe29')
proton=stage/'tool-install/compatibilitytools.d/GE-Proton11-9-aarch64'
arch='aarch64-windows' if case=='arm64' else 'x86_64-windows'
game=proton/'files/lib/wine'/arch/'winemine.exe'
expected={'arm64':'c50c5e538bca4eb31d6355b599d2ee11001fa752c5d49e558b57a9e91f24e656',
          'x64':'1d46a3c30b4ccacb3be50ab0d83a3537a04e06977d5193a274289233e758a820'}
assert hashlib.sha256(game.read_bytes()).hexdigest()==expected['arm64' if case=='arm64' else 'x64']
variable=stage/'variables'/('game30-'+case);variable.mkdir(mode=0o700,exist_ok=False);os.chown(variable,1000,1000)
baseline=set(json.loads((out/'baseline-namespaces.json').read_text()))
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()

def identity(pid):
 p=Path('/proc')/str(pid)
 status=dict(s.split(':',1) for s in p.joinpath('status').read_text().splitlines() if ':' in s)
 return {'pid':pid,'starttime':p.joinpath('stat').read_text().rsplit(') ',1)[1].split()[19],
         'exe':os.readlink(p/'exe'),'uid':status['Uid'].split(),'ppid':int(status['PPid']),
         'tracer':int(status['TracerPid'])}

def same_child(current,initial):
 return (current['pid']==initial['pid'] and current['starttime']==initial['starttime']
         and current['ppid']==os.getpid() and current['tracer']==0
         and current['uid'] in (['0']*4,['1000']*4)
         and Path(current['exe']).name in ('python3.13','python3','setpriv','timeout'))

# Security self-check: a reused PID/starttime or a different owner is refused.
test={'pid':1,'starttime':'2','ppid':os.getpid(),'tracer':0,'uid':['1000']*4,'exe':'/usr/bin/timeout'}
assert same_child(test,test) and not same_child({**test,'starttime':'3'},test)
assert not same_child({**test,'uid':['1001']*4},test)
assert not same_child({**test,'ppid':os.getpid()+1},test)

def stop_owned(child,fd,initial,signals):
 if child.poll() is not None:return
 try:
  assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==boot
  assert same_child(identity(child.pid),initial)
  signal.pidfd_send_signal(fd,signal.SIGTERM);signals.append('SIGTERM to owned timeout/helper')
 except (FileNotFoundError,ProcessLookupError):
  child.wait(timeout=2);return
 child.wait(timeout=20)

def snapshot():
 memory=Path('/proc/meminfo').read_text()
 available=int(re.search(r'^MemAvailable:\s+(\d+)',memory,re.M)[1])
 vm=Path('/proc/vmstat').read_text();oom=int(re.search(r'^oom_kill\s+(\d+)',vm,re.M)[1])
 rows=[];unexpected=[]
 for p in Path('/proc').iterdir():
  if not p.name.isdecimal():continue
  try:
   exe=os.readlink(p/'exe')
   if exe.endswith(('/steamrtarm64/steam','/steamrtarm64/steamwebhelper')):unexpected.append(int(p.name))
   ns=os.readlink(p/'ns/mnt')
   if ns in baseline:continue
   status=dict(s.split(':',1) for s in p.joinpath('status').read_text().splitlines() if ':' in s)
   if status['Uid'].split()!=['1000']*4:continue
   maps=p.joinpath('maps').read_text(errors='replace')
   rows.append({'pid':int(p.name),'starttime':p.joinpath('stat').read_text().rsplit(') ',1)[1].split()[19],
     'exe':exe,'uid':status['Uid'].split(),'ppid':int(status['PPid']),'tracer':int(status['TracerPid']),
     'nspid':status.get('NSpid','').split(),'state':status['State'].strip(),'rss':status.get('VmRSS','').strip(),
     'cmdline':p.joinpath('cmdline').read_text().replace(chr(0),' '),'mnt':ns,
     'mapped_winemine':[line for line in maps.splitlines() if 'winemine.exe' in line],
     'mapped_fex':[line for line in maps.splitlines() if 'libarm64ecfex' in line or 'libwow64fex' in line]})
  except (FileNotFoundError,ProcessLookupError):pass
 return {'seconds':round(time.monotonic()-started,3),'available_kib':available,'oom_kill':oom,
         'processes':rows,'unexpected_steam_pids':unexpected}

argv=[str(stage/'SteamLinuxRuntime_4-arm64/_v2-entry-point'),'--verb=waitforexitandrun','--',
      str(proton/'proton'),'waitforexitandrun',str(game)]
started=time.monotonic();samples=[];signals=[];failure=None;reason='application_exit'
with (folder/'stdout.log').open('xb') as stdout,(folder/'stderr.log').open('xb') as stderr:
 child=subprocess.Popen(['python3','/run/ideck/game-namespace30.py',json.dumps({'argv':argv,'seconds':360,'variable':str(variable)})],
          stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,start_new_session=True)
 fd=os.pidfd_open(child.pid);initial=identity(child.pid)
 (folder/'started.json').write_text(json.dumps({'boot_id':boot,'child':initial,'guardian_pid':os.getpid(),
          'case':case,'pe_target':str(game),'target_sha256':expected['arm64' if case=='arm64' else 'x64'],
          'max_seconds':360,'private_compatdata':str(stage/'variables/game30-shared/compatdata')},indent=2)+'\n')
 try:
  while child.poll() is None:
   sample=snapshot();samples.append(sample)
   with (folder/'timeline.jsonl').open('a') as f:f.write(json.dumps(sample)+'\n')
   temporary=folder/'latest.json.partial'
   temporary.write_text(json.dumps(sample,indent=2)+'\n');temporary.replace(folder/'latest.json')
   cause=('unexpected_steam_start' if sample['unexpected_steam_pids'] else
          'memory_reserve' if sample['available_kib']<512*1024 else
          'kernel_oom' if sample['oom_kill']>samples[0]['oom_kill'] else
          'outer_deadline' if time.monotonic()-started>380 else
          'log_size_bound' if stdout.tell()>16*1024**2 or stderr.tell()>16*1024**2 else None)
   if cause:
    reason=cause
    stop_owned(child,fd,initial,signals);break
   time.sleep(1)
 except BaseException as error:
  failure=type(error).__name__;reason='guardian_failure'
  if child.poll() is None:
   stop_owned(child,fd,initial,signals)
 finally:
  os.close(fd)
  result={'case':case,'exit':child.poll(),'seconds':round(time.monotonic()-started,3),'reason':reason,
    'failure_class':failure,'signals':signals,'samples':len(samples),'minimum_available_kib':min((s['available_kib'] for s in samples),default=None),
    'first_oom':samples[0]['oom_kill'] if samples else None,'last_oom':samples[-1]['oom_kill'] if samples else None,
    'ui_review_required':True,'gameplay_automatically_accepted':False,'steam_or_iphone_acceptance':False}
  (folder/'result.json').write_text(json.dumps(result,indent=2)+'\n')
  print(json.dumps(result),flush=True)

SOURCE
chmod 600 /run/ideck/game-guardian30.py
