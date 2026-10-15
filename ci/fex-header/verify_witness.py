"""Read compiler data objects only. No target loading, linking or execution."""
import argparse, hashlib, json, pathlib, struct

def require(value, message):
 if not value: raise ValueError(message)

def inspect_object(data, spec):
 require(len(data)>=32,'truncated header')
 magic,cpu,subtype,kind,ncmds,sizeofcmds,flags,reserved=struct.unpack_from('<8I',data)
 require((magic,cpu,subtype,kind)==(0xfeedfacf,0x100000c,0,1),'requires little-endian arm64 MH_OBJECT, not executable or arm64e')
 require(1<=ncmds<=64 and 8*ncmds<=sizeofcmds<=65536 and sizeofcmds%8==0,'unbounded or unaligned commands')
 require(32+sizeofcmds<=len(data),'truncated commands')
 sections=[];symtab=None;version=None;pos=32;singletons=set()
 for _ in range(ncmds):
  require(pos+8<=32+sizeofcmds,'truncated command')
  cmd,size=struct.unpack_from('<II',data,pos)
  require(pos%8==0 and size>=8 and size%8==0 and pos+size<=32+sizeofcmds,'invalid command size/alignment')
  require(cmd!=0x1d,'signature forbidden')
  require(cmd not in {0xc,0xd,0x80000018,0x8000001c,0x8000001f,0x20,0x80000023},'runtime dylib/RPATH command forbidden')
  require(cmd not in {0x24,0x25,0x2f,0x30},'legacy platform command forbidden')
  # Deliberately narrow: a data-only compile object needs no runtime, entry,
  # routine, dyld, linker-option or executable-load commands.
  require(cmd in {0x19,2,0xb,0x32},'unexpected data-object load command')
  if cmd!=0x19:
   require(cmd not in singletons,'duplicate singleton command');singletons.add(cmd)
  if cmd==0x19:
   require(size>=72,'truncated segment')
   ns=struct.unpack_from('<I',data,pos+64)[0]
   require(ns<=128 and 72+80*ns==size,'invalid section count/segment size')
   for i in range(ns):
    s=pos+72+80*i
    name,segment,addr,length,offset,align,reloff,nreloc,secflags,r1,r2,r3=struct.unpack_from('<16s16sQQ8I',data,s)
    name=name.split(b'\0')[0].decode();segment=segment.split(b'\0')[0].decode()
    require((secflags&0xff) not in {9,10,0x16} and name not in {'__mod_init_func','__mod_term_func','__init_offsets'},'initializer/terminator forbidden')
    require(not length or (name!='__text' and not secflags&0x80000400),'nonempty executable text forbidden')
    sections.append({'name':name,'segment':segment,'addr':addr,'size':length,'offset':offset,'nreloc':nreloc,'index':len(sections)+1})
  elif cmd==2:
   require(symtab is None and size==24,'duplicate/invalid symtab')
   symtab=struct.unpack_from('<4I',data,pos+8)
  elif cmd==0x32:
   require(version is None and size>=24,'duplicate/invalid build version')
   platform,minimum,sdk,ntools=struct.unpack_from('<4I',data,pos+8)
   require(ntools<=16 and size==24+8*ntools,'invalid build-version tool count/size')
   require(platform==2,'requires iOS device platform')
   version={'platform':platform,'minimum':minimum,'sdk':sdk}
  elif cmd==0xb:
   require(size==80,'invalid dynamic symbol table size')
  pos+=size
 require(pos==32+sizeofcmds and symtab and version,'missing/trailing commands or required metadata')
 symoff,nsyms,stroff,strsize=symtab
 require(symoff+16*nsyms<=len(data) and stroff+strsize<=len(data),'truncated symbol/string table')
 symbols={}
 for i in range(nsyms):
  strx,typ,sect,desc,value=struct.unpack_from('<IBBHQ',data,symoff+16*i)
  require(strx<strsize,'symbol name outside table')
  tail=data[stroff+strx:stroff+strsize];require(b'\0'in tail,'unterminated symbol name')
  name=tail.split(b'\0')[0].decode()
  if name in [spec['symbol'],spec['gdt_symbol']]:
   require(name not in symbols,'duplicate witness symbol')
   require(typ==0x0f,'witness must be defined external N_SECT symbol')
   require(1<=sect<=len(sections),'invalid symbol section')
   symbols[name]=(sections[sect-1],value)
 def payload(symbol,expected_section,length):
  require(symbol in symbols,'missing '+symbol)
  s,value=symbols[symbol]
  require([s['segment'],s['name']]==expected_section,'wrong witness section')
  require(value==s['addr'] and s['size']==length,'witness must occupy exactly its dedicated section')
  require(s['nreloc']==0,'witness data has relocations')
  require(s['offset']+length<=len(data),'truncated witness data')
  return data[s['offset']:s['offset']+length]
 raw=payload(spec['symbol'],spec['section'],8*spec['field_count'])
 values=struct.unpack('<'+'Q'*spec['field_count'],raw)
 for f,value in zip(spec['fields'],values):
  if 'required_value'in f:require(value==f['required_value'],'wrong source-contract value '+f['name'])
 gdt=payload(spec['gdt_symbol'],spec['gdt_section'],8)
 require(gdt.hex()==spec['gdt_required_hex'],'wrong gdt bit-field sentinel')
 return {'object_sha256':hashlib.sha256(data).hexdigest(),'object_bytes':len(data),'build_version':version,'data_sha256':hashlib.sha256(raw).hexdigest(),'data_hex':raw.hex(),'gdt_hex':gdt.hex(),'fields':{f['name']:v for f,v in zip(spec['fields'],values)},'symbol':spec['symbol'],'data_relocations':0,'target_execution':False}

def verify_producer(producer):
 require(producer['build_version']=={'platform':2,'minimum':0x110000,'sdk':0x1a0500},'producer must use original iOS17 SDK26.5 contract')
 return producer

def compare(producer,consumer):
 verify_producer(producer)
 require(producer['data_hex']==consumer['data_hex'],'layout/config data mismatch')
 require(producer['gdt_hex']==consumer['gdt_hex'],'gdt data mismatch')
 # Historical native archives: iOS 17 / SDK 26.5. Intended app: iOS 18 / SDK 27.
 require(consumer['build_version']=={'platform':2,'minimum':0x120000,'sdk':0x1b0000},'consumer must use intended iOS18 SDK27 contract')
 return {'status':'matching-compiler-generated-layout-data','producer':producer,'consumer':consumer,'limits':'Compiler-equivalent reconstructed source witness, not historical archive debug-layout extraction; does not prove link or runtime.'}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('producer',type=pathlib.Path);p.add_argument('consumer',nargs='?',type=pathlib.Path);p.add_argument('--fields',type=pathlib.Path,default=pathlib.Path(__file__).with_name('LAYOUT_FIELDS.json'));a=p.parse_args()
 spec=json.loads(a.fields.read_text());producer=verify_producer(inspect_object(a.producer.read_bytes(),spec))
 result=compare(producer,inspect_object(a.consumer.read_bytes(),spec))if a.consumer else producer
 print(json.dumps(result,indent=2))
