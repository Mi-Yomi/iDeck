#!/usr/bin/env python3
"""Render the pinned run27 private profile; never install or launch it.

The bounded owner/resource guardian and fresh ARM64 fixtures remain mandatory.
These files reproduce the tested launcher/preload route, not an iOS integration.
"""
import argparse
import hashlib
import json
from pathlib import Path


PINS = {
    'launcher': '893ac73943214cbd6ac87723c32a3774c872dad2b91429cd4aedb48737e92b33',
    'namespace_helper': '96c929eafefb2f76aa7751fb1869baa6def54e5e31be2a0e6620a486bca64b0d',
    'zero_library': 'c350f21128358eb4bdc942db571affe38b5817341e9656cadb7e592c74e36f9d',
}


def render(launcher, namespace_helper, zero_library):
    inputs = dict(launcher=launcher, namespace_helper=namespace_helper,
                  zero_library=zero_library)
    for name, data in inputs.items():
        if hashlib.sha256(data).hexdigest() != PINS[name]:
            raise ValueError('unsupported pinned input: ' + name)
    flag = b'-cef-disable-gpu -cef-force-sandbox\n'
    target = b"'/usr/local/bin/ideck-steam', mode], env)"
    assert launcher.count(flag) == namespace_helper.count(target) == 1
    launcher = launcher.replace(flag, flag[:-1] + b' -cef-disable-hang-timeouts\n')
    namespace_helper = namespace_helper.replace(
        target, b"'/usr/bin/env', 'LD_PRELOAD=/opt/ideck-shm-zero/libideck-shm-zero.so', "
        b"'/usr/local/bin/ideck-steam-desktop-v11', mode], env)")
    return {'ideck-steam-desktop-v11': launcher,
            'namespace-zero-watchdog-500m.py': namespace_helper}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('launcher', 'namespace_helper', 'zero_library', 'output'):
        parser.add_argument('--' + name.replace('_', '-'), type=Path, required=True)
    args = parser.parse_args()
    files = render(args.launcher.read_bytes(), args.namespace_helper.read_bytes(),
                   args.zero_library.read_bytes())
    args.output.mkdir(mode=0o700, exist_ok=False)
    for name, data in files.items():
        with (args.output / name).open('xb') as stream:
            stream.write(data)
    receipt = {'schema': 1, 'reference_run': 27, 'rendered_only': True,
               'installed': False, 'steam_launched': False, 'iphone_verified': False,
               'input_sha256': PINS,
               'output_sha256': {name: hashlib.sha256(data).hexdigest()
                                 for name, data in files.items()},
               'required_runtime_controls': [
                   'fresh actual ARM64 checker, fallback and cross-process IPC fixtures',
                   'root-owned pinned library at /opt/ideck-shm-zero/libideck-shm-zero.so',
                   'private namespace helper; drop to UID1000 before preload',
                   'original bounded identity/pidfd, browser-exit and SHM reserve guardian',
                   '4096 MiB guest, four vCPUs; owned browser affinity phase recorded separately',
                   'ordinary application shutdown, verified original VM Stop and offline fsck'],
               'limitations': 'one local desktop navigation run; games, Big Picture and iPhone require separate acceptance'}
    with (args.output / 'profile.json').open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(receipt, stream, indent=2)
        stream.write('\n')
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
