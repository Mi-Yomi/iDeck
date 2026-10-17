import importlib.util, struct, unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('snap',HERE.parent/'tools/snapshot_steam_ipc_stack.py')
snap=importlib.util.module_from_spec(spec);spec.loader.exec_module(snap)

class Fake:
 def __init__(self,stopped=False,fail=None):
  self.initial={'tid':42,'tgid':40,'starttime':100,'uid':[1000]*4,'tracer':0,'state':'T' if stopped else 'S','exe':snap.ROOT+'steam'}
  self.attached=False;self.stopped=False;self.group=stopped;self.calls=[];self.fail=fail;self.waits=0
 def info(self,tid):
  out=dict(self.initial);out['tracer']=99 if self.attached else 0;out['state']='t' if self.stopped else ('T' if self.group else 'S');return out
 def ptrace(self,op,tid,addr=0,data=0):
  self.calls.append((op,tid,data))
  if self.fail=='seize' and op==snap.SEIZE:raise OSError(1,'secret-not-to-report')
  if self.fail=='detach' and op==snap.DETACH:raise OSError(5,'secret-not-to-report')
  if op==snap.SEIZE:self.attached=True
  if op==snap.INTERRUPT:self.stopped=True
  if op==snap.DETACH:self.attached=False;self.stopped=False
 def wait(self,tid,seconds):
  self.waits+=1
  if self.fail=='firstwait' and self.waits==1:raise snap.Refusal('ptrace_stop_timeout')
  return (snap.EVENT_STOP<<16)|(snap.signal.SIGTRAP<<8)|127
 def pin_group(self,pid):pass
 def close_group(self,pid):pass
 def stop_group(self,pid):self.calls.append(('stopgroup',pid));self.group=True

class Frames(unittest.TestCase):
 def test_browser_parent_rejects_inherited_assertion_dumper_argv(self):
  argv=[b'steamwebhelper',b'-steampid=123',b'-force-sandbox']
  self.assertTrue(snap.is_browser_argv({'ppid':123},argv,123))
  self.assertFalse(snap.is_browser_argv({'ppid':456},argv,123))
  self.assertFalse(snap.is_browser_argv({},argv,123))
  self.assertFalse(snap.is_browser_argv({'ppid':123},argv+[b'--type=renderer'],123))
 def setUp(self):
  self.maps=snap.parse_maps('1000-2000 rw-p 00000000 00:00 0 [stack]\n4000-5000 r-xp 00001000 00:00 1 /test/lib.so\n')
 def test_chain(self):
  buf={0x1100:struct.pack('<QQ',0x1200,0x4100),0x1200:struct.pack('<QQ',0,0x4200)}
  rows,why=snap.walk_frames(0x1100,0x1000,self.maps,buf.__getitem__)
  self.assertEqual(why,'end_zero');self.assertEqual(len(rows),2)
  self.assertEqual(rows[0]['return']['file_offset'],'0x1100')
 def test_alignment_bounds_and_cycle(self):
  for fp,expected in [(0x1101,'unaligned_frame'),(0x2000,'frame_outside_stack'),(0x1000,'nonincreasing_frame')]:
   _,why=snap.walk_frames(fp,0x1010,self.maps,lambda _:self.fail('must not read'))
   self.assertEqual(why,expected)
  rows,why=snap.walk_frames(0x1100,0x1000,self.maps,lambda _:struct.pack('<QQ',0x1100,0x4100))
  self.assertEqual(len(rows),1);self.assertEqual(why,'nonincreasing_frame')
 def test_cross_mapping_no_read(self):
  _,why=snap.walk_frames(0x2000,0x1000,self.maps,lambda _:self.fail('must not read'))
  self.assertEqual(why,'frame_outside_stack')
 def test_short_read_and_pac(self):
  self.assertEqual(snap.walk_frames(0x1100,0x1000,self.maps,lambda _:b'123')[1],'short_frame_read')
  self.assertEqual(snap.walk_frames(0x1100,0x1000,self.maps,lambda _:struct.pack('<QQ',0,0xabcd000000004100))[1],'return_not_executable_or_pac')
 def test_bounded(self):
  count=[0]
  def read(fp):count[0]+=1;return struct.pack('<QQ',fp+16,0x4100)
  rows,why=snap.walk_frames(0x1100,0x1000,self.maps,read)
  self.assertEqual(count[0],32);self.assertEqual(why,'frame_limit')

