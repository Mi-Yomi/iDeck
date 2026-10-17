"""Guest-only namespace helper guards, with host syscalls mocked throughout.

These tests never create a namespace or change host credentials/mounts. Actual
inside/outside/private-root proof must come from the production-kernel guest.
"""
import ctypes
import errno
import importlib.util
import io
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if os.name == 'posix':
    spec = importlib.util.spec_from_file_location('steam_namespace', ROOT/'guest/steam/namespace-check.py')
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)


@unittest.skipUnless(os.name == 'posix', 'Linux guest helper requires POSIX syscall declarations')
class NamespaceHelper(unittest.TestCase):
    def test_private_propagation_precedes_move_then_adopts_real_root(self):
        calls = []
        def unshare(flags):
            calls.append(('unshare', flags)); return 0
        def mount(source, target, kind, flags, data):
            calls.append(('mount', source, target, flags)); return 0
        with mock.patch.object(helper.os, 'chroot', side_effect=lambda path: calls.append(('chroot', path))), \
             mock.patch.object(helper.os, 'chdir', side_effect=lambda path: calls.append(('chdir', path))), \
             mock.patch.object(helper.LIBC, 'unshare', side_effect=unshare), \
             mock.patch.object(helper.LIBC, 'mount', side_effect=mount):
            operations = []
            helper.private_root(operations)
        self.assertEqual(calls, [('chroot', '/proc/1/root'), ('chdir', '/'),
            ('unshare', helper.CLONE_NEWNS), ('mount', None, b'/', helper.MS_REC | helper.MS_PRIVATE),
            ('chdir', '/sysroot'), ('mount', b'.', b'/', helper.MS_MOVE),
            ('chroot', '.'), ('chdir', '/')])
        self.assertTrue(all(item['errno'] == 0 for item in operations))

    def test_failed_syscall_records_direct_errno_and_stops(self):
        def fail():
            ctypes.set_errno(errno.EPERM)
            return -1
        operations = []
        with self.assertRaises(OSError) as raised:
            helper.native('unshare_fixture', fail, operations=operations)
        self.assertEqual(raised.exception.errno, errno.EPERM)
        self.assertEqual(operations, [{'operation': 'unshare_fixture', 'return': -1,
                                      'errno': errno.EPERM, 'errno_name': 'EPERM'}])

    def test_uid_drop_removes_supplementary_groups_before_gid_uid(self):
        calls = []
        with mock.patch.object(helper.os, 'setgroups', side_effect=lambda value: calls.append(('groups', value))), \
             mock.patch.object(helper.os, 'setgid', side_effect=lambda value: calls.append(('gid', value))), \
             mock.patch.object(helper.os, 'setuid', side_effect=lambda value: calls.append(('uid', value))):
            helper.user1000()
        self.assertEqual(calls, [('groups', []), ('gid', 1000), ('uid', 1000)])

    def test_guard_refuses_nonroot_wrong_kernel_missing_profile_or_wrong_root(self):
        cases = [({'uid': 1000}, 'guest root'), ({'release': 'host-kernel'}, 'pinned'),
                 ({'cmdline': 'console=ttyAMA0'}, 'opt-in'), ({'pid1': False}, 'PID1'),
                 ({'identity': [{'device': 1, 'inode': 2}, {'device': 3, 'inode': 4}]}, 'chroot')]
        for changes, reason in cases:
            with self.subTest(changes=changes), \
                 mock.patch.object(helper.os, 'geteuid', return_value=changes.get('uid', 0)), \
                 mock.patch.object(helper.os, 'uname', return_value=SimpleNamespace(release=changes.get('release', '6.18.35-0-virt'))), \
                 mock.patch.object(helper.Path, 'read_text', return_value=changes.get('cmdline', 'ideck.steam_experiment=1')), \
                 mock.patch.object(helper.Path, 'is_file', return_value=changes.get('pid1', True)), \
                 mock.patch.object(helper, 'identity', side_effect=changes.get('identity', [{'device': 1, 'inode': 2}]*2)):
                with self.assertRaisesRegex(RuntimeError, reason):
                    helper.guard()

    def test_failed_uid1000_preflight_never_executes_client(self):
        with mock.patch.object(helper, 'snapshot', return_value={}), \
             mock.patch.object(helper, 'private_root'), \
             mock.patch.object(helper, 'exec_preflight', return_value={'status': 'failed', 'failure': {'errno': 1}}) as probe, \
             mock.patch.object(helper.os, 'execve') as execute, \
             mock.patch.object(helper.os, 'closerange') as close, \
             mock.patch('sys.stdout', new_callable=io.StringIO):
            with self.assertRaises(SystemExit) as raised:
                helper.launch('desktop')
        self.assertEqual(raised.exception.code, 1)
        probe.assert_called_once_with('inherited-private-real-root')
        execute.assert_not_called()
        close.assert_not_called()

    def test_successful_preflight_closes_fds_and_execs_unprivileged_launcher_only(self):
        with mock.patch.object(helper, 'snapshot', return_value={}), \
             mock.patch.object(helper, 'private_root'), \
             mock.patch.object(helper, 'exec_preflight', return_value={'status': 'pass'}), \
             mock.patch.object(helper.os, 'execve') as execute, \
             mock.patch.object(helper.os, 'closerange') as close, \
             mock.patch('sys.stdout', new_callable=io.StringIO):
            helper.launch('big-picture')
        close.assert_called_once_with(3, 65536)
        path, argv, env = execute.call_args.args
        self.assertEqual(path, '/usr/bin/setpriv')
        self.assertEqual(argv, ['setpriv', '--reuid=1000', '--regid=1000', '--init-groups',
                                '/usr/local/bin/ideck-steam', 'big-picture'])
        self.assertEqual(env['HOME'], '/home/ideck')
        self.assertEqual(env['XAUTHORITY'], '/run/user/1000/Xauthority')
        self.assertNotIn('LD_PRELOAD', env)

    def test_failed_pid_proc_preflight_never_executes_client(self):
        with mock.patch.object(helper, 'snapshot', return_value={}), \
             mock.patch.object(helper, 'private_root'), \
             mock.patch.object(helper, 'exec_preflight', side_effect=[{'status': 'pass'},
                 {'status': 'failed', 'exit_code': 1}]) as probe, \
             mock.patch.object(helper.os, 'execve') as execute, \
             mock.patch.object(helper.os, 'closerange') as close, \
             mock.patch('sys.stdout', new_callable=io.StringIO):
            with self.assertRaises(SystemExit):
                helper.launch('desktop')
        self.assertEqual(probe.call_args_list, [mock.call('inherited-private-real-root'),
                                               mock.call('inherited-private-real-root', True)])
        execute.assert_not_called()
        close.assert_not_called()

    def test_pid_proc_preflight_is_child_exec_only_with_corrected_root(self):
        with mock.patch.object(helper, 'snapshot', return_value={}), \
             mock.patch.object(helper, 'private_root') as root, \
             mock.patch.object(helper.subprocess, 'run', return_value=SimpleNamespace(
                 returncode=0, stdout='', stderr='')) as run:
            result = helper.exec_preflight('inherited-private-real-root', True)
        root.assert_not_called()
        self.assertEqual(run.call_args.args[0], ['/usr/bin/setpriv', '--reuid=1000',
            '--regid=1000', '--init-groups', '/usr/bin/unshare', '--user', '--map-root-user',
            '--mount', '--pid', '--fork', '--mount-proc', '/usr/bin/true'])
        self.assertTrue(result['pid_namespace_requested'])
        with mock.patch.object(helper, 'outside_root') as outside:
            with self.assertRaises(ValueError):
                helper.exec_preflight('outside', True)
        outside.assert_not_called()

    def test_exec_preflight_uses_normal_uid1000_exec_and_reports_exact_result(self):
        completed = SimpleNamespace(returncode=1, stdout='fixture output\n', stderr='fixture error\n')
        with mock.patch.object(helper, 'snapshot', return_value={}), \
             mock.patch.object(helper.subprocess, 'run', return_value=completed) as run, \
             mock.patch.object(helper, 'private_root') as root:
            result = helper.exec_preflight('inherited-private-real-root')
        root.assert_not_called()
        self.assertEqual(run.call_args.args[0], ['/usr/bin/setpriv', '--reuid=1000',
            '--regid=1000', '--init-groups', '/usr/bin/unshare', '--user', '--map-root-user',
            '--mount', '/usr/bin/true'])
        self.assertTrue(run.call_args.kwargs['close_fds'])
        self.assertEqual(result['exit_code'], 1)
        self.assertEqual(result['stdout'], 'fixture output\n')
        self.assertEqual(result['stderr'], 'fixture error\n')
        self.assertEqual(result['status'], 'failed')

    def test_outside_exec_uses_native_alpine_binary_after_numeric_uid_drop(self):
        with mock.patch.object(helper, 'snapshot', return_value={}), \
             mock.patch.object(helper, 'outside_root') as root, \
             mock.patch.object(helper, 'path_access', return_value={'uid': 0}) as paths, \
             mock.patch.object(helper, 'fork_report', return_value={'uid': 1000}) as child, \
             mock.patch.object(helper.subprocess, 'run', return_value=SimpleNamespace(
                 returncode=0, stdout='', stderr='')) as run:
            result = helper.exec_preflight('outside')
        root.assert_called_once()
        argv = run.call_args.args[0]
        self.assertEqual(argv, ['/usr/bin/busybox', 'unshare', '-U', '-r', '-m',
                                '/usr/bin/busybox', 'true'])
        self.assertEqual(run.call_args.kwargs['user'], 1000)
        self.assertEqual(run.call_args.kwargs['group'], 1000)
        self.assertEqual(run.call_args.kwargs['extra_groups'], [])
        paths.assert_called_once_with(0)
        child.assert_called_once_with(paths, 1000)
        self.assertEqual(result['path_access_uid1000'], {'uid': 1000})
        self.assertEqual(result['status'], 'pass')

    def test_arbitrary_launch_mode_refused_before_namespace_changes(self):
        with mock.patch.object(helper, 'private_root') as root:
            with self.assertRaises(ValueError):
                helper.launch('-no-cef-sandbox')
        root.assert_not_called()


if __name__ == '__main__':
    unittest.main()
