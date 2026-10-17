"""Read-only verification of the actual selected private cloud inputs."""
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

REPO = Path('/workspace/iDeck')
ROOT = REPO/'experiments/linux-guest'
PRIVATE = Path('/workspace/steam-fresh-20261017')
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT/'tools'))
sys.dont_write_bytecode = True
import gui_host_tools
import steam_vm

def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def check(path, expected):
    assert path.is_file() and not path.is_symlink(), path.name
    actual = {'size': path.stat().st_size, 'sha256': sha(path)}
    assert actual['sha256'] == expected['sha256'], path.name
    if 'size' in expected:
        assert actual['size'] == expected['size'], path.name
    return actual

report = {'time_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'source_sha': subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),
          'read_only_image_verification': True, 'vm_started': False,
          'policy_changed': False, 'experimental_seed_selected': False}
manifests = {}
for path in sorted((ROOT/'evidence').glob('steam-*/manifest.json')):
    entries = json.loads(path.read_text())['files']
    for pin in entries:
        target = path.parent/pin['path']
        assert target.resolve().is_relative_to(path.parent.resolve())
        check(target, pin)
    manifests[path.parent.name] = {'count':len(entries),'sha256':sha(path),'all_match':True}
report['manifests'] = manifests

report['qemu_pids'] = []
for proc in Path('/proc').iterdir():
    if not proc.name.isdecimal():
        continue
    try:
        executable = (proc/'comm').read_text().strip()
        if executable.startswith(('qemu-system','qemu-img','qemu-nbd')):
            report['qemu_pids'].append(int(proc.name))
    except OSError:
        pass
report['task_mounts'] = [line for line in Path('/proc/self/mountinfo').read_text().splitlines()
                         if str(PRIVATE) in line or str(OUT) in line]
assert not report['qemu_pids'] and not report['task_mounts']

production = json.loads((ROOT/'ipa/gui.lock.json').read_text())
report['production_inputs'] = {name:check(PRIVATE/'gui'/name,pin)
                               for name,pin in production['files'].items()}
report['release'] = check(PRIVATE/'release/ideck-debian-gui-v1.tar', {
    'size':292065280,'sha256':'112bdba6e12ae182fb347e52e7368e26f748bb3dc2bcd77dbd3122fb14dcdedd'})
client = json.loads((ROOT/'ipa/steam-client.lock.json').read_text())
for pin in client['parts']:
    check(PRIVATE/'client-cache'/pin['file'],pin)
report['client_cache'] = {'count':len(client['parts']), 'all_match':True,
                          'bytes':sum(pin['size'] for pin in client['parts'])}
dependencies = json.loads((ROOT/'ipa/steam-dependencies.lock.json').read_text())
for pin in dependencies['extra_packages']:
    check(PRIVATE/'deps-cache/debs'/Path(pin['filename']).name,pin)
report['dependency_cache'] = {'count':len(dependencies['extra_packages']),'all_match':True}

bootstrap = json.loads((PRIVATE/'bootstrap/bootstrap.json').read_text())
report['bootstrap'] = check(PRIVATE/'bootstrap/initramfs-steam.gz',bootstrap['initramfs'])
for name,pin in bootstrap['inputs'].items():
    check(ROOT/name,pin)
report['bootstrap_repo_inputs_match'] = True

report['runs'] = {}
previous = json.loads((ROOT/'evidence/steam-proxy-ipc-static-20261017/environment-verification.json').read_text())
for name in ('run1','run2'):
    folder = PRIVATE/name
    with (folder/'owner.lock').open('rb') as owner:
        fcntl.flock(owner,fcntl.LOCK_EX|fcntl.LOCK_NB)
        steam_vm.validate_continuation(folder,production['files']['gui-rootfs-v1.raw']['sha256'])
        disk = check(folder/'steam-experiment.qcow2',previous['preserved_inputs'][name])
        report['runs'][name] = {**disk,'unchanged':True,'owner_lock_free':True,'dirty_marker':False}
report['previous_guest_install'] = json.loads((PRIVATE/'run1-evidence/install-result.json').read_text())
assert report['previous_guest_install']['verified_debs'] == 45
assert report['previous_guest_install']['dpkg_audit_empty'] is True
report['previous_boot_persistence'] = json.loads((PRIVATE/'probes/persistence-after.json').read_text())
assert report['previous_boot_persistence']['dpkg_audit'] == {'exit_code':0,'stdout_bytes':0,'stderr_bytes':0}
report['new_guest_audit_run'] = False

report['prior_offline_fsck_revalidated'] = {}
for name in ('run2','post-run2-fsck'):
    folder = PRIVATE/name
    receipt = json.loads((folder/'offline-fsck.json').read_text())
    for suffix in ('stdout','stderr'):
        check(folder/f'offline-fsck.{suffix}.log',{'sha256':receipt[f'{suffix}_sha256']})
    evaluation = steam_vm.evaluate_offline_fsck(receipt['exit_code'],
        (folder/'offline-fsck.stdout.log').read_text(),(folder/'offline-fsck.stderr.log').read_text(),
        Path(receipt['fsck_command'][-1]))
    assert evaluation == receipt['evaluation'] and evaluation['accepted']
    assert receipt['raw_size'] == 12*1024**3 and not receipt['writer_running']
    report['prior_offline_fsck_revalidated'][name] = {'accepted':True,'new_fsck_run':False,
                                                   'raw_sha256':receipt['raw_sha256']}

receipt = json.loads((PRIVATE/'probes/qemu-img-receipt.json').read_text())
host = PRIVATE/'host'
report['qemu_img_binary'] = check(host/'usr/bin/qemu-img',{'sha256':receipt['binary_sha256']})
check(host/'usr/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2',{'sha256':receipt['loader_sha256']})
check(PRIVATE/'probes/host-tools.json',{'sha256':receipt['closure_receipt_sha256']})
check(PRIVATE/'debian-cache/debs'/Path(receipt['package']['filename']).name,receipt['package'])
probe = subprocess.run(gui_host_tools.command(host,[host/'usr/bin/qemu-img','--version']),
                       env={'PATH':os.defpath,'LC_ALL':'C'},capture_output=True,text=True,timeout=10)
assert probe.returncode == 0
report['qemu_img_version'] = probe.stdout.strip()
report['qemu_utils_receipt_verified'] = True
report['storage'] = steam_vm.storage_preflight(OUT,json.loads((ROOT/'profiles/steam-host-experiment.json').read_text()))
report['new_image_written'] = False
(OUT/'current-verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'all_verified':True,'manifests':{k:v['count'] for k,v in manifests.items()},
                  'production_seed':report['production_inputs']['gui-rootfs-v1.raw']['sha256'],
                  'runs_unchanged':True,'zip_count':17,'dependency_count':45,
                  'new_guest_audit_run':False,'qemu_utils_receipt_verified':True,
                  'storage':report['storage'],'qemu_pids':report['qemu_pids']},indent=2))
