#!/usr/bin/env python3
"""Future Mac source-only 37-unit ntdll archive control. Never links/executes it.

Arguments: MADEIRA WINE_HEADERS FREETYPE FFMPEG GNUTLS CRYPTO_PROOF PROOF_HELPER OUT
All prefixes/proof must already be imported, verified and prepared by the outer
stage. This helper downloads, installs, signs and dispatches nothing.
"""
from __future__ import annotations
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import struct
import sys

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
MADEIRA = '279fd0f83170425db002fe25d6bd62f6355f497d'
WINE = '9129e9684daaeae70da9435e7c6060e59392634e'
MANIFEST_SHA256 = '8d487906f5bf8c402456584631bf8cb142242c2f6193eb30f1257f48a0dc1b6d'
PROOF_HELPER_SHA256 = '6d3a662a0760a17d329675bea3d3445959f9e85ed7d0d37ff7e608f3a055af9f'
CONFIG_SHA256 = '22332cb47937d006792e911322c2978a953d25fb5c883837c952b05e7e4077e4'
ARTIFACTS = {'wine-headers':'7049a985768cf3bcd100c0fea2fcbdb2cd28d8cf3087a63b24936f023055ebc2', 'freetype':'0a2520d9f9eeb1281387c01bb2e7e612302567ab9a735c5ae28e24e2285454fc', 'ffmpeg':'5530af1588c577f022f15911bedb683509263d93ea4df88ec2b7efd9d75f2bd8'}
TABLES = {'audio_null_ios.o':('audio_null_ios',37), 'nsi_unixlib_ios.o':('nsi',3), 'ws2_32_unixlib.o':('ws2_32',5), 'bcrypt_unixlib.o':('bcrypt',18), 'secur32_unixlib.o':('secur32',22), 'crypt32_unixlib.o':('crypt32',7), 'dwrite_unixlib.o':('dwrite',10), 'dnsapi_unixlib.o':('dnsapi',4), 'winegstreamer_unixlib.o':('winegstreamer',37)}
CRYPTO_MEMBERS = frozenset(('bcrypt_unixlib.o','secur32_unixlib.o','crypt32_unixlib.o'))
OVERLAY_SCOPE = ['bcrypt/gnutls.c', 'secur32/schannel_gnutls.c', 'Madeira crypt32_unixlib_ios.c']
INHERITED_DIAGNOSTICS = ['-Wno-implicit-function-declaration','-Wno-int-conversion']
ANCHORS = {
    'gnutls_symtab_ios.o': ('ios_gnutls_dlopen','ios_gnutls_dlsym','ios_gnutls_dlclose'),
    'madsync.o': ('madsync_enabled','madsync_ref','madsync_close','madsync_post','madsync_take','madsync_ioctl'),
    'nsi_network_ios.o': ('nsi_enumerate_all_ex','nsi_get_all_parameters_ex','nsi_get_parameter_ex'),
    'nsi_ndis.o': ('ndis_module','convert_unix_name_to_luid','convert_luid_to_unix_name'),
    'nsi_ip.o': ('ipv4_module','ipv6_module'),
    'wg_parser_apple_ios.o': ('mav_apple_video_backend','mav_apple_audio_backend'),
    'cdrom.o': ('cdrom_DeviceIoControl',), 'debug.o': ('__wine_dbg_output',),
    'env.o': ('init_environment',), 'file.o': ('NtCreateFile','NtReadFile','NtWriteFile'),
    'loader.o': ('__wine_main',), 'loadorder.o': ('get_load_order',),
    'process.o': ('NtTerminateProcess','NtQueryInformationProcess'),
    'registry.o': ('NtCreateKey',), 'security.o': ('NtAccessCheck',),
    'serial.o': ('serial_DeviceIoControl',), 'server.o': ('wine_server_call','server_init_process'),
    'signal_arm64.o': ('__wine_syscall_dispatcher','__wine_syscall_dispatcher_return','__wine_unix_call_dispatcher'),
    'socket.o': ('sock_ioctl',), 'sync.o': ('NtWaitForSingleObject',),
    'syscall.o': ('KeServiceDescriptorTable','KeAddSystemServiceTable'),
    'system.o': ('NtQuerySystemInformation',), 'tape.o': ('tape_DeviceIoControl',),
    'thread.o': ('NtCreateThreadEx',), 'virtual.o': ('NtAllocateVirtualMemory',),
}
EMPTY_ARCHITECTURE_MEMBERS = frozenset(('signal_arm.o','signal_i386.o','signal_x86_64.o'))
MIB=1024*1024

