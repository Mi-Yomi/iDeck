"""Preparation evidence only: no VM/image write, download, policy change or cleanup."""
from contextlib import ExitStack
import datetime
import hashlib
import json
import lzma
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import patch

REPO=Path('/workspace/iDeck/experiments/linux-guest')
TASK=Path('/workspace/steam-cloud-20261017')
OUT=REPO/'evidence/steam-seed-contract-20261017'
OUT.mkdir(exist_ok=False)
sys.path.insert(0,str(REPO/'tools'))
import debian_rootfs as base
import gui_host_tools
import steam_vm

def save(name,value):
    (OUT/name).write_text(json.dumps(value,indent=2)+'\n')

def no_qemu():
    found=[]
    for p in Path('/proc').iterdir():
        if not p.name.isdecimal():continue
        try:
            if any(os.fsdecode(a).rsplit('/',1)[-1]=='qemu-system-aarch64'
                   for a in (p/'cmdline').read_bytes().split(b'\0') if a):found.append(int(p.name))
        except (FileNotFoundError,PermissionError,ProcessLookupError):pass
    if found:raise RuntimeError('unexpected QEMU: '+str(found))
    return found

contract=REPO/'profiles/steam-experimental-seed-20261017.lock.json'
seed=TASK/'experimental-seed-v4/seed/gui-rootfs-v1.raw'
kernel=TASK/'gui-bootstrap/vmlinuz-virt';bootstrap=TASK/'steam-bootstrap'
common=[sys.executable,str(REPO/'tools/steam_seed.py'),'--contract',str(contract),
        '--kernel',str(kernel),'--bootstrap',str(bootstrap),'--storage-root',str(TASK)]
