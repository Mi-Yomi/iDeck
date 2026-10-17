set -eu
cat > /run/ideck/native-game-smoke.py <<'PY'
from pathlib import Path
import os,json,time,subprocess,hashlib,signal
out=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-gamepadui-v13')
assert json.loads((out/'game-install.json').read_text())['dpkg_audit_clean']
assert 'LD_PRELOAD' not in os.environ
binary=Path('/usr/games/xgalaga');header=binary.read_bytes()[:20]
assert header[:6]==b'\x7fELF\x02\x01' and int.from_bytes(header[18:20],'little')==183
env={'PATH':'/usr/bin:/bin','HOME':'/home/ideck','USER':'ideck','LOGNAME':'ideck','DISPLAY':':0','XAUTHORITY':'/run/user/1000/Xauthority','XDG_RUNTIME_DIR':'/run/user/1000','LANG':'C.UTF-8'}
with (out/'game-runtime.log').open('wb') as log:
    child=subprocess.Popen(['setpriv','--reuid=1000','--regid=1000','--init-groups',str(binary),'-window','-winsize','640x480','-nosound','-keyboard'],env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    proc=Path('/proc')/str(child.pid);fd=os.pidfd_open(child.pid)
    start=time.monotonic();identity=None;signals=[]
    try:
        while child.poll() is None and time.monotonic()-start<10:
            if os.readlink(proc/'exe')==str(binary):
                s=dict(line.split(':',1) for line in (proc/'status').read_text().splitlines() if ':' in line)
                assert s['Uid'].split()==['1000']*4
                identity={'pid':child.pid,'starttime':(proc/'stat').read_text().rsplit(') ',1)[1].split()[19],'exe':str(binary),'uid':1000,'binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest()}
                (out/'game-process.json').write_text(json.dumps(identity,indent=2)+'\n');break
            time.sleep(.05)
        assert identity is not None,'game did not start as UID1000'
        try:child.wait(timeout=max(1,120-(time.monotonic()-start)))
        except subprocess.TimeoutExpired:
            assert os.readlink(proc/'exe')==identity['exe'] and (proc/'stat').read_text().rsplit(') ',1)[1].split()[19]==identity['starttime']
            signal.pidfd_send_signal(fd,signal.SIGTERM);signals.append('SIGTERM')
            try:child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                signal.pidfd_send_signal(fd,signal.SIGKILL);signals.append('SIGKILL');child.wait(timeout=5)
    finally:
        if child.poll() is None:
            signal.pidfd_send_signal(fd,signal.SIGKILL);signals.append('SIGKILL');child.wait(timeout=5)
        os.close(fd)
        result={'identity':identity,'exit_code':child.returncode,'seconds':time.monotonic()-start,'signals':signals,'process_reaped':True,'clean_application_exit':child.returncode==0 and not signals,'scope':'native ARM64 X11, no Steam/Proton/iPhone acceptance'}
        (out/'game-result.json').write_text(json.dumps(result,indent=2)+'\n')
PY
python3 /run/ideck/native-game-smoke.py </dev/null >/run/ideck/native-game-smoke.log 2>&1 &
echo "IDECK_GAME_GUARDIAN_PID=$!"
