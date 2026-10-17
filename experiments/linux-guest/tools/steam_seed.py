#!/usr/bin/env python3
"""Verify the reviewed private Steam seed contract; never writes/boots a disk.

An explicit repository contract selects the independent cloud seed. Production
GUI inputs remain the runner default. Acceptance is authenticated by the pinned
evidence manifest, then checked semantically, including full offline fsck logs.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_SOURCE = Path(__file__).read_bytes()
CONTRACT = 'profiles/steam-experimental-seed-20261017.lock.json'
CONTRACT_ID = 'steam-cloud-gui-20261017-a7758d82'
BINDINGS = {'ipa/gui.lock.json', 'ipa/gui-inputs.lock.json',
            'ipa/steam-client.lock.json', 'ipa/steam-dependencies.lock.json',
            'profiles/steam-host-experiment.json'}


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def real_file(path, limit=None):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file():
        raise ValueError('seed contract requires regular files without symlink ancestors')
    if limit is not None and path.stat().st_size > limit:
        raise ValueError('seed contract file exceeds bound')
    return path


def relative(base, name):
    if (not isinstance(name, str) or not name or len(name) > 1024
            or ':' in name or '\\' in name or '\0' in name
            or name != PurePosixPath(name).as_posix()
            or PurePosixPath(name).is_absolute()
            or any(p in ('.', '..') for p in name.split('/'))):
        raise ValueError('invalid seed provenance path')
    return real_file(base/name)


def pin(value, maximum):
    if (not isinstance(value, dict) or type(value.get('size')) is not int
            or not 0 <= value['size'] <= maximum
            or not isinstance(value.get('sha256'), str)
            or not re.fullmatch('[0-9a-f]{64}', value['sha256'])):
        raise ValueError('invalid seed contract hash/size pin')
    return {'size': value['size'], 'sha256': value['sha256']}


def checked(path, value, maximum=16*1024**2):
    value = pin(value, maximum)
    path = real_file(path, maximum)
    if path.stat().st_size != value['size'] or sha(path) != value['sha256']:
        raise ValueError('seed contract integrity mismatch: '+path.name)
    return path


def load(path, limit=1024**2):
    return json.loads(real_file(path, limit).read_text(encoding='utf-8'))


def evidence(provenance):
    ref = provenance['manifest']
    if not ref['path'].startswith('evidence/'):
        raise ValueError('seed provenance must be repository evidence')
    manifest_path = checked(relative(ROOT, ref['path']), ref, 2*1024**2)
    manifest = load(manifest_path, 2*1024**2)
    if type(manifest.get('schema')) is not int or manifest['schema'] != 1 or not isinstance(manifest.get('files'), list):
        raise ValueError('invalid seed evidence manifest')
    entries = manifest['files']
    if not 1 <= len(entries) <= 2048 or sum(pin(e, 16*1024**2)['size'] for e in entries) > 32*1024**2:
        raise ValueError('seed evidence manifest bound')
    paths = {}
    for entry in entries:
        name = entry['path']
        if name in paths: raise ValueError('duplicate seed evidence entry')
        paths[name] = checked(relative(manifest_path.parent, name), entry)
    return paths


def validate(contract_path, seed, kernel, bootstrap, evaluate_fsck, *, runner_source):
    contract_path = real_file(contract_path, 256*1024)
    if contract_path != (ROOT/CONTRACT).absolute():
        raise ValueError('unreviewed experimental seed contract path')
    c = load(contract_path, 256*1024)
    if (type(c.get('schema')) is not int or c['schema'] != 1 or c.get('kind') != 'private-steam-experimental-seed'
            or c.get('id') != CONTRACT_ID or c.get('host_only') is not True
            or c.get('app_route_enabled') is not False
            or c.get('production_gui_override') is not False):
        raise ValueError('invalid experimental seed contract scope')
    if set(c['repository_bindings']) != BINDINGS:
        raise ValueError('incomplete experimental seed repository bindings')
    for name, digest in c['repository_bindings'].items():
        if not re.fullmatch('[0-9a-f]{64}', digest) or sha(relative(ROOT, name)) != digest:
            raise ValueError('experimental seed repository binding differs: '+name)
    production = load(ROOT/'ipa/gui.lock.json')
    if (c['kernel'] != production['files']['vmlinuz-virt']
            or c['gui_initramfs'] != production['files']['initramfs-desktop.gz']
            or c['seed'] == production['files']['gui-rootfs-v1.raw']):
        raise ValueError('experimental seed must preserve production GUI inputs and identity')
    if pin(c['seed'], 4*1024**3)['size'] == 0:
        raise ValueError('empty experimental seed refused')
    checked(seed, c['seed'], 4*1024**3)
    checked(kernel, c['kernel'], 64*1024**2)
    checked(Path(bootstrap)/'initramfs-steam.gz', c['steam_bootstrap'], 64*1024**2)
    prep_path = checked(Path(bootstrap)/'bootstrap.json', c['steam_bootstrap_receipt'])
    prep = load(prep_path)
    if (prep['base_initramfs'] != c['gui_initramfs']
            or prep['initramfs'] != c['steam_bootstrap']
            or prep['required_kernel_sha256'] != c['kernel']['sha256']
            or prep.get('original_shutdown_function_preserved') is not True
            or prep.get('gui_payload_changed') is not False
            or prep.get('valve_client_bundled') is not False):
        raise ValueError('experimental seed Steam bootstrap scope differs')
    paths = evidence(c['provenance'])
    def item(name):
        if name not in paths: raise ValueError('required seed evidence is absent')
        return load(paths[name])
    p = c['provenance']
    accepted, seed_receipt, completed = [item(p[k]) for k in ('acceptance', 'seed_receipt', 'completion')]
    root_identity = {'file': 'gui-rootfs-v1.raw', **c['seed']}
    if (seed_receipt.get('schema') != 1 or seed_receipt.get('mode') != 'gui-seed'
            or seed_receipt.get('rootfs') != root_identity
            or seed_receipt.get('read_only_fsck') is not True
            or seed_receipt.get('app_payload_ready') is not False
            or seed_receipt.get('gui_package_lock_sha256') != c['repository_bindings']['ipa/gui-inputs.lock.json']):
        raise ValueError('experimental seed builder receipt differs')
    if (accepted.get('schema') != 1 or accepted.get('kind') != 'production-alpine-two-boots'
            or accepted.get('status') != 'pass' or accepted.get('matching_kernel_gui') is not True
            or accepted.get('two_boots_clean') is not True or accepted.get('machine_id_persisted') is not True
            or accepted.get('rootfs_sha256') != c['seed']['sha256']
            or accepted.get('kernel_sha256') != c['kernel']['sha256']
            or accepted.get('initramfs_sha256') != c['gui_initramfs']['sha256']
            or accepted.get('gui_package_lock_sha256') != c['repository_bindings']['ipa/gui-inputs.lock.json']
            or accepted.get('ios_compiled') is not False or accepted.get('device_verified') is not False):
        raise ValueError('experimental seed Alpine acceptance differs')
    base_ref = p['gui_bootstrap_receipt']
    base_path = checked(relative(ROOT, base_ref['path']), base_ref)
    base = load(base_path)
    if (accepted['bootstrap_receipt_sha256'] != base_ref['sha256']
            or base['kernel'] != c['kernel'] or base['initramfs'] != c['gui_initramfs']):
        raise ValueError('experimental seed original GUI bootstrap differs')
    if (completed.get('schema') != 1 or completed.get('status') != 'pass'
            or completed.get('scope') != 'separate experimental seed only'
            or completed.get('seed') != root_identity or completed.get('alpine_acceptance') != accepted
            or completed.get('production_gui_lock_unchanged') is not True
            or completed.get('production_seed_replaced') is not False
            or completed.get('seed_published') is not False
            or completed.get('task_qemu_remaining') is not False
            or completed.get('security_or_network_settings_changed') is not False):
        raise ValueError('experimental seed completion receipt differs')
    if set(p['boot_reports']) != {'boot1', 'boot2'} or set(p['strict_checks']) != {'boot1', 'boot2', 'seed'}:
        raise ValueError('incomplete experimental seed boot/fsck provenance')
    machine_ids = []
    for name in ('boot1', 'boot2'):
        ref = p['boot_reports'][name]
        report = item(ref['report'])
        if sha(paths[ref['report']]) != accepted['boot_reports'][name]:
            raise ValueError('experimental seed boot report hash differs')
        if (not all(report.get(k) is True for k in ('host_only', 'production_bootstrap', 'gui_mapped',
                'keyboard_input_verified', 'emulated_pointer_move_resize', 'wheel_evdev_verified',
                'real_root_menu_launch', 'clean_unmount', 'read_only_fsck'))
                or type(report.get('qemu_exit')) is not int or report['qemu_exit'] != 0
                or report.get('forced_termination') or report.get('persistence_boot') != (name == 'boot2')
                or report['preparation']['kernel_sha256'] != c['kernel']['sha256']
                or report['preparation']['initramfs_sha256'] != c['gui_initramfs']['sha256']
                or report['runner_sha256'] != sha(paths[ref['runner']])):
            raise ValueError('experimental seed real boot acceptance failed')
        if name == 'boot2' and not all(report.get(k) is True for k in
                ('persistence_read_before_write', 'editor_reopened_after_boot')):
            raise ValueError('experimental seed persistence acceptance failed')
        machine_ids.append(report.get('machine_id_sha256'))
    if (not isinstance(machine_ids[0], str) or not re.fullmatch('[0-9a-f]{64}', machine_ids[0])
            or machine_ids[0] != machine_ids[1]):
        raise ValueError('experimental seed machine ID did not persist')
    for name, ref in p['strict_checks'].items():
        check = item(ref['report'])
        stdout, stderr = [paths[ref[k]].read_text(encoding='utf-8') for k in ('stdout', 'stderr')]
        if (check.get('read_only') is not True or check.get('writer_running') is not False
                or check.get('host_fsync') is not True
                or check.get('raw_sha256_before') != check.get('raw_sha256_after')
                or not isinstance(check.get('command'), list) or not check['command']):
            raise ValueError('experimental seed offline check ownership differs')
        if name == 'seed' and check['raw_sha256_after'] != c['seed']['sha256']:
            raise ValueError('experimental seed offline check covers different bytes')
        evaluation = evaluate_fsck(check['exit_code'], stdout, stderr, check['command'][-1])
        if not evaluation['accepted'] or check.get('evaluation') != evaluation:
            raise ValueError('experimental seed strict full-output fsck failed')
    validator_hash = hashlib.sha256(VALIDATOR_SOURCE).hexdigest()
    runner_hash = hashlib.sha256(runner_source).hexdigest()
    configuration = {'seed': c['seed'], 'kernel': c['kernel'], 'steam_bootstrap': c['steam_bootstrap'],
                     'contract_sha256': sha(contract_path), 'repository_bindings': c['repository_bindings'],
                     'validator_sha256': validator_hash, 'runner_sha256': runner_hash, 'vcpus': 4,
                     'profile': load(ROOT/'profiles/steam-host-experiment.json')}
    config_bytes = json.dumps(configuration, sort_keys=True, separators=(',', ':')).encode()
    return {'mode': 'explicit-experimental-seed', 'id': c['id'], 'contract_path': CONTRACT,
            'contract_sha256': sha(contract_path), 'seed': c['seed'], 'kernel': c['kernel'],
            'validator_sha256': validator_hash,
            'runner_sha256': runner_hash,
            'acceptance_sha256': sha(paths[p['acceptance']]), 'evidence_files_verified': len(paths),
            'configuration': configuration, 'configuration_sha256': hashlib.sha256(config_bytes).hexdigest(),
            'production_gui_override': False, 'host_only': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('contract', 'seed', 'kernel', 'bootstrap', 'storage-root'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    import steam_vm
    try:
        receipt = validate(args.contract, args.seed, args.kernel, args.bootstrap, steam_vm.evaluate_offline_fsck,
                           runner_source=steam_vm.RUNNER_SOURCE)
        storage = steam_vm.storage_preflight(args.storage_root, receipt['configuration']['profile'])
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({'seed_contract_valid': False,
                          'failure': {'class': type(error).__name__, 'message': str(error)},
                          'qemu_started': False, 'disk_created': False, 'dependencies_installed': False}, indent=2))
        return 1
    print(json.dumps({'seed_contract_valid': True, 'validation': receipt, 'storage': storage,
                      'qemu_started': False, 'disk_created': False, 'dependencies_installed': False}, indent=2))
    return 0 if storage['allowed'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
