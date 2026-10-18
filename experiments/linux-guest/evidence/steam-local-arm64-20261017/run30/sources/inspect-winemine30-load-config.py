from pathlib import Path
import hashlib,json,struct,tarfile
p=Path(__file__).parent

def inspect(data):
 assert len(data)>=64 and data[:2]==b'MZ'
 pe=struct.unpack_from('<I',data,60)[0];assert pe>=64 and pe+24<=len(data) and data[pe:pe+4]==b'PE\0\0'
 machine,sections=struct.unpack_from('<HH',data,pe+4);size=struct.unpack_from('<H',data,pe+20)[0];opt=pe+24
 assert 208<=size<=len(data)-opt and struct.unpack_from('<H',data,opt)[0]==0x20b
 sec=opt+size;assert sections<=96 and sec+40*sections<=len(data)
 def offset(rva,length):
  for i in range(sections):
   base=sec+40*i;vsize,va,rawsize,raw=struct.unpack_from('<IIII',data,base+8)
   if va<=rva and rva+length<=va+min(vsize,rawsize):
    at=raw+rva-va;assert at+length<=len(data);return at
  raise ValueError('RVA outside backed sections')
 nr=struct.unpack_from('<I',data,opt+108)[0];assert nr>=11
 rva,length=struct.unpack_from('<II',data,opt+112+10*8)
 chpe=dynamic=None
 if rva and length>=208:
  at=offset(rva,208);declared=struct.unpack_from('<I',data,at)[0];assert declared>=208
  dynamic,chpe=struct.unpack_from('<QQ',data,at+192)
 return {'machine_hex':hex(machine),'load_config_size':length,'chpe_metadata_nonzero':bool(chpe),'dynamic_relocation_table_nonzero':bool(dynamic),'is_pure_x64_proven_by_machine_field':False}

b=bytearray(1024);b[:2]=b'MZ';struct.pack_into('<I',b,60,64);b[64:68]=b'PE\0\0';struct.pack_into('<HH',b,68,0x8664,1);struct.pack_into('<H',b,84,240)
opt=88;struct.pack_into('<H',b,opt,0x20b);struct.pack_into('<I',b,opt+108,16);struct.pack_into('<II',b,opt+192,0x1000,208)
sec=opt+240;struct.pack_into('<IIII',b,sec+8,256,0x1000,256,512);struct.pack_into('<I',b,512,208);struct.pack_into('<Q',b,712,0x1234)
assert inspect(b)['chpe_metadata_nonzero'];struct.pack_into('<Q',b,712,0);assert not inspect(b)['chpe_metadata_nonzero']
for invalid in (b'',b[:700]):
 try:inspect(invalid)
 except (AssertionError,ValueError):pass
 else:raise AssertionError('truncated headers accepted')
rows=[]
with tarfile.open(p/'ge-proton11-9-arm64/GE-Proton11-9-aarch64.tar.gz','r|gz') as archive:
 for member in archive:
  if member.name not in ('GE-Proton11-9-aarch64/files/lib/wine/aarch64-windows/winemine.exe','GE-Proton11-9-aarch64/files/lib/wine/x86_64-windows/winemine.exe'):continue
  assert member.isfile() and member.size<1024**2
  data=archive.extractfile(member).read();assert len(data)==member.size
  rows.append({'path':member.name,'sha256':hashlib.sha256(data).hexdigest(),**inspect(data)})
assert len(rows)==2
result={'selfcheck':'pass','sources':['https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-image_load_config_directory64','https://lists.llvm.org/pipermail/llvm-commits/Week-of-Mon-20230529/1162539.html'],'files':rows}
(p/'winemine30-load-config.json').write_text(json.dumps(result,indent=2)+'\n',newline='\n');print(json.dumps(result,indent=2))