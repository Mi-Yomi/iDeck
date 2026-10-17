"""Fail-closed stale-X endpoint recovery; never runs against a host display."""
import errno
import importlib.util
import io
import os
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('steam_display', ROOT/'guest/steam/prepare-display.py')
display = importlib.util.module_from_spec(spec)
spec.loader.exec_module(display)


def metadata(**changes):
    values = dict(st_dev=2, st_ino=12, st_mode=stat.S_IFREG|0o444, st_uid=0,
                  st_gid=0, st_nlink=1, st_size=11, st_mtime_ns=10, st_ctime_ns=20)
    return SimpleNamespace(**{**values, **changes})


@unittest.skipUnless(os.name == 'posix', 'Linux guest endpoint checks')
class DisplayRecovery(unittest.TestCase):
    def test_missing_object_is_noop(self):
        path = mock.Mock()
        path.lstat.side_effect = FileNotFoundError
        self.assertIsNone(display.candidate(path, 2_000_000_000))

    def test_wrong_kind_owner_links_time_size_or_write_permissions_refused(self):
        for changes in ({'st_mode':stat.S_IFLNK|0o777}, {'st_uid':1000},
                        {'st_nlink':2}, {'st_mtime_ns':2_000_000_000},
                        {'st_size':33}, {'st_mode':stat.S_IFREG|0o666}):
            path=mock.Mock();path.lstat.return_value=metadata(**changes)
            with self.subTest(changes=changes), self.assertRaises(display.Refusal), mock.patch.object(display.os,'open') as opened:
                display.candidate(path, 2_000_000_000)
            opened.assert_not_called()

    def test_valid_old_lock_retains_hash_pid_and_exact_inode(self):
        path=mock.Mock();path.lstat.return_value=metadata()
        with mock.patch.object(display.os,'open',return_value=9) as opened, \
             mock.patch.object(display.os,'fstat',return_value=metadata()), \
             mock.patch.object(display.os,'read',return_value=b'       718\n'), \
             mock.patch.object(display.os,'close') as closed:
            row=display.candidate(path,2_000_000_000)
        self.assertEqual(row['pid'],718)
        self.assertEqual(row['fingerprint'],list(display.fingerprint(metadata())))
        self.assertEqual(len(row['sha256']),64)
        self.assertTrue(opened.call_args.args[1] & display.os.O_NOFOLLOW)
        closed.assert_called_once_with(9)

    def test_changed_lock_inode_and_bad_content_refused(self):
        for changed,data in ((True,b'718\n'),(False,b'not a PID'),(False,b'0\n')):
            path=mock.Mock();path.lstat.return_value=metadata()
            with mock.patch.object(display.os,'open',return_value=9), \
                 mock.patch.object(display.os,'fstat',return_value=metadata(st_ino=13) if changed else metadata()), \
                 mock.patch.object(display.os,'read',return_value=data), \
                 mock.patch.object(display.os,'close') as closed, self.assertRaises(display.Refusal):
                display.candidate(path,2_000_000_000)
            closed.assert_called_once_with(9)

    def test_live_listener_timeout_and_permission_error_refused(self):
        for error in (None,TimeoutError(),PermissionError(errno.EACCES,'denied')):
            probe=mock.MagicMock();probe.__enter__.return_value=probe
            probe.connect.side_effect=error
            with mock.patch.object(display.socket,'socket',return_value=probe), self.assertRaises(display.Refusal):
                display.assert_no_listener('/fixture/X0')

    def test_only_absent_or_refused_listener_permitted(self):
        for code in (errno.ENOENT,errno.ECONNREFUSED):
            probe=mock.MagicMock();probe.__enter__.return_value=probe
            probe.connect.side_effect=OSError(code,'fixture')
            with mock.patch.object(display.socket,'socket',return_value=probe):
                display.assert_no_listener('/fixture/X0')

    def recover_fixture(self, inspection_error=None, changed=False):
        row={'path':str(display.LOCK),'kind':'lock','pid':718,
             'fingerprint':list(display.fingerprint(metadata()))}
        calls=[]
        def lstat(path):
            if path in (display.TMP,display.SOCKET.parent):
                return metadata(st_mode=stat.S_IFDIR|0o1777)
            return metadata(st_ino=13) if changed else metadata()
        def inspect(rows):
            calls.append('inspect')
            if inspection_error:raise inspection_error
        report={}
        with mock.patch.object(Path,'lstat',lstat), \
             mock.patch.object(display,'candidate',side_effect=[row,None]), \
             mock.patch.object(display,'inspect_processes',side_effect=inspect), \
             mock.patch.object(display,'assert_no_listener',side_effect=lambda *_:calls.append('probe')), \
             mock.patch.object(Path,'unlink',side_effect=lambda:calls.append('unlink')):
            if inspection_error or changed:
                with self.assertRaises(display.Refusal):display.recover(report)
            else:display.recover(report)
        return report,calls

    def test_complete_checks_run_twice_before_unlink(self):
        report,calls=self.recover_fixture()
        self.assertEqual(calls,['inspect','probe','probe','inspect','unlink'])
        self.assertEqual(report['removed'],[str(display.LOCK)])

    def test_live_reference_or_object_swap_never_unlinked(self):
        for error,changed in ((display.Refusal('live_lock_descriptor'),False),(None,True)):
            report,calls=self.recover_fixture(error,changed)
            self.assertNotIn('unlink',calls)
            self.assertEqual(report['removed'],[])

    def test_kernel_socket_table_refuses_before_process_scan(self):
        with mock.patch.object(Path,'read_text',return_value='header\n000: 2 0 0 1 1 42 /tmp/.X11-unix/X0\n'), \
             mock.patch.object(Path,'iterdir') as scan, self.assertRaises(display.Refusal):
            display.inspect_processes([])
        scan.assert_not_called()

    def test_reused_pid_live_x_and_fd_or_map_owners_distinguished(self):
        for kind in ('reused_pid', 'server', 'descriptor', 'mapping'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                proc=Path(tmp)
                (proc/'net').mkdir();(proc/'net/unix').write_text('header\n')
                p=proc/'718';p.mkdir();(p/'fd').mkdir()
                (p/'comm').write_text('Xorg\n' if kind=='server' else 'udevd\n')
                (p/'maps').write_text('1000-2000 r--p 0000 00:02 12 /tmp/.X0-lock\n' if kind=='mapping' else '')
                if kind=='descriptor':(p/'fd/3').write_text('fixture')
                rows=[{'kind':'lock','pid':718,'fingerprint':list(display.fingerprint(metadata()))}]
                with mock.patch.object(display,'PROC',proc), \
                     mock.patch.object(display.os,'readlink',return_value='/usr/lib/xorg/Xorg' if kind=='server' else '/usr/lib/systemd/systemd-udevd'), \
                     mock.patch.object(Path,'stat',return_value=metadata()):
                    if kind=='reused_pid':
                        owner=display.inspect_processes(rows)
                        self.assertEqual(owner['pid'],718)
                        self.assertEqual(owner['comm'],'udevd')
                    else:
                        with self.assertRaises(display.Refusal):display.inspect_processes(rows)

    def test_guard_failure_never_reaches_recovery_or_writes_receipt(self):
        with mock.patch.object(display,'guard',side_effect=display.Refusal('not_guest')), \
             mock.patch.object(display,'recover') as recovery, \
             mock.patch.object(Path,'write_text') as write, mock.patch('sys.stdout',new=io.StringIO()):
            self.assertEqual(display.main(),1)
        recovery.assert_not_called();write.assert_not_called()

    def test_real_guard_requires_pinned_boot_optins_and_original_root(self):
        for case in ('allowed','uid','kernel','optin','pid1','root_device','root_inode'):
            with self.subTest(case=case), \
                 mock.patch.object(Path,'read_text',return_value='ideck.steam_experiment=1 ideck.steam_disk_grow=1' if case!='optin' else 'ideck.steam_experiment=1'), \
                 mock.patch.object(Path,'is_file',return_value=case!='pid1'), \
                 mock.patch.object(display.os,'geteuid',return_value=1000 if case=='uid' else 0), \
                 mock.patch.object(display.os,'uname',return_value=SimpleNamespace(release='wrong' if case=='kernel' else '6.18.35-0-virt')), \
                 mock.patch.object(display.os,'stat',side_effect=[metadata(),metadata(st_dev=3 if case=='root_device' else 2,st_ino=13 if case=='root_inode' else 12)]):
                if case=='allowed':display.guard()
                else:
                    with self.assertRaises(display.Refusal):display.guard()

    def test_untrusted_parent_refused_before_inspecting_candidates(self):
        with mock.patch.object(Path,'lstat',return_value=metadata(st_mode=stat.S_IFDIR|0o777)), \
             mock.patch.object(display,'candidate') as inspect, self.assertRaises(display.Refusal):
            display.recover({})
        inspect.assert_not_called()


if __name__=='__main__':unittest.main()
