set -eu
export PYTHONDONTWRITEBYTECODE=1
python3 - <<'PROFILE_SOURCE'
from pathlib import Path
import os,json,hashlib,stat
result=json.loads(Path('/home/ideck/steam-experiment-logs/resume-local-20261017-connect-5000-v7/v3-runtime-tests.json').read_text());assert result['corrected_cases_pass'] and result['old_stack_bug_reproduced'] and len(result['tests'])==6;assert all(t['exit']==0 and not t['stderr'] for t in result['tests'] if t['case']!='clone-old-v2')
assert result['source_sha256']=='dd7a19b8531294772b3b11e1742c12341d1df2bd77186fdbf042accdb9c9b4c6'
library=Path('/opt/ideck-ipc-probe-v3/libideck-ipc-connect.so');st=library.lstat();assert stat.S_ISREG(st.st_mode) and st.st_uid==0 and not st.st_mode&0o022
library_sha=hashlib.sha256(library.read_bytes()).hexdigest();assert library_sha=='14ae446d263a783d341c0236b7fe9a710f4fe7946eb43afde435063473cabb1c'
p=Path('/opt/ideck-steam/namespace-check.py');original=p.read_bytes();assert hashlib.sha256(original).hexdigest()=='96c929eafefb2f76aa7751fb1869baa6def54e5e31be2a0e6620a486bca64b0d'
launcher_source=Path('/usr/local/bin/ideck-steam').read_bytes()
assert hashlib.sha256(launcher_source).hexdigest()=='11cc1c70d2960a745b0f2c31a989eedc3ed23a1f6a95d5be7e6094cd25a7f790'
assert launcher_source.count(b'desktop) set -- "$@" -nobigpicture;;')==1
launcher_modified=__import__('base64').b64decode('IyEvYmluL3NoCiMgRXhwZXJpbWVudGFsIGhvc3QtZ3Vlc3QgbGF1bmNoZXIuIFRoaXMgZG9lcyBub3QgcHJvdmUgYW4gaVBob25lIGxhdW5jaCBvciBnYW1pbmcKIyBwZXJmb3JtYW5jZS4gVmFsdmUncyBjbGllbnQgcmVtYWlucyBhIHNlcGFyYXRlbHkgaW5zdGFsbGVkLCB1c2VyLW93bmVkIGlucHV0LgpzZXQgLWV1CnVtYXNrIDA3NwoKc3RlYW1faG9tZT0vaG9tZS9pZGVjawpydW50aW1lX2Rpcj0vcnVuL3VzZXIvMTAwMApkaXNwbGF5PTowCnN0ZWFtX3Jvb3Q9JHN0ZWFtX2hvbWUvLmxvY2FsL3NoYXJlL1N0ZWFtCmNsaWVudD0kc3RlYW1fcm9vdC9zdGVhbXJ0YXJtNjQvc3RlYW0KCmZhaWwoKSB7CiAgICBwcmludGYgJ0lERUNLX1NURUFNX0VSUk9SPSVzXG4nICIkMSIgPiYyCiAgICBleGl0ICIkezI6LTF9Igp9CgpbICIkIyIgLWVxIDEgXSB8fCBmYWlsIHVzYWdlX2Rlc2t0b3BfYmlnX3BpY3R1cmVfb3Jfc3RvcCA2NApjYXNlICIkMSIgaW4gZGVza3RvcHxiaWctcGljdHVyZXxzdG9wKSBtb2RlPSQxOzsgKikgZmFpbCB1bmtub3duX21vZGUgNjQ7OyBlc2FjClsgIiQoaWQgLXUpIiA9IDEwMDAgXSAmJiBbICIkKGlkIC11bikiID0gaWRlY2sgXSB8fCBmYWlsIHJlcXVpcmVzX2lkZWNrX3VpZDEwMDAKWyAiJHtIT01FOi19IiA9ICIkc3RlYW1faG9tZSIgXSB8fCBmYWlsIHdyb25nX2hvbWUKWyAiJHtESVNQTEFZOi19IiA9ICIkZGlzcGxheSIgXSB8fCBmYWlsIGV4aXN0aW5nX2Rlc2t0b3BfcmVxdWlyZWQKWyAiJHtYREdfUlVOVElNRV9ESVI6LX0iID0gIiRydW50aW1lX2RpciIgXSB8fCBmYWlsIHdyb25nX3J1bnRpbWVfZGlyClsgIiR7WEFVVEhPUklUWTotfSIgPSAiJHJ1bnRpbWVfZGlyL1hhdXRob3JpdHkiIF0gfHwgZmFpbCB3cm9uZ194YXV0aG9yaXR5ClsgLWQgIiRydW50aW1lX2RpciIgXSAmJiBbICEgLUwgIiRydW50aW1lX2RpciIgXSB8fCBmYWlsIGludmFsaWRfcnVudGltZV9kaXIKWyAiJChzdGF0IC1jICcldTolYScgIiRydW50aW1lX2RpciIpIiA9IDEwMDA6NzAwIF0gfHwgZmFpbCB1bnNhZmVfcnVudGltZV9kaXIKWyAtZiAiJFhBVVRIT1JJVFkiIF0gJiYgWyAtciAiJFhBVVRIT1JJVFkiIF0gJiYgWyAhIC1MICIkWEFVVEhPUklUWSIgXSB8fCBmYWlsIG1pc3NpbmdfeGF1dGhvcml0eQpbICIkKHN0YXQgLWMgJyV1JyAiJFhBVVRIT1JJVFkiKSIgPSAxMDAwIF0gfHwgZmFpbCB3cm9uZ194YXV0aG9yaXR5X293bmVyClsgLWQgIiRzdGVhbV9yb290IiBdICYmIFsgISAtTCAiJHN0ZWFtX3Jvb3QiIF0gfHwgZmFpbCBjbGllbnRfbm90X2luc3RhbGxlZApbICIkKHN0YXQgLWMgJyV1JyAiJHN0ZWFtX3Jvb3QiKSIgPSAxMDAwIF0gfHwgZmFpbCB3cm9uZ19jbGllbnRfb3duZXIKdmFsaWRhdGVfY2xpZW50KCkgewogICAgWyAtZiAiJGNsaWVudCIgXSAmJiBbIC14ICIkY2xpZW50IiBdICYmIFsgISAtTCAiJGNsaWVudCIgXSB8fCBmYWlsIGNsaWVudF9ub3RfZXhlY3V0YWJsZQogICAgWyAiJChzdGF0IC1jICcldScgIiRjbGllbnQiKSIgPSAxMDAwIF0gfHwgZmFpbCB3cm9uZ19iaW5hcnlfb3duZXIKfQp2YWxpZGF0ZV9jbGllbnQKZm9yIHRvb2wgaW4gZmxvY2sgcGdyZXAgZGJ1cy1zZW5kIGRidXMtcnVuLXNlc3Npb247IGRvCiAgICBjb21tYW5kIC12ICIkdG9vbCIgPi9kZXYvbnVsbCAyPiYxIHx8IGZhaWwgbWlzc2luZ19zZXNzaW9uX2RlcGVuZGVuY3kKZG9uZQpjbGllbnRfcnVubmluZygpIHsKICAgIHByb2JlX3N0YXR1cz0wCiAgICBwZ3JlcCAtdSAxMDAwIC14IHN0ZWFtID4vZGV2L251bGwgMj4mMSB8fCBwcm9iZV9zdGF0dXM9JD8KICAgIGNhc2UgIiRwcm9iZV9zdGF0dXMiIGluCiAgICAgICAgMCkgcmV0dXJuIDA7OwogICAgICAgIDEpIHJldHVybiAxOzsKICAgICAgICAqKSBmYWlsIHByb2Nlc3NfcHJvYmVfZmFpbGVkOzsKICAgIGVzYWMKfQoKZXhwb3J0IEhPTUU9JHN0ZWFtX2hvbWUgVVNFUj1pZGVjayBMT0dOQU1FPWlkZWNrIERJU1BMQVk9JGRpc3BsYXkKZXhwb3J0IFhBVVRIT1JJVFk9JHJ1bnRpbWVfZGlyL1hhdXRob3JpdHkgWERHX1JVTlRJTUVfRElSPSRydW50aW1lX2RpcgpleHBvcnQgR0RLX0JBQ0tFTkQ9eDExIFFUX1FQQV9QTEFURk9STT14Y2IgU0RMX1ZJREVPRFJJVkVSPXgxMSBTRExfVklERU9fWDExX0RHQU1PVVNFPTAKZXhwb3J0IFNURUFNX1JVTlRJTUU9MQpleHBvcnQgTERfTElCUkFSWV9QQVRIPSRzdGVhbV9yb290L3N0ZWFtcnRhcm02NDokc3RlYW1fcm9vdC9zdGVhbXJ0YXJtNjQvcGFub3JhbWEKY2QgIiRzdGVhbV9yb290IgoKaWYgWyAiJG1vZGUiID0gc3RvcCBdOyB0aGVuCiAgICAjIE5ldmVyIHdhaXQgZm9yIHRoZSBsYXVuY2ggbG9jazogaXRzIG93bmVyIGlzIHByZWNpc2VseSB0aGUgcnVubmluZyBjbGllbnQKICAgICMgdGhhdCBuZWVkcyB0aGUgcmVxdWVzdC4gVGhpcyBpcyBub3QgdGhlIFZNIFN0b3AvY2xlYW4tdW5tb3VudCBwcm90b2NvbC4KICAgIGlmICEgY2xpZW50X3J1bm5pbmc7IHRoZW4KICAgICAgICBwcmludGYgJ0lERUNLX1NURUFNX1NUQVRVUz1ub3RfcnVubmluZ1xuJwogICAgICAgIGV4aXQgMAogICAgZmkKICAgIHN0YXR1cz0wCiAgICAiJGNsaWVudCIgLXNodXRkb3duIHx8IHN0YXR1cz0kPwogICAgWyAiJHN0YXR1cyIgLWVxIDAgXSB8fCBmYWlsIHNodXRkb3duX3JlcXVlc3RfZmFpbGVkICIkc3RhdHVzIgogICAgcHJpbnRmICdJREVDS19TVEVBTV9TVEFUVVM9c2h1dGRvd25fcmVxdWVzdGVkX2Rlc2t0b3BfcmV0YWluZWRcbicKICAgIGV4aXQgMApmaQoKWyAhIC1MICIkcnVudGltZV9kaXIvaWRlY2stc3RlYW0ubG9jayIgXSB8fCBmYWlsIHVuc2FmZV9sb2NrX2ZpbGUKZXhlYyA5PiIkcnVudGltZV9kaXIvaWRlY2stc3RlYW0ubG9jayIKZmxvY2sgLW4gOSB8fCBmYWlsIGxhdW5jaGVyX2FscmVhZHlfcnVubmluZwojIFRoZSBuYXRpdmUgY2xpZW50IG1heSBvdXRsaXZlIGEgdGVybWluYWwvbGF1bmNoZXI7IGRvIG5vdCBkZXBlbmQgb24gaXRzIGluaGVyaXRlZAojIGRlc2NyaXB0b3JzIGZvciBzZXJpYWxpemF0aW9uIG9yIG1pc3Rha2UgYW4gdW5sb2NrZWQgd3JhcHBlciBmb3Igbm8gY2xpZW50LgppZiBjbGllbnRfcnVubmluZzsgdGhlbgogICAgZmFpbCBjbGllbnRfYWxyZWFkeV9ydW5uaW5nCmZpCgojIE1hdGNoIHRoZSBjdXJyZW50IHVwc3RyZWFtIFgxMS9ydW50aW1lIHJvdXRlOyBrZWVwIENocm9taXVtJ3Mgc2FuZGJveCBlbmFibGVkLgojIENFRiBzb2Z0d2FyZSBVSSByZW5kZXJpbmcgaXMgYSBkaWFnbm9zdGljIGNob2ljZSwgbm90IGdhbWUtcGVyZm9ybWFuY2UgZXZpZGVuY2UuCiMgVmFsdmUncyBwZXJzaXN0ZW50IC5jZWYtaW5pdGlhbGl6ZS1zZW50aW5lbCBvdGhlcndpc2Ugc2lsZW50bHkgZGlzYWJsZXMgdGhlCiMgc2FuZGJveCBhZnRlciBhbiBpbnRlcnJ1cHRlZCBpbml0aWFsaXphdGlvbi4gVGhpcyBzdXBwb3J0ZWQgbmF0aXZlIGFyZ3VtZW50CiMgb3ZlcnJpZGVzIHRoYXQgZmFsbGJhY2s7IG5ldmVyIHJlbW92ZSB1c2VyIGNhY2hlIG9yIGVuYWJsZSBhIGJ5cGFzcyBpbnN0ZWFkLgpzZXQgLS0gLWNsaWVudGJldGEgc3RlYW1kZWNrX3B1YmxpY2JldGEgLWNlZi1vem9uZS1wbGF0Zm9ybT14MTEgLWNlZi1kaXNhYmxlLWdwdSAtY2VmLWZvcmNlLXNhbmRib3gKY2FzZSAiJG1vZGUiIGluCiAgICBkZXNrdG9wKSBzZXQgLS0gIiRAIiAtbm9iaWdwaWN0dXJlOzsKICAgICMgVGhpcyBnZW5lcmljIExpbnV4IGd1ZXN0IGhhcyBubyBTdGVhbU9TIGZpcnN0LWJvb3QvdXBkYXRlIHNlcnZpY2VzLgogICAgYmlnLXBpY3R1cmUpIHNldCAtLSAiJEAiIC1nYW1lcGFkdWk7Owplc2FjCnByaW50ZiAnSURFQ0tfU1RFQU1fU1RBVFVTPWV4cGVyaW1lbnRhbF9sYXVuY2hfcmVxdWVzdGVkXG4nCnByaW50ZiAnSURFQ0tfU1RFQU1fUkVOREVSSU5HPWNlZl9zb2Z0d2FyZV91aV9vbmx5XG4nCmZvciBhdHRlbXB0IGluIDAgMSAyOyBkbwogICAgc3RhdHVzPTAKICAgIHZhbGlkYXRlX2NsaWVudAogICAgaWYgWyAtbiAiJHtEQlVTX1NFU1NJT05fQlVTX0FERFJFU1M6LX0iIF0gJiYKICAgICAgIGRidXMtc2VuZCAtLXNlc3Npb24gLS10eXBlPW1ldGhvZF9jYWxsIC0tcHJpbnQtcmVwbHkgXAogICAgICAgICAgIC0tZGVzdD1vcmcuZnJlZWRlc2t0b3AuREJ1cyAvb3JnL2ZyZWVkZXNrdG9wL0RCdXMgXAogICAgICAgICAgIG9yZy5mcmVlZGVza3RvcC5EQnVzLkxpc3ROYW1lcyA+L2Rldi9udWxsIDI+JjE7IHRoZW4KICAgICAgICAiJGNsaWVudCIgIiRAIiB8fCBzdGF0dXM9JD8KICAgIGVsc2UKICAgICAgICB1bnNldCBEQlVTX1NFU1NJT05fQlVTX0FERFJFU1MgREJVU19TRVNTSU9OX0JVU19QSUQKICAgICAgICBkYnVzLXJ1bi1zZXNzaW9uIC0tICIkY2xpZW50IiAiJEAiIHx8IHN0YXR1cz0kPwogICAgZmkKICAgICMgU3RlYW0ncyB1cGRhdGVyIHJldHVybnMgNDIgdG8gcmVxdWVzdCBhIHJlc3RhcnQ7IHJldGFpbiBvdXIgbGF1bmNoIGxvY2suCiAgICBbICIkc3RhdHVzIiAtZXEgNDIgXSB8fCBicmVhawogICAgWyAiJGF0dGVtcHQiIC1sdCAyIF0gfHwgZmFpbCB1cGRhdGVfcmVzdGFydF9saW1pdCA0MgogICAgaWYgY2xpZW50X3J1bm5pbmc7IHRoZW4gZmFpbCBjbGllbnRfc3RpbGxfcnVubmluZ19hZnRlcl91cGRhdGU7IGZpCiAgICBwcmludGYgJ0lERUNLX1NURUFNX1NUQVRVUz11cGRhdGVfcmVzdGFydF9yZXF1ZXN0ZWRcbicKZG9uZQpbICIkc3RhdHVzIiAtZXEgMCBdIHx8IGZhaWwgY2xpZW50X2V4aXRfbm9uemVybyAiJHN0YXR1cyIKcHJpbnRmICdJREVDS19TVEVBTV9TVEFUVVM9Y2xpZW50X3JldHVybmVkX3dpbmRvd19ub3RfYXNzZXJ0ZWRcbicK',validate=True)
launcher_path=Path('/usr/local/bin/ideck-steam-desktop-v8')
fd=os.open(launcher_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o755)
with os.fdopen(fd,'wb') as f:f.write(launcher_modified)
assert Path('/usr/local/bin/ideck-steam').read_bytes()==launcher_source
needle=b"'/usr/local/bin/ideck-steam', mode], env)";assert original.count(needle)==1
replacement=b"'/usr/local/bin/ideck-steam-desktop-v8', mode], env)"
modified=original.replace(needle,replacement);helper=Path('/run/ideck/namespace-native-500i.py');fd=os.open(helper,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o700)
with os.fdopen(fd,'wb') as f:f.write(modified)
assert p.read_bytes()==original
assert 'LD_PRELOAD' not in os.environ and 'IDECK_IPC_WAIT_MODE' not in os.environ
profile={'mode':'native-no-preload','original_deadline_ms':500,'effective_deadline_ms':500,'library_sha256':None,'library_source_sha256':result['source_sha256'],'original_helper_sha256':hashlib.sha256(original).hexdigest(),'private_helper_sha256':hashlib.sha256(modified).hexdigest(),'only_helper_change':'private restart-aware desktop launcher only; no diagnostic environment','private_launcher_sha256':hashlib.sha256(launcher_modified).hexdigest(),'launcher_flag_change':'-nobigpicture desktop mode; no SteamOS/device flags','original_helper_unchanged':True,'sandbox_preserved':True,'resource_profile_changed':False}
p=Path('/run/ideck/ipc-native-500i-profile.json');fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
with os.fdopen(fd,'w') as f:json.dump(profile,f,indent=2);f.write('\n')
print('IDECK_OBSERVER_PROFILE='+json.dumps(profile),flush=True)
probe=Path('/run/ideck/minidump-metadata.py');assert not probe.exists();probe.write_bytes(__import__('base64').b64decode('IiIiUmVhZCBleGNlcHRpb24gbWV0YWRhdGEgb25seTsgbmV2ZXIgZXhwb3J0IHN0YWNrLCBtZW1vcnksIGFjY291bnQgb3IgbW9kdWxlIHN0cmluZ3MuIiIiCmZyb20gcGF0aGxpYiBpbXBvcnQgUGF0aAppbXBvcnQganNvbixvcyxzdGF0LHN0cnVjdCxzeXMKCmRlZiBtZXRhZGF0YShkYXRhKToKICAgIGlmIGxlbihkYXRhKTwzMiBvciBkYXRhWzo0XSE9YidNRE1QJzpyYWlzZSBWYWx1ZUVycm9yKCdoZWFkZXInKQogICAgdmVyc2lvbixjb3VudCxkaXJlY3Rvcnk9c3RydWN0LnVucGFja19mcm9tKCc8SUlJJyxkYXRhLDQpCiAgICBpZiB2ZXJzaW9uJjB4ZmZmZiE9MHhhNzkzIG9yIGNvdW50PjI1NiBvciBkaXJlY3Rvcnk8MzIgb3IgZGlyZWN0b3J5K2NvdW50KjEyPmxlbihkYXRhKTpyYWlzZSBWYWx1ZUVycm9yKCdkaXJlY3RvcnknKQogICAgcmVzdWx0PXsndGltZXN0YW1wJzpzdHJ1Y3QudW5wYWNrX2Zyb20oJzxJJyxkYXRhLDIwKVswXSwnc3RyZWFtX2NvdW50Jzpjb3VudCwnZXhjZXB0aW9ucyc6W119CiAgICBmb3IgaSBpbiByYW5nZShjb3VudCk6CiAgICAgICAga2luZCxzaXplLG9mZnNldD1zdHJ1Y3QudW5wYWNrX2Zyb20oJzxJSUknLGRhdGEsZGlyZWN0b3J5K2kqMTIpCiAgICAgICAgaWYgb2Zmc2V0K3NpemU+bGVuKGRhdGEpOnJhaXNlIFZhbHVlRXJyb3IoJ3N0cmVhbV9ib3VuZHMnKQogICAgICAgIGlmIGtpbmQ9PTY6CiAgICAgICAgICAgIGlmIHNpemU8MTY4OnJhaXNlIFZhbHVlRXJyb3IoJ2V4Y2VwdGlvbl9zaXplJykKICAgICAgICAgICAgcmVzdWx0WydleGNlcHRpb25zJ10uYXBwZW5kKHsndGhyZWFkJzpzdHJ1Y3QudW5wYWNrX2Zyb20oJzxJJyxkYXRhLG9mZnNldClbMF0sCiAgICAgICAgICAgICAgICAnY29kZSc6aGV4KHN0cnVjdC51bnBhY2tfZnJvbSgnPEknLGRhdGEsb2Zmc2V0KzgpWzBdKSwKICAgICAgICAgICAgICAgICdmbGFncyc6aGV4KHN0cnVjdC51bnBhY2tfZnJvbSgnPEknLGRhdGEsb2Zmc2V0KzEyKVswXSksCiAgICAgICAgICAgICAgICAnYWRkcmVzcyc6aGV4KHN0cnVjdC51bnBhY2tfZnJvbSgnPFEnLGRhdGEsb2Zmc2V0KzI0KVswXSl9KQogICAgcmV0dXJuIHJlc3VsdAoKZGVmIHNlbGZjaGVjaygpOgogICAgYj1ieXRlYXJyYXkoMjEyKTtiWzo0XT1iJ01ETVAnCiAgICBzdHJ1Y3QucGFja19pbnRvKCc8SUlJJyxiLDQsMHhhNzkzLDEsMzIpCiAgICBzdHJ1Y3QucGFja19pbnRvKCc8SUlJJyxiLDMyLDYsMTY4LDQ0KQogICAgc3RydWN0LnBhY2tfaW50bygnPEknLGIsNDQsMTIzKTtzdHJ1Y3QucGFja19pbnRvKCc8SScsYiw1MiwxMSk7c3RydWN0LnBhY2tfaW50bygnPFEnLGIsNjgsMHgxMjM0KQogICAgYXNzZXJ0IG1ldGFkYXRhKGIpWydleGNlcHRpb25zJ109PVt7J3RocmVhZCc6MTIzLCdjb2RlJzonMHhiJywnZmxhZ3MnOicweDAnLCdhZGRyZXNzJzonMHgxMjM0J31dCiAgICBmb3IgaW52YWxpZCBpbiAoYicnLGJbOjEwMF0sYidOT1BFJytiWzQ6XSk6CiAgICAgICAgdHJ5Om1ldGFkYXRhKGludmFsaWQpCiAgICAgICAgZXhjZXB0IFZhbHVlRXJyb3I6cGFzcwogICAgICAgIGVsc2U6cmFpc2UgQXNzZXJ0aW9uRXJyb3IoJ21hbGZvcm1lZCBkdW1wIGFjY2VwdGVkJykKCmRlZiBpbnZlbnRvcnkoKToKICAgIHJvd3M9W10KICAgIGZvciBkaXJlY3RvcnkgaW4gKFBhdGgoJy90bXAvZHVtcHMnKSxQYXRoKCcvaG9tZS9pZGVjay8ubG9jYWwvc2hhcmUvU3RlYW0vZHVtcHMnKSk6CiAgICAgICAgaWYgbm90IGRpcmVjdG9yeS5leGlzdHMoKTpjb250aW51ZQogICAgICAgIGlmIGRpcmVjdG9yeS5pc19zeW1saW5rKCkgb3Igbm90IGRpcmVjdG9yeS5pc19kaXIoKTpyYWlzZSBWYWx1ZUVycm9yKCd1bnNhZmUgZHVtcCBkaXJlY3RvcnknKQogICAgICAgIGZpbGVzPXNvcnRlZChkaXJlY3RvcnkuZ2xvYignKi5kbXAnKSkKICAgICAgICBpZiBsZW4oZmlsZXMpPjI1NjpyYWlzZSBWYWx1ZUVycm9yKCdkdW1wIGNvdW50IGJvdW5kJykKICAgICAgICBmb3IgcCBpbiBmaWxlczoKICAgICAgICAgICAgYmVmb3JlPXAubHN0YXQoKQogICAgICAgICAgICBpZiBub3Qgc3RhdC5TX0lTUkVHKGJlZm9yZS5zdF9tb2RlKSBvciBiZWZvcmUuc3RfdWlkIT0xMDAwIG9yIGJlZm9yZS5zdF9ubGluayE9MTpjb250aW51ZQogICAgICAgICAgICByb3c9eydmaWxlJzpzdHIocCksJ3NpemUnOmJlZm9yZS5zdF9zaXplLCdtdGltZV9ucyc6YmVmb3JlLnN0X210aW1lX25zfQogICAgICAgICAgICBpZiBiZWZvcmUuc3Rfc2l6ZT4xNioxMDI0KioyOnJvd1snbm90X3JlYWQnXT0nc2l6ZV9ib3VuZCcKICAgICAgICAgICAgZWxzZToKICAgICAgICAgICAgICAgIGZkPW9zLm9wZW4ocCxvcy5PX1JET05MWXxvcy5PX05PRk9MTE9XfG9zLk9fTk9OQkxPQ0t8b3MuT19DTE9FWEVDKQogICAgICAgICAgICAgICAgd2l0aCBvcy5mZG9wZW4oZmQsJ3JiJykgYXMgZjoKICAgICAgICAgICAgICAgICAgICBvcGVuZWQ9b3MuZnN0YXQoZi5maWxlbm8oKSkKICAgICAgICAgICAgICAgICAgICBpZiAob3BlbmVkLnN0X2RldixvcGVuZWQuc3RfaW5vLG9wZW5lZC5zdF9zaXplKSE9KGJlZm9yZS5zdF9kZXYsYmVmb3JlLnN0X2lubyxiZWZvcmUuc3Rfc2l6ZSk6cmFpc2UgVmFsdWVFcnJvcignZHVtcCBjaGFuZ2VkJykKICAgICAgICAgICAgICAgICAgICBkYXRhPWYucmVhZCgxNioxMDI0KioyKzEpCiAgICAgICAgICAgICAgICB0cnk6cm93WydtZXRhZGF0YSddPW1ldGFkYXRhKGRhdGEpCiAgICAgICAgICAgICAgICBleGNlcHQgVmFsdWVFcnJvciBhcyBlOnJvd1snbm90X3BhcnNlZCddPXN0cihlKQogICAgICAgICAgICByb3dzLmFwcGVuZChyb3cpCiAgICByZXR1cm4gcm93cwoKaWYgX19uYW1lX189PSdfX21haW5fXyc6CiAgICBzZWxmY2hlY2soKQogICAgaWYgc3lzLmFyZ3ZbMTpdIT1bJy0tc2VsZmNoZWNrJ106cHJpbnQoanNvbi5kdW1wcyhpbnZlbnRvcnkoKSxpbmRlbnQ9MikpCg=='));probe.chmod(0o600)

