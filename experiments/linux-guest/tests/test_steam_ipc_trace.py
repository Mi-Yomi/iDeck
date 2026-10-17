import importlib.util
import io
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('ipc_trace',Path(__file__).resolve().parents[1]/'tools/trace_steam_ipc.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class TraceTests(unittest.TestCase):
    def info(self):
        return {'exe':str(m.ROOT/'steamrtarm64/steamwebhelper'),'uid':[1000]*4,'ppid':123,'argv':['steamwebhelper','-steampid=123','-force-sandbox']}
    def test_browser_excludes_children_and_other_clients(self):
        x=self.info();self.assertTrue(m.is_browser(x,123));self.assertFalse(m.is_browser(x,456))
        x['argv'].append('--type=renderer');self.assertFalse(m.is_browser(x,123))
        x=self.info();x['uid']=[0]*4;self.assertFalse(m.is_browser(x,123))
    def test_forked_assertion_dumper_with_identical_argv_is_not_browser(self):
        x=self.info();x['ppid']=456
        self.assertFalse(m.is_browser(x,123))
        x.pop('ppid');self.assertFalse(m.is_browser(x,123))
    def test_explicit_syscall_allowlist_no_buffer_or_child_capture(self):
        c=m.trace_command('/strace',[8,7,8])
        self.assertEqual(c[-4:],['-p','7','-p','8']);self.assertNotIn('-f',c)
        allowed=c[c.index('trace='+','.join(m.SYSCALLS))][6:].split(',')
        self.assertTrue({'futex','ftruncate','mmap'}.issubset(allowed))
        self.assertFalse({'read','write','readv','writev','send','sendto','recv','execve','execveat'}.intersection(allowed))
    def test_narrow_trace_only_reduces_existing_owned_threads(self):
        self.assertEqual(m.select_tids([8,7,9],None),[7,8,9])
        self.assertEqual(m.select_tids([8,7,9],[9,7]),[7,9])
    def test_unknown_duplicate_invalid_or_overwide_selection_refused(self):
        for requested in ([],[7,7],[1],[100],list(range(2,35))):
            with self.subTest(requested=requested), self.assertRaisesRegex(RuntimeError,'invalid_selected_threads'):
                m.select_tids(range(2,40),requested)
        for available in ([],range(2,259)):
            with self.assertRaisesRegex(RuntimeError,'invalid_thread_count'):
                m.select_tids(available,None)
    def test_force_sandbox_required(self):
        x={'exe':str(m.ROOT/'steamrtarm64/steam'),'uid':[1000]*4,'argv':['steam','-cef-force-sandbox']}
        m.validate_main(x);x['argv'].append('-cef-disable-sandbox')
        with self.assertRaisesRegex(RuntimeError,'sandbox_disable_argument'):m.validate_main(x)
        x['argv']=['steam']
        with self.assertRaisesRegex(RuntimeError,'force_sandbox_missing_native'):m.validate_main(x)
    def fake(self):
        code='import os,signal,sys,time\nsignal.signal(signal.SIGINT,lambda *_:sys.exit(0))\nwhile True: os.write(2,b"x"*4096)\n'
        return subprocess.Popen([sys.executable,'-c',code],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,start_new_session=True)
    def test_byte_cap_then_detach_never_signals_other_processes(self):
        p=self.fake()
        try:
            out=io.BytesIO();n,why,_=m.collect(p,out,3,8192,[False],reserve=0)
            self.assertEqual(n,8192);self.assertEqual(len(out.getvalue()),8192);self.assertEqual(why,'byte_limit')
            self.assertTrue(m.detach(p));self.assertIsNotNone(p.poll())
        finally:
            if p.poll() is None:p.terminate();p.wait(timeout=3)
            p.stderr.close()
    def test_interruption_detaches(self):
        p=self.fake()
        try:
            out=io.BytesIO();n,why,_=m.collect(p,out,3,8192,[True],reserve=0)
            self.assertEqual(n,0);self.assertEqual(why,'interrupted');self.assertTrue(m.detach(p))
        finally:
            if p.poll() is None:p.terminate();p.wait(timeout=3)
            p.stderr.close()
    def test_existing_output_refused(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as existing:
            with patch.object(sys, 'argv', ['trace-first-ipc.py','--main-pid','123','--output',existing]), patch.object(m.subprocess,'Popen') as launch:
                with self.assertRaises(FileExistsError):m.main()
                launch.assert_not_called()

if __name__=='__main__':unittest.main(verbosity=2)
