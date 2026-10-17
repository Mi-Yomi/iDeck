#!/usr/bin/env python3
"""Inventory the configured root; actual glibc loader checks run inside the VM.

An unreferenced private DSO is not a standalone executable. Record every static
edge, including residual private contexts, instead of inventing a global path.
"""
import argparse
import json
import os
from pathlib import Path
import debian_rootfs as base


def inventory(root):
    parsed={};executables=[];edges=0;residual=[]
    def parse(path):
        if path not in parsed:parsed[path]=base.elf_dependencies(path)
        return parsed[path]
    defaults=['/lib/aarch64-linux-gnu','/usr/lib/aarch64-linux-gnu','/lib','/usr/lib']
    count=0
    for directory,_names,files in os.walk(root):
        for name in sorted(files):
            path=Path(directory)/name
            if path.is_symlink():continue
            entry=parse(path)
            if entry is None:continue
            count+=1;interp,needed,search=entry;relative='/'+path.relative_to(root).as_posix()
            if interp:
                if interp!='/lib/ld-linux-aarch64.so.1' or not base.rooted_path(root,interp).is_file():
                    raise ValueError('missing/unexpected executable interpreter')
                executables.append(relative)
            origin='/'+path.parent.relative_to(root).as_posix()
            search=[p.replace('${ORIGIN}',origin).replace('$ORIGIN',origin) for p in search]
            if any('$' in p or not p.startswith('/') for p in search):
                raise ValueError('unsupported static ELF search token')
            for needed_name in needed:
                if '/' in needed_name:raise ValueError('unsupported slash in DT_NEEDED')
                candidates=[base.rooted_path(root,p+'/'+needed_name) for p in search+defaults]
                edges+=1
                if not any(p.is_file() and parse(p) is not None for p in candidates):
                    residual.append({'file':relative,'needed':needed_name,'interpreter':interp})
    if not executables:raise ValueError('no actual dynamic executables')
    return {'schema':1,'arm64_elf_files':count,'dt_needed_edges':edges,
            'dynamic_executables':sorted(executables),'standalone_static_residuals':residual,
            'status':'inventory_requires_actual_guest_loader_audit',
            'scope':'No fake global search path or symlink. PT_INTERP roots are checked by actual glibc in VM.'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=inventory(a.root.resolve())
    with a.output.open('x') as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='dynamic_executables'},indent=2))
