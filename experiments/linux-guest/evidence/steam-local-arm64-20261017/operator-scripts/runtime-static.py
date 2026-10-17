from pathlib import Path
import hashlib,json,os,subprocess
root=Path(__file__).resolve().parent;base=root.parent
modules=json.loads((root/'guest-evidence-v2/resume-local-20261017-guarded-v2__module-identities.json').read_text())
inputs={'libc.so.6':base/'review/cpu-probe/lib/libc.so.6','chromehtml.so':base/'review/cef-first-failure/chromehtml.so','steamwebhelper':base/'review/cef-first-failure/steamwebhelper'}
ranges={'libc.so.6':[(0xa3f80,0xa3f98),(0xebdc0,0xebdf8)],'chromehtml.so':[(0x60390,0x60450),(0x63a00,0x63ad0),(0x5b078,0x5b410)],'steamwebhelper':[(0x140730,0x1407e0),(0xdc7c0,0xdc8b0),(0xdae80,0xdaf80),(0x25a2c0,0x25a3c0),(0xd6540,0xd6620)]}
out=root/'runtime-static';out.mkdir(exist_ok=False)
records=[]
for name,path in inputs.items():
    with path.open('rb') as f:checksum=hashlib.file_digest(f,'sha256').hexdigest()
    if checksum!=modules[name]['sha256']:raise RuntimeError('static ELF differs from guest: '+name)
    argv=['gdb','-q','-nx','-batch','-iex','set auto-load off',str(path)]
    for start,end in ranges[name]:argv+=['-ex',f'disassemble /r {start:#x},{end:#x}']
    result=subprocess.run(argv,capture_output=True,text=True,env={**os.environ,'LC_ALL':'C'},timeout=30)
    if result.returncode:raise RuntimeError(result.stderr)
    target=out/(name+'.txt');target.write_text(result.stdout)
    records.append({'module':name,'sha256':checksum,'guest_dev':modules[name]['device'],'guest_inode':modules[name]['inode'],'command':argv,'output_sha256':hashlib.sha256(result.stdout.encode()).hexdigest()})
(out/'receipt.json').write_text(json.dumps(records,indent=2)+'\n')
print(json.dumps({'modules':len(records),'output':str(out)}))