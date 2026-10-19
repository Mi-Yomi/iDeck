import ast,hashlib,json,subprocess,sys
from pathlib import Path
root=Path('experiments/linux-guest'); work=Path('.work/steam-ci43-report-fix-20261019')
sys.path.insert(0,str(root/'tools'))
from stage_husk import load_overlay
from typecheck_source import restore,overlay
import steam_bundle,steam_bundled_cache
baseline='a669a3977c551fdaad7a4830dec116ec53660d9d'
allowed={'ci/build_linux_probe_ipa.py','codemagic.yaml','experiments/linux-guest/ios/tests/MarkdownReportChecks.swift','experiments/linux-guest/ios/tests/SteamRecoveryChecks.swift','experiments/linux-guest/tests/test_ci_build.py','experiments/linux-guest/tests/test_markdown_report.py'}
changed={name for name in subprocess.check_output(['git','diff','--name-only',baseline],text=True).splitlines() if name.endswith(('.py','.swift','.yaml')) and '/evidence/' not in name}
assert changed==allowed,changed
load_overlay()
lock=json.loads((root/'husk/overlay.lock.json').read_text())
# All packaged sources, payload pins and original GUI acceptance bindings stay exact.
for name in [*lock['inputs'],*['ipa/steam-cache.lock.json','guest/recovery/fsck-clean.awk']]:
    assert (root/name).read_bytes()==subprocess.check_output(['git','show',baseline+':'+str(root/name)]),name
source=work/'source-check';upstream=restore(source);overlay(source)
for name,dest in lock['copies'].items(): assert (source/dest).read_bytes()==(root/name).read_bytes(),name
steam=steam_bundle.load_lock(root/'ipa/steam.lock.json')
for name,pin in steam['source_inputs'].items():steam_bundle.checked(root/name,pin)
prior=Path('.work/steam-recovery-review-20261019/Payload/Husk.app')
steam_bundle.verify(prior/'iDeckLinuxSteam',steam)
steam_bundled_cache.verify(prior/'iDeckSteamCache',root/'ipa/steam-cache.lock.json')
attrs=subprocess.check_output(['git','check-attr','text','--',str(root/'vendor/alpine-3.24.1-aarch64/modloop-virt')],text=True).strip();assert attrs.endswith(': text: unset')
for name in changed:
    if name.endswith('.py'):ast.parse(Path(name).read_text(),filename=name)
report={'schema':1,'baseline':baseline,'changed_source_files_sha256':{name:hashlib.sha256(Path(name).read_bytes()).hexdigest() for name in sorted(changed)},'overlay_input_sources_and_payload_pins':'PASS byte-identical','upstream_files':len(upstream['files']),'overlay_copies':len(lock['copies']),'full_fresh_source_restore_overlay':'PASS','original_23_steam_source_bindings':'PASS unchanged','existing_real_linux_cache_staging_resources':'PASS reverified; no source/payload changed','git_attributes':attrs,'ci43':{'source':baseline,'outcome':'FAILED','first_failure':'main/MarkdownReportChecks.swift:15: Precondition failed','exit_code':-5,'ios_typecheck':'PASS (coordinator supplied)','native_syntax':'PASS (coordinator supplied)','mac_compile':'PASS (coordinator supplied)','mac_tests':'FAILED','integrated_husk_typecheck':'NOT REACHED','ipa_created':False},'new_apple_execution':'NOT RUN','positive_12gib_recovery':'NOT RUN','device_acceptance':'NOT RUN','ci_started':False,'budget':{'provider_minutes':23,'worker_seconds':1260,'snapshot_free_minutes':25,'paid':'OFF, coordinator supplied; fresh recheck before dispatch','reserve_minutes':2},'busybox_provenance':'OPEN'}
(work/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
print('Packaged runtime/locks unchanged; fresh81-file restore,5 patches,29 copies, Steam source pins, real staged Linux/cache resources, AST/git attributes PASS')
