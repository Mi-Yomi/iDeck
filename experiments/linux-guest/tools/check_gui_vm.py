#!/usr/bin/env python3
"""Run the real host-only GUI VM; production Alpine/iPhone gates remain separate."""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import select
import shlex
import socket
import subprocess
import struct
import time

import debian_rootfs as base
import gui_host_tools


def package_audit_script(audit_path='/run/ideck/dpkg-audit'):
    """Require both successful audit execution and genuinely empty stdout.

    A command substitution inside `test -z` discards dpkg's exit status. Capture
    to a file instead, preserve status immediately and check both explicitly.
    """
    path=shlex.quote(str(audit_path))
    return ('dpkg --configure -a && { dpkg --audit > '+path+'; '
            'ideck_audit_status=$?; printf "GUI_DPKG_AUDIT_STATUS:%s\\n" "$ideck_audit_status"; '
            'test "$ideck_audit_status" -eq 0 && test ! -s '+path+'; }')


def validate_loader_paths(paths):
    if (not isinstance(paths,list) or not paths or len(paths)>1024
            or any(not isinstance(p,str) or not p.startswith('/') or len(p)>1024
                   or any(c in p for c in ('\0','\n','\r')) or '..' in p.split('/') for p in paths)
            or len(set(paths))!=len(paths)):
        raise ValueError('invalid loader audit inventory')
    return paths


