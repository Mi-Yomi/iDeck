#!/usr/bin/env bash
# Fresh-cloud rebuild only. No upload/CI, host installation or existing-disk edit.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../../.."
steam_branch=codex/steam-arm64-experiment-20261017
[ "$(git branch --show-current)" = "$steam_branch" ]
[ -z "$(git status --porcelain)" ]
[ "$(git rev-parse HEAD)" = "$(git rev-parse "refs/remotes/origin/$steam_branch")" ]
mkdir -p .work
steam_work="$(mktemp -d "$PWD/.work/steam-fresh-rebuild-XXXXXXXX")"
STEAM_REBUILD_WORK="$steam_work" python3 - <<'PY'
import json,os,platform,shutil,subprocess,sys
from pathlib import Path
assert platform.system() == 'Linux' and platform.machine() in ('x86_64','amd64'), 'Linux amd64 required'
assert sys.version_info >= (3,11), 'Python 3.11+ required'
assert shutil.which('gh') and shutil.which('dpkg-deb'), 'Existing gh and dpkg-deb required; no installation performed'
assert shutil.disk_usage('.').free >= 20 * 1024**3, 'Require 20 GiB free before preparation; no sparse capacity assumption'
sys.path.insert(0,'experiments/linux-guest/tools')
import steam_bundle as bundle
root=bundle.ROOT
candidate=bundle.load_lock(root/'evidence/steam-device-review-20261018/steam.lock.candidate.json')
for name,pin in candidate['source_inputs'].items():bundle.checked(root/name,pin)
assert bundle.load_lock(root/'ipa/steam.lock.json')['status']=='blocked', 'Review changed delivery state before rebuilding'
repo=json.loads(subprocess.check_output(['gh','api','repos/Mi-Yomi/iDeck'],text=True))
assert repo['private'] is True, 'Require existing private-repository access; do not create credentials'
PY
gh api repos/Mi-Yomi/iDeck/releases/assets/650023557 \
  -H 'Accept: application/octet-stream' > "$steam_work/ideck-debian-gui-v1.tar"
STEAM_REBUILD_WORK="$steam_work" python3 - <<'PY'
import json,os,shlex,subprocess,sys
from pathlib import Path
sys.path.insert(0,'experiments/linux-guest/tools')
import debian_rootfs as base,gui_bundle,gui_host_tools
root=Path('experiments/linux-guest').absolute();work=Path(os.environ['STEAM_REBUILD_WORK'])
gui_lock=root/'ipa/gui.lock.json'
gui_bundle.restore(work/'ideck-debian-gui-v1.tar',work/'gui',gui_lock)
manifest_path=root/'evidence/steam-device-review-20261018/rebuild-host-tool-pins.json'
pins=json.loads(manifest_path.read_text())['packages']
cache=work/'cache';host=work/'host';launchers=work/'launchers'
for path in (cache,host,launchers):path.mkdir()
for pin in pins:
    path=base.fetch(base.BASE+pin['filename'],cache/Path(pin['filename']).name,pin['size'],pin['sha256'])
    subprocess.run(['dpkg-deb','-x',str(path),str(host)],check=True)
checks=[]
for name,relative,args,version in [
    ('e2fsck','usr/sbin/e2fsck',['-V'],'1.47.2'),
    ('tune2fs','usr/sbin/tune2fs',[],'1.47.2'),
    ('resize2fs','usr/sbin/resize2fs',[],'1.47.2'),
    ('unsquashfs','usr/bin/unsquashfs',['-version'],'4.6.1')]:
    executable=host/relative
    wrapper=launchers/name
    wrapper.write_text('#!/bin/sh\nexec '+shlex.join(gui_host_tools.command(host,[executable]))+' "$@"\n')
    wrapper.chmod(0o755)
    result=subprocess.run([str(wrapper),*args],capture_output=True,text=True,timeout=15)
    text=result.stdout+result.stderr
    assert version in text and 'error while loading shared libraries' not in text,(name,text)
    checks.append({'tool':name,'version':version,'binary_sha256':base.sha256(executable)})
(work/'host-inputs.json').write_text(json.dumps({'package_manifest_sha256':base.sha256(manifest_path),
    'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'checks':checks},indent=2)+'\n')
PY
python3 experiments/linux-guest/tools/prepare_steam_payload.py \
  --gui-assets "$steam_work/gui" \
  --modloop experiments/linux-guest/vendor/alpine-3.24.1-aarch64/modloop-virt \
  --unsquashfs "$steam_work/launchers/unsquashfs" \
  --e2fsck "$steam_work/launchers/e2fsck" \
  --tune2fs "$steam_work/launchers/tune2fs" \
  --resize2fs "$steam_work/launchers/resize2fs" \
  --output "$steam_work/candidate"
STEAM_REBUILD_WORK="$steam_work" python3 - <<'PY'
import gzip,hashlib,json,os,sys
from pathlib import Path
sys.path.insert(0,'experiments/linux-guest/tools');import steam_bundle as bundle
root=Path(os.environ['STEAM_REBUILD_WORK'])/'candidate'
lock=bundle.load_lock(root/'steam.lock.candidate.json')
for name,pin in lock['source_inputs'].items():bundle.checked(bundle.ROOT/name,pin)
bundle.checked(root/'ideck-steam-device-v1.tar',lock['archive'])
count=0;digest=hashlib.sha256()
with gzip.open(root/'assets/steam-rootfs-v1.raw.gz','rb') as source:
    while chunk:=source.read(1024**2):
        count+=len(chunk);assert count<=bundle.SIZE;digest.update(chunk)
assert count==bundle.SIZE and digest.hexdigest()==lock['seed_sha256']
print(json.dumps({'status':'new candidate checked; not uploaded or device tested','directory':str(root),
    'archive':lock['archive'],'raw_sha256':lock['seed_sha256'],
    'warning':'Ext4 metadata timestamps may change bytes. Never substitute the previous f4084e40 hash.'},indent=2))
PY
