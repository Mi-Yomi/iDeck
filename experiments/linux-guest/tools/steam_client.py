#!/usr/bin/env python3
"""Pinned official ARM64 client installer for PRIVATE experiments, not payloads.

No login, agreement acceptance, binary patching or sandbox changes. Metadata is
captured from Valve HTTPS and reviewed as a lock; updates require a new lock.
The parser/installer is original code, informed by the attributed DroidDeck flow.
"""
import argparse
import ctypes
import errno
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import posixpath
import re
import shutil
import stat
import sys
import tempfile
import urllib.parse
import urllib.request
import zipfile

CDN='https://client-update.fastly.steamstatic.com'
MANIFEST='steam_client_steamdeck_publicbeta_linuxarm64'
HOSTS={'client-update.steamstatic.com','client-update.akamai.steamstatic.com','client-update.fastly.steamstatic.com'}
UPSTREAM='64d78aa812305d707700e2ad460f3b94d03ed50c'

def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def parse_vdf(data):
    text=data.decode('utf-8');tokens=re.findall(r'"([^"\r\n]*)"|([{}])',text)
    if re.sub(r'"[^"\r\n]*"|[{}]|\s','',text):raise ValueError('unsupported manifest syntax')
    values=[a or b for a,b in tokens];index=0
    def obj(nested=False):
        nonlocal index
        out={}
        while index<len(values):
            key=values[index];index+=1
            if key=='}':
                if not nested:raise ValueError('extra manifest brace')
                return out
            if key in ('{','') or key in out or index==len(values):raise ValueError('invalid/duplicate manifest key')
            value=values[index];index+=1
            out[key]=obj(True) if value=='{' else value
        if nested:raise ValueError('unclosed manifest object')
        return out
    return obj()

def capture(manifest):
    data=manifest.read_bytes()
    if len(data)>1024*1024:raise ValueError('manifest too large')
    root=parse_vdf(data)['linuxarm64'];parts=[]
    for name,item in root.items():
        if isinstance(item,dict) and (name.endswith('_all') or name.endswith('_linuxarm64_linuxarm64')):
            parts.append({'component':name,'file':item['file'],'size':int(item['size']),'sha256':item['sha2']})
    lock={'schema':1,'kind':'private-steam-arm64-experiment','channel':'steamdeck_publicbeta',
          'version':root['version'],'manifest_url':CDN+'/'+MANIFEST,'manifest_sha256':hashlib.sha256(data).hexdigest(),
          'upstream_commit':UPSTREAM,'redistribution_approved':False,'parts':sorted(parts,key=lambda p:p['component'])}
    validate(lock);return lock

def validate(lock):
    if (lock.get('schema')!=1 or lock.get('kind')!='private-steam-arm64-experiment'
            or lock.get('channel')!='steamdeck_publicbeta' or lock.get('redistribution_approved') is not False
            or not re.fullmatch(r'[0-9]+',str(lock.get('version','')))
            or lock.get('manifest_url')!=CDN+'/'+MANIFEST
            or not re.fullmatch(r'[0-9a-f]{64}',lock.get('manifest_sha256',''))):raise ValueError('invalid Steam lock')
    parts=lock.get('parts',[]);names=set();components=set()
    if not 1<=len(parts)<=64:raise ValueError('invalid component count')
    for part in parts:
        if (set(part)!={'component','file','size','sha256'} or part['file'] in names or part['component'] in components
                or not re.fullmatch(r'[a-zA-Z0-9_.-]+\.zip\.[0-9a-f]{40}',part['file'])
                or not part['file'].startswith(part['component']+'.zip.')
                or not (part['component'].endswith('_all') or part['component'].endswith('_linuxarm64_linuxarm64'))
                or type(part['size']) is not int or not 0<part['size']<1024**3
                or not re.fullmatch(r'[0-9a-f]{64}',part['sha256'])):raise ValueError('invalid Steam component')
        names.add(part['file']);components.add(part['component'])
    if 'bins_linuxarm64_linuxarm64' not in {p['component'] for p in parts}:raise ValueError('ARM64 native component absent')
    if sum(p['size'] for p in parts)>2*1024**3:raise ValueError('Steam download bound')
    return lock

def checked(path,part):
    if path.is_symlink() or not path.is_file() or path.stat().st_size!=part['size'] or sha(path)!=part['sha256']:
        raise ValueError('Steam component integrity mismatch: '+part['component'])

class Redirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,url):
        parsed=urllib.parse.urlsplit(url)
        if parsed.scheme!='https' or parsed.hostname not in HOSTS or parsed.username or parsed.password:
            raise ValueError('unapproved Steam redirect')
        return super().redirect_request(req,fp,code,msg,headers,url)

def download(lock,cache):
    validate(lock);cache.mkdir(parents=True,exist_ok=True)
    if cache.is_symlink():raise ValueError('symlink cache')
    for part in lock['parts']:
        dest=cache/part['file']
        if dest.exists():checked(dest,part);continue
        fd,tmp=tempfile.mkstemp(prefix='.steam-part-',dir=cache)
        try:
            count=0
            with os.fdopen(fd,'wb') as target,urllib.request.build_opener(Redirect).open(CDN+'/'+part['file'],timeout=60) as src:
                while data:=src.read(1024*1024):
                    count+=len(data)
                    if count>part['size']:raise ValueError('Steam response exceeds lock')
                    target.write(data)
                target.flush();os.fsync(target.fileno())
            checked(Path(tmp),part);os.link(tmp,dest)
        finally:Path(tmp).unlink(missing_ok=True)

def member_name(info):
    name=info.filename.replace('\\','/');path=PurePosixPath(name)
    if (not name or name.startswith('/') or ':' in name or '\x00' in name
            or any(p in ('','..','.') for p in name.rstrip('/').split('/'))
            or (info.flag_bits&1)):
        raise ValueError('unsafe Steam archive member')
    mode=stat.S_IFMT(info.external_attr>>16)
    if mode not in (0,stat.S_IFREG,stat.S_IFDIR,stat.S_IFLNK):raise ValueError('special Steam archive member')
    return path

def link_target(name,data):
    """Only observed basename or single-parent codec aliases, never a chain."""
    if not 0<len(data)<=256:raise ValueError('unsafe Steam link size')
    target=data.decode('ascii')
    if not re.fullmatch(r'(?:\.\./)?[A-Za-z0-9_+.-]+',target) or target in ('.','..','../.','../..'):
        raise ValueError('unsafe Steam link target')
    resolved=posixpath.normpath(posixpath.join(posixpath.dirname(name),target))
    if resolved.startswith('../') or resolved in ('.','..') or resolved.startswith('/'):
        raise ValueError('escaping Steam link target')
    return target,resolved

def archive_inventory(lock,cache):
    total=0;seen={};links={};directories=set()
    for part in lock['parts']:
        path=cache/part['file'];checked(path,part)
        with zipfile.ZipFile(path) as z:
            for info in z.infolist():
                name=member_name(info).as_posix()
                if info.is_dir():directories.add(name);continue
                total+=info.file_size
                if info.file_size>1024**3 or total>4*1024**3:raise ValueError('Steam expanded size bound')
                if name in seen:raise ValueError('overlapping Steam archive entries')
                is_link=stat.S_ISLNK(info.external_attr>>16)
                seen[name]='link' if is_link else 'regular'
                if is_link:
                    if info.file_size>256:raise ValueError('unsafe Steam link size')
                    links[name]=link_target(name,z.read(info))
    for name,(target,resolved) in links.items():
        if name in directories or seen.get(resolved)!='regular':raise ValueError('Steam link requires a regular internal target')
        if any(other.startswith(name+'/') for other in (*seen,*directories)):
            raise ValueError('Steam archive descends through a link')
    return total,links

def publish(stage,destination):
    """Atomic no-replace publication on supported local Windows/Linux hosts."""
    if os.name=='nt':os.rename(stage,destination);return
    if sys.platform!='linux':raise OSError(errno.ENOTSUP,'no atomic no-replace publication available')
    libc=ctypes.CDLL(None,use_errno=True)
    rename=getattr(libc,'renameat2',None)
    if rename is None:raise OSError(errno.ENOTSUP,'renameat2 is required')
    rename.argtypes=[ctypes.c_int,ctypes.c_char_p,ctypes.c_int,ctypes.c_char_p,ctypes.c_uint]
    rename.restype=ctypes.c_int
    if rename(-100,os.fsencode(stage),-100,os.fsencode(destination),1):
        raise OSError(ctypes.get_errno(),'Steam publication failed')

def install(lock,cache,destination,*,resume=False):
    validate(lock)
    if destination.exists() or destination.is_symlink():raise ValueError('Steam destination exists; no automatic repair/replacement')
    if any(p.is_symlink() for p in destination.parents):raise ValueError('symlink Steam ancestor')
    total,links=archive_inventory(lock,cache)
    destination.parent.mkdir(parents=True,exist_ok=True)
    if shutil.disk_usage(destination.parent).free<total+256*1024**2:raise ValueError('insufficient Steam staging space')
    if resume:
        # Reserved installer tree only, serialized by the device install owner.
        # A killed extraction restarts from verified ZIPs; no published data moves.
        stage=destination.parent/('.steam-install-'+lock['manifest_sha256'])
        if os.path.lexists(stage):
            state=stage.lstat()
            if not stat.S_ISDIR(state.st_mode) or state.st_uid!=os.geteuid() or stat.S_IMODE(state.st_mode)!=0o700:
                raise ValueError('unsafe resumable Steam staging')
            shutil.rmtree(stage)
        stage.mkdir(mode=0o700)
    else:
        stage=Path(tempfile.mkdtemp(prefix='.steam-install-',dir=destination.parent))
    try:
        for part in lock['parts']:
            with zipfile.ZipFile(cache/part['file']) as z:
                for info in z.infolist():
                    dest=stage.joinpath(*member_name(info).parts)
                    if info.is_dir():dest.mkdir(parents=True,exist_ok=True);continue
                    if stat.S_ISLNK(info.external_attr>>16):continue
                    dest.parent.mkdir(parents=True,exist_ok=True)
                    with z.open(info) as src,dest.open('wb') as target:
                        shutil.copyfileobj(src,target,1024*1024)
                        target.flush();os.fsync(target.fileno())
                    with dest.open('rb') as f:prefix=f.read(4)
                    dest.chmod(0o755 if (info.external_attr>>16)&0o111 or prefix.startswith((b'\x7fELF',b'#!')) else 0o644)
        # Every regular byte is extracted before aliases; no extraction follows links.
        for name,(target,resolved) in links.items():
            dest=stage.joinpath(*PurePosixPath(name).parts)
            actual=stage.joinpath(*PurePosixPath(resolved).parts)
            if not actual.is_file() or actual.is_symlink():raise ValueError('Steam link target changed')
            dest.parent.mkdir(parents=True,exist_ok=True)
            dest.symlink_to(target)
        native=stage/'steamrtarm64/steam'
        header=native.read_bytes()[:20]
        if header[:6]!=b'\x7fELF\x02\x01' or int.from_bytes(header[18:20],'little')!=183:raise ValueError('not an authentic ARM64 ELF layout')
        (stage/'package').mkdir(exist_ok=True)
        (stage/'package/beta').write_text(lock['channel']+'\n')
        (stage/'package/ideck-install.json').write_text(json.dumps({'version':lock['version'],
            'manifest_sha256':lock['manifest_sha256'],'expanded_bytes':total,'private_experiment':True,
            'agreement_accepted':False,'login_performed':False},indent=2)+'\n')
        # Rename publishes the complete tree only. Never replace an existing install.
        if destination.exists():raise ValueError('Steam destination appeared during install')
        for directory,_,_ in os.walk(stage,topdown=False):
            if os.name=='posix':
                fd=os.open(directory,os.O_RDONLY|os.O_DIRECTORY)
                try:os.fsync(fd)
                finally:os.close(fd)
        publish(stage,destination)
        if os.name=='posix':
            fd=os.open(destination.parent,os.O_RDONLY|os.O_DIRECTORY)
            try:os.fsync(fd)
            finally:os.close(fd)
        return {'status':'installed','version':lock['version'],'expanded_bytes':total,'native_machine':'AArch64',
                'client_executed':False,'agreement_accepted':False}
    finally:
        if stage.exists():shutil.rmtree(stage)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=('capture','download','install'))
    p.add_argument('--lock',type=Path,required=True);p.add_argument('--manifest',type=Path)
    p.add_argument('--cache',type=Path);p.add_argument('--destination',type=Path)
    p.add_argument('--resume',action='store_true',help='Restart only the reserved, unpublished installer tree')
    a=p.parse_args()
    if a.command=='capture':
        if a.lock.exists() or not a.manifest:p.error('new lock and --manifest required')
        result=capture(a.manifest);a.lock.parent.mkdir(parents=True,exist_ok=True);a.lock.write_text(json.dumps(result,indent=2)+'\n')
    else:
        if not a.cache:p.error('--cache required')
        lock=validate(json.loads(a.lock.read_text()))
        if a.command=='download':download(lock,a.cache);result={'status':'downloaded','parts':len(lock['parts'])}
        else:
            if not a.destination:p.error('--destination required')
            if hasattr(os,'geteuid') and os.geteuid()==0:p.error('install the private client as a normal guest user')
            result=install(lock,a.cache,a.destination,resume=a.resume)
    print(json.dumps(result,indent=2))
