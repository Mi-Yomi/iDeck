"""Offline acceptance of a separate experimental seed; production locks untouched."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path('/workspace/iDeck/experiments/linux-guest')
TASK = Path('/workspace/steam-cloud-20261017')
sys.path.insert(0, str(ROOT/'tools'))
import debian_rootfs as base
import check_gui_vm
import gui_elf
import gui_gate
import gui_host_tools
import gui_seed
import steam_vm

def save(path, value):
    with path.open('x') as out:
        out.write(json.dumps(value, indent=2)+'\n')

def no_qemu():
    found=[]
    for p in Path('/proc').iterdir():
        if not p.name.isdecimal(): continue
        try:
            argv=(p/'cmdline').read_bytes().split(b'\0')
            if any(os.fsdecode(a).rsplit('/',1)[-1]=='qemu-system-aarch64' for a in argv if a):
                found.append(int(p.name))
        except (FileNotFoundError, PermissionError, ProcessLookupError): pass
    if found: raise RuntimeError('existing QEMU process: '+str(found))

def strict_fsck(raw, host, output):
    no_qemu()
    with raw.open('rb') as f: os.fsync(f.fileno())
    before=base.sha256(raw)
    cmd=gui_host_tools.command(host,[host/'usr/sbin/e2fsck','-f','-n',raw])
    r=subprocess.run(cmd,capture_output=True,text=True,
                     env={'PATH':os.defpath,'LC_ALL':'C','LANG':'C'},check=False)
    (output/'strict-fsck.stdout.log').write_text(r.stdout)
    (output/'strict-fsck.stderr.log').write_text(r.stderr)
    evaluation=steam_vm.evaluate_offline_fsck(r.returncode,r.stdout,r.stderr,raw)
    after=base.sha256(raw)
    receipt={'command':cmd,'exit_code':r.returncode,'evaluation':evaluation,
             'read_only':True,'writer_running':False,'host_fsync':True,
             'raw_sha256_before':before,'raw_sha256_after':after}
    save(output/'strict-fsck.json',receipt)
    if not evaluation['accepted'] or after!=before:
        raise RuntimeError('strict offline fsck refused; no repair or further boot')
    return receipt

def guarded_boot(vm, output, **kwargs):
    no_qemu()
    result=check_gui_vm.boot(vm,output,**kwargs)
    if (result.get('status')!='pass' or result.get('clean_unmount') is not True
            or result.get('qemu_exit')!=0 or result.get('forced_termination')):
        raise RuntimeError('unclean or incomplete GUI acceptance')
    strict_fsck(vm/'scratch-gui.raw',vm/'host',output)
    return result

lock_path=ROOT/'ipa/gui-inputs.lock.json'
production_lock=ROOT/'ipa/gui.lock.json'
production_before=base.sha256(production_lock)
base.OFFLINE=True
out=TASK/'experimental-seed-acceptance-v3'
with (TASK/'experimental-seed-v4-owner.lock').open('xb') as owner:
    fcntl.flock(owner,fcntl.LOCK_EX|fcntl.LOCK_NB)
    no_qemu()
    vm=TASK/'gui-lab-inputfix';source=vm/'scratch-gui.raw'
    frozen=json.loads((out/'frozen-lab.json').read_text())
    source_hash=frozen['sha256']
    if base.sha256(source)!=source_hash:raise RuntimeError('frozen lab changed')
    inventory=out/'elf-inventory.json';lab=TASK/'gui-lab-acceptance-v3'
    gui_seed.boot=guarded_boot
    print('Starting cleanup from verified frozen lab; exact probe now a real directory',flush=True)
    seed_report=gui_seed.prepare(source,vm,TASK/'gui-cache',TASK/'experimental-seed-v4',lock_path,lab,source_hash)
    seed=TASK/'experimental-seed-v4/seed'
    strict_fsck(seed/'gui-rootfs-v1.raw',TASK/'experimental-seed-v4/vm/host',seed)
    print('Created experimental seed; starting matching Alpine two-boot gate',flush=True)
    gui_gate.boot=guarded_boot
    accepted=gui_gate.run(seed,TASK/'gui-bootstrap',TASK/'gui-cache',TASK/'experimental-alpine-gate-v4',lock_path,inventory)
    if base.sha256(production_lock)!=production_before:raise RuntimeError('production lock changed')
    preserved=TASK/'gui-provisioned-preserved.raw'
    if base.sha256(preserved)!='425893ed8c04270e293f7b5ed8b4db5cf94d3c98db17f66f0666de515f821f22':raise RuntimeError('original preserved copy changed')
    no_qemu()
    report={'schema':1,'status':'pass','scope':'separate experimental seed only','seed':seed_report['rootfs'],'gzip':seed_report['gzip'],'alpine_acceptance':accepted,'production_gui_lock_unchanged':True,'production_seed_replaced':False,'seed_published':False,'steam_runtime':'NOT RUN','task_qemu_remaining':False,'security_or_network_settings_changed':False,'lab_orchestrator_sha256':base.sha256(TASK/'run_seed_acceptance_v3.py'),'finalization_orchestrator_sha256':base.sha256(Path(__file__))}
    save(out/'experimental-acceptance.json',report)
    print(json.dumps(report,indent=2),flush=True)
