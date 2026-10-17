#!/usr/bin/env python3
"""Private host Steam experiment, never an Apple/app runtime acceptance gate.

The accepted GUI seed is a read-only qcow2 backing input. This runner owns one
new overlay, serial/control channels and a loopback-only verified-input server.
Commands in a private queue are explicit operator-controlled guest scripts.
"""
import argparse
import fcntl
import hashlib
import http.server
import json
import os
from pathlib import Path
import re
import select
import shlex
import socket
import subprocess
import threading
import time
import urllib.parse

import gui_host_tools

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def boot(args):
    profile_path = ROOT/'profiles/steam-host-experiment.json'
    profile = json.loads(profile_path.read_text())
    if (profile['disk']['kind'] != 'new-qcow2-overlay' or profile['disk']['reuse_dirty']
            or profile['network']['kind'] != 'qemu-user-nat' or profile['network']['host_forwarding']
            or profile['client_bundled'] or profile['app_route_enabled']):
        raise ValueError('unsafe experiment profile')
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    lockfile = (out/'owner.lock').open('xb')
    fcntl.flock(lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
    report = {'schema': 1, 'status': 'failed', 'host_only': True,
              'iphone_tested': False, 'steam_window_verified': False,
              'big_picture_verified': False, 'clean_shutdown': False,
              'network': 'explicit QEMU user NAT, no host forwarding', 'commands': []}
    report['profile_sha256'] = sha(profile_path)
    seed = args.seed.resolve()
    expected = json.loads((ROOT/'ipa/gui.lock.json').read_text())['files']
    for path, name in ((seed, 'gui-rootfs-v1.raw'), (args.kernel, 'vmlinuz-virt')):
        if path.stat().st_size != expected[name]['size'] or sha(path) != expected[name]['sha256']:
            raise ValueError('accepted GUI input differs: '+name)
    prep = json.loads((args.bootstrap/'bootstrap.json').read_text())
    initrd = args.bootstrap/'initramfs-steam.gz'
    if initrd.stat().st_size != prep['initramfs']['size'] or sha(initrd) != prep['initramfs']['sha256']:
        raise ValueError('Steam bootstrap differs from receipt')
    report['bootstrap'] = prep
    report['initramfs_sha256'] = sha(initrd)
    report['kernel_sha256'] = sha(args.kernel)
    report['seed_sha256'] = expected['gui-rootfs-v1.raw']['sha256']
    report['runner_sha256'] = sha(Path(__file__))
    disk = out/'steam-experiment.qcow2'
    env = {'PATH': os.defpath, 'LC_ALL': 'C', 'QEMU_MODULE_DIR': str(args.host/'usr/lib/x86_64-linux-gnu/qemu')}
    def host(argv):
        return gui_host_tools.command(args.host, argv)
    tool_receipt = json.loads(args.image_tool_receipt.read_text())
    if args.qemu_img.is_symlink() or sha(args.qemu_img) != tool_receipt['binary_sha256']:
        raise ValueError('image tool differs from authenticated extraction receipt')
    report['image_tool'] = tool_receipt
    loader = host([args.host/'usr/bin/qemu-system-aarch64'])[:-1]
    subprocess.run([*loader, str(args.qemu_img), 'create', '-f', 'qcow2', '-F', 'raw',
                    '-b', str(seed), str(disk), profile['disk']['virtual_size']], env=env, check=True)
    dirty = out/'needs-recovery'
    dirty.write_text('VM started; never reuse automatically\n')
    args.commands.mkdir(parents=True, exist_ok=True)
    allowed = {}
    for path in args.cache.iterdir():
        if path.is_file() and not path.is_symlink(): allowed['/client/'+path.name] = path
    for path in args.debs.iterdir():
        if path.is_file() and path.suffix == '.deb' and not path.is_symlink(): allowed['/debs/'+path.name] = path
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_GET(self):
            target = allowed.get(urllib.parse.unquote(self.path))
            if re.fullmatch(r'/commands/[0-9]{3}-[a-z0-9-]+\.sh', self.path):
                candidate = args.commands/self.path.rsplit('/', 1)[1]
                if candidate.is_file() and not candidate.is_symlink(): target = candidate
            if target is None:
                self.send_error(404); return
            self.send_response(200); self.send_header('Content-Length', str(target.stat().st_size)); self.end_headers()
            try:
                with target.open('rb') as stream:
                    while chunk := stream.read(1024*1024): self.wfile.write(chunk)
            except (BrokenPipeError, ConnectionResetError): pass
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    report['cache_port'] = server.server_port
    (out/'cache-port').write_text(str(server.server_port))
    listeners = []
    for _ in range(2):
        s = socket.socket(); s.bind(('127.0.0.1', 0)); s.listen(1); s.settimeout(30); listeners.append(s)
    port = socket.socket(); port.bind(('127.0.0.1', 0)); qport = port.getsockname()[1]; port.close()
    argv = [args.host/'usr/bin/qemu-system-aarch64', '-L', args.host/'usr/share/qemu',
            '-machine', 'virt', '-cpu', 'cortex-a72', '-m', str(profile['memory_mib']), '-smp', '4',
            '-accel', 'tcg,thread=multi,tb-size=256', '-display', 'none', '-nodefaults', '-no-reboot',
            '-kernel', args.kernel, '-initrd', initrd, '-append',
            'console=ttyAMA0 rdinit=/ideck-steam-init panic=0 loglevel=4 ideck.steam_experiment=1 ideck.steam_disk_grow=1',
            '-drive', 'if=none,id=root,format=qcow2,cache=writethrough,file='+str(disk),
            '-device', 'virtio-blk-device,drive=root', '-device', 'virtio-gpu-pci,xres=800,yres=600',
            '-device', 'virtio-tablet-pci', '-device', 'virtio-keyboard-pci',
            '-netdev', 'user,id=steamnet,ipv6=off', '-device', 'virtio-net-device,netdev=steamnet',
            '-qmp', f'tcp:127.0.0.1:{qport},server=on,wait=off']
    for name, s in zip(('serial', 'control'), listeners):
        argv += ['-chardev', f'socket,id={name},host=127.0.0.1,port={s.getsockname()[1]}']
    argv += ['-serial', 'chardev:serial', '-device', 'virtio-serial-pci',
             '-device', 'virtserialport,chardev=control,name=org.ideck.control']
    process = None; peers = []; logs = [bytearray(), bytearray()]; closed = set(); qmp = None; qfile = None
    started = time.monotonic()
    def save():
        report['elapsed_seconds'] = round(time.monotonic()-started, 3)
        (out/'result.json').write_text(json.dumps(report, indent=2)+'\n')
    def pump():
        readable, _, _ = select.select([p for p in peers if p not in closed], [], [], .1)
        for peer in readable:
            try: data = peer.recv(65536)
            except ConnectionResetError: data = b''
            if not data: closed.add(peer); continue
            index = peers.index(peer); logs[index].extend(data)
            with (out/('serial.log' if index == 0 else 'control.log')).open('ab') as stream: stream.write(data)
            if sum(map(len, logs)) > 32*1024**2: raise RuntimeError('guest log bound')
    def until(predicate, seconds):
        deadline = time.monotonic()+seconds
        while not predicate():
            pump()
            if process.poll() is not None:
                pump()
                if not predicate(): raise RuntimeError('QEMU exited before requested evidence')
            if time.monotonic() > deadline: raise TimeoutError('guest operation deadline')
    def qcommand(name, arguments=None):
        qfile.write((json.dumps({'execute': name, **({'arguments': arguments} if arguments else {})})+'\n').encode())
        while True:
            value = json.loads(qfile.readline())
            if 'event' in value: continue
            if 'error' in value: raise RuntimeError('QMP command rejected')
            return value['return']
    try:
        with (out/'qemu.log').open('wb') as output:
            process = subprocess.Popen(host(argv), env=env, stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT)
        peers = [s.accept()[0] for s in listeners]
        for peer in peers: peer.setblocking(False)
        qmp = socket.create_connection(('127.0.0.1', qport), timeout=10); qfile = qmp.makefile('rwb', buffering=0)
        json.loads(qfile.readline()); qcommand('qmp_capabilities')
        nodes = qcommand('query-named-block-nodes')
        backing = [node for node in nodes if node.get('drv') == 'raw' and node.get('file') == str(seed)]
        if len(backing) != 1 or backing[0].get('ro') is not True:
            raise RuntimeError('QEMU did not confirm read-only seed backing')
        report['seed_read_only_qmp'] = True
        (out/'block-nodes.json').write_text(json.dumps(nodes, indent=2)+'\n')
        (out/'runner-source.py').write_bytes(Path(__file__).read_bytes())
        until(lambda: b'IDECK_DESKTOP_READY\r\n' in logs[0], 240)
        report['gui_ready'] = True; save()
        until(lambda: b'debian# ' in logs[0], 20)
        peers[0].sendall(b"stty -echo; export DISPLAY=:0 XAUTHORITY=/run/ideck/Xauthority; printf '\\nSTEAM_RECOVERY_READY\\n'\n")
        until(lambda: b'STEAM_RECOVERY_READY\r\n' in logs[0], 20)
        print('STEAM_VM_READY cache_port='+str(server.server_port), flush=True)
        done = set()
        while not (args.commands/'STOP').exists():
            if time.monotonic()-started > args.seconds: raise TimeoutError('experiment time budget')
            for script in sorted(args.commands.glob('*.sh')):
                if script.name in done: continue
                if not re.fullmatch(r'[0-9]{3}-[a-z0-9-]+\.sh', script.name): raise ValueError('unsafe queued script name')
                begin = len(logs[0]); tag = 'STEAM_COMMAND_'+script.name[:3]+'_'
                url = f'http://10.0.2.2:{server.server_port}/commands/{script.name}'
                fetch = "import urllib.request;open('/run/ideck/steam-command.sh','wb').write(urllib.request.urlopen("+repr(url)+",timeout=20).read(65536))"
                line = 'python3 -c '+shlex.quote(fetch)+' && IDECK_CACHE_PORT='+str(server.server_port)+' /bin/sh /run/ideck/steam-command.sh; rc=$?; printf "\\n'+tag+'%s\\n" "$rc"\n'
                peers[0].sendall(line.encode())
                until(lambda: re.search(re.escape(tag.encode())+rb'[0-9]+\r\n', logs[0][begin:]), 900)
                chunk = bytes(logs[0][begin:]); status = int(re.search(re.escape(tag.encode())+rb'([0-9]+)\r\n', chunk)[1])
                (out/(script.stem+'.log')).write_bytes(chunk)
                report['commands'].append({'name': script.name, 'script_sha256': sha(script), 'exit_code': status})
                qcommand('screendump', {'filename': str(out/(script.stem+'.png')), 'format': 'png'})
                done.add(script.name); save(); print(tag+str(status), flush=True)
            pump()
        report['status'] = 'experiment_finished'
    except BaseException as error:
        report['failure'] = {'class': type(error).__name__, 'message': str(error)}
        raise
    finally:
        if process is not None and process.poll() is None and len(peers) == 2:
            try:
                peers[1].sendall(b'IDECK_STOP_V1\n')
                until(lambda: process.poll() is not None, 90)
                pump()
                if process.returncode == 0 and b'IDECK_DESKTOP_CLEAN_UNMOUNT\r\n' in logs[1]:
                    with disk.open('rb') as stream: os.fsync(stream.fileno())
                    report['clean_shutdown'] = True
                    dirty.unlink()
            except BaseException as error:
                report['stop_failure'] = type(error).__name__
        if process is not None and process.poll() is None:
            process.kill(); process.wait(); report['forced'] = True
        if process is not None: report['qemu_exit_code'] = process.returncode
        # Subprocess exit is mandatory; embedded iOS backend lifetime differs and
        # its existing retained owner/disk lock contract is intentionally untouched.
        save()
        for peer in peers+listeners: peer.close()
        if qfile: qfile.close()
        if qmp: qmp.close()
        server.shutdown(); server.server_close(); lockfile.close()
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('host', 'seed', 'kernel', 'bootstrap', 'cache', 'debs', 'commands', 'output', 'qemu-img', 'image-tool-receipt'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--seconds', type=int, default=1500)
    p.add_argument('--enable-experimental-network', action='store_true', required=True)
    a = p.parse_args()
    print(json.dumps(boot(a), indent=2))
