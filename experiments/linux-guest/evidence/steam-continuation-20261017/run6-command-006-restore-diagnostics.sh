set -eu
printf 'IDECK_AFTER_STOP_TIMEOUT_PROCESSES\n'
ps -eo uid,pid,ppid,stat,comm,args | grep -E 'steam|webhelper' | head -25
python3 - <<'PY'
from pathlib import Path
import hashlib,os,stat,subprocess,json,ctypes
p=Path('/usr/local/bin/ideck-steam'); b=Path('/run/ideck/ideck-steam-before-composer-probe').read_bytes()
assert hashlib.sha256(b).hexdigest()=='470bdf1559fb5272776dd076cf04a58a3a81b4c451bf97b9a870d8e1f9957603'
old=b'set -- -clientbeta steamdeck_publicbeta -cef-ozone-platform=x11 -cef-disable-gpu\n'
assert p.read_bytes()==b.replace(old,old[:-1]+b' -system-composer\n')
meta=p.stat(); temporary=p.with_name('.ideck-steam-restored-20261017')
with temporary.open('xb') as f:
 f.write(b); f.flush(); os.fchmod(f.fileno(),stat.S_IMODE(meta.st_mode)); os.fchown(f.fileno(),meta.st_uid,meta.st_gid); os.fsync(f.fileno())
os.replace(temporary,p)
print('IDECK_LAUNCHER_ATOMICALLY_RESTORED='+hashlib.sha256(p.read_bytes()).hexdigest())
lib=ctypes.CDLL('libXrandr.so.2'); print('IDECK_SYSTEM_XRR_SYMBOL_PRESENT='+str(bool(lib.XRRGetOutputInfo)))
r=subprocess.run(['dpkg','--audit'],capture_output=True,text=True)
print('IDECK_FINAL_DPKG_AUDIT='+json.dumps({'exit_code':r.returncode,'stdout_empty':not r.stdout.strip(),'stderr_empty':not r.stderr.strip()}))
assert r.returncode==0 and not r.stdout.strip() and not r.stderr.strip()
p=Path('/home/ideck/Documents/ideck-steam-continuation-20261017.txt')
assert hashlib.sha256(p.read_bytes()).hexdigest()=='da4a878f74aad07470b03d8811ed1e86bec4ac181c3fa01bc0d4a91bc67a5aa6'
print('IDECK_PERSISTENCE_FINAL=PASS')
PY