class ControlError(Exception): pass

def require(value, message):
    if not value: raise ControlError(str(message))

def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(MIB),b''): h.update(chunk)
    return h.hexdigest()

def safe(path, directory=False, fresh=False):
    p=Path(path).absolute()
    require('..' not in p.parts and not any(ord(c)<32 or ord(c)==127 or c in ':#$\\' for c in str(p)), 'Unsupported/noncanonical path')
    require(not any(q.is_symlink() for q in (p,*p.parents)), 'Symlink input/output path')
    require(p.resolve(strict=False)==p, 'Canonical path required')
    if fresh: require(not p.exists(), 'Fresh output required')
    else: require(p.is_dir() if directory else p.is_file(), 'Missing regular input: '+str(p))
    return p

def regular(path, maximum=64*MIB, allow_empty=False):
    p=safe(path)
    require((0 if allow_empty else 1)<=p.stat().st_size<=maximum, 'Input size bound exceeded: '+str(p))
    return p

def read_json(path, maximum=16*MIB):
    def unique(pairs):
        result={}
        for k,v in pairs:
            require(k not in result,'Duplicate JSON key');result[k]=v
        return result
    return json.loads(regular(path,maximum).read_text(), object_pairs_hook=unique)

def write_json(path, value):
    path=Path(path); tmp=path.with_name(path.name+'.pending')
    require(not tmp.exists() and not tmp.is_symlink(),'Unexpected temporary output')
    tmp.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n');tmp.replace(path)

def load_manifest():
    p=regular(PACKAGE/'ntdll-source-manifest.json')
    require(digest(p)==MANIFEST_SHA256,'Reviewed source manifest changed')
    data=read_json(p)
    require(data['madeira']==MADEIRA and data['wine']==WINE,'Source pin mismatch')
    units=data['units'];require(len(units)==37 and len({u['member'] for u in units})==37,'Exact37 units required')
    require({u['member'] for u in units if u['crypto_overlay']}==CRYPTO_MEMBERS,'Overlay scope drift')
    return data

def load_proof_helper(path):
    path=regular(path,MIB)
    require(digest(path)==PROOF_HELPER_SHA256,'Frozen target-proof helper hash mismatch')
    spec=importlib.util.spec_from_file_location('reviewed_crypto_proof',path)
    module=importlib.util.module_from_spec(spec)
    previous=sys.dont_write_bytecode;sys.dont_write_bytecode=True
    try:spec.loader.exec_module(module)
    finally:sys.dont_write_bytecode=previous
    module.load_contract() # Pins adjacent106-symbol lock and typed own probe.
    return module

def check_files(root, records, size_key='size'):
    mapping={}
    for row in records:
        name=row['path'];p=Path(name)
        require(not p.is_absolute() and '..' not in p.parts and p.as_posix()==name,'Invalid manifest file name')
        path=regular(root/p,256*MIB,allow_empty=True)
        require(str(path) not in mapping,'Duplicate manifest file')
        require(path.stat().st_size==row[size_key] and digest(path)==row['sha256'],'Immutable input mismatch: '+str(path))
        mapping[str(path)]={'path':name,'sha256':row['sha256'],'size':row[size_key]}
    return mapping

def enumerate_files(root):
    out=set()
    for parent,dirs,files in os.walk(root,followlinks=False):
        for name in dirs: safe(Path(parent)/name,directory=True)
        for name in files: out.add(str(safe(Path(parent)/name)))
        require(len(out)<=20000,'Prefix file bound exceeded')
    return out

