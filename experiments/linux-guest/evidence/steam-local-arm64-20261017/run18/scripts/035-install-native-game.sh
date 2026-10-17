set -eu
python3 - <<'PY'
from pathlib import Path
import os,stat,hashlib,json,subprocess,urllib.request
out=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-gamepadui-v13')
stop=json.loads((out/'application-stop.json').read_text())
assert stop['ready_for_original_vm_stop']
for p in Path('/proc').iterdir():
    if not p.name.isdecimal():continue
    try:assert os.readlink(p/'ns/mnt') not in stop['owned_mount_namespaces']
    except FileNotFoundError:pass
def packages():
    r=subprocess.run(['dpkg-query','-W','-f=${Package}\t${Version}\n'],check=True,capture_output=True,text=True)
    return dict(line.split('\t') for line in r.stdout.splitlines())
before=packages();assert 'xgalaga' not in before
assert os.statvfs('/').f_bavail*os.statvfs('/').f_frsize>3*1024**3
url='https://deb.debian.org/debian/pool/main/x/xgalaga/xgalaga_2.1.1.0-7_arm64.deb'
with urllib.request.urlopen(url,timeout=30) as response:
    payload=response.read(212893)
assert len(payload)==212892
sha=hashlib.sha256(payload).hexdigest()
assert sha=='68986eaee721a9060fa99a661a564ef30ec7485912057e8fe97a8722f447f240'
path=Path('/run/ideck/xgalaga-smoke.deb')
fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
with os.fdopen(fd,'wb') as f:f.write(payload)
result=subprocess.run(['dpkg','-i',str(path)],capture_output=True,text=True,timeout=60,env=dict(os.environ,DEBIAN_FRONTEND='noninteractive'))
(out/'game-install.log').write_text(result.stdout+result.stderr)
assert result.returncode==0
after=packages();assert after.get('xgalaga')=='2.1.1.0-7'
assert all(after.get(name)==version for name,version in before.items())
assert set(after)-set(before)=={'xgalaga'}
audit=subprocess.run(['dpkg','--audit'],capture_output=True)
assert audit.returncode==0 and not audit.stdout and not audit.stderr
report={'game':'xgalaga','version':'2.1.1.0-7','architecture':'arm64','package_sha256':sha,'package_size':len(payload),'existing_packages_unchanged':True,'new_packages':['xgalaga'],'dpkg_audit_clean':True,'started':False,'scope':'native ARM64 X11 smoke test, not Steam/Proton or iPhone acceptance'}
(out/'game-install.json').write_text(json.dumps(report,indent=2)+'\n')
print('IDECK_NATIVE_GAME_INSTALL='+json.dumps(report))
PY
