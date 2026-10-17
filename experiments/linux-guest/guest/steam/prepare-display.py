#!/usr/bin/env python3
"""Recover only obsolete display :0 endpoints on an opted-in Steam copy.

Run once before Xorg, from the original Debian recovery root. Never touches
SHM, user data, the GUI payload, mounts, or the PID1 shutdown implementation.
"""
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import stat
import time

TMP = Path('/tmp')
PROC = Path('/proc')
LOCK = TMP/'.X0-lock'
SOCKET = TMP/'.X11-unix/X0'


class Refusal(Exception):
    pass


def fingerprint(s):
    return (s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_gid, s.st_nlink,
            s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def candidate(path, boot_ns, socket_file=False):
    try:
        s = path.lstat()
    except FileNotFoundError:
        return None
    kind = stat.S_ISSOCK if socket_file else stat.S_ISREG
    if (not kind(s.st_mode) or s.st_uid != 0 or s.st_nlink != 1
            or s.st_mtime_ns >= boot_ns-1_000_000_000
            or (not socket_file and (s.st_size > 32 or s.st_mode & 0o022))):
        raise Refusal('unsafe_or_current_boot_display_object: '+str(path))
    row = {'path': str(path), 'fingerprint': list(fingerprint(s)),
           'kind': 'socket' if socket_file else 'lock'}
    if not socket_file:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            if fingerprint(os.fstat(fd)) != fingerprint(s):
                raise Refusal('lock_changed_on_open')
            data = os.read(fd, 33)
            if not re.fullmatch(rb'\s*[1-9][0-9]{0,9}\s*', data):
                raise Refusal('unexpected_lock_content')
            row.update(pid=int(data), sha256=hashlib.sha256(data).hexdigest())
        finally:
            os.close(fd)
    return row


def assert_no_listener(address):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as probe:
        probe.settimeout(.25)
        try:
            probe.connect(address)
        except OSError as error:
            if error.errno in (errno.ENOENT, errno.ECONNREFUSED):
                return
            raise Refusal('display_probe_inconclusive') from error
        raise Refusal('live_display_listener')


def inspect_processes(rows):
    """Refuse a server, matching live socket, or open/map reference to the lock."""
    unix = (PROC/'net/unix').read_text()
    for line in unix.splitlines()[1:]:
        fields = line.split()
        if len(fields) >= 8 and fields[7] in (str(SOCKET), '@'+str(SOCKET)):
            raise Refusal('display_socket_in_kernel_table')
    lock_identity = next(((r['fingerprint'][0], r['fingerprint'][1])
                          for r in rows if r['kind'] == 'lock'), None)
    lock_pid = next((r['pid'] for r in rows if r['kind'] == 'lock'), None)
    owner = None
    for p in PROC.iterdir():
        if not p.name.isdecimal():
            continue
        try:
            comm = (p/'comm').read_text().strip()
            try:
                exe = os.readlink(p/'exe')
            except FileNotFoundError:
                exe = ''
            if comm.lower() in ('xorg', 'x', 'xwayland', 'xvfb', 'xephyr') or Path(exe).name.lower() in ('xorg', 'xwayland', 'xvfb', 'xephyr'):
                raise Refusal('live_x_server_process')
            if int(p.name) == lock_pid:
                owner = {'pid': lock_pid, 'comm': comm, 'exe': exe,
                         'interpretation': 'old PID now names a non-X process'}
            if lock_identity:
                for fd in (p/'fd').iterdir():
                    try:
                        s = fd.stat()
                    except FileNotFoundError:
                        continue
                    if (s.st_dev, s.st_ino) == lock_identity:
                        raise Refusal('live_lock_descriptor')
                for line in (p/'maps').read_text().splitlines():
                    fields = line.split(None, 5)
                    major, minor = (int(x, 16) for x in fields[3].split(':'))
                    if (os.makedev(major, minor), int(fields[4])) == lock_identity:
                        raise Refusal('live_lock_mapping')
        except FileNotFoundError:
            # An exiting process cannot retain ownership. Permission errors and
            # unknown failures propagate; they never authorize deletion.
            continue
    return owner


def recover(report):
    for parent in (TMP, SOCKET.parent):
        try:
            s = parent.lstat()
        except FileNotFoundError:
            if parent == SOCKET.parent:
                continue
            raise
        if not stat.S_ISDIR(s.st_mode) or s.st_uid != 0 or stat.S_IMODE(s.st_mode) != 0o1777:
            raise Refusal('unsafe_display_parent')
    boot_ns = time.time_ns()-int(time.clock_gettime(time.CLOCK_BOOTTIME)*1e9)
    rows = [r for r in (candidate(LOCK, boot_ns), candidate(SOCKET, boot_ns, True)) if r]
    report.update(boot_start_ns=boot_ns, candidates=rows, removed=[])
    if not rows:
        report['status'] = 'no_stale_objects'
        return
    report['reused_lock_pid'] = inspect_processes(rows)
    for address in (str(SOCKET), '\0'+str(SOCKET)):
        assert_no_listener(address)
    # Validate the complete set a second time immediately before mutation.
    inspect_processes(rows)
    for row in rows:
        if list(fingerprint(Path(row['path']).lstat())) != row['fingerprint']:
            raise Refusal('display_object_changed_before_cleanup')
    for row in rows:
        path = Path(row['path'])
        if list(fingerprint(path.lstat())) != row['fingerprint']:
            raise Refusal('display_object_changed_during_cleanup')
        path.unlink()
        report['removed'].append(str(path))
    report['status'] = 'obsolete_display_objects_removed'


def guard():
    cmdline = (PROC/'cmdline').read_text().split()
    current = os.stat('/')
    expected = os.stat(PROC/'1/root/sysroot')
    if (os.geteuid() != 0 or os.uname().release != '6.18.35-0-virt'
            or not {'ideck.steam_experiment=1', 'ideck.steam_disk_grow=1'} <= set(cmdline)
            or not (PROC/'1/root/ideck-steam-init').is_file()
            or (current.st_dev, current.st_ino) != (expected.st_dev, expected.st_ino)):
        raise Refusal('requires_original_opted_in_steam_guest_root')


def main():
    report = {'schema': 1, 'scope': 'Steam private copy, pre-Xorg display :0 only',
              'status': 'refused', 'shm_touched': False}
    try:
        guard()
        recover(report)
    except Exception as error:
        report.update(status='refused', error_class=type(error).__name__, reason=str(error))
        print('IDECK_STEAM_DISPLAY_RECOVERY='+json.dumps(report), flush=True)
        return 1
    output = Path('/run/ideck')
    output.mkdir(mode=0o700, exist_ok=True)
    (output/'display-recovery.json').write_text(json.dumps(report, indent=2)+'\n')
    print('IDECK_STEAM_DISPLAY_RECOVERY='+json.dumps(report), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
