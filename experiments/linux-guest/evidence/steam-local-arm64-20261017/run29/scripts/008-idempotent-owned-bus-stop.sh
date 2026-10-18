set -eu
python3 - <<'PY'
from pathlib import Path
import os,json,signal,select,time
out=Path('/home/ideck/steam-experiment-logs/runtime-tools-run29')
expected=json.loads((out/'residuals-inspected.json').read_text())
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==expected['boot_id']
case=json.loads((out/'namespace-container.json').read_text())
assert len(expected['processes'])==2
assert {r['exe'] for r in expected['processes']}=={'/usr/bin/dbus-launch','/usr/bin/dbus-daemon'}
assert case['rooted']['mount_namespace'] not in json.loads((out/'baseline-namespaces.json').read_text())

def current(pid):
 p=Path('/proc')/str(pid)
 status=dict(s.split(':',1) for s in p.joinpath('status').read_text().splitlines() if ':' in s)
 return {'starttime':p.joinpath('stat').read_text().rsplit(') ',1)[1].split()[19],
  'exe':os.readlink(p/'exe'),'uid':status['Uid'].split(),'tracer':int(status['TracerPid']),
  'mnt':os.readlink(p/'ns/mnt'),'cmdline':p.joinpath('cmdline').read_text().replace(chr(0),' ')}

pins=[];results=[]
try:
 for row in expected['processes']:
  assert row['source_case']=='namespace-container' and row['mnt']==case['rooted']['mount_namespace']
  assert row['uid']==['1000']*4 and row['tracer']==0
  try:fd=os.pidfd_open(row['pid'])
  except ProcessLookupError:
   results.append({'pid':row['pid'],'already_exited':True});continue
  pins.append((fd,row))
  now=current(row['pid'])
  assert all(now[k]==row[k] for k in now),'ownership changed; refuse signalling'
 # Pin and validate the complete set before sending either ordinary stop signal.
 for fd,row in pins:
  poll=select.poll();poll.register(fd,select.POLLIN)
  if poll.poll(0):
   results.append({'pid':row['pid'],'already_exited':True});continue
  try:
   now=current(row['pid']);assert all(now[k]==row[k] for k in now)
   signal.pidfd_send_signal(fd,signal.SIGTERM)
  except (FileNotFoundError,ProcessLookupError):
   assert poll.poll(1000),'missing live process identity; refuse further action'
   results.append({'pid':row['pid'],'already_exited':True});continue
  assert poll.poll(20000),'ordinary test-bus stop did not finish; no forced escalation'
  results.append({'pid':row['pid'],'exe':row['exe'],'signal':'SIGTERM','exited':True,
                  'same_boot_starttime_uid_exe_command_namespace_verified':True})
finally:
 for fd,row in pins:os.close(fd)
r={'processes':results,'signal_scope':'only the two pinned UID1000 D-Bus processes from namespace-container',
   'forced_signal_used':False,'time_ns':time.time_ns()}
(out/'residuals-stopped.json').write_text(json.dumps(r,indent=2)+'\n')
print('OWNED_TEST_BUS_STOP='+json.dumps(r))
PY
