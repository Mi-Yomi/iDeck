"""Retain small private-cloud evidence only; never copies disks or client bytes."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

REPO = Path('/workspace/iDeck')
ROOT = REPO/'experiments/linux-guest'
TASK = Path('/workspace/steam-cloud-20261017')
OUT = ROOT/'evidence/steam-cloud-20261017'
sys.path.insert(0, str(ROOT/'tools'))
import steam_vm
import gui_host_tools

def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def write(name, data):
    p = OUT/name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2)+'\n')

def copy(source, destination):
    p = OUT/destination
    p.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, p)

prior = ROOT/'evidence/steam-ipc-20261017'
manifest = json.loads((prior/'manifest.json').read_text())
for entry in manifest['files']:
    p = prior/entry['path']
    assert p.stat().st_size == entry['size'] and sha(p) == entry['sha256']

provision = TASK/'gui-lab-acceptance/provision'
result = json.loads((provision/'result.json').read_text())
assert result['status'] == 'pass' and result['clean_unmount'] is True
assert result['qemu_exit'] == 0 and not result.get('forced_termination')
# Only inspect offline images after the owning runner has fully exited.
qemu_users = []
for proc in Path('/proc').iterdir():
    if not proc.name.isdecimal():
        continue
    try:
        cmd = (proc/'cmdline').read_bytes()
        if b'qemu-system-aarch64\0' in cmd and bytes(str(TASK), 'utf-8') in cmd:
            qemu_users.append(int(proc.name))
    except (FileNotFoundError, PermissionError, ProcessLookupError):
        pass
assert not qemu_users, qemu_users
raw = TASK/'gui-lab/scratch-gui.raw'
with raw.open('rb') as f:
    os.fsync(f.fileno())
before = sha(raw)
host = TASK/'gui-lab/host'
command = gui_host_tools.command(host, [host/'usr/sbin/e2fsck', '-f', '-n', raw])
check = subprocess.run(command, capture_output=True, text=True,
                       env={'PATH': os.defpath, 'LC_ALL': 'C', 'LANG': 'C'})
evaluation = steam_vm.evaluate_offline_fsck(check.returncode, check.stdout, check.stderr, raw)
copy(provision/'result.json', 'gui-provision/result.json')
copy(provision/'serial.log', 'gui-provision/serial.log')
copy(provision/'control.log', 'gui-provision/control.log')
copy(provision/'runner-source.py', 'gui-provision/runner-source.py')
copy(provision/'package-manifest.tsv', 'gui-provision/package-manifest.tsv')
(OUT/'gui-provision/offline-fsck.stdout.log').write_text(check.stdout)
(OUT/'gui-provision/offline-fsck.stderr.log').write_text(check.stderr)
after = sha(raw)
write('gui-provision/offline-fsck.json', {
    'command': command, 'exit_code': check.returncode, 'evaluation': evaluation,
    'read_only': True, 'task_qemu_pids': qemu_users, 'writer_running': False,
    'raw_size': raw.stat().st_size, 'raw_sha256_before': before,
    'raw_sha256_after': after, 'host_fsync': 'pass',
    'scope': 'new disposable GUI provisioning image; not accepted seed/Steam runtime'})

for source, destination in [
    ('source-check.json', 'source-check.json'),
    ('prepare_support.py', 'prepare_support.py'),
    ('finalize_evidence.py', 'finalize_evidence.py'),
    ('support-receipt.json', 'support-receipt.json'),
    ('gui-lab/preparation.json', 'gui-preparation.json'),
    ('gui-bootstrap/bootstrap.json', 'gui-bootstrap.json'),
    ('steam-bootstrap/bootstrap.json', 'steam-bootstrap.json'),
    ('logs/gui-download.stdout.log', 'gui-download.json'),
    ('logs/steam-download.stderr.log', 'steam-download.stderr.log'),
    ('logs/steam-download.stdout.log', 'steam-download.stdout.log'),
    ('logs/release-metadata.stderr.log', 'release-metadata.stderr.log'),
    ('logs/steam-tests.log', 'steam-tests.log'),
]:
    copy(TASK/source, destination)

client_lock = ROOT/'ipa/steam-client.lock.json'
client = json.loads(client_lock.read_text())
first = client['parts'][0]
assert not list((TASK/'client-cache').iterdir())
bootstrap = json.loads((TASK/'steam-bootstrap/bootstrap.json').read_text())
usage = shutil.disk_usage(TASK)
preflight = {
    'schema': 1, 'observed_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'repository': 'https://github.com/Mi-Yomi/iDeck.git',
    'initial_workspace_branch': 'work',
    'initial_workspace_sha': 'a77ab500cdf8c8307af36a58b25816a3fa4d66db',
    'initial_foreign_changes': [], 'initial_task_images_or_cache': [],
    'branch': 'codex/steam-arm64-experiment-20261017',
    'source_sha': 'b493a4909f81a5df0c226d9562a049e59e191039',
    'remote_source_sha_verified': True,
    'repo_or_ancestor_agents_instructions_found': False,
    'repo_agents_skills_found': False,
    'prior_ipc_manifest_sha256': sha(prior/'manifest.json'),
    'prior_ipc_files_verified': len(manifest['files']),
    'host_architecture': os.uname().machine,
    'cgroup_memory_max': Path('/sys/fs/cgroup/memory.max').read_text().strip(),
    'cgroup_cpu_max': Path('/sys/fs/cgroup/cpu.max').read_text().strip(),
    'initial_workspace_free': 'approximately30GiB from df; no existing task disks',
    'retained_workspace_free_bytes': usage.free,
    'host_filesystem': 'overlayfs',
    'steam_bootstrap_exact_handoff_match': bootstrap['initramfs'] == {
        'size': 11665437, 'sha256': '6a0081d76fedbb38b72e705334513313093b46e701907ed8b6d516640978df7f'},
    'steam_client_lock_sha256': sha(client_lock),
    'steam_initial_version': client['version'],
    'failed_download': {'url': 'https://client-update.fastly.steamstatic.com/'+first['file'],
        'component': first, 'installer_exit': 1, 'received_zip_count': 0,
        'error': 'URLError: <urlopen error Tunnel connection failed: 403 Forbidden>'},
    'release_shell_download': {
        'command': "gh api -i -H 'Accept: application/octet-stream' repos/Mi-Yomi/iDeck/releases/assets/650023557",
        'exit_code': 1,
        'stderr': 'Get "https://api.github.com/repos/Mi-Yomi/iDeck/releases/assets/650023557": Forbidden',
        'http_status_or_body_received': False,
        'source': 'initial exec tool result, observed before file logging'},
    'steam_guest_dependencies': 'NOT INSTALLED;45 verified packages cached',
    'new_gui_provision': result['status'],
    'strict_offline_fsck_accepted': evaluation['accepted'] and before == after,
    'new_gui_seed_acceptance': 'NOT RUN; scratch image is not the accepted seed',
    'steam_runtime': {k: 'NOT RUN' for k in ['main_ui', 'big_picture', 'input', 'restart',
        'ram', 'shm', 'sandbox', 'ipc_trace', 'aarch64_stack_capture', 'iphone', 'apple_build', 'gpu_acceleration']},
    'final_task_qemu_pids': qemu_users,
    'secrets_created': False, 'security_changed': False, 'client_or_disk_published': False,
    'system_package_install': False, 'ci_dispatched': False, 'subagents_created': False,
}
write('preflight.json', preflight)
files = []
for p in sorted(OUT.rglob('*')):
    if p.is_file() and p.name != 'manifest.json':
        files.append({'path': p.relative_to(OUT).as_posix(), 'size': p.stat().st_size, 'sha256': sha(p)})
write('manifest.json', {'schema': 1, 'scope': 'cloud input preparation and infrastructure blocker; no Steam UI acceptance', 'files': files})
print(json.dumps({'files': len(files), 'provision_status': result['status'],
    'fsck_accepted': evaluation['accepted'], 'disk_unchanged_by_check': before == after,
    'provision_qemu_peak_rss_bytes': result['qemu_peak_rss_bytes']}, indent=2))
