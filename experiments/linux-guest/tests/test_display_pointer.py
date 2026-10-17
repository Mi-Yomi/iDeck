"""Production pointer-state/overlay checks; not a guest GUI acceptance substitute."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from typecheck_source import restore,overlay


class DisplayPointerChecks(unittest.TestCase):
    def test_actual_pinned_view_releases_without_final_hit_test(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'source';restore(p);overlay(p)
            source=(p/'src/app/Husk/HuskMetalView.swift').read_text()
            for callback in ('touchesEnded','touchesCancelled'):
                body=source.split('override func '+callback,1)[1].split('\n    }',1)[0]
                self.assertIn('releasePointer()',body)
                self.assertNotIn('guestPoint',body)
                self.assertNotIn('touches.first',body)
            for trigger in ('willResignActiveNotification','didEnterBackgroundNotification',
                            'iDeck.releaseDisplayInput','if window == nil { releasePointer() }',
                            'drawableSizeWillChange size: CGSize) { releasePointer() }'):
                self.assertIn(trigger,source)
            session=(ROOT/'ios/LinuxTerminalSession.swift').read_text().split('    func stop() {',1)[1].split('\n    }',1)[0]
            self.assertLess(session.index('iDeck.releaseDisplayInput'),session.index('worker?.stop()'))
            self.assertEqual((p/'src/app/Husk/LinuxDisplayPointer.swift').read_bytes(),(ROOT/'ios/LinuxDisplayPointer.swift').read_bytes())

    def test_apple_gate_requires_actual_pointer_state_execution(self):
        gate=(ROOT.parents[1]/'ci/check_linux_guest_profile.py').read_text()
        self.assertIn('str(pointer), str(pointer_tests)',gate)
        self.assertIn('"LINUX_DISPLAY_POINTER_PASS"',gate)
        self.assertIn('runDisplayPointerChecks()', (ROOT/'ios/tests/main.swift').read_text())

    @unittest.skipUnless(shutil.which('swiftc'),'Swift compiler unavailable; mandatory Apple execution remains pending')
    def test_actual_swift_paired_release_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); main=root/'main.swift';main.write_text('runDisplayPointerChecks()\n')
            binary=root/'checks'
            subprocess.run(['swiftc',str(ROOT/'ios/LinuxDisplayPointer.swift'),
                            str(ROOT/'ios/tests/DisplayPointerChecks.swift'),str(main),'-o',str(binary)],check=True,capture_output=True,timeout=60)
            done=subprocess.run([str(binary)],check=True,capture_output=True,text=True,timeout=10)
            self.assertIn('LINUX_DISPLAY_POINTER_PASS',done.stdout)