def boot(vm, output, provision=False, persistence=False, loader_inventory=None):
    prep=json.loads((vm/'preparation.json').read_text())
    production=prep.get('production_bootstrap') is True
    if production:
        from desktop_modules import KERNEL, KERNEL_SHA256
        if provision or prep['kernel_release']!=KERNEL or prep['kernel_sha256']!=KERNEL_SHA256:
            raise ValueError('invalid production GUI acceptance kernel')
    prefix=b'IDECK_DESKTOP_' if production else b'IDECK_GUI_HOST_'
    for path,digest in [(vm/'initramfs-gui-host.gz',prep['initramfs_sha256']),
                        (vm/'kernel/boot'/('vmlinuz-'+prep['kernel_release']),prep['kernel_sha256'])]:
        if base.sha256(path)!=digest:raise ValueError('immutable VM boot input differs from preparation')
    output.mkdir(parents=True,exist_ok=False)
    (output/'runner-source.py').write_bytes(Path(__file__).read_bytes())
    env={'PATH':os.defpath,'LC_ALL':'C','LD_LIBRARY_PATH':str(vm/'host/usr/lib/x86_64-linux-gnu'),
         'QEMU_MODULE_DIR':str(vm/'host/usr/lib/x86_64-linux-gnu/qemu')}
    servers=[]
    for _ in range(2):
        s=socket.socket();s.bind(('127.0.0.1',0));s.listen(1);s.settimeout(30);servers.append(s)
    qmp_path=output/'qmp.sock'
    args=[vm/'host/usr/bin/qemu-system-aarch64','-L',vm/'host/usr/share/qemu',
          '-machine','virt','-cpu','cortex-a72','-m','1024','-smp','4',
          '-accel','tcg,thread=multi,tb-size=256','-display','none','-nodefaults','-nic','none','-no-reboot',
          '-kernel',vm/'kernel/boot'/('vmlinuz-'+prep['kernel_release']),
          '-initrd',vm/'initramfs-gui-host.gz','-append',
          ('console=ttyAMA0 rdinit=/ideck-desktop-init panic=0 loglevel=4' if production else
           'console=ttyAMA0 rdinit=/ideck-gui-host-init panic=0 loglevel=4')+(' ideck.provision=1' if provision else ''),
          '-drive','if=none,id=root,format=raw,cache=writethrough,file='+str(vm/'scratch-gui.raw'),
          '-device','virtio-blk-device,drive=root',
          '-device','virtio-gpu-pci,xres=800,yres=600','-device','virtio-tablet-pci','-device','virtio-keyboard-pci',
          '-qmp','unix:'+str(qmp_path)+',server=on,wait=off']
    if not production:
        args+=['-drive','if=none,id=packages,format=raw,readonly=on,file='+str(vm/'packages.raw'),
               '-device','virtio-blk-device,drive=packages']
    for name,s in zip(('serial','control'),servers):
        args+=['-chardev',f'socket,id={name},host=127.0.0.1,port={s.getsockname()[1]}']
    args+=['-serial','chardev:serial','-device','virtio-serial-pci','-device','virtserialport,chardev=control,name=org.ideck.control']
    args=gui_host_tools.command(vm/'host',args); logs=[bytearray(),bytearray()]; peers=[]; qmp=None; qfile=None; process=None
    started=time.monotonic();peak=0;pump=None;command=None
    report={'schema':1,'status':'failed','host_only':True,'production_kernel_changed':False,
            'production_bootstrap':production,
            'rss_measurement':'maximum sampled QEMU VmHWM on Linux host; not iOS or guest process memory',
            'provision':provision,'persistence_boot':persistence,'argv':args,'preparation':prep,'runner_sha256':base.sha256(Path(__file__)),
            'host_tools_sha256':base.sha256(Path(gui_host_tools.__file__))}
    try:
        with (output/'qemu.log').open('wb') as log:
            process=subprocess.Popen(args,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
            peers=[s.accept()[0] for s in servers]
            for s in peers:s.setblocking(False)
            qmp=socket.socket(socket.AF_UNIX);qmp.settimeout(10);qmp.connect(str(qmp_path));qfile=qmp.makefile('rwb',buffering=0)
            json.loads(qfile.readline())
            def command(execute,arguments=None):
                qfile.write((json.dumps({'execute':execute,**({'arguments':arguments} if arguments is not None else {})})+'\n').encode())
                while True:
                    result=json.loads(qfile.readline())
                    if 'event' in result:continue
                    if 'error' in result:raise RuntimeError(str(result))
                    return result['return']
            command('qmp_capabilities')
            closed=set()
            def pump():
                nonlocal peak
                active=[p for p in peers if p not in closed]
                readable,_,_=select.select(active,[],[],0.05)
                for s in readable:
                    try:data=s.recv(65536)
                    except ConnectionResetError:data=b''
                    if data:
                        index=peers.index(s);logs[index].extend(data)
                        with (output/('serial-live.log' if index==0 else 'control-live.log')).open('ab') as live:live.write(data)
                    else:closed.add(s)
                try:
                    status=Path(f'/proc/{process.pid}/status').read_text()
                    for row in status.splitlines():
                        if row.startswith('VmHWM:'):peak=max(peak,int(row.split()[1])*1024)
                except FileNotFoundError:pass
                if sum(map(len,logs))>16*1024**2:raise RuntimeError('serial log bound')
            def until(predicate,seconds=180):
                deadline=time.monotonic()+seconds
                while not predicate():
                    pump()
                    if prefix+b'FAILED:' in logs[0]:raise RuntimeError('guest supervisor failed')
                    if process.poll() is not None and not predicate():
                        pump()
                        if not predicate():raise RuntimeError('QEMU exited before evidence')
                    if time.monotonic()>deadline:raise TimeoutError('VM acceptance deadline')
            if provision:
                # Local nested ext4/WSL storage can spend >10 minutes in real
                # dpkg fsync/maintainer scripts. This only enlarges provisioning
                # time; audit, clean unmount, QEMU exit and fsck stay mandatory.
                report['provision_deadline_seconds']=1800
                until(lambda:b'IDECK_GUI_PACKAGES_CONFIGURED\r\n' in logs[0],seconds=1800)
                report['package_configuration_verified']=True
                until(lambda:process.poll() is not None,seconds=30)
            else:
                until(lambda:prefix+b'READY\r\n' in logs[0])
                if production and (prefix+b'KERNEL:'+prep['kernel_release'].encode()+b'\r\n') not in logs[0]:
                    raise RuntimeError('production kernel version not observed')
                report['gui_mapped']=True
                command('screendump',{'filename':str(output/'desktop.png'),'format':'png'})
                # Genuine input must travel through QEMU's emulated keyboard.
                # Acceptance commands below inspect/save results from the guest.
                until(lambda:b'debian# ' in logs[0],seconds=20)
                peers[0].sendall(b"stty -echo; export DISPLAY=:0 XAUTHORITY=/run/ideck/Xauthority; printf '\\nRECOVERY_%s\\n' ready\n")
                until(lambda:b'RECOVERY_ready\r\n' in logs[0],seconds=20)
                def serial(script,tag):
                    # A delayed prompt can arrive after this log offset. Frame
                    # real output on a fresh line for anchored ID/evdev parsing.
                    begin=len(logs[0]); peers[0].sendall(("printf '\\n'; "+script+" && printf '\\nGUI_CHECK_%s\\n' "+shlex.quote(tag)+'\n').encode())
                    until(lambda:('GUI_CHECK_'+tag+'\r\n').encode() in logs[0][begin:],seconds=30)
                    return bytes(logs[0][begin:])
                if production:
                    data=serial('dbus-uuidgen --get=/etc/machine-id','machine_id')
                    ids=re.findall(rb'(?m)^([0-9a-f]{32})\r?$',data)
                    if len(ids)!=1:raise RuntimeError('invalid actual guest machine ID')
                    report['machine_id_sha256']=hashlib.sha256(ids[0]).hexdigest()
                serial(package_audit_script()+' && cat /run/ideck/windows && xrandr --current && ps -eo uid,pid,comm', 'audit')
                serial("test $(xdpyinfo | awk '/dimensions:/ {print $2}') = 800x600 && cat /var/log/Xorg.0.log && cat /proc/bus/input/devices && udevadm info -q property -n /dev/input/event0 && free -b", 'display_input_evidence')
                if loader_inventory:
                    inventory=json.loads(loader_inventory.read_text())
                    paths=validate_loader_paths(inventory['dynamic_executables'])
                    for offset in range(0,len(paths),20):
                        script='for path in '+shlex.join(paths[offset:offset+20])+'; do echo "LOADER_AUDIT:$path"; /lib/ld-linux-aarch64.so.1 --list "$path" >/run/ideck/loader-list || exit 1; done'
                        serial(script,'loader_'+str(offset))
                    report['actual_glibc_loader_executables_passed']=len(paths)
                    report['loader_inventory_sha256']=base.sha256(loader_inventory)
                serial("for name in openbox tint2 pcmanfm mousepad xterm; do pid=$(pgrep -xo $name) || exit 1; test $(awk '/^Uid:/ {print $2}' /proc/$pid/status) = 1000 || exit 1; done", 'client_uid')
                if production:
                    serial('test "$(readlink /proc/$(pgrep -xo xterm)/cwd)" = /home/ideck','terminal_home')
                serial("xdotool search --onlyvisible --class XTerm | head -1 > /run/ideck/xterm; xdotool windowactivate --sync $(cat /run/ideck/xterm)", 'focus')
                def key(name,down):
                    command('input-send-event',{'events':[{'type':'key','data':{'down':down,'key':{'type':'qcode','data':name}}}]})
                def text(value):
                    codes={' ':'spc','\n':'ret','-':'minus','/':'slash','.':'dot','>':'dot'}
                    for char in value:
                        shift=char.isupper() or char=='>'
                        code=codes.get(char,char.lower())
                        if shift:key('shift',True)
                        key(code,True);key(code,False)
                        if shift:key('shift',False)
                        time.sleep(0.01)
                if persistence:
                    serial('test "$(cat /home/ideck/Documents/check.txt)" = ideck-gui-persistence && test "$(cat /home/ideck/Documents/editor.txt)" = ideck-editor-persistence','persisted_before_write')
                    text('cat /home/ideck/Documents/check.txt\n')
                else:
                    text('echo ideck-gui-persistence > /home/ideck/Documents/check.txt\necho ideck-editor-start > /home/ideck/Documents/editor.txt\n')
                serial('i=0; until test "$(cat /home/ideck/Documents/check.txt 2>/dev/null)" = ideck-gui-persistence; do i=$((i+1)); test "$i" -lt 20 || exit 1; sleep 1; done','typed_saved')
                serial('test "$(stat -c %u:%g /home/ideck/Documents/check.txt)" = 1000:1000','file_owner')
                serial('w=$(cat /run/ideck/xterm); xdotool windowmove "$w" 80 65 windowsize --sync "$w" 560 320; xwininfo -id "$w"', 'moved_resized')
                geometries=[]
                def geometry():
                    data=serial('xdotool getwindowgeometry --shell $(cat /run/ideck/xterm)', 'geometry_'+str(len(geometries)))
                    value={name.decode():int(number) for name,number in re.findall(rb'(?m)^(X|Y|WIDTH|HEIGHT)=(\d+)\r?$',data)}
                    if set(value)!={'X','Y','WIDTH','HEIGHT'}:raise RuntimeError('missing actual X geometry')
                    geometries.append(value);return value
                def point(x,y):
                    command('input-send-event',{'events':[
                        {'type':'abs','data':{'axis':'x','value':max(0,min(32767,int(x*32767/799)))}},
                        {'type':'abs','data':{'axis':'y','value':max(0,min(32767,int(y*32767/599)))}}]})
                def button(name,down):
                    command('input-send-event',{'events':[{'type':'btn','data':{'button':name,'down':down}}]})
                def drag(x,y,button_name):
                    point(x,y);key('alt',True);time.sleep(0.15);button(button_name,True)
                    try:
                        time.sleep(0.1)
                        for step in range(1,9):point(x+step*5,y+step*3);time.sleep(0.025)
                    finally:
                        button(button_name,False);time.sleep(0.1);key('alt',False)
                    time.sleep(0.2)
                serial('xdotool windowactivate --sync $(cat /run/ideck/xterm) windowraise $(cat /run/ideck/xterm)', 'pointer_focus')
                time.sleep(0.5)
                before=geometry();drag(before['X']+120,before['Y']+80,'left');moved=geometry()
                command('screendump',{'filename':str(output/'after-pointer-move.png'),'format':'png'})
                if abs(moved['X']-before['X'])<15 or abs(moved['Y']-before['Y'])<10:
                    raise RuntimeError('emulated pointer did not move the real window')
                drag(moved['X']+moved['WIDTH']*0.8,moved['Y']+moved['HEIGHT']*0.8,'right');resized=geometry()
                if abs(resized['WIDTH']-moved['WIDTH'])<15 or abs(resized['HEIGHT']-moved['HEIGHT'])<10:
                    raise RuntimeError('emulated pointer did not resize the real window')
                report.update(emulated_pointer_move_resize=True,window_geometries=geometries)
                serial('tablet=$(for p in /sys/class/input/event*; do case "$(cat "$p/device/name")" in *"Virtio Tablet"*) echo /dev/input/${p##*/};; esac; done); test -c "$tablet"; timeout 2 cat "$tablet" > /run/ideck/wheel.events & echo $! > /run/ideck/wheel.pid','wheel_capture')
                time.sleep(0.1)
                for direction in ('wheel-up','wheel-down'):
                    button(direction,True);button(direction,False)
                data=serial('wait $(cat /run/ideck/wheel.pid) || test "$?" = 124; od -An -v -tx1 /run/ideck/wheel.events | sed "s/^/WHEEL_BYTES:/"','wheel_events')
                raw=bytes.fromhex(' '.join(row.decode() for row in re.findall(rb'(?m)^WHEEL_BYTES:([ 0-9a-f]+)\r?$',data)))
                if not raw or len(raw)%24:raise RuntimeError('invalid actual tablet evdev capture')
                events=[struct.unpack_from('<qqHHi',raw,i)[2:] for i in range(0,len(raw),24)]
                if (2,8,1) not in events or (2,8,-1) not in events:raise RuntimeError('virtual tablet wheel events missing')
                report['wheel_evdev_verified']=True
                def combo(*names):
                    for name in names:key(name,True)
                    for name in reversed(names):key(name,False)
                    time.sleep(0.2)
                serial('xdotool windowactivate --sync $(cat /run/ideck/xterm) windowraise $(cat /run/ideck/xterm)', 'editor_launch_terminal')
                text('mousepad /home/ideck/Documents/editor.txt\n')
                serial('i=0; while :; do w=$(xdotool search --all --onlyvisible --pid $(pgrep -xo mousepad) --name editor.txt | head -1); test -z "$w" || break; i=$((i+1)); test "$i" -lt 20 || exit 1; sleep 1; done; echo "$w" > /run/ideck/editor; xdotool windowactivate --sync "$w" windowraise "$w"', 'editor_file_loaded')
                time.sleep(0.3)
                if not persistence:
                    combo('ctrl','a');text('ideck-editor-persistence\n');combo('ctrl','s')
                    serial('i=0; until test "$(cat /home/ideck/Documents/editor.txt)" = ideck-editor-persistence; do i=$((i+1)); test "$i" -lt 20 || exit 1; sleep 1; done', 'editor_saved')
                serial('test "$(cat /home/ideck/Documents/editor.txt)" = ideck-editor-persistence && xdotool search --onlyvisible --name editor.txt', 'editor_reopened')
                serial('w=$(cat /run/ideck/editor); xdotool windowmove "$w" 20 270 windowsize "$w" 440 270; f=$(xdotool search --onlyvisible --class Pcmanfm | head -1); xdotool windowmove "$f" 430 40 windowsize "$f" 350 440', 'client_layout')
                serial('pgrep -xc xterm > /run/ideck/xterm-count','menu_baseline')
                point(790,540);button('right',True);button('right',False);time.sleep(0.3)
                command('screendump',{'filename':str(output/'desktop-menu.png'),'format':'png'})
                key('home',True);key('home',False);key('ret',True);key('ret',False)
                serial('i=0; until test "$(pgrep -xc xterm)" -gt "$(cat /run/ideck/xterm-count)"; do i=$((i+1)); test "$i" -lt 15 || exit 1; sleep 1; done','menu_launched_terminal')
                report['real_root_menu_launch']=True
                report['editor_file_loaded']=True
                report['editor_typed_saved']=not persistence
                report['editor_reopened_after_boot']=persistence
                command('screendump',{'filename':str(output/'after-input.png'),'format':'png'})
                peers[1].sendall(b'IDECK_STOP_V1\n')
                until(lambda:process.poll() is not None,seconds=30)
                report['keyboard_typed_saved']=not persistence
                report['keyboard_input_verified']=True
                report['persistence_read_before_write']=persistence
            pump()
            if process.wait()!=0 or prefix+b'CLEAN_UNMOUNT\r\n' not in logs[0]:
                raise RuntimeError('no clean VM stop')
            fsck=base.run(gui_host_tools.command(vm/'host',[vm/'host/usr/sbin/e2fsck','-fn',vm/'scratch-gui.raw']),env=env)
            (output/'fsck.log').write_text(fsck.stdout+fsck.stderr)
            stats=base.run(gui_host_tools.command(vm/'host',[vm/'host/usr/sbin/dumpe2fs','-h',vm/'scratch-gui.raw']),env=env).stdout
            (output/'filesystem.log').write_text(stats)
            fields=dict(row.split(':',1) for row in stats.splitlines() if ':' in row)
            block_size=int(fields['Block size']);blocks=int(fields['Block count']);free=int(fields['Free blocks'])
            manifest=base.run(gui_host_tools.command(vm/'host',[vm/'host/usr/sbin/debugfs','-R','cat /var/lib/ideck/package-manifest.tsv',vm/'scratch-gui.raw']),env=env).stdout
            (output/'package-manifest.tsv').write_text(manifest)
            expected=(vm/'packages/expected-packages.tsv').read_text()
            if manifest != expected:raise RuntimeError('persisted package manifest differs')
            report.update(status='pass',clean_unmount=True,qemu_exit=0,read_only_fsck=True,
                          used_block_bytes=(blocks-free)*block_size,free_block_bytes=free*block_size,
                          disk_sha256=base.sha256(vm/'scratch-gui.raw'))
    finally:
        if process and process.poll() is None and command is not None:
            try:command('screendump',{'filename':str(output/'failure.png'),'format':'png'})
            except (OSError,ValueError,RuntimeError):pass
        if process and process.poll() is None and len(peers)==2 and pump is not None:
            try:
                peers[1].sendall(b'IDECK_STOP_V1\n')
                deadline=time.monotonic()+15
                while process.poll() is None and time.monotonic()<deadline:pump()
                if prefix+b'CLEAN_UNMOUNT\r\n' in logs[0]:
                    report['cleanup_clean_unmount']=True
            except OSError:pass
        if process and process.poll() is None:
            process.kill();process.wait();report['forced_termination']=True
        if qfile:qfile.close()
        if qmp:qmp.close()
        for s in peers+servers:s.close()
        for name,data in zip(('serial','control'),logs):(output/(name+'.log')).write_bytes(data)
        report.update(elapsed_seconds=round(time.monotonic()-started,3),qemu_peak_rss_bytes=peak)
        (output/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--vm',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--provision',action='store_true')
    p.add_argument('--persistence',action='store_true')
    p.add_argument('--loader-inventory',type=Path)
    a=p.parse_args();print(json.dumps(boot(a.vm.resolve(),a.output.resolve(),a.provision,a.persistence,a.loader_inventory),indent=2))
