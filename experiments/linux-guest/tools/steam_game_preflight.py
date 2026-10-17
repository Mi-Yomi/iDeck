#!/usr/bin/env python3
"""Read-only inventory before installing games; presence is not runtime acceptance."""
import argparse
import json
import os
from pathlib import Path
import platform


def elf_machine(path):
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
                        'wine_elf_machine': elf_machine(candidate / 'files/bin/wine'),
                        'wine64_elf_machine': elf_machine(candidate / 'files/bin/wine64'),
                    })
    fex = {}
    for name in ('FEXInterpreter', 'FEXLoader'):
        for prefix in ('usr/bin', 'usr/local/bin'):
            candidate = system / prefix / name
            if candidate.is_file():
                fex[prefix + '/' + name] = elf_machine(candidate)
    icds = []
    for prefix in ('usr/share/vulkan/icd.d', 'etc/vulkan/icd.d'):
        directory = system / prefix
        if directory.is_dir():
            icds.extend(prefix + '/' + p.name for p in sorted(directory.glob('*.json')))
    fs = os.statvfs(steam)
    return {
        'schema': 1, 'host_machine': platform.machine(),
        'native_steam_elf_machine': elf_machine(steam / 'steamrtarm64/steam'),
        'steam_filesystem_available_bytes': fs.f_bavail * fs.f_frsize,
        'proton_candidates': tools, 'system_fex_candidates': fex,
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