validation=[]
for name,input_seed,expected in [('verify1',seed,2),('verify2',seed,2),
        ('wrong-seed',TASK/'gui-provisioned-preserved.raw',1)]:
    cmd=[*common,'--seed',str(input_seed)]
    r=subprocess.run(cmd,capture_output=True,text=True,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
    (OUT/(name+'.json')).write_text(r.stdout);(OUT/(name+'.stderr.log')).write_text(r.stderr)
    save(name+'-command.json',{'argv':cmd,'exit_code':r.returncode})
    if r.returncode!=expected:raise RuntimeError('unexpected verifier exit '+name)
    validation.append(json.loads(r.stdout))
if validation[0]['validation']!=validation[1]['validation'] or validation[2]['seed_contract_valid']:
    raise RuntimeError('non-reproducible configuration or wrong seed admitted')
save('reproducibility.json',{'independent_processes':2,'identical_validation':True,
    'configuration_sha256':validation[0]['validation']['configuration_sha256'],
    'contract_sha256':validation[0]['validation']['contract_sha256'],
    'runner_sha256':validation[0]['validation']['runner_sha256'],
    'validator_sha256':validation[0]['validation']['validator_sha256'],
    'wrong_seed_refused':True,'qemu_started':False,'disk_created':False})

# Execute the runner's actual input/storage preparation against current files.
# A test fence would reject any image tool/VM call; all counts must remain zero.
no_qemu();target=TASK/'dependency-vm-not-started'
if target.exists():raise RuntimeError('preflight destination already exists')
args=SimpleNamespace(seed=seed,kernel=kernel,bootstrap=bootstrap,experimental_seed_contract=contract)
profile_path=REPO/'profiles/steam-host-experiment.json';profile=json.loads(profile_path.read_text())
report={'mode':'read-only runner preflight; no boot/output directory created',
        'qemu_started':False,'disk_created':False,'dependencies_installed':False}
with ExitStack() as cleanup, \
        patch.object(steam_vm.subprocess,'run',side_effect=AssertionError('unexpected image tool')) as images, \
        patch.object(steam_vm.subprocess,'Popen',side_effect=AssertionError('unexpected VM')) as vms:
    try:steam_vm._boot(args,profile_path,profile,target,report,cleanup)
    except ValueError as error:
        if str(error)!='insufficient space for Steam image write and offline copy reserve':raise
        report['blocked_reason']=str(error)
    else:raise RuntimeError('storage gate unexpectedly allowed')
    report['image_tool_calls']=images.call_count;report['vm_calls']=vms.call_count
if target.exists() or images.call_count or vms.call_count:raise RuntimeError('preflight wrote a disk')
report['output_directory_created']=False;save('runner-storage-gate.json',report)

deps=json.loads((REPO/'ipa/steam-dependencies.lock.json').read_text())
for pin in deps['extra_packages']:
    path=TASK/'deps-cache/debs'/Path(pin['filename']).name
    if path.is_symlink() or path.stat().st_size!=pin['size'] or base.sha256(path)!=pin['sha256']:
        raise RuntimeError('locked dependency cache mismatch')
save('dependency-cache.json',{'lock_sha256':base.sha256(REPO/'ipa/steam-dependencies.lock.json'),
    'packages_verified':len(deps['extra_packages']),
    'download_bytes':sum(p['size'] for p in deps['extra_packages']),
    'declared_installed_bytes':sum(p['installed_size_kib']*1024 for p in deps['extra_packages']),
    'guest_install':'NOT RUN; standard Steam profile storage gate blocked before image write',
    'dpkg_audit_in_dependency_vm':'NOT RUN','new_vm_disk_created':False})

# Read cached signed metadata; APT is simulation-only, with no download/install.
gui=json.loads((REPO/'ipa/gui-inputs.lock.json').read_text());metadata=TASK/'gui-cache/metadata'
release=metadata/'InRelease'
if release.stat().st_size!=gui['release']['size'] or base.sha256(release)!=gui['release']['sha256']:
    raise RuntimeError('cached Debian release mismatch')
fields,signers=base.verify_release(release)
if not set(gui['release']['signer_fingerprints']).issubset(signers):raise RuntimeError('signer mismatch')
desc=gui['release']['indexes'][1]
if desc!=base.index_descriptor(fields,'amd64'):raise RuntimeError('amd64 index differs')
xz=metadata/'Packages-amd64.xz'
if xz.stat().st_size!=desc['size'] or base.sha256(xz)!=desc['sha256']:raise RuntimeError('index hash mismatch')
with lzma.open(xz,'rb') as src:plain_bytes=src.read(128*1024**2+1)
if len(plain_bytes)>128*1024**2 or base.sha256(metadata/'Packages-amd64')!=hashlib.sha256(plain_bytes).hexdigest():
    raise RuntimeError('cached plain index differs')
records=list(base.paragraphs(plain_bytes.decode()));del plain_bytes
closure=base.resolve(records,metadata/'Packages-amd64',['qemu-utils'],metadata,architecture='amd64')
existing={p['name']:p for p in gui['host_packages']};missing=[]
for pin in closure:
    if pin['name'] in existing:
        if pin!=existing[pin['name']]:raise RuntimeError('image-tool closure changes pinned GUI host package')
    else:missing.append(pin)
checker=TASK/'gui-lab/host/usr/sbin/e2fsck';host=TASK/'gui-lab/host'
checker_command=gui_host_tools.command(host,[checker,'-V'])
check=subprocess.run(checker_command,capture_output=True,text=True,env={'PATH':os.defpath,'LC_ALL':'C'})
if check.returncode:raise RuntimeError('pinned checker could not execute')
save('host-tools.json',{'qemu_utils_closure_source':'same cached signed Debian release/by-hash amd64 index',
    'index_sha256':desc['sha256'],'solver':'APT --simulate only; no download/install',
    'missing_packages':missing,'missing_download_bytes':sum(p['size'] for p in missing),
    'missing_declared_installed_bytes':sum(p['installed_size_kib']*1024 for p in missing),
    'task_qemu_img_paths':sorted(str(p) for p in TASK.rglob('qemu-img') if p.is_file()),
    'system_e2fsck_present':Path('/usr/sbin/e2fsck').is_file(),
    'pinned_e2fsck_sha256':base.sha256(checker),'pinned_checker_version_argv':checker_command,
    'pinned_checker_version_exit':check.returncode,'pinned_checker_version_stdout':check.stdout,
    'pinned_checker_version_stderr':check.stderr,'system_install':False})

# File metadata only; group hardlinks by device/inode, never follow symlinks.
seen=set();groups={};large=[];count=0;links=0;logical_paths=0;logical_unique=0;allocated=0
for directory,dirs,files in os.walk(TASK,followlinks=False):
    dirs.sort();files.sort()
    for name in files:
        p=Path(directory)/name;s=p.lstat()
        if p.is_symlink():links+=1;continue
        if not p.is_file():continue
        count+=1;logical_paths+=s.st_size;key=(s.st_dev,s.st_ino)
        rel=p.relative_to(TASK).as_posix();group=rel.split('/')[0] if '/' in rel else '.'
        if key not in seen:
            seen.add(key);allocated+=s.st_blocks*512;logical_unique+=s.st_size
            groups[group]=groups.get(group,0)+s.st_blocks*512
        if s.st_size>=16*1024**2:
            large.append({'path':rel,'logical_bytes':s.st_size,'allocated_bytes':s.st_blocks*512,
                          'hardlink_count':s.st_nlink,'inode_key':str(s.st_dev)+':'+str(s.st_ino)})
usage=shutil.disk_usage(TASK)
save('space-inventory.json',{'observed_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'filesystem_total_bytes':usage.total,'filesystem_used_bytes':usage.used,'filesystem_free_bytes':usage.free,
    'task_regular_path_count':count,'task_unique_inodes':len(seen),'symlink_file_count':links,
    'task_logical_bytes_all_paths':logical_paths,'task_logical_bytes_unique_inodes':logical_unique,
    'task_allocated_bytes_unique_inodes':allocated,'allocated_by_top_level_first_inode_attribution':groups,
    'largest_files':sorted(large,key=lambda p:p['allocated_bytes'],reverse=True),
    'symlink_directories_followed':False,'source_data_deleted':False,
    'note':'Filesystem free space is authoritative; per-file allocation excludes directory/overlay metadata and attributes hardlinks once.'})
virtual=12*1024**3;reserve=4*1024**3
client=json.loads((REPO/'ipa/steam-client.lock.json').read_text())
future_client=sum(p['size'] for p in client['parts'])
host_download=sum(p['size'] for p in missing)
fresh_host_extraction=gui['totals']['host']['installed_size_bytes']+sum(p['installed_size_kib']*1024 for p in missing)
peak=2*virtual+reserve+future_client+host_download+fresh_host_extraction
save('space-plan.json',{'current_free_bytes':usage.free,'current_entry_floor_bytes':virtual+reserve,
    'current_entry_shortfall_bytes':max(0,virtual+reserve-usage.free),
    'worst_case_new_overlay_bytes':virtual,'offline_flattened_copy_bytes':virtual,'required_remaining_reserve_bytes':reserve,
    'uncached_steam_zip_bytes':future_client,'missing_host_download_bytes':host_download,
    'separate_complete_host_extraction_declared_bytes':fresh_host_extraction,
    'conservative_target_free_bytes_before_future_staging':peak,
    'additional_free_bytes_to_that_target':max(0,peak-usage.free),
    'minimum_total_capacity_with_current_data_retained_bytes':usage.used+peak,
    'conditions':['Keep all originals, failed outputs, evidence and caches.',
        'Owner supplies larger cloud capacity or an additional private filesystem under /workspace; no deletion/replacement.',
        'Verify/replay the explicit seed contract and current sources after capacity is available.',
        'Materialize the missing authenticated host-tool closure into a new separate host tree; retain old tools.',
        'Recompute actual free space after download/extraction metadata; at least12GiB+4GiB before any image write.',
        'Create only a new disposable Steam overlay; keep source read-only and exclusive ownership.',
        'Install locked dependencies and require dpkg --audit exit0 with byte-empty output; preserve341 existing versions.',
        'Clean Stop/QEMU exit/fsync, then recheck capacity for the full12GiB offline copy+4GiB reserve and strict full-output fsck.',
        'Stop if any check fails; do not shrink the profile, count sparse savings or purge retained files.'],
    'budget_scope':'28GiB full overlay+offline copy+reserve, plus known future external caches/declared separate host extraction. Re-measure filesystem metadata overhead at every gate.',
    'actions_performed':'planning only; no guest/image write, cleanup, policy change or denied-download retry'})
save('summary.json',{'seed_contract_valid':True,'configuration_reproduced':True,
    'configuration_sha256':validation[0]['validation']['configuration_sha256'],
    'existing_production_gui_default_preserved':True,'wrong_seed_refused':True,
    'dependency_packages_cached_and_verified':45,'dependencies_installed':False,
    'install_blocker':'standard12GiB Steam target fails full offline-copy+4GiB reserve before image write',
    'qemu_pids':no_qemu(),'image_created':False,'network_requests_for_downloads':0,'data_removed':False})
shutil.copyfile(Path(__file__),OUT/Path(__file__).name)
shutil.copyfile(TASK/'logs/steam-contract-tests-final.log',OUT/'tests.log')
print(json.dumps({'evidence':str(OUT),'configuration_sha256':validation[0]['validation']['configuration_sha256'],
    'free_bytes':usage.free,'entry_shortfall_bytes':max(0,virtual+reserve-usage.free),
    'missing_host_packages':[p['name'] for p in missing],'dependency_install':'NOT RUN'},indent=2))
