set -eu
printf 'IDECK_FINAL_CLIENT_DIAGNOSTICS\n'
grep -v '^IDECK_NAMESPACE_ROOT_READY=' /home/ideck/steam-experiment-logs/rooted-desktop-composer-probe.log | tail -55
tail -40 /home/ideck/.local/share/Steam/logs/steamui_html.txt
df -B1 /dev/shm
setpriv --reuid=1000 --regid=1000 --init-groups env HOME=/home/ideck DISPLAY=:0 XAUTHORITY=/run/user/1000/Xauthority XDG_RUNTIME_DIR=/run/user/1000 /usr/local/bin/ideck-steam stop
for n in $(seq 1 60); do
 if ! pgrep -u 1000 -x steam >/dev/null && ! pgrep -u 1000 -x steamwebhelper >/dev/null; then break; fi
 sleep 1
done
if pgrep -u 1000 -x steam >/dev/null || pgrep -u 1000 -x steamwebhelper >/dev/null; then echo IDECK_CLIENT_STOP_TIMEOUT; exit 1; fi
echo IDECK_CLIENT_STOPPED_WITHOUT_FORCE
python3 - <<'PY'
from pathlib import Path
import hashlib,ctypes,json,subprocess
p=Path('/usr/local/bin/ideck-steam'); b=Path('/run/ideck/ideck-steam-before-composer-probe').read_bytes()
assert hashlib.sha256(b).hexdigest()=='470bdf1559fb5272776dd076cf04a58a3a81b4c451bf97b9a870d8e1f9957603'
p.write_bytes(b)
print('IDECK_LAUNCHER_RESTORED='+hashlib.sha256(p.read_bytes()).hexdigest())
lib=ctypes.CDLL('libXrandr.so.2'); print('IDECK_SYSTEM_XRR_SYMBOL_PRESENT='+str(bool(lib.XRRGetOutputInfo)))
r=subprocess.run(['dpkg','--audit'],capture_output=True,text=True)
print('IDECK_FINAL_DPKG_AUDIT='+json.dumps({'exit_code':r.returncode,'stdout_empty':not r.stdout.strip(),'stderr_empty':not r.stderr.strip()}))
assert r.returncode==0 and not r.stdout.strip() and not r.stderr.strip()
p=Path('/home/ideck/Documents/ideck-steam-continuation-20261017.txt')
assert hashlib.sha256(p.read_bytes()).hexdigest()=='da4a878f74aad07470b03d8811ed1e86bec4ac181c3fa01bc0d4a91bc67a5aa6'
print('IDECK_PERSISTENCE_FINAL=PASS')
PY
