"""Bounded checks using the existing resolver and managed HTTPS proxy only."""
import datetime
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import time
import urllib.parse
import urllib.request

OUT = Path(__file__).resolve().parent
result = {'time_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'owner_reported_network_config_version':'71a66f3c-3170-475c-82f6-cf3dc0ded790~cecfgver_6ad378804dc88199be22c7b77b1cebb4',
          'network_config_version_independently_introspected':False,
          'network_or_policy_changed':False,'refused_updater_host_retried':False,
          'proxy_forwarding_or_override_attempted':False,'vm_started':False}
result['proxy_configuration'] = {}
for scheme,value in urllib.request.getproxies().items():
    if scheme not in ('http','https'):
        continue
    parsed = urllib.parse.urlsplit(value)
    result['proxy_configuration'][scheme] = {'scheme':parsed.scheme,'hostname':parsed.hostname,
        'port':parsed.port,'credentials_present':bool(parsed.username or parsed.password)}
result['configured_resolvers'] = [line.split()[1] for line in Path('/etc/resolv.conf').read_text().splitlines()
                                  if line.startswith('nameserver ')]
result['allowed_host_system_dns'] = {}
program = '''import socket,sys,json,time
t=time.monotonic()
try:
 r=socket.getaddrinfo(sys.argv[1],443,type=socket.SOCK_STREAM)
 print(json.dumps({'success':True,'address_count':len(r),'elapsed_seconds':round(time.monotonic()-t,3)}))
except OSError as e:
 print(json.dumps({'success':False,'error_type':type(e).__name__,'errno':e.errno,'elapsed_seconds':round(time.monotonic()-t,3)}))
'''
for name in ('client-update.fastly.steamstatic.com','api.github.com'):
    try:
        probe = subprocess.run([sys.executable,'-c',program,name],capture_output=True,text=True,timeout=12)
        assert probe.returncode == 0
        result['allowed_host_system_dns'][name] = json.loads(probe.stdout)
    except subprocess.TimeoutExpired:
        result['allowed_host_system_dns'][name] = {'success':False,'error_type':'TimeoutExpired','bound_seconds':12}

# One ordinary DNS query to the existing configured resolver, never an alternate.
if result['configured_resolvers']:
    server = result['configured_resolvers'][0]
    name = 'client-update.fastly.steamstatic.com'
    query = struct.pack('!HHHHHH',0x6944,0x100,1,0,0,0)
    query += b''.join(bytes([len(label)])+label.encode('ascii') for label in name.split('.'))+b'\0'+struct.pack('!HH',1,1)
    started = time.monotonic()
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
        sock.settimeout(2)
        sock.connect((server,53))
        try:
            sock.send(query)
            data=sock.recv(4096)
            answer={'received_bytes':len(data),'dns_rcode':data[3]&15 if len(data)>=12 else None}
        except OSError as error:
            answer={'error_type':type(error).__name__,'errno':error.errno}
    result['configured_dns_udp'] = {'query':name,'server':server,
                                    'elapsed_seconds':round(time.monotonic()-started,3),**answer}

result['native_updater_host_status'] = {
    'hostname':'client-update.steamstatic.com','requested_this_run':False,
    'prior_observation':'proxy CONNECT403, no origin status',
    'new_approval_established':False,
    'reason':'Owner lists three additions; this newly observed native updater host is absent. No denial retry.'}
(OUT/'current-network.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
