set -eu
export PYTHONDONTWRITEBYTECODE=1
python3 - <<'PY'
from pathlib import Path
import hashlib,importlib.util,json,os,stat,struct
out=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-guarded-v2')
path=Path('/tmp/dumps/assert_20261017181345_5.dmp')
fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
try:
    before=os.fstat(fd)
    if not stat.S_ISREG(before.st_mode) or before.st_uid!=1000 or not 32<=before.st_size<=16*1024**2:raise RuntimeError('unexpected dump identity')
    def read(offset,size):
        if offset<0 or size<0 or offset+size>before.st_size:raise RuntimeError('dump read bound')
        data=os.pread(fd,size,offset)
        if len(data)!=size:raise RuntimeError('short dump read')
        return data
    signature,version,count,directory,checksum,timestamp,flags=struct.unpack('<IIIIIIQ',read(0,32))
    if signature!=0x504d444d or version&0xffff!=0xa793 or count>128:raise RuntimeError('unsupported dump header')
    streams={}
    for i in range(count):
        kind,size,rva=struct.unpack('<III',read(directory+12*i,12))
        if kind in streams or rva+size>before.st_size:raise RuntimeError('invalid stream directory')
        streams[kind]=(size,rva)
    result={'kind':'metadata and address-only read of existing Steam dump','dump_path':str(path),'dump_size':before.st_size,'dump_time':timestamp,'streams':{hex(k):{'size':v[0]} for k,v in streams.items()},'argument_registers_exported':False,'environment_or_message_streams_read':False,'process_attached':False}
    if 7 in streams:result['cpu_architecture']=struct.unpack('<H',read(streams[7][1],2))[0]
    if result.get('cpu_architecture') not in (12,0x8003):raise RuntimeError('ARM64 dump required')
    if 0x47670002 in streams:
        size,rva=streams[0x47670002]
        if size!=776:raise RuntimeError('assertion info size')
        result['assertion']={key:read(rva+256*n,256).decode('utf-16-le').split('\0',1)[0] for n,key in enumerate(('expression','function','file'))}
        result['assertion'].update(zip(('line','type'),struct.unpack('<II',read(rva+768,8))))
    requesting=None
    if 0x47670001 in streams:
        size,rva=streams[0x47670001]
        valid,dump_thread,requesting=struct.unpack('<III',read(rva,12))
        result['breakpad_info']={'valid':valid,'dump_thread':dump_thread,'requesting_thread':requesting}
    if 6 in streams:
        size,rva=streams[6]
        if size!=168:raise RuntimeError('exception stream size')
        tid=struct.unpack('<I',read(rva,4))[0]
        code,exception_flags=struct.unpack('<II',read(rva+8,8))
        address=struct.unpack('<Q',read(rva+24,8))[0]
        context_size,context_rva=struct.unpack('<II',read(rva+160,8))
        result['exception']={'thread_id':tid,'code':hex(code),'flags':hex(exception_flags),'address':hex(address),'context_size':context_size}
    else:tid=requesting;context_size=context_rva=None
    size,rva=streams[3];thread_count=struct.unpack('<I',read(rva,4))[0]
    if thread_count>256 or size!=4+48*thread_count:raise RuntimeError('thread list bound/layout')
    selected=None
    for i in range(thread_count):
        record=read(rva+4+48*i,48)
        if struct.unpack_from('<I',record)[0]==tid:
            start,stack_size,stack_rva=struct.unpack_from('<QII',record,24)
            selected=(start,stack_size,stack_rva)
            if context_rva is None:context_size,context_rva=struct.unpack_from('<II',record,40)
            break
    if selected is None:raise RuntimeError('requesting thread stack missing')
    context_flags=struct.unpack('<I',read(context_rva,4))[0]
    if context_size<272 or context_flags&0xffffff00 not in (0x00400000,0x80000000):raise RuntimeError('unsupported ARM64 context')
    regs={name:struct.unpack('<Q',read(context_rva+8+index*8,8))[0] for name,index in (('fp',29),('lr',30),('sp',31),('pc',32))}
    crash=json.loads((out/'first-browser-crash-state.json').read_text())
    maps_text=next(r['maps'] for r in crash['processes'] if r['pid']==2295)
    spec=importlib.util.spec_from_file_location('address_walker','/run/ideck/snapshot-ipc-stack.py');walker=importlib.util.module_from_spec(spec);spec.loader.exec_module(walker)
    maps=walker.parse_maps(maps_text)
    start,stack_size,stack_rva=selected
    def read_frame(address):
        if not start<=address or address+16>start+stack_size:raise OSError('frame outside captured stack')
        return read(stack_rva+address-start,16)
    frames,reason=walker.walk_frames(regs['fp'],regs['sp'],maps,read_frame)
    result['thread_id']=tid;result['registers']={k:walker.address_info(v,maps) for k,v in regs.items()};result['frames']=frames;result['unwind_stop']=reason
    with os.fdopen(os.dup(fd),'rb') as stream:result['dump_sha256']=hashlib.file_digest(stream,'sha256').hexdigest()
    after=os.fstat(fd)
    if (before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns):raise RuntimeError('dump changed while reading')
    (out/'dump-addresses.json').write_text(json.dumps(result,indent=2)+'\n')
    print('IDECK_DUMP_ADDRESSES='+json.dumps(result),flush=True)
finally:os.close(fd)
for p in sorted(out.glob('delta-*.txt')):
    lines=[line[:800] for line in p.read_text(errors='replace').splitlines() if 'assert' in line.lower()]
    if lines:print('IDECK_ASSERT_LOG='+p.name+'\n'+'\n'.join(lines[-15:]),flush=True)
PY