import hashlib,json,shutil,subprocess,sys
from pathlib import Path
root=Path('experiments/linux-guest'); work=Path('.work/steam-recovery-review-20261019')
sys.path[:0]=[str(root/'tests'),str(root/'tools')]
from test_terminal import swift_block
import recovery_guest,steam_recovery_guest
baseline='0f413a857c7b5273eef09c25d4746a7abe65e443'
def before(name):return subprocess.check_output(['git','show',baseline+':'+str(root/name)],text=True)
methods={
'ios/LinuxGUIRecovery.swift':['func closeUnused(', 'func regular(', 'func matches(', 'func sourceIdentity(', 'func validateOwnership(', 'func synchronize(', 'func hash(', 'func readReceipt(', 'func write(', 'func save(', 'func file(', 'func copy(', 'func markRunning(', 'func recordFailure('],
'ios/LinuxGUIProfile.swift':['func arguments(', 'func open(', 'func checked(', 'func openExisting(', 'func provision(']}
for name,items in methods.items():
    for marker in items:assert swift_block(before(name),marker)==swift_block((root/name).read_text(),marker),(name,marker)
for name in ['ios/LinuxConsoleLifecycle.swift','ios/LinuxDesktopDisk.swift','ios/LinuxSteamProfile.swift','ios/LinuxSteamCacheContract.swift','ios/LinuxRecoveryGuest.swift','tools/recovery_guest.py','guest/recovery/ideck-recovery-init','guest/recovery/fsck-clean.awk']:
    assert before(name)==(root/name).read_text(),name
old=swift_block(before('ios/LinuxGUIRecovery.swift'),'static func promotePending(')
new=swift_block((root/'ios/LinuxGUIRecovery.swift').read_text(),'static func promotePending(')
assert old==new.replace('              receipt.failure == nil, scope.resultBound(receipt),\n','')
suffix=recovery_guest.suffix(steam_recovery_guest.steam_script())
report={'schema':1,'baseline':baseline,'unchanged_production_methods':methods,
'promotion_body_only_change':'additional failure==nil and scope.resultBound(receipt) guard before opening backup/full hashing; no rename/fsync/lock changes',
'normal_disk_lifecycle_steam_cache_and_gui_guest_generator':'PASS byte-identical',
'new_steam_suffix':{'size':len(suffix),'sha256':hashlib.sha256(suffix).hexdigest()},
'host_capabilities':{name:shutil.which(name) for name in ['swift','xcrun','qemu-system-aarch64','e2fsck']},
'filesystem_free_bytes':shutil.disk_usage('.').free,
'positive_12gib_guest_replay':'NOT RUN','apple_compilation_and_executable_new_swift_regressions':'NOT RUN','phone_recovery':'NOT RUN','ci_started':False}
(work/'safety-comparison.json').write_text(json.dumps(report,indent=2)+'\n')
print('Byte comparisons and narrowly added promotion guard PASS; Steam suffix',len(suffix),hashlib.sha256(suffix).hexdigest())
