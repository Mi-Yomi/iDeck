set -eu
if pgrep -u 1000 -x steam >/dev/null || pgrep -u 1000 -x steamwebhelper >/dev/null; then exit 1; fi
python3 - <<'PY'
from pathlib import Path
import hashlib,struct,json
p=Path('/usr/local/bin/ideck-steam'); old=Path('/run/ideck/ideck-steam-before-timeout-probe').read_bytes()
assert hashlib.sha256(old).hexdigest()=='470bdf1559fb5272776dd076cf04a58a3a81b4c451bf97b9a870d8e1f9957603'
assert hashlib.sha256(p.read_bytes()).hexdigest()=='8e2dcacfcb734f053b6efe8bfb294134aaa1ab04ece3727e724b462e66ab29b4'
p.write_bytes(old)
print('IDECK_TIMEOUT_PROBE_REVERTED')
for p in sorted(Path('/tmp/dumps').glob('crash*.dmp')):
 b=p.read_bytes(); sig,ver,n,rva=struct.unpack_from('<IIII',b)
 if sig!=0x504d444d: continue
 streams={typ:(size,at) for typ,size,at in [struct.unpack_from('<III',b,rva+i*12) for i in range(n)]}
 out={'name':p.name,'sha256':hashlib.sha256(b).hexdigest(),'size':len(b)}
 if 6 in streams:
  _,at=streams[6]; tid=struct.unpack_from('<I',b,at)[0]; code,flags=struct.unpack_from('<II',b,at+8); address=struct.unpack_from('<Q',b,at+24)[0]
  out.update(thread=tid,exception_code=hex(code),flags=flags,address=hex(address))
  if 4 in streams:
   _,mat=streams[4]; count=struct.unpack_from('<I',b,mat)[0]
   for i in range(count):
    m=mat+4+i*108; base,size=struct.unpack_from('<QI',b,m); nrva=struct.unpack_from('<I',b,m+20)[0]
    if base<=address<base+size:
     length=struct.unpack_from('<I',b,nrva)[0]; name=b[nrva+4:nrva+4+length].decode('utf-16le')
     out.update(module=name,module_base=hex(base),module_offset=hex(address-base))
 print('IDECK_MINIDUMP_EXCEPTION='+json.dumps(out))
PY