def verify_imported_prefix(prefix, kind, expected):
    path=regular(prefix.parent/'import-manifest.json')
    record=read_json(path)
    require(record['status']=='imported-exact-reviewed-bytes' and record['original_archive_sha256']==ARTIFACTS[kind],'Unverified/wrong dependency producer')
    require(record['metadata_rewritten'] is False and record['target_executed'] is False,'Unexpected dependency import mutation/execution')
    require(record['producer']['madeira']==MADEIRA,'Dependency source pin mismatch')
    require(all(r['content_changed'] is False for r in record['prefix_files']),'Dependency content was changed')
    normalized=[{'path':r['path'],'sha256':r['sha256'],'size':r['bytes']} for r in record['prefix_files']]
    require(sorted(normalized,key=lambda r:r['path'])==expected['prefix_files'] and record['producer']==expected['producer'] and record['original_archive_sha256']==expected['archive_sha256'],'Transport manifest does not match frozen exact prefix bytes')
    files=check_files(prefix,record['prefix_files'],'bytes')
    require(set(files)==enumerate_files(prefix),'Extra/missing mapped prefix input')
    return files,{'manifest':str(path),'sha256':digest(path),'original_archive_sha256':record['original_archive_sha256'],'files':record['prefix_files']}

def expected_overlay():
    return ('/* Generated only after passed real iOS GnuTLS API/link proof. */\n'
            '#ifndef MADEIRA_VALIDATED_GNUTLS_FEATURES_H\n#define MADEIRA_VALIDATED_GNUTLS_FEATURES_H\n'
            '#ifndef __WINE_CONFIG_H\n#error Original immutable Wine config must be included first\n#endif\n'
            '#if defined(HAVE_GNUTLS_CIPHER_INIT) || defined(SONAME_LIBGNUTLS)\n#error Unexpected base TLS feature macros\n#endif\n'
            '#define HAVE_GNUTLS_CIPHER_INIT 1\n'
            '/* Static-provider token consumed by the existing iOS GnuTLS shim. */\n'
            '#define SONAME_LIBGNUTLS "libgnutls.a"\n#endif\n')

def verify_overlay(proof_module, prefix, proof_dir, config):
    # The frozen helper performs real-input/hash/platform/command revalidation.
    proof=proof_module.verify_passed_proof(prefix,proof_dir,config)
    metadata=read_json(proof_dir/'feature-overlay.json',MIB)
    name=metadata.get('path','')
    require(re.fullmatch(r'[A-Za-z0-9_-]+\.h',name),'Invalid overlay filename')
    path=regular(proof_dir/name,MIB)
    require(metadata.get('apply_only_to')==OVERLAY_SCOPE,'Unreviewed overlay consumer scope')
    require(metadata.get('base_config_sha256')==CONFIG_SHA256 and metadata.get('proof_sha256')==digest(proof_dir/'proof.json'),'Overlay proof/config provenance mismatch')
    require(metadata.get('sha256')==digest(path) and path.read_text()==expected_overlay(),'Overlay text is not the exact reviewed two-macro wrapper')
    return path,{'manifest_sha256':digest(proof_dir/'feature-overlay.json'),'proof_sha256':digest(proof_dir/'proof.json'),'overlay_sha256':digest(path),'path':str(path),'proof':proof}

def render_symtab(symbols, tracked_source):
    require(len(symbols)==106 and len(set(symbols))==106 and all(re.fullmatch(r'gnutls_[a-z0-9_]+',x) for x in symbols),'Exact106 API contract required')
    symbols=sorted(symbols)
    suffix=tracked_source.split('#define IOS_GNUTLS_MAGIC',1)
    require(len(suffix)==2,'Pinned static resolver body missing')
    source='/* Generated by gen_gnutls_symtab.sh — do not edit. */\n#include <string.h>\n#include <dlfcn.h>\n\n'
    source+=''.join(f'extern char ios_gts_{i} __asm__("_{name}");\n' for i,name in enumerate(symbols))
    source+='\nstatic const struct { const char *name; void *addr; } ios_gnutls_symtab[] = {\n'
    source+=''.join(f'    {{ "{name}", &ios_gts_{i} }},\n' for i,name in enumerate(symbols))
    source+='};\n\n#define IOS_GNUTLS_MAGIC'+suffix[1]
    return source

