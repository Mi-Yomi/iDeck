import json
from pathlib import Path
import shlex
import subprocess
import sys
import urllib.parse

REPO = Path('/workspace/iDeck/experiments/linux-guest')
TASK = Path('/workspace/steam-cloud-20261017')
sys.path.insert(0, str(REPO/'tools'))
import debian_rootfs as base
import gui_rootfs as gui

lock_path = REPO/'ipa/gui-inputs.lock.json'
lock = json.loads(lock_path.read_text())
cache = TASK/'gui-cache'
base.OFFLINE = True
gui.authenticate(lock, cache/'metadata')
indexes = {}
for desc in lock['release']['indexes']:
    records, _ = base.load_index(cache/'metadata', desc)
    indexes[desc['architecture']] = {r['Filename']: base.package_pin(r)
                                   for r in records if 'Filename' in r}

extras_path = REPO/'ipa/steam-dependencies.lock.json'
extras = json.loads(extras_path.read_text())
assert extras['gui_inputs_sha256'] == base.sha256(lock_path)
assert extras['release'] == lock['release']
tools_lock = REPO/'evidence/gui-alpine-20261017/module-tools.lock.json'
tool_lock = json.loads(tools_lock.read_text())
assert tool_lock['release'] == lock['release']
base.OFFLINE = False
report = {'schema': 1, 'gui_inputs_sha256': base.sha256(lock_path),
          'steam_dependencies_sha256': base.sha256(extras_path),
          'module_tools_lock_sha256': base.sha256(tools_lock),
          'release_signature_verified': True, 'system_install': False,
          'guest_install': False, 'packages': []}
for group, pins, arch, folder in [
    ('steam', extras['extra_packages'], 'arm64', TASK/'deps-cache/debs'),
    ('module-tools', tool_lock['packages'], 'amd64', TASK/'module-tools-cache/debs'),
]:
    for pin in pins:
        assert indexes[arch].get(pin['filename']) == pin
        path = base.fetch(base.BASE + urllib.parse.quote(pin['filename'], safe='/+'),
                          folder/Path(pin['filename']).name, pin['size'], pin['sha256'])
        if group == 'module-tools':
            subprocess.run(['dpkg-deb', '-x', str(path), str(TASK/'module-tools')], check=True)
        report['packages'].append({'group': group, **pin})

host = TASK/'module-tools'
library = host/'usr/lib/x86_64-linux-gnu'
binary = host/'usr/bin/unsquashfs'
wrapper = TASK/'unsquashfs'
with wrapper.open('x') as out:
    out.write('#!/bin/sh\nexec '+shlex.join([str(library/'ld-linux-x86-64.so.2'),
              '--library-path', str(library), str(binary)])+' "$@"\n')
wrapper.chmod(0o700)
report['unsquashfs_sha256'] = base.sha256(binary)
report['wrapper_sha256'] = base.sha256(wrapper)
report['steam_packages_verified'] = len(extras['extra_packages'])
report['steam_download_bytes'] = sum(p['size'] for p in extras['extra_packages'])
with (TASK/'support-receipt.json').open('x') as out:
    out.write(json.dumps(report, indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='packages'}, indent=2))