PROFILE_SOURCE
set -eu
cat > /run/ideck/local-guarded-v19-connect.py <<'IDECKPY'
import os, time, json, subprocess, signal, hashlib, threading, select, stat
# Run18: V3 baseline from run16; only -nobigpicture becomes -gamepadui in a private launcher. Original launcher remains unchanged.
# Keep 384 MiB SHM reserve to observe the first failure without exhaustion.
from pathlib import Path

out = Path('/home/ideck/steam-experiment-logs/resume-local-20261017-desktop-4g-v19')
out.mkdir(exist_ok=False)
root = Path('/home/ideck/.local/share/Steam')
profile=json.loads(Path('/run/ideck/ipc-native-500i-profile.json').read_text());assert hashlib.sha256(Path('/run/ideck/namespace-native-500i.py').read_bytes()).hexdigest()==profile['private_helper_sha256'];(out/'launch-profile.json').write_text(json.dumps(profile,indent=2)+'\n')
logs = root/'logs'
positions = {p.name:p.stat().st_size for p in logs.glob('*.txt')}
assert hashlib.sha256(Path('/usr/local/bin/ideck-steam').read_bytes()).hexdigest() == '11cc1c70d2960a745b0f2c31a989eedc3ed23a1f6a95d5be7e6094cd25a7f790'
assert hashlib.sha256(Path('/opt/ideck-steam/namespace-check.py').read_bytes()).hexdigest() == '96c929eafefb2f76aa7751fb1869baa6def54e5e31be2a0e6620a486bca64b0d'
assert os.statvfs('/').f_bavail * os.statvfs('/').f_frsize > 3*1024**3
def display_probe(argv):
    try:
        return subprocess.run(argv,capture_output=True,text=True,timeout=5)
    except (subprocess.TimeoutExpired,OSError) as error:
        emit('display_probe_unavailable',command=argv[0],failure_class=type(error).__name__)
        return subprocess.CompletedProcess(argv,-1,stdout='',stderr='unavailable')