def target_guard():
    return ('/* Own target identity assertions only; no feature declarations/providers. */\n'
            '#include <TargetConditionals.h>\n'
            '#if !defined(__APPLE__) || !defined(__aarch64__) || !defined(__LP64__)\n#error Expected Apple arm64 LP64\n#endif\n'
            '#if !TARGET_OS_IPHONE || TARGET_OS_SIMULATOR\n#error Expected physical iPhoneOS SDK\n#endif\n'
            '#if !defined(__ENVIRONMENT_IPHONE_OS_VERSION_MIN_REQUIRED__) || __ENVIRONMENT_IPHONE_OS_VERSION_MIN_REQUIRED__ != 170000\n#error Expected exact iOS17.0 deployment target\n#endif\n'
            '_Static_assert(sizeof(void *) == 8, "Expected LP64");\n')

def compiler_args(unit, paths, clang, sdk, overlay):
    source,headers,ft,ff,gn,output=map(Path,(paths['source'],paths['headers'],paths['freetype'],paths['ffmpeg'],paths['gnutls'],paths['output']))
    build=source/'build/ntdll-unix';wine=source/'wine'
    args=[str(clang),'-arch','arm64','-isysroot',str(sdk),'-miphoneos-version-min=17.0','-O2','-fPIC','-fvisibility=hidden','-fno-stack-protector','-fno-strict-aliasing','-include',str(output/'generated/target_contract.h')]
    if unit['kind']=='apple': args+=['-Wall','-Werror=implicit-function-declaration']
    else:
        args+=INHERITED_DIAGNOSTICS+['-include',str(headers/'include/config.h')]
        if unit['crypto_overlay']: args+=['-include',str(overlay)]
        args+=['-include',str(build/'shims/wine_ios_exit.h'),'-I'+str(build/'shims'),'-I'+str(source/'build/madsync'),'-DHAVE_LINUX_NTSYNC_H=1']
        if unit['kind']=='core': args+=['-I'+str(wine/'dlls/ntdll'),'-I'+str(wine/'dlls/ntdll/unix')]
        args+=['-I'+str(headers/'include'),'-I'+str(wine/'include'),'-D__WINESRC__','-D_NTSYSTEM_','-D_ACRTIMP=','-DWINBASEAPI=','-DWINE_UNIX_LIB','-DWINE_IOS=1']
        if unit['kind']=='core':
            args+=['-DLTC_NO_PROTOTYPES','-DLTC_SOURCE','-DBINDIR="/usr/local/bin"','-DLIBDIR="/usr/local/lib"','-DDATADIR="/usr/local/share"','-DSYSTEMDLLPATH=""','-Dget_thread_context=ntdll_get_thread_context','-Dset_thread_context=ntdll_set_thread_context']
        else:
            prefix=unit['unix_prefix'];args+=['-D__wine_unix_call_funcs='+prefix+'_unix_call_funcs','-D__wine_unix_call_wow64_funcs='+prefix+'_unix_call_wow64_funcs']
            args+=['-I'+str(wine/'dlls'/prefix)]
            if unit['crypto_overlay']:args+=['-I'+str(gn/'include'),'-include',str(source/'build/crypto-unix/ios_gnutls_shim.h')]
            elif prefix=='dwrite':args+=['-I'+str(ft/'include')]
            elif prefix=='winegstreamer':args+=['-I'+str(ff/'include')]
    src=output/'generated/gnutls_symtab_ios.c' if unit['generated_source'] else source/unit['path']
    obj=output/'objects'/unit['member'];dep=output/'dependencies'/(unit['member']+'.d')
    return args+['-MD','-MF',str(dep),'-MT',str(obj),'-c',str(src),'-o',str(obj)]

def parse_dependencies(text, expected_target):
    text=text.replace('\\\n','')
    require('\r' not in text and '$' not in text,'Unsupported dependency syntax')
    # Clang Makefile escaping, without shell or make evaluation.
    tokens=[];token='';escaped=False
    for char in text:
        if escaped:token+=char;escaped=False
        elif char=='\\':escaped=True
        elif char.isspace():
            if token:tokens.append(token);token=''
        else:token+=char
    require(not escaped,'Truncated dependency escape')
    if token:tokens.append(token)
    require(tokens and tokens.pop(0)==str(expected_target)+':','Unexpected dependency target')
    require(tokens and all(x.startswith('/') and ':' not in x for x in tokens),'Expected absolute file dependencies')
    return list(dict.fromkeys(tokens))

