"""Execute the real acceptance shell guard with dpkg fault fixtures.

These are command-failure regressions, not a mocked GUI acceptance gate. The
same guard must additionally succeed in two real system-QEMU desktop boots.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from check_gui_vm import package_audit_script


class GUIPackageAudit(unittest.TestCase):
    def run_case(self,configure_status,audit_status,audit_output):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);program=root/'dpkg';calls=root/'calls'
            program.write_text('''#!/bin/sh
case "$1" in
--configure) printf 'configure\\n' >> "$DPKG_CALLS"; exit "$DPKG_CONFIGURE_STATUS";;
--audit) printf 'audit\\n' >> "$DPKG_CALLS"; printf '%s' "$DPKG_AUDIT_OUTPUT"; exit "$DPKG_AUDIT_STATUS";;
*) exit 99;;
esac
''');program.chmod(0o755)
            # Quote-sensitive fixture path also exercises actual shell quoting.
            audit=root/"audit output's file"
            env=dict(os.environ,PATH=str(root)+os.pathsep+os.defpath,DPKG_CALLS=str(calls),
                     DPKG_CONFIGURE_STATUS=str(configure_status),DPKG_AUDIT_STATUS=str(audit_status),
                     DPKG_AUDIT_OUTPUT=audit_output)
            script=package_audit_script(audit)+" && printf 'GUI_CHECK_audit\\n'"
            result=subprocess.run(['/bin/sh','-c',script],env=env,capture_output=True,text=True,timeout=5)
            return result,calls.read_text(),audit.read_bytes() if audit.exists() else None

    def test_nonzero_audit_with_empty_stdout_cannot_emit_acceptance_marker(self):
        for status in (1,2,17):
            with self.subTest(status=status):
                result,calls,output=self.run_case(0,status,'')
                self.assertNotEqual(result.returncode,0)
                self.assertNotIn('GUI_CHECK_audit',result.stdout)
                self.assertIn('GUI_DPKG_AUDIT_STATUS:'+str(status),result.stdout)
                self.assertEqual(calls,'configure\naudit\n');self.assertEqual(output,b'')

    def test_zero_status_requires_byte_empty_output(self):
        for text in ('problem\n','\n',' '):
            with self.subTest(output=text):
                result,calls,output=self.run_case(0,0,text)
                self.assertNotEqual(result.returncode,0)
                self.assertNotIn('GUI_CHECK_audit',result.stdout)
                self.assertEqual(output,text.encode())
        result,calls,output=self.run_case(0,0,'')
        self.assertEqual(result.returncode,0);self.assertEqual(output,b'')
        self.assertIn('GUI_CHECK_audit\n',result.stdout)
        self.assertIn('GUI_DPKG_AUDIT_STATUS:0\n',result.stdout)

    def test_configure_failure_skips_audit_and_acceptance(self):
        result,calls,output=self.run_case(23,0,'')
        self.assertEqual(result.returncode,23)
        self.assertEqual(calls,'configure\n');self.assertIsNone(output)
        self.assertNotIn('GUI_CHECK_audit',result.stdout)
        self.assertNotIn('GUI_DPKG_AUDIT_STATUS',result.stdout)
