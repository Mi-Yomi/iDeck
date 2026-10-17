#!/bin/sh
set -eu
python3 - <<'PY'
import base64,gzip,hashlib,io,json,os,pathlib,socket,subprocess,tarfile,time
root=pathlib.Path('/home/ideck/.local/share/Steam')
out=pathlib.Path('/tmp/ideck-first-attempt')
print('FRESH_FIRST_ATTEMPT_RESULT='+ (out/'result.json').read_text())
for name in ('bootstrap_log.txt','webhelper.txt','cef_log.txt','steamui_html.txt','transport_steamui.txt'):
 p=root/'logs'/name
 print('FRESH_LOG='+json.dumps({'name':name,'exists':p.exists(),'size':p.stat().st_size if p.exists() else 0}))
 if p.exists():print(p.read_text(errors='replace')[-6000:])
print('FRESH_CLOCK='+subprocess.run(['date','-u'],capture_output=True,text=True).stdout)
print('FRESH_ROUTE='+subprocess.run(['ip','route'],capture_output=True,text=True).stdout)
print('FRESH_RESOLVER='+pathlib.Path('/etc/resolv.conf').read_text())
print('FRESH_PROXY_ENV_PRESENT='+json.dumps({k:k in os.environ for k in ('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy')}))
for host in ('client-update.steamstatic.com','client-update.fastly.steamstatic.com'):
 try:
  result={'hostname':host,'addresses':sorted(set(x[4][0] for x in socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)))}
 except OSError as e:result={'hostname':host,'error_class':type(e).__name__,'errno':e.errno,'reason':e.strerror}
 print('FRESH_DNS='+json.dumps(result))
files=[out/'timeline.jsonl',out/'result.json',pathlib.Path('/tmp/ideck-launch1/launcher.log'),root/'logs/bootstrap_log.txt',pathlib.Path('/var/log/ideck-steam-install/result.json')]
raw=io.BytesIO()
with tarfile.open(fileobj=raw,mode='w:gz') as t:
 for p in files:
  if p.is_file():
   assert p.stat().st_size<8*1024**2
   info=t.gettarinfo(str(p),arcname=p.name);info.uid=info.gid=0;info.uname=info.gname=''
   with p.open('rb') as f:t.addfile(info,f)
data=raw.getvalue()
print('FRESH_DIAGNOSTIC_ARCHIVE_SHA256='+hashlib.sha256(data).hexdigest())
print('FRESH_DIAGNOSTIC_ARCHIVE_BASE64='+base64.b64encode(data).decode())
PY
xset q
xwininfo -root -tree
