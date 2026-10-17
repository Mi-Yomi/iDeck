"""Save bounded text/screenshots; never publish disks, client or package bytes."""
import datetime,fcntl,hashlib,json,os,shutil,subprocess,sys
from pathlib import Path
REPO=Path('/workspace/iDeck')
ROOT=REPO/'experiments/linux-guest'
TASK=Path('/workspace/steam-fresh-20261017')
OUT=ROOT/'evidence/steam-fresh-network-20261017'
OUT.mkdir(exist_ok=False)
sys.path.insert(0,str(ROOT/'tools'))
import steam_vm
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(name,value):
 p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value,indent=2)+'\n')
def copy(source,dest):
 p=OUT/dest;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,p)

branch=subprocess.check_output(['git','branch','--show-current'],cwd=REPO,text=True).strip()
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()
remote=subprocess.check_output(['git','ls-remote','--heads','origin','codex/steam-arm64-experiment-20261017'],cwd=REPO,text=True).split()[0]
assert branch=='codex/steam-arm64-experiment-20261017'
assert head==remote=='bfcb3a8bb2a719240daf04ed9023d8a425444e7a'
qemu=[]
for p in Path('/proc').iterdir():
 if not p.name.isdecimal():continue
 try:
  if str(TASK/'host/usr/bin/qemu-system-aarch64').encode() in (p/'cmdline').read_bytes().split(b'\0'):qemu.append(int(p.name))
 except OSError:pass
assert not qemu
mounts=[s for s in Path('/proc/self/mountinfo').read_text().splitlines() if str(TASK) in s]
assert not mounts
runs={}
for name in ('run1','run2'):
 r=json.loads((TASK/name/'result.json').read_text())
 assert r['clean_shutdown'] is True and r['qemu_exit_code']==0 and not r.get('forced')
 assert not (TASK/name/'needs-recovery').exists()
 with (TASK/name/'owner.lock').open('rb') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
 runs[name]={'status':r['status'],'clean_shutdown':True,'qemu_exit_code':0,
  'disk_sha256':sha(TASK/name/'steam-experiment.qcow2'),'owner_lock_free':True,
  'dirty_marker_present':False,'seed_read_only_qmp':r['seed_read_only_qmp']}
 for p in (TASK/name).iterdir():
  if p.suffix in ('.json','.log','.png','.py'):
   assert p.stat().st_size<4*1024**2
   copy(p,Path(name)/p.name)
assert runs['run1']['disk_sha256']==json.loads((TASK/'run2/result.json').read_text())['continuation']['source_sha256']
fscks={}
for source in (TASK/'run2',TASK/'post-run2-fsck'):
 r=json.loads((source/'offline-fsck.json').read_text())
 assert r['raw_size']==12*1024**3 and r['read_only'] and not r['writer_running']
 assert r['evaluation']==steam_vm.evaluate_offline_fsck(r['exit_code'],
  (source/'offline-fsck.stdout.log').read_text(),(source/'offline-fsck.stderr.log').read_text(),
  Path(r['fsck_command'][-1]))
 assert r['evaluation']['accepted']
 for n in ('offline-fsck.json','offline-fsck.log','offline-fsck.stdout.log','offline-fsck.stderr.log'):
  copy(source/n,source.name+'/'+n)
 fscks[source.name]=r['raw_sha256']
lock=json.loads((ROOT/'ipa/gui.lock.json').read_text())
for name,expected in lock['files'].items():
 p=TASK/'gui'/name
 assert p.stat().st_size==expected['size'] and sha(p)==expected['sha256']
client=json.loads((ROOT/'ipa/steam-client.lock.json').read_text());verified=[]
for pin in client['parts']:
 p=TASK/'client-cache'/pin['file'];assert p.stat().st_size==pin['size'] and sha(p)==pin['sha256']
 verified.append({k:pin[k] for k in ('file','size','sha256')})
save('client-cache.json',{'count':len(verified),'download_bytes':sum(p['size'] for p in verified),'parts':verified,'client_bytes_in_git':False})
for p in (TASK/'probes').iterdir():
 if p.suffix in ('.json','.log'):
  assert p.stat().st_size<1024**2;copy(p,'preparation/'+p.name)
for p in (TASK/'run1-evidence').iterdir():copy(p,'first-attempt/'+p.name)
for directory in ('commands','commands2'):
 for p in (TASK/directory).iterdir():copy(p,directory+'/'+p.name)
for name in ('prepare_inputs.py','finalize_tools.py','observe_first_attempt.py','finalize_evidence.py','preparation.log'):
 copy(TASK/name,'sources/'+name)
copy(TASK/'bootstrap/bootstrap.json','bootstrap.json')
rows=[json.loads(x) for x in (TASK/'run1-evidence/timeline.jsonl').read_text().splitlines()]
first=json.loads((TASK/'run1-evidence/first-attempt-result.json').read_text())
install=json.loads((TASK/'run1-evidence/install-result.json').read_text())
assert install['verified_debs']==45 and install['dpkg_exit_code']==0 and install['dpkg_audit_empty']
assert install['unchanged_existing_packages']==341 and install['retained_verified_client_cache_parts']==17
assert first['first_browser'] is None and first['processes']==[] and first['shm_deleted'] is False
usage=shutil.disk_usage(TASK)
summary={'observed_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'source_commit':head,'remote_source_verified':remote,'branch':branch,
 'owner_reported_network_config_version':'71a66f3c-3170-475c-82f6-cf3dc0ded790~cecfgver_6ad378804dc88199be22c7b77b1cebb4',
 'network_config_version_independently_introspected':False,
 'repo_or_ancestor_AGENTS_found':False,'repo_agents_skills_found':False,
 'old_private_seed_or_caches_transferred':False,'production_release_verified':True,
 'production_seed_sha256':lock['files']['gui-rootfs-v1.raw']['sha256'],
 'experimental_seed_contract_selected':False,'client_zip_count':17,
 'guest_install':install,'runs':runs,'full_offline_fsck_raw_hashes':fscks,
 'first_attempt':first,'timeline_samples':len(rows),'min_shm_free_bytes':min(r['shm_free'] for r in rows),
 'max_shm_objects':max(len(r['shm']) for r in rows),
 'updater_origin_http_status':None,'updater_host_proxy_connect_http_status':403,
 'guest_dns':{'nameserver':'10.0.2.3','hosts':['client-update.steamstatic.com','client-update.fastly.steamstatic.com'],
              'result':'EAI_AGAIN','errno':-3},
 'network_diagnosis_scope':'host CONNECT refusal and guest DNS failure; no successful guest updater HTTPS request',
 'first_historical_webhelper_timeout_cause':'UNRESOLVED; not reached in this independent cloud attempt',
 'steam_main_ui':'NOT REACHED','big_picture':'NOT REACHED','steam_ui_input_and_relaunch':'NOT RUN',
 'clean_application_stop':'NOT RUN; updater failed and exited before CEF',
 'trace_steam_ipc':'NOT RUN; no browser target','aarch64_ipc_stack':'NOT RUN; no browser target',
 'apple_runtime':'NOT RUN','steam_on_iphone':'NOT RUN','gpu_acceleration':'NOT RUN',
 'qemu_pids':qemu,'task_mounts':mounts,'free_bytes':usage.free,'filesystem_total_bytes':usage.total,
 'originals_and_failed_outputs_retained':True,'sentinel_or_runtime_cache_deleted':False,
 'installer_cache_retained':True,'shm_cleanup_performed':False,
 'network_or_security_policy_changed':False,'proxy_or_dns_configuration_changed':False,
 'runtime_flags_cpu_ram_timeouts_changed':False,'system_packages_installed':False,
 'tokens_created':False,'login_or_agreements_or_games':False,'subagents_created':False,
 'ci_dispatched':False,'release_or_gui_payload_changed':False,'client_or_disk_published':False,
 'offline_tests':{'passed':149,'log_sha256':sha(TASK/'probes/steam-tests.log')}}
save('summary.json',summary)
save('manifest.json',{'schema':1,'scope':'fresh cloud downloads, actual install, network blocker, persistence and strict fsck; no Steam UI acceptance',
 'files':[{'path':p.relative_to(OUT).as_posix(),'size':p.stat().st_size,'sha256':sha(p)} for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='manifest.json']})
print(json.dumps({'evidence':str(OUT),'files':len(json.loads((OUT/'manifest.json').read_text())['files']),
 'vm_clean_stops':len(runs),'strict_fsck_passes':len(fscks),'remaining_blocker':'updater host CONNECT403 and guest DNS EAI_AGAIN'},indent=2))