def read(path):
    try: return Path(path).read_text(errors='replace')
    except OSError as e: return 'UNAVAILABLE:'+str(e.errno)
def link(path):
    try: return os.readlink(path)
    except OSError: return None
def fd_links(path):
    try: return {f.name:link(f) for f in path.iterdir()}
    except OSError: return {}
def processes():
    found={}
    for p in Path('/proc').iterdir():
        if not p.name.isdigit(): continue
        comm=read(p/'comm').strip()
        if comm not in ('steam','steamwebhelper','steamerrorreport','steamsysinfo'): continue
        st=read(p/'status'); fields={}
        for line in st.splitlines():
            if ':' in line:
                k,v=line.split(':',1)
                if k in ('Name','State','PPid','Uid','Gid','VmRSS','VmSwap','Threads','NSpid','NoNewPrivs','TracerPid','Seccomp','Cpus_allowed_list'): fields[k]=v.strip()
        fields.update(exe=link(p/'exe'),cmdline=read(p/'cmdline').replace('\x00',' '),stat=read(p/'stat'),wchan=read(p/'wchan'),syscall=read(p/'syscall'),ns={n:link(p/'ns'/n) for n in ('mnt','pid','user','ipc')})
        found[p.name]=fields
    return found
def shm():
    v=os.statvfs('/dev/shm'); rows=[]; deleted={}
    for p in Path('/dev/shm').iterdir():
        try:
            s=p.stat(); rows.append({'name':p.name,'inode':s.st_ino,'uid':s.st_uid,'mode':oct(s.st_mode&0o7777),'size':s.st_size,'allocated':s.st_blocks*512})
        except OSError: pass
    for p in Path('/proc').iterdir():
        if not p.name.isdigit(): continue
        try:
            for fd in (p/'fd').iterdir():
                target=link(fd)
                if target and ('/dev/shm/' in target or target.startswith('/memfd:')):
                    s=fd.stat(); key=f'{s.st_dev}:{s.st_ino}'
                    row=deleted.setdefault(key,{'target':target,'size':s.st_size,'allocated':s.st_blocks*512,'fds':[]})
                    row['fds'].append(f'{p.name}/{fd.name}')
        except OSError: pass
    return {'size':v.f_blocks*v.f_frsize,'used':(v.f_blocks-v.f_bfree)*v.f_frsize,'free':v.f_bavail*v.f_frsize,'inodes_free':v.f_ffree,'objects':rows,'open_objects':deleted}
