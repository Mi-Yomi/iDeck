#!/usr/bin/env python3
"""Private host Steam experiment, never an Apple/app runtime acceptance gate.

The accepted GUI seed is a read-only qcow2 backing input. This runner owns one
new overlay, serial/control channels and a loopback-only verified-input server.
Commands in a private queue are explicit operator-controlled guest scripts.
"""
import argparse
from contextlib import ExitStack
import fcntl
import hashlib
import http.server
import json
import os
from pathlib import Path
import re
import select
import shlex
import shutil
import socket
import stat
import subprocess
import threading
import time
import urllib.parse

import gui_host_tools

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        # Large sequential reads keep task-local Windows/WSL storage practical.
        while chunk := stream.read(8*1024*1024): digest.update(chunk)
    return digest.hexdigest()


def clean_stop_evidence(exit_code, control_bytes):
    return (type(exit_code) is int and exit_code == 0
            and b'IDECK_DESKTOP_CLEAN_UNMOUNT' in control_bytes.splitlines())


def finalize_disk(report, disk, dirty):
    if report.get('stop_failure'):
        return False
    try:
        with disk.open('rb') as stream: os.fsync(stream.fileno())
        dirty.unlink()
    except OSError as error:
        report['clean_shutdown'] = False
        report['stop_failure'] = type(error).__name__
        raise
    report['clean_shutdown'] = True
    return True


def validate_continuation(source, seed_hash):
    """Only an explicitly selected, clean private run can seed a NEW copy."""
    if source.is_symlink() or not source.is_dir():
        raise ValueError('continuation must be a real private run directory')
    for name in ('result.json', 'owner.lock', 'steam-experiment.qcow2'):
        entry = source/name
        if entry.is_symlink() or not stat.S_ISREG(entry.stat().st_mode):
            raise ValueError('unsafe continuation input')
    if os.path.lexists(source/'needs-recovery'):
        raise ValueError('dirty continuation refused; recovery is never automatic')
    prior = json.loads((source/'result.json').read_text())
    if (prior.get('host_only') is not True or prior.get('clean_shutdown') is not True
            or type(prior.get('qemu_exit_code')) is not int or prior['qemu_exit_code'] != 0
            or prior.get('forced') or prior.get('seed_sha256') != seed_hash):
        raise ValueError('continuation lacks matching clean private-run evidence')
    return source/'steam-experiment.qcow2'


def exclusive_image_output(image_command, arguments, destination, env):
    """Pin a newly created output inode; image tools cannot follow a substituted path."""
    descriptor = os.open(destination, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        subprocess.run([*image_command, *map(str, arguments), f'/proc/self/fd/{descriptor}'],
                       env=env, pass_fds=(descriptor,), check=True, capture_output=True, text=True)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def continuation_copy(source, disk, seed, seed_hash, image_command, env):
    original = validate_continuation(source, seed_hash)
    if os.path.lexists(disk): raise FileExistsError(disk)
    with (source/'owner.lock').open('rb') as owner:
        fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
        validate_continuation(source, seed_hash)
        def image(*argv):
            return subprocess.run([*image_command, *map(str, argv)], env=env,
                                  check=True, capture_output=True, text=True)
        chain = json.loads(image('info', '--backing-chain', '--output=json', original).stdout)
        if (len(chain) != 2 or chain[0]['format'] != 'qcow2' or chain[1]['format'] != 'raw'
                or Path(chain[1]['filename']).resolve() != seed or chain[0].get('encrypted')):
            raise ValueError('continuation backing chain differs from accepted seed')
        if shutil.disk_usage(disk.parent).free < chain[0]['virtual-size'] + 4*1024**3:
            raise ValueError('insufficient space for continuation copy')
        before = sha(original)
        # qemu-img holds its source backend read lock; no force-share or repair.
        exclusive_image_output(image_command,
            ['convert', '-f', 'qcow2', '-O', 'qcow2', '-B', seed, '-F', 'raw', original], disk, env)
        if sha(original) != before:
            raise ValueError('continuation source changed during copy')
        with disk.open('rb') as stream: os.fsync(stream.fileno())
        return {'source': str(source), 'source_sha256': before,
                'original_preserved': True, 'method': 'qemu-img convert; source read lock',
                'copied_sha256': sha(disk)}


def offline_fsck(disk, out, image_command, env):
    """Check a flattened point-in-time copy, only before this runner starts QEMU."""
    raw = out/'offline-fsck.raw'
    if os.path.lexists(raw): raise FileExistsError(raw)
    image_info = subprocess.run([*image_command, 'info', '--output=json', str(disk)],
                                env=env, check=True, capture_output=True, text=True)
    virtual_size = json.loads(image_info.stdout)['virtual-size']
    if type(virtual_size) is not int or virtual_size <= 0:
        raise ValueError('invalid offline filesystem copy size')
    # The continuation qcow2 already occupies space here. Budget a full raw
    # image independently; sparse extents are an optimization, not a guarantee.
    free_before = shutil.disk_usage(out).free
    if free_before < virtual_size + 4*1024**3:
        raise ValueError('insufficient space for offline filesystem copy and reserve')
    exclusive_image_output(image_command, ['convert', '-f', 'qcow2', '-O', 'raw', disk], raw, env)
    result = subprocess.run(['/usr/sbin/e2fsck', '-f', '-n', str(raw)],
                            env=env, capture_output=True, text=True)
    log = result.stdout+result.stderr
    (out/'offline-fsck.log').write_text(log)
    receipt = {'exit_code': result.returncode, 'read_only': True, 'writer_running': False,
               'free_bytes_before_copy': free_before, 'virtual_size': virtual_size,
               'raw_sha256': sha(raw), 'raw_size': raw.stat().st_size,
               'log_sha256': sha(out/'offline-fsck.log'), 'scope': 'ext4 filesystem, flattened offline copy'}
    (out/'offline-fsck.json').write_text(json.dumps(receipt, indent=2)+'\n')
    if result.returncode != 0:
        raise RuntimeError('offline ext4 check failed; no repair or boot')
    # The exact successful check is recorded; remove only our own disposable raw copy.
    raw.unlink()
    return receipt


def boot(args):
    profile_path = ROOT/'profiles/steam-host-experiment.json'
    profile = json.loads(profile_path.read_text())
    if (profile['disk']['kind'] != 'new-qcow2-overlay' or profile['disk']['reuse_dirty']
            or profile['network']['kind'] != 'qemu-user-nat' or profile['network']['host_forwarding']
            or profile['client_bundled'] or profile['app_route_enabled']):
        raise ValueError('unsafe experiment profile')
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    report = {'schema': 1, 'status': 'failed', 'host_only': True,
              'iphone_tested': False, 'steam_window_verified': False,
              'big_picture_verified': False, 'clean_shutdown': False,
              'qemu_started': False,
              'network': 'explicit QEMU user NAT, no host forwarding', 'commands': []}
    total_started = time.monotonic()
    with (out/'owner.lock').open('xb') as lockfile:
        fcntl.flock(lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            with ExitStack() as cleanup:
                return _boot(args, profile_path, profile, out, report, cleanup)
        except BaseException as error:
            report['failure'] = {'class': type(error).__name__, 'message': str(error)}
            report['preparation_failed'] = not report['qemu_started']
            raise
        finally:
            report['total_elapsed_seconds'] = round(time.monotonic()-total_started, 3)
            report.setdefault('elapsed_seconds', report['total_elapsed_seconds'])
            (out/'result.json').write_text(json.dumps(report, indent=2)+'\n')


def _boot(args, profile_path, profile, out, report, cleanup):
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
    image_command = [*loader, str(args.qemu_img)]
    continuation = getattr(args, 'continue_from', None)
    if continuation is not None:
        report['continuation'] = continuation_copy(continuation.absolute(), disk, seed,
                                                  report['seed_sha256'], image_command, env)
        report['offline_fsck'] = offline_fsck(disk, out, image_command, env)
        subprocess.run([*image_command, 'resize', str(disk), profile['disk']['virtual_size']], env=env, check=True)
    else:
        subprocess.run([*image_command, 'create', '-f', 'qcow2', '-F', 'raw',
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
    cleanup.callback(server.server_close)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    cleanup.callback(server.shutdown)
    report['cache_port'] = server.server_port
    (out/'cache-port').write_text(str(server.server_port))
    listeners = []
    for _ in range(2):
        s = socket.socket(); cleanup.callback(s.close)
        s.bind(('127.0.0.1', 0)); s.listen(1); s.settimeout(30); listeners.append(s)
    with socket.socket() as port:
        port.bind(('127.0.0.1', 0)); qport = port.getsockname()[1]
    argv = [args.host/'usr/bin/qemu-system-aarch64', '-L', args.host/'usr/share/qemu',
            '-machine', 'virt', '-cpu', profile['cpu'], '-m', str(profile['memory_mib']), '-smp', '4',
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
        report['qemu_started'] = True
        for listener in listeners:
            peer = listener.accept()[0]; cleanup.callback(peer.close); peers.append(peer)
        for peer in peers: peer.setblocking(False)
        qmp = socket.create_connection(('127.0.0.1', qport), timeout=10); cleanup.callback(qmp.close)
        qfile = qmp.makefile('rwb', buffering=0); cleanup.callback(qfile.close)
        json.loads(qfile.readline()); qcommand('qmp_capabilities')
        nodes = qcommand('query-named-block-nodes')
        seed_nodes = [node for node in nodes if node.get('drv') == 'raw' and node.get('file') == str(seed)]
        if len(seed_nodes) != 1 or seed_nodes[0].get('ro') is not True:
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
                if clean_stop_evidence(process.returncode, logs[1]):
                    finalize_disk(report, disk, dirty)
            except BaseException as error:
                report['stop_failure'] = type(error).__name__
        if process is not None and process.poll() is None:
            process.kill(); process.wait(); report['forced'] = True
        if process is not None: report['qemu_exit_code'] = process.returncode
        # Subprocess exit is mandatory; embedded iOS backend lifetime differs and
        # its existing retained owner/disk lock contract is intentionally untouched.
        save()
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('host', 'seed', 'kernel', 'bootstrap', 'cache', 'debs', 'commands', 'output', 'qemu-img', 'image-tool-receipt'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--seconds', type=int, default=1500)
    p.add_argument('--continue-from', type=Path, help='Explicit clean private run to COPY, never modify or repair')
    p.add_argument('--enable-experimental-network', action='store_true', required=True)
    a = p.parse_args()
    print(json.dumps(boot(a), indent=2))
