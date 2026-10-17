"""Real cpio/strict-header checks plus wiring guards, not simulated GUI acceptance."""
import ast
import base64
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import recovery_guest
from check_gui_recovery import strict_header, serial_command, serial_result, output_gate, checked_image_digest, verify_checked_image
from test_terminal import swift_block


class GUIRecovery(unittest.TestCase):
    def test_generated_native_suffix_is_exact_deterministic_reviewed_cpio(self):
        script = recovery_guest.SCRIPT.read_bytes()
        suffix = recovery_guest.suffix(script)
        self.assertEqual((ROOT/'ios/LinuxRecoveryGuest.swift').read_text(), recovery_guest.swift(script))
        self.assertLess(len(suffix), 32768)
        files, offset = {}, 0
        while offset < len(suffix):
            self.assertEqual(suffix[offset:offset+6], b'070701')
            fields = [int(suffix[offset+6+i*8:offset+14+i*8],16) for i in range(13)]
            offset += 110
            name = suffix[offset:offset+fields[11]-1].decode(); offset += fields[11]; offset = (offset+3)//4*4
            data = suffix[offset:offset+fields[6]]; offset += fields[6]; offset = (offset+3)//4*4
            if name == 'TRAILER!!!': break
            self.assertEqual(fields[1],0o100444 if name.endswith('.awk') else 0o100755)
            self.assertEqual(fields[2:6],[0,0,1,0])
            self.assertNotIn(name,files);files[name]=data
        self.assertEqual(set(files),{'ideck-recovery-init','ideck-desktop-init','ideck-fsck-clean.awk','ideck-scope-head.awk'})
        self.assertEqual(files['ideck-recovery-init'],script)
        self.assertEqual(files['ideck-desktop-init'],recovery_guest.desktop_runtime())
        self.assertEqual(files['ideck-fsck-clean.awk'],recovery_guest.SCAN.read_bytes())
        self.assertEqual(files['ideck-scope-head.awk'],recovery_guest.HEAD.read_bytes())
        self.assertIn(b'run tmp dev/shm dev/pts dev sys proc',files['ideck-desktop-init'])
        self.assertIn(b'mode=1777,size=64m tmpfs /sysroot/tmp',files['ideck-desktop-init'])

    def test_guest_fsck_is_unmounted_and_kernel_cycle_has_scope_gates(self):
        script = recovery_guest.SCRIPT.read_text()
        self.assertIn('serial',script);self.assertIn('ideck-recovery-tools',script);self.assertIn('ideck-recovery-work',script)
        self.assertIn('mount -t ext4 -o ro,noload "/dev/$tools" /tools',script)
        self.assertIn('mount -t ext4 -o rw,noatime,nosuid,nodev,noexec "/dev/$work" /counter-sync',script)
        self.assertLess(script.index('awk -v eligible=1'),script.index('mount -t ext4 -o rw,noatime'))
        self.assertLess(script.index('umount /counter-sync'),script.rindex('check -f -n'))
        self.assertNotIn('chroot /counter-sync',script)
        self.assertIn('chroot /tools /usr/bin/env -i',script)
        self.assertIn('E2FSCK_CONFIG=/dev/null',script)
        self.assertIn('/usr/sbin/e2fsck "$@" "/dev/$work" 3>&-',script)
        for forbidden in ('fsck -y','check -y','debugfs','tune2fs','mkfs','/home/ideck','chroot /sysroot'):
            self.assertNotIn(forbidden,script)
        self.assertEqual(script.count('check -f -n'),3)
        self.assertEqual(script.count('check -p -E journal_only'),1)
        self.assertLess(script.index('set_target_mode ro 1'),script.index('check -f -n'))
        self.assertLess(script.index('check -p -E journal_only'),script.rindex('set_target_mode ro 1'))
        self.assertLess(script.index('[ "$verified" = 0 ]'),script.index('IDECK_RECOVERY_DONE'))
        self.assertLess(script.index('umount /tools ||'),script.index('IDECK_RECOVERY_DONE'))
        self.assertLess(script.index('awk -f /ideck-fsck-clean.awk'),script.index('IDECK_RECOVERY_SCAN_CLEAN'))

    def test_native_recovery_retains_lock_and_never_promotes_after_loop_return(self):
        store = (ROOT/'ios/LinuxGUIRecovery.swift').read_text()
        self.assertIn('specification.uuid == LinuxGUIProfile.uuid',store)
        self.assertIn('receipt.process != process',store)
        self.assertIn('LOCK_EX | LOCK_NB',store)
        self.assertIn('receipt.toolSeedSHA256 == toolSeedSHA256',store)
        self.assertIn('receipt.suffixSHA256 == LinuxRecoveryGuest.sha256',store)
        self.assertIn('receipt.scanClean == true',store)
        result = swift_block(store,'func recordResult(')
        for forbidden in ('renameat','hash(','validateSuperblock','closeUnused','unlink'):
            self.assertNotIn(forbidden,result)
        promotion = swift_block(store,'static func promotePending(')
        self.assertLess(promotion.index('validateSuperblock(fd: transaction.work'),promotion.index('renameat('))
        self.assertLess(promotion.index('try transaction.save()'),promotion.index('renameat('))
        self.assertIn('activeHash == checkedSHA256',promotion)
        self.assertIn('let checkedSHA256 = receipt.recoveredSHA256',promotion)
        self.assertIn('guard recoveredHash == checkedSHA256',promotion)
        self.assertNotIn('receipt.recoveredSHA256 =',promotion)
        self.assertIn('receipt?.recoveredSHA256 = imageSHA256',result)
        session = (ROOT/'ios/LinuxTerminalSession.swift').read_text()
        stop = swift_block(session,'private func finalizeIfClean()')
        self.assertIn('recovery.recordResult(',stop)
        self.assertNotIn('promotePending(',stop)
        self.assertNotIn('qemu_cleanup(',session)
        self.assertEqual(session.count('qemu_init('),1)
        self.assertIn('LinuxQEMUThreadLifetime.retainCurrentThread',session)
        self.assertIn('catch LinuxDesktopDisk.Invalid.needsRecovery',session)
        prepare = swift_block(session,'private func prepareRecovery(')
        self.assertIn('guard !enteredQEMU',prepare)

    def test_guest_final_full_image_digest_is_after_clean_scan_and_readonly(self):
        script=recovery_guest.SCRIPT.read_text()
        final=script[script.index('echo IDECK_RECOVERY_SCAN_CLEAN >&3'):]
        self.assertLess(final.index('sync || fail sync'),final.index('checked_hash=$(image_hash'))
        self.assertLess(final.index('cat /sys/block/"$work"/ro'),final.index('checked_hash=$(image_hash'))
        self.assertIn('$1==1342177280',final)
        self.assertIn('*[!0-9a-f]*',final)
        self.assertLess(final.index('IDECK_RECOVERY_IMAGE_SHA256:'),final.index('umount /tools'))
        after=final[final.index('IDECK_RECOVERY_IMAGE_SHA256:'):]
        self.assertNotIn('set_target_mode rw',after)
        self.assertNotIn('check ',after)
        function=script[script.index('image_hash() {'):script.index('header_snapshot() {')]
        self.assertIn('/bin/bash -o pipefail',function)
        self.assertIn('bs=1048576 iflag=fullblock | sha256sum',function)
        self.assertNotIn('skip=',function)

    def test_changed_byte_outside_superblock_cannot_use_checked_receipt(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'work.raw'
            path.write_bytes(bytes(65536))
            digest=hashlib.sha256(path.read_bytes()).hexdigest()
            control=('IDECK_RECOVERY_SCAN_CLEAN\nIDECK_RECOVERY_IMAGE_SHA256:'+digest+'\nIDECK_RECOVERY_DONE\n').encode()
            self.assertEqual(verify_checked_image(path,control),digest)
            with path.open('r+b') as stream:stream.seek(32768);stream.write(b'X')
            with self.assertRaisesRegex(RuntimeError,'differs from guest checked image'):verify_checked_image(path,control)
            for invalid in [control.replace(b'IDECK_RECOVERY_IMAGE_SHA256:',b'old:'),
                            control.replace(digest.encode(),digest.upper().encode()),
                            control.replace(b'IDECK_RECOVERY_DONE\n',b''),
                            control.replace(b'IDECK_RECOVERY_SCAN_CLEAN\n',b''),
                            control+control,control[::-1]]:
                with self.assertRaises(RuntimeError):checked_image_digest(invalid)

    def test_final_stop_runner_enforces_full_output_gate(self):
        source=(ROOT/'tools/check_gui_recovery.py').read_text()
        parsed=ast.parse(source)
        run=next(node for node in parsed.body if isinstance(node,ast.FunctionDef) and node.name=='run')
        final=next(node for node in ast.walk(run) if isinstance(node,ast.If) and 'final_fsck.returncode' in ast.unparse(node.test))
        self.assertIn('output_gate(final_fsck.stdout + final_fsck.stderr, active)',ast.unparse(final.test))

    def test_terminal_echo_partial_lines_and_failed_commands_never_satisfy_sync_receipt(self):
        nonce='0123456789abcdef0123456789abcdef'
        command,marker,failed=serial_command('printf canary > /tmp/lab-file && sync',nonce)
        self.assertNotIn(marker,command);self.assertNotIn(failed,command)
        self.assertIsNone(serial_result(command.encode(),marker,failed))
        self.assertIsNone(serial_result((marker+':EXIT:0').encode(),marker,failed))
        self.assertIsNone(serial_result(('prompt# '+marker+':EXIT:0\n').encode(),marker,failed))
        self.assertEqual(serial_result(('\x1b[0m\r\n'+marker+':EXIT:0\r\n').encode(),marker,failed),0)
        for line in (marker+':EXIT:1\n',failed+'\n'):
            with self.assertRaises(RuntimeError):serial_result(line.encode(),marker,failed)

    def test_full_output_gate_rejects_exit0_fix_no_and_every_unknown_diagnostic(self):
        normal='\n'.join(['e2fsck 1.47.2 (1-Jan-2025)',
            'Pass 1: Checking inodes, blocks, and sizes','Pass 2: Checking directory structure',
            'Pass 3: Checking directory connectivity','Pass 4: Checking reference counts',
            'Pass 5: Checking group summary information','/tmp/lab.raw: 21235/163840 files (0.3% non-contiguous), 215837/327680 blocks'])+'\n'
        self.assertEqual(output_gate(normal,Path('/tmp/lab.raw')),0)
        for extra in ('Free blocks count wrong (1, counted=2).\nFix? no\n',
                      'Free inodes count wrong (1, counted=2).\nFix? no\n','UNEXPECTED_PRIVATE_TEXT\n'):
            self.assertNotEqual(output_gate(normal+extra,Path('/tmp/lab.raw')),0)
        self.assertNotEqual(output_gate('',Path('/tmp/lab.raw')),0)
        self.assertNotEqual(output_gate(normal.replace('Pass 2: Checking directory structure\n',''),Path('/tmp/lab.raw')),0)

    def test_current_real_receipt_is_strict_refusal_old_acceptance_is_withdrawn(self):
        evidence=ROOT/'evidence/gui-recovery-20261017'
        old=json.loads((evidence/'receipt.json').read_text())
        self.assertEqual(old['status'],'withdrawn');self.assertFalse(old['acceptance'])
        current=json.loads((evidence/'strict-gate-receipt.json').read_text())
        self.assertEqual(current['status'],'blocked_verified');self.assertFalse(current['acceptance'])
        self.assertEqual(len(current['cycles']),2);self.assertTrue(current['pristine_positive_gate'])
        self.assertEqual(current['guest_script_sha256'],hashlib.sha256((evidence/'strict-guest-source.sh').read_bytes()).hexdigest())
        self.assertEqual(current['scan_source_sha256'],hashlib.sha256((evidence/'strict-scan-source.awk').read_bytes()).hexdigest())
        self.assertEqual(current['runner_sha256'],hashlib.sha256((evidence/'strict-runner-source.py').read_bytes()).hexdigest())
        for row in current['cycles']:
            self.assertFalse(row['promoted']);self.assertNotEqual(row['post_output_gate_exit'],0)
            self.assertTrue(row['sync_completed_before_kill']);self.assertTrue(row['readonly_control_file_verified'])
            self.assertTrue(all(r['marker_absent_from_input'] and r['complete_output_line'] and r['exit_status']==0
                                for r in row['serial_receipts']))

    def test_digest_real_acceptance_is_bound_to_current_sources_and_clean_output(self):
        r=json.loads((ROOT/'evidence/gui-recovery-20261017/digest-receipt.json').read_text())
        self.assertEqual(r['status'],'pass');self.assertEqual(len(r['cycles']),2)
        self.assertIn('OLD cloud seed46fea only',r['acceptance_scope'])
        self.assertEqual(r['suffix_sha256'],hashlib.sha256(recovery_guest.suffix(recovery_guest.SCRIPT.read_bytes())).hexdigest())
        for path,expected in r['source_inputs'].items():self.assertEqual(hashlib.sha256((ROOT/path).read_bytes()).hexdigest(),expected)
        for c in r['cycles']:
            self.assertEqual(c['post_fsck_exit'],0);self.assertTrue(c['original_preserved'])
            self.assertIn('IDECK_RECOVERY_SUMMARY_RECONCILED\n',c['control_markers'])
            self.assertIn('IDECK_RECOVERY_SCAN_CLEAN\n',c['control_markers'])
            self.assertEqual(checked_image_digest(c['control_markers'].encode()),c['guest_checked_image_sha256'])
            self.assertTrue(c['checked_image_hash_matched_before_promotion'])
            self.assertGreater(c['recovery_sampled_peak_rss_bytes'],0)
        self.assertEqual(r['final_output_gate_exit'],0)

    def test_header_scope_refuses_boot_uuid_state_and_feature_changes(self):
        fixture=json.loads((ROOT/'ios/tests/fixtures/desktop-ext4-superblock.json').read_text())
        before=bytearray(4096);before[1024:2048]=bytes.fromhex(fixture['header_hex'])
        def run(after,eligible=False):
            with tempfile.TemporaryDirectory() as tmp:
                a=Path(tmp)/'a';b=Path(tmp)/'b'
                a.write_text(' '.join(map(str,before))+'\n');b.write_text(' '.join(map(str,after))+'\n')
                args=['awk','-f',str(recovery_guest.HEAD)]
                if eligible:args+=['-v','eligible=1',str(a)]
                else:args += [str(a),str(b)]
                return subprocess.run(args,capture_output=True).returncode
        self.assertEqual(run(before,True),0)
        for offset in [1024+12,1024+16,1024+44,1024+48,1024+52,1024+376,1024+1020]:
            after=before.copy();after[offset]^=1;self.assertEqual(run(after),0)
        for offset in [0,4095,1024+58,1024+96,1024+104,1024+232,1024+404]:
            after=before.copy();after[offset]^=1;self.assertNotEqual(run(after),0)

    def test_counter_eligibility_is_separate_from_final_clean_gate_and_body_is_constrained(self):
        normal='\n'.join(['e2fsck 1.47.2 (1-Jan-2025)','Pass 1: Checking inodes, blocks, and sizes',
            'Pass 2: Checking directory structure','Pass 3: Checking directory connectivity','Pass 4: Checking reference counts',
            'Pass 5: Checking group summary information','Free blocks count wrong (10, counted=9).','Fix? no','',
            'Free inodes count wrong (20, counted=19).','Fix? no','',
            '/dev/vda: 1/100 files (0.0% non-contiguous), 100/200 blocks'])+'\n'
        def mode(text):return subprocess.run(['awk','-v','allow_counters=1','-f',str(recovery_guest.SCAN)],input=text,text=True,capture_output=True).returncode
        self.assertEqual(mode(normal),0);self.assertNotEqual(output_gate(normal,Path('/dev/vda')),0)
        self.assertNotEqual(mode(normal.replace('Free blocks count wrong','Free blocks count wrong for group #1')),0)
        self.assertNotEqual(mode(normal.replace('Fix? no','Fix? yes')),0)
        script=recovery_guest.SCRIPT.read_text()
        self.assertIn('pipefail',script);self.assertIn('iflag=skip_bytes,fullblock',script)
        self.assertEqual(script.count('$1==1342173184'),2)
        self.assertIn('[ "$scope_before" = "$1" ] || fail counter_scope',script)

    def test_bundled_seed_is_hash_verified_and_original_never_attached(self):
        profile = (ROOT/'ios/LinuxGUIProfile.swift').read_text()
        args = swift_block(profile,'func recoveryArguments(')
        self.assertIn('try checked(rootfs, assets: assets)',args)
        self.assertIn('readonly=on',args)
        self.assertIn('escaped(transaction.url)',args)
        self.assertLess(args.index('original.arguments('),args.index('LinuxRecoveryGuest.append('))
        normal = swift_block(profile,'func arguments(')
        self.assertLess(normal.index('original.arguments('),normal.index('LinuxRecoveryGuest.append('))
        self.assertNotIn('original.raw',args);self.assertNotIn('rootfs-v1.raw',args)
        guest = (ROOT/'ios/LinuxRecoveryGuest.swift').read_text()
        for guard in ('O_EXCL | O_NOFOLLOW','digest == expectedSHA256','expectedSize','32 * 1024 * 1024'):
            self.assertIn(guard,guest)

    def test_actual_swift_process_crash_regressions_are_mandatory(self):
        ci = (ROOT.parents[1]/'ci/check_linux_guest_profile.py').read_text()
        tree = ast.parse(ci)
        calls = {n.args[0].value:n.args[1] for n in ast.walk(tree) if isinstance(n,ast.Call)
                 and isinstance(n.func,ast.Name) and n.func.id=='run' and len(n.args)>1 and isinstance(n.args[0],ast.Constant)}
        for gate in ('mac-compile','ios-typecheck'):
            names={n.id for n in ast.walk(calls[gate]) if isinstance(n,ast.Name)}
            self.assertTrue({'recovery','recovery_guest'}.issubset(names))
        self.assertIn('"LINUX_GUI_RECOVERY_PASS"',ci)
        checks=(ROOT/'ios/tests/GUIRecoveryChecks.swift').read_text()
        for item in ('before_rename','after_rename','Invalid.space','Invalid.busy','--gui-recovery-promote',
                     'reject_changed','reject_receipt','4 * 1024 * 1024','recoveredSHA256 = nil'):
            self.assertIn(item,checks)

    def test_strict_gate_uses_real_mke2fs_header_and_refuses_dirty_and_checksum_damage(self):
        fixture=json.loads((ROOT/'ios/tests/fixtures/desktop-ext4-superblock.json').read_text())
        header=bytearray.fromhex(fixture['header_hex'])
        image={key:fixture[key] for key in ('size_bytes','uuid','features')}
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'unit.raw'
            with path.open('wb') as f:f.truncate(image['size_bytes']);f.seek(1024);f.write(header)
            self.assertEqual(strict_header(path,image)['state'],1)
            for offset in (0x60,0x3a,0xe8,0x194,0x80):
                changed=header.copy();changed[offset]^=4
                if offset != 0x80:
                    crc=0xffffffff
                    for b in changed[:1020]:
                        crc ^= b
                        for _ in range(8):crc=(crc>>1)^(0x82f63b78 if crc&1 else 0)
                    changed[1020:1024]=crc.to_bytes(4,'little')
                with path.open('r+b') as f:f.seek(1024);f.write(changed)
                with self.assertRaises(ValueError):strict_header(path,image)


if __name__=='__main__':unittest.main()