def parse_undefined(text):
    symbols=[]
    for line in text.splitlines():
        line=line.strip()
        if not line or line.endswith(':') or line.endswith(': no symbols'):continue
        m=re.fullmatch(r'(?:U\s+)?(_[A-Za-z0-9_.$]+)',line)
        require(m is not None,'Unexpected nm undefined output: '+line[:120])
        symbols.append(m.group(1))
    require(len(set(symbols))==len(symbols),'Duplicate undefined symbol record')
    return sorted(symbols)

def read_external_sections(data):
    # Called only after the frozen helper's strict arm64/iOS raw parser passed.
    ncmds,size=struct.unpack_from('<II',data,16);offset=32;sections=[];symtab=None
    for _ in range(ncmds):
        code,length=struct.unpack_from('<II',data,offset)
        if code==0x19:
            count=struct.unpack_from('<I',data,offset+64)[0]
            for i in range(count):
                p=offset+72+80*i
                section=data[p:p+16].rstrip(b'\0').decode();segment=data[p+16:p+32].rstrip(b'\0').decode()
                address,bytes_count=struct.unpack_from('<QQ',data,p+32)
                sections.append({'segment':segment,'section':section,'address':address,'size':bytes_count})
        elif code==2:
            require(symtab is None,'Duplicate symbol table');symtab=struct.unpack_from('<IIII',data,offset+8)
        offset+=length
    if symtab is None:return {}
    symoff,nsyms,stroff,strsize=symtab
    require(symoff+nsyms*16<=len(data) and stroff+strsize<=len(data),'Invalid symbol table bounds')
    result={}
    for i in range(nsyms):
        strx,kind,section,desc,value=struct.unpack_from('<IBBHQ',data,symoff+i*16)
        if not strx or kind&0xE0 or not kind&1 or kind&0x0E!=0x0E:continue
        require(strx<strsize and 0<section<=len(sections),'Invalid external section/string')
        stop=data.find(b'\0',stroff+strx,stroff+strsize);require(stop>=0,'Unterminated symbol')
        name=data[stroff+strx:stop].decode('ascii');require(name not in result,'Duplicate defined external symbol')
        result[name]={**sections[section-1],'symbol_address':value,'section_index':section}
    return result

def verify_tables(member, definitions):
    require('_'+'__wine_unix_call_funcs' not in definitions and '_'+'__wine_unix_call_wow64_funcs' not in definitions,'Unrenamed generic Unix table')
    needed=[]
    if member in TABLES:
        prefix,count=TABLES[member]
        needed=[(prefix+'_unix_call_funcs',count),(prefix+'_unix_call_wow64_funcs',count)]
    if member=='loader.o':needed.append(('unix_call_wow64_funcs',13))
    found=[]
    for name,count in needed:
        require('_'+name in definitions,'Required real ordinary/WoW64 table absent: '+name)
        record=definitions['_'+name]
        require(record['section'] in ('__const','__data') and record['segment'] in ('__DATA','__DATA_CONST'),'Table is not an external data definition')
        relative=record['symbol_address']-record['address']
        require(0<=relative and relative+count*8<=record['size'],'Table data extent shorter than source contract')
        found.append({'symbol':name,'expected_pointer_count_from_pinned_source':count,'minimum_table_bytes':count*8,'actual_definition':record})
    return found