class Cleanup(unittest.TestCase):
 def test_running_no_stop_signals(self):
  fake=Fake();r=snap.capture_thread(fake.initial,fake,lambda _: {'frames':[]})
  self.assertEqual(r['status'],'captured');self.assertTrue(r['detached']);self.assertFalse(any(c[0]=='stopgroup' for c in fake.calls))
 def test_preserves_group_stop(self):
  fake=Fake(stopped=True);r=snap.capture_thread(fake.initial,fake,lambda _: {})
  self.assertTrue(r['group_stop_restored']);self.assertTrue(r['detached']);self.assertEqual(r['state_after'],'T')
 def test_snapshot_failure_always_detaches_no_error_text(self):
  fake=Fake()
  def fail(_):raise OSError(5,'TOP_SECRET_NOT_LOGGED')
  r=snap.capture_thread(fake.initial,fake,fail)
  self.assertTrue(r['detached']);self.assertEqual(r['status'],'failed');self.assertNotIn('TOP_SECRET',str(r))
 def test_first_wait_timeout_recovered_for_detach(self):
  fake=Fake(fail='firstwait');r=snap.capture_thread(fake.initial,fake,lambda _: {})
  self.assertTrue(r['detached']);self.assertEqual(fake.waits,2);self.assertEqual(r['status'],'failed')
 def test_seize_failure_never_detaches_other_tracer(self):
  fake=Fake(fail='seize');r=snap.capture_thread(fake.initial,fake,lambda _: {})
  self.assertFalse(r['detached']);self.assertEqual(len(fake.calls),1)
 def test_detach_failure_is_not_success(self):
  fake=Fake(stopped=True,fail='detach');r=snap.capture_thread(fake.initial,fake,lambda _: {})
  self.assertEqual(r['status'],'cleanup_failed');self.assertFalse(r['detached']);self.assertTrue(fake.group)
 def test_identity_change_prevents_attach(self):
  fake=Fake();initial=dict(fake.initial,starttime=99)
  r=snap.capture_thread(initial,fake,lambda _: {})
  self.assertEqual(r['reason'],'identity_changed');self.assertEqual(fake.calls,[])
 def test_exec_event_does_not_inject_synthetic_trap(self):
  fake=Fake();fake.wait=lambda *_:(4<<16)|(snap.signal.SIGTRAP<<8)|127
  r=snap.capture_thread(fake.initial,fake,lambda _:self.fail('unexpected stop must not capture'))
  self.assertTrue(r['detached']);self.assertEqual(r['reason'],'unexpected_signal_stop')
  self.assertEqual(fake.calls[-1],(snap.DETACH,42,0))
 def test_real_signal_delivery_preserved(self):
  fake=Fake();fake.wait=lambda *_:(snap.signal.SIGUSR1<<8)|127
  r=snap.capture_thread(fake.initial,fake,lambda _:self.fail('unexpected stop must not capture'))
  self.assertTrue(r['detached']);self.assertEqual(fake.calls[-1],(snap.DETACH,42,snap.signal.SIGUSR1))
 def test_changed_group_state_refuses_attach(self):
  fake=Fake();initial=dict(fake.initial,state='T')
  r=snap.capture_thread(initial,fake,lambda _:self.fail('must not capture'))
  self.assertEqual(r['reason'],'group_state_changed');self.assertEqual(fake.calls,[])
 def test_rejects_foreign_uid_exe_tracer(self):
  good=Fake().initial
  for change in ({'uid':[0]*4},{'exe':'/wrong'},{'tracer':123},{'tgid':90}):
   with self.assertRaises(snap.Refusal):snap.validate(dict(good,**change),40,snap.ROOT+'steam')

if __name__=='__main__':unittest.main(verbosity=2)
