#!/usr/bin/env python3
"""Read-only structural/content comparison of DISPOSABLE ext4 repair experiments.

Uses existing authenticated debugfs/dumpe2fs; never repairs, mounts, follows
extracted symlinks, or exports file contents. Original images are read-only.
"""
import argparse
import collections
import hashlib
import json
import os
from pathlib import Path
import shlex
import stat
import struct
import subprocess

import gui_host_tools


def digest(path):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,'rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def tool(host,program,args):
    result=subprocess.run(gui_host_tools.command(host,[host/'usr/sbin'/program,*args]),
                          capture_output=True,text=True,timeout=180,
                          env={'PATH':os.defpath,'LC_ALL':'C','E2FSCK_CONFIG':'/dev/null'})
    if result.returncode or len(result.stdout)>64*1024**2:raise RuntimeError(program+' failed/bound')
    return result.stdout,result.stderr


def quote(path):
    if any(c in path for c in ('\n','\r','\0')):raise ValueError('unsupported lab filename')
    return '"'+path.replace('\\','\\\\').replace('"','\\"')+'"'


def catalog(image,host,out):
    out.mkdir(parents=True,exist_ok=False)
    groups,err=tool(host,'dumpe2fs',['-g',image]);(out/'groups.log').write_text(groups+err)
    tables={};metadata={}
    for line in groups.splitlines():
        if not line or not line[0].isdigit():continue
        g,block,superblock,gdt,bb,ib,it=line.split(':')
        tables[int(g)]=int(it)
        for label,field in [('superblock',superblock),('group_descriptors',gdt),('block_bitmap',bb),('inode_bitmap',ib)]:
            if field=='-1':continue
            start,end=map(int,field.split('-')) if '-' in field else (int(field),int(field))
            for n in range(start,end+1):metadata[n]=label
    with image.open('rb') as raw:
        raw.seek(1024);sb=raw.read(1024)
    ipg=struct.unpack_from('<I',sb,0x28)[0];inode_size=struct.unpack_from('<H',sb,0x58)[0]
    for start in tables.values():
        for n in range(start,start+(ipg*inode_size+4095)//4096):metadata[n]='inode_table'
    records={};pending=['/'];seen={2};generation=0
    with image.open('rb') as raw:
        while pending:
            commands=out/f'ls-{generation}.cmd'
            commands.write_text(''.join('ls -l -p '+quote(p)+'\n' for p in pending))
            text,err=tool(host,'debugfs',['-f',commands,image]);generation+=1
            current=None;next_dirs=[];section=0
            for line in text.splitlines():
                if line.startswith('debugfs: ls -l -p '):
                    if section>=len(pending):raise ValueError('unexpected listing section')
                    current=pending[section];section+=1;continue
                if not line:continue
                if not line.startswith('/') or current is None:raise ValueError('unexpected listing output')
                fields=line.split('/')
                if len(fields)!=8:raise ValueError('unsupported listing row')
                inode,mode,uid,gid,name,size=fields[1:7]
                if int(inode)==0:continue # unused/deleted directory slot
                if name in ('.','..') and not (name=='.' and current=='/'):continue
                path='/' if name=='.' else current.rstrip('/')+'/'+name
                if path in records:raise ValueError('duplicate directory entry')
                ino=int(inode);mode=int(mode,8)
                raw.seek(tables[(ino-1)//ipg]*4096+((ino-1)%ipg)*inode_size);data=raw.read(inode_size)
                u16=lambda n:struct.unpack_from('<H',data,n)[0]
                u32=lambda n:struct.unpack_from('<I',data,n)[0]
                if (mode!=u16(0) or int(uid)!=u16(2)+(u16(0x78)<<16)
                    or int(gid)!=u16(0x18)+(u16(0x7a)<<16)):raise ValueError('raw inode/listing disagreement')
                extra=u16(0x80);acl=u32(0x68)+(u16(0x76)<<32)
                acl_hash=None
                if acl:raw.seek(acl*4096);acl_hash=hashlib.sha256(raw.read(4096)).hexdigest()
                item={'inode':ino,'mode':mode,'uid':int(uid),'gid':int(gid),'links':u16(0x1a),
                      'size':u32(4)+(u32(0x6c)<<32),'flags':u32(0x20),'blocks':u32(0x1c)+(u16(0x74)<<32),
                      'inline_xattr_sha256':hashlib.sha256(data[128+extra:]).hexdigest(),'external_xattr_sha256':acl_hash,
                      'atime':u32(8),'ctime':u32(0xc),'mtime':u32(0x10),'generation':u32(0x64),
                      'inode_bytes_sha256':hashlib.sha256(data).hexdigest()}
                records[path]=item
                if stat.S_ISDIR(mode) and path!='/':
                    if ino in seen:raise ValueError('directory hardlink/cycle')
                    seen.add(ino);next_dirs.append(path)
            if section!=len(pending) or len(records)>200000:raise ValueError('incomplete/oversized catalog')
            pending=next_dirs
    tree=out/'tree';tree.mkdir()
    _,err=tool(host,'debugfs',['-R','rdump / '+quote(str(tree)),image]);(out/'rdump.log').write_text(err)
    for path,item in records.items():
        target=tree/path.lstrip('/')
        if stat.S_ISREG(item['mode']):
            if not stat.S_ISREG(target.lstat().st_mode) or target.stat().st_size!=item['size']:raise ValueError('incomplete extracted file')
            item['content_sha256']=digest(target)
        elif stat.S_ISLNK(item['mode']):item['symlink_target']=os.readlink(target)
    (out/'catalog.json').write_text(json.dumps(records,sort_keys=True,separators=(',',':'))+'\n')
    return records,metadata,tables,ipg,inode_size


def analyze(before,after,host,out):
    out.mkdir(parents=True,exist_ok=False)
    a,meta_a,tables,ipg,isize=catalog(before,host,out/'before')
    b,meta_b,_,_,_=catalog(after,host,out/'after')
    added=sorted(set(b)-set(a));removed=sorted(set(a)-set(b))
    logical_diffs=[];directory_layout=[];inode_changes=[]
    ignored={'inode_bytes_sha256','flags','blocks'}
    for path in sorted(set(a)&set(b)):
        one,two=a[path],b[path]
        skip=ignored|({'size'} if stat.S_ISDIR(one['mode']) else set())
        changed={k:[one.get(k),two.get(k)] for k in set(one)|set(two) if k not in skip and one.get(k)!=two.get(k)}
        if changed:logical_diffs.append({'path':path,'changed':changed})
        if one['inode_bytes_sha256']!=two['inode_bytes_sha256']:
            inode_changes.append(path)
            if stat.S_ISDIR(one['mode']):directory_layout.append({'path':path,'inode':one['inode'],'size_before':one['size'],'size_after':two['size'],'flags_before':one['flags'],'flags_after':two['flags'],'blocks_before':one['blocks'],'blocks_after':two['blocks']})
    # Extent trees/data for changed directories explain physical reindex writes.
    directory_blocks=set();extent_blocks=set()
    def extent(raw,data,depth=0):
        if depth>5 or struct.unpack_from('<H',data,0)[0]!=0xf30a:raise ValueError('invalid extent tree')
        count,_,level=struct.unpack_from('<HHH',data,2)
        for index in range(count):
            offset=12+index*12
            if level:
                _,lo,hi=struct.unpack_from('<IIH',data,offset);block=lo+(hi<<32)
                extent_blocks.add(block);raw.seek(block*4096);extent(raw,raw.read(4096),depth+1)
            else:
                _,length,hi,lo=struct.unpack_from('<IHHI',data,offset)
                for block in range(lo+(hi<<32),lo+(hi<<32)+(length&0x7fff)):directory_blocks.add(block)
    for image,records in [(before,a),(after,b)]:
        with image.open('rb') as raw:
            for row in directory_layout:
                ino=records[row['path']]['inode'];raw.seek(tables[(ino-1)//ipg]*4096+((ino-1)%ipg)*isize)
                data=raw.read(isize);extent(raw,data[40:100])
    changed_blocks=collections.Counter();unknown=[];changed_bytes=0
    with before.open('rb') as one,after.open('rb') as two:
        block=0
        while True:
            x=one.read(4096);y=two.read(4096)
            if not x and not y:break
            if len(x)!=len(y):raise ValueError('image size mismatch')
            if x!=y:
                label=meta_a.get(block) or meta_b.get(block)
                if not label:label='directory_extent_tree' if block in extent_blocks else ('directory_data_or_index' if block in directory_blocks else 'unclassified')
                changed_blocks[label]+=1;changed_bytes+=sum(a!=b for a,b in zip(x,y))
                if label=='unclassified':unknown.append(block)
            block+=1
    result={'schema':1,'scope':'Read-only complete comparison of disposable laboratory images; not owner-image acceptance',
            'before_sha256':digest(before),'after_sha256':digest(after),'entries_before':len(a),'entries_after':len(b),
            'entry_types':dict(collections.Counter('directory' if stat.S_ISDIR(r['mode']) else ('regular' if stat.S_ISREG(r['mode']) else ('symlink' if stat.S_ISLNK(r['mode']) else 'special')) for r in a.values())),
            'added_paths':added,'removed_paths':removed,'logical_differences':logical_diffs,'changed_inode_count':len(inode_changes),
            'directory_layout_changes':directory_layout,'changed_blocks_by_structure':dict(changed_blocks),'unclassified_changed_blocks':unknown,
            'changed_bytes_total':changed_bytes,'logical_comparison_fields':['path->inode','mode','uid','gid','links','regular size/content SHA256','symlink target','timestamps','xattrs','inode generation'],
            'raw_inode_hashes_and_directory_physical_layout_excluded_from_logical_equality':True,
            'full_before_catalog_sha256':digest(out/'before/catalog.json'),'full_after_catalog_sha256':digest(out/'after/catalog.json')}
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--before',type=Path,required=True);p.add_argument('--after',type=Path,required=True)
    p.add_argument('--host',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();r=analyze(a.before.resolve(),a.after.resolve(),a.host.resolve(),a.output.resolve())
    print(json.dumps({k:r[k] for k in ['entries_before','entries_after','entry_types','added_paths','removed_paths','logical_differences','changed_inode_count','changed_blocks_by_structure','unclassified_changed_blocks','changed_bytes_total']},indent=2))
