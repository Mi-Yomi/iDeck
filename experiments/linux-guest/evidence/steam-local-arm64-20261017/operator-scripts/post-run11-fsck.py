import os,sys,json,fcntl
from pathlib import Path
base=Path('/mnt/e/Freddy Fazbear/iDeck.work/steam-arm64-experiment-20261017')
task=base/'resume-local-20261017';sys.path.insert(0,str(base/'source/experiments/linux-guest/tools'))
import steam_vm,gui_host_tools
run=task/'run11';report=json.loads((run/'result.json').read_text());assert report['qemu_exit_code']==-9 and report['clean_shutdown'] is False and (run/'needs-recovery').is_file()
with (run/'owner.lock').open('rb') as owner:
    fcntl.flock(owner,fcntl.LOCK_EX|fcntl.LOCK_NB)
    disk=run/'steam-experiment.qcow2';out=task/'post-run11-fsck';out.mkdir(exist_ok=False)
    host=base/'prior-build/production/vm/host';tool=base/'image-tools/usr/bin/qemu-img'
    assert steam_vm.sha(tool)==json.loads((base/'image-tools/receipt.json').read_text())['binary_sha256']
    image=gui_host_tools.command(host,[host/'usr/bin/qemu-system-aarch64'])[:-1]+[str(tool)]
    env={'PATH':os.defpath,'LC_ALL':'C','QEMU_MODULE_DIR':str(host/'usr/lib/x86_64-linux-gnu/qemu')}
    before=steam_vm.sha(disk)
    try:steam_vm.offline_fsck(disk,out,image,env,gui_host_tools.command(host,[host/'usr/sbin/e2fsck']))
    except RuntimeError as exc:print(str(exc),flush=True)
    after=steam_vm.sha(disk);assert before==after
    receipt={'source_sha256_before':before,'source_sha256_after':after,'original_unchanged':True,'owner_lock_exclusive':True,'clean_shutdown':False,'dirty_marker_retained':(run/'needs-recovery').is_file(),'repair_attempted':False,'continuation_allowed':False}
    (out/'source-preservation.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt),flush=True)