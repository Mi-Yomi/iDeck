from pathlib import Path
import json,re,hashlib
base=Path(__file__).resolve().parent;trace=base/'guest-evidence-post-pause/post-pause-trace__trace.log';lines=trace.read_text().splitlines();threads={};pending={}
for line in lines:
    m=re.match(r'\[pid\s+(\d+)\]',line)
    if not m:continue
    tid=int(m[1]);r=threads.setdefault(tid,{'lines':0,'literal_500ms_wait_entries':0,'etimedout_returns':0,'five_second_wait_entries':0,'large_26214416_ftruncates':0});r['lines']+=1
    r['literal_500ms_wait_entries']+=int('futex(' in line and re.search(r'tv_sec=0, tv_nsec=500000000',line) is not None)
    r['etimedout_returns']+=int('= -1 ETIMEDOUT' in line)
    r['five_second_wait_entries']+=int('futex(' in line and '{tv_sec=5, tv_nsec=0}' in line)
    r['large_26214416_ftruncates']+=int('ftruncate(' in line and ', 26214416' in line)
result={'scope':'separate post-pause instrumented interval only; not baseline startup or pure memset timing','trace_sha256':hashlib.sha256(trace.read_bytes()).hexdigest(),'receipt_status':'trace_incomplete','selected':{str(t):threads.get(t,{}) for t in (2192,2295,2296,2316)},'other_threads_etimedout_returns':sum(r['etimedout_returns'] for t,r in threads.items() if t not in (2192,2295,2296,2316)),'all_literal_500ms_wait_entries':sum(r['literal_500ms_wait_entries'] for r in threads.values()),'root_cause_proven':False}
(base/'post-pause-analysis.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))