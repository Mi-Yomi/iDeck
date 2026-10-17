#!/usr/bin/env python3
"""Diagnose Steam user namespaces; optionally launch in a real private root.

Run as guest root from the existing Debian recovery console. No sysctl, LSM,
seccomp, capability policy or sandbox setting is weakened. PID1 and its mounts
remain unchanged. The launch process creates no PID namespace; a short-lived
preflight child tests user/mount/PID/proc isolation before exiting. PID1's
existing Stop still reaches Steam. The Alpine initramfs root is never deleted.
"""
import argparse
import ctypes
import errno
import gzip
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys

CLONE_NEWNS = 0x00020000
CLONE_NEWUSER = 0x10000000
CLONE_NEWPID = 0x20000000
CLONE_NEWNET = 0x40000000
MS_MOVE = 8192
MS_REC = 16384
MS_PRIVATE = 1 << 18
LIBC = ctypes.CDLL(None, use_errno=True)
LIBC.unshare.argtypes = [ctypes.c_int]
LIBC.unshare.restype = ctypes.c_int
LIBC.mount.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_ulong, ctypes.c_void_p]
LIBC.mount.restype = ctypes.c_int


def text(path, limit=65536):
    try:
        with open(path, 'r') as stream:
            return stream.read(limit)
    except OSError as error:
        return {'errno': error.errno, 'class': type(error).__name__}


def identity(path):
    try:
        st = os.stat(path)
        return {'device': st.st_dev, 'inode': st.st_ino}
    except OSError as error:
        return {'errno': error.errno}


def namespace(path):
    try:
        return os.readlink(path)
    except OSError as error:
        return {'errno': error.errno}


def snapshot():
    status = text('/proc/self/status')
    keys = {'Name', 'Pid', 'PPid', 'Uid', 'Gid', 'CapInh', 'CapPrm', 'CapEff', 'CapBnd',
            'CapAmb', 'NoNewPrivs', 'Seccomp', 'Seccomp_filters'}
    selected = {line.split(':', 1)[0]: line.split(':', 1)[1].strip()
                for line in status.splitlines() if line.split(':', 1)[0] in keys} if isinstance(status, str) else status
    mounts = text('/proc/self/mountinfo')
    securityfs = [line for line in mounts.splitlines() if ' - securityfs ' in line] if isinstance(mounts, str) else mounts
    return {'uid': os.getuid(), 'gid': os.getgid(), 'root': identity('/'),
            'pid1_root': identity('/proc/1/root'), 'cwd': os.getcwd(),
            'mount_namespace': namespace('/proc/self/ns/mnt'),
            'pid1_mount_namespace': namespace('/proc/1/ns/mnt'),
            'user_namespace': namespace('/proc/self/ns/user'), 'status': selected,
            'uid_map': text('/proc/self/uid_map'), 'gid_map': text('/proc/self/gid_map'),
            'root_mounts': [line for line in mounts.splitlines() if len(line.split()) > 4
                            and line.split()[4] in ('/', '/proc', '/dev', '/dev/pts', '/dev/shm', '/run', '/sys')]
                           if isinstance(mounts, str) else mounts,
            'securityfs_mounts': securityfs,
            'limits_and_security': {path: text(path, 4096) for path in (
                '/proc/sys/user/max_user_namespaces', '/proc/sys/user/max_mnt_namespaces',
                '/proc/sys/user/max_pid_namespaces',
                '/proc/sys/kernel/unprivileged_userns_clone', '/sys/kernel/security/lsm',
                '/proc/self/attr/current')}}


def kernel_config():
    wanted = {'CONFIG_NAMESPACES', 'CONFIG_USER_NS', 'CONFIG_PID_NS', 'CONFIG_NET_NS',
              'CONFIG_UTS_NS', 'CONFIG_IPC_NS', 'CONFIG_CGROUP_NS', 'CONFIG_SECCOMP',
              'CONFIG_SECCOMP_FILTER', 'CONFIG_SECURITY_APPARMOR', 'CONFIG_SECURITY_SELINUX',
              'CONFIG_SECURITY_YAMA', 'CONFIG_LSM'}
    try:
        with gzip.open('/proc/config.gz', 'rt') as stream:
            data = stream.read(4 * 1024**2 + 1)
        if len(data) > 4 * 1024**2:
            return {'status': 'size_bound_exceeded'}
        rows = [line for line in data.splitlines()
                if line.split('=', 1)[0] in wanted or any(line == '# '+key+' is not set' for key in wanted)]
        return {'status': 'available', 'source': '/proc/config.gz', 'flags': rows}
    except OSError as error:
        return {'status': 'unavailable', 'errno': error.errno, 'class': type(error).__name__}


def native(label, function, *args, operations):
    ctypes.set_errno(0)
    result = function(*args)
    code = ctypes.get_errno() if result == -1 else 0
    operations.append({'operation': label, 'return': result, 'errno': code,
                       'errno_name': errno.errorcode.get(code)})
    if result == -1:
        raise OSError(code, label)


def outside_root(operations):
    os.chroot('/proc/1/root')
    os.chdir('/')
    operations.append({'operation': 'chroot_to_pid1_real_root', 'return': 0, 'errno': 0})


def private_root(operations):
    outside_root(operations)
    native('unshare_private_mount_namespace', LIBC.unshare, CLONE_NEWNS, operations=operations)
    native('recursive_private_propagation', LIBC.mount, None, b'/', None, MS_REC | MS_PRIVATE, None,
           operations=operations)
    os.chdir('/sysroot')
    # pivot_root cannot replace the initramfs rootfs. The switch_root mount move
    # creates the namespace's topmost root, without deleting Alpine or touching
    # PID1's original mount namespace. Merely pivoting a submount inside a chroot
    # does not establish this namespace-root invariant.
    native('move_debian_to_namespace_root', LIBC.mount, b'.', b'/', None, MS_MOVE, None,
           operations=operations)
    os.chroot('.')
    os.chdir('/')
    operations.append({'operation': 'adopt_namespace_root', 'return': 0, 'errno': 0})


def user1000():
    os.setgroups([])
    os.setgid(1000)
    os.setuid(1000)


def probe_one(root_mode, uid, flags):
    result = {'root_mode': root_mode, 'requested_uid': uid, 'unshare_flags': flags, 'operations': []}
    try:
        result['before'] = snapshot()
        if root_mode == 'outside':
            outside_root(result['operations'])
        elif root_mode == 'private-real-root':
            private_root(result['operations'])
        if uid == 1000:
            user1000()
        result['pre_unshare'] = snapshot()
        native('unshare_requested', LIBC.unshare, flags, operations=result['operations'])
        result['unshare_succeeded'] = True
        if flags & CLONE_NEWUSER:
            # Establish only the caller's own UID/GID map; this is the normal
            # userns protocol, not an expansion of the host/initial namespace.
            for path, value in (('/proc/self/setgroups', 'deny\n'),
                                ('/proc/self/uid_map', '0 '+str(uid)+' 1\n'),
                                ('/proc/self/gid_map', '0 '+str(uid)+' 1\n')):
                with open(path, 'w') as stream:
                    stream.write(value)
            result['self_mapping_succeeded'] = True
            if not flags & CLONE_NEWNS:
                native('unshare_mount_after_user', LIBC.unshare, CLONE_NEWNS, operations=result['operations'])
        result['after'] = snapshot()
        result['status'] = 'pass'
    except BaseException as error:
        result['status'] = 'failed'
        result['failure'] = {'class': type(error).__name__, 'errno': getattr(error, 'errno', None),
                             'phase': str(error)[:120]}
    return result


def path_access(uid):
    if uid == 1000:
        user1000()
    paths = ('/', '/usr', '/usr/bin', '/usr/bin/busybox', '/usr/lib',
             '/usr/lib/ld-musl-aarch64.so.1', '/lib', '/lib/ld-musl-aarch64.so.1',
             '/sysroot', '/sysroot/usr', '/sysroot/usr/bin', '/sysroot/usr/bin/unshare',
             '/sysroot/usr/lib', '/sysroot/usr/lib/aarch64-linux-gnu',
             '/sysroot/usr/lib/aarch64-linux-gnu/ld-linux-aarch64.so.1')
    rows = []
    for path in paths:
        row = {'path': path}
        try:
            info = os.stat(path)
            row.update(mode=oct(stat.S_IMODE(info.st_mode)), uid=info.st_uid, gid=info.st_gid,
                       readable=os.access(path, os.R_OK), searchable_or_executable=os.access(path, os.X_OK))
            if os.path.islink(path):
                row['link'] = os.readlink(path)
        except OSError as error:
            row.update(errno=error.errno, exception_class=type(error).__name__)
        rows.append(row)
    return {'uid': os.getuid(), 'gid': os.getgid(), 'paths': rows}


def exec_preflight(root_mode, pid_namespace=False):
    """Test a normal post-exec UID1000 process, not Python after setuid.

    setuid in an already running root process changes proc-file ownership via
    its nondumpable state. Exec of the ordinary unshare binary follows the same
    credential transition used for Steam, without changing dumpability policy.
    """
    if pid_namespace and root_mode not in ('private-real-root', 'inherited-private-real-root'):
        raise ValueError('PID/proc probe requires corrected Debian root')
    operations = []
    if root_mode == 'outside':
        outside_root(operations)
    elif root_mode == 'private-real-root':
        private_root(operations)
    env = {'PATH': '/usr/bin:/bin', 'HOME': '/home/ideck', 'USER': 'ideck',
           'LOGNAME': 'ideck', 'LANG': 'C.UTF-8'}
    credentials = {}
    if root_mode == 'outside':
        # Use Alpine's own musl-linked executable outside Debian, avoiding any
        # assumption that Debian binaries/libraries can be opened through
        # /sysroot after the exec. Child credentials are numeric and need no
        # Alpine passwd entry. The ordinary exec follows credential dropping.
        argv = ['/usr/bin/busybox', 'unshare', '-U', '-r', '-m', '/usr/bin/busybox', 'true']
        credentials = {'user': 1000, 'group': 1000, 'extra_groups': []}
    else:
        argv = ['/usr/bin/setpriv', '--reuid=1000', '--regid=1000', '--init-groups',
                '/usr/bin/unshare', '--user', '--map-root-user', '--mount']
        if pid_namespace:
            argv += ['--pid', '--fork', '--mount-proc']
        argv += ['/usr/bin/true']
    result = {'root_mode': root_mode, 'requested_uid': 1000, 'argv': argv,
              'pid_namespace_requested': pid_namespace,
              'operations': operations, 'before_exec': snapshot()}
    if root_mode == 'outside':
        result['path_access_root'] = path_access(0)
        result['path_access_uid1000'] = fork_report(path_access, 1000)
        result['child_credentials'] = credentials
    try:
        completed = subprocess.run(argv, env=env, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, timeout=20, close_fds=True, check=False, **credentials)
        result.update(exit_code=completed.returncode, stdout=completed.stdout,
                      stderr=completed.stderr,
                      status='pass' if completed.returncode == 0 else 'failed')
    except (OSError, subprocess.TimeoutExpired) as error:
        result.update(status='failed', failure={'class': type(error).__name__,
                      'errno': getattr(error, 'errno', None)})
    return result


def fork_report(function, *args):
    read_fd, write_fd = os.pipe()
    pid = os.fork()
    if pid == 0:
        os.close(read_fd)
        signal.alarm(25)
        try:
            result = function(*args)
            data = json.dumps(result, sort_keys=True).encode()
            with os.fdopen(write_fd, 'wb') as stream:
                stream.write(data)
                stream.flush()
        finally:
            os._exit(0)
    os.close(write_fd)
    with os.fdopen(read_fd, 'rb') as stream:
        data = stream.read(131073)
    _, status = os.waitpid(pid, 0)
    if not os.WIFEXITED(status) or os.WEXITSTATUS(status) != 0 or len(data) > 131072:
        return {'status': 'failed', 'child_wait_status': status}
    return json.loads(data)


