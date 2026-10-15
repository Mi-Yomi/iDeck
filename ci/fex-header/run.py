#!/usr/bin/env python3
"""Bounded manual FEX CONFIG_INC + data-only witness producer. Proposal, not dispatched."""
from __future__ import annotations
import hashlib, importlib.util, json, os, pathlib, platform, re, shlex, shutil, signal, stat, struct, subprocess, sys, time, zipfile
P=pathlib.Path
BUNDLE=P(__file__).resolve().parent
ROOT=BUNDLE.parents[1]
RUN=ROOT/'.work/fex-header-control-run'
OUT=ROOT/'.work/fex-header-control-artifacts'
MIB=1024*1024
AGGREGATE=240
WORKER=215
PINS={
 'CONTRACT.json':'0ee501c31baddde07e3a419c6819391648c0f3a738739a372b398cdd0f1e0ef7',
 'LAYOUT_FIELDS.json':'cbd8382d259eae8e6bff781aed333d7ee28930267b7d782e454d8d418b5610c3',
 'layout_witness.mm':'d205d61cb5cf9a05753e41764070101b4e7000a02103f686caf35244ab930b59',
 'verify_witness.py':'4db637e73e31cc83c5a95b4fe58886b86d0ca4088ee0fc15ff240a8b1324b7e3',
 'portable-contract.json':'658b8d0f6f2e99837eba5f85bd425427377c2351c991b8e28083fa1ed35cc33c',
}
class Failure(ValueError):pass
def need(ok,message):
 if not ok:raise Failure(message)
def safe(p,*,fresh=False,directory=False,cap=8*MIB):
 p=P(p).absolute();need(p.resolve(strict=False)==p and not any(x.is_symlink()for x in [p,*p.parents]),'Noncanonical or symlink path: '+str(p))
 if fresh:need(not p.exists(),'Fresh path required: '+str(p))
 elif directory:need(p.is_dir(),'Missing directory: '+str(p))
 else:
  s=p.stat();need(stat.S_ISREG(s.st_mode)and s.st_nlink==1 and s.st_size<=cap,'Unsafe/oversized file: '+str(p))
 return p
def digest(p):return hashlib.sha256(safe(p).read_bytes()).hexdigest()
def unique(pairs):
 d={}
 for k,v in pairs:need(k not in d,'Duplicate JSON key');d[k]=v
 return d
def read(p):return json.loads(safe(p).read_text(),object_pairs_hook=unique)
def write(p,x):
 p=P(p);p.parent.mkdir(parents=True,exist_ok=True);safe(p,fresh=True).write_text(json.dumps(x,indent=2,sort_keys=True)+'\n')
def reviewed(bundle=BUNDLE,environ=None):
 env=os.environ if environ is None else environ
 expected=env.get('EXPECTED_FEX_HEADER_WRAPPER_SHA256','')
 need(re.fullmatch('[0-9a-f]{64}',expected)and digest(bundle/'run.py')==expected,'Exact reviewed wrapper hash required')
 for n,h in PINS.items():need(digest(bundle/n)==h,'Frozen input drift: '+n)
 c=read(bundle/'CONTRACT.json');p=read(bundle/'portable-contract.json')
 need(p['reference_contract_sha256']==PINS['CONTRACT.json'],'Wrong portable original contract')
 need(c['fex_pin']==p['reference_source_pin']=='f59cab95659e8add0c88f0c76ec1cf483c536dbf','Wrong FEX source pin')
 need(c['permitted_build_targets']==['CONFIG_INC'],'Only CONFIG_INC allowed')
 need(p['time_budget_seconds']=={'aggregate':240,'worker':215,'finalization_reserve':25},'Wrong bounded budget')
 return c,p

def clean_env(run=RUN):
 # Keep no account tokens, SSH agent, compiler flags, caches, Git credentials or user config.
 return {'PATH':str(P(sys.executable).resolve().parent)+':/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin',
 'HOME':str(run/'home'),'TMPDIR':str(run/'tmp'),'LC_ALL':'C','LANG':'C','TZ':'UTC',
 'DEVELOPER_DIR':'/Applications/Xcode-26.6.app/Contents/Developer','GIT_TERMINAL_PROMPT':'0',
 'GIT_CONFIG_NOSYSTEM':'1','GIT_CONFIG_GLOBAL':'/dev/null','GIT_LFS_SKIP_SMUDGE':'1',
 'PYTHONNOUSERSITE':'1','PYTHONDONTWRITEBYTECODE':'1'}
