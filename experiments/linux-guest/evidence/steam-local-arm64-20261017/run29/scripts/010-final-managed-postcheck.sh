set -eu
export PYTHONDONTWRITEBYTECODE=1
cat > /run/ideck/game-preflight29.py <<'GAME_PREFLIGHT'
#!/usr/bin/env python3
"""Read-only inventory before installing games; presence is not runtime acceptance."""
import argparse
import json
import os
from pathlib import Path
import platform


def elf_machine(path, root=None):
    if root is not None and not path.resolve().is_relative_to(root.resolve()):
        return None
    try:
        with path.open('rb') as source:
            header = source.read(20)
    except FileNotFoundError:
        return None
    if len(header) != 20 or header[:4] != b'\x7fELF' or header[5] not in (1, 2):
        return None
    return int.from_bytes(header[18:20], 'little' if header[5] == 1 else 'big')


def inventory(steam, system=Path('/')):
    # Inspect only runtime names, never account files or the user's game list.
    common = steam / 'steamapps/common'
    tools = []
    for parent in (common, steam / 'compatibilitytools.d'):
        if parent.is_dir():
            for candidate in sorted(parent.iterdir()):
                if candidate.is_dir() and (candidate / 'proton').is_file():
                    tools.append({
                        'name': candidate.name,
                        'wine_elf_machine': elf_machine(candidate / 'files/bin/wine', steam),
                        'wine64_elf_machine': elf_machine(candidate / 'files/bin/wine64', steam),
                        'wine_arm64_elf_machine': elf_machine(candidate / 'files/bin-arm64/wine', steam),
                        'wineserver_arm64_elf_machine': elf_machine(candidate / 'files/bin-arm64/wineserver', steam),
                    })
    fex = {}
    for name in ('FEXInterpreter', 'FEXLoader'):
        for prefix in ('usr/bin', 'usr/local/bin'):
            candidate = system / prefix / name
            if candidate.is_file():
                fex[prefix + '/' + name] = elf_machine(candidate, system)
    icds = []
    for prefix in ('usr/share/vulkan/icd.d', 'etc/vulkan/icd.d'):
        directory = system / prefix
        if directory.is_dir():
            icds.extend(prefix + '/' + p.name for p in sorted(directory.glob('*.json')))
    launchers = []
    for base, prefixes in (
        (system, ('usr/bin', 'usr/local/bin')),
        (steam, ('steamrtarm64/pv-runtime/steam-runtime-steamrt/bin',
                 'steamrt64/pv-runtime/steam-runtime-steamrt/bin')),
    ):
        for prefix in prefixes:
            candidate = base / prefix / 'steam-runtime-launcher-service'
            if candidate.is_file():
                # Runtime symlinks are normal, but never inspect outside this root.
                if not candidate.resolve().is_relative_to(base.resolve()):
                    continue
                launchers.append({
                    'origin': 'system' if base == system else 'steam',
                    'path': prefix + '/steam-runtime-launcher-service',
                    'elf_machine': elf_machine(candidate, base),
                    'executable': os.access(candidate, os.X_OK),
                })
    fs = os.statvfs(steam)
    return {
        'schema': 1, 'host_machine': platform.machine(),
        'native_steam_elf_machine': elf_machine(steam / 'steamrtarm64/steam', steam),
        'steam_filesystem_available_bytes': fs.f_bavail * fs.f_frsize,
        'proton_candidates': tools, 'system_fex_candidates': fex,
        'runtime_launcher_candidates': launchers,
        'vulkan_icd_manifests': icds,
        'render_nodes': sorted(p.name for p in (system / 'dev/dri').glob('renderD*')),
        'scope': 'default Steam library and local compatibilitytools.d; external libraries not inspected',
        'execution_tested': False, 'accelerated_graphics_verified': False,
        'game_launch_verified': False, 'iphone_verified': False,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--steam-root', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(inventory(args.steam_root), indent=2))

GAME_PREFLIGHT
python3 /run/ideck/game-preflight29.py --steam-root /opt/ideck-tools-probe29/tool-install > /run/ideck/game-inventory29.json || true
if [ -d /home/ideck/steam-experiment-logs/runtime-tools-run29 ]; then cp /run/ideck/game-inventory29.json /home/ideck/steam-experiment-logs/runtime-tools-run29/inventory.json; fi
python3 - <<'FINAL_AUDIT'
from pathlib import Path
import os,json,hashlib,subprocess,base64,gzip
out=Path('/home/ideck/steam-experiment-logs/runtime-tools-run29');out.mkdir(mode=0o700,exist_ok=True)
namespaces=set()
baseline_namespaces=set(json.loads((out/'baseline-namespaces.json').read_text()))
for p in out.glob('namespace-*.json'):namespaces.add(json.loads(p.read_text())['rooted']['mount_namespace'])
holders=[];tools=[];steam=[]
for p in Path('/proc').iterdir():
 if not p.name.isdecimal():continue
 try:
  exe=os.readlink(p/'exe');args=p.joinpath('cmdline').read_text(errors='replace')
  if os.readlink(p/'ns/mnt') not in baseline_namespaces:holders.append(int(p.name))
  if exe.startswith('/opt/ideck-tools-probe29/') or 'tools-namespace29.py' in args:tools.append(int(p.name))
  if exe.endswith(('/steamrtarm64/steam','/steamrtarm64/steamwebhelper')):steam.append(int(p.name))
 except (FileNotFoundError,ProcessLookupError):pass
before=json.loads(Path('/home/ideck/steam-experiment-logs/resume-local-20261017-preflight/result.json').read_text())
client={}
for relative,expected in before['client'].items():
 with (Path('/home/ideck/.local/share/Steam')/relative).open('rb') as f:sha=hashlib.file_digest(f,'sha256').hexdigest()
 client[relative]={'sha256':sha,'unchanged':sha==expected['sha256']}
audit=subprocess.run(['dpkg','--audit'],capture_output=True)
r={'private_namespace_holders':holders,'tool_processes':tools,'steam_processes':steam,'client':client,'audit_exit':audit.returncode,'audit_stdout_bytes':len(audit.stdout),'audit_stderr_bytes':len(audit.stderr)}
r['ready_for_original_vm_stop']=not holders and not tools and not steam and all(v['unchanged'] for v in client.values()) and audit.returncode==0 and not audit.stdout and not audit.stderr
(out/'final-postcheck.json').write_text(json.dumps(r,indent=2)+'\n')
for p in sorted(out.iterdir()):
 if p.is_file() and not p.is_symlink():
  b=p.read_bytes();assert len(b)<1024**2
  print('IDECK_BLOB=runtime-tools-run29__'+p.name+':'+base64.b64encode(gzip.compress(b)).decode(),flush=True)
print('TOOL_FINAL_AUDIT='+json.dumps(r),flush=True)

FINAL_AUDIT