started=time.monotonic(); frozen=[]; reason='deadline'; last_windows=0; candidate=None
assert subprocess.check_output(['dpkg-query','-W','-f=${Version}','lsof'],text=True)=='4.99.4+dfsg-2'
def emit(kind, **data):
    row={'seconds':round(time.monotonic()-started,3),'wall_ns':time.time_ns(),'kind':kind,**data}
    with (out/'timeline.jsonl').open('a') as f: f.write(json.dumps(row)+'\n')
emit('preflight',memory=read('/proc/meminfo'),mounts=read('/proc/self/mountinfo'),shm=shm(),processes=processes())
assert not processes(), 'unexpected preexisting Steam processes'
with (out/'launcher.log').open('wb') as f:
    launcher=subprocess.Popen(['python3','/run/ideck/namespace-native-500i.py','launch','desktop'],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
emit('launch',pid=launcher.pid)
# A separate cheap watcher must run independently of expensive /proc/SHM walks.
# The prior 128 MiB sampled guard overshot; this is diagnostic instrumentation,
# not a change to Steam's memory, CPU or timeout configuration.
finish_guard=threading.Event();guard_tripped=threading.Event()
pin_lock=threading.Lock();pins={};browser_pid=None;guard_result={}
def identity(pid):
    p=Path('/proc')/str(pid)
    fields=(p/'stat').read_text().rsplit(') ',1)[1].split()
    status=dict(x.split(':',1) for x in (p/'status').read_text().splitlines() if ':' in x)
    return {'pid':int(pid),'starttime':fields[19],'exe':os.readlink(p/'exe'),
            'uid':status['Uid'].split(),'state':fields[0],'tracer':int(status['TracerPid']),'ppid':int(status['PPid'])}
def roles(ps):
    native=[];browsers=[];tracers=set()
    for pid,row in ps.items():
        if row.get('TracerPid','0').isdigit() and int(row.get('TracerPid','0'))>0:tracers.add(str(int(row['TracerPid'])))
        if row.get('Uid','').split()!=['1000']*4:continue
        parent=ps.get(str(row.get('PPid','')), {})
        if row.get('exe')==str(root/'steamrtarm64/steam') and parent.get('exe')!=str(root/'steamrtarm64/steam'):
            native.append(str(pid))
    for pid,row in ps.items():
        if row.get('Uid','').split()==['1000']*4 and row.get('exe')==str(root/'steamrtarm64/steamwebhelper') and str(row.get('PPid','')) in native and '--type=' not in row.get('cmdline',''):
            browsers.append(str(pid))
    return native,browsers,tracers

def pin_seen(ps):
    global browser_pid
    natives,browsers,tracers=roles(ps)
    if len(natives)>1:raise RuntimeError("ambiguous native process")
    for pid,row in ps.items():
        if pid in tracers:continue
        if row.get('exe') not in (str(root/'steamrtarm64/steam'),str(root/'steamrtarm64/steamwebhelper')) or row.get('Uid','').split()!=['1000']*4:continue
        with pin_lock:
            if pid in pins:continue
            fd=None
            try:
                fd=os.pidfd_open(int(pid));now=identity(pid)
                if now['uid']!=['1000']*4 or now['exe']!=row['exe'] or now['starttime']!=row['stat'].rsplit(') ',1)[1].split()[19] or now['tracer']:
                    os.close(fd);fd=None;guard_result.setdefault('refused_processes',[]).append(pid);continue
                pins[pid]={'fd':fd,'identity':now,'stopped':False};fd=None
                if pid in browsers:
                    if browser_pid is not None and browser_pid!=pid:guard_result['requested_cause']='second_browser_before_diagnosis';continue
                    browser_pid=pid
            except (FileNotFoundError,ProcessLookupError):
                if fd is not None:os.close(fd)
def freeze_pinned(cause):
    # Never freeze Steam's assertion dumper while it traces an owned parent.
    _,_,protected=roles(processes())
    with pin_lock:
        ordered=sorted(pins.items(),key=lambda item:0 if item[0]==browser_pid else 1 if item[1]['identity']['exe'].endswith('/steam') else 2)
        for pid,pin in ordered:
            if pid in protected:continue
            try:
                now=identity(pid);before=pin['identity']
                if any(now[k]!=before[k] for k in ('pid','starttime','uid')) or now['tracer']:
                    guard_result.setdefault('refused_pins',[]).append({'before':before,'current':now});continue
                if now['exe']!=before['exe']:guard_result.setdefault('owned_exec_changes',[]).append({'before':before,'current':now})
                signal.pidfd_send_signal(pin['fd'],signal.SIGSTOP);pin['stopped']=True
            except (FileNotFoundError,ProcessLookupError):continue
    # Parents are stopped first, so they cannot add another browser/allocator.
    current=processes();pin_seen(current)
    _,_,protected=roles(current)
    with pin_lock:
        for pid,pin in pins.items():
            if pin['stopped'] or pid in protected:continue
            try:
                now=identity(pid);before=pin['identity']
                if any(now[k]!=before[k] for k in ('pid','starttime','uid')) or now['tracer']:
                    guard_result.setdefault('refused_pins',[]).append({'before':before,'current':now});continue
                if now['exe']!=before['exe']:guard_result.setdefault('owned_exec_changes',[]).append({'before':before,'current':now})
                signal.pidfd_send_signal(pin['fd'],signal.SIGSTOP);pin['stopped']=True
            except (FileNotFoundError,ProcessLookupError):continue
    v=os.statvfs('/dev/shm')
    guard_result.update(cause=cause,seconds=time.monotonic()-started,browser_pid=int(browser_pid) if browser_pid else None,free_bytes_after_freeze=v.f_bavail*v.f_frsize)
def watch():
    try:
        while not finish_guard.wait(.02):
            v=os.statvfs('/dev/shm')
            cause=guard_result.get('requested_cause') or ('shared_memory_reserve' if v.f_bavail*v.f_frsize<384*1024**2 else None)
            with pin_lock:bp=pins.get(browser_pid)
            if bp:
                poll=select.poll();poll.register(bp['fd'],select.POLLIN)
                if poll.poll(0):cause='first_browser_exit'
            if cause:
                freeze_pinned(cause);guard_tripped.set();return
    except BaseException as e:
        guard_result.update(failure_class=type(e).__name__,message=str(e))
        try:freeze_pinned('guard_failure')
        finally:guard_tripped.set()
guard_thread=threading.Thread(target=watch,daemon=True);guard_thread.start()
def kernel_snapshot(label):
    try:
        result=subprocess.run(['dmesg'],capture_output=True,timeout=5)
        if result.returncode!=0 or len(result.stdout)>4*1024**2:
            raise RuntimeError('kernel_log_unavailable_or_over_bound')
        (out/('kernel-'+label+'.log')).write_bytes(result.stdout)
        return result.stdout
    except Exception as error:
        (out/('kernel-'+label+'-failure.json')).write_text(json.dumps({'error_class':type(error).__name__})+'\n')
        return None

def oom_count():
    try:
        counts=dict(line.split() for line in Path('/proc/vmstat').read_text().splitlines())
        return int(counts['oom_kill'])
    except (OSError,ValueError,KeyError):return None

def dump_snapshot(label):
    try:
        result=subprocess.run(['python3','/run/ideck/minidump-metadata.py'],capture_output=True,timeout=10)
        if result.returncode or len(result.stdout)>262144:raise RuntimeError('dump metadata probe failed')
        data=json.loads(result.stdout)
        (out/('dump-'+label+'.json')).write_text(json.dumps(data,indent=2)+'\n')
    except Exception as e:
        (out/('dump-'+label+'-failure.json')).write_text(json.dumps({'error_class':type(e).__name__})+'\n')

kernel_snapshot('before');initial_oom=oom_count();dump_snapshot('before')
previous={}; last_full=0; dbus_checked=False
observer_failure_class=None
try:
    while time.monotonic()-started < 1200:
        control=out/'finish-monitor'
        if control.is_file():
            assert not control.is_symlink() and control.stat().st_uid==0 and control.read_text().strip()=='stop'
            reason='operator_requested_stop';break
        if guard_tripped.is_set():reason=guard_result.get('cause','guard_failure');break
        ps=processes();pin_seen(ps);memory=read('/proc/meminfo');shared=shm()
        for probe in Path('/run/user/1000').glob('ideck-ipc-connect-*.jsonl'):
            st=probe.lstat()
            if not stat.S_ISREG(st.st_mode) or st.st_uid!=1000 or st.st_nlink!=1 or st.st_size>131072 or (st.st_mode&0o777)!=0o600:raise RuntimeError('unsafe probe log')
            fd=os.open(probe,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
            try:
                current=os.fstat(fd)
                if (current.st_dev,current.st_ino,current.st_uid)!=(st.st_dev,st.st_ino,st.st_uid):raise RuntimeError('probe log identity changed')
                data=os.read(fd,131073);assert len(data)<=131072
            finally:os.close(fd)
            (out/probe.name).write_bytes(data)

        if guard_tripped.is_set():reason=guard_result.get('cause','guard_failure');break
        if time.monotonic()-last_windows > 15:
            display_probe(['xdotool','mousemove','400','300'])
            w=display_probe(['xwininfo','-root','-tree'])
            emit('windows',exit_code=w.returncode,text=w.stdout,stderr=w.stderr)
            last_windows=time.monotonic()
            if any('--type=renderer' in p['cmdline'] for p in ps.values()) and any(('\"Steam\"' in line or 'Sign in to Steam' in line) for line in w.stdout.splitlines()):
                candidate=candidate or time.monotonic()
                if time.monotonic()-candidate>15:
                    candidate_file=out/'ui-candidate.json'
                    if not candidate_file.exists():candidate_file.write_text(json.dumps({'seconds':time.monotonic()-started,'requires_real_screenshot_review':True})+'\n')
        current_oom=oom_count()
        emit('sample',memory=memory,processes=ps,shm=shared,launcher_exit=launcher.poll(),oom_kill=current_oom,pressure=read('/proc/pressure/memory'),vmstat=read('/proc/vmstat'))
        if current_oom is None or initial_oom is None:
            reason='kernel_observer_unavailable';break
        if current_oom>initial_oom:
            kernel_snapshot('oom');reason='kernel_oom_kill';break
        if not dbus_checked:
            native=next((pid for pid,row in ps.items() if row.get('exe')==str(root/'steamrtarm64/steam')),None)
            if native:
                selected=[v.split(b'=',1)[1].decode() for v in (Path('/proc')/native/'environ').read_bytes().split(b'\0') if v.startswith(b'DBUS_SESSION_BUS_ADDRESS=')]
                if len(selected)==1:
                    bus=subprocess.run(['setpriv','--reuid=1000','--regid=1000','--init-groups','env','DBUS_SESSION_BUS_ADDRESS='+selected[0],'dbus-send','--session','--type=method_call','--print-reply','--dest=org.freedesktop.DBus','/org/freedesktop/DBus','org.freedesktop.DBus.ListNames'],capture_output=True,timeout=8)
                    emit('native_dbus',pid=native,exit_code=bus.returncode,reply_bytes=len(bus.stdout),stderr=bus.stderr.decode(errors='replace'))
                else:emit('native_dbus',pid=native,failure='session_address_absent_or_ambiguous')
                dbus_checked=True
        new_log=''
        for p in logs.glob('*.txt'):
            try: size=p.stat().st_size
            except OSError: continue
            start=positions.get(p.name,0)
            if size<start: start=0
            if size>start:
                with p.open('rb') as f: f.seek(start); b=f.read(262144)
                with (out/('delta-'+p.name)).open('ab') as f: f.write(b)
                text=b.decode(errors='replace'); emit('log',file=p.name,text=text)
                if p.name=='steamui_html.txt': new_log+=text
                positions[p.name]=start+len(b)
        for pid,row in ps.items():
            if pid not in previous:
                p=Path('/proc')/pid
                emit('process_birth',pid=pid,row=row,maps=read(p/'maps'),fds=fd_links(p/'fd'))
        for pid,row in previous.items():
            if pid not in ps:
                emit('process_disappeared',pid=pid,last=row,exit_status='not a direct child; unavailable without tracing')
                if row.get('Seccomp')=='2':kernel_snapshot('sandboxed-helper-exit-'+pid)
        previous=ps
        if 'Timed out waiting for webhelper init' in new_log or 'Restart webhelper process' in new_log or shared['free']<384*1024**2:
            reason='first_timeout_or_restart' if shared['free']>=384*1024**2 else 'shared_memory_reserve'
            break
        time.sleep(2)
except BaseException as error:
    observer_failure_class=type(error).__name__
    reason='observer_failure'
finish_guard.set();guard_thread.join(10)
if guard_thread.is_alive():raise RuntimeError('guard thread did not finish')
if reason!='ui_candidate_requires_screenshot_review' and not guard_tripped.is_set():freeze_pinned(reason)
frozen=[];freeze_identities=[]
for pid,pin in pins.items():
    if pin['stopped']:
        try:
            now=identity(pid)
            group_states=[read(t/'stat').rsplit(') ',1)[1].split()[0] for t in (Path('/proc')/pid/'task').iterdir()]
            if any(s!='T' for s in group_states):raise RuntimeError('group freeze incomplete')
            frozen.append(int(pid));freeze_identities.append({k:now[k] for k in ('pid','starttime','exe')})
        except (FileNotFoundError,ProcessLookupError):pass
    os.close(pin['fd'])
(out/'freeze-identities.json').write_text(json.dumps(freeze_identities,indent=2)+'\n')
(out/'fast-guard.json').write_text(json.dumps(guard_result,indent=2)+'\n')
kernel_snapshot('after');dump_snapshot('after')
emit('diagnostic_freeze',reason=reason,pids=frozen,shm=shm(),memory=read('/proc/meminfo'),oom_kill=oom_count())
(out/'summary.json').write_text(json.dumps({'reason':reason,'observer_failure_class':observer_failure_class,'seconds':time.monotonic()-started,'frozen':frozen,'launcher_pid':launcher.pid,'path':str(out)},indent=2)+'\n')
display_probe(['xdotool','mousemove','410','300'])
print((out/'summary.json').read_text(),flush=True)
for name in ('delta-steamui_html.txt','delta-cef_log.txt','launcher.log'):
    p=out/name
    if p.exists():
        print('IDECK_FIRST_LOG='+name)
        print('\n'.join(p.read_text(errors='replace').splitlines()[-55:]))

IDECKPY
setsid python3 /run/ideck/local-guarded-v19-connect.py </dev/null >/run/ideck/local-guarded-v19-connect.log 2>&1 &
printf 'IDECK_MONITOR_PID=%s\n' "$!"
