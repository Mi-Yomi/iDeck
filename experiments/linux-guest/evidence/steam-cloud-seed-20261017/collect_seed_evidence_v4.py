"""Collect small acceptance evidence; keep every disk/client input private."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

ROOT=Path('/workspace/iDeck/experiments/linux-guest')
TASK=Path('/workspace/steam-cloud-20261017')
OUT=ROOT/'evidence/steam-cloud-seed-20261017'
sys.path.insert(0,str(ROOT/'tools'))
import debian_rootfs as base

def copy(src,dst):
    target=OUT/dst
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('xb') as out,src.open('rb') as inp:
        shutil.copyfileobj(inp,out)

final=TASK/'experimental-seed-acceptance-v3/experimental-acceptance.json'
report=json.loads(final.read_text())
assert report['status']=='pass' and report['production_gui_lock_unchanged'] is True
assert report['seed_published'] is False and report['task_qemu_remaining'] is False
lock=ROOT/'ipa/gui.lock.json'
scope=json.loads((TASK/'experimental-seed-acceptance-v3/scope.json').read_text())
assert base.sha256(lock)==scope['production_gui_lock_sha256']
seed=TASK/'experimental-seed-v4/seed/gui-rootfs-v1.raw'
assert seed.stat().st_size==report['seed']['size'] and base.sha256(seed)==report['seed']['sha256']
assert report['seed']['sha256']!=json.loads(lock.read_text())['files']['gui-rootfs-v1.raw']['sha256']
preserved=TASK/'gui-provisioned-preserved.raw'
assert base.sha256(preserved)=='425893ed8c04270e293f7b5ed8b4db5cf94d3c98db17f66f0666de515f821f22'
frozen=json.loads((TASK/'experimental-seed-acceptance-v3/frozen-lab.json').read_text())
assert base.sha256(TASK/'gui-lab-inputfix/scratch-gui.raw')==frozen['sha256']
for name in ['scope.json','preserved-provision.json','frozen-lab.json','elf-inventory.json','experimental-acceptance.json']:
    copy(TASK/'experimental-seed-acceptance-v3'/name,name)
copy(TASK/'experimental-seed-v4/seed/gui-seed.json','experimental-gui-seed.json')
copy(TASK/'experimental-alpine-gate-v4/acceptance.json','alpine-acceptance.json')
copy(TASK/'run_seed_acceptance_v3.py','run_seed_acceptance_v3.py')
copy(Path(__file__),'collect_seed_evidence_v4.py')
copy(TASK/'logs/seed-acceptance-v3.stdout.log','orchestrator.stdout.log')
copy(TASK/'logs/seed-acceptance-v3.stderr.log','orchestrator.stderr.log')
steps=[(TASK/'gui-lab-acceptance-v3/boot1','lab-boot1'),
       (TASK/'gui-lab-acceptance-v3/boot2','lab-boot2'),
       (TASK/'experimental-seed-v4/cleanup-boot','seed-cleanup'),
       (TASK/'experimental-alpine-gate-v4/boot1','alpine-boot1'),
       (TASK/'experimental-alpine-gate-v4/boot2','alpine-boot2')]
summary=[]
for source,name in steps:
    r=json.loads((source/'result.json').read_text())
    fsck=json.loads((source/'strict-fsck.json').read_text())
    assert r['status']=='pass' and r['clean_unmount'] is True and r['qemu_exit']==0
    assert fsck['evaluation']['accepted'] is True and fsck['raw_sha256_before']==fsck['raw_sha256_after']
    for f in ['result.json','serial.log','control.log','runner-source.py','package-manifest.tsv',
              'strict-fsck.json','strict-fsck.stdout.log','strict-fsck.stderr.log',
              'desktop.png','after-input.png','desktop-menu.png']:
        copy(source/f,name+'/'+f)
    summary.append({'step':name,**{k:r.get(k) for k in ['status','elapsed_seconds',
        'qemu_peak_rss_bytes','actual_glibc_loader_executables_passed','keyboard_input_verified',
        'emulated_pointer_move_resize','wheel_evdev_verified','real_root_menu_launch',
        'persistence_read_before_write','editor_reopened_after_boot','clean_unmount','qemu_exit']},
        'strict_fsck_pass':True})
for f in ['strict-fsck.json','strict-fsck.stdout.log','strict-fsck.stderr.log']:
    copy(TASK/'experimental-seed-v4/seed'/f,'seed-offline/'+f)
with (OUT/'summary.json').open('x') as out:
    out.write(json.dumps({'scope':'separate experimental seed; no production replacement',
        'seed':report['seed'],'gzip':report['gzip'],'steps':summary,
        'strict_checks':6,'production_gui_lock_unchanged':True,
        'original_provisioned_copy_preserved':True,'frozen_lab_preserved':True,
        'steam_client_downloads':'0 of17; previously blocked; not retried',
        'steam_runtime':'NOT RUN','security_or_network_changes':False},indent=2)+'\n')

copy(TASK/'run_seed_acceptance.py','initial/run_seed_acceptance.py')
copy(TASK/'logs/seed-acceptance.stdout.log','initial/orchestrator.stdout.log')
copy(TASK/'logs/seed-acceptance.stderr.log','initial/orchestrator.stderr.log')
copy(TASK/'logs/gui-inputfix-tests.log','gui-inputfix-tests.log')
for prior, label in [('gui-lab-acceptance/boot1','initial/lab-boot1'),
                     ('gui-lab-acceptance/boot2','initial/lab-boot2')]:
    for name in ['result.json','serial.log','runner-source.py','strict-fsck.json',
                 'strict-fsck.stdout.log','strict-fsck.stderr.log']:
        copy(TASK/prior/name,label+'/'+name)
for name in ['result.json','serial.log','runner-source.py','failure.png',
             'failed-run-fsck.json','failed-run-fsck.stdout.log','failed-run-fsck.stderr.log']:
    copy(TASK/'experimental-seed/cleanup-boot'/name,'initial/failed-cleanup/'+name)


copy(TASK/'run_seed_acceptance_v2.py','preparation-error/run_seed_acceptance_v2.py')
copy(TASK/'logs/seed-acceptance-v2.stdout.log','preparation-error/orchestrator.stdout.log')
copy(TASK/'logs/seed-acceptance-v2.stderr.log','preparation-error/orchestrator.stderr.log')


copy(TASK/'finalize_seed_v4.py','finalize_seed_v4.py')
copy(TASK/'logs/seed-finalization-v4.stdout.log','finalization.stdout.log')
copy(TASK/'logs/seed-finalization-v4.stderr.log','finalization.stderr.log')

files=[]
for p in sorted(OUT.rglob('*')):
    if p.is_file() and p.name!='manifest.json':
        files.append({'path':p.relative_to(OUT).as_posix(),'size':p.stat().st_size,'sha256':base.sha256(p)})
with (OUT/'manifest.json').open('x') as out:
    out.write(json.dumps({'schema':1,'scope':'experimental seed acceptance and precise network requirements; no disk/client bytes','files':files},indent=2)+'\n')
print(json.dumps({'copied_files':len(files),'seed':report['seed'],'steps':summary},indent=2))
