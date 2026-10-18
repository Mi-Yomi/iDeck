from pathlib import Path
import os,json,hashlib,subprocess,base64,gzip,time
out=Path('/home/ideck/steam-experiment-logs/game-run30')
baseline=set(json.loads((out/'baseline-namespaces.json').read_text()))
holders=[];fixtures=[];steam=[]
for p in Path('/proc').iterdir():
 if not p.name.isdecimal():continue
 try:
  exe=os.readlink(p/'exe');args=p.joinpath('cmdline').read_text(errors='replace')
  if os.readlink(p/'ns/mnt') not in baseline:holders.append(int(p.name))
  if any(s in args for s in ('/run/ideck/game-guardian30.py','/run/ideck/game-namespace30.py')) or 'GE-Proton11-9-aarch64' in exe:fixtures.append(int(p.name))
  if exe.endswith(('/steamrtarm64/steam','/steamrtarm64/steamwebhelper')):steam.append(int(p.name))
 except (FileNotFoundError,ProcessLookupError):pass
before=json.loads(Path('/home/ideck/steam-experiment-logs/resume-local-20261017-preflight/result.json').read_text())
client={}
for relative,expected in before['client'].items():
 with (Path('/home/ideck/.local/share/Steam')/relative).open('rb') as f:sha=hashlib.file_digest(f,'sha256').hexdigest()
 client[relative]={'sha256':sha,'unchanged':sha==expected['sha256']}
controls={}
for filename,key in (('/etc/machine-id','machine_id_sha256'),('/home/ideck/Documents/ideck-steam-continuation-20261017.txt','document_sha256')):
 with Path(filename).open('rb') as file:sha=hashlib.file_digest(file,'sha256').hexdigest()
 controls[key]={'sha256':sha,'unchanged':sha==before[key]}
production={}
for filename,expected in (('/opt/ideck-steam/namespace-check.py','96c929eafefb2f76aa7751fb1869baa6def54e5e31be2a0e6620a486bca64b0d'),('/usr/local/bin/ideck-steam','11cc1c70d2960a745b0f2c31a989eedc3ed23a1f6a95d5be7e6094cd25a7f790')):
 with Path(filename).open('rb') as file:sha=hashlib.file_digest(file,'sha256').hexdigest()
 production[filename]={'sha256':sha,'unchanged':sha==expected}
audit=subprocess.run(['dpkg','--audit'],capture_output=True)
r={'private_namespace_holders':holders,'fixture_processes':fixtures,'steam_processes':steam,'client':client,'persistence_controls':controls,'production_sources':production,
 'audit_exit':audit.returncode,'audit_stdout_bytes':len(audit.stdout),'audit_stderr_bytes':len(audit.stderr)}
r['ready_for_original_vm_stop']=not holders and not fixtures and not steam and all(v['unchanged'] for v in client.values()) and all(v['unchanged'] for v in controls.values()) and all(v['unchanged'] for v in production.values()) and audit.returncode==0 and not audit.stdout and not audit.stderr
(out/'final-postcheck.json').write_text(json.dumps(r,indent=2)+'\n')
for case in ('arm64','arm64-nosync','arm64-repeat','arm64-long-nosync','x64-long-nosync','x64','x64-repeat'):
 p=Path('/opt/ideck-tools-probe29/variables')/('game30-'+case)/'proton-logs/steam-0.log'
 if p.is_file() and not p.is_symlink():
  with p.open('rb') as f:f.seek(max(0,p.stat().st_size-32768));data=f.read(32768)
  (out/(case+'-proton-tail.log')).write_bytes(data)
for p in sorted(out.rglob('*')):
 if p.is_file() and not p.is_symlink():
  b=p.read_bytes()
  if len(b)>16*1024**2:
   print('PRIVATE_LARGE_LOG_RETAINED='+json.dumps({'file':str(p.relative_to(out)),'size':len(b),'sha256':hashlib.sha256(b).hexdigest()}),flush=True)
   continue
  print('IDECK_BLOB=game-run30__'+str(p.relative_to(out)).replace('/','__')+':'+base64.b64encode(gzip.compress(b)).decode(),flush=True)
print('GAME_FINAL_AUDIT='+json.dumps(r),flush=True)
