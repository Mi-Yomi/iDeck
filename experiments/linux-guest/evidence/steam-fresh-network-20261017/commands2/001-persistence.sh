#!/bin/sh
set -eu
python3 - <<'PY'
import hashlib,json,pathlib,subprocess,os
root=pathlib.Path('/home/ideck/.local/share/Steam')
prior=json.loads(pathlib.Path('/var/log/ideck-steam-install/persistence-before.json').read_text())
doc=pathlib.Path('/home/ideck/Documents/Steam-cloud-persistence.txt')
assert doc.stat().st_uid==1000
assert hashlib.file_digest(doc.open('rb'),'sha256').hexdigest()==prior['document_sha256']
assert hashlib.sha256(pathlib.Path('/etc/machine-id').read_bytes()).hexdigest()==prior['machine_id_sha256']
for name,expected in prior['client'].items():
 p=root/name
 assert p.stat().st_size==expected['size'] and hashlib.file_digest(p.open('rb'),'sha256').hexdigest()==expected['sha256']
cache=pathlib.Path('/home/ideck/.cache/ideck-steam-parts')
assert {p.name for p in cache.iterdir()}==set(prior['installer_cache'])
for name,expected in prior['installer_cache'].items():
 p=cache/name
 assert p.stat().st_uid==1000 and p.stat().st_size==expected['size'] and hashlib.file_digest(p.open('rb'),'sha256').hexdigest()==expected['sha256']
r=subprocess.run(['dpkg','--audit'],capture_output=True)
assert r.returncode==0 and r.stdout==b'' and r.stderr==b''
report={'status':'pass','scope':'independent cloud disk and installation persistence; Steam UI not reached',
 'document_sha256':prior['document_sha256'],'machine_id_sha256':prior['machine_id_sha256'],
 'verified_client_elf_files':len(prior['client']),'retained_installer_zip_files':len(prior['installer_cache']),
 'dpkg_audit':{'exit_code':r.returncode,'stdout_bytes':len(r.stdout),'stderr_bytes':len(r.stderr)},
 'steam_launched':False,'network_denial_retried':False}
print('FRESH_PERSISTENCE_AFTER='+json.dumps(report,sort_keys=True))
PY
xset q
xwininfo -root -tree
