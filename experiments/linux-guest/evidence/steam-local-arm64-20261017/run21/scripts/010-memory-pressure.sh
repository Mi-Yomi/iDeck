set -eu
python3 - <<'PY'
from pathlib import Path
import json,time,subprocess
out=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-desktop-v16')
keys=('pgmajfault','pgscan_kswapd','pgscan_direct','pgsteal_kswapd','pgsteal_direct','allocstall_dma','allocstall_normal','oom_kill','pswpin','pswpout')
def pressure(root):
 return {p.name:p.read_text() for p in root.iterdir()} if root.is_dir() else {'available':False}
assert pressure(Path('/proc/ideck-no-such-pressure'))=={'available':False}
def snapshot():
 vm=dict(line.split() for line in Path('/proc/vmstat').read_text().splitlines())
 return {'monotonic':time.monotonic(),'vmstat':{k:int(vm[k]) for k in keys if k in vm},'pressure':pressure(Path('/proc/pressure')),'cpu_stat':Path('/proc/stat').read_text().splitlines()[0],'loadavg':Path('/proc/loadavg').read_text(),'swaps':Path('/proc/swaps').read_text()}
a=snapshot();time.sleep(20);b=snapshot()
r={'before':a,'after':b,'elapsed_seconds':b['monotonic']-a['monotonic'],'counter_delta':{k:b['vmstat'][k]-v for k,v in a['vmstat'].items()}}
assert r['elapsed_seconds']>=20 and all(v>=0 for v in r['counter_delta'].values())
(out/'memory-pressure-window.json').write_text(json.dumps(r,indent=2)+'\n')
print('PRESSURE='+json.dumps(r))
r={'system_bus_socket_present':Path('/run/dbus/system_bus_socket').exists(),'config_present':Path('/usr/share/dbus-1/system.conf').is_file()}
p=subprocess.run(['sh','-c','command -v dbus-daemon'],capture_output=True,text=True,timeout=5)
r['dbus_daemon_path']=p.stdout.strip() if p.returncode==0 else None
print('SYSTEM_BUS_PREFLIGHT='+json.dumps(r))
PY
