set -eu
ulimit -c 0
export PYTHONDONTWRITEBYTECODE=1
python3 - <<'PY'
import hashlib,importlib.util,json,os,pathlib,shutil,socket,ssl,subprocess,time,urllib.request
from pathlib import Path,PurePosixPath
out=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-preflight')
out.mkdir(exist_ok=False)
spec=importlib.util.spec_from_file_location('cached_install','/opt/ideck-steam/install-cached.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
pins=m.dependencies(json.loads((m.OPT/'steam-dependencies.lock.json').read_text()))
before=m.installed();m.audit()
conflicts=[p['name'] for p in pins if p['name'] in before and before[p['name']]!=p['version']]
if conflicts:raise RuntimeError('installed pin conflict: '+repr(conflicts))
missing=[p for p in pins if p['name'] not in before]
if shutil.disk_usage('/').free<3*1024**3:raise RuntimeError('guest reserve')
paths=[m.fetch(int(os.environ['IDECK_CACHE_PORT']),'debs',PurePosixPath(p['filename']).name,p['size'],p['sha256'],out/'debs') for p in missing]
env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','HOME':'/root','LANG':'C.UTF-8','DEBIAN_FRONTEND':'noninteractive'}
if paths:
    r=subprocess.run(['dpkg','-i',*map(str,paths)],env=env,capture_output=True)
    (out/'dpkg.stdout').write_bytes(r.stdout);(out/'dpkg.stderr').write_bytes(r.stderr)
    if r.returncode:raise RuntimeError('dpkg failed '+str(r.returncode))
audit=subprocess.run(['dpkg','--audit'],capture_output=True)
(out/'audit.stdout').write_bytes(audit.stdout);(out/'audit.stderr').write_bytes(audit.stderr)
if audit.returncode or audit.stdout or audit.stderr:raise RuntimeError('nonempty dpkg audit')
after=m.installed()
if any(after.get(n)!=v for n,v in before.items()):raise RuntimeError('preexisting packages changed')
if any(after.get(p['name'])!=p['version'] for p in pins):raise RuntimeError('pinned dependency absent')
root=Path('/home/ideck/.local/share/Steam')
def digest(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
identities={str(p.relative_to(root)):{'sha256':digest(p),'uid':p.stat().st_uid,'size':p.stat().st_size} for p in
    (root/'steamrtarm64/steam',root/'steamrtarm64/steamwebhelper',root/'steamrtarm64/steamclient.so',root/'steamrtarm64/chromehtml.so')}
if any(v['uid']!=1000 for v in identities.values()):raise RuntimeError('wrong client owner')
state={'status':'pass','installed_missing':[p['name'] for p in missing],'locked_dependencies':len(pins),
    'unchanged_existing_packages':len(before),'audit_exit':audit.returncode,'audit_stdout_bytes':len(audit.stdout),'audit_stderr_bytes':len(audit.stderr),
    'client':identities,'machine_id_sha256':digest(Path('/etc/machine-id')),
    'document_sha256':digest(Path('/home/ideck/Documents/ideck-steam-continuation-20261017.txt')),
    'lsof':subprocess.run(['lsof','-v'],capture_output=True,text=True).stderr,
    'guest_free_bytes':shutil.disk_usage('/').free,'shm_free_bytes':shutil.disk_usage('/dev/shm').free}
socket.setdefaulttimeout(15)
network=[]
for host in ('client-update.steamstatic.com','client-update.fastly.steamstatic.com'):
    row={'host':host,'started_ns':time.time_ns(),'certificate_verification':True,'proxy_configuration':'unchanged system defaults'}
    try:row['addresses']=sorted({a[4][0] for a in socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)})
    except OSError as e:row['dns_error']={'class':type(e).__name__,'errno':e.errno,'message':str(e)}
    if 'addresses' in row:
        try:
            url='https://'+host+'/steam_client_steamdeck_publicbeta_linuxarm64'
            with urllib.request.urlopen(url,timeout=20,context=ssl.create_default_context()) as r:
                b=r.read(1024*1024+1)
                if len(b)>1024*1024:raise RuntimeError('manifest response size bound')
                row.update(http_status=r.status,bytes=len(b),body_sha256=hashlib.sha256(b).hexdigest())
        except Exception as e:row['https_error']={'class':type(e).__name__,'message':str(e)}
    network.append(row)
state['network']=network
state['display_recovery']=json.loads(Path('/run/ideck/display-recovery.json').read_text())
state['resolver']=Path('/etc/resolv.conf').read_text()
(out/'result.json').write_text(json.dumps(state,indent=2)+'\n')
print('IDECK_LOCAL_PREFLIGHT='+json.dumps(state),flush=True)
print('HOME_RUNTIME_OWNERS')
subprocess.run(['stat','-c','%u:%g:%a %n','/home/ideck','/run/user/1000','/run/user/1000/Xauthority'])
print('X11_CHECK')
subprocess.run(['setpriv','--reuid=1000','--regid=1000','--init-groups','env','DISPLAY=:0','XAUTHORITY=/run/user/1000/Xauthority','xdpyinfo'],stdout=subprocess.DEVNULL,check=True)
PY
