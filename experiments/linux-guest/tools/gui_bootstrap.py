#!/usr/bin/env python3
"""Build the production GUI suffix only from the exact accepted Alpine inputs."""
import argparse
import gzip
import io
import json
from pathlib import Path
import shutil
import sys

import desktop_modules as modules
from debian_rootfs import sha256
from check_debian_ext4_boot import checked,cpio_suffix
from stage_bundle import verify

ROOT=Path(__file__).resolve().parents[1]


def prepare(output,module_dir):
    reference_path=ROOT/'evidence/local-debian-ext4-modules.json'
    reference=json.loads(checked(reference_path,{'size':3665,'sha256':'0281b08b8d9eacd2c07a8475ebd5ebf61d5eeeed0e2ad1561f13048409f2b403'}))
    path=module_dir/'manifest.json'
    if path.is_symlink() or path.stat().st_size>65536:raise ValueError('invalid module manifest')
    manifest=json.loads(path.read_text())
    # Provenance may say standalone_modloop instead of verified_archive. Exact
    # metadata/module bytes must match the already accepted original closure.
    for key in ('kernel_release','expected_kernel_sha256','modloop_sha256','modloop_size',
                'metadata','load_order','modules','total_module_bytes'):
        if manifest.get(key)!=reference[key]:raise ValueError('module input differs from original pinned closure')
    if (manifest['kernel_release']!=modules.KERNEL or manifest['modloop_sha256']!=modules.MODLOOP_SHA256
            or manifest['expected_kernel_sha256']!=modules.KERNEL_SHA256):raise ValueError('production module kernel mismatch')
    prefix=module_dir/modules.MODULE_PREFIX
    dep=checked(prefix/'modules.dep',manifest['metadata']['modules.dep'])
    soft=checked(prefix/'modules.softdep',manifest['metadata']['modules.softdep'])
    built=checked(prefix/'modules.builtin',manifest['metadata']['modules.builtin'])
    order=modules.closure(modules.dependencies(dep),modules.soft_dependencies(soft,reachable_only=True),built)
    if order!=manifest['load_order'] or order!=[p['path'] for p in manifest['modules']]:raise ValueError('module closure mismatch')
    files={'ideck/ext4-load-order':(('\n'.join(order)+'\n').encode(),0o644)}
    for item in manifest['modules']:
        path=modules.module_path(item['path'])
        data=checked(prefix/path,{k:item[k] for k in ('size','sha256')});modules.module_metadata(data)
        files['usr/lib/modules/'+modules.KERNEL+'/'+path]=(data,0o644)
    for name in ('ideck-desktop-init','ideck-desktop-login'):
        files[name]=((ROOT/'guest/gui'/name).read_bytes(),0o755)
    output.mkdir(parents=True,exist_ok=False)
    sys.path.insert(0,str(ROOT.parents[1]/'ci'))
    from build_linux_probe_ipa import restore_guest
    restore_guest(output/'probe')
    probe=verify(output/'probe')
    suffix=io.BytesIO()
    with gzip.GzipFile(filename='',mode='wb',fileobj=suffix,mtime=0,compresslevel=0) as f:f.write(cpio_suffix(files))
    initrd=output/'initramfs-desktop.gz';initrd.write_bytes(probe['initramfs-ideck.gz']+suffix.getvalue())
    kernel=output/'vmlinuz-virt';kernel.write_bytes(probe['vmlinuz-virt'])
    report={'schema':1,'purpose':'production GUI bootstrap; runtime gate still required',
            'kernel':{'size':kernel.stat().st_size,'sha256':sha256(kernel)},
            'initramfs':{'size':initrd.stat().st_size,'sha256':sha256(initrd)},
            'module_manifest_sha256':sha256(module_dir/'manifest.json'),
            'load_order':order,'original_gpu_input_modules':'unchanged in pinned probe initramfs',
            'gui_verified':False,'device_verified':False}
    (output/'bootstrap.json').write_text(json.dumps(report,indent=2)+'\n');return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--modules',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();print(json.dumps(prepare(a.output.resolve(),a.modules.resolve()),indent=2))
