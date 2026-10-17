set -eu
export PYTHONDONTWRITEBYTECODE=1
cat > /run/ideck/trace-ipc-narrow.py <<'NARROW_SOURCE'
#!/usr/bin/env python3
"""Bounded guest-only IPC syscall trace. Never launch/stop a guest or Steam."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import time

SYSCALLS = ('futex', 'openat', 'ftruncate', 'mmap', 'munmap', 'close', 'unlink',
            'unlinkat', 'connect', 'clone', 'clone3', 'exit', 'exit_group')
ROOT = Path('/home/ideck/.local/share/Steam')
DEFAULT_STRACE = '/opt/ideck-diagnostic-strace/usr/bin/strace'


def proc_info(pid, proc=Path('/proc')):
    base = proc / str(pid)
    raw = (base / 'stat').read_text()
    fields = raw[raw.rfind(')') + 2:].split()
    status = dict(line.split(':', 1) for line in (base / 'status').read_text().splitlines() if ':' in line)
    argv = [x.decode('utf-8', 'replace') for x in (base / 'cmdline').read_bytes().split(b'\0') if x]
    return {'pid': pid, 'starttime': fields[19], 'ppid': int(fields[1]),
            'exe': os.readlink(base / 'exe'), 'argv': argv,
            'uid': [int(x) for x in status['Uid'].split()],
            'tracer_pid': int(status.get('TracerPid', '0')),
            'state': status.get('State', '').strip(),
            'seccomp': int(status.get('Seccomp', '-1'))}


def is_browser(info, main_pid):
    return (info['exe'] == str(ROOT / 'steamrtarm64/steamwebhelper') and
            info['uid'] == [1000] * 4 and
            info.get('ppid') == main_pid and
            f'-steampid={main_pid}' in info['argv'] and
            not any(x.startswith('--type=') for x in info['argv']))


def validate_main(info):
    if info['exe'] != str(ROOT / 'steamrtarm64/steam') or info['uid'] != [1000] * 4:
        raise RuntimeError('unexpected_native_process')
    if '-cef-force-sandbox' not in info['argv']:
        raise RuntimeError('force_sandbox_missing_native')
    deny = {'-no-cef-sandbox', '-cef-disable-sandbox', '--no-sandbox'}
    if deny.intersection(info['argv']):
        raise RuntimeError('sandbox_disable_argument')


def find_browser(main_pid, proc=Path('/proc')):
    found = []
    for path in proc.iterdir():
        if not path.name.isdecimal():
            continue
        try:
            info = proc_info(int(path.name), proc)
        except (OSError, KeyError, ValueError):
            continue
        if is_browser(info, main_pid):
            found.append(info)
    if len(found) > 1:
        raise RuntimeError('multiple_browser_processes')
    return found[0] if found else None


def trace_command(strace, tids):
    argv = [strace, '-qq', '-ttt', '-T', '-i', '-s', '128',
            '-e', 'signal=none', '-e', 'trace=' + ','.join(SYSCALLS)]
    # Explicit existing TIDs: no -f, no ptrace of future sandboxed children.
    for tid in sorted(set(tids)):
        argv.extend(['-p', str(tid)])
    return argv


def select_tids(available, requested):
    """An explicit narrow trace may only reduce the verified existing set."""
    owned = set(available)
    if not owned or len(owned) > 256:
        raise RuntimeError('invalid_thread_count')
    if requested is None:
        return sorted(owned)
    selected = set(requested)
    if (not 1 <= len(requested) <= 32 or len(selected) != len(requested)
            or any(tid <= 1 for tid in selected) or not selected <= owned):
        raise RuntimeError('invalid_selected_threads')
    return sorted(selected)


def snapshot(pid, dest, phase):
    info = proc_info(pid)
    safe = {k: v for k, v in info.items() if k != 'argv'}
    safe['force_sandbox_arg'] = any(x in info['argv'] for x in ('-cef-force-sandbox', '-force-sandbox', '--force-sandbox'))
    safe['cwd'] = os.readlink(f'/proc/{pid}/cwd')
    marker = Path(f'/proc/{pid}/cwd/.cef-initialize-sentinel')
    try:
        st = marker.lstat()
        safe['sentinel'] = {'exists': True, 'size': st.st_size, 'uid': st.st_uid, 'mode': st.st_mode, 'mtime_ns': st.st_mtime_ns}
    except FileNotFoundError:
        safe['sentinel'] = {'exists': False}
    (dest / f'{phase}-{pid}.maps').write_bytes(Path(f'/proc/{pid}/maps').read_bytes())
    return safe


def detach(tracer):
    # Drain the bounded pipe while waiting: strace can otherwise block while
    # printing its detach messages after the byte budget has been reached.
    os.set_blocking(tracer.stderr.fileno(), False)
    for sig in (signal.SIGINT, signal.SIGTERM):
        if tracer.poll() is not None:
            return True
        try:
            tracer.send_signal(sig)
        except ProcessLookupError:
            return True
        deadline = time.monotonic() + 5
        while tracer.poll() is None and time.monotonic() < deadline:
            try:
                os.read(tracer.stderr.fileno(), 65536)
            except BlockingIOError:
                pass
            time.sleep(0.01)
    return tracer.poll() is not None


def collect(tracer, sink, seconds, byte_cap, interrupted, reserve=64 * 1024 * 1024):
    started = time.monotonic()
    stored = 0
    reason = 'duration_limit'
    selector = selectors.DefaultSelector()
    selector.register(tracer.stderr, selectors.EVENT_READ)
    try:
        while True:
            if interrupted[0]:
                reason = 'interrupted'
                break
            if time.monotonic() - started >= seconds:
                break
            shm = os.statvfs('/dev/shm')
            if shm.f_bavail * shm.f_frsize < reserve:
                reason = 'shared_memory_reserve'
                break
            if stored >= byte_cap:
                reason = 'byte_limit'
                break
            events = selector.select(timeout=0.1)
            for key, _ in events:
                chunk = os.read(key.fd, min(65536, byte_cap - stored))
                if not chunk:
                    reason = 'tracer_exited'
                    return stored, reason, round(time.monotonic() - started, 3)
                sink.write(chunk)
                stored += len(chunk)
            if tracer.poll() is not None and not events:
                reason = 'tracer_exited'
                break
        return stored, reason, round(time.monotonic() - started, 3)
    finally:
        selector.close()
        sink.flush()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--main-pid', type=int, required=True)
    ap.add_argument('--browser-pid', type=int)
    ap.add_argument('--wait-browser', type=float, default=45)
    ap.add_argument('--seconds', type=float, default=25)
    ap.add_argument('--max-bytes', type=int, default=8 * 1024 * 1024)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--strace', default=DEFAULT_STRACE)
    ap.add_argument('--tid', type=int, action='append',
                    help='trace only these existing native/browser TIDs (at most32)')
    args = ap.parse_args()
    if not (0 < args.seconds <= 30 and 0 <= args.wait_browser <= 60 and
            1024 <= args.max_bytes <= 16 * 1024 * 1024 and args.main_pid > 1):
        ap.error('bounds: seconds<=30, wait-browser<=60, max-bytes1024..16MiB, main-pid>1')
    args.output.mkdir(parents=False, exist_ok=False)
    result = {'schema': 1, 'kind': 'separate_instrumented_probe', 'status': 'failed',
              'baseline_timing': False, 'capture': 'existing native/browser TIDs only',
              'read_write_buffers_captured': False, 'new_sandbox_children_traced': False,
              'requested_seconds': args.seconds, 'max_bytes': args.max_bytes,
              'started_wall_ns': time.time_ns(), 'before': [], 'after': []}
    tracer = None
    interrupted = [False]
    old_handlers = {}
    try:
        initial = proc_info(args.main_pid)
        validate_main(initial)
        deadline = time.monotonic() + args.wait_browser
        while True:
            current = proc_info(args.main_pid)
            if current['starttime'] != initial['starttime']:
                raise RuntimeError('native_pid_reused')
            browser = proc_info(args.browser_pid) if args.browser_pid else find_browser(args.main_pid)
            if browser is not None:
                break
            if time.monotonic() >= deadline:
                raise RuntimeError('browser_not_found')
            time.sleep(0.1)
        if not is_browser(browser, args.main_pid):
            raise RuntimeError('unexpected_browser_process')
        if not {'-force-sandbox', '--force-sandbox'}.intersection(browser['argv']):
            raise RuntimeError('force_sandbox_missing_browser')
        if '--no-sandbox' in browser['argv']:
            raise RuntimeError('browser_no_sandbox')
        pids = [args.main_pid, browser['pid']]
        tids = []
        for pid in pids:
            result['before'].append(snapshot(pid, args.output, 'before'))
            for task in Path(f'/proc/{pid}/task').iterdir():
                try:
                    info = proc_info(int(task.name))
                except FileNotFoundError:
                    continue
                if info['tracer_pid']:
                    raise RuntimeError('already_traced')
                tids.append(int(task.name))
        result['available_tids'] = sorted(tids)
        tids = select_tids(tids, args.tid)
        result['tids'] = tids
        command = trace_command(args.strace, tids)
        result['command'] = command
        for sig in (signal.SIGINT, signal.SIGTERM):
            old_handlers[sig] = signal.signal(sig, lambda *_: interrupted.__setitem__(0, True))
        tracer = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, start_new_session=True)
        result['tracer_pid'] = tracer.pid
        with (args.output / 'trace.log').open('xb') as sink:
            size, reason, elapsed = collect(tracer, sink, args.seconds, args.max_bytes, interrupted)
        result.update(bytes=size, stop_reason=reason, trace_seconds=elapsed)
        result['tracer_detached'] = detach(tracer)
        result['tracer_exit'] = tracer.poll()
        result['remaining_traced_tids'] = []
        for tid in tids:
            try:
                if proc_info(tid)['tracer_pid'] == tracer.pid:
                    result['remaining_traced_tids'].append(tid)
            except FileNotFoundError:
                pass
        for pid in pids:
            try:
                result['after'].append(snapshot(pid, args.output, 'after'))
            except FileNotFoundError:
                result['after'].append({'pid': pid, 'exited': True})
        result['status'] = ('captured' if result['tracer_detached'] and
                            not result['remaining_traced_tids'] and result['tracer_exit'] == 0
                            and size else 'trace_incomplete')
    except Exception as exc:
        # No command-line/environment content or arbitrary exception string.
        result['failure_class'] = type(exc).__name__
        result['reason'] = exc.args[0] if isinstance(exc, RuntimeError) else 'trace_setup_or_capture_failed'
    finally:
        if tracer is not None and tracer.poll() is None:
            result['tracer_detached'] = detach(tracer)
            result['tracer_exit'] = tracer.poll()
        for sig, handler in old_handlers.items():
            signal.signal(sig, handler)
        for path in args.output.glob('*.maps'):
            result.setdefault('files', {})[path.name] = {'size': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        path = args.output / 'trace.log'
        if path.exists():
            result.setdefault('files', {})[path.name] = {'size': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        result['finished_wall_ns'] = time.time_ns()
        (args.output / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'status': result['status'], 'output': str(args.output),
                      'tracer_detached': result.get('tracer_detached'),
                      'reason': result.get('reason', result.get('stop_reason'))}))
    return 0 if result['status'] == 'captured' else 1


if __name__ == '__main__':
    raise SystemExit(main())

NARROW_SOURCE
python3 - <<'PY'
from pathlib import Path
import ast,hashlib
p=Path('/run/ideck/trace-ipc-narrow.py');b=p.read_bytes();assert hashlib.sha256(b).hexdigest()=='ce4a2170052f612eb759589b8e2a4e20adff073cace5a093c2b33e4b235e5fc3'
ast.parse(b)
print('IDECK_NARROW_TRACE_SOURCE='+hashlib.sha256(b).hexdigest(),flush=True)
PY