class Control:
    def __init__(self,args):
        require(len(args)==8,'Expected eight arguments')
        keys=('source','headers','freetype','ffmpeg','gnutls','crypto_proof','proof_helper','output')
        self.paths={key:safe(value,directory=key not in ('proof_helper','output'),fresh=key=='output') for key,value in zip(keys,args)}
        self.output=self.paths['output'];self.stage='preflight'
        self.helper_sha256=digest(HERE/'build_ntdll_control.py')
        require('.work' in self.output.parts and self.output.parent.is_dir(),'Output must be a fresh .work child')
        for key,path in self.paths.items():
            if key!='output': require(not self.output.is_relative_to(path) and not path.is_relative_to(self.output),'Output/input roots overlap')
        self.module=load_proof_helper(self.paths['proof_helper'])
        self.manifest=load_manifest()
        self.output.mkdir()
        for name in ('logs','home','tmp','generated','objects','dependencies'):(self.output/name).mkdir()
        self.runner=self.module.Proof(self.paths['gnutls'],self.output)
        self.runner.env['ZERO_AR_DATE']='1'
        self.run=self.runner.run
        self.identities={}

    def verify_inputs(self):
        paths=self.paths;source=paths['source']
        require(self.run('madeira-source-pin',['/usr/bin/git','-C',source,'rev-parse','HEAD'])==MADEIRA,'Wrong Madeira checkout')
        require(self.run('wine-source-pin',['/usr/bin/git','-C',source/'wine','rev-parse','HEAD'])==WINE,'Wrong/uninitialized Wine checkout')
        self.identities=check_files(source,self.manifest['sources'])
        transports={}
        for key,kind in (('headers','wine-headers'),('freetype','freetype'),('ffmpeg','ffmpeg')):
            files,record=verify_imported_prefix(paths[key],kind,self.manifest['dependencies'][kind]);self.identities.update(files);transports[key]=record
        actual=check_files(paths['headers']/'include',self.manifest['generated_headers']['headers'])
        require(set(actual)=={p for p in self.identities if Path(p).is_relative_to(paths['headers']/'include')},'Generated header inventory drift')
        config=regular(paths['headers']/'include/config.h',MIB)
        require(digest(config)==CONFIG_SHA256,'Original config must remain immutable')
        overlay,self.crypto=verify_overlay(self.module,paths['gnutls'],paths['crypto_proof'],config)
        self.overlay=overlay
        for row in self.module.inspect_headers(paths['gnutls']):
            p=paths['gnutls']/row['path'];self.identities[str(p)]={'sha256':row['sha256'],'size':row['size'],'path':row['path']}
        self.identities[str(overlay)]={'sha256':digest(overlay),'size':overlay.stat().st_size,'path':overlay.name}
        libraries={}
        for key,names in (('freetype',('libfreetype.a',)),('ffmpeg',('libavcodec.a','libavformat.a','libavutil.a','libswresample.a'))):
            for name in names:libraries[key+'/'+name]=self.module.inspect_archive(paths[key]/'lib'/name)
        self.input_record={'source_manifest_sha256':MANIFEST_SHA256,'source_files':len(self.manifest['sources']),'generated_headers':356,'config_sha256':CONFIG_SHA256,'transports':transports,'crypto_overlay':self.crypto,'dependency_archive_validation':libraries}
        write_json(self.output/'inputs.json',self.input_record)

    def prepare_generated(self):
        _,symbols,_=self.module.load_contract();self.symbols=symbols
        tracked=self.paths['source']/'build/crypto-unix/gnutls_symtab_ios.c'
        source=render_symtab(symbols,tracked.read_text())
        generated=self.output/'generated/gnutls_symtab_ios.c';generated.write_text(source)
        guard=self.output/'generated/target_contract.h';guard.write_text(target_guard())
        for path in (generated,guard):self.identities[str(path)]={'path':str(path.relative_to(self.output)),'sha256':digest(path),'size':path.stat().st_size}
        aliases=[{'alias':'ios_gts_'+str(i),'c_symbol':name,'macho_symbol':'_'+name} for i,name in enumerate(sorted(symbols))]
        write_json(self.output/'generated-source-record.json',{'aliases':aliases,'api_count':106,'generated_path':str(generated.relative_to(self.output)),'generated_sha256':digest(generated),'tracked_source_sha256':digest(tracked),'byte_identical_to_tracked_source':generated.read_bytes()==tracked.read_bytes(),'tracked_source_modified':False,'target_contract_sha256':digest(guard),'crypto_optional_labels_preserved_in_lock':True})

    def dependency_record(self,path,obj,sdk,resource):
        entries=[]
        for name in parse_dependencies(regular(path).read_text(),obj):
            reported=Path(name)
            p=reported.resolve(strict=True)
            require(p==Path(os.path.normpath(name)),'Dependency symlink/lexical path disagreement')
            identity=str(p)
            if identity in self.identities:
                p=regular(p,64*MIB,allow_empty=True);expected=self.identities[identity]
                require(digest(p)==expected['sha256'] and p.stat().st_size==expected['size'],'Dependency changed: '+name)
                entries.append({'path':identity,'reported_path':name,'origin':'verified-source/generated/prefix','sha256':expected['sha256'],'size':expected['size']})
            else:
                # Compiler resource and SDK headers may use Apple installation symlinks.
                require(p.is_file() and (p.is_relative_to(sdk) or p.is_relative_to(resource)),'Unverified source/non-iPhoneOS-SDK include dependency: '+name)
                require(p.stat().st_size<=16*MIB,'Oversized SDK/compiler header')
                entries.append({'path':name,'resolved':str(p),'origin':'sdk' if p.is_relative_to(sdk) else 'selected-clang-resource','sha256':digest(p),'size':p.stat().st_size})
        return entries

    def execute(self):
        require(sys.platform=='darwin','This helper only builds on the reviewed Mac')
        require(self.run('host-architecture',['/usr/bin/uname','-m'])=='arm64','arm64 Mac host required')
        developer=self.runner.select_developer()
        require('Xcode 26.6' in self.run('xcode-version',['/usr/bin/xcodebuild','-version']).splitlines(),'Xcode26.6 required')
        require(self.run('sdk-version',['/usr/bin/xcrun','--sdk','iphoneos','--show-sdk-version'])=='26.5','SDK26.5 required')
        sdk=self.runner.selected_xcode_path(self.run('sdk-path',['/usr/bin/xcrun','--sdk','iphoneos','--show-sdk-path']),developer,directory=True)
        tools={name:self.runner.selected_xcode_path(self.run('find-'+name,['/usr/bin/xcrun','--sdk','iphoneos','--find',name]),developer) for name in ('clang','nm','ar')}
        require(self.run('clang-version',[tools['clang'],'--version']).startswith('Apple clang version '),'Apple clang required')
        resource=self.runner.selected_xcode_path(self.run('clang-resource-dir',[tools['clang'],'-print-resource-dir']),developer,directory=True)
        self.stage='verify-inputs';self.verify_inputs();self.prepare_generated()
        results=[];self.stage='compile'
        for unit in self.manifest['units']:
            name=unit['member'][:-2];args=compiler_args(unit,self.paths,tools['clang'],sdk,self.overlay)
            self.run('compile-'+name,args)
            obj=regular(self.output/'objects'/unit['member']);raw=obj.read_bytes()
            binary=self.module.inspect_macho(raw,unit['member'])
            defs=self.module.parse_nm_definitions(self.run('defined-'+name,[tools['nm'],'-gU',obj]))
            undef=parse_undefined(self.run('undefined-'+name,[tools['nm'],'-u',obj]))
            external=read_external_sections(raw)
            tables=verify_tables(unit['member'],external)
            anchors=ANCHORS.get(unit['member'],())
            require(all('_'+name in external for name in anchors),'Missing source-backed member definition: '+unit['member'])
            require(tables or anchors or unit['member'] in EMPTY_ARCHITECTURE_MEMBERS,'Unspecified member proof contract')
            dep=self.output/'dependencies'/(unit['member']+'.d');deps=self.dependency_record(dep,obj,sdk,resource)
            if unit['crypto_overlay']:
                # Preserve original argv except dependency/output options and compilation mode.
                macro_args=args[:args.index('-MD')]+['-dM','-E',str(self.paths['source']/unit['path'])]
                macros=self.run('macros-'+name,macro_args)
                require(re.search(r'^#define HAVE_GNUTLS_CIPHER_INIT 1$',macros,re.M) and re.search(r'^#define SONAME_LIBGNUTLS "libgnutls.a"$',macros,re.M) and re.search(r'^#define _WIN64(?:\s|$)',macros,re.M),'Real crypto/WoW64 feature macros missing')
                require(str(self.overlay) in {x['path'] for x in deps},'Crypto TU did not consume validated overlay')
            else:require(str(self.overlay) not in {x['path'] for x in deps},'Crypto overlay leaked to another TU')
            if unit['member']=='sync.o':require(str(self.paths['source']/'build/madsync/linux/ntsync.h') in {x['path'] for x in deps},'Real userspace ntsync header was not consumed')
            if unit['member']=='gnutls_symtab_ios.o':require({x for x in undef if x.startswith('_gnutls_')}=={'_'+x for x in self.symbols},'Generated static alias table does not reference all106 APIs')
            row={'member':unit['member'],'source':unit['path'],'generated_source':unit['generated_source'],'argv':args,'sha256':digest(obj),'bytes':obj.stat().st_size,'target':binary,'global_definitions':defs,'undefined_symbols':undef,'source_backed_anchors_present':list(anchors),'tables':tables,'dependency_file':str(dep.relative_to(self.output)),'dependency_sha256':digest(dep),'dependencies':deps}
            results.append(row);write_json(self.output/'units.json',results)
        self.stage='archive';archive=self.output/'libntdll_unix.a'
        self.run('archive',[tools['ar'],'rcs',archive,*[self.output/'objects'/u['member'] for u in self.manifest['units']]])
        actual=self.module.inspect_archive(archive)
        require([x['member'] for x in actual['members']]==[x['member'] for x in results],'Exact37 archive member order mismatch')
        require(all(a['sha256']==b['sha256'] and a['size']==b['bytes'] for a,b in zip(actual['members'],results)),'Archive member content mismatch')
        self.run('archive-members',[tools['ar'],'-t',archive]);self.run('archive-defined',[tools['nm'],'-gU',archive]);self.run('archive-undefined',[tools['nm'],'-u',archive])
        # Revalidate every immutable non-SDK input and the proof after compilation.
        for name,row in self.identities.items():require(digest(regular(name,256*MIB,allow_empty=True))==row['sha256'],'Input changed during control: '+name)
        _,crypto_again=verify_overlay(self.module,self.paths['gnutls'],self.paths['crypto_proof'],self.paths['headers']/'include/config.h')
        require(crypto_again==self.crypto,'Crypto proof/overlay provenance changed during control')
        for transport in self.input_record['transports'].values():require(digest(regular(transport['manifest']))==transport['sha256'],'Transport manifest changed during control')
        require(digest(HERE/'build_ntdll_control.py')==self.helper_sha256 and digest(PACKAGE/'ntdll-source-manifest.json')==MANIFEST_SHA256,'Control helper/source contract changed during build')
        require(digest(self.paths['proof_helper'])==PROOF_HELPER_SHA256,'Proof helper changed')
        require(sum(len(x['tables']) for x in results)==19,'Nine ordinary/WoW64 table pairs plus loader WoW64 table required')
        self.stage='complete'
        result={'result':'passed-source-ntdll-archive-control','scope':'37 real compiled units and ordinary/WoW64 tables; unresolved native/app providers remain for later link','madeira':MADEIRA,'wine':WINE,'source_manifest_sha256':MANIFEST_SHA256,'helper_sha256':digest(HERE/'build_ntdll_control.py'),'proof_helper_sha256':PROOF_HELPER_SHA256,'config_sha256':CONFIG_SHA256,'crypto_overlay_sha256':digest(self.overlay),'member_count':37,'table_symbol_count':19,'archive':actual,'target_binaries_run':False,'native_link_performed':False,'signed':False,'installed':False,'source_modified':False,'developer_selection':self.runner.developer_selection,'sdk':'26.5','xcode':'26.6','tools':{k:{'path':str(p),'sha256':digest(p)} for k,p in tools.items()},'evidence':{n:digest(self.output/n) for n in ('inputs.json','generated-source-record.json','units.json','commands.json')},'inherited_diagnostic_suppressions':INHERITED_DIAGNOSTICS,'timeout_owner':'outer reviewed process-group wrapper'}
        write_json(self.output/'result.json',result)
        return result

def main(argv=None):
    args=list(sys.argv[1:] if argv is None else argv);control=None
    try:
        control=Control(args);control.execute();return 0
    except Exception as error:
        if control is not None:write_json(control.output/'failure.json',{'result':'failed','stage':control.stage,'error':str(error),'target_binaries_run':False,'native_link_performed':False,'source_modified':False})
        print('ntdll source control failed: '+str(error),file=sys.stderr);return 1

if __name__=='__main__':raise SystemExit(main())
