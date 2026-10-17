from pathlib import Path
import hashlib,json
task=Path(__file__).parent
source=(task/'commands14/010-resume-existing.sh').read_text().split("<<'RESUME'\n",1)[1].split('\nRESUME',1)[0]
old="expected=json.loads((out/'freeze-identities.json').read_text())\nassert expected and json.loads((out/'summary.json').read_text())['reason']=='deadline'"
new="""deadline=time.monotonic()+90
while not (out/'resume-summary.json').exists():
    assert time.monotonic()<deadline,'prior guardian did not finish'
    time.sleep(.5)
prior=json.loads((out/'resume-summary.json').read_text())
assert prior['guard']['cause']=='resume_operator_budget'
last=json.loads((out/'resume-timeline.jsonl').read_text().splitlines()[-1])['processes']
expected=[]
for pid,row in processes().items():
    assert pid in last and row['Uid'].split()==['1000']*4
    before=last[pid]
    assert row['exe']==before['exe'] and row['stat'].rsplit(') ',1)[1].split()[19]==before['stat'].rsplit(') ',1)[1].split()[19]
    expected.append({'pid':int(pid),'exe':row['exe'],'starttime':row['stat'].rsplit(') ',1)[1].split()[19]})
assert expected
started=time.monotonic()"""
assert source.count(old)==1
source=source.replace(old,new).replace("out/'resume-summary.json').write_text","out/'resume2-summary.json').write_text").replace("out/'resume-timeline.jsonl').open","out/'resume2-timeline.jsonl').open").replace("out/'finish-resume'","out/'finish-resume2'").replace("time.monotonic()-started<300","time.monotonic()-started<150")
for line in ("    # Wake Steam's own screensaver through real X11 input, no account action.\n","    subprocess.run(['xdotool','mousemove_relative','--','35','15'],timeout=5,check=True)\n","    subprocess.run(['xdotool','key','Escape'],timeout=5,check=True)\n"):
    assert source.count(line)==1;source=source.replace(line,'')
compile(source,'resume14-second','exec')
command="set -eu\ncat > /run/ideck/resume14-second.py <<'RESUME'\n"+source+"\nRESUME\nsetsid python3 /run/ideck/resume14-second.py </dev/null >/run/ideck/resume14-second.log 2>&1 &\nprintf 'IDECK_SECOND_GUARD_PID=%s\\n' \"$!\"\n"
(task/'commands14/017-continue-guard.sh').write_text(command)
(task/'resume14-second-source.json').write_text(json.dumps({'command_sha256':hashlib.sha256(command.encode()).hexdigest(),'purpose':'same client guardian transfer after prior guard freeze, no X input or runtime configuration change','budget_seconds':150},indent=2)+'\n')
print('queued bounded guardian transfer')