class Commands:
 def __init__(self,deadline,run=RUN):self.deadline=deadline;self.run=run;self.env=clean_env(run);self.records=[];self.log_total=0
 def run_command(self,name,args,cwd=None,cap=4*MIB):
  need(re.fullmatch('[a-z0-9-]+',name),'Unsafe log name');need(time.monotonic()<self.deadline,'Aggregate worker deadline expired')
  need(len(self.records)<96,'Command count cap')
  path=safe(self.run/'logs'/(name+'.log'),fresh=True);path.parent.mkdir(parents=True,exist_ok=True)
  start=time.monotonic()
  with path.open('wb')as log:
   proc=subprocess.Popen([str(a)for a in args],cwd=cwd or self.run,env=self.env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
   # Direct children inherit the outer worker's started process group.
   # Supervisor kills remaining members of that group on all exit paths.
   # A descendant that creates a separate session is outside killpg's reach.
   while proc.poll()is None:
    if time.monotonic()>=self.deadline or path.stat().st_size>cap or self.log_total+path.stat().st_size>16*MIB:
     proc.kill();proc.wait();raise Failure('Command budget/log cap: '+name)
    time.sleep(.05)
   rc=proc.returncode
  self.log_total+=path.stat().st_size
  self.records.append({'name':name,'argv':[str(a)for a in args],'cwd':str(cwd or self.run),'returncode':rc,'seconds':round(time.monotonic()-start,3),'log_bytes':path.stat().st_size,'log_sha256':digest(path)})
  need(path.stat().st_size<=cap and self.log_total<=16*MIB and rc==0,'Command failed/log cap: '+name)
  return path.read_text(errors='replace').strip()

def rebase(argv,fex,sdk,make=None):
 return [a.replace('@FEX@',str(fex)).replace('@SDK@',str(sdk)).replace('@MAKE@',str(make))for a in argv]
def cache_dict(text):
 return {m[1]:m[3]for line in text.splitlines()if(m:=re.fullmatch(r'([^/#][^:]*):([^=]+)=(.*)',line))}
def verify_features(cache,contract,sdk):
 for k,v in contract['cache_inputs'].items():
  expected=str(sdk)if k=='CMAKE_OSX_SYSROOT'else v['value']
  need(cache.get(k)==expected,'Original configure cache drift: '+k)
 need(cache.get('ENABLE_GUEST_WINDOW')=='OFF','GuestWindow must remain off')
 need(cache.get('_Python_INTERPRETER_PROPERTIES','').split(';')[1:4]==['3','13','14'],'CMake-discovered Python drift')
 need('FEX_IOS_HOST_BUILD'not in cache,'Unexpected iOS-host mode')

def checkout(cmd,path,url,commit,name):
 need(url.startswith('https://github.com/')and re.fullmatch('[0-9a-f]{40}',commit),'Invalid immutable source')
 if path.exists():need(path.is_dir()and not any(path.iterdir()),'Source checkout must be empty')
 else:path.mkdir(parents=True)
 prefix=['/usr/bin/git','-c','core.hooksPath=/dev/null','-c','protocol.file.allow=never','-c','filter.lfs.required=false','-c','filter.lfs.smudge=','-c','submodule.recurse=false','-C',str(path)]
 cmd.run_command(name+'-init',prefix+['init'])
 cmd.run_command(name+'-fetch',prefix+['fetch','--depth=1','--no-tags',url,commit])
 cmd.run_command(name+'-checkout',prefix+['checkout','--detach','FETCH_HEAD'])
 need(cmd.run_command(name+'-head',prefix+['rev-parse','HEAD'])==commit,'Source pin mismatch')
 need(cmd.run_command(name+'-clean',prefix+['status','--porcelain','--untracked-files=no'])=='','Tracked source drift')

def final_sources_clean(cmd,fex,portable):
 sources=[('root',fex,portable['reference_source_pin'])]+[('external-'+str(i),fex/e['path'],e['commit'])for i,e in enumerate(portable['external_sources'])]
 for name,path,pin in sources:
  prefix=['/usr/bin/git','-C',str(path)]
  need(cmd.run_command('final-'+name+'-head',prefix+['rev-parse','HEAD'])==pin,'Final source HEAD drift: '+name)
  # Explicitly inspect every nested repository, independently of the root's
  # submodule-ignore policy. diff HEAD includes staged and unstaged changes.
  cmd.run_command('final-'+name+'-diff',prefix+['diff','--exit-code','HEAD','--'])

def compile_argv(original,witness,obj,dep):
 args=list(original);need(args.count('-c')==1 and args.count('-o')==1,'Unexpected original compile shape')
 need(args[0]=='/usr/bin/c++','Unexpected compiler driver')
 args[args.index('-c')+1]=str(witness);args[args.index('-o')+1]=str(obj)
 args[1:1]=['-x','c++','-Werror=invalid-offsetof','-MD','-MF',str(dep)]
 return args

def macro_argv(args,output):
 args=list(args);i=args.index('-MD');del args[i];i=args.index('-MF');del args[i:i+2]
 args[args.index('-c')]='-E';args.insert(1,'-dM');args[args.index('-o')+1]=str(output)
 return args

def copy_checked(src,dst):
 safe(src);safe(dst,fresh=True);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst);need(digest(src)==digest(dst),'Copy hash mismatch')
def load_verifier():
 need(digest(BUNDLE/'verify_witness.py')==PINS['verify_witness.py'],'Verifier drift')
 spec=importlib.util.spec_from_file_location('fex_header_data_verifier',BUNDLE/'verify_witness.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def probe_metadata(build,deadline):
 """Read-only census of configure intermediates. Never export their bytes."""
 rows=[];seen=0
 for f in (build/'CMakeFiles').rglob('*'):
  need(time.monotonic()<deadline,'Probe census deadline');seen+=1;need(seen<=4096,'Probe census file-count cap')
  if not f.is_file()or f.is_symlink():continue
  with f.open('rb')as inp:head=inp.read(32)
  if len(head)!=32 or head[:4]!=b'\xcf\xfa\xed\xfe':continue
  b=safe(f,cap=4*MIB).read_bytes();_,cpu,sub,kind,ncmds,nbytes,flags,reserved=struct.unpack_from('<8I',b)
  need(ncmds<=128 and 32+nbytes<=len(b),'Malformed configure Mach-O');pos=32;commands=[]
  for _ in range(ncmds):
   need(pos+8<=32+nbytes,'Malformed configure load command');command,size=struct.unpack_from('<II',b,pos)
   need(size>=8 and pos+size<=32+nbytes,'Malformed configure load size');commands.append(command);pos+=size
  need(pos==32+nbytes,'Trailing configure load bytes')
  rows.append({'path':f.relative_to(build).as_posix(),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'filetype':kind,'cpu':cpu,'load_commands':commands,'code_signature_command':0x1d in commands,'exported':False})
 return rows

def worker(deadline):
 c,p=reviewed();cmd=Commands(deadline);package=RUN/'package';package.mkdir();(RUN/'logs').mkdir(exist_ok=True)
 result={'status':'failed','reusable':False,'target_execution':False,'archive_rebuild':False,'app_or_witness_link':False}
 try:
  need(platform.system()=='Darwin'and platform.machine()=='arm64','Original Apple arm64 host required')
  need(sys.version_info[:3]==(3,12,7),'Original bare Python3.12.7 required; no installation fallback')
  need(cmd.run_command('xcode-version',['/usr/bin/xcodebuild','-version'])=='Xcode 26.6\nBuild version 17F113','Wrong original Xcode')
  need(cmd.run_command('sdk-version',['/usr/bin/xcrun','--sdk','iphoneos','--show-sdk-version'])=='26.5','Wrong SDK')
  sdk=P(cmd.run_command('sdk-path',['/usr/bin/xcrun','--sdk','iphoneos','--show-sdk-path'])).resolve();safe(sdk,directory=True)
  make=cmd.run_command('make-path',['/usr/bin/xcrun','--find','make']);need(cmd.run_command('make-version',[make,'--version']).splitlines()[0]=='GNU Make 3.81','Wrong make')
  need(cmd.run_command('cmake-version',['cmake','--version']).splitlines()[0]=='cmake version 4.3.4','Wrong CMake')
  clang=cmd.run_command('compiler-version',['/usr/bin/c++','--version']);need(clang.splitlines()[0]=='Apple clang version 21.0.0 (clang-2100.1.1.101)','Wrong original compiler')
  need(cmd.run_command('bare-python',['python3','--version'])=='Python 3.12.7','Generator python3 resolution differs')
  fex=RUN/'source/FEX';checkout(cmd,fex,p['source_url'],p['reference_source_pin'],'fex')
  for i,e in enumerate(p['external_sources']):
   line=cmd.run_command('external-gitlink-'+str(i),['/usr/bin/git','-C',str(fex),'ls-tree','HEAD',e['path']])
   need(line==f'160000 commit {e["commit"]}\t{e["path"]}','External gitlink drift')
   checkout(cmd,fex/e['path'],e['url'],e['commit'],'external-'+str(i))
  for row in c['source_inputs']+c['source_header_closure']+c['licenses']['required_fex_notices']:
   need(digest(fex/row['path'])==row['sha256'],'Pinned source/header drift: '+row['path'])
  build=fex/'build-ios';safe(build,fresh=True)
  cmd.run_command('configure',rebase(p['configure_argv'],fex,sdk,make),cwd=RUN)
  cache=cache_dict(safe(build/'CMakeCache.txt').read_text());verify_features(cache,c,sdk)
  commands=read(build/'compile_commands.json');selected=[x for x in commands if x['file'].endswith('/Interface/Context/Context.cpp')];need(len(selected)==1,'Missing unique original Context compile contract')
  original=rebase(p['original_context_argv'],fex,sdk,make)
  need(shlex.split(selected[0]['command'])==original,'Effective original Context compile argv drift')
  need(selected[0]['directory']==rebase([p['original_context_directory']],fex,sdk)[0],'Original Context directory drift')
  cmd.run_command('config-inc',['cmake','--build',str(build),'--target','CONFIG_INC','--parallel','1'])
  configured=build/'generated/Config/Config.json';need(digest(configured)==c['config_contract']['configured_json_expected_sha256'],'Configured JSON substitution drift')
  forbidden={P(x['member']).name for x in c['reference_producer']['archive_inputs']}
  need(not any(f.name in forbidden for f in build.rglob('*.a')),'Selected library archive build forbidden')
  configure_probes=probe_metadata(build,deadline)
  witness=RUN/'producer-layout.o';dep=RUN/'producer-layout.d';macros=RUN/'producer-macros.txt'
  args=compile_argv(original,BUNDLE/'layout_witness.mm',witness,dep)
  cmd.run_command('compile-witness',args,cwd=selected[0]['directory'])
  # Capture complete raw load commands before strict data-only verification.
  cmd.run_command('witness-raw-load-commands',['/usr/bin/xcrun','otool','-l',str(witness)])
  cmd.run_command('witness-raw-symbols',['/usr/bin/xcrun','nm','-m',str(witness)])
  cmd.run_command('preprocess-witness',macro_argv(args,macros),cwd=selected[0]['directory'])
  definitions={m[1]:m[2]or''for line in safe(macros).read_text().splitlines()if(m:=re.fullmatch(r'#define (\w+)(?: (.*))?',line))}
  need(definitions.get('ARCHITECTURE_arm64')=='1'and definitions.get('NDEBUG')=='1','Native public macro contract absent')
  need(all(k not in definitions for k in c['consumer_contract']['required_absent']),'Forbidden public feature macro')
  need(all(k in definitions for k in ['__APPLE__','__aarch64__'])and '__OBJC__'not in definitions,'Producer must use actual C++ Apple arm64 builtins')
  verifier=load_verifier();data=verifier.verify_producer(verifier.inspect_object(safe(witness,cap=4*MIB).read_bytes(),read(BUNDLE/'LAYOUT_FIELDS.json')))
  for row in c['config_contract']['generated_header_outputs']:copy_checked(build/row['path'],package/row['path'])
  for src,dst in [(configured,'configuration/Config.json'),(build/'CMakeCache.txt','configuration/CMakeCache.txt'),(build/'compile_commands.json','configuration/compile_commands.json'),(witness,'witness/producer-layout.o'),(dep,'witness/producer-layout.d'),(macros,'witness/producer-macros.txt')]:copy_checked(src,package/dst)
  for name in PINS:copy_checked(BUNDLE/name,package/'contract'/name)
  for name in p['notices']:copy_checked(fex/name,package/'notices/FEX'/name)
  for e in p['external_sources']:copy_checked(fex/e['path']/e['notice'],package/'notices'/e['path']/e['notice'])
  for name in ['CMakeLists.txt','FEXCore/Source/CMakeLists.txt','FEXCore/Scripts/config_generator.py','FEXCore/Source/Interface/Config/Config.json.in']:copy_checked(fex/name,package/'generation-source'/name)
  write(package/'witness/producer-layout.json',data)
  write(package/'evidence/configure-probe-metadata.json',{'intermediates':configure_probes,'target_execution':False,'exported':False,'all_intermediates_unsigned_claimed':False,'scope':'Original CMake compiler compile/link probes only; their possible linker-added signatures are separate from exported witness validation.'})
  write(package/'provenance.json',{'schema':1,'fex_pin':p['reference_source_pin'],'fex_url':p['source_url'],'external_sources':p['external_sources'],'source_input_hashes':c['source_inputs'],'source_header_hashes':c['source_header_closure'],'reference_archive_hashes':c['reference_producer']['archive_inputs'],'language':'C++ (forced -x c++)','sdk':str(sdk),'compiler_version':clang,'python_version':platform.python_version(),'consumer_equality_established':False,'note':'Reconstructed original-configuration compiler witness, not historical archive layout extraction. Actual Objective-C++ Xcode27 FEXBridge witness remains required.'})
  final_sources_clean(cmd,fex,p)
  need(time.monotonic()<deadline,'Worker deadline expired before success')
  result.update(status='verified-header-supplement-producer',reusable=True,header_sha256={row['path']:digest(package/row['path'])for row in c['config_contract']['generated_header_outputs']},layout_data_sha256=data['data_sha256'])
 except BaseException as e:result['error']=type(e).__name__+': '+str(e)
 finally:
  write(RUN/'commands.json',cmd.records);write(RUN/'worker-result.json',result)
 return 0 if result['reusable']else 1

def pack_success(package,output,deadline,caps):
 safe(package,directory=True);safe(output,fresh=True);files=sorted(x for x in package.rglob('*')if x.is_file()or x.is_symlink())
 need(len(files)+1<=caps['file_count'],'Artifact file count cap');total=0;rows=[]
 for f in files:
  need(time.monotonic()<deadline,'Finalization deadline');safe(f,cap=caps['file_bytes']);total+=f.stat().st_size;need(total<=caps['total_bytes'],'Artifact total size cap')
  rows.append({'path':f.relative_to(package).as_posix(),'bytes':f.stat().st_size,'sha256':digest(f)})
 write(package/'artifact-manifest.json',{'schema':1,'status':'verified-header-supplement-producer','reusable':True,'files':rows,'target_execution':False,'archive_rebuild':False,'consumer_equality_established':False})
 need(total+(package/'artifact-manifest.json').stat().st_size<=caps['total_bytes'],'Manifest-inclusive artifact cap')
 with zipfile.ZipFile(output,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6)as z:
  for f in files+[package/'artifact-manifest.json']:
   need(time.monotonic()<deadline,'Finalization deadline');safe(f)
   with f.open('rb')as inp,z.open(f.relative_to(package).as_posix(),'w')as dst:
    while block:=inp.read(65536):need(time.monotonic()<deadline,'Finalization deadline');dst.write(block)
   need(output.stat().st_size<=caps['zip_bytes'],'ZIP size cap')
 need(output.stat().st_size<=caps['zip_bytes']and time.monotonic()<deadline,'ZIP size/deadline cap')
 return {'bytes':output.stat().st_size,'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'manifest_sha256':digest(package/'artifact-manifest.json')}

def supervise():
 start=time.monotonic();deadline=start+AGGREGATE;c,p=reviewed()
 need(os.environ.get('FREE_QUOTA_VERIFIED')=='true'and os.environ.get('PRIVATE_SOURCE_VERIFIED')=='true','Existing approved private source/free quota gates required')
 need(platform.system()=='Darwin'and platform.machine()=='arm64','Only original Apple arm64 executor')
 safe(ROOT,directory=True);safe(RUN,fresh=True);safe(OUT,fresh=True);RUN.mkdir(parents=True);OUT.mkdir(parents=True)
 for d in ['home','tmp','logs']:(RUN/d).mkdir()
 log=OUT/'worker.log';proc=None;status={'status':'failed','reusable':False,'target_execution':False,'archive_rebuild':False};pending=OUT/'headers-and-witness.pending.zip';final=OUT/'headers-and-witness.zip'
 try:
  env=clean_env();env['EXPECTED_FEX_HEADER_WRAPPER_SHA256']=os.environ['EXPECTED_FEX_HEADER_WRAPPER_SHA256'];env['FEX_HEADER_WORKER_DEADLINE']=str(start+WORKER)
  with log.open('wb')as stream:
   proc=subprocess.Popen([sys.executable,'-I',str(BUNDLE/'run.py'),'--worker'],cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
   while proc.poll()is None:
    need(time.monotonic()<start+WORKER and log.stat().st_size<=2*MIB,'Worker deadline/log cap');time.sleep(.05)
   need(proc.returncode==0,'Worker failed; inspect diagnostic logs')
  # Kill remaining members of the started process group before packaging.
  try:os.killpg(proc.pid,signal.SIGKILL)
  except ProcessLookupError:pass
  result=read(RUN/'worker-result.json');need(result.get('reusable')is True,'Worker did not validate reusable headers')
  copy_checked(RUN/'commands.json',RUN/'package/evidence/commands.json');copy_checked(RUN/'worker-result.json',RUN/'package/evidence/worker-result.json')
  for f in sorted((RUN/'logs').glob('*.log')):copy_checked(f,RUN/'package/evidence/logs'/f.name)
  info=pack_success(RUN/'package',pending,deadline,p['artifact_caps'])
  need(time.monotonic()<deadline,'Aggregate deadline before publication');pending.replace(final);status.update(status='verified-header-supplement-producer',reusable=True,artifact=info)
 except BaseException as e:status['error']=type(e).__name__+': '+str(e)
 finally:
  if proc:
   try:os.killpg(proc.pid,signal.SIGKILL)
   except ProcessLookupError:pass
   try:proc.wait(timeout=max(.01,min(2,deadline-time.monotonic())))
   except subprocess.TimeoutExpired:pass
  if not status['reusable']:
   for f in [pending,final]:
    if f.exists():f.unlink()
   # Failure publishes diagnostics only. Never copy partially generated headers,
   # a data object or a success archive from the run directory.
   diagnostic_bytes=0
   for src in [RUN/'commands.json',RUN/'worker-result.json',*sorted((RUN/'logs').glob('*.log'))]:
    if time.monotonic()>=deadline:break
    if src.is_file()and src.stat().st_size<=4*MIB and diagnostic_bytes+src.stat().st_size<=16*MIB:
     copy_checked(src,OUT/'diagnostics'/src.name);diagnostic_bytes+=src.stat().st_size
  status['elapsed_seconds']=round(time.monotonic()-start,3);write(OUT/'result.json',status)
 return 0 if status['reusable']else 1

if __name__=='__main__':
 sys.dont_write_bytecode=True
 if sys.argv[1:]==['--worker']:
  need(os.environ.get('FEX_HEADER_WORKER_DEADLINE')is not None,'Worker is supervisor-only');deadline=float(os.environ['FEX_HEADER_WORKER_DEADLINE']);need(time.monotonic()<deadline<=time.monotonic()+WORKER,'Invalid bounded worker deadline');sys.exit(worker(deadline))
 need(len(sys.argv)==1,'No public arguments');sys.exit(supervise())
