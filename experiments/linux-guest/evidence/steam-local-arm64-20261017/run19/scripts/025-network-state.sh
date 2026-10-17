set -eu
python3 - <<'PY'
from pathlib import Path
import json,socket,urllib.request,re,subprocess
out=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-gamepadui-v14')
r={}
try:
    r['dns_address_count']=len(socket.getaddrinfo('store.steampowered.com',443,type=socket.SOCK_STREAM))
    with urllib.request.urlopen('https://store.steampowered.com/',timeout=10) as response:r['store_https_status']=response.status
except Exception as e:r['network_probe_error_class']=type(e).__name__
p=out/'delta-steamui_login.txt'
s=p.read_text(errors='replace') if p.exists() else ''
r['login_transitions']=re.findall(r'\[([^\]]+)\] SetLoginState: ([A-Za-z_ ]+ - [A-Za-z_ ]+)',s)[-10:]
r['system_dbus_socket_present']=Path('/run/dbus/system_bus_socket').exists()
r['network_interfaces']=sorted(p.name for p in Path('/sys/class/net').iterdir())
(out/'network-state.json').write_text(json.dumps(r,indent=2)+'\n')
print('NETWORK_STATE='+json.dumps(r))
PY
