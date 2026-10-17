#!/usr/bin/env python3
"""Explicit recovery of one fully captured, stopped Steam attempt's orphan SHM.

Never invoked by launch or Stop. Requires a SHA-pinned operator manifest and an
empty captured baseline from the same guest boot. No signal, memory read, mount,
sysctl or sandbox change. Cooperative Steam launch is excluded by its own lock;
every surviving process is inspected for FD/mapping references before unlink.
Unlink is not a kernel compare-and-delete operation: this deliberately assumes
no adversarial root/UID1000 process bypassing the launcher lock. Any observed
identity/process/manifest change fails closed, including during partial cleanup.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time

NAME = re.compile(r'u1000-(?:Shm_[0-9a-f]{1,8}|ValveIPCSharedObj-Steam)')
PROC = Path('/proc')
SHM = Path('/dev/shm')
RUNTIME = Path('/run/user/1000')
LOCK = 'ideck-steam.lock'


class Refused(RuntimeError):
    pass


def require(condition, code):
    if not condition:
        raise Refused(code)


def identity(info):
    return (info.st_dev, info.st_ino)


def guard():
    require(os.geteuid() == 0, 'guest_root_required')
    require(os.uname().release == '6.18.35-0-virt', 'pinned_kernel_required')
    require('ideck.steam_experiment=1' in (PROC/'cmdline').read_text().split(), 'experiment_opt_in_required')
    require((PROC/'1/root/ideck-steam-init').is_file(), 'steam_pid1_required')
    require(identity(os.stat('/')) == identity(os.stat(PROC/'1/root/sysroot')), 'debian_guest_root_required')
    require(os.readlink(PROC/'self/ns/pid') == os.readlink(PROC/'1/ns/pid'), 'full_pid_visibility_required')
    mounts = (PROC/'self/mountinfo').read_text().splitlines()
    require(any(len(row.split()) > 8 and row.split()[4] == '/dev/shm'
                and row.split(' - ', 1)[-1].split()[0] == 'tmpfs' for row in mounts), 'shm_tmpfs_required')


def validate_manifest(value, boot_id):
    require(isinstance(value, dict) and value.get('schema') == 1, 'manifest_schema')
    require(value.get('boot_id') == boot_id and bool(boot_id), 'manifest_boot_mismatch')
    require(value.get('baseline_empty') is True and value.get('capture_complete') is True, 'manifest_incomplete')
    objects, processes = value.get('objects'), value.get('processes')
    require(isinstance(objects, list) and 0 < len(objects) <= 256, 'manifest_object_count')
    require(isinstance(processes, list) and 0 < len(processes) <= 256, 'manifest_process_count')
    names, ids, total = set(), set(), 0
    for item in objects:
        require(isinstance(item, dict), 'manifest_object')
        require(isinstance(item.get('name'), str) and NAME.fullmatch(item['name']), 'manifest_name')
        require(all(type(item.get(key)) is int for key in ('device', 'inode', 'uid', 'size', 'mode')), 'manifest_identity')
        require(item['device'] > 0 and item['inode'] > 0 and item['uid'] == 1000
                and item['mode'] == 0o700 and 0 < item['size'] <= 128*1024**2, 'manifest_identity')
        key = (item['device'], item['inode'])
        require(item['name'] not in names and key not in ids, 'manifest_duplicate')
        names.add(item['name']); ids.add(key); total += item['size']
    require(total <= 2*1024**3, 'manifest_total_bound')
    seen = set()
    for process in processes:
        require(isinstance(process, dict) and type(process.get('pid')) is int
                and type(process.get('starttime')) is int and process['pid'] > 1
                and process['starttime'] > 0 and process['pid'] not in seen, 'manifest_process')
        seen.add(process['pid'])
    return objects, {row['pid']: row['starttime'] for row in processes}


def process_stat(path):
    value = (path/'stat').read_text()
    # comm may contain spaces and ')'; subsequent fields start after the last ')'.
    fields = value[value.rfind(')')+2:].split()
    require(len(fields) >= 20, 'proc_stat_invalid')
    return {'starttime': int(fields[19]), 'state': fields[0]}


def process_info(path):
    result = process_stat(path)
    status = dict(line.split(':', 1) for line in (path/'status').read_text().splitlines() if ':' in line)
    return {**result, 'name': status['Name'].strip(), 'uids': [int(x) for x in status['Uid'].split()]}


def process_gone(path):
    try:
        path.stat()
    except FileNotFoundError:
        return True
    return False


def scan_references(objects, captured, proc=None):
    """Inspect every PID identity, allowing bounded convergence of short helpers.

    PID1's control loop spawns innocuous tr/sleep children. New/reused PIDs are
    fully inspected rather than ignored or requiring the whole guest to freeze.
    Unreadable surviving PIDs or continuing churn after eight rounds are unsafe.
    """
    proc = PROC if proc is None else proc
    wanted = {(item['device'], item['inode']) for item in objects}
    checked = set()
    paths = {p.name: p for p in proc.iterdir() if p.name.isdecimal()}
    for _ in range(8):
        for pid, path in paths.items():
            try:
                before = process_info(path)
                if before['state'] != 'Z':
                    require(captured.get(int(pid)) != before['starttime'], 'captured_process_alive')
                    argv = (path/'cmdline').read_bytes()
                    require(not (1000 in before['uids'] and
                        (before['name'].startswith('steam') or before['name'] == 'ideck-steam'
                         or b'/home/ideck/.local/share/Steam/' in argv)), 'steam_process_alive')
                key = (pid, before['starttime'])
                if key in checked:
                    continue
                for fd in (path/'fd').iterdir():
                    try:
                        entry = fd.stat()
                    except FileNotFoundError:
                        continue  # FD closed; retained mappings are still checked below.
                    require(identity(entry) not in wanted, 'live_fd_reference')
                for row in (path/'maps').read_text().splitlines():
                    columns = row.split(None, 5)
                    require(len(columns) >= 5, 'proc_maps_invalid')
                    major, minor = (int(part, 16) for part in columns[3].split(':'))
                    require((os.makedev(major, minor), int(columns[4])) not in wanted, 'live_mapping_reference')
                require(process_stat(path)['starttime'] == before['starttime'], 'proc_identity_changed')
                checked.add(key)
            except (OSError, KeyError, ValueError) as error:
                if isinstance(error, FileNotFoundError) and process_gone(path):
                    continue
                raise Refused('proc_unreadable_or_changed') from None
        # Final inventory only reads stat identities, so PID1's short control
        # helpers need not stop spawning for a whole expensive status/FD pass.
        # A replacement PID is never treated as its already-scanned predecessor.
        pending = {}
        for path in proc.iterdir():
            if not path.name.isdecimal():
                continue
            try:
                key = (path.name, process_stat(path)['starttime'])
            except (OSError, KeyError, ValueError) as error:
                if isinstance(error, FileNotFoundError) and process_gone(path):
                    continue
                raise Refused('proc_unreadable_or_changed') from None
            if key not in checked:
                pending[path.name] = path
        if not pending:
            return
        paths = pending
    raise Refused('process_scan_did_not_converge')


def verify_object(directory, item):
    entry = os.stat(item['name'], dir_fd=directory, follow_symlinks=False)
    require(stat.S_ISREG(entry.st_mode) and entry.st_nlink == 1
            and identity(entry) == (item['device'], item['inode'])
            and entry.st_uid == item['uid'] and entry.st_size == item['size']
            and stat.S_IMODE(entry.st_mode) == item['mode'], 'shm_identity_changed')


def verify_set(directory, objects):
    present = {name for name in os.listdir(directory) if NAME.fullmatch(name)}
    require(present == {item['name'] for item in objects}, 'manifest_not_complete_for_current_names')
    for item in objects:
        verify_object(directory, item)


def recover(value, report):
    guard()
    objects, captured = validate_manifest(value, (PROC/'sys/kernel/random/boot_id').read_text().strip())
    # Open the existing user lock; never create/chown a substitute launcher lock.
    runtime = os.open(RUNTIME, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    directory = lock = None
    try:
        rs = os.fstat(runtime)
        require(rs.st_uid == 1000 and stat.S_IMODE(rs.st_mode) == 0o700, 'unsafe_runtime_directory')
        lock = os.open(LOCK, os.O_RDWR | os.O_NOFOLLOW, dir_fd=runtime)
        ls = os.fstat(lock)
        require(stat.S_ISREG(ls.st_mode) and ls.st_uid == 1000 and ls.st_nlink == 1
                and stat.S_IMODE(ls.st_mode) == 0o600, 'unsafe_launch_lock')
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        directory = os.open(SHM, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        ds = os.fstat(directory)
        require(ds.st_uid == 0 and stat.S_IMODE(ds.st_mode) == 0o1777, 'unsafe_shm_directory')
        require(all(item['device'] == ds.st_dev for item in objects), 'shm_device_changed')
        remaining = list(objects)
        verify_set(directory, remaining)
        scan_references(remaining, captured)
        report['preflight_passed'] = True
        while remaining:
            require(identity(os.stat(RUNTIME, follow_symlinks=False)) == identity(rs), 'runtime_directory_changed')
            require(identity(os.stat(LOCK, dir_fd=runtime, follow_symlinks=False)) == identity(ls), 'launch_lock_changed')
            require(identity(os.stat(SHM, follow_symlinks=False)) == identity(ds), 'shm_directory_changed')
            verify_set(directory, remaining)
            scan_references(remaining, captured)
            item = remaining[0]
            # Same directory FD and an immediately revalidated manifested inode.
            verify_object(directory, item)
            os.unlink(item['name'], dir_fd=directory)
            report['removed'].append(dict(item))
            remaining.pop(0)
        report['status'] = 'reclaimed_manifested_orphans'
        report['removed_bytes'] = sum(item['size'] for item in report['removed'])
    finally:
        for fd in (directory, lock, runtime):
            if fd is not None:
                os.close(fd)


def read_manifest(path, expected):
    require(re.fullmatch(r'[0-9a-f]{64}', expected), 'manifest_sha256_required')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and info.st_nlink == 1
                and not stat.S_IMODE(info.st_mode) & 0o022 and info.st_size <= 256*1024, 'unsafe_manifest')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            data = stream.read(256*1024+1)
        require(hashlib.sha256(data).hexdigest() == expected, 'manifest_hash_mismatch')
        return json.loads(data)
    finally:
        os.close(fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--result', required=True, type=Path)
    parser.add_argument('--confirm-orphan-cleanup', action='store_true', required=True)
    args = parser.parse_args()
    require(os.geteuid() == 0, 'guest_root_required')
    parent = args.result.parent.stat()
    require(parent.st_uid == 0 and not stat.S_IMODE(parent.st_mode) & 0o022, 'unsafe_result_directory')
    # Reserve a new output before any cleanup; later failure never overwrites evidence.
    fd = os.open(args.result, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    report = {'schema': 1, 'status': 'refused', 'manifest_sha256': args.manifest_sha256,
              'preflight_passed': False, 'removed': [], 'automatic': False}
    started = time.monotonic()
    try:
        recover(read_manifest(args.manifest, args.manifest_sha256), report)
    except Exception as error:
        report['reason'] = str(error) if isinstance(error, Refused) else type(error).__name__
        report['errno'] = getattr(error, 'errno', None)
    finally:
        report['seconds'] = round(time.monotonic()-started, 3)
        with os.fdopen(fd, 'w') as stream:
            json.dump(report, stream, indent=2); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    print(json.dumps(report, sort_keys=True))
    return 0 if report['status'] == 'reclaimed_manifested_orphans' else 1


if __name__ == '__main__':
    raise SystemExit(main())