def isolated(root_mode, uid, flags):
    return fork_report(probe_one, root_mode, uid, flags)


def guard():
    if os.geteuid() != 0:
        raise RuntimeError('guest root required')
    if os.uname().release != '6.18.35-0-virt':
        raise RuntimeError('only the pinned experimental guest is supported')
    if 'ideck.steam_experiment=1' not in Path('/proc/cmdline').read_text().split():
        raise RuntimeError('explicit Steam guest opt-in required')
    if not Path('/proc/1/root/ideck-steam-init').is_file():
        raise RuntimeError('expected Alpine Steam PID1 root missing')
    root = identity('/')
    if 'device' not in root or root != identity('/proc/1/root/sysroot'):
        raise RuntimeError('run from the original Debian chroot only')


def launch(mode):
    if mode not in ('desktop', 'big-picture'):
        raise ValueError('unsupported launch mode')
    operations = []
    before = snapshot()
    private_root(operations)
    rooted = snapshot()
    preflight = exec_preflight('inherited-private-real-root')
    if preflight.get('status') != 'pass':
        print('IDECK_NAMESPACE_LAUNCH_REFUSED='+json.dumps(preflight, sort_keys=True), flush=True)
        raise SystemExit(1)
    pid_preflight = exec_preflight('inherited-private-real-root', True)
    if pid_preflight.get('status') != 'pass':
        print('IDECK_NAMESPACE_LAUNCH_REFUSED='+json.dumps(pid_preflight, sort_keys=True), flush=True)
        raise SystemExit(1)
    print('IDECK_NAMESPACE_ROOT_READY='+json.dumps({'before': before, 'rooted': rooted,
          'operations': operations, 'uid1000_user_mount_preflight': preflight,
          'uid1000_user_mount_pid_proc_preflight': pid_preflight,
          'launch_pid_namespace_created': False, 'settings_changed': False}, sort_keys=True), flush=True)
    # No control FD or namespace handle survives in Steam. No retained root
    # process or PID namespace can obstruct PID1's existing kill/wait/unmount.
    os.closerange(3, 65536)
    env = {'PATH': '/usr/local/bin:/usr/bin:/bin', 'HOME': '/home/ideck', 'USER': 'ideck',
           'LOGNAME': 'ideck', 'LANG': 'C.UTF-8', 'DISPLAY': ':0',
           'XAUTHORITY': '/run/user/1000/Xauthority', 'XDG_RUNTIME_DIR': '/run/user/1000'}
    os.execve('/usr/bin/setpriv', ['setpriv', '--reuid=1000', '--regid=1000', '--init-groups',
               '/usr/local/bin/ideck-steam', mode], env)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('probe', 'launch'))
    parser.add_argument('mode', nargs='?', choices=('desktop', 'big-picture'))
    args = parser.parse_args()
    guard()
    if args.command == 'probe':
        cases = [(root, uid, flags) for root in ('inside-chroot', 'outside', 'private-real-root')
                 for uid, flags in ((0, CLONE_NEWNS), (0, CLONE_NEWUSER),
                                     (1000, CLONE_NEWUSER), (1000, CLONE_NEWUSER | CLONE_NEWNS))]
        report = {'schema': 1, 'kernel': os.uname().release, 'pid1_before': identity('/proc/1/root'),
                  'kernel_config': kernel_config(),
                  'cases': [isolated(*case) for case in cases],
                  'exec_cases': [fork_report(exec_preflight, root) for root in
                                 ('inside-chroot', 'outside', 'private-real-root')]
                                + [fork_report(exec_preflight, 'private-real-root', True)],
                  'settings_changed': False,
                  'steam_launched': False, 'launch_pid_namespace_created': False,
                  'child_pid_namespace_probe_requested': True}
        report['pid1_after'] = identity('/proc/1/root')
        print('IDECK_NAMESPACE_MATRIX='+json.dumps(report, sort_keys=True), flush=True)
        return
    if args.mode is None:
        parser.error('launch requires desktop or big-picture')
    launch(args.mode)


if __name__ == '__main__':
    main()
