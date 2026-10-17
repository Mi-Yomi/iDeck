"""Exercise the actual shell capture with a deliberately unscheduled reader.

This checks descriptor readiness/error handling, not emulated input acceptance.
The latter still requires real system-QEMU wheel events in every GUI boot.
"""
import ast
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


def capture_commands(directory):
    tree=ast.parse((ROOT/'tools/check_gui_vm.py').read_text())
    commands={}
    for node in ast.walk(tree):
        if (isinstance(node,ast.Call) and isinstance(node.func,ast.Name)
                and node.func.id=='serial' and len(node.args)==2
                and isinstance(node.args[1],ast.Constant)
                and node.args[1].value in ('wheel_capture','wheel_events')):
            commands[node.args[1].value]=ast.literal_eval(node.args[0]).replace('/run/ideck',str(directory))
    # Keep the actual capture code, replacing only host-unavailable discovery.
    commands['wheel_capture']=commands['wheel_capture'].split('test -c "$tablet"',1)[1]
    commands['wheel_capture']='test -c "$tablet"'+commands['wheel_capture']
    return commands


@unittest.skipUnless(Path('/proc/self/fd').is_dir(),'Linux descriptor readiness regression')
class EvdevCaptureReadiness(unittest.TestCase):
    def test_ready_marker_requires_open_descriptor_before_delayed_reader(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);gate=root/'release';started=root/'reader-started'
            wrapper=root/'timeout'
            wrapper.write_text('''#!/bin/sh
test "$1" = 2 || exit 90
shift
: > "$READER_STARTED"
while [ ! -f "$READER_RELEASE" ]; do sleep 0.01; done
exec "$@"
''')
            wrapper.chmod(0o755)
            commands=capture_commands(root)
            script=('tablet=/dev/null; '+commands['wheel_capture']+
                    "; printf 'CAPTURE_READY\\n'; read release; "+commands['wheel_events']+
                    "; test ! -e /proc/$$/fd/4 && printf 'CAPTURE_CLOSED\\n'")
            env={**os.environ,'PATH':str(root)+os.pathsep+os.defpath,
                 'READER_STARTED':str(started),'READER_RELEASE':str(gate)}
            child=subprocess.Popen(['/bin/sh','-c',script],stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,text=True)
            try:
                self.assertEqual(child.stdout.readline(),'CAPTURE_READY\n')
                # Background timeout is still blocked; the parent has already
                # opened the character device before exposing the ready marker.
                self.assertEqual(os.readlink(f'/proc/{child.pid}/fd/4'),'/dev/null')
                self.assertFalse(gate.exists())
                gate.touch()
                stdout,stderr=child.communicate('release\n',timeout=5)
                self.assertEqual(child.returncode,0,stderr)
                self.assertIn('CAPTURE_CLOSED\n',stdout)
            finally:
                gate.touch(exist_ok=True)
                if child.poll() is None:
                    child.kill();child.wait()
                for stream in (child.stdin,child.stdout,child.stderr):
                    if stream:stream.close()

    def test_bad_device_never_reports_capture_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            commands=capture_commands(Path(tmp))
            result=subprocess.run(['/bin/sh','-c','tablet=/does-not-exist; '+commands['wheel_capture']+
                                   "; printf 'CAPTURE_READY\\n'"],capture_output=True,text=True,timeout=5)
            self.assertNotEqual(result.returncode,0)
            self.assertNotIn('CAPTURE_READY',result.stdout)
            self.assertFalse((Path(tmp)/'wheel.pid').exists())

    def test_reader_failure_cannot_be_hidden_by_hex_dump(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);wrapper=root/'timeout'
            wrapper.write_text('#!/bin/sh\nexit 7\n');wrapper.chmod(0o755)
            commands=capture_commands(root)
            script=('tablet=/dev/null; '+commands['wheel_capture']+'; '+commands['wheel_events']+
                    "; printf 'CAPTURE_ACCEPTED\\n'")
            result=subprocess.run(['/bin/sh','-c',script],capture_output=True,text=True,timeout=5,
                                  env={**os.environ,'PATH':str(root)+os.pathsep+os.defpath})
            self.assertNotEqual(result.returncode,0)
            self.assertNotIn('CAPTURE_ACCEPTED',result.stdout)
