import hashlib,json,sys,tarfile
from pathlib import Path
sys.path.insert(0,'experiments/linux-guest/tools')
import steam_bundled_cache as bundle
import steam_offline_cache as packer
import steam_client
root=Path('experiments/linux-guest');work=Path('.work/steam-bundled-gamepad-20261019')
archive=work/'owner-cache/owner-steam-cache.tar';lock_path=root/'ipa/steam-cache.lock.json';lock=bundle.load_lock(lock_path)
report={'schema':1,'baseline':'52aa5b55d3c3466adf59ac2edac82a4b670f767f','client_executed':False,'agreement_accepted':False,'network_policy_changed':False,'existing_managed_proxy_used':True,'official_origin_fallback_or_redirect_used':False}
report['real_archive']=bundle.verify_archive(archive,lock)
report['packer_verify']=len(packer.verify(archive))
rows=packer.pins();members=[]
with tarfile.open(archive,'r:') as tar:
 for row in rows:
  info=tar.next();assert info and info.name==row['name'] and info.isfile() and info.size==row['size'] and info.uid==0 and info.gid==0 and info.mtime==0 and info.mode==0o644 and not info.pax_headers
  digest=hashlib.sha256();count=0
  with tar.extractfile(info) as source:
   while chunk:=source.read(1024**2):count+=len(chunk);assert count<=row['size'];digest.update(chunk)
  assert count==row['size'] and digest.hexdigest()==row['sha256'];members.append({'name':info.name,'size':count,'sha256':digest.hexdigest()})
 assert tar.next() is None
report['independent_tarfile_hash_verification']={'parts':len(members),'input_bytes':sum(r['size'] for r in members),'matches_existing_locks':True}
client=steam_client.validate(json.loads((root/'ipa/steam-client.lock.json').read_bytes()))
expanded,links=steam_client.archive_inventory(client,work/'owner-cache/client')
report['official_zip_safety_inventory']={'compressed_parts':len(client['parts']),'expanded_bytes':expanded,'validated_internal_link_count':len(links),'extracted':False}
report['real_stage']=bundle.stage(archive,work/'guests/ideck-steam-cache',lock_path)
report['real_stage_repeat']=bundle.stage(archive,work/'guests/ideck-steam-cache',lock_path)
report['delivery']={'upload_endpoint':'https://uploads.github.com/repos/Mi-Yomi/iDeck/releases/417003571/assets','upload_result':'HTTP401 Bad credentials','auto_review_rejection':False,'new_credentials_created':False,'retry_or_bypass':False,'post_failure_release_get':'HTTP404','post_failure_release_tag_list_matches':0,'asset_url':'NOT AVAILABLE'}
report['apple_swift']='NOT RUN';report['physical_device']='NOT RUN';report['busybox_provenance']='OPEN'
(work/'real-cache-verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
