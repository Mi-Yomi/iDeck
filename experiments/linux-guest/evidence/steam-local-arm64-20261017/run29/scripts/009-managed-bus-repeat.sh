set -eu
python3 - <<'PY'
from pathlib import Path
import os,json,subprocess,time,hashlib
out=Path('/home/ideck/steam-experiment-logs/runtime-tools-run29')
prior=json.loads((out/'final-postcheck.json').read_text())
assert prior['ready_for_original_vm_stop'] and not prior['private_namespace_holders']
assert Path('/usr/bin/dbus-run-session').is_file()
original=Path('/run/ideck/tools-namespace29.py').read_text()
old="str(case['seconds'])+'s',*case['argv']],env)"
new="str(case['seconds'])+'s','dbus-run-session','--',*case['argv']],env)"
assert original.count(old)==1
modified=original.replace(old,new);compile(modified,'managed-bus-helper29','exec')
helper=Path('/run/ideck/tools-namespace29-managedbus.py')
with helper.open('x') as f:f.write(modified)
helper.chmod(0o600)
stage=Path('/opt/ideck-tools-probe29');variable=stage/'variables/container-wine-managedbus'
variable.mkdir(mode=0o700,exist_ok=False);os.chown(variable,1000,1000)
argv=[str(stage/'SteamLinuxRuntime_4-arm64/_v2-entry-point'),'--verb=waitforexitandrun','--',
      str(stage/'tool-install/compatibilitytools.d/GE-Proton11-9-aarch64/files/bin-arm64/wine'),'--version']
start=time.monotonic()
p=subprocess.run(['python3',str(helper),json.dumps({'argv':argv,'seconds':180,'variable':str(variable)})],
                 capture_output=True,stdin=subprocess.DEVNULL,start_new_session=True,timeout=270)
(out/'managed-bus-repeat.stdout.log').write_bytes(p.stdout)
(out/'managed-bus-repeat.stderr.log').write_bytes(p.stderr)
baseline=set(json.loads((out/'baseline-namespaces.json').read_text()));holders=[]
for proc in Path('/proc').iterdir():
 if not proc.name.isdecimal():continue
 try:
  if os.readlink(proc/'ns/mnt') not in baseline:holders.append(int(proc.name))
 except (FileNotFoundError,ProcessLookupError):pass
r={'case':'container-wine-version-managed-bus','exit':p.returncode,'seconds':round(time.monotonic()-start,3),
   'wine_version_reported':b'wine-' in p.stdout,'private_namespace_holders':holders,
   'only_helper_change':'dbus-run-session inside existing UID1000 timeout; root and namespace guards unchanged',
   'original_helper_sha256':hashlib.sha256(original.encode()).hexdigest(),
   'managed_helper_sha256':hashlib.sha256(modified.encode()).hexdigest(),'game_or_iphone_verified':False}
(out/'managed-bus-repeat.json').write_text(json.dumps(r,indent=2)+'\n')
print('MANAGED_BUS_REPEAT='+json.dumps(r),flush=True)
assert p.returncode==0 and r['wine_version_reported'] and not holders
PY
