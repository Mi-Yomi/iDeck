#!/usr/bin/env python3
"""Bounded control verbs for the persistent guest; logs remain on its own disk."""
import fcntl
import importlib.util
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

OPT = Path('/opt/ideck-steam')
ENV = {'PATH': '/usr/local/bin:/usr/bin:/bin', 'HOME': '/home/ideck', 'USER': 'ideck',
       'LOGNAME': 'ideck', 'LANG': 'C.UTF-8', 'DISPLAY': ':0',
       'XAUTHORITY': '/run/user/1000/Xauthority', 'XDG_RUNTIME_DIR': '/run/user/1000'}


def main(mode):
    if mode not in ('install', 'big-picture', 'desktop') or os.geteuid() != 0:
        raise RuntimeError('invalid_device_action')
    cmdline = Path('/proc/cmdline').read_text().split()
    if not {'ideck.steam_experiment=1', 'ideck.steam_persistent=1', 'ideck.steam_network=1'} <= set(cmdline):
        raise RuntimeError('persistent_network_opt_in_required')
    log = Path('/var/log/ideck-steam-install')
    log.mkdir(mode=0o700, exist_ok=True)
    if log.is_symlink():
        raise RuntimeError('unsafe_action_log')
    # The return-to-Desktop request must reach a live launch lock owner.
    held = None
    if mode != 'desktop':
        held = open('/run/ideck-steam-action.lock', 'w')
        try:
            fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('action_busy') from None
    if mode == 'install':
        print('IDECK_STEAM_INSTALLING', flush=True)
        spec = importlib.util.spec_from_file_location('official_install', OPT / 'install-official.py')
        installer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(installer)
        installer.install()
        print('IDECK_STEAM_INSTALLED', flush=True)
        return
    for tool in ('ldd', 'setpriv', 'dbus-send', 'dbus-run-session', 'flock', 'pgrep', 'lsof'):
        if shutil.which(tool, path=ENV['PATH']) is None:
            raise RuntimeError('missing_guest_tool_' + tool.replace('-', '_'))
    # Real loader checks; absent libraries block launch without sandbox fallback.
    for name in ('steamrtarm64/steam', 'steamrtarm64/steamwebhelper', 'steamrtarm64/steamclient.so', 'steamrtarm64/chromehtml.so'):
        binary = Path('/home/ideck/.local/share/Steam') / name
        if not binary.is_file():
            raise RuntimeError('client_not_installed')
        loader_env = dict(ENV, LD_LIBRARY_PATH='/home/ideck/.local/share/Steam/steamrtarm64:/home/ideck/.local/share/Steam/steamrtarm64/panorama')
        checked = subprocess.run(['ldd', str(binary)], env=loader_env, capture_output=True, text=True)
        if checked.returncode or 'not found' in checked.stdout or 'not found' in checked.stderr:
            with (log / 'loader.log').open('a') as output:
                output.write(checked.stdout + checked.stderr)
            missing = re.findall(r'([A-Za-z0-9_.+-]+) => not found', checked.stdout)
            code = re.sub('[^a-z0-9_]', '_', '_'.join(missing).lower())[:65]
            raise RuntimeError('client_loader_missing_' + (code or 'see_loader_log'))
    if mode == 'desktop':
        args = ['setpriv', '--reuid=1000', '--regid=1000', '--init-groups',
                '/usr/local/bin/ideck-steam', 'stop']
    else:
        args = ['python3', str(OPT / 'namespace-check.py'), 'launch', 'big-picture']
    with (log / (mode + '.log')).open('ab') as output:
        print('IDECK_STEAM_' + ('LAUNCH_REQUESTED' if mode == 'big-picture' else 'DESKTOP_REQUESTED'), flush=True)
        result = subprocess.run(args, env=ENV, stdout=output, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError('launcher_failed_see_guest_log')
    print('IDECK_STEAM_' + ('CLIENT_RETURNED' if mode == 'big-picture' else 'DESKTOP_REQUEST_SENT'), flush=True)


if __name__ == '__main__':
    try:
        main(sys.argv[1] if len(sys.argv) == 2 else '')
    except Exception as error:
        reason = str(error)
        if not re.fullmatch('[a-z0-9_]{1,100}', reason):
            reason = type(error).__name__
        print('IDECK_STEAM_BLOCKER:' + reason, flush=True)
        raise SystemExit(1)
