"""Source/transition checks. Actual GUI acceptance remains the real system VM."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from typecheck_source import restore,overlay


class DesktopRoute(unittest.TestCase):
    def test_verified_vendor_modloop_is_binary_without_eol_conversion(self):
        path=ROOT/'vendor/alpine-3.24.1-aarch64/modloop-virt'
        from gui_bundle import metadata
        self.assertEqual(metadata(path),{'size':17670144,'sha256':'f969d12c8e23b486c8df651f04a4a9767f32fee16aed385c23462c31ea6cb47b'})
        result=subprocess.run(['git','check-attr','text','--',str(path)],cwd=ROOT.parents[1],capture_output=True,text=True,check=True,timeout=10)
        self.assertTrue(result.stdout.rstrip().endswith(': text: unset'))

    def test_separate_route_disk_control_and_existing_lifetime(self):
        session=(ROOT/'ios/LinuxTerminalSession.swift').read_text()
        self.assertIn('"iDeckDebianGUI-v1"',session)
        self.assertIn('"iDeckLinuxDesktop"',session)
        self.assertIn('IDECK_DESKTOP_',session)
        self.assertIn('IDECK_DESKTOP_RECOVERY_READY',session)
        self.assertIn('IDECK_DESKTOP_GUI_FAILED',session)
        self.assertIn('LinuxQEMUThreadLifetime.retainCurrentThread',session)
        self.assertIn('self.owner.desktopInput?.guestEnded()',session)
        self.assertLess(session.index('self.owner.desktopInput?.guestEnded()'),session.index('LinuxQEMUThreadLifetime.retainCurrentThread'))
        self.assertIn('desktopInput.prepareStop',session)
        inputs=(ROOT/'ios/LinuxDesktopInput.swift').read_text()
        self.assertIn('queue.async { self.deliver(events) }',inputs)
        self.assertIn('.milliseconds(250)',inputs) # Stop can bypass a stalled input/BQL queue.
        self.assertIn('gate.finish()',inputs)
        view=(ROOT/'ios/LinuxDesktopView.swift').read_text()
        self.assertIn('phase == .active && !recovery',view)
        self.assertIn('geometry.size.width > geometry.size.height',view)
        self.assertNotIn('qemu_cleanup(',session)
        view=(ROOT/'ios/LinuxProbeView.swift').read_text()
        self.assertIn('case .desktop: LinuxDesktopView()',view)
        self.assertIn('case .some(.desktop): return desktop',view)
        self.assertIn('LinuxDesktopView()',view)
        self.assertIn('case .terminal:',view);self.assertIn('case .debian:',view);self.assertIn('case .linux:',view)
        profile=(ROOT/'ios/LinuxGUIProfile.swift').read_text()
        self.assertIn('b66e1c8d-9cbf-45a7-b97b-dcc8f68efca7',profile)
        self.assertIn('O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC',profile)
        self.assertIn('1024 * 1024',profile)
        self.assertNotIn('readToEnd()',profile)
        self.assertIn('512 * 1024 * 1024',profile)

    def test_production_supervisor_mount_and_readiness_order(self):
        source=(ROOT/'guest/gui/ideck-desktop-init').read_text()
        self.assertIn('6.18.35-0-virt',source)
        self.assertIn('modprobe "$module"',source)
        self.assertIn('insmod /ideck/evdev.ko',source)
        self.assertIn('b66e1c8d-9cbf-45a7-b97b-dcc8f68efca7',source)
        self.assertLess(source.index('echo IDECK_DESKTOP_RECOVERY_READY'),source.index('echo IDECK_DESKTOP_READY'))
        self.assertLess(source.index('gui-ready'),source.index('echo IDECK_DESKTOP_READY'))
        self.assertLess(source.index('umount /sysroot'),source.index('echo IDECK_DESKTOP_CLEAN_UNMOUNT'))
        self.assertIn('run dev/shm dev/pts dev sys proc',source)
        self.assertIn('wait "$shell_pid"',source)
        self.assertIn('cd /home/ideck && exec /usr/local/lib/ideck/start',source)
        self.assertIn('IDECK_DESKTOP_KERNEL:$(uname -r)',source)
        self.assertNotIn('mkfs',source)

    @unittest.skipUnless(shutil.which('cc'),'existing C compiler required')
    def test_actual_new_c_bridge_body_clamps_pairs_and_bounds(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'source';restore(p);overlay(p)
            c=(p/'src/ios-jit/husk-display.c').read_text()
            start=c.index('bool husk_display_send_pointer_buttons(')
            body=c[start:c.index('\n}\n',start)+3]
            harness=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#define MAX(a,b) ((a)>(b)?(a):(b))
#define MIN(a,b) ((a)<(b)?(a):(b))
typedef struct {int unused;} QemuConsole;
typedef enum { INPUT_BUTTON_LEFT, INPUT_BUTTON_RIGHT, INPUT_BUTTON_MIDDLE, INPUT_BUTTON_WHEEL_UP, INPUT_BUTTON_WHEEL_DOWN } InputButton;
enum { INPUT_AXIS_X, INPUT_AXIS_Y };
static QemuConsole console;
static bool active=true,locked=false;
static int width=800,height=600,syncs,btns,xpos,ypos,downs,ups;
static void bql_lock(void){assert(!locked);locked=true;}
static void bql_unlock(void){assert(locked);locked=false;}
static QemuConsole *husk_input_console(void){assert(locked);return active?&console:NULL;}
static void husk_input_size(QemuConsole*c,int*w,int*h){(void)c;assert(locked);*w=width;*h=height;}
static void qemu_input_queue_abs(QemuConsole*c,int axis,int value,int low,int high){assert(c && locked && low==0 && high>0);if(axis==INPUT_AXIS_X)xpos=value;else ypos=value;}
static void qemu_input_queue_btn(QemuConsole*c,InputButton b,bool down){assert(c && locked);btns++;if(b==INPUT_BUTTON_WHEEL_UP||b==INPUT_BUTTON_WHEEL_DOWN){if(down)downs++;else ups++;}}
static void qemu_input_event_sync(void){assert(locked);syncs++;}
'''+body+r'''
int main(void){
 assert(husk_display_send_pointer_buttons(900,-5,7,2));assert(!locked&&xpos==799&&ypos==0&&btns==7&&syncs==5&&downs==2&&ups==2);
 assert(husk_display_send_pointer_buttons(10,20,0,-8));assert(!locked&&downs==10&&ups==10);
 int before=syncs;assert(!husk_display_send_pointer_buttons(0,0,8,0));assert(!husk_display_send_pointer_buttons(0,0,0,9));assert(syncs==before&&!locked);
 active=false;assert(!husk_display_send_pointer_buttons(0,0,0,0));assert(!locked&&syncs==before);
 active=true;width=0;assert(!husk_display_send_pointer_buttons(0,0,0,0));assert(!locked&&syncs==before);
 return 0;
}
'''
            src=Path(tmp)/'input.c';src.write_text(harness);binary=Path(tmp)/'input'
            subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror',str(src),'-o',str(binary)],check=True,capture_output=True,timeout=30)
            subprocess.run([str(binary)],check=True,timeout=10)
            integrate=(p/'scripts/integrate_husk.sh').read_text()
            self.assertIn('"husk_display_send_pointer_buttons",',integrate)

    @unittest.skipUnless(shutil.which('swiftc'),'Swift compiler unavailable; mandatory Apple checks remain pending')
    def test_actual_swift_input_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'main.swift').write_text('runDesktopInputChecks()\n')
            subprocess.run(['swiftc',str(ROOT/'ios/LinuxDesktopInputState.swift'),str(ROOT/'ios/tests/DesktopInputChecks.swift'),str(p/'main.swift'),'-o',str(p/'test')],check=True,capture_output=True,timeout=60)
            done=subprocess.run([str(p/'test')],check=True,capture_output=True,text=True,timeout=10)
            self.assertIn('LINUX_DESKTOP_INPUT_PASS',done.stdout)
