#!/usr/bin/env python3
"""Real production-kernel clone-only journal recovery and force-kill acceptance.

Only disposable lab copies. No owner image, no automatic fsck repair beyond
journal_only, no source promotion while any QEMU subprocess remains alive.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import select
import shutil
import socket
import subprocess
import struct
import time

import debian_rootfs as base
import gui_host_tools
import recovery_guest


def strict_header(path, image):
    with path.open('rb') as stream:
        stream.seek(1024); h=stream.read(1024)
    if len(h)!=1024: raise ValueError('short superblock')
    u16=lambda n:struct.unpack_from('<H',h,n)[0]
    u32=lambda n:struct.unpack_from('<I',h,n)[0]
    crc=0xffffffff
    for byte in h[:1020]:
        crc ^= byte
        for _ in range(8): crc=(crc>>1) ^ (0x82f63b78 if crc & 1 else 0)
    blocks=u32(4)+(u32(0x150)<<32);groups=(blocks+32767)//32768
    if (path.stat().st_size!=image['size_bytes'] or u16(0x38)!=0xef53 or u32(0x4c)!=1
        or h[0x175]!=1 or crc!=u32(1020) or h[0x68:0x78].hex()!=image['uuid'].replace('-','')
        or u32(0x5c)!=image['features']['compat'] or u32(0x60)!=image['features']['incompat']
        or u32(0x64)!=image['features']['ro_compat'] or u16(0x3a)!=1 or u32(0xe8)!=0 or u32(0x194)!=0
        or blocks!=image['size_bytes']//4096 or u32(0x14)!=0 or u32(0x18)!=2 or u32(0x1c)!=2
        or u32(0x20)!=32768 or u32(0x24)!=32768 or not 0<u32(0x28)<=32768
        or u32(0)!=groups*u32(0x28) or u16(0x58)!=256 or u16(0xfe)!=64
        or u32(0xe0)!=8 or u32(0xe4)!=0 or any(h[0xd0:0xe0])):
        raise ValueError('strict native-equivalent clean header rejected')
    return {'recover_bit':False,'state':u16(0x3a),'last_orphan':u32(0xe8),'error_count':u32(0x194),'checksum':'valid'}


class VM:
    def __init__(self, assets, host, work, out, recovery):
        out.mkdir(parents=True, exist_ok=False)
        self.out, self.logs, self.peers = out, [bytearray(), bytearray()], []
        servers = []
        for _ in range(2):
            s = socket.socket(); s.bind(('127.0.0.1', 0)); s.listen(1); s.settimeout(30); servers.append(s)
        initrd = assets/'initramfs-desktop.gz'
        raw = initrd.read_bytes()
        initrd = out/'runtime-initramfs'
        initrd.write_bytes(raw + b'\0'*(-len(raw)%4) + recovery_guest.suffix(recovery_guest.SCRIPT.read_bytes()))
        args = [host/'usr/bin/qemu-system-aarch64', '-L', host/'usr/share/qemu', '-machine', 'virt',
                '-cpu', 'cortex-a72', '-m', '1024', '-smp', '4', '-accel', 'tcg,thread=multi,tb-size=256',
                '-display', 'none', '-nodefaults', '-nic', 'none', '-no-reboot', '-kernel', assets/'vmlinuz-virt',
                '-initrd', initrd, '-append', 'console=ttyAMA0 panic=0 loglevel=4 rdinit='+('/ideck-recovery-init' if recovery else '/ideck-desktop-init')]
        if recovery:
            args += ['-drive', 'if=none,id=tools,format=raw,readonly=on,file='+str(assets/'gui-rootfs-v1.raw'),
                     '-device', 'virtio-blk-device,drive=tools,serial=ideck-recovery-tools']
        args += ['-drive', 'if=none,id=work,format=raw,cache=writethrough,file='+str(work),
                 '-device', 'virtio-blk-device,drive=work,serial=ideck-recovery-work',
                 '-device', 'virtio-gpu-pci,xres=800,yres=600', '-device', 'virtio-tablet-pci', '-device', 'virtio-keyboard-pci']
        for name, s in zip(('serial', 'control'), servers):
            args += ['-chardev', f'socket,id={name},host=127.0.0.1,port={s.getsockname()[1]}']
        args += ['-serial', 'chardev:serial', '-device', 'virtio-serial-pci', '-device', 'virtserialport,chardev=control,name=org.ideck.control']
        env = {'PATH': os.defpath, 'LC_ALL': 'C', 'QEMU_MODULE_DIR': str(host/'usr/lib/x86_64-linux-gnu/qemu')}
        self.err = (out/'qemu.log').open('wb')
        self.process = subprocess.Popen(gui_host_tools.command(host, args), env=env, stdout=self.err, stderr=subprocess.STDOUT)
        for s in servers:
            self.peers.append(s.accept()[0]); s.close()

    def pump(self):
        readable, _, _ = select.select(self.peers, [], [], .05)
        for peer in readable:
            data = peer.recv(65536)
            if data:
                index = self.peers.index(peer); self.logs[index].extend(data)
                with (self.out/('serial.log' if index == 0 else 'control.log')).open('ab') as f: f.write(data)
        if sum(map(len, self.logs)) > 4*1024**2: raise RuntimeError('guest log bound')

    def until(self, marker, seconds=180):
        deadline = time.monotonic()+seconds
        while marker not in self.logs[1]:
            self.pump()
            if b'IDECK_RECOVERY_FAILED:' in self.logs[1] or b'IDECK_DESKTOP_FAILED:' in self.logs[0]:
                raise RuntimeError('guest failed: '+self.logs[1].decode(errors='replace'))
            if self.process.poll() is not None or time.monotonic()>deadline: raise RuntimeError('guest stopped/timed out before '+repr(marker))

    def serial(self, command):
        self.peers[0].sendall(('\n'+command+' && echo RECOVERY_LAB_OK\n').encode())
        deadline = time.monotonic()+30
        while b'RECOVERY_LAB_OK' not in self.logs[0]:
            self.pump()
            if time.monotonic()>deadline: raise RuntimeError('serial command failed')
        self.logs[0].clear()

    def close(self, kill=False):
        if kill and self.process.poll() is None: self.process.kill()
        status = self.process.wait(timeout=30)
        for peer in self.peers: peer.close()
        self.err.close()
        return status


def run(assets, host, output, cycles):
    if cycles < 2: raise ValueError('at least two cycles required')
    if shutil.disk_usage(output.parent).free < (cycles+2)*1_342_177_280+256*1024**2: raise ValueError('insufficient disposable lab space')
    profile = json.loads((assets/'desktop-profile.json').read_text())
    for key in ('kernel', 'initramfs', 'rootfs'):
        item = profile[key]; path = assets/item['file']
        if path.stat().st_size != item['size'] or base.sha256(path) != item['sha256']: raise ValueError('immutable assets failed')
    output.mkdir(parents=True, exist_ok=False)
    active = output/'active.raw'; shutil.copyfile(assets/'gui-rootfs-v1.raw', active)
    result = {'schema': 1, 'status': 'failed', 'owner_image_accessed': False,
              'host_only': True, 'base_profile': profile, 'cycles': [], 'suffix_sha256': hashlib.sha256(recovery_guest.suffix(recovery_guest.SCRIPT.read_bytes())).hexdigest()}
    try:
        for index in range(1, cycles+1):
            vm = VM(assets, host, active, output/f'gui-{index}', False)
            try:
                vm.until(b'IDECK_DESKTOP_READY')
                checks = [f'test "$(cat /home/ideck/Documents/recovery-{previous}.txt)" = cycle-{previous}' for previous in range(1,index)]
                checks += [f'printf cycle-{index} > /home/ideck/Documents/recovery-{index}.txt', 'sync']
                vm.serial(' && '.join(checks))
            finally: status = vm.close(kill=True)
            if status != -9: raise RuntimeError('force-kill not reproduced')
            dirty = base.ext4_header(active)
            if not dirty['features']['incompat'] & 4: raise RuntimeError('expected actual mounted ext4 RECOVER state')
            original_hash = base.sha256(active)
            backup = output/f'original-{index}.raw'; work = output/'work.raw'
            shutil.copyfile(active, backup); shutil.copyfile(backup, work)
            if base.sha256(backup) != original_hash or base.sha256(work) != original_hash: raise RuntimeError('backup/copy hash mismatch')
            vm = VM(assets, host, work, output/f'recovery-{index}', True)
            try:
                vm.until(b'IDECK_RECOVERY_DONE')
                vm.until(b'IDECK_DESKTOP_CLEAN_UNMOUNT')
                status = vm.close()
            except BaseException:
                vm.close(kill=True); raise
            if status != 0 or base.sha256(active) != original_hash or base.sha256(backup) != original_hash: raise RuntimeError('recovery modified preserved original or failed')
            # QEMU subprocess has completely exited before validation/promotion.
            fsck = subprocess.run(gui_host_tools.command(host,[host/'usr/sbin/e2fsck','-fn',work]),capture_output=True,text=True)
            (output/f'fsck-{index}.log').write_text(fsck.stdout+fsck.stderr)
            if fsck.returncode != 0: raise RuntimeError('post-recovery readonly gate')
            clean_header = strict_header(work, profile['image'])
            os.replace(work, active)
            result['cycles'].append({'cycle':index,'forcekill_exit':-9,'dirty_header':dirty,
                'original_sha256':original_hash,'original_preserved':True,'recovery_exit':status,
                'post_fsck_exit':fsck.returncode,'prior_control_files_read_before_write':index-1,
                'strict_clean_header':clean_header,
                'control_markers':vm.logs[1].decode()})
        vm = VM(assets, host, active, output/'final-relaunch',False)
        try:
            vm.until(b'IDECK_DESKTOP_READY')
            vm.serial(' && '.join(f'test "$(cat /home/ideck/Documents/recovery-{i}.txt)" = cycle-{i}' for i in range(1,cycles+1)))
            vm.peers[1].sendall(b'IDECK_STOP_V1\n'); vm.until(b'IDECK_DESKTOP_CLEAN_UNMOUNT')
            if vm.close() != 0: raise RuntimeError('final relaunch stop failed')
        except BaseException:
            vm.close(kill=True); raise
        final_fsck=subprocess.run(gui_host_tools.command(host,[host/'usr/sbin/e2fsck','-fn',active]),capture_output=True,text=True)
        (output/'final-fsck.log').write_text(final_fsck.stdout+final_fsck.stderr)
        if final_fsck.returncode!=0:raise RuntimeError('final readonly fsck')
        result.update(status='pass',all_control_files_reopened=True,final_clean_stop=True,
                      final_fsck_exit=0,final_strict_header=strict_header(active,profile['image']))
        return result
    finally:
        (output/'receipt.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__ == '__main__':
    p=argparse.ArgumentParser(); p.add_argument('--assets',type=Path,required=True); p.add_argument('--host',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True); p.add_argument('--cycles',type=int,default=2)
    a=p.parse_args(); print(json.dumps(run(a.assets.resolve(),a.host.resolve(),a.output.resolve(),a.cycles),indent=2))
