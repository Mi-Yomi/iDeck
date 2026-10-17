# HANDOFF — продолжение iDeck, 2026-10-15

## Private cloud Steam continuation: input transfer blocker — 2026-10-17

Started from the verified remote Steam branch at
`b493a4909f81a5df0c226d9562a049e59e191039`, with no foreign changes. All work
is confined to this private cloud. No laptop/Windows/WSL, subagent, CI, token,
Release mutation, main/GUI branch change or security change was used.
Evidence: [cloud continuation](experiments/linux-guest/evidence/steam-cloud-20261017/README.md).

The exact official Steam installer cannot obtain its first pinned ZIP:
`URLError: <urlopen error Tunnel connection failed: 403 Forbidden>` from the
official Fastly Steam CDN. The private client cache remains empty. No alternate
host/proxy or policy bypass was attempted. This prevents a Steam runtime test;
it does not diagnose or resolve the historical first webhelper-init timeout.

Existing shell Release access also returns `Forbidden`. The authorized GitHub
connector separately confirms asset 650023557 is uploaded with 292065280 bytes
and the expected `112bdba6…dedd` digest, but that tool supports metadata/text
only and rejects binary downloads. No evidence of invalid GitHub credentials
was obtained. Library search found no suitable seed/client. The owner's local
installed disk remains unavailable and was never accessed.

The reproducible path made concrete progress using existing pinned builders:
the signed Debian indexes and 432 unique GUI inputs were downloaded and verified;
a new disposable GUI provisioning image was prepared. The original production
GUI kernel/initramfs and the current Steam bootstrap reproduced exactly.
Steam bootstrap: 11665437 bytes, SHA-256
`6a0081d76fedbb38b72e705334513313093b46e701907ed8b6d516640978df7f`.
The original Stop and namespace helper are unchanged. All 45 additional Steam
packages / 18238048 bytes were authenticated and cached, **not installed in a
Steam guest**. The existing 129 offline Steam tests passed in this cloud.

The standard GUI provisioning subsequently completed in 623.065 seconds,
verified its 341-package manifest, cleanly unmounted and exited QEMU with 0.
After that sole writer exited, host fsync passed and a separate read-only fsck
passed the strict Steam full-output policy (all five passes, no extra output).
The scratch image's SHA-256 stayed
`425893ed8c04270e293f7b5ed8b4db5cf94d3c98db17f66f0666de515f821f22`.
Sampled QEMU peak RSS was 1407672320 bytes with 1024 MiB guest RAM/four vCPUs,
using the unchanged GUI host-only provisioning profile. Steam RAM/SHM were not
measured. No task QEMU remains and no host disk mount was created. This is not
GUI seed acceptance or boot acceptance of the exact current Steam archive.
The 45-package Steam guest install and byte-empty successful Steam dpkg audit
are still NOT RUN; no Steam disk was created from an unaccepted seed.

Working inputs remain private under `/workspace/steam-cloud-20261017`.
The new GUI scratch image is not the accepted seed and must not bypass
`ipa/gui.lock.json`. No client/disk is committed or published. Steam main UI,
Big Picture, their input/restart/screenshots, Steam RAM/SHM, ARM64 stack capture,
IPC tracing, Apple/iPhone and GPU acceleration remain **NOT RUN** here.
Continue only after a supported permitted transfer of the locked official
client inputs and a verified cloud seed contract; keep all runtime/security,
disk ownership and Stop/lifetime gates.

## Steam IPC continuation paused for cloud handoff — 2026-10-17

The owner requested an immediate end to local experiments so the laptop can be
taken away. **Continue online only; do not connect to this laptop.** Work started
clean at `5176baecd08455cae90403e2a7a32bb4e5d8fcdc`, matching the remote Steam
branch. The records below supersede earlier continuation recommendations.

Current result: updater complete; **main Steam UI, Big Picture and their input
NOT REACHED**. The first Chrome-init timeout's root cause remains unresolved.
See [current diagnosis](experiments/linux-guest/STEAM-IPC-HANDOFF.md) and
`experiments/linux-guest/evidence/steam-ipc-20261017` for committed runtime logs,
timelines, bounded traces, fsck output and test receipts available to cloud work.

Changes saved:

- The launcher now uses Valve's supported `-cef-force-sandbox`. An interrupted
  initialization leaves a sentinel which otherwise makes Valve silently add
  `--no-sandbox`. That fallback was actually observed and stopped. The subsequent
  attempt logged `Force enabling sandbox`; a child had NoNewPrivs=1/Seccomp=2.
  No sentinel/cache removal or sandbox bypass is used. Namespace helper unchanged.
- Pin the real missing `lsof` program and its three-library/data closure: **45
  additional packages**, 18,238,048 download bytes, preserving all previous pins.
  The exact client invokes lsof for TCP peer ownership admission. Guest install
  of the new packages and any effect on the timeout are **NOT RUN**.
- Add explicit, manifest-bound orphan SHM recovery with full fd/map checks and
  launcher ownership. It is never automatic. Actual run7 removed 38 proven
  unreferenced objects only after the relevant processes died; tmpfs use fell to
  zero. The underlying repeated stream allocation is **not fixed** by recovery.
- Add bounded read-only IPC syscall tracing and an AArch64 stack/register sampler
  which does not collect argument/message buffers. The latter has offline tests
  and host attach/detach checks, but actual ARM64 Steam sampling is **NOT RUN**.
- Read-only fsck now requires all five passes, the target summary, version and
  no additional warnings/questions; exit0 alone is insufficient. Runner receipts
  and saved source use the same immutable startup snapshot.

Stop and persistence:

- Run7 reused the installed client, preserved the document/machine-id, and had
  empty successful dpkg audit. Individual Steam shutdown needed forced termination
  after its bounded wait: **not clean application shutdown**. The independent VM
  Stop subsequently achieved guest unmount, QEMU exit0 and host fsync.
- Before run8, a full offline read-only ext4 check of the copied run7 disk passed
  the stricter policy. Raw12GiB SHA-256:
  `49d3a42cf993bbd84b7552f72143044df6b1e9dfd6e7d2107ee1f2a3dbb573e4`.
- Run8 was interrupted deliberately at the owner's request, during early boot,
  before GUI readiness or any queued command. Its result says `failed` /
  `KeyboardInterrupt`, **clean_shutdown=true**, QEMU exit0, clean unmount. This is
  cancellation, not a successful Steam test. No post-run8 fsck is claimed.
- No task QEMU remains; run5–run8 exclusive owners are free. The owned read-only
  input mount and test mounts were detached, and its keepalive process stopped.
  Existing disks and client installation remain on E, unchanged by handoff.

Latest local-only inputs (unavailable to cloud):

- `E:\Freddy Fazbear\iDeck.work\steam-arm64-experiment-20261017\run7` is the
  last diagnostic run; `run8` is its preserved, cleanly stopped copy. Keep all
  earlier disks. Re-establish the read-only backing path before a future local
  continuation; never overwrite/reuse an existing output or resume its command
  queue blindly. `commands-ipc8/STOP` is intentionally present.
- New bootstrap: `bootstrap-ipc-20261017/initramfs-steam.gz`, **11665437 bytes**,
  SHA-256 `6a0081d76fedbb38b72e705334513313093b46e701907ed8b6d516640978df7f`.
  Its build receipt is committed; run8 only began booting it. Full guest boot,
  new dependency install and Steam startup with this exact archive remain untested.
- Host CPU max, 4vCPU,1536MiB, QEMU10.0.13/TCG; unchanged production kernel,
  software display and explicit IPv4 NAT/no forwarding. SHM769449984 bytes was
  deliberately not enlarged. Production iOS CPU/RAM/network settings unchanged.

Validation: **129 PASS** (`test_steam*.py`) on a task-owned 1GiB ext4 fixture,
subsequently unmounted. Earlier DrvFS attempts hit unsupported
renameat2(RENAME_NOREPLACE); an initial64MiB fixture failed the real256MiB reserve
checks. The filesystem/fixture was corrected, not the safety contract. See saved
test log. Swift/Apple runtime, Steam on iPhone, GPU acceleration: **NOT RUN**.

Cloud continuation must inspect its own actual files. Git contains neither the
Windows-installed Steam disk nor GUI seed bytes. Use a verified existing cloud
seed/cache or authorized private GUI asset; otherwise rebuild through the pinned
scripts and revalidate. A new independent Steam disk is legitimate when the
local disk is inaccessible, but must not be described as continuity of that disk.
No main/GUI branch, GUI payload/Release, Codemagic or Windows security changes.


## Steam continuation: namespace fix and completed update — 2026-10-17

Work started clean at `661fbf19b5074b00ca64b48dac11e8e3654e348c` on
`codex/steam-arm64-experiment-20261017`, matching the remote. This is still an
isolated experiment: **do not merge** into the parallel GUI-recovery branch.
No GUI payload/Release, main, Codemagic, Windows/WSL security setting or existing
user disk was modified. All new work remains under the same E: task directory.

Implemented:

- A guarded private-root Steam launcher in `guest/steam/namespace-check.py`.
  Actual minimal tests reproduce EPERM inside the original chroot and successful
  user/mount namespace creation outside it and after the private root transition.
  An ordinary UID1000 exec additionally passes user/mount/PID/private-proc tests.
  No sysctl, LSM or sandbox bypass is used. Original PID1/Stop mounts remain intact.
- Safe explicit `steam_vm.py --continue-from PREVIOUS_RUN`: copy only an owned,
  clean private experiment into a **new** output, refuse dirty/busy/symlink inputs,
  verify seed/source identities, retain the original, and run read-only offline
  ext4 `e2fsck -f -n` before boot. New experiment capacity is 12GiB. Output creation
  is exclusive and fd-bound; remaining free space is checked again before raw
  fsck conversion. Preparation failures get a result receipt and cleanup.
- Permanent failed classification after host fsync/dirty-marker failure; later
  finalization cannot promote it to clean. Embedded iOS owner-thread/block-backend
  lifetime code remains unchanged and still requires Apple runtime regression.
- Exact Cortex-A72 SIGILL diagnosis: the original native Valve client executes
  `LDADDAL x1,x0,[x0]` (`f8e10000`, ELF offset `0xe2548`), requiring FEAT_LSE.
  A72 fails the actual instruction; A76/max pass the original small atomic probe.
  Pinned iOS QEMU10.0.12-utm source contains the model/TCG path, but the built Apple
  runtime remains **NOT RUN**. Production CPU profiles remain Cortex-A72.

Runtime progress and current limitation:

- Run5 copied and preserved run4, passed offline ext4 fsck, and genuinely booted
  the previous final bootstrap. Valve completed the retained update at 10:51:10
  UTC; the updater is now **complete**. No full installer was rerun.
- Corrected-root native Steam and CEF ran as UID1000. A renderer was observed with
  `NoNewPrivs=1`, `Seccomp=2` and nested user/PID namespaces. **The main UI and Big
  Picture have not been verified.** The log says `Timed out waiting for webhelper
  init` and records repeated restarts; this is a later failure than chroot EPERM.
- A bounded supported `-cef-disable-hang-timeouts` probe did not fix it and was
  reverted byte-for-byte. Repeated attempts filled `/dev/shm` (769449984 bytes,
  zero free); the later SIGBUS dump points into `u1000-Shm_*`. This is a confirmed
  secondary failure, not the proven initial timeout cause. No sandbox was disabled.
- UID1000 `ideck-steam stop` shut down the first client and all helpers without
  force, leaving Desktop running. Subsequent VM Stop recorded clean unmount,
  QEMU exit0 and successful host fsync. Run5 is retained clean; run4 is untouched.
- Run6 copied run5 and passed another offline ext4 check. It **booted the exact
  final namespace bootstrap**, verified helper bytes, and preserved machine-id,
  the fsynced user document and client binary. Steam found version1792192922 with
  no pending update, skipped download and completed checksum verification.
  This proves retained installation, not a successful main-interface restart.
- The supported `-system-composer` diagnostic and measured guest webhelper
  affinity correction (Valve's `taskset 0x7c` left only CPUs2–3; probe allowed0–3)
  did not produce a visible UI. No unsuccessful diagnostic became a default.
  Main interface, login, Big Picture and their input tests are **NOT REACHED**.
  The primary remaining blocker is Steam/CEF initialization/IPC; its unique
  root cause is **not established**. Do not infer a GPU requirement from warnings.
- Run6's individual Steam shutdown timed out: active Steam and a zombie helper
  remained. **Do not call that application shutdown clean.** The original launcher
  was atomically restored, and dpkg audit passed with empty output. The independent
  VM Stop subsequently achieved guest unmount, QEMU exit0 and host fsync without
  forced QEMU termination. The runner's clean flag describes that filesystem/
  backend stop only. Final post-stop read-only ext4 fsck returned **0** with the
  exclusive owner held and no writer; no repair. Checked12GiB raw SHA-256:
  `6b8a1beeb22de348ba040fbaa13c8616e91895c1e379dff2789521b4b1e83409`.
  Together with both pre-boot checks, this is **three actual offline fsck passes**.

Local continuation inputs (private; do not distribute the installed Valve client):

- Latest disk: `E:\Freddy Fazbear\iDeck.work\steam-arm64-experiment-20261017\run6\steam-experiment.qcow2`.
  Preserve run4 and run5 as earlier snapshots. All depend on the accepted seed
  through the read-only `prior-build` mount; use the existing local
  `mount-inputs.sh` to re-establish that same path, then **copy** using a new output
  and `--continue-from run6`. Do not write the seed or reuse a running/dirty disk.
- Bootstrap: `...\bootstrap-namespace\initramfs-steam.gz`, **11650349 bytes**,
  SHA-256 `573ed99583fa2b40a51f7ad0e3c825d28a0b226a06ada517243d0468b686b170`.
  `bootstrap.json` / `verification.json` are build receipts; run6 is its boot proof.
  The local `continue-steam-namespace.sh` was the run6 invocation; it uses a finished
  output directory and must not be blindly rerun.
- Host settings remain CPU **max**, 4vCPU,1536MiB, TCG, QEMU10.0.13,
  virtio-gpu software display, explicit IPv4 user NAT/no forwarding. New virtual
  disk capacity12GiB; guest free space at reboot was8202125312 bytes. For another
  copied run allow at least about25GiB additional host headroom: the continuation
  plus a full12GiB raw fsck copy and4GiB reserve. These are not iPhone budgets.
- Do not repeat helper-restart loops into tmpfs exhaustion. Preserve diagnostics,
  request Stop and verify offline; never remove arbitrary live shared-memory
  objects, disable sandbox, or infer that watchdog flags cure the IPC timeout.

Focused regression result: **29 PASS in WSL** (namespace11, bootstrap5, runner13),
`review/final-steam-tests.log`. CPU evidence includes real original-client A72
SIGILL and A76 reaching updater startup in a deliberately empty offline HOME;
that A76 probe is not a full UI acceptance. A tiny real qemu-img fd-output smoke
also passed. Swift/Apple toolchain, Steam on iPhone and GPU acceleration: **NOT RUN**.

Current runtime records: `experiments/linux-guest/evidence/steam-continuation-20261017`.
See [namespace diagnosis](experiments/linux-guest/STEAM-NAMESPACES.md),
[CPU diagnosis](experiments/linux-guest/STEAM-CPU.md),
[CEF diagnostic limits](experiments/linux-guest/STEAM-WEBHELPER.md), and the exact
[future iOS file/dependency checklist](experiments/linux-guest/STEAM-IOS-INTEGRATION.md).
Do not distribute private Valve client bytes in an IPA/payload/Release.

The older section below describes the previous turn and is retained as history;
its updater-incomplete, disk-space and chroot blockers are superseded above.

## Isolated Steam ARM64 experiment — 2026-10-17

Branch `codex/steam-arm64-experiment-20261017`, based exactly on
`27e9736f35ffb7c572e2fa81c75458ee1d1b8ff9`; **not merged**. The GUI branch,
accepted payload/Release, Codemagic configuration and existing user disks were
not changed. Local worktree:
`E:\Freddy Fazbear\iDeck.work\steam-arm64-experiment-20261017\source`.

Implemented an original pinned Valve ARM64 installer, authenticated additional
Debian dependency closure, ordinary UID1000 X11/D-Bus launcher, separate explicitly
networked host profile and new qcow2 disk runner. See
[STEAM-EXPERIMENT.md](experiments/linux-guest/STEAM-EXPERIMENT.md).
No Valve binaries are in Git, an app payload or a Release; no account, agreement,
game installation, sandbox-disable flag or system/security configuration change.
The app Steam route remains disabled until actual client validation.

**Actual runtime result:** the official native ARM64 executable starts with QEMU
`-cpu max` and shows its real **Steam updater window** on the Debian Desktop.
The main Steam/CEF UI, login and Big Picture are **NOT verified**. Screenshot and
runtime records: [evidence](experiments/linux-guest/evidence/steam-arm64-20261017).
Host QEMU10.0.13 and production Alpine6.18.35 were used; iOS QEMU10.0.12-utm,
Swift/Apple build, IPA and Steam on iPhone are **NOT RUN**. No gaming/GPU claim.

Two private disks were actually provisioned: all17 locked client ZIPs verified,
41 additional packages configured, `dpkg --audit` exit0 and empty output, all341
original GUI package versions preserved. Install times149.822s and143.613s.
The first Cortex-A72 launch exited132 (SIGILL), with its ELF loader dependencies
resolved. The fresh CPUmax run eliminated that early failure and displayed the
updater. It then downloaded an additional669522KB as reported by Valve and began
extracting its own update; this automatic update is separate from our pinned
initial17-archive install. It was intentionally interrupted by VM Stop as E:
approached exhaustion (about260MB free after stopping), **not** declared complete.
The17 verified guest installer cache files were removed after successful install;
the host source cache remains. This cleanup is now part of the installer and has
three additional regressions. The final rebuilt bootstrap includes that change;
it is built/verified but **not booted**. Runtime evidence binds the earlier exact
bootstrap and the explicit equivalent cache-cleanup command.

The final run proves read-only seed ownership via QMP, independent control-channel
Stop, guest sync/unmount acknowledgement, QEMU process exit0 and host fsync. Its
dirty marker was cleared only after these conditions. The earlier runner expected
CRLF on the LF control channel and conservatively reported not-clean despite its
guest acknowledgement/exit0; that failed classification is retained, not rewritten.
The old private test overlay was discarded to reclaim space, never reused. The
correct LF/CRLF exact-line predicate now has regression coverage. Embedded iOS
LinuxTerminalSession/owner-thread/disk-lock lifetime code remains untouched.

Next blockers and concrete continuation:

1. Provide more free E: space before continuing the updater (several GiB of
   headroom, plus a larger private virtual disk if needed). The retained private
   test disk is `...\steam-arm64-experiment-20261017\run4\steam-experiment.qcow2`;
   it has a clean **filesystem** stop but an unfinished Steam update. It depends on
   the accepted GUI seed through the read-only `prior-build` mount. Recreate that
   mount using the local `mount-inputs.sh` before any explicit reviewed continuation.
   The runner intentionally refuses existing output directories; it does not
   auto-resume, repair, delete or recreate this disk.
2. `unshare --user --map-root-user --mount true` as UID1000 returns EPERM in the
   current chroot route. Linux documents this restriction for chroot callers
   ([unshare(2)](https://man7.org/linux/man-pages/man2/unshare.2.html)). Two private
   mount-namespace probes did not solve it (same-root pivot EBUSY, distinct-root
   pivot followed by user namespace EPERM). They changed no global mounts or
   sysctls. Implement/test a proper separate Steam root/mount namespace bootstrap
   with the existing Stop invariants before relying on Chromium's namespace
   sandbox. This is a demonstrated namespace limitation, not yet a proven CEF
   crash: the updater had not reached CEF. Do not bypass the sandbox.
3. After the update and root-namespace work, validate the normal client window,
   then `ideck-steam big-picture`; keep agreement/login decisions with the owner.

Touched-code checks: **63 PASS** across Windows installer/cache fixtures and WSL
launcher/bootstrap/host guards. The earlier unsupported DrvFS atomic-publication
errors remain documented; actual installation inside guest ext4 succeeded twice.
No Codemagic dispatch or merge was performed.

## Local Windows/WSL GUI rebuild — 2026-10-17

Rebuilt from the authenticated package closure on E:, starting at `d88aaefea758479f1da4fb81f15a02bc904898b5`.
The former cloud seed was unavailable and was **not** reused or claimed identical.
The new payload is `292065280` bytes, SHA-256 `112bdba6e12ae182fb347e52e7368e26f748bb3dc2bcd77dbd3122fb14dcdedd`;
local archive: `E:\Freddy Fazbear\iDeck.work\gui-local-20261017\payload-final\ideck-debian-gui-v1.tar`.
Current lock: [gui.lock.json](experiments/linux-guest/ipa/gui.lock.json).
New proof: [receipt.json](experiments/linux-guest/evidence/gui-local-20261017/receipt.json).

Two real Alpine 6.18.35 production boots PASS: keyboard/Mousepad save, reopen before
any write on boot2, pointer move/resize, wheel, root menu/xterm, stable machine-id,
independent control Stop, clean unmount, QEMU exit0 and read-only fsck after each.
All 423 inventoried dynamic executables also pass the actual guest glibc loader in both runs.
Host QEMU is pinned Debian10.0.13; iOS QEMU remains10.0.12-utm.
Offline replay produces the identical new tar; seal/replay/restore/full-Husk-stage
verify all five GUI assets. Native recipe patch check PASS.

Regressions: 295 total / 292 PASS / 3 Swift-only SKIP / 0 failures/errors.
Existing native C compiler, user-mode QEMU and pinned-source RCU regression ran.
Swift runtime regressions, Apple/UIKit/native link/IPA and iPhone GUI are **NOT RUN**.
No CI dispatch, Steam or guest GPU-acceleration claim.

Local portability fixes: extracted amd64 tools now use their matching pinned ELF
loader/libc; kmod paths preserve the space in `Freddy Fazbear` and trim its trailing
separator; seeder accepts a new snapshot only when its digest matches boot2 plus
current provisioning/source/input/two-boot evidence. No guest or iOS runtime file
changed. Separate GUI disk, dirty/ownership safeguards, one VM and retained QEMU
owner thread/disk lock remain unchanged. No existing user disk was opened.

The first provisioning attempt hit600s and was forcibly stopped: FAILED, not clean;
read-only fsck returned4. Its small evidence is retained, the temporary disk was
discarded, and a fresh disk passed with an1800s provision-only deadline. No acceptance
condition or production Stop deadline was relaxed. No system package/security change.
The GUI runner also frames serial output with a leading newline: a delayed prompt
had hidden the first actual evdev hex row. Failed evidence is retained, fsck0 confirmed,
and both GUI runs were repeated. The saved provisioning runner is hashed and its
whole AST must match current code except the inactive GUI branch; changed imports,
top-level code, provisioning, shutdown or fsck reject reuse. GUI reports require
the full current runner hash. No archived source is executed by that comparison.

The first offline replay was rejected for a kernel-copy hash mismatch. A four-method
isolated copy check did not reproduce it; the cause is UNKNOWN. The rejected files
and metadata remain available. A new-directory replay reproduced the exact sealed
tar, and seal/replay/restore/staged assets passed again after sync. No hash was
relaxed and no damaged output was published.

**Published and downloaded back:** [private prerelease](https://github.com/Mi-Yomi/iDeck/releases/tag/ideck-debian-gui-v1-local-20261017),
asset API `https://api.github.com/repos/Mi-Yomi/iDeck/releases/assets/650023557`. Server digest, downloaded size/SHA-256 and checksum all
match the locked payload. Private status verified before and after; no existing
asset or token changed. Release tag points exactly to source/evidence commit
`65cf483580ff27db57a33c2c53dcf67448861b0b`. This follow-up changes documentation/receipts only; Apple CI must use
the actual final pushed branch HEAD, including this delivery record.
See [delivery](experiments/linux-guest/GUI-PAYLOAD-DELIVERY.md) for the separate
`IDECK_GUI_PAYLOAD_URL` and one-run Apple preflight. CI remains NOT RUN.

Storage follow-up localized the first replay failure: the WSL kernel recorded
loop0 allocation failure in p9 writes and ext4 writeback errors; inode numbers map
to the rejected replay files. Final syncfs surfaced prior ENOMEM; its next call
passed. The task volume was unmounted, read-only fsck passed, then a read-only/noload
remount verified the accepted seed, frozen lab snapshot, kernel/initramfs, exact
replay tar, restored and staged assets from storage again. No repair was performed.
`build.raw` is retained unmounted; the staged Husk worktree is locked against pruning
until remount. The uploaded tar/checksum are ordinary Windows-visible files outside
that volume. See the five new publication/storage records in current evidence.

## Limited GUI credential fallback; Library producer attempt failed — 2026-10-17

После source/host readiness review parent указал avoidable CI setup blocker:
YAML уже импортирует `ideck-debian-payload`, но GUI downloader использовал только
отдельный GUI token. Исправлен ТОЛЬКО GUI transport selection:
`IDECK_GUI_PAYLOAD_TOKEN` имеет приоритет; если unset/empty, существующий
`IDECK_DEBIAN_PAYLOAD_TOKEN` читается/используется исключительно для HTTPS
`api.github.com[:443]/repos/Mi-Yomi/iDeck/releases/assets/<numeric-id>` без
userinfo/query/fragment, с прежним allowlist. Вне этого API fallback даже не
читается. GUI URL остаётся отдельным; Debian URL/token не заменяются и не
меняются. Новая credential/group не требуется. YAML/CI/guest/native/lifecycle
и payload lock/bytes не менялись. Redirect stripping/redaction прежние.

7 новых offline tests со СИНТЕТИЧЕСКОЙ env mapping и mocked HTTP: primary
precedence, fallback/missing/empty primary, port443, чужой host/repo/path/port /
query/fragment, bad URL, отсутствие чтения fallback вне scope, сохранение
Debian URL/token, redirect credential stripping/HTTPS-only, redacted HTTP error
и отсутствие publication. Никаких live env/token reads/auth requests в этих
проверках. Полный suite:281 tests /276PASS /5 explicit SKIP /0fail/error.
Обновлён только overlay input hash GUI helper. Повтор VM не требуется для
transport-only fix; original-kernel GUI evidence/seed/payload остаются прежними.

**Library output реально попробован:** свежие official upload/hosted-apps/
file-transfer helpers в `.work/gui-library-producer.8z3qh2`, один prepared batch
для ТОГО ЖЕ `ideck-debian-gui-v1.tar` и `SHA256SUMS`. Exit1, точный текст:
`library upload failed: hosted apps tools/list request failed: network`.
Подтверждённых Library files/library_file_id НЕТ; передача не состоялась.
Архив292034560bytes, SHA
`4b4b0bb1f75d5b662a8c1d866f482329449ee4d52d181e585ef4964a3540bbdb`
и checksum90bytes сохранены; `sha256sum -c SHA256SUMS` после попытки PASS.
Parent не имеет доступа к локальному `/workspace` пути: это НЕ delivery.
Нужен рабочий supported producer bridge; прямые неподдерживаемые обходы не делались.

**Уточнение прежней gh диагностики, БЕЗ повторных запросов:**
`gh release list --repo Mi-Yomi/iDeck --limit 5 --json tagName,name,isDraft,isPrerelease`
был последней shell-командой, exit1, stderr
`Post "https://api.github.com/graphql": Forbidden`.
`gh api repos/Mi-Yomi/iDeck/releases --jq 'map({id,tag_name,draft,prerelease})'`
дал `Get "https://api.github.com/repos/Mi-Yomi/iDeck/releases": Forbidden`;
его отдельный exit status не сохранён, общий shell позже вернул0 от tail.
GitHub HTTP status/body не получены; auth-отказ GitHub и proxy/tool-policy
запрет достоверно не различены. exec tool сам не отклонял команды.
Не выдавать этот transport-level error за доказанный GitHub credential failure.
Новых gh/auth/upload запросов, credential изменений и CI dispatch не было.


## ORIGINAL ALPINE GUI PASS; payload sealed, Apple inputs ready for review — 2026-10-17

**Прежний module transfer blocker закрыт.** Parent commits
`1d5f743d00a4de5f34637dc4cbd59e1675b15ab2` / `831b66c158239ac4c6de4dea0b9e470f05f30ad9`
получены через fetch/fast-forward поверх a2c32c5 в той же разрешённой ветке.
Vendor `experiments/linux-guest/vendor/alpine-3.24.1-aarch64/modloop-virt`
проверен локально:17670144bytes, SHA
`f969d12c8e23b486c8df651f04a4a9767f32fee16aed385c23462c31ea6cb47b`.
Parent/index/worktree bytes совпадают. Добавлен per-directory binary attribute:
глобальное text/eol правило иначе пыталось нормализовать этот binary при add.
Оригинальные parent commits/bytes сохранены, main не трогался.

Официальный unsquashfs извлечён из10 pinned Debian amd64 packages(4010988bytes),
проверенных по уже подписанному trixie/main index и GPG/freshness. Никакой установки
в host OS/maintainer scripts на host нет. Полный module closure/metadata/vermagic
совпал с ранее принятыми ext4 pins. GPU/input/evdev bytes исходного probe сохранены.
Production bootstrap использует тот же kernel SHA47970...1d756, не Debian provision kernel.

**Первый production boot выявил реальную ошибку machine-id:** dbus-uuidgen
отвергал existing empty seed placeholder. Исправление удаляет только пустой
regular placeholder, сохраняет непустой ID, отвергает symlink. Failed run НЕ
посчитан успешным GUI gate; serial recovery/independent Stop/clean unmount и
последующий read-only fsck PASS. Два новых boot проверяют стабильный machine ID.

**Два настоящих GUI boot с ORIGINAL Alpine6.18.35-0-virt PASS:**
29.489/27.410s acceptance elapsed, QEMU host sampled VmHWM932151296/922447872bytes.
Xorg modesetting DRM/KMS/VT1, root Xorg, UID1000 apps, real keyboard/pointer
move/resize, evdev wheel±1, root menu запускает xterm, Mousepad save/reopen,
проверка файлов до записи на boot2; normal configure + explicit audit status0
AND byte-empty output, exact341-package manifest, два control Stop и clean fsck.
RAM1024MiB/4vCPU/256MiB TCG/no swap прежние. Immutable GUI seed v4 не менялся.
Host QEMU10.0.13 всё ещё отличается от iOS10.0.12-utm: **device GUI не проверен**.
Evidence: `experiments/linux-guest/evidence/gui-alpine-20261017/acceptance.json`
и receipt/logs/scanout/failure-recovery fsck в той же папке.

**Seal/transport/staging PASS:** `ipa/gui.lock.json` теперь ready, это текущий
контракт payload; старые blocked/not-tested записи ниже исторические.

- raw1342177280bytes, SHA `46fea0230963ca494a5adeef19f46668f559f77522e3b82215d5f543646b0791`;
- gzip270352431bytes, SHA `8deb611138ad0afe400669d4d615093fea567d0950f48f55c97d608446a61769`;
- initrd11319304bytes, SHA `f8d8f4cc92f3f8d49e68adb90ab50d901c54f115d6134ae7030526fdee3de8b4`;
- **tar292034560bytes**, SHA `4b4b0bb1f75d5b662a8c1d866f482329449ee4d52d181e585ef4964a3540bbdb`.

Архив: `/workspace/iDeck/.work/gui-20261017/sealed-gui/ideck-debian-gui-v1.tar`,
рядом `SHA256SUMS` и exact gui.lock. Offline rebuild дал побайтно тот же tar;
sealed/replay/restored/staged bundles проверили все5 hashes/size. Исходный raw/gzip
и `.work/gui-20261017/gui-rebuild-inputs`/`alpine-modules`/authenticated cache
сохранены. Готовые raw assets: `.work/gui-20261017/desktop-app-assets/iDeckLinuxDesktop`.
Большие root images/tar не добавлены в git. Obsolete private candidates/VM roots
удалены после сохранения evidence, актуальные seed/production VM и source lab
snapshot сохранены. Прежние preparation receipts отражают свой pre-gate момент;
их false flags не переписывались задним числом.

**Проверки:**274 tests /269PASS /5 explicit toolchain SKIP /0fail/error.
Full pinned Husk source stage/native recipe patch check PASS; isolated copied
GUI helper verify готовых assets PASS. Source81 original Git blobs,37 inputs,
10 patched files,25 copies. Новый lock скопирован в overlay и inputs hashes обновлены.
Console locks, console guest init, LinuxDesktopDisk и owner NSCondition lifecycle
не изменены. Native Desktop route/input остаются в исходниках, готовые GUI assets
и Apple recipe reviewable; Swift/UIKit/full native link всё ещё NOT RUN здесь.

**Единственный delivery blocker:** текущий gh не может читать Release API:
`Post https://api.github.com/graphql: Forbidden` и
`Get https://api.github.com/repos/Mi-Yomi/iDeck/releases: Forbidden`.
Writable Release upload tool не exposed. Токены не создавались/не читались/не
менялись. Архив validated, но Release upload НЕ сделан. Точный необходимый шаг
parent: перенести этот archive+SHA256SUMS из сохранённого cloud workspace на host
с уже разрешённым private Release upload и загрузить без --clobber; затем проверить
скачанный hash и установить actual asset API URL в существующий CI transport.
См. `experiments/linux-guest/GUI-PAYLOAD-DELIVERY.md`; там нет guessed asset ID
или token instructions. Перед единственной сборкой parent выполняет review и
fresh free-quota/paidOFF preflight. **CI НЕ запускать здесь.**

Apple compilation/full native link/IPA/iPhone GUI, guest GPU acceleration, Steam
NOT RUN. Настоящий original-kernel host desktop и sealed GUI payload готовы;
приёмка GUI на iPhone остаётся владельцу после parent build.


## Audit status regression fixed; Library consumer transfer rechecked — 2026-10-17

После **e6fa8d17eb015d838a847e4c74a83f6f9cc55aba** readonly review нашёл
ошибку host acceptance: `test -z "$(dpkg --audit)"` игнорировал ненулевой
exit status dpkg при пустом stdout. Исправлено: audit stdout в отдельный файл,
status сохранён сразу, PASS требует status0 И byte-empty file. Нормальный
`dpkg --configure -a` остаётся обязательным; его ошибка пропускает audit и gate.
Provision/seed cleanup не обходились: их самостоятельный assignment под set-e /
explicit `|| fail` уже сохраняли неуспех. Новый guard общий для host и будущего
production Alpine acceptance; seal отвергает старый runner hash.

Добавлены3 shell regressions, исполняющие тот же guard: nonzero+empty stdout,
zero+непустой/newline/space stdout, configure failure. Это fault fixtures,
не mock GUI acceptance. Полный suite: **272 tests /267PASS /5SKIP /0fail/error**.
На свежей writable копии того же immutable GUI seed повторены ДВА настоящих
host GUI boot с замороженным runner source: **43.556/37.786s**, audit status0,
byte-empty audit file gate, input/wheel/menu/save/reopen, два clean Stop/fsck PASS.
Seed SHA46fea... не менялся. Новое evidence:
`experiments/linux-guest/evidence/gui-audit-fix-20261017/receipt.json`.
Host всё ещё Debian6.12.107/QEMU10.0.13, не Alpine6.18.35/iOS10.0.12-utm.
Старые results ниже исторические; новый acceptance supersedes слабый audit guard.
Obsolete private VM roots удалены для места; актуальный seed v4, новый audit VM,
все evidence и исходный immutable source snapshot сохранены.

Transfer диагностирован отдельно до этого исправления. В текущем ALL_TOOLS и
shell команды **download_file нет**; с новым parent Sediment ID
`file_00000000712881fd888e5ac42e4803ae` он НЕ вызывался, ошибки такого вызова нет.
Предусмотренный consumer-local Library путь — свежий официальный
`library_download.py` с полным результатом Library search через stdin.
Он выполнен ОДИН раз в `.work/modloop-transfer.y9rznW/`, exit1, точный текст:
`library download request failed: hosted apps tools/list request failed: network`.
Ни одного локального modloop-virt файла/bytes не появилось. Новый Drive Sediment
ID не смешивался с другим backing ID существующей Library записи. Дальнейшие
transport retries, token requests и изменения вне audit fix не выполнялись.

Matching-kernel GUI /sealing всё ещё BLOCKED, `ipa/gui.lock.json`=blocked.
Apple/native link/IPA/device GUI NOT RUN; CI не запускался.


## Native Desktop route + clean GUI seed; matching Alpine gate blocked — 2026-10-17

Продолжение после **9a6d18ea0c05d026b7feb142e511bdb2d1c2b950**, та же ветка
`codex/linux-guest-feasibility-20261015`, origin `Mi-Yomi/iDeck` проверен.
Fresh fetch показал тот же9a6d18e, новых чужих коммитов нет. В окружении нет
AGENTS.md/Apple SDK/Swift compiler; subagents, main/work, CI и credentials не трогались.
Commit/push только своей проверенной части разрешены делегацией.

**Реализован native route в исходниках:** `LinuxDesktopView`, отдельный
`LinuxGUIProfile`, `Documents/iDeckDebianGUI-v1/rootfs-v1.raw` и UUID
`b66e1c8d-9cbf-45a7-b97b-dcc8f68efca7`. Реальный существующий Husk Metal
framebuffer; landscape controls; normal keyboard events, special keys/F1–F12,
Ctrl/Alt/Shift/Super, right click и scroll. Serial recovery выделен отдельно;
serial sendLine не выдаётся за графическую клавиатуру. Soft text — US/ASCII,
максимум4096 символов; неподдержанный Unicode paste отклоняется целиком.
Unicode/IME ещё не заявляются. Keyboard HID/modifier ownership, cancel/outside
letterbox/focus/background/Stop releases парные. C/BQL input — отдельная очередь;
Stop имеет250ms независимый control fallback при застрявшей input queue.
Ни cleanup/unregister/unlock, ни userdata reset/resize/reseed не добавлены.
QEMU owner thread/NSCondition и disk lock до process exit сохранены.

**Guest production bootstrap написан, но NOT RUN:** исходное Alpine6.18.35,
точные virtio GPU/input/evdev/ext4, udev, DRM/VT, root Xorg с private Xauthority,
UID1000 session, local X socket/nic none, devpts/shm/run и обратный unmount.
RECOVERY_READY позволяет serial/Stop до X. GUI READY возможен только после
X connection +800x600 +mapped XTerm/Pcmanfm/Mousepad. Exit GUI оставляет recovery.

**Чистый seed v4 сохранён локально:**
`.work/gui-20261017/gui-seed-final-v4/seed/`:

- raw1342177280bytes, SHA `46fea0230963ca494a5adeef19f46668f559f77522e3b82215d5f543646b0791`;
- gzip270352431bytes, SHA `8deb611138ad0afe400669d4d615093fea567d0950f48f55c97d608446a61769`;
- used884068352 /free458108928bytes; streaming gzip/raw count+digest совпали;
- accepted sourceA32... не менялся. Cleanup в настоящей VM завершает writers,
  удаляет acceptance files/history/logs, normal configure/audit; e2image копирует
  только allocated blocks в НОВЫЙ raw; read-only fsck/UUID/размер/scripts проверены.

**Финальные два boot на свежей копии seed**40.775/38.621s PASS:
actual apps/UID1000, pointer move/resize, evdev REL_WHEEL ±1, real right-click
menu запускает ещё xterm, ввод/сохранение Mousepad, reopen до записи на boot2,
два clean Stop и read-only fsck. QEMU peak host VmHWM816996352/804188160bytes.
Гостевые1024MiB/4vCPU/256MiB TCG прежние. Runner source заморожен на оба boot,
его сохранённые bytes/hashes совпадают с текущим скриптом. Важно: **и kernel,
и QEMU отличаются** — host Debian6.12.107+deb13-arm64 /QEMU10.0.13, app original
Alpine6.18.35-0-virt /iOS10.0.12-utm. Это НЕ matching-kernel или iPhone acceptance.
Evidence: `experiments/linux-guest/evidence/gui-native-20261017/receipt.json`,
два набора оригинальных logs/results/fsck и actual scanout/menu. Крупные raw/gzip
не в git. Старые disposable test roots частично удалены, evidence сохранено;
актуальный seed v4 и исходный immutable laboratory snapshot сохранены.

**Отдельная payload chain реализована, fail-closed:** `gui_bootstrap.py` →
`gui_gate.py` (два real original-kernel GUI boots) → `seal_gui_payload.py`
(только exact successful evidence) → `gui_bundle.py` (verify/restore/stage/exact
rebuild). Отдельные GUI lock/HTTPS transport, gzip bounds, hash/size/low-space,
Xcode prebuild и IPA verify; IPA SHA тоже streaming1MiB. iPhone по-прежнему
импортирует verified raw из Xcode assets; gzip importer на iPhone не существует.
`ipa/gui.lock.json` намеренно **blocked**, без выдуманных hashes: build recipe
останавливается ДО Apple/native setup/private fetch. Финальный asset lock/archive
пока НЕ sealed, НЕ опубликован, НЕ готов к IPA. Console payload locks неизменны.

**Проверки:**269 tests,264PASS,5SKIP,0fail/error; полный overlay37 inputs,
81 original files,10 patched hashes,25 copies PASS;81 исходник совпал с real
Husk Git blobs0695248. Full source stage/native recipe patch --check PASS.
Новый C pointer function body действительно compiled/executed с unit queue
fixtures; это не full QEMU compile. Swift executable +UIKit/Apple checks NOT RUN;
обязательные actual Swift state/profile tests добавлены в Apple gate.

**Реальный blocker:** точные Alpine module bytes не materialized в этом executor.
Parent сообщает свой verified modloop, но его paths/file IDs не local files здесь.
CDN CONNECT403; Library tools/list network; Library prepare workspace_path:null;
Drive archive HTTP413(431008592>268435456); supported streamed-reference GET
URLError; inline modloop fetch `Transport closed`; download_file tool отсутствует.
Бесконечные retries/unknown binaries/live token requests не делались.
Минимум: modloop17670144bytes SHA
`f969d12c8e23b486c8df651f04a4a9767f32fee16aed385c23462c31ea6cb47b`, ИЛИ
4 exact .ko +3 metadata(~1.99MB)+manifest по `local-debian-ext4-modules.json`.
Bootstrap сверяет content с уже принятым pinned closure; provenance standalone
допустим, self-asserted hashes других модулей — нет. Прямой scan kernel не дал
читаемого config; DRM/VT acceptance остаётся реальным VM gate.

Следующий исполнитель: доставить эти bytes в cloud, выполнить bootstrap/gate/
seal по `GUI-DESKTOP.md`, review готового lock +refresh overlay hashes +tests,
передачу large private Release/CI согласовать с parent. **Не запускать CI**:
parent координирует одну сборку после review/fresh free-quota/paidOFF checks.
Apple/full native link/IPA/device GUI, accelerated guest GPU, Steam — NOT RUN.

Историческая запись предыдущего checkpoint ниже сохранена.


## Настоящий GUI на host; production Alpine transfer заблокирован — 2026-10-17

Продолжение от **b8a943f063302883e87d7deac0cb9abec0e37172** в сохранённом
cloud workspace `/workspace/iDeck`, только
`codex/linux-guest-feasibility-20261015`. Начальное дерево было чистым,
origin проверен, выполнен явный switch с `work`; новых чужих коммитов нет.
Применимых AGENTS.md в repo/родителях нет. Main/work, credentials и CI не менялись.

**Сделан реальный host desktop:** Xorg modesetting/KMS/VT1 с software rendering,
Openbox, tint2 с launchers, PCManFM, Mousepad, xterm; root Xorg, session UID1000,
local X socket/Xauthority, отдельные devpts/shm/run mounts, udev, no guest network.
Это полноценные Linux процессы внутри system-QEMU, не mock/framebuffer-test,
не remote streaming. Debian — не SteamOS. По parent upstream audit для Steam
существует ARM64 client; обязательная x86 эмуляция клиента не утверждается.
Steam, GPU acceleration и iPhone GUI этим этапом не проверены.

Отдельный authenticated `ipa/gui-inputs.lock.json`: **341 пакет ARM64/all**,
**175210844bytes .debs**, **736205824bytes declared installed**; один trixie/main
InRelease, принятые GPG signers, by-hash arm64/amd64 indexes, точные versions /
architectures /sizes /SHA, full solver replay. Security metadata не смешивалась.
Официальные QEMU/e2fsprogs/kmod извлечены локально из94 pinned host packages;
установки в host OS нет. Отдельный pinned Debian kernel6.12.107 — только
provision instrument, не замена production Alpine6.18.35.

Настоящая ARM64 VM успешно исполнила все package maintainer scripts, включая
systemd-sysusers/udev; normal `dpkg --configure -a`, пустой successful audit и
точный persisted341-package manifest PASS. Предварительный `--force-depends
--unpack` только bootstrap cycles; scripts не подменялись/не пропускались.
Два final GUI boot **38.882/34.546s**: mapped real clients, UID1000, фактический
ввод клавиатуры, move/resize виртуальной мышью, typing/Ctrl-S в Mousepad,
второй boot читает оба файла до записи и открывает сохранённый файл в редакторе.
Два control Stop, clean unmount и `e2fsck -fn` PASS. Дополнительный loader boot
**43.466s** повторил GUI/Stop/fsck и проверил **423 PT_INTERP executables** через
настоящий glibc loader `--list`. Inventory: 1133 ELF /3791 DT_NEEDED; один отдельный
private-DSO static residual сохранён, all-standalone-DSO PASS не заявлен.

Измеренный **host-only snapshot**: raw1342177280bytes (1.25GiB),
used884133888 /free458043392bytes; gzip400617549bytes. Raw SHA
`a32f7b9c0c59e651492811458e3a46667010eb4be54d07a79487e94c5e43ed06`, gzip SHA
`c1476f9e179b3dc5f6c8c3bbfce3e7e6e38351e4d914bc49aaa01b677a76b078`;
stream count/hash match. Это lab disk с acceptance files, не готовый app seed.
Будущий GUI UUID b66e1c8d-9cbf-45a7-b97b-dcc8f68efca7 /gui-rootfs-v1.raw;
production profile/size/disk path ещё не выпущены. Никакого auto resize/reseed.
Builder peak810754048bytes; host-QEMU provisioning peak sampled VmHWM1415208960,
GUI826548224/811683840, loader828547072bytes. Это не iOS memory evidence.
1GiB guest/4vCPU/256MiB TCG/no swap сохранены. Все 341 copyright files проверены.

**Native pointer fix:** release/cancel больше не требуют финального hit test,
stray move не создаёт down, duplicate/repeated releases idempotent; release при
app focus/background, removal/size change и перед Stop. Production Swift state
имеет mandatory 10000-cycle Apple test. Локально исходный pinned Husk restored,
patches/hashes/copies PASS; Swift/Apple/UIKit execution NOT RUN. Полный Desktop
input (keyboard/special/modifiers/right-click/scroll) и route остаются pending.
Owner-thread retention, single VM/process, lifecycle failure latch и disk locks
до app exit сохранены; qemu_cleanup/unregister/unlock не вводились. Accepted
console payload/seed/guest scripts и storage/lifecycle implementations неизменны;
в TerminalSession добавлена только pre-Stop input-release notification.

**Реальный production blocker:** прежних .work/rootfs/module artifacts в
восстановленном cloud workspace не было. Точный Alpine CDN archive HEAD дал
`403 CONNECT tunnel failed`; Library нашла приложенный modloop-virt17670144bytes,
но текущий штатный helper дал `hosted apps tools/list request failed: network`.
Обходных proxy/token channels нет. Нужен точный modloop SHA
`f969d12c8e23b486c8df651f04a4a9767f32fee16aed385c23462c31ea6cb47b`
либо уже принятые4 ext4 modules+metadata из прежнего build (total1908556bytes
module content; pins в local-debian-ext4-modules.json). Далее matching-kernel GUI
boot, final GUI seed/lock/stage/IPA integration и native Desktop route/input.
Не считать host Debian-kernel PASS доказательством production Alpine/iPhone GUI.

**Финальная offline suite:** 253 tests, 249 PASS, 4 SKIP, 0 failures/errors,
7.178 s. Четыре skips — отсутствуют
Swift, user-QEMU, original RCU archive и Swift pointer runtime. Native Apple gate
обязателен. Overlay: 30 inputs /78 originals /6 patched /19 copies PASS.

Сводка/команды/ограничения: [GUI-DESKTOP.md](experiments/linux-guest/GUI-DESKTOP.md).
Полные receipts, serial/package/fsck/loader/notices и настоящий scanout:
[evidence/gui-host-20261017](experiments/linux-guest/evidence/gui-host-20261017/receipt.json).
Большие raw/gzip/cache остались в `.work/gui-20261017/`; не загружены/не в git.
Нет Codemagic/иной CI, Apple build/typecheck/IPA/install/device runs, Steam или
новых live credential requests. Parent координирует transfer/review и будущую CI
после fresh quota/paidOFF checks; никаких самостоятельных запусков здесь.


## Debian device gate принят: две сессии, persistence и Stop — 2026-10-17

**Принято в ограниченном объёме:** две Debian console сессии на runtime source
**`338ee8065f90efd7f9fada1855c6f13d89035c8f`**, чтение сохранённого файла после
перезапуска приложения и Stop без дополнительного reported crash. Это новый
device evidence после fix; прежние записи «device NOT RUN / persistence
условна» ниже относятся к состоянию до этой приёмки и сохранены исторически.

Owner в **2026-10-17 04:50:36 UTC**: «Да все команды прошли успешно, вот тебе
логи, и не крашнуло, два запуска норм». Это ответ на явный вопрос, вернул ли
`cat` во втором запуске `ideck-debian-ok` **без повторного `echo`**, и перестал
ли Stop вызывать crash. Persistence — **owner-confirmed**, поддержана
screenshot; raw serial/result.json не предоставлены, machine-validated serial
assertion не заявляется. Две сессии не являются exhaustive fix/stress proof.

Parent прочитал оба device Markdown и осмотрел screenshot; этот executor
получил их bounded summary, самостоятельно IPA/reports/screenshots не скачивал
и визуальный просмотр не заявляет. Успешная Apple build:
[`6ad2f81f7550aed8108f7b0e`](https://codemagic.io/app/6ad03ce9a8a969b53f3a4aa9/build/6ad2f81f7550aed8108f7b0e).
SHA-256 доставленной IPA по parent:
`32ba7f8fbd3f2983d080ddf44103b90b5a0d907ef29c5aa11aaba404e275e75f`.
Это provenance полученной сборки; новая CI в этой docs-задаче не запускалась.

Оба reports: source338ee806, app2.0.0 build119, iOS27.0 build24A5430a;
installed executable SHA-256
`7d013c67bba87d71247d192b88ea6bf8c78c7bf9f33b78a7c7e8e11ec859ebdf`.
Сессии started **2026-10-17T04:44:20Z / elapsed69.290 s** и
**2026-10-17T04:47:53Z / elapsed72.445 s**. В обеих:
`terminal_clean_stopped`, JIT до/после init PASS, terminal ready PASS,
guest unmount PASS, QEMU loop return PASS, host fsync PASS, orderly Stop PASS,
owner-thread **RETENTION ENTERED**, host log/socket close path **RETURNED**,
disk lock **RETAINED**, import `existing_disk_preserved`, storage failure
**NONE RECORDED**. Seed/initramfs hashes по сравнению parent неизменны;
нового чтения/хеширования payload здесь не было. **Block layer drained
NOT VERIFIED** остаётся отдельным результатом.

Screenshot по parent: Debian GNU/Linux13(trixie), VERSION_FULL13.7, uid0;
`/dev/vda` size480M / used136M / available335M; marker file16bytes с более
ранним timestamp04:44; `CLEAN_UNMOUNT` и `Power down`. Это поддерживает
owner-confirmed one-file persistence, не whole-filesystem audit.
Bounded receipt с разделением источников:
[debian-two-session-device-acceptance.json](experiments/linux-guest/evidence/debian-two-session-device-acceptance.json).

**Ограничения сохранены:** GUI, accelerated GPU и полный backend teardown —
NOT VERIFIED; Steam и extended stress — NOT RUN. Один VM invocation на процесс,
следующая сессия после полного app exit/relaunch; disk owner/lock удерживаются
до process exit. Возврат host close path не доказывает backend close/drain.
Parent независимо проверяет следующий GUI milestone; реализации GUI здесь нет.

Эта docs/evidence задача начата с чистого дерева и проверенного remote HEAD
338ee8065f90efd7f9fada1855c6f13d89035c8f в той же ветке. Runtime, tests, overlay,
guest/payload/locks, пользовательские диски, credentials и main не менялись.
Старый native receipt остаётся исходной host-квитанцией до device acceptance.
Новых CI/build/download/install/device-run действий этим executor нет.
JSON/source/hash/date/claim-scope checks и `git diff --check` PASS; проверены
ровно три docs/evidence изменения и побайтная сохранность исторических секций.
Runtime tests повторно не запускались для этой документационной правки.

## Native RCU crash после Debian Stop: owner-thread lifetime — 2026-10-17

Работа в облачном Codex `/workspace/iDeck`, только
`codex/linux-guest-feasibility-20261015`, от проверенного remote HEAD
**`341541d09251556eff6fd9c99f5abd83ea20fb82`**. Окружение открылось на `work`
(`a77ab50`), дерево было чистым; выполнены fetch и явный switch нужной ветки.
`origin` — `https://github.com/Mi-Yomi/iDeck.git`. Применимых `AGENTS.md` в
репозитории/родителях нет. `main`, чужие изменения и credentials не менялись.

Новый owner device evidence: Debian console загрузилась; первая сессия дала
`terminal_clean_stopped` (source341541d, started2026-10-17T03:53:40Z,
elapsed379.325). Во второй Stop привёл к native crash. Screenshot с READY и
`ideck-debian-ok` не показывает команду: persistence остаётся **условной**,
окончательный Debian device PASS не заявлен. Первая квитанция завершается до
log/socket close и выхода worker, поэтому не доказывает здоровый shutdown tail.

Parent независимо сопоставил IPA UUID с системным IPS: EXC_BAD_ACCESS/SIGSEGV,
`synchronize_rcu +324 → call_rcu_thread +184 → qemu_thread_start`; **не Jetsam**.
На dylib offset8831588 `STR X11,[X10]`, X10=0; preceding load читает offset24
reader, то есть `node.le_prev`. Fault совпадает с записью в `QLIST_REMOVE`.
QEMU owner/Swift thread отсутствовал, четыре MTTCG vCPU оставались. Raw IPS,
личные metadata и IPA этим executor не загружались; учитывалось переданное
reviewer evidence. UUID и точные offsets записаны в документе ниже.

**Проверено по точному source:** публичный pinned release archive QEMU
`10.0.12-utm`, 142836072 B, SHA-256
`7c9605290b34152debb842e965a55d2e4fbba4793e536ab677b4027e5dc0ba1a`.
`system/vl.c:2851–2853` регистрирует caller в RCU для shared library;
reader — `__thread`, registry хранит его intrusive node; контракт `rcu.h`
требует unregister до выхода. `qemu_main_loop()` возвращается без teardown;
оба Linux Swift worker прежде возвращались из closure сразу после него.
Это **доказанный lifecycle defect**, хорошо объясняющий stale RCU linkage;
исправление device crash новым запуском ещё не подтверждено.

**Fix:** общий `LinuxQEMUThreadLifetime.retainCurrentThread() -> Never` после
loop-return на **том же** owner thread в Terminal/Debian и Probe. Private
NSCondition wait без polling/sleep/release API, с защитой от spurious wake;
сохраняются native TLS, стек и существующее владение BQL. Callback записывает
`qemuOwnerThreadRetained` до async loop-return handling. Это RETENTION ENTERED,
а не измерение дальнейшего здоровья процесса. Блокирующиеся на BQL callbacks
могут оставаться незавершёнными; **block-layer drain NOT VERIFIED**.
Сохраняются one VM/process, disk owner/lock до app exit, dirty-disk refusal,
failure latch, no reseed, Terminal/Probe routes. Нет null-check, unregister,
отключения RCU, `qemu_cleanup`, BQL unlock или освобождения backend/disk.

После прежнего узкого `cleanStopped` добавлены durable/fsync checkpoints
`consoleLogCloseBegin/Returned`, `consolePeersCloseBegin/Returned` и отдельное
поле report о возврате host tail. Они отражают достигнутый код/возврат попыток
close, не успех best-effort log IO и не завершение backend. Старые journals
читаются; tail completion для старых квитанций — NOT ESTABLISHED. Новый
renderer отличает retention/tail от clean unmount/sync и block drain.
В overlay.lock изменены только пять SHA соответствующих Swift runtime files;
copies, patches, guest/payload/disk lock inputs неизменны.

**Регрессии:** native C harness компилирует из SHA-verified source archive
точные RCU registry/grace-period/read-lock functions, struct/TLS/list macros с
pthread/atomic adapters. Реальный exit без unregister оставляет expired TLS
адрес в registry (без небезопасного dereference); unregister-control удаляет
его; retained owner проходит **10000 grace periods с 4 concurrent readers**,
repeated condition signals и сохранённым mutex/TLS linkage. Все три процесса
**PASS** на существующем GCC14.2.0. Это native RCU source slice, **не полный
QEMU backend и не выполнение production Swift**. Нового software не ставили.

Mandatory Apple gate отдельно дополнен реальным production Swift wait на
Foundation thread + pthread TLS destructor negative control, cancellation и
queue-progress; обязателен `LINUX_QEMU_OWNER_LIFETIME_PASS`. Добавлены actual
Swift journal reopen/tail-order/late-failure и Markdown compatibility checks.
В этом окружении Swift/Apple SDK отсутствуют: эти проверки **NOT RUN**.
Исторические host tests не заменяют новый Apple gate или device test.

**Окончательный offline suite:** Python3.12.14, **240 tests: 238 PASS,
2 SKIP, 0 failures/errors**, 11.285 s, с включённой native RCU regression.
SKIP: actual Swift owner/validation и user-mode ARM64 BusyBox/PTY — toolchains
отсутствуют. Python syntax, `git diff --check` и protected-input identity PASS.

Исследование/source evidence и инструкция следующей проверки:
[qemu-owner-lifetime.md](experiments/linux-guest/docs/qemu-owner-lifetime.md).
Native receipt: [qemu-owner-lifetime-native.json](experiments/linux-guest/evidence/qemu-owner-lifetime-native.json).
Рабочие logs/source/output: `.work/rcu-stop-20261017/`; полный окончательный
suite и числа — `tests-result.json`, `full-tests-verified.log`; offline overlay —
`overlay-result.json` (28 inputs / 78 originals / 5 patched / 18 exact copies).
Первые два прогона нашли только ошибки новых source assertions (substring
`Thread` в имени helper и ожидание signature в body-only extractor); они
исправлены, runtime по этим failures не менялся. Предыдущие logs сохранены.

**NOT RUN:** Codemagic/любая CI, Apple typecheck/build/link/IPA/signing/install,
полный QEMU backend на host, iPhone Stop→wait/export→relaunch/read. Payload,
guest, пользовательские диски/locks не открывались и не менялись; live payload
requests с token отсутствуют. Commit/push в эту же ветку без force разрешены
пользователем; итоговый полный SHA получить через `git rev-parse HEAD` и
сверить с remote. Следующий шаг — parent review и отдельный запуск CI только
владельцем после проверки бесплатной квоты, затем описанный device gate.

## Debian staging: SHA-256 без Python file_digest — 2026-10-16

Исправление выполнено в сохранённом облачном Codex `/workspace/iDeck`,
ветка `codex/linux-guest-feasibility-20261015`, от проверенного remote SHA
`00725bf78da543c62910d1b9d5c105521b4f5508`. Начальное дерево было чистым;
окружение открылось на `work`, затем явно переключено на рабочую ветку.
`origin` — `https://github.com/Mi-Yomi/iDeck.git`; применимых `AGENTS.md`
в репозитории и родительских каталогах нет. `main` не менялся.

По переданной пользователем диагностике build
[`6ad271b37550aed8108f5fff`](https://codemagic.io/app/6ad03ce9a8a969b53f3a4aa9/build/6ad271b37550aed8108f5fff)
прошёл Swift gate, payload size/SHA и native dependencies, включая QEMU
integrated и pairing, затем `app-build` завершился exit 65. Первый отказ —
`Stage verified iDeck Debian console`: `hashlib.file_digest` отсутствует в
Xcode `python3`. Точная версия этого Python из переданного лога неизвестна;
сам build/log заново здесь не запрашивался. Исторический fetch blocker ниже
не является первым отказом этой попытки.

`tools/debian_bundle.py:metadata`, `ci/build_linux_probe_ipa.py:sha` и
`ipa/package_probe.py:check_terminal_assets` теперь вычисляют `hashlib.sha256`
потоково, блоками **1 MiB**, включая корректный SHA пустого файла. Staging CLI
самодостаточен: общего импортируемого helper не добавлено. В
`husk/overlay.lock.json` изменён только SHA исходника `tools/debian_bundle.py`:
`e1bb0b89a87c4f95b3169c6f2772c37a515d5e6873c2db00e1d9a541e702a450`.
Проверки размера/SHA, самостоятельное перечитывание записанных файлов, fsync,
отказы для symlink/лишних файлов/небезопасного destination сохранены.

Добавлены **10 offline-регрессий** в `tests/test_streaming_hashes.py`:
пустой, малый и многоблочный файл для всех трёх функций; реальные чтения
ограничены 1 MiB; metadata/verify/stage/повторный stage без API; fsync и отказ
при его ошибке; обнаружение порчи записанных bytes как с изменённым размером,
так и при прежнем размере; отсутствующие/повреждённые/лишние файлы, symlink,
overlap и symlink ancestors. Отдельный subprocess с `-I` удаляет API **до
runpy**, исполняет побайтную копию `scripts/ideck-stage-debian.py` с
синтетическим lock и ресурсами теми же CLI-аргументами, что в Xcode phase:
verify → stage → повторный stage → verify, затем независимое сравнение bytes.

**Фактический полный прогон:** Python **3.12.14**, `hashlib.file_digest`
удалён перед unittest discovery: **236 tests, 234 PASS, 2 SKIP, 0 failures,
0 errors**, 7.954 s. Все **22 fetch diagnostics regression tests** и все
10 новых тестов PASS. SKIP: actual Swift owner/validation и ARM64 BusyBox/PTY —
здесь нет explicit Swift toolchain и user-mode QEMU. Python 3.9 не найден;
это **проверка отсутствующего API, не полная проверка Python 3.9 совместимости**.
Никакая версия toolchain/runtime не устанавливалась и не менялась.

Независимая offline-проверка overlay PASS: все **28 input hashes**,
восстановление **78** закреплённых оригинальных source files, применение
патчей и **5 patched hashes**, **18 byte-identical copies**. Semantic diff
overlay lock подтверждает единственное изменение соответствующего SHA.
`git diff --check` PASS. Логи и receipts в облачном workspace:
`.work/debian-python-compat-20261016/full-tests.log`, `tests-result.json`,
`overlay-result.json`; restored source — `overlay-source` рядом.

Payload, guest inputs и `ipa/debian.lock.json` не менялись. Lock побайтно
сравнён с исходным commit: **75601920 bytes**, SHA-256
`84851a3597901f1e3ef293c1490dc9c8a4a78b286bea8d2a10c330cb1413c558`.
Реальный payload здесь не загружался и повторно не хешировался; тесты используют
только synthetic fixtures. Release asset/secrets не менялись, токены не читались,
live credential/payload requests не выполнялись; пользовательские диски не
открывались. Commit/push разрешены владельцем в ту же ветку, без force;
полный итоговый SHA получить через `git rev-parse HEAD` и сверить с remote.

**NOT RUN:** Codemagic/другие CI, новые Apple Swift/native/app builds,
IPA packaging/signing/install, device execution и Debian на iPhone.
Host-тесты не являются доказательством запуска Debian на iPhone. Следующий
шаг — ревью нового pushed SHA; CI запускает владелец отдельно после ревью.

## Безопасная диагностика Debian fetch — 2026-10-16

Продолжение от `a63c8a7238bc6eafc8be1b015d9857798b28d5c2`, та же ветка
`codex/linux-guest-feasibility-20261015`. По переданному владельцем логу CI
`6ad25abf7550aed8108f597a` прошла Swift gate, затем остановилась на fetch до
native-компиляции. Причина **пока неизвестна**: прежнее сообщение её скрывало.
Эта правка добавляет наблюдаемость; успешная загрузка в CI не заявляется.

Release `ideck-debian-console-v1` уже опубликован на этом коммите, asset
`647969136` существует: `https://api.github.com/repos/Mi-Yomi/iDeck/releases/assets/647969136`.
Предыдущий исторический блокер «архив ещё не загружен» больше не актуален.
Размер 75601920 и серверный SHA-256 совпали с lock при публикации; в этой
задаче живые запросы к payload с токеном **не выполнялись**. Secrets не читались
и не менялись; транспорт, права и токены наугад не исправлялись.

`debian_bundle.fetch()` теперь печатает `IDECK_DEBIAN_FETCH_RESULT` и передаёт
тот же безопасный объект в `result.json` → `debian_payload_fetch`:

- Фиксированные коды `DEBIAN_FETCH_OPEN_FAILED`, `READ_FAILED`, `WRITE_FAILED`,
  `VERIFY_SIZE`, `VERIFY_HASH`, `VERIFY_FILE`, `PUBLISH_FAILED` с тем же префиксом;
  отдельные фиксированные CONFIG/CLEANUP-коды, успешный `DEBIAN_FETCH_OK`.
- Только класс исключения из списка стандартных классов (для URLError —
  вложенный TLS/socket-класс, произвольный класс заменяется на `Exception`),
  числовые `http_status`/`errno` либо null, `received_bytes`, `expected_size`,
  вычисленный `sha256`, `sha256_scope` и `elapsed_seconds`.
- SHA относится к полученным байтам, включая `IncompleteRead.partial`,
  даже если запись не удалась. `complete` означает EOF при точном размере
  из lock, **не** совпадение хеша; обрыв/короткий ответ/лишние байты — `partial`.
  HTTP error body не читается. При нуле полученных байтов — SHA пустого потока.
- URL, headers, body, token, environment, текст/notes/цепочка исключений
  не экспортируются. CI ловит безопасный `FetchError`, записывает фиксированный
  failure-код и выходит с кодом 1 без transport traceback. CLI делает то же.
- HTTPS, ограничение адресата токена, удаление Authorization при redirect,
  проверка размера/хеша потока **и отдельная проверка сохранённого файла**,
  публикация через `link` без перезаписи и очистка partial сохранены. Ошибка
  очистки отражается безопасно, не скрывая первичную причину сбоя.

Добавлены **22 offline-теста**: HTTP401/403/404/429/5xx, timeout/TLS/DNS,
deadline, обрыв с partial, короткий/длинный ответ, неверный хеш, порча записанного
файла, ошибки открытия/записи/flush/publish/cleanup, конфликт публикации,
HTTPS redirect и запрет утечки секретов, включая реальный путь формирования
CI result.json и CLI. Никаких live payload requests или новых компонентов.
Полный набор: **226 tests, 225 PASS, 1 SKIP**. Swift/Apple toolchain локально
отсутствует: **NOT RUN**; здесь прежняя обязательная Swift gate не обходилась.
Логи: `E:\Freddy Fazbear\iDeck.work\debian-fetch-diagnostics-20261016\full-tests.log`
и `tests-result.json`.

Payload/guest inputs и `ipa/debian.lock.json` не менялись, пересборки payload
не было. В `husk/overlay.lock.json` обновлён исключительно вычисленный SHA-256
изменённого `tools/debian_bundle.py`, необходимый для проверки исходников.
Следующий шаг — ревью и отдельно разрешённый CI-запуск, затем разбор нового
кода/числовых полей, без предположений о токене или транспорте. В этой задаче
CI/Codemagic **не запускались**, main и существующий userdata не изменялись.

## Stop: необратимая ошибка host fsync — 2026-10-16

Продолжение от `1cb1cb1a0f22fea9a5af6f16fbe6a0c167a02ef8`, та же ветка
`codex/linux-guest-feasibility-20261015`. В общем пути Terminal/Debian ошибка
host fsync теперь фиксирует `lifecycle.failed` до выхода из синхронизации,
а `finalizeIfClean()` устанавливает `stopFailed`, checkpoint `.stopFailed`,
`terminal_stop_failed = true`, `terminal_clean_stop = false` и status
`terminal_stop_failed` до сохранения отчёта. UI тоже остаётся без clean Stop.
Повторный/уже поставленный в очередь finalize не повторяет fsync и не может
объявить эту сессию clean. Владелец, дескриптор и эксклюзивная блокировка
сохраняются до выхода приложения; возврат QEMU loop не доказывает cleanup.

Swift-регрессия вызывает production `synchronizeForCleanStop` для обоих
реальных владельцев диска: первый sync получает внедрённую ошибку, повторный
finalize отклоняется, отдельный следующий настоящий sync проходит, но даже
поздний `.hostSynced` оставляет состояние failed. Проверяются оба порядка
unmount/loop-return, владение диском и последующие отдельные процессы,
которым по-прежнему недоступна блокировка. Успешный Stop и повторный finalize
после успеха также проверяются через этот production helper. Это обязательная
часть существующего Apple runtime/storage gate, не симуляция QEMU.

Локально: **204 Python tests, 203 PASS, 1 SKIP**, включая новый контракт
необратимого failure, прежние Terminal/Debian/Probe и применение overlay
к закреплённым настоящим исходникам Husk. **Swift runtime / Apple SDK:
NOT RUN** — toolchain отсутствует, SKIP не заменяет обязательный Apple gate.
Новые логи: `E:\Freddy Fazbear\iDeck.work\stop-fsync-20261016\full-tests.log`
и `tests-result.json`. Guest/bootstrap/storage inputs не менялись, поэтому
host VM и payload не пересобирались. Повторно проверен SHA-256 существующего
`debian-console-20261016\payload-final\ideck-debian-console-v1.tar`:
`84851a3597901f1e3ef293c1490dc9c8a4a78b286bea8d2a10c330cb1413c558`.
Блокер доставки payload в Apple CI остаётся прежним (см. ниже).
Codemagic/CI **не запускались**; main, чужие изменения и userdata не тронуты.

## Отдельная Debian-консоль и production payload — 2026-10-16

Продолжение от **`3bcb4811726c690a988b95c828c11661090869ca`**, в той же
ветке `codex/linux-guest-feasibility-20261015`. Все новые файлы, тестовые диски,
кэши и отчёты — на E:. Применимого `AGENTS.md` в репозитории и его родительских
каталогах не найдено; прочитан актуальный HANDOFF. `main`, чужой индекс
`.work/source` и существующий userdata не изменялись. Codemagic **не запускался**.

Добавлен отдельный Debian route через существующий настоящий Husk/QEMU и
консольный worker, с диском `Documents/iDeckDebian/rootfs-v1.raw`. Terminal и
Probe сохранены. Первый импорт проверяет SHA-256, свободное место, ext4 и
владение, не перезаписывает существующий диск; прерванный импорт повторяется
через эксклюзивно захваченный staging-файл. Dirty/needsRecovery вызывает
понятную ошибку восстановления без форматирования/пересоздания.

**Инвариант Stop сохранён:** clean unmount + возврат QEMU loop + host fsync
не доказывают закрытие backend. Эксклюзивный владелец диска удерживается до
выхода приложения, включая успешный Stop. Повторная VM — только после выхода
и нового запуска приложения. Таймаут и failure не становятся clean после
позднего подтверждения. Никакого неподтверждённого `qemu_cleanup`/unlock.

Production bootstrap сохраняет Alpine initramfs → Debian chroot, merged-/usr,
virtio_mmio/virtio_blk и точное ext4 closure. Это живая консоль, с отдельным
control-каналом Stop; тестового автоматического poweroff нет. Найдено и
исправлено наследование ignored SIGINT/SIGQUIT Debian dash от фонового getty:
login использует `env --default-signal=INT,QUIT`. Реальный Ctrl-C теперь проходит.

**Проверки:** 203 Python tests: **202 PASS, 1 SKIP** (Swift toolchain отсутствует).
Две настоящие загрузки окончательного payload в host QEMU 11.1.0: интерактивные
команды, Ctrl-C, Stop через control / shell exit, перезапуск, сохранение файла,
прав, UID/GID, inode/hardlink/symlink; оба exit 0. `e2fsck -fn` exit 0 и не менял
копию. Эталонный seed не изменился. Swift/Apple/IPA/Debian на iPhone — **NOT RUN**.
Новый Swift lifecycle/storage regression обязателен в Apple workflow; parse-only
или SKIP не удовлетворяет gate. Исторические неудачные host-попытки сохранены.

Полная инструкция: [DEBIAN-CONSOLE.md](experiments/linux-guest/DEBIAN-CONSOLE.md).
Receipt: [debian-console-receipt.json](experiments/linux-guest/evidence/debian-console-receipt.json).
Рабочая папка: `E:\Freddy Fazbear\iDeck.work\debian-console-20261016`;
окончательная host-проверка — `host-006`, передаваемый payload —
`payload-final\ideck-debian-console-v1.tar`, **75601920 B**, SHA-256
**`84851a3597901f1e3ef293c1490dc9c8a4a78b286bea8d2a10c330cb1413c558`**.
Raw seed SHA остался `a081d86594a0c59e585541ae26fa586468f267767dc081796f51186ea9c01217`.
Final payload повторно воспроизведён production helper побайтово.

**Блокер Apple IPA:** tar ещё не загружен в доступное CI приватное хранилище.
Конкретный путь: Release asset приватного Mi-Yomi/iDeck → GitHub asset API,
secret group `ideck-debian-payload` с URL и ограниченным read Contents token.
Подробные команды и проверки приведены в DEBIAN-CONSOLE.md. URL/asset ID/token
не выдуманы и не созданы. Downloader проверяет размер/SHA до распаковки,
не передаёт API token на redirect, проверяет все bundle-файлы и seed после
декомпрессии; Xcode/packager повторяют проверки. Большие payload в Git не добавлены.

Следующий шаг после ревью: настроить доставку payload, обязательный Apple
Swift regression/typecheck, затем отдельно разрешённая native IPA-сборка и
проверка владельцем на iPhone. Host PASS не является проверкой iPhone, безопасной
очистки встроенного QEMU backend, GUI или Steam.

## Локальный Debian/ext4: две настоящие VM-загрузки PASS — 2026-10-16

Продолжение от remote `5adc493570f3cc41cc1a70925d95e74f2ebab37d` в
`E:\Freddy Fazbear\iDeck`, та же рабочая ветка. Новая инструкция владельца
заменила старый ночной план: **только локальный host Debian/ext4, без Codemagic,
GUI и Steam**. Все новые инструменты, кэши, образы и отчёты сохранены на E:.

**Результат:** [полный receipt](experiments/linux-guest/evidence/local-debian-ext4.json),
два полных serial logs и fsck/tests/build/module receipts рядом в evidence.
Локальный комплект: `E:\Freddy Fazbear\iDeck.work\local-debian-ext4`,
основные `result.json` и читаемый `result.md`; успешный запуск — `two-boot-002`.

- Найден уже имевшийся Alpine netboot на E:. Архив **431008592 B** и modloop
  **17670144 B** совпали с исходными закреплёнными SHA. Перенос из облака не нужен.
- Получено фактическое замыкание; порядок загрузки: `crc16, mbcache, jbd2, ext4`, суммарно
  **1908556 B**. Проверены AArch64 ELF, vermagic `6.18.35-0-virt`, зависимости
  и структура подписей. Исходные modules.dep/softdep/builtin сохранены.
- Debian seed пересобран полным builder из 90 официальных пакетов, с проверкой
  Debian signatures/indexes/hashes. Raw **536870912 B**, SHA
  `a081d86594a0c59e585541ae26fa586468f267767dc081796f51186ea9c01217`;
  gzip **53918211 B**, SHA
  `97e55ebdf61892848e55a45e4016163e6c55b737afb2c31ccb3939a23e12a747`.
  Оба **побайтово совпали с прежними эталонами**, несмотря на другую среду.
- Windows system-QEMU **11.1.0**, `virt`, Cortex-A72, 4 CPU, 1024MiB RAM,
  TCG/256MiB, `-nic none`. Только новая копия seed подключалась на запись.
  Boot 1: **4.485 s**, boot 2: **4.281 s**, оба QEMU exit 0. В каждом реально
  загрузилось ядро 6.18.35, смонтировался ext4 и выполнился Debian/glibc 2.41.
- На обоих boot совпали пакетная база, содержимое, UID/GID, chmod/exec, symlink,
  hardlink/inode/link count и результат rename. Запись сделана с `dd conv=fsync`,
  исполняемый файл запущен также как UID/GID1000. Оба раза проверены sync,
  unmount и poweroff. Это последовательные корректные выключения/старты,
  не тест аварийного питания.
- После остановки `e2fsck -fn` **exit 0**, проверка не меняла тестовый диск.
  SHA исходного seed после обоих boot остался прежним. Действующий userdata
  не открывался. **190 tests: 189 PASS, 1 SKIP** (нет установленного Swift
  toolchain); реальный ARM64 BusyBox/PTY regression прошёл. Shell syntax PASS.

Исправления: softdep теперь строго проверяется в достижимом hard/soft closure,
включая builtin owners; посторонние cifs/ksmbd/btrfs declarations не блокируют
ext4, нераспознаваемые headers и ошибки/дубликаты достижимых записей отклоняются.
`dpkg --audit` отдельно проверяет exit code и output. Builder обходит разбор
пробелов в PRoot `-q` через повторно проверенную копию QEMU с относительным
именем и контролируемым cwd. Тестовые Apple compiler fixtures работают на E:
с пробелом без ослабления production guard. Новый host runner и bootstrap
изолированы от production iOS assets/locks.

Сохранены неуспешные подготовительные попытки. У первого boot тестовый suffix
заменял Alpine `/lib` symlink каталогом; kernel не находил shell interpreter.
Исправлено размещением модулей в `/usr/lib/modules`; regression запрещает
замену merged-/usr aliases. `two-boot-001` не считается успешным. Первые host
попытки выявили NTFS FIFO/permissions и PRoot space-path ограничения; свежая
сборка прошла в отдельном ext4 scratch image на E:, после работы размонтированном.

**Следующий шаг для Гвен:** отдельно интегрировать подтверждённые Debian seed
и ext4 bootstrap с существующим `LinuxDesktopDisk`/profile и управляемым clean
Stop, сохранив terminal/probe. Затем отдельная Apple/IPA и owner device проверка
Debian. Здесь новая IPA/CI не запускались, Debian/ext4 на iPhone, GUI и Steam
**не проверены**. Успех терминала на iPhone из прежней передачи остаётся отдельным
пользовательским подтверждением. `main` и индекс `.work/source` сохранены.

Ночная передача Dots: [DOTS_OVERNIGHT.md](DOTS_OVERNIGHT.md). В ней указаны
текущий этап, работа четырёх подагентов и порядок сборки/фиксации результата.
Для следующего Codemagic запуска нужен полный текущий pushed HEAD, включая
коммит этой инструкции; SHA последнего исправления кода указан отдельно.

## Attached modloop: Library transfer tunnel BLOCKED — 2026-10-16

Продолжение от pushed **c973f4ca648856ad2fba18a27130bb2fad8dc38e**. Среда
доступна, checkout/чтение/запись работают. Owner приложил отдельный `modloop-virt`;
`library.prepare_materialize` успешно вернул transfer и metadata размер
**17,670,144 B**, но `workspace_path:null`: для получения bytes требуется GET
по выданному signed transfer URL.

Единственный штатный GET завершился **`URLError: <urlopen error Tunnel
connection failed: 403 Forbidden>`**. Это отказ network tunnel, не доказанный
запрет Library ownership и не ошибка digest. Получено **0 bytes**, partial
temporary не осталось, локального `modloop-virt` нет. Размер выше — declared metadata,
не измерение content в этом executor. Expected SHA-256 остаётся
**f969d12c8e23b486c8df651f04a4a9767f32fee16aed385c23462c31ea6cb47b**,
actual SHA **не проверен**. Library/Drive ID, completion token и signed URL в
Git не сохраняются. [Точный receipt](experiments/linux-guest/evidence/desktop-modloop-library-transfer-blocked.json).

Повторов, других URL/proxy/executor, network/security setting changes и
escalation обхода не выполнялось. Требуется поддерживаемо материализованный
exact member в выбранной среде. До доступных bytes нельзя разрешить ext4 module
closure, собрать проверенный initramfs или выполнить guest mount/POSIX/two-boot.
Новая IPA не подготовлена; CI не запускался. Прежние проверенные rootfs images,
userdata, terminal/probe, JIT/SideStore/MD export, main сохранены. Ниже сохранён
предыдущий независимый Drive size-limit blocker; новый файл меньше этого
лимита, текущий отказ относится именно к Library transfer network tunnel.

## Owner-provided netboot: Drive transfer BLOCKED — 2026-10-16

Продолжение от pushed **b59e209b7a9ec55aef7bfb2bf6f968805a4a9727**.
Owner передал Drive-ссылку на файл с именем официального netboot. Поддерживаемый
connector metadata read вернул `alpine-netboot-3.24.1-aarch64.tar.gz`, MIME
`application/x-gzip`, **431,008,592 B** — ожидаемый размер совпадает.

Raw fetch с `download_raw_file:true, include_base64:false` отклонён **до action
invocation**: **HTTP413**, `431008592 bytes exceeds the 268435456-byte limit`.
Это лимит Drive connector **256MiB**, не доказанный запрет доступа владельцем
и не ошибка SHA. Bytes не получены; actual archive SHA и modloop SHA **не
проверены**. Среди доступных tools отдельного streaming `download_file` нет;
native-file export неприменим к сохранённому .tar.gz. Другой executor, proxy,
альтернативные download URL, дробление/encoding не использовались.

[Точный transfer receipt](experiments/linux-guest/evidence/desktop-netboot-drive-transfer-blocked.json)
содержит provider error без private Drive ID/URL. Expected archive по-прежнему
**431,008,592 B**, SHA-256
**54fe38fa41cce740ba379458ed63cfcd89ab06ae5e6a47a06dafe0a34e8427e8**.
Минимальный payload — `boot/modloop-virt`, expected SHA-256
**f969d12c8e23b486c8df651f04a4a9767f32fee16aed385c23462c31ea6cb47b**;
actual размер неизвестен. Для следующего шага нужен поддерживаемо
материализованный exact archive/member в выбранном execution environment.
До проверки bytes нельзя извлекать closure, собирать проверенный bootstrap
или заявлять Debian/ext4 guest mount/two-boot PASS.

Прежние byte-identical Debian images, terminal/probe, legacy userdata,
JIT/SideStore/MD export сохранены. Runtime и main не менялись; CI/новая IPA/
payload publication, Drive sharing changes, новые keys/connections/payment
не выполнялись. Эта запись фиксирует конкретный transfer blocker; она не
заменяет отсутствие guest/iPhone validation host metadata evidence.

## Полный offline CLI replay и воспроизводимость — 2026-10-16

Новая реализация/проверка от pushed **be432d6283d0f47ca5e9ad5f1bd60cbd8627c728**.
**Два независимых полных окончательных builder CLI, каждый с нуля, PASS.**
Actual `cmp` raw/gzip/profile, build receipts и manifests совпали побайтово.
Это заменяет прежнее «full final CLI replay unverified» только для новых
результатов; исторический staged receipt ниже сохранён без переписывания.
Полный [replay receipt](experiments/linux-guest/evidence/desktop-rootfs-cli-replay.json)
и [инструкция](experiments/linux-guest/DESKTOP-ROOTFS.md).

Два отдельных output и cache metadata, общий exact verified package/tool input,
тот же host/toolchain. CLI `build --offline` повторно проверяет size/SHA каждого
cache input, GPG/freshness и точные package pins; miss/corruption прекращается
до fetch/download temporary. Новый lock offline запрещён. Это не network
namespace isolation для maintainer scripts. Source digest захвачен в начале;
изменение builder до выдачи profile/receipt отклоняется. Frozen final source SHA
**4b0492b1e8562b78d23abe5a7538d47fd7b2b1fdbdc399e8b89560c0b0df39ee**,
`end_to_end_replay_of_final_source:true` в обоих финальных receipts.

Актуальные локальные артефакты: `/workspace/ideck-desktop-build/cli-replay-v2/`
и независимый `/workspace/ideck-desktop-build/cli-independent-v2/`.

- `rootfs-v1.raw`: **536,870,912 B**, SHA-256
  **a081d86594a0c59e585541ae26fa586468f267767dc081796f51186ea9c01217**.
- `rootfs-v1.raw.gz`: **53,918,211 B**, SHA-256
  **97e55ebdf61892848e55a45e4016163e6c55b737afb2c31ccb3939a23e12a747**.
- `desktop-rootfs-profile.json`, `build-receipt.json`, manifests, private logs.
  Used blocks **175,714,304 B**, free **361,156,608 B**; resize2fs -P estimate
  **168,038,400 B** без actual resize. First import D+C+512MiB =
  **1,127,660,035 B**, плюс iOS install и optional legacy backup.

Первые два полных CLI уже проходили configure/audit/ELF/fsck, но raw/gzip
различались. Independent semantic diff всех 6744 entries нашёл только
timestamped `var/log/alternatives.log`; inode ctime/atime зависели от host.
Исправлены именно fresh seed outputs: fixed ext4 directory hash seed, sorted
publication paths, все четыре inode times+extra nanoseconds закреплены и
проверяются после mke2fs, очищается только generated alternatives install log.
У всех 19 validated locked accounts в shadow и shadow- last-change day теперь
release epoch; password fields/остальные поля сохранены, unlocked seed row
отклоняется. Другие logs/docs, notices и package DB не очищались. Existing
userdata не открывалась и не нормализовалась.

Independent readonly validation **каждого** нового image: Swift CRC/UUID/
features/geometry, e2fsck -fn, gzip-stream digest, все 6744 UID/GID/mode entries
и 26976 inode timestamp fields+extra0, 19 locked rows в каждом shadow/backup,
source/tool/keyring/manifest hashes — PASS. Root Swift owner и disposable image
tool roundtrip тоже PASS, seed SHA unchanged. **182 tests PASS, 14.045 s**;
module13 и builder15 regressions reviewer повторил. Scope byte identity:
два полных fresh CLI в этом host/toolchain; не универсальное доказательство
всех платформ/будущих дат. Freshness/expiry/90-day предел cache replay сохранён.

**Точный минимальный внешний input для ext4:** файл **`boot/modloop-virt`**
(можно передать под именем `modloop-virt`) из исходного
`alpine-netboot-3.24.1-aarch64.tar.gz`, kernel **6.18.35-0-virt**. SHA-256
**f969d12c8e23b486c8df651f04a4a9767f32fee16aed385c23462c31ea6cb47b**;
его actual size здесь **UNKNOWN**. Historical pin подтверждён original
commit **36d2463190b1fbac503960a30e0f6bf5dccb7e79**,
`evidence/guest-profile.json` и profile внутри committed probe bundle.
`prepare_guest.py` сначала проверяет archive SHA/size, затем вычисляет SHA
именно этого member. Source pointers в `ipa/desktop-kernel-source.lock.json`.

Ранее проверенный официальный [archive URL](https://dl-cdn.alpinelinux.org/alpine/v3.24/releases/aarch64/alpine-netboot-3.24.1-aarch64.tar.gz),
[checksum URL](https://dl-cdn.alpinelinux.org/alpine/v3.24/releases/aarch64/alpine-netboot-3.24.1-aarch64.tar.gz.sha256):
**431,008,592 B**, SHA-256
**54fe38fa41cce740ba379458ed63cfcd89ab06ae5e6a47a06dafe0a34e8427e8**.
Эти pins сохранены также в `evidence/boot-inputs.json`. Отдельного проверенного
прямого URL modloop нет. Existing local cache/artifact search его не нашёл;
никакого нового download/другого executor/proxy обхода HTTP403 не было.
Если exact modloop уже сохранён у владельца, полный 431MB archive передавать
не требуется: `tools/desktop_modules.py --modloop <local-file>` принимает
snapshot regular/no-follow/bounded input с exact SHA и прежними общими
deps/ELF/vermagic/signature-container guards. Standalone manifest честно
помечает archive/kernel bytes verification false/null; expected kernel pin
отдельно. Actual closure/load/mount остаются UNKNOWN до получения bytes.

**CI/новая IPA/большой payload не публиковались**, main, legacy FAT/userdata,
terminal/probe, JIT/SideStore/MD export и глобальные network/security settings
сохранены. No new external accounts/keys/connections/payment. Следом по-прежнему exact
module closure → реальный ext4 mount/два guest boot POSIX → Xorg/Openbox/xterm.
Apple/CryptoKit/device/memory/GUI/Steam gates не пройдены этим host replay.

## G0/G1 Debian/ext4 host preparation — 2026-10-16

Реализация от pushed **d4d447779a4fc1d6e2b45b9de6893fb16722cb8f** на той же
`codex/linux-guest-feasibility-20261015`. Это следующий desktop этап после
подтверждённого terminal device PASS ниже, а не возврат к старому read-only
аудиту. Подробности: [DESKTOP-ROOTFS.md](experiments/linux-guest/DESKTOP-ROOTFS.md),
полный [host receipt](experiments/linux-guest/evidence/desktop-rootfs-host-preparation.json).

**Получен настоящий локальный Debian13/trixie arm64 glibc minbase+POSIX ext4
seed**, 90 exact packages: download **35,157,424 B**, declared Installed-Size
**155,331,584 B**. Signed InRelease, оба by-hash indexes и каждый guest/host
.deb проверены; independent reviewer повторил проверку offline. Официальные
Debian источники, существующий keyring; ни новых ключей, ни внешних аккаунтов/оплаты.
Lock: `experiments/linux-guest/ipa/desktop-rootfs.lock.json`.

Артефакты остаются **локально**, не в Git/Library/CI:
`/workspace/ideck-desktop-build/posix-v4/final-v2/`.

- `rootfs-v1.raw`: **536,870,912 B**, SHA-256
  **db0a5b715ff4caf5e326d30d79cce8146baa33246e5fa89c522b62c4f5254f84**.
- `rootfs-v1.raw.gz`: **53,918,756 B**, SHA-256
  **7971640d7a295c78a853b1a49fb4abdb6cb222efff67eaf6165d564393004f54**.
- `desktop-rootfs-profile.json`, `build-receipt.json`, retained local finalizer
  script; allocated blocks **175,718,400 B**, free **361,152,512 B**.
  resize2fs -P estimate **168,042,496 B** — не validated minimum resize.

Actual ARM64 maintainer scripts/configure, empty dpkg audit, exact installed
manifest и glibc execution PASS; 700 ELF/1888 DT_NEEDED edges, все 6744 source
manifest UID/GID/mode entries, e2fsck -fn PASS. Independent reviewer повторил
raw/gzip hash, decompressed stream, read-only Swift CRC/UUID/features/geometry,
fsck, ownership/modes/password-lock metadata checks. Root actual Swift owner
проверил этот же raw; disposable ext4 tool copy сохранила content/hardlink/
symlink/UID/GID/mode через reopen+fsck, seed hash не изменился. Это host/image
evidence, **не guest POSIX syscall/two-boot PASS**.

**Честная граница build evidence:** configure уже завершился, когда review нашёл
host umask0077 effects. Текущий shared helper явно задаёт public guest modes;
новый image phase прошёл из того же audited configured tree после исправления.
Два invalid mke2fs.conf candidates отвергнуты, причина empty base_features
исправлена. `end_to_end_replay_of_final_source:false` сохранён в receipt:
полный fresh CLI replay и byte-identical rebuild не заявляются. PRoot child-only
compatibility filter добавляет ограничения для старых stat/access/chown paths,
не меняет глобальные host security/network settings; PRoot не является VM.
Notices `/usr/share/doc` сохранены. Retained cache replay ограничен expiry и
90-day release max-age; mutable mirror не гарантирует вечную доступность pool.

Добавлены отдельные `LinuxDesktopDisk`/`LinuxDesktopProfile`, exact ext4 contract
и SHA-validated raw provisioning. Locked descriptor сохраняется при no-clobber
publication; directory/temp replacement и malformed/dirty filesystem отклоняются.
Mutable reopen не сравнивает seed whole-file hash. Existing FAT guards не
расширялись. Это **storage-only**: runtime route/QEMU argv/user-facing gzip import
ещё отсутствуют. Примитив raw copy reserve D+32MiB; будущий importer должен
проверять D+C+512MiB = **1,127,660,580 B** плюс iOS install/optional FAT backup.
Ни auto-reset/delete/migrate, ни crash/power-loss durability claim нет.

Финальный suite **174 tests PASS, 14.561 s**, с реальным Swift6.2.1 storage helper
и ARM64 BusyBox/PTy regressions; umask077 regression включена. Overlay24 hashes /
14 copies и diff check PASS. Четыре роли: root integration/storage, Debian builder,
same-kernel modules, independent reviewer; после найденных исправлений blockers
к коду не осталось. Apple SDK/CryptoKit новые tests подключены к прежнему check,
но **CI не запускался**, новой IPA нет; parent контролирует quota/payment.

**G0 module / G1 guest blockers:** official aports source config показывает
`CONFIG_EXT4_FS=m`, это не compiled IKCONFIG proof. Exact original Alpine archive
**431,008,592 B**, SHA
**54fe38fa41cce740ba379458ed63cfcd89ab06ae5e6a47a06dafe0a34e8427e8**
не cached; official CDN/dl-2/listed mirror дали HTTP403. Source lock и offline
`tools/desktop_modules.py` готовы, но фактические closure/load order/bytes/hashes
не выдуманы. Нужен доступный exact archive, затем extraction/vermagic/signature
container checks и настоящий kernel ext4 mount. `udev`/sysusers/related shared
package отдельно pinned, отложены после actual postinst assertion в PRoot;
их scripts не обходились. Проверить configure внутри VM до G2.

Следом — guest ext4 uid/gid/chmod/symlink/hardlink/execute/rename/fsync и package
DB через **два boot**, потом Xorg/Openbox/xterm/software framebuffer/input. Старый
FAT сначала RO at /data, POSIX home на новом ext4; conversion in place/удаления и
автоматического reverse-sync нет. Main, legacy userdata, probe/kernel/terminal,
JIT/SideStore/MD export не менялись. Host VmHWM ~772MiB и late sampled RSS —
не guest/iOS memory: baseline1024MiB/4vCPU/256MiB TCG сохранён, Jetsam/desktop
fit не измерен. GUI/Steam/GL и Apple/device desktop gates остаются открытыми.

## Commandfix device PASS и следующий desktop milestone (docs-only)

Apple CI **6ad1efad7550aed8108f37fe — SUCCESS, 12m21s**, actual source
**190f87caa0aac16e81d20cd699bd54b5e9f4d8f9**. IPA **58868284**, SHA-256
**3e57c5c895afb41de51708458b12644725ccb040f8b0b9fb073bf9b57cd6edae**.
Это CI/artifact evidence от parent, не повторный download/hash этим executor.
Owner в **09:56 UTC**: «Все прекрасно сработало». Parent осмотрел screenshots:
**IDECK_TERMINAL_READY**, `ideck#`, реальный uname **Linux (none)
6.18.35-0-virt … Alpine … aarch64**, затем **ideck-test**, прежнего **[6n** нет.
Ручной one-file persistence между двумя boot, подтверждённый ранее, теперь
также пережил app update. Итого command links и canonical lineconsole fix
подтверждены на device. Raw screenshots/Library IDs в Git не внесены; автор
получил parent inspection summary, прямой visual inspection не заявляется.
Это не crash/power-loss durability, whole-disk audit, GUI/Steam/GPU PASS.
Smart quotes/safe-area/long-output UI backlog остаётся отдельно.

Новый evidence: `experiments/linux-guest/evidence/terminal-commandfix-device-pass.json`.
Предыдущие evidence с «device not yet tested» ниже — исторические receipts
до этого нового результата, их содержимое сохранено.

Следующий конкретный план: **[DESKTOP-MILESTONE.md](experiments/linux-guest/DESKTOP-MILESTONE.md)**.
Рекомендация: Debian13 arm64 glibc minbase, отдельный **ext4 rootfs**, сначала
**Xorg modesetting без glamor + Openbox/xterm** через прежний software framebuffer.
Не менять исходный kernel/machine/JIT/1024MiB/4vCPU/256MiBTCG без measured gate.
4GiB rootfs — экспериментальный budget, package footprint/memory fit не измерены.
Mesa/softwareGL — после первого 2D desktop; Steam/CEF/игры ещё дальше, без FPS
обещаний. Большой payload предлагается отдельным verified offline import, не
4GiB raw в каждой IPA. Конкретные direct packages, mount/VT/input/stop lifecycle,
размеры/free-space formula, network requirements и G0–G5 gates — в плане.

**Сохранение /data:** старый 128MiB FAT не конвертировать. В первом desktop
подключать RO по прежнему /data с uid1000 mapping, POSIX files — в /home/ideck
нового ext4. При последующей необходимости POSIX /data — verified copy import,
без удаления старого FAT и без заявления о reverse-sync при rollback.
Новые ext4 validators отдельно; не ослаблять existing FAT guards и lockfix.

Read-only inspection нашёл конкретные blockers: committed initramfs не содержит
ext4/jbd2/mbcache modules или ext4 builtin entry; нужно подтвердить config/mount,
затем exact same-kernel modloop closure. Terminal init ещё не грузит GPU/input/
evdev как probe. Для Xorg нужно доказать DRM KMS/VT, не только /dev/fb0.
Display bridge даёт left touch, probe UI только Send A: нужен настоящий desktop
keyboard/focus-release и проверенный pointer scope. Current executor uid1000/
capabilities0, без debootstrap/e2fsprogs/full-system QEMU — image builder не готов.
Transitive package lock, compressed size и реальный memory/Jetsam fit pending.

В этой задаче изменены только docs/evidence: payload не загружался, runtime,
userdata, network/security settings, ключи/подключения/оплата и main не менялись;
CI/новая IPA не запускались. Независимый design/documentation review завершён:
**без blockers**, JSON/source/SHA/diff checks PASS; подтверждены ровно четыре
docs/evidence изменения, desktop/Apple gates остаются будущей работой. Следующая implementation задача — G0/G1 POSIX storage,
потом G2 desktop, потом G3 Apple/device. Parent по-прежнему управляет CI/quota.

## Device two-boot persistence PASS; guest commands/plain-shell fix; UI transfer blocked

Новая задача реализации от pushed **e0bfdb9f674fbf2cb814f4b45fd57e1e88e44ad7**.
Owner/parent подтвердили настоящий interactive boot: **IDECK_TERMINAL_READY**,
`ideck#`, shell builtins смогли записать/прочитать `/data/check.txt` со значением
**ideck-test**. Затем lowercase `exit` дал **IDECK_TERMINAL_CLEAN_UNMOUNT** и
**reboot: Powerdown**. Новое сообщение owner **09:21 UTC**: «Перезапустил и
отправил команду». Parent осмотрел свежий bootlog/READY и повторный
`read -r line < /data/check.txt; echo $line` → **ideck-test**.

**Ручной persistence test одного файла между двумя boot — PASS** по явному
owner restart и parent screenshot inspection. Это не crash/power-loss durability,
не проверка всего диска/full Linux/Steam. Host fsync receipt здесь не получен.
Actual installed source/build из скриншотов автором не восстановлен. Старые
исторические UNKNOWN/evidence ниже сохранены; новый факт supersedes прежнее
«second boot not yet tested» только в пределах этого ручного sentinel test.

Оставшиеся баги: `cat: not found`, literal **[6n**, smart quotes и clipped output.
Команды проверены в **actual locked ARM64 BusyBox 1.37.0**, не по списку строк:
304 applets включая cat/uname есть, но links в минимальном initramfs отсутствуют,
а standalone lookup отключён. Теперь init ставит links **в RAM /run/ideck-bin**,
добавляет PATH в init/login и проверяет cat/uname до READY. `/data` не меняется;
seed остаётся побайтно прежним (**a09478ab12b7238eb929de5f3780f1107e6f9348821e68b74686690d32310552**).
Terminal asset/overlay locks пересчитаны по детерминированному suffix; исходные
kernel/probe initramfs, host flock/lockfix, JIT/SideStore/diagnostics не изменены.

Для plain line console **TERM=dumb недостаточно**: actual ash -i на PTY испускает
ESC[6n. Вместо неподдерживаемых emacs/noediting options login теперь вызывает
**stty icanon isig icrnl -igncr -inlcr -echo -echonl** перед настоящим `ash -i`.
Так compiled BusyBox выбирает plain canonical/noecho input path, сохраняя реальный
shell, controlling tty и Ctrl-C/Ctrl-D. Host CR Send превращается в newline.
Редактирование — в app command field; guest echo/Tab completion/vi redraw нет.
Никакого eval-loop вместо shell или отключения shutdown protocol.

Actual ARM64 regression **PASS**: locked archive/initramfs digest → BusyBox/musl
→ QEMU user-mode → 304 applets → install links → executable cat/uname и ash PATH
lookup. PTY сначала воспроизводит старый ESC[6n, затем проверяет canonical/noecho:
CR submit, read state, Ctrl-C прерывает pending builtin read и возвращает prompt,
exit и Ctrl-D без ESC. External foreground process signal delivery не проверен. Новый offline tool
`experiments/linux-guest/tools/check_terminal_busybox.py <existing-qemu-aarch64>`
ничего не скачивает и userdata не открывает. Это user-mode/host PTY check,
**не guest kernel boot / iOS UI test**. Suite с IDECK_QEMU_AARCH64: **152 tests
PASS (6.538 s)**; sh -n и diff check PASS. Независимый reviewer повторил
152 tests с actual ARM64 check: PASS, все 22 overlay hashes совпали; blockers нет.
Усиленный pending-read Ctrl-C test дополнительно прошёл actual tool.

**UI пока заблокирован, UI-код не изменён.** Parent потребовал сначала перенести
и осмотреть исходные скриншоты в этом executor. Standard Library helper для всех
трёх файлов даёт **download failed / OSError: Tunnel connection failed:
403 Forbidden**, включая fresh transfers и повтор с network permission.
Обхода, подмены скриншотов summary или заявления о визуальном осмотре нет.
Запрошены уже материализованные доступные local paths. После их получения:
explicit smartQuotes/smartDashes/capitalization/correction off; narrow safe-area
layout/readable long output и подходящие controls для canonical line console.
Library IDs/raw screenshots/private transfer URLs в Git не внесены.

Новый evidence: `experiments/linux-guest/evidence/terminal-commands-lineconsole.json`.
**CI не запускался**, IPA этого guest fix не собрана; parent управляет единственной
сборкой/quota/payment. Перед финальной IPA желательно завершить UI после transfer
unblock. На device новых scripts ещё проверить cat/uname, quotes/ввод, line output,
clean Stop и сохранность существующего sentinel после relaunch без reset disk.

## Userdata byte-100 lock: конкретная Darwin-причина и terminal-only fix

Новая реализация от pushed **`224f5f7d08280598a3e006c92f60e7247b9941d8`**.
Parent передал точную последнюю строку native snapshot **1644 bytes** из
установленной **eed2a5eda400056c1550d6588662e4186e5cf00c**, build **119**:

```text
qemu-system-aarch64: -drive if=none,id=userdata,format=raw,cache=writethrough,file=<APP>/Documents/iDeckLinux/userdata.raw: Failed to lock byte 100.
```

Raw private log/Library ID/attempt UUID в Git не добавлены. До этой строки JIT
self-test PASS (generated code 42), dual mapping 512 MiB, debugger detached,
audio driver registered. Native time **13:14:53.125 local**, JIT elapsed ~5082 ms;
согласующийся MD начинает **08:14:54 UTC**, final **qemuInitBegin 08:14:57.600 UTC**.
Association остаётся **UNKNOWN**: это rotating previous-launch candidate,
хронология согласуется, но identity не доказана. Два других MD на той же границе
не доказывают одинаковую причину; ещё один заканчивается JIT claim без VM.
Исторические evidence ниже сохранены, их UNKNOWN не переписан как proven.

В exact pinned QEMU **10.0.12-utm** `locking=auto` проверяет **F_OFD_GETLK на
/dev/null** и выбирает OFD. `raw_apply_lock_bytes` пытается взять **F_RDLCK** на
byte **100**. Apple XNU направляет и whole-file `flock`, и OFD byte locks в общую
проверку перекрытия: наш уже удерживаемый **LOCK_EX** на другом fileglob мешает
этому read lock. Exact message без strerror согласуется с QEMU-веткой, которая
скрывает suffix только при EAGAIN/EACCES. Это конкретная причина explicit disk
open failure в полученном native log, а не установленный signal/crash type для
всех попыток. Ранее высказанное source-only предположение «Darwin обязательно
отключает auto locking» неверно; Linux-разделение flock/OFD сюда не переносится.
Public Apple XNU source подтверждает механизм, но не объявляется exact kernel
revision установленной iOS. URL/hash исходников и цепочка есть в новом evidence.

Исправление: только terminal userdata получает **`file.locking=off`**, точный
protocol-child option, проверенный по pinned `drive_new` → QDict → `file.` child
→ file-posix parser. Прежний **exclusive nonblocking flock НА userdata.raw**
остаётся от validated open до process exit, в том числе после clean stop;
`synchronize()` не отпускает его. QEMU продолжает I/O через свой descriptor,
повторный конфликтующий byte lock убран. Probe/JIT/SideStore/MD export сохранены.

`arguments` теперь требует живой **LinuxTerminalDisk**, URL-only bypass удалён.
До assets/session и повторно перед native entry проверяются active fd, LOCK_EX,
fstat/lstat same dev/inode, regular file, single link, 128 MiB и прежние directory
guards. Closed/unlinked/replaced token прекращает запуск до C со статическим
**diskOwnership**. Никакого reset/reseed/delete user disk. Защита advisory:
она исключает cooperating app writers, не произвольное внешнее изменение файла;
pathname open QEMU не стал atomic against hostile concurrent replacement.
Сохраняется прежняя trust model app-owned private Documents directory.

Добавлены Apple host regressions: настоящий OFD byte100 conflict/success after
release; same-process и 3 independent processes до/после sync; release/reopen
с сохранением sentinel; закрытый token до session creation; same-size inode
replacement, unlink, symlink, hardlink и truncate; only userdata argv override.
Они подключены к существующему mac-tests gate, **локально ещё не выполнены**.
Manual safe native summary распознаёт exact byte100 failure фиксированной
KNOWN ERROR подписью, сохраняя UNKNOWN association и privacy guards.

Локально: **150 Python tests PASS (14.330 s)**, compiled actual Swift diagnostics
helper **PASS** с exact signature/privacy регрессией; Swift parse changed files
**PASS**. Apple SDK отсутствует: Darwin runtime tests/full typecheck/IPA/device
fix ещё не проверены. Независимый review финального diff: **без blockers**; reviewer повторил
150 tests PASS (17.204 s), actual Swift diagnostics PASS, syntax/diff checks
PASS, все 22 overlay hashes совпали. Pinned QEMU option routing подтверждён
независимо. Darwin struct/fcntl проверены по source, SDK execution ещё pending.
Новый evidence: `experiments/linux-guest/evidence/terminal-userdata-lock-fix.json`.
CI **не запускался**, parent единолично управляет сборкой/quota/payment;
main не менять. Следующий acceptance: Apple gates → IPA → qemuInitReturned →
terminal/input/control ready → /data sentinel → orderly stop → app reopen и
второй guest boot с чтением того же sentinel. Старый userdata сохранять.

## Device journal получен: native snapshots доступны через Files; добавлен manual safe export

Parent передал содержание device diagnostic MD (**3514 bytes**) от установленной
**`eed2a5eda400056c1550d6588662e4186e5cf00c`**, build **119**. Это подтверждает
установку/исполнение диагностической версии, а не только source stage из
следующего исторического раздела. Journal intact; final checkpoint
**`qemuInitBegin`**, **2026-10-16T08:14:10.244Z**, elapsed **11025 ms**.
JIT claim/readiness/execution, runtime ownership и все host preparation phases
вернулись. `qemuInitReturned` и clean stop не записаны. Native stderr snapshot
**1644 bytes**, app log snapshot **5840 bytes** доступны отдельно; association
остаётся **UNKNOWN**. Автор этой записи получил parent summary, не raw native
bytes. **Причина выхода/вылета ещё не установлена.** Между qemuInitBegin и C
call есть host handoff/report write; один checkpoint не доказывает упавшую
инструкцию или exception type.

### Забрать snapshots из УЖЕ установленной IPA, без Start/JIT/новой сборки

В pinned Husk `src/app/Husk/Info.plist` включены **UIFileSharingEnabled=true**
и **LSSupportsOpeningDocumentsInPlace=true**. Packager меняет display name на
**iDeck Linux Probe**, сохраняя эти flags. Это проверка source/build recipe;
actual Files UI SideStore-копии автором не управлялся. Встроенный EED menu
пока экспортирует только checkpoint MD; raw native export button там нет.

1. **Файлы → Обзор → На моём iPhone → iDeck Linux Probe** (папка может
   отображаться под именем подписанной копии/Husk) → **iDeckDiagnostics**.
2. Взять значение **Attempt** из уже полученного MD. Нужны только два файла
   **attempt-<Attempt>.native.txt** (**1644 bytes**) и
   **attempt-<Attempt>.app.txt** (**5840 bytes**), с тем же stem.
3. Долгое нажатие → **Поделиться**, либо **скопировать**, не перемещать/удалять.
   Просмотреть raw text на private content перед ручной передачей. Pairing
   records и весь Documents не нужны. Не нажимать Start, не включать JIT,
   не reinstall/uninstall и не трогать userdata/journal ради экспорта.

Если папка не показывается в Files, те же Documents доступны через существующий
File Sharing приложения в Finder/Apple Devices на компьютере: сохранить
**iDeckDiagnostics** отдельно. Это альтернатива чтения существующих файлов,
не новая VM attempt. Snapshot capture receipt сохраняет уже скопированные
файлы; повторный запуск не должен заменять их свежими rotating logs.

### Новый source: explicit manual native summary для следующей сборки

В **Startup diagnostics (.md)** рядом с каждой попыткой добавлена кнопка
**Native log summary N (.md)**. Она читает только сохранённые `.native.txt` /
`.app.txt` выбранной попытки, без JIT/VM, journal append, recapture или подстановки
текущих/rotating logs. Export — отдельный atomic/synced `attempt-<id>.native.md`;
исходные raw bytes, journal и старый checkpoint Markdown остаются неизменными.

General regex redaction произвольного native text не гарантирует отсутствие
секретов, поэтому экспортируются только **фиксированные подписи распознанных
диагностических строк** (JIT allocation/prewarm, socket fd/chardev, file/lock,
assertion/fatal-signal/display text). Matched substrings/captures/values, адреса,
пути, команды, unknown lines и credentials в MD не копируются. Есть счётчик
omitted lines; `NONE RECOGNIZED` не означает отсутствие ошибки. Association и
cause остаются UNKNOWN; signature presence не является crash attribution.
Автоотправки нет. Для полного текста ТЕКУЩИХ snapshots использовать Files выше,
не ждать новой IPA и не запускать VM повторно.

Проверка: **148 Python tests PASS, 9.360 s**, exit 0. Actual Swift 6.2.1 helper
с новыми native-summary regressions: **PASS**, run **0.142 s**. Проверены
same-line token/path/Markdown injection при recognized signature, unknown/
invalid UTF8/long lines, repeated export с побайтным сохранением raw/journal/
checkpoint MD, absent snapshot без rotating fallback, symlink и oversized read
failures без partial publication. Независимый reviewer пересобрал/исполнил
latest helper: PASS; блокирующих замечаний нет. Session/View Swift parse PASS;
Apple SDK/UI/device нового export ещё не проверены. Все **22 overlay hashes**
проверены, прежние runtime/argv/JIT/disk guards и evidence сохранены.

Дополнительная pinned source review: default ROM не задан ни у virtio-blk-pci,
ни у virtio-serial-pci; прежняя Husk PXE ROM ошибка относилась к отключённому
`-nic none` network device. QEMU сам резервирует port 0 и выбирает следующий
для virtserialport. Эти гипотезы не дают основания менять argv. Native logs
1644/5840 bytes либо IPS остаются следующим решающим evidence.

Новый evidence: `experiments/linux-guest/evidence/terminal-native-log-export.json`.
Source base — **eed2a5eda400056c1550d6588662e4186e5cf00c**; новый commit/push
содержит manual export и тесты. CI не запускался; новый IPA для этого UI не
собран. Parent координирует CI, main не меняется. Текущий приоритет — получить
существующие snapshots через Files, затем исправлять подтверждённую причину.

## Диагностическая версия startup: журнал/relaunch/Markdown готовы к Apple build

Новая задача реализации от **`68c80dcdc8fee85a00fc2f16ca4bfc7ee77b7b19`**:
owner попросил версию с crash log для немедленного вылета terminal Start с JIT.
Причина вылета установленной IPA source `46582b44b577651679155efe60c56256496415b8`
**остаётся неизвестной**. Ниже реализована диагностика, а не доказанное исправление
этого вылета. Новый IPA ещё не собран; CI запускает только parent после свежих
quota >=120 free / paid off / private repository / exact SHA checks.

`LinuxTerminalDiagnostics.swift` — отдельный Foundation/POSIX helper. В
`Documents/iDeckDiagnostics` каждой диагностической попытке даётся новый
append-only `attempt-<time>-<UUID>.jsonl`; прежние попытки не переписываются и
не удаляются. NSLock сериализует main/worker/QEMU записи, каждый checkpoint
записывается синхронно с **fsync до возврата**. Journal ограничен 128 KiB /
256 records; reader использует только полный корректный prefix, отмечает torn
final record/corruption, отвергает symlinks/hardlinks/non-regular files. Reads
nonblocking, чтобы FIFO не подвесил UI. Это сохранение после выхода процесса,
не обещание пережить аппаратную потерю питания или поймать любой сигнал.

Checkpoints стоят до/после JIT claim/execution/ownership, Documents, assets,
disk validation/provision, sockets, argv/session, report, thread startup,
`qemu_init`, native JIT check, display init и main loop; также ready/Stop/
guest unmount/host sync/clean-stop и failures/timeouts. **qemuInitReturned теперь
пишется прямо на QEMU thread до display init**, независимо от async result.json.
До входа в C сбой записи останавливает запуск и закрывает только unused
endpoints/disk. После входа диагностическая ошибка показывается в UI, не
разрушает runtime и не снимает disk lock. Известные validation enums имеют
статические коды, arbitrary error.localizedDescription в journal не попадает.

Recovery выполняется на root chooser и terminal screen до нового Start; он
не запускает JIT/VM, не открывает userdata и не создаёт новую попытку.
Terminal screen больше не prewarm-ит JIT просто для чтения/export reports:
Enable/attach/Start сохраняют обычные execution gates с checkpoints.
UI **Startup diagnostics (.md)** доступен без VM/JIT. Показываются текущая и
до 8 последних предыдущих попыток; более старые файлы остаются на диске.
Незавершённый previous process обозначается как interrupted/unconfirmed с
последним сохранённым checkpoint, **без guessed cause**. Clean-stop требует
journal receipts guest unmount + QEMU loop return + host disk sync; lone clean
marker PASS не даёт. Это не device two-boot persistence proof.

Существующий Husk stderr capture сохраняется. При первом recovery bounded
snapshots `husk-native-prev.log`/`husk-prev.log` (до 1 MiB каждый) сохраняются
локально отдельно. Capture receipt не позволяет дополнять отсутствующие logs
текстом другого последующего запуска; association явно UNKNOWN. Raw snapshots
могут содержать private text/paths и **не включаются в Markdown/автоотправку**.
Markdown содержит только enum checkpoints, UTC/elapsed, validated build/SHA,
known errors и наличие/размер snapshots; исключены argv, commands/transcript,
личные paths, pairing data/tokens и arbitrary native text. Новых signal/crash
handlers нет, системные IPS/Jetsam через sandbox не обещаются.

Проверено локально:

- **147 Python tests PASS, 6.545 s**, exit 0: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s experiments/linux-guest/tests -q`.
- **Actual Swift 6.2.1 Linux helper compile + execution PASS**, run 0.236 s,
  marker `LINUX_TERMINAL_DIAGNOSTICS_CHECKS_PASS`. Реальный child пишет checkpoint
  и вызывает `_exit(23)` без Swift destructors, parent/relaunch восстанавливает
  его и экспортирует MD. Проверены torn/malformed/oversized records, clean vs
  interrupted/rejected/JIT-only, concurrency, fsync failure, bounded FIFO child
  regressions, symlink rejection, privacy и first-capture preservation.
- Swift parser проверил Session/View/Root syntax. Это **не Apple SDK typecheck**.
  Linux helper использует реальный Glibc/POSIX/Foundation; Apple Darwin branch
  и полный app typecheck/link/device проверит существующий CI gate, куда
  подключены тот же helper и реальные Swift tests.
- Независимый reviewer повторно собрал/исполнил actual helper: PASS; блокирующих
  замечаний после исправления FIFO/pre-entry failure/capture association нет.
- Все **22 overlay input hashes / 12 copies** проверены. Все **43 прежних
  evidence snapshots** и 12 protected runtime/native/guest/CI files побайтно
  сохранены; probe payload, JIT native code, original MD renderer, userdata
  guards/locks и quota/request gates не менялись. Новый evidence:
  `experiments/linux-guest/evidence/terminal-startup-diagnostics.json`.

Инструкция после parent build/install диагностической IPA:

1. Открыть Linux terminal, Enable JIT, нажать Start terminal один раз.
2. После вылета открыть приложение снова. **Не запускать VM повторно**:
   выбрать Linux terminal → **Startup diagnostics (.md)** → при необходимости
   **Refresh saved startup reports** → **Saved startup report 1 (.md)** и
   передать этот Markdown вручную. Export не требует JIT.
3. Сохранить original IPS/Jetsam, если iOS его создала. Для неизвестной native
   ошибки parent может отдельно запросить локальные snapshots/оригинальные
   logs; проверять их на private content перед ручной передачей. Ничего не
   загружается автоматически. Диск Documents/iDeckLinux/userdata.raw не
   удалять/не reset и приложение не uninstall ради диагностики.

Source готов к parent-controlled Apple build **нового полного pushed SHA**.
Не проверены: Apple compilation/typecheck/link/package этой версии, survival
после actual device crash/Jetsam, новый diagnostic export на iPhone, terminal
readiness/Stop/two-process persistence. Готовой новой диагностической IPA и
подтверждённой причины прежнего crash пока нет; main не изменялся.

## Текущий device blocker: немедленный вылет при Start console с JIT

Owner через parent подтвердил: terminal IPA source
**`46582b44b577651679155efe60c56256496415b8`** установлена через **SideStore**
на **iPhone 16 Pro Max / iOS 27**, но приложение немедленно вылетает при Start
console с включённым JIT. Значит прежний download/install pending уже не текущий
статус. **Terminal readiness и persistence не пройдены.** Предыдущий device
probe на `660e27e515f666040a5959fa845fe85b3290a740` остаётся отдельным PASS.
Crash/IPS или JetsamEvent запрошен parent у владельца; здесь ещё не получен.

Диагностика проведена от чистого remote
`457b95305c8eefa61ffee8ae0420ed733bb35db1`, без переноса старых WIP. Сравнены
current terminal/probe, exact pinned Husk native bridge и QEMU 10.0.12-utm.
Размер/SHA-256 QEMU archive проверены по native lock; полученные Husk native
файлы/patches проверены Git-blob SHA против дерева pin. Независимый reviewer
проверил startup/FD/callbacks и native socket paths. Проверенные findings:

- JIT prewarm, guest RAM 1024 MiB, TCG 256 MiB, stack 16 MiB, thread QoS,
  argv lifetime и `qemu_init → husk_display_init → qemu_main_loop` совпадают
  с probe. Это source comparison, не новое device исполнение.
- QEMU принимает `socket,fd=N,server=off` для connected AF_UNIX socketpair;
  этот fd-path не делает повторный connect/listen. Оснований переключать
  `server=on` или заменять socketpair нет.
- `cache=writethrough` использует buffered file I/O; `locking=auto` включает
  QEMU locks при наличии OFD support. Конфликт с host disk flock не установлен;
  ослаблять lock/no-clobber/format guards оснований нет.
- Pinned `husk_display_init()` регистрирует QEMU display listener без MTKView;
  явной зависимости от отсутствующего в terminal screen view не найдено.
- Swift preparation errors перехватываются, но worker catch теряет конкретную
  ошибку. Это диагностический недостаток, **не доказанная причина вылета**.
  Native `exit/abort/signal` из qemu_init Swift catch не перехватывает.

Нужны существующие **Documents/husk-native.log, husk-native-prev.log, husk.log,
husk-prev.log** и последний **iDeckLinuxSessions/<UUID>/result.json** с
**linux-serial.log**. Сохранить до нескольких новых app launches: логи ротируются.
`terminal_prepared` подтверждает завершение подготовки, но отсутствие
`qemu_init_returned` **не доказывает падение внутри qemu_init**: flag ставится
после display init и async queue write. Нужны native last lines/stack.
Normal QEMU exit может не оставить IPS; поэтому native stderr нужен отдельно.

IPS: timestamp/app version/build, Exception Type/Codes, Termination Reason,
Triggered by Thread/faultingThread, полный frames упавшего потока, Application
Specific Information/asi, lastExceptionBacktrace, Binary Images/usedImages
(UUID, base, imageOffset), OS build. JetsamEvent: запись iDeck/Husk с reason,
rpages/lifetimeMax, pageSize, footprint и memory-pressure context. Лучше полный
исходный файл; raw device logs/контейнерные пути/личные данные не добавлять в Git.

Подтверждённой причины или обоснованного runtime-fix пока нет. Новый snapshot:
`experiments/linux-guest/evidence/terminal-startup-device-blocker.json`.
В этой диагностической сессии только HANDOFF/evidence; runtime и данные диска,
probe/JIT/MD export, guards/locks не менялись. Новые CI, IPA, Apple/guest/device
runs не выполнялись. Следующий шаг — сопоставить owner native logs/IPS/Jetsam
с startup границами, затем исправлять доказанную причину и передавать parent
точный source SHA для единственной координируемой им CI.

## Terminal IPA: Apple build SUCCESS на 46582b44, device gate ещё не пройден

Parent передал результат Apple build
[`6ad1bdf03ffd2c7f0ad3d38c`](https://codemagic.io/app/6ad03ce9a8a969b53f3a4aa9/build/6ad1bdf03ffd2c7f0ad3d38c)
для **`46582b44b577651679155efe60c56256496415b8`**: **SUCCESS**, длительность
**10m54s**, `runtime_linked=true`, `LINUX_TERMINAL_HOST_CHECKS_PASS`.
Исправление asset paths прошло Apple host gate; terminal IPA действительно
собрана. Следующие исторические разделы описывают состояние до этого запуска;
их прежние «IPA отсутствует / Apple gate pending» больше не являются текущим
статусом. Этот docs-only update не меняет SHA собранной IPA.

Actual IPA: **58 819 622 bytes**, SHA-256
**`9ca755651657a5a5f0ce0b1c913b53460764820dd71b723455875de942267855`**.
По переданному независимому аудиту actual IPA: **7 ARM64 iOS Mach-O**, все
**4 terminal files** совпадают с lock, **128 MiB FAT16 seed** корректен,
original probe побайтно сохранён, Markdown export присутствует для обоих режимов.
Автор этой записи не скачивал и не пересчитывал IPA самостоятельно: build,
размер/hash и выводы independent actual-IPA audit получены от parent. Новый
snapshot: `experiments/linux-guest/evidence/terminal-ipa-success.json`.

IPA загружена в private Drive. Пользователь устраняет **404 при скачивании**;
успешное скачивание и установка ещё не подтверждены. Private URLs/IDs в Git не
добавляются. **Device terminal/persistence пока не проверены**: нет приёмки
команд в terminal, foreground orderly Stop и exact-file `/data` persistence
после fresh app process. Ранее пройденный device probe не подменяет этот gate.
Следующий шаг — восстановить доступ к уже собранной IPA, затем обычный owner
sideload и `experiments/linux-guest/docs/terminal-device-check.md`.

В этой сессии изменяются только HANDOFF и новый evidence snapshot; runtime,
fixtures, locks и прежние evidence остаются неизменными. Новый CI не запускается.
Предыдущие docs-запросы получили UNKNOWN и не были запущены; этот update
фиксируется и отправляется отдельно в ту же рабочую ветку. Main не изменяется.

## mac-tests Invalid.asset после profile-disk-open: исправление asset paths

Задание реализации от 2026-10-16, база **`04cde5f8a296e57305d3ebfe91b1ec790ea90fc0`**.
Remote рабочей ветки перед изменениями точно совпал с этой базой. Создан чистый
checkout от pushed HEAD; старый WIP и ограничения исторического read-only аудита
не переносились. Применимых `AGENTS.md`/`.agents/skills` в checkout нет.

Пользователь сообщил Apple build
[`6ad1b6843ffd2c7f0ad3d211`](https://codemagic.io/app/6ad03ce9a8a969b53f3a4aa9/build/6ad1b6843ffd2c7f0ad3d211):
iOS typecheck/native syntax/mac-compile PASS, disk-first-open/reopen/rejection
пройдены, затем после `profile-disk-open` mac-tests exit -5 с
`LinuxTerminalProfile.Invalid.asset`. Это переданный результат; полный raw log
и actual checkout receipt в этой сессии независимо не получены.

В `checked(seed)` оставалось сравнение **полных Foundation URL**:
`file.resolvingSymlinksInPath().deletingLastPathComponent() == root`.
Terminal fixture создаёт URL будущего каталога без directory hint; ранее
прошедший `main.swift` fixture задаёт `isDirectory: true`. URL representations
могут различаться завершающим slash и Apple alias normalization, хотя путь
указывает на один каталог. Аналогичный guard найден в `LinuxGuestProfile`.
Это source-localized дефект; точный старый Darwin subguard без исполнения нового
Apple gate не объявляется доказанным. Seed fixture не меняет размер/формат:
manifest теперь считается от actual bundled copy с отдельной проверкой digest
исходного seed.

Оба validator используют общий POSIX `realpath` для asset root и проверяют
точное canonical имя разрешённого файла. Leaf symlink/type, filename whitelist,
metadata size, actual byte count и SHA-256 guards сохранены; причины разделены
статическими `assetDescriptor/Directory/Inspection/Type/Size/Containment/Read/
ContentSize/Digest` errors, kernel agreement — `assetKernelMismatch`. Пути в
новые error labels не попадают. Disk validation/provision/lock/no-clobber,
production FAT16 seed, JIT/SideStore, original probe и MD export сохранены.

В Apple helper tests добавлены полноценные terminal openDisk/argv и probe
asset checks для **обоих directory hints** и `/var/tmp` alias независимо от
TMPDIR. Negative tests требуют exact typed guard при same-size corruption,
внутренних/внешних leaf symlinks, wrong seed digest/name, и проверяют отсутствие
нового userdata/session. Старые disk/layout/reopen/control/report checks остаются.
Эти Swift tests написаны и уже подключены к существующему gate; **здесь не
исполнялись**, Swift compiler и Apple SDK отсутствуют.

Локально **143 Python tests PASS, 5.725 s**, exit 0:
`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s experiments/linux-guest/tests -q`.
Независимый reviewer: блокирующих source замечаний нет; отдельно **143 tests
PASS, 5.830 s**, diff check PASS. Все **21 overlay input hashes** проверены;
обновлены только два соответствующих runtime Swift hashes. Все **40 прежних
evidence snapshots** и 14 protected CI/native/probe/terminal/JIT/MD files
побайтно сохранены. Новый evidence:
`experiments/linux-guest/evidence/terminal-asset-path-fix.json`.

**CI в этой сессии не запускался** по прямому указанию пользователя: parent
управляет одной сборкой и quota/payment checks. Новый terminal IPA отсутствует;
Apple Swift gate/native link/package, terminal commands/foreground orderly Stop
и exact-file `/data` persistence после fresh app process пока не проверены.
Следующий шаг — parent-controlled Apple build полного **нового pushed SHA**,
после успешной упаковки — `docs/terminal-device-check.md`. Main не изменять.
Полный итоговый remote SHA координатор сообщает после commit/push; это не старый
expected SHA и не обещание готовой IPA. Оплата/ключи/подключения не создавались.

## Второй mac-tests Invalid.disk: filesystem path validation

Parent сообщил [build 6ad1a9933ffd2c7f0ad3cfc8](https://codemagic.io/app/6ad03ce9a8a969b53f3a4aa9/build/6ad1a9933ffd2c7f0ad3cfc8)
после source revision `512aa6e9d7f41e70f0d8c0d9d94b0de970b80fc4`: checkpoints
`seed-layout` и `appended-header-regression` пройдены, затем mac-tests падает
на `disk-first-open` с `LinuxTerminalProfile.Invalid.disk`. Это parent-reported
log findings; полный raw log/result.json/actual checkout receipt автором записи
не получены. Native/app build из этого source-check stage не достигнуты;
ошибок линкера и нового terminal IPA этим не подтверждено.

Подтверждён portability defect: Foundation URL normalization использовался как
строгая filesystem canonicalization. Это шире одного equality guard:
`standardizedFileURL` и Foundation symlink resolution могут убирать системный
`/private` prefix, а последующий ancestor lstat может встретить alias/symlink.
**Actual temp/Documents path failing CI не получен**, поэтому конкретный alias
или единственный throwing guard по этим checkpoints не установлен. CI
настраивает TMPDIR под worker output; нельзя выдавать пример `/var` alias за
прочитанное фактическое окружение.

Реализована проверка trusted root через POSIX realpath, проверка исходных raw path
components через lstat и повторная POSIX-проверка после создания каталога.
Trusted Documents call site обновлён; production disk size/BPB, no-follow,
lock/no-clobber и запрет destructive reset сохранены. Именованные
ошибки различают остальные возможные first-open failures без private path dump. Старый negative
appended-header test мог принять любой `Invalid.disk` из directory guard как
нужный отказ seed-size; новый regression требует `diskSeedSize` failure и
отдельно подтверждает positive path checks. Base-relative URL и dot/dot-dot
components отклоняются, symlink ancestors не скрываются нормализацией.

**Source fix проверен локально и готов к Apple rerun**: root full suite
**142 Python tests PASS, 4.917 s**, exit 0; команда
`PYTHONDONTWRITEBYTECODE=1 TMPDIR=/workspace/iDeck/.work python3 -m unittest discover -s experiments/linux-guest/tests -q`.
Это Python source/staging/resource validation, не исполнение Swift/Foundation
на Mac. Frozen Profile/Session/Swift tests hashes и overlay проверены;
overlay SHA-256 `b6ca36b66827fa24a60434f91351b7e8152e5b3e059115801b87f335998219cd`.
Все 21 overlay inputs valid; изменились только два existing runtime Swift hashes,
copy mapping/upstream patched bytes прежние. Root подтвердил: все 39 prior
evidence snapshots побайтно сохранены; Codemagic/build worker/request gate,
native/guest locks и payloads не менялись; diff check PASS. Локального
Swift/QEMU исполнения, Apple rerun и device persistence проверки нет.
Точный старый throwing guard остаётся недоказанным; новый named error поможет
локализовать повторный отказ, если он возникнет. Исторические sections/snapshots
сохраняются; новый evidence:
`experiments/linux-guest/evidence/terminal-disk-path-fix.json`.

Для следующего запуска использовать полный pushed SHA исправления.
Только parent выполняет отдельно авторизованный Apple rerun с прежними
request/quota gates. Новый terminal IPA/mac-tests/device persistence PASS
объявлять только после фактического результата.

## Apple gate: исправление sparse FAT16 fixture в mac-tests

Parent сообщил отказ [build 6ad1a04a3ffd2c7f0ad3ce47](https://codemagic.io/app/6ad03ce9a8a969b53f3a4aa9/build/6ad1a04a3ffd2c7f0ad3ce47):
iOS typecheck и Mac compilation прошли, затем **mac-tests exit -5** с
`Swift/ErrorType.swift:254` и `main.LinuxTerminalProfile.Invalid.disk`.
Parent связывает запуск с `f1d3bd1912f4d17a2ff6476fff05f55d6b97c432`;
actual checkout receipt/full result.json независимо не получены. Это переданный
parent результат/raw-log finding; автор этой записи сам raw log не читал. Отказ произошёл в Foundation helper tests до native/app build;
нового app-link/IPA результата для terminal stage нет.

Причина подтверждена source review и сообщённым parent Apple API contract:
`TerminalChecks.swift.makeSeed` после `FileHandle.truncate(atOffset: 134217728)`
не возвращал cursor к началу. Следующий 512-byte boot-sector write шёл в EOF:
fixture становился **134218240 bytes**, а BPB/signature на offset 0 оставались
нулевыми. Production provision correctly отклоняет `count > 134217728` уже
при первом open; ослаблять disk guard, менять production FAT16 seed или runtime
не требуется. Native owner независимо сравнил BPB offsets 11/19/32/54/510 с
actual prepared seed: при правильном размещении header согласован.
Primary API: [Apple FileHandle.truncate(atOffset:)](https://developer.apple.com/documentation/foundation/filehandle/truncate%28atoffset%3A%29).

Fixture-only explicit seek(0) реализован; добавлены offset/size/BPB/last-byte
EOF assertions и real Foundation regression старого layout с typed catch только
`Invalid.disk` и проверкой отсутствия published userdata. Fixed stderr checkpoints
не печатают пути. Source SHA-256
`d584f5de8fc0cc9d7b7e71f1562c1390a447cc0eb425c2000261d52021a504e4`;
исходник fixture проверен и **готов к Apple rerun**. Root full suite:
**141 Python tests PASS, 4.891 s**, exit 0; команда
`PYTHONDONTWRITEBYTECODE=1 TMPDIR=/workspace/iDeck/.work python3 -m unittest discover -s experiments/linux-guest/tests -q`.
Новый Python source guard отвергает old f1d3 fixture и принимает corrected source
через `Path.read_text` mock; это не выполнение Swift/Foundation API.
Root подтвердил: остальные tracked production/runtime/CI/locks не изменены,
все 38 base evidence snapshots побайтно сохранены, все 21 overlay input hashes
соответствуют прежнему lock; diff check PASS. Здесь Swift/QEMU не
устанавливались и не запускались; fix ещё не прошёл новый Apple gate.
Probe/terminal payloads, native pins и старые evidence snapshots сохраняются.
Новые CI/IPA/device actions этой документацией не выполняются. Evidence:
`experiments/linux-guest/evidence/terminal-mac-fixture-fix.json`.

Исправление фиксируется отдельным коммитом в рабочей ветке. Для следующего
запуска использовать его полный pushed SHA; только parent запускает отдельно
авторизованный Apple rerun с прежними request/quota checks. До фактического результата не объявлять
mac-tests/terminal IPA/device two-boot persistence успешными.

## Новый этап: local terminal и файл после orderly stop / следующего запуска

Работа начинается от `28d862fd4fcddd9421688756e6fa1e5cea7021fb`. Авторизован
отдельный real BusyBox ash с controlling TTY через getty/ttyAMA0 и local **line console** с сохранением
user file после orderly stop и fresh app process. TERM=dumb, без обещания full
VT/full-screen terminal apps. **Это source stage, не новый device PASS.**
Прежний принятый probe остаётся отдельным режимом; original kernel/initramfs/
profile/archive/locks, native pins, JIT и Markdown не заменяются.

Архитектура: два local AF_UNIX socket pairs — console и независимый fixed
virtio-control `IDECK_STOP_V1` на `org.ideck.control`. PID1 останавливает children,
делает sync/unmount/poweroff; app считает остановку чистой только после
`IDECK_TERMINAL_CLEAN_UNMOUNT`, QEMU return и host
userdata fsync. Одна VM на процесс; после stop закрыть/открыть приложение,
без unsafe in-process restart. Networking/Steam не добавляются.
Disk lock сохраняется до выхода app даже после orderly stop: возврат main loop
не доказывает полный QEMU block-layer drain. Report сохраняет
`qemu_block_layer_drained_verified=false`; полного runtime teardown не заявляем.
Guest shell не наследует control fd3; текст в console сам по себе не является
подтверждением clean unmount. Таймаут/потеря канала также не дают clean PASS.
Startup 60 s / Stop 30 s — reporting timeouts без force shutdown/clean PASS;
явный guest STOP_FAILED сохраняет failure. Serial EOF сам по себе не отключает
независимый Stop. Terminal elapsed включает disk prep, init, работу и Stop;
это не boot benchmark и не прежний probe post-init interval.

Новый deterministic **128 MiB FAT16 seed** копируется только при отсутствии
`Documents/iDeckLinux/userdata.raw`. Только **/data** persistent, не весь rootfs.
Existing disk не форматируется/не сбрасывается после mount error; изменённый
userdata не обязан совпадать с seed hash. FAT16 не обещает POSIX permissions,
symlinks или persistence после uninstall/reset/unclean kill. Приёмка:
unpredictable nonsecret file → foreground command → app Stop через независимый
control → все clean-stop условия → fresh process → exact read same file.
План: `experiments/linux-guest/docs/terminal-device-check.md`.

Baseline initramfs проверен read-only в памяти: kernel 6.18.35-0-virt,
BusyBox 1.37.0 AArch64 с musl loader; exact musl version не определена.
virtio_blk/FAT/VFAT доступны как существующие **loadable modules**.
`modules.builtin` отдельно подтверждает встроенные virtio_console/virtio/
virtio_ring/virtio_pci. Новая terminal library не требуется. GPL notices/source pins
сохранять; source fetch 403 и неполный corresponding-source/musl audit фиксируются
как ограничение, это не license-compliance certification. Primary BusyBox
license: [официальная страница](https://busybox.net/license.html).

Подготовлены `guest/ideck-terminal-init`, `ideck-terminal-login`,
`tools/terminal_bundle.py`, `ipa/terminal.lock.json`, provenance NOTICE и три
Swift source `LinuxTerminalProfile/Session/View`. Новый deterministic CPIO suffix
содержит только init/login, kernel reused из original validated probe; отдельные
terminal-profile/initramfs/seed/notice проверяются дополнительно, original probe
проверки не заменяются. **Source stage локально проверен и готов к Apple build**:
root full suite **140 Python tests PASS, 4.604 s** (`PYTHONDONTWRITEBYTECODE=1
TMPDIR=/workspace/iDeck/.work python3 -m unittest discover -s
experiments/linux-guest/tests -q`). Первоначальный suite имел одну устаревшую
проверку количества preBuildScripts (1 вместо новых 2); assertion исправлен,
затем весь suite прошёл. Это host-test fixture mismatch, не Apple failure.
Native owner проверил actual resource prepare/standalone CLI stage, shell syntax
и source review/freeze завершены. Root проверил все 21 overlay input hashes,
11 source copies; overlay SHA-256
`fc359df97048aa83aa7e50a2e735a75f6c24bc3f7440301bb275da6ac508135e`.
14 protected файлов и все 37 прежних evidence snapshots побайтно сохранены;
старый HANDOFF начиная с first-device heading также не изменён.
Foundation/Swift checks написаны и подключены к Apple gate, но здесь нет
QEMU/Swift compiler: actual two-boot persistence и foreground-stop на устройстве
не проверены. Новых CI/IPA/Steam/network actions нет; лимиты
6900 s / 120 min сохраняются. Evidence:
`experiments/linux-guest/evidence/terminal-persistence-preparation.json`.
Старые snapshots и baseline артефакты остаются без изменений.
Следующий шаг: root review/commit/push этой source stage, затем отдельный
авторизованный Apple build точного pushed SHA с обычной quota/request проверкой.
После полученного IPA owner выполняет device check выше; до этого не объявлять
terminal/persistence работоспособными. SHA build должен быть отдельным от
последующих doc-only коммитов; полный итоговый SHA получать через git rev-parse HEAD.

## Первый device Linux/JIT/framebuffer/input gate прошёл

Owner сообщил результат на **iPhone 16 Pro Max / iOS 27**, SideStore, после IPA
build `660e27e515f666040a5959fa845fe85b3290a740`. Parent/root независимо проверили
переданные screenshot, serial и device result.json; автор HANDOFF получил их
findings и сам устройством не управлял. Device report: **2141 bytes**,
`status=guest_frames_and_input_verified`, `qemu_init_returned=true`,
`jit_available_after_init=true`, `guest_input_verified=true`, phases **[0,1]**,
**480000 pixels** проверено в каждом кадре. OS 27.0 build 24A5430a, bundle 119.

Serial **40988 bytes**, SHA-256
`bd34d1c9132449428b69d0f7f00c8e4fd771af3b1e36b2455414602b67c5bae0`
совпал с device JSON. Реальный kernel **6.18.35-0-virt** дошёл до завершения
probe. Независимо decoded **24 keyboard events / 6 KEY_A press-release pairs**
и **493 tablet events / 69 BTN_LEFT pairs**; это evdev counts, не утверждение
числа отдельных физических taps. Parent/root также воспроизвели exact SHA-256
обоих ожидаемых 800×600 BGRA кадров (alpha 255):

- frame 0: `e8863c335217e021bca1ec62372ec27a7d569818ec085180162cbf6539e8fd97`
- frame 1: `a6c7820146e38170a5bc6b4c247acd838098b64ac1b61847c343ace2dea02f4f`

Screenshot показывает phase B с четырьмя quadrants и UI labels о JIT execution
и verified buffers/input. **A→B physical-screen video не проверено**;
`physical_screen_verified=false` в JSON сохранено как есть. Guest GPU acceleration
и Steam также false. **21.536118 s** — polling после `qemu_init` с owner input,
не pure boot time, не весь init и не benchmark; start UTC 2026-10-16T02:38:28Z.

Device executable SHA-256
`cbfcb81585c200a02f49257d0817a9c7bae5a3c53d98e1d45e0bfada62db15ba`
отличается от original CI executable. Это совместимо с SideStore re-signing,
но byte proof «отличается только подпись» не получен. Выдача всех requested
entitlements и конкретный pairing/JIT method этим отдельно не доказаны.
**Gate PASS: real Linux boot, JIT-after-init, software framebuffer и guest input**,
по owner evidence и parent/root audit. **Steam/игры/accelerated guest GPU не
проверены.** Sanitized summary: `evidence/first-device-probe-success.json` внутри
`experiments/linux-guest`; raw JSON/serial, container UUIDs, private Drive/Library
URLs/IDs и screenshots в Git не добавляются. Baseline IPAs/старые snapshots
сохранены без изменений.

Parent уже отдельно превратил текущий owner report в Markdown и доставил его
по запросу; это **one-off document**, не доказательство встроенного app export.
Source feature реализована отдельно: `ios/LinuxProbeReport.swift` создаёт
`iDeck-Linux-Probe-Report.md` из того же snapshot после atomic JSON write.
Save report даёт **Markdown-only основной action**, а raw JSON/log — отдельный
secondary. Renderer допускает только известные поля/typed values; missing/type
mismatch остаётся UNKNOWN. Text ограничен/escaped; serial даёт лишь fixed
whole-line markers и kernel token. Нет unknown/secret appendix, raw argv,
container paths или произвольного serial text. Markdown failure не меняет guest
result; stale MD недоступен, export error видим, raw files остаются доступны.

Pinned source restore/full overlay/fifth Swift file и input hashes проверены.
Actual Foundation renderer tests включены в existing Apple gate, но **Swift
compiler здесь отсутствует и эти tests пока не выполнялись**. Coordinator run:
`PYTHONDONTWRITEBYTECODE=1 TMPDIR=/workspace/iDeck/.work python3 -m unittest
discover -s experiments/linux-guest/tests -v` — **126 Python tests PASS**,
exit 0, **1.042 секунды**; 8 новых package/source/staging checks отдельно прошли
за 0.096 секунды, плюс 118 прежних. Independent source/compile-visible review
PASS, blocker не найден. Это не исполнение Swift renderer и не проверка app
Markdown на устройстве. Source feature **локально проверена, готова к Apple gate**.

Новая CI/IPA и app Markdown device test не выполнялись. Final source/test/input
hashes: `experiments/linux-guest/evidence/markdown-report-export.json`.
Native pins и boot/JIT/input gates сохраняются; лимиты worker **6900 секунд /
120 минут provider** не увеличиваются. Следующий шаг — coordinator review,
commit/push/exact remote SHA и один Apple workflow после свежих quota/private/
disabled-billing проверок. Actual Foundation checks должны исполниться там;
затем новый IPA и отдельная device export проверка. Старый доказанный device
probe относится к build 660e, не к ещё не собранной Markdown версии.

## JIT setup fix собран в новом IPA и доставлен; ожидается device test

[Build `6ad18a803ffd2c7f0ad3ca15`](https://codemagic.io/app/6ad03ce9a8a969b53f3a4aa9/build/6ad18a803ffd2c7f0ad3ca15)
завершился **SUCCESS / finished**, provider index 9, **9m 32s**. Защищённый
build SHA — [`660e27e515f666040a5959fa845fe85b3290a740`](https://github.com/Mi-Yomi/iDeck/commit/660e27e515f666040a5959fa845fe85b3290a740),
ветка `codex/linux-guest-feasibility-20261015`, workflow `ideck-linux-probe-ipa`.
Это новая Apple-сборка source fix после owner feedback о Magnifier.
Координатор независимо прочитал полный structured result.json (729 строк):
**`status=linux_probe_ipa_built`, `ipa_created=true`, `runtime_linked=true`**,
correct commit, device/Steam false; worker elapsed **531.351 секунды**. В 92
шагах 91 exit 0, единственный nonzero — `metal-probe-before=1` (0.553 s), затем
официальный download (14.079 s) и after probe (2.45 s) exit 0. Native QEMU
110.227 s, integrate 0.148 s, integrated rebuild 8.453 s, pairing **library build**
25.5 s, app build 50.603 s, signature verification 0.055 s — exit 0. Content
read не является локальной проверкой raw-byte hash result; file hash ниже
передан parent как внешне проверенный. Последующий **doc-only SHA** получить после commit/push через `git rev-parse HEAD`, сверить
с remote и сообщить отдельно от build SHA выше.

**`iDeck-Linux-Probe.ipa`: 49212045 bytes**, SHA-256
`30ea8480333ae2002dd6e8fa8fd0416ce9317280f8d1536430b9e8fd3283108f`.
**`result.json`: 19032 bytes**, SHA-256
`6e6195433213a19933446e959e0298bc40a3d949ac47d1d886e112760f2286d2`.
Parent/root независимо выполнили static delta audit **реальных артефактов** —
PASS; автор раздела получил findings, локальную materialization не заявляет.
Проверены 7 ARM64 iOS-device Mach-O, сохранённые bundle IDs/helper и embedded
**requested ad-hoc entitlements**, три побайтно неизменных guest assets.
Exact-SHA source/overlay receipts подтверждают JIT setup UI, TrollStore marker,
registered `ideck-linux-probe` VPN callback и actual JIT execution gate.
Это **не** доказательство выдачи requested entitlements на устройстве, работы
pairing/helper, JIT execution или Linux boot. Minimum OS unchanged: app 16.0,
helper 26.0, StikJIT 17.4; JIT на iOS 16 не обещается.

По явному запросу владельца parent приватно доставил новый файл в Drive в
**02:35**. Private URL/ID, Library identifiers и screenshots в Git не сохраняются.
Статус — **delivered, awaiting device test**; доставка не означает установку
или успешный device run. Первый baseline IPA `5cd442c…`, его исходные bytes и
старые evidence snapshots сохранены. Новая запись:
`experiments/linux-guest/evidence/jit-setup-ipa-success.json`.

Следующий шаг выполняет owner: re-sign **копии** нового IPA обычным SideStore
путём, отдельно записать новый signed hash; открыть **JIT setup and method** →
on-device pairing либо import owner pairing file → Settings/Privacy & Security/
Developer Mode/PIN для on-device pairing → LocalDevVPN → Check setup/DDI →
Enable JIT → actual execution check → Start Linux. Затем frame A, touch +
Send A, frame B и probe report с signed app identity/OS. Pairing credentials
остаются у owner. **Pairing, JIT, Linux boot/display/input нового IPA и Steam
на iPhone пока не проверены.** Code/native pins, baseline IPA и CI этим doc-only
обновлением не менялись; новых CI/device/credential действий здесь нет.

## Первый owner device attempt: JIT открыл Magnifier, Linux boot не подтверждён

После установки первого IPA пользователь сообщил: **Enable JIT открывает
Magnifier**, ожидаемый original Husk pairing/settings UI недоступен, Linux не
запустился. Это owner feedback, переданный координатором, не собственное device
наблюдение автора HANDOFF. Пользователь подтвердил SideStore, без LiveContainer.
**Первый device attempt не считается успешным**.
При этом baseline native compilation/linking/static audit остаются доказанными:
защитить build `5cd442c7670932c551459f015c71e295c4b6610a` и original IPA
49205131 bytes, SHA-256
`2c38939b7c0d03586879b69451a4e42afa3d62399ab165fe76e8810f472a6513`.
Текущий doc base — `29807382cfe5fb151e2257b77981f1ea71ab37ec`.

Source-проверка baseline 5cd объясняет симптом: LinuxProbeView.swift:83 вызывал
`jit.enable()` напрямую; pinned JITSetup.swift:138-143 в Automatic выбирал
TrollStore раньше встроенного JIT, а JITBootstrap.swift:245-247 принимает
`canOpenURL(apple-magnifier://)` за installed TrollStore. Request на lines
288-300 открывает тот же scheme. В original JITCard:147-150 при доступном
built-in helper сначала выставлялся `.builtIn` — этого поведения в baseline
Linux UI не было. Он также не показывал `jit.busy/status/error`, а TrollStore
branch мог ждать 60 секунд до setup-sheet. JITSetupFlow с pairing/import/VPN
был сохранён и подключён как sheet, но явного доступного setup action не было.

Это объясняет JIT onboarding/routing blocker; пока нет оснований называть это
ошибкой QEMU Linux boot после успешного JIT. LinuxProbeSession.start() остаётся
за `JITBootstrap.ready` и execution check. Whole ContentView/SettingsTab не нужно
возвращать: original JITSettings содержит Start Android on launch, и это может
размыть Linux isolation. Прямо проверен callback mismatch: pinned
JITSetup.swift:407 задаёт `localdevvpn://enable?scheme=husk`, а
`ipa/package_probe.py:43-44` регистрирует только `ideck-linux-probe`.
Helper ID читается из actual embedded Info.plist (JITBuiltIn.swift:60-64);
поломка extension/BG-task IDs из-за rename или SideStore этим не доказана.

Подготовлен focused source fix `husk/patches/0002-jit-setup-routing.patch`:
per-app TrollStore marker требуется и для detection, и для attach; VPN callback
берётся из actual registered scheme через URLComponents. Linux UI даёт явную
**JIT setup and method** с original JITSetupFlow, busy/status/error и выбирает
built-in на Automatic при доступном helper, сохраняя explicit user method.
Debugger attach и executable-memory execution test теперь различаются; session
публикует результат actual claim/start checks, без probe в SwiftUI view body.
Сохранены прежние JIT/start gates и one-session Linux isolation.

Original flow остаётся owner-driven: Pair on this device либо import pairing
file → Settings/Privacy & Security/Developer Mode/PIN для on-device pairing →
LocalDevVPN → Check setup/DDI → Enable → execution check → Start Linux.
Pairing store — Documents этого приложения; из original Husk он автоматически
не переносится. Подготовка здесь не выполняет pairing и не читает credentials.
Source fix **локально проверен и готов к Apple build**. Coordinator run:
`PYTHONDONTWRITEBYTECODE=1 TMPDIR=/workspace/iDeck/.work python3 -m unittest
discover -s experiments/linux-guest/tests -v` — **118 tests PASS**, exit 0,
**0.902 секунды**, Python 3.12.14/Linux; 8 новых source/staging checks отдельно
прошли независимым reviewer за 0.109 секунды, плюс 110 прежних. Реальный pinned
restore, full patch application и hashes прошли. Native/UI и independent review
не нашли blocker. Это source/staging checks, не Swift execution/typecheck,
UIKit, JIT или device proof; Apple Swift compiler здесь отсутствует.

Workflow/CI worker/native/guest locks/project/package/source-check lock+archive/
guest archive и first-IPA evidence побайтно неизменны относительно doc base;
baseline IPA сохранён. Final patch/series/overlay/UI/session/test hashes:
`experiments/linux-guest/evidence/jit-setup-routing.json`. Следующий шаг —
координатор commit/push, exact новый SHA и одна Apple сборка после свежих quota,
disabled billing, private/no-active-CI проверок; затем owner re-signing копии
нового IPA и повторный device setup/JIT/boot/display/input/report test.
Новая Apple сборка/IPA и device success **ещё не заявлены**. Linux/JIT execution,
boot/display/input на iPhone и Steam не подтверждены.

## Первый настоящий IPA собран; независимый static package audit прошёл

Успешный [build `6ad174a63ffd2c7f0ad3c64c`](https://codemagic.io/app/6ad03ce9a8a969b53f3a4aa9/build/6ad174a63ffd2c7f0ad3c64c),
защищённая build revision
[`5cd442c7670932c551459f015c71e295c4b6610a`](https://github.com/Mi-Yomi/iDeck/commit/5cd442c7670932c551459f015c71e295c4b6610a),
workflow `ideck-linux-probe-ipa`, правильная Linux-ветка. Result:
**`status=linux_probe_ipa_built`, `ipa_created=true`, `runtime_linked=true`**.
Provider index 8, Mac Mini M2, Xcode 27.0 (27A266a), 8m 32s; worker elapsed
471.901 секунды. Все этапы actual host compile/link/execute, QEMU, Husk
integration/rebuild, pairing, XcodeGen, app build и package завершились.
В 92 шагах 91 exit 0; единственный nonzero — ожидаемый `metal-probe-before=1`,
после которого официальный download, after probe и version check прошли.

**`iDeck-Linux-Probe.ipa`: 49205131 bytes**, SHA-256
`2c38939b7c0d03586879b69451a4e42afa3d62399ab165fe76e8810f472a6513`.
**`native-products.tar.gz`: 10521805 bytes**, SHA-256
`dd00675f035ed11c3f4647e7e16c452622a9136d0abba4666a709fbf818b3bc3`.
Исходный workflow output: `.work/linux-ipa/iDeck-Linux-Probe.ipa`; исходные
артефакты сохранить без изменений. Private Library URLs/IDs и signed download
URLs в Git не добавляются. Итоговый doc-only SHA после commit/push получить
через `git rev-parse HEAD`, сверить с remote и сообщить **отдельно от build SHA**.

Parent/root выполнили независимый static audit **реально скачанных bytes**;
автор этого раздела получил findings. IPA/log ZIP CRC clean; 7 настоящих thin
ARM64 Mach-O, platform 2 (iOS device), явные bundled load dependencies на месте.
Три guest assets побайтно совпали с locks на GitHub build SHA и result;
initramfs содержит реальные `ideck-init`, `fb-probe`, `evdev.ko`. Source/native/
overlay locks и staged hash receipts совпали, app log содержит BUILD SUCCEEDED.
CI ad-hoc signature verification прошла; root отдельно Apple `codesign` не
выполнял. Static reports `independent-static-audit.md/json` доступны у parent,
SHA-256 JSON `081eec1edb9350d210e8e628cccec761b2c0794f375089402b7b017f959855cc`;
локально в этом checkout они не материализованы. Evidence:
`experiments/linux-guest/evidence/first-ipa-success.json`.

Host compiler receipt ready: macOS SDK 27, arm64 Darwin 27, actual probe binary
33432 bytes, SHA-256
`c9f33a3fc59736f0ec357b242f512958ceb4611c65dafea40754e427d76f2298`, marker OK.
Nested runtime=false в source/guest stage — ранние pre-build snapshots;
верхнеуровневое final `runtime_linked=true` относится к результату сборки.
Minimum OS: app 16.0, StikJIT 17.4, JITHelper 26.0; это не обещание JIT на iOS 16.

**Сохранить эту code revision, native pins, исходный IPA и native products.**
Дополнительные CI/code/Steam/device действия здесь не выполняются. Для следующего
шага owner делает обычный sideload re-signing **копии** IPA; hash новой подписи/
исполняемого файла фиксировать отдельно от исходного IPA hash. Затем на устройстве:
JIT self-test → Linux boot → display/input → сохранение probe report.
**Установка, Linux boot/JIT/input на iPhone и Steam не проверены.** Старые
HANDOFF/evidence snapshots ниже сохранены; их pending/failed относятся к прежним
ревизиям и не отменяют этот результат сборки.

## Последняя Apple-попытка: cross wrapper исправлен, build-machine C compiler не исполняется

[Build `6ad16f883ffd2c7f0ad3c55b`](https://codemagic.io/app/6ad03ce9a8a969b53f3a4aa9/build/6ad16f883ffd2c7f0ad3c55b)
на [`9e2e481ced29de05ab63deb6404330b6bf0e2061`](https://github.com/Mi-Yomi/iDeck/commit/9e2e481ced29de05ab63deb6404330b6bf0e2061)
завершился **failed** в `native-qemu`. `needs_exe_wrapper` прошёл; следующий
отказ связан с build-machine C compiler для native generator
`target/hexagon/gen_semantics.c`, не app linker или запуском guest. Parent передал
actual `config-meson.native`: **77 bytes**, `c = ['cc']`; в Meson log sanity
compile не дал stderr, но запуск host sanity program отказал. Линкерные пути
ссылаются на iPhoneOS27.0.sdk, при этом default target `cc` — Darwin.

Источник — browser-сводка координатора и переданные parent config/log excerpts,
**не локально прочитанный полный raw ZIP**. Это сильное основание проверить
утечку iOS SDK selection в native host build, но фактическое значение `SDKROOT`
из этих excerpts не доказано и не утверждается.

Реализован `ensure_qemu_build_compiler`: `xcrun --sdk macosx` получает absolute
clang/MacOSX SDK, затем clang `-isysroot <MacSDK> -dumpmachine` даёт фактический
compiler default Apple arm64/aarch64 Darwin/macOS triple. Это проверка default
target, не независимое доказательство runtime OS. Safe-token validation
отклоняет пути/значения, которые QEMU meson_quote не сможет передать корректно.
Explicit `-target <triple> -isysroot <MacSDK>` компилирует и линкует C program с
`TargetConditionals.h`: `#error`, если не macOS или iPhone. Новый binary обязан
быть непустым и **реально исполниться** с точным marker. Только после этого
публикуется `IDECK_QEMU_HOST_CC`; новый Husk patch
`ipa/0003-qemu-macos-build-compiler.patch` передаёт его через documented
`--host-cc`. SDKROOT/CC/CFLAGS/iOS target environment не меняются. Ошибки SDK,
compiler/platform/compile/link/execute/marker/timeout не маскируются.

Full pinned Husk `build_ios.sh` materialized root и проверен автором evidence:
8825 bytes, Git blob `22a6ff932eccc51e1d58ddce8ee334884c9ac8b9`, SHA-256
`9f039b008da5ab56e0f7581b3d84f6e4b8f1e74adc9d8c608f26d94e0a8ef176`.
Это source proof, не Apple execution. Native agent проверил полный recipe
в isolated Git root `.work/qemu-host-compiler/native-verify`: existing `0001`
check/apply, затем `0003` check/apply, `bash -n` PASS; byte compare показывает
только одну добавленную `--host-cc` строку относительно 0001-patched recipe,
original сохранён. New patch SHA-256
`f95fbe471fdddea4fd593e9af7201a96d6f7aef81416730881acd4d34a9d1579`,
resulting recipe SHA-256
`02729ae1e0a5b50aed33b79c1e459a21f45ddaa531c53934a9ed3e08cddeea55`.
Оба независимых review одобрили итог. Координатор выполнил
`python3 -B -m unittest discover -s experiments/linux-guest/tests -v` —
**110 tests PASS**, exit 0, **0.813 секунды**, Python 3.12.14/Linux: 15 новых и
95 прежних. Это network-free host controls с моделированием xcrun/clang/probe,
**не actual Apple compile/link/execute probe**. Log:
`.work/qemu-host-compiler/host-tests.log`, 16858 bytes, SHA-256
`a44166fc7eda8a499a635bc32d2713afd46e07229a36697ce98e9baf6f6fb3b4`;
не добавлен в Git. AST/diff checks PASS. Workflow/request/native lock/0001/0002/
guest lock/Python lock не менялись. Final script/test/patch hashes в новом
evidence; Apple-проверка host compiler fix ещё требуется.

Parent предоставил Library ZIP `libfile_d2ac800c3dd081918e780006cf73c064`,
239601 bytes, SHA-256
`df9a6489fee2837e98043bec0aad544f22c4f6ad491198b9189813b2bada0d73`.
Это **reported / unverified locally**: официальный helper отказал с
`library file transfer failed: download failed`, ZIP payload не получен,
HTTP status не раскрыт. Этот отказ не называется 403; access bypass не было.
Evidence: `experiments/linux-guest/evidence/qemu-host-compiler.json`.

Старые evidence и HANDOFF snapshots сохранены. Integrated QEMU/Husk runtime,
app linking и IPA ещё не получены; device Linux/JIT и Steam не проверены.
Лимиты **6900 секунд / 120 минут** не меняются. Новая CI для host compiler fix
ещё не запускалась; следующий запуск только browser-координатором после свежих
quota/disabled-billing/private/exact pushed HEAD/no-active-CI проверок.

## Последняя Apple-попытка: Python и GPU прошли, QEMU ошибочно проверяет device binary на host

[Build `6ad169bc3ffd2c7f0ad3c451`](https://codemagic.io/app/6ad03ce9a8a969b53f3a4aa9/build/6ad169bc3ffd2c7f0ad3c451)
на [`c9bd25b8ee7eea1f88f44895430c3d3c0ac9f9fc`](https://github.com/Mi-Yomi/iDeck/commit/c9bd25b8ee7eea1f88f44895430c3d3c0ac9f9fc)
завершился **failed**. Python venv/import и проверки actual Meson cross files
прошли; native-base, Metal probe и ANGLE также прошли. `native-gpu`: exit 0,
**19.916 секунды**. Первый отказ — `native-qemu`, **12.853 секунды**:
`../meson.build:1:0: ERROR: Executables created by C compiler clang -target
arm64-apple-ios15.5 are not runnable`. QEMU **10.0.12-utm**, его Meson **1.5.0**.
Это ошибка configure/Meson host-versus-device проверки, не app linker failure.
Источник — terminal browser-сводка координатора и переданный parent полный
QEMU log text (1302), **не локально прочитанные artifact bytes**. В тексте:
Python 3.12.7, собственный QEMU pyvenv с Meson 1.5.0/pycotap 1.3.1; Meson уже
распознал cross build. Это не доказательство отсутствующего cross-файла.

Предыдущий yaml fix этой Apple попыткой проверен. Старые evidence и нижние
HANDOFF sections сохраняются как исторические snapshots. Integrated QEMU/Husk
runtime ещё не собран, app не слинкован, IPA нет; device Linux/JIT и Steam не
проверены. Реализован минимальный source-backed fix: `needs_exe_wrapper=true`
в properties сгенерированного QEMU cross-файла, без подмены host/target platform.
Патч `ipa/0002-qemu-ios-needs-exe-wrapper.patch` добавляет property только при
`cross_compile=yes`; actual compiler/target/machine settings сохраняются.
Worker фиксирует patch SHA, делает `git apply --check` и apply в locked QEMU
directory до `native-qemu`. Source evidence: materialized tag configure
(v10.0.12-utm), **60470 bytes**, Git blob
`000309cf610ec058e147b9b0a21d5994a6e61c0b`, SHA-256
`dced6162c1d2de70924b90e94ad508fa46bec1ab820417d83a366f379428093b`;
автор evidence проверил bytes/hash. Это не полная распаковка locked QEMU archive
или native build. Native agent проверил полный primary configure в
`.work/qemu-cross-build/native-verify`: worker-equivalent `git apply --check` и
apply с точным `--directory` (включая ignored third_party path), `bash -n` PASS;
byte compare показывает только 4 добавленные строки. Original не менялся.
Patch SHA-256 `a14a585823b7a5401ceea4f29524d33b81837ecfb1c7d77d81325ca7951b99a3`,
patched configure SHA-256
`8aa188b69bc674f0ec754b944dce413b5aba96e4e9143fa9439bc64550b28f41`.
Это source-control proof, без исполнения actual configure или Apple compiler.
Role2 одобрил fix/diagnostics. Первый общий host run выполнил 95 tests, но
6 новых cases отказали из-за fixture: временные каталоги под `.work` не имели
собственного Git repo; git apply обнаружил parent/cwd prefix и пропустил patch.
Это ошибка нового test setup, не Apple/runtime failure; reviewer добавил
изолированный `git init`, runtime fix не менялся. Initial log сохранён:
`.work/qemu-cross-build/host-tests-initial.log`, 20361 bytes, SHA-256
`730f45129acf39232baacdf87f8d8ed2f56963f2cbb4879507116e70590d4fc4`.
После изоляции fixtures финальный coordinator run:
`python3 -B -m unittest discover -s experiments/linux-guest/tests -v` —
**95 tests PASS**, exit 0, **0.723 секунды**, Python 3.12.14/Linux; 8 новых +
87 прежних. Final log `.work/qemu-cross-build/host-tests.log`, 14233 bytes,
SHA-256 `2d55f01b1994e855e190af12651e41303b5bef5ec90b74acc6338a10d6b0134e`;
логи не добавлены в Git. Native/Swift-Xcode review и независимые regressions
завершены; root независимо подтвердил только 4 source insertions. YAML
structural check подтвердил только три новых diagnostic artifact paths;
AST/diff checks PASS. Эти host controls не запускают actual QEMU configure,
iOS compiler или app linker; Apple rerun этого fix ещё нужен. Лимиты **6900 секунд /
120 минут** сохраняются. Evidence:
`experiments/linux-guest/evidence/qemu-cross-build.json`.

Parent передал ZIP Library `libfile_02d08571e5c0819184cb6ad380b712c4`,
197312 bytes, SHA-256
`e9611d2da2bc6e47441c38f6392cce0487e8b219878263c1447b4c3da3ff1ceb`:
**reported / unverified locally**: официальный Library helper завершился
exit 1, `library file transfer failed: download failed`; payload не получен,
HTTP status helper не показал. Это не называется 403; bypass не было.
По проверенному parent ZIP namelist глубокий `meson-logs/meson-log.txt` в архив
не попал; его содержание не заявляется прочитанным. Root добавил три exact
artifact paths для будущих попыток: `_husk_build/meson-logs/meson-log.txt`,
`_husk_build/config-meson.cross` и `_husk_build/config-meson.native` внутри
staged QEMU. Это не восстанавливает старый log.

Новая CI для этого fix ещё не запускалась. Следующий запуск — только
browser-координатором после свежих quota/disabled-billing/private/exact pushed
HEAD/no-active-CI проверок. Полный новый SHA брать после commit/push через
`git rev-parse HEAD` и сверять с удалённой Linux-веткой; SHA выше — уже завершённый
build, не будущий результат.

## Последняя Apple-попытка: Metal и ANGLE прошли, Python не находит yaml

[Build `6ad15ff23ffd2c7f0ad3c239`](https://codemagic.io/app/6ad03ce9a8a969b53f3a4aa9/build/6ad15ff23ffd2c7f0ad3c239)
на [`efa674191ea9b337d30d2aa8e2185584dba1fe3d`](https://github.com/Mi-Yomi/iDeck/commit/efa674191ea9b337d30d2aa8e2185584dba1fe3d)
завершился **failed** на `native-gpu`: virglrenderer `meson.build:72:16`,
Python **3.12.7** не находит module `yaml`. Источник здесь — краткая browser-сводка
координатора, не полный raw log; локальная независимая проверка artifact bytes
пока не выполнена.

- `native-base`: exit 0, **83.179 секунды**.
- Официальная загрузка MetalToolchain: **18.208 секунды**, затем настоящий
  compile probe создал AIR **2944 bytes** и прошёл.
- `native-angle`: exit 0, **241.068 секунды**.
- Integrated QEMU/Husk runtime, app linking и IPA ещё не получены.
  Device Linux/JIT и Steam не проверены.

Таким образом, bootstrap Metal из предыдущего раздела уже проверен этой Apple
попыткой. Старый Metal evidence JSON и все нижние HANDOFF snapshots сохранены
как история, не переписываются задним числом. Новый blocker — конкретный
Python build dependency, а не ошибка Metal toolchain или app linker.

В worker добавлена новая build-only venv перед `native-base`: CPython 3.12,
Darwin arm64, pinned **PyYAML 6.0.2**, wheel
`PyYAML-6.0.2-cp312-cp312-macosx_11_0_arm64.whl`, **173302 bytes**, SHA-256
`ce826d6ef20b1bc864f0a68340c8b3287705cae2f8b4b1d932177dcc76721725`.
Role2 проверил реальные wheel bytes в памяти и metadata (нет Requires-Dist),
сверил [официальный PyPI manifest](https://pypi.org/pypi/PyYAML/6.0.2/json);
автор HANDOFF загрузку не повторял. Lock задаёт один exact public wheel URL;
pip использует `--isolated --no-index --no-deps --only-binary=:all:
--require-hashes`, без system install или дополнительных пакетов.

До изменения child PATH тот же venv interpreter с `-I` импортирует `yaml`;
проверяются версия, executable/prefix и module path внутри новой venv. Только
после этого venv/bin ставится первой в PATH и задаётся VIRTUAL_ENV, до генерации
cross-файла в `native-base`. После него проверяются **оба фактических**
`cross-ios.meson` и `cross-darwin.meson`: `binaries.python` должен содержать ровно
один абсолютный путь к проверенному venv/bin/python3; в отчёт идут hashes файлов.
Проверка выполняется до копирования cross-darwin и ANGLE/GPU. Отсутствующий,
malformed или иной interpreter даёт отказ. Ошибки install/import/identity/
permissions/timeout сохраняются. Не добавлены Mako/Jinja; QEMU configure/pythondeps и его собственная
среда не менялись, успешная сборка QEMU не заявлена. Лимиты **6900 секунд /
120 минут** сохраняются; подготовка только на disposable runner, без
аккаунтов/credentials/оплаты.

**Проверено координатором:** `python3 -B -m unittest discover -s
experiments/linux-guest/tests -v` — **87 host tests PASS**, exit 0, 0.717 секунды,
Python 3.12.14/Linux: **19 новых** Python setup/cross-file tests и 68 прежних.
Это network-free controls с моделированием subprocess/pip/Apple outputs,
не фактическая установка pip или Apple build. Оба независимых review одобрены;
AST и whitespace checks PASS. Request/workflow/native lock/native patch/guest
lock не менялись. Log: `.work/python-yaml-bootstrap/host-tests.log`, 12939 bytes,
SHA-256 `a8bb516d4ba71eb0694f025d6c74ad20088855a5bdf279a2934bd6ce5133d7ee`;
не добавлен в Git. Script/test/requirements hashes и полное evidence:
`experiments/linux-guest/evidence/python-yaml-bootstrap.json`.

Parent передал Library ZIP `libfile_e6c01d01964c81918895c27f477ced07`, size
193432 bytes, SHA-256
`9fce05976bca43f89ba9097671437eb7a595a289d6402aefe2d1726cabfc147d`.
Это **reported / unverified locally**. Library prepare прошёл с
`workspace_path=null`, но официальный materialization helper
`.work/python-yaml-bootstrap/library-helper` завершился exit 1:
`library file transfer failed: download failed`. ZIP payload не получен;
helper не раскрыл HTTP status, поэтому этот отказ не называется 403.
Локальная независимая проверка digest не выполнена, обхода не было.
Новая CI для yaml fix ещё не запускалась. Следующий запуск — только
browser-координатором после свежих quota/disabled-billing/private/exact pushed
HEAD/no-active-CI проверок.

## Новая Apple-попытка: native-base прошёл, отсутствует Metal toolchain

[Build `6ad15b143ffd2c7f0ad3c111`](https://codemagic.io/app/6ad03ce9a8a969b53f3a4aa9/build/6ad15b143ffd2c7f0ad3c111)
на [`86d4ac0ea9b7c503fb0c982e648d50e7bd178c23`](https://github.com/Mi-Yomi/iDeck/commit/86d4ac0ea9b7c503fb0c982e648d50e7bd178c23)
завершился **failed**, первый упавший шаг — `native-angle`: отсутствует Metal
toolchain; диагностика указывает официальный
`xcodebuild -downloadComponent MetalToolchain`. Источник — последняя краткая
browser-сводка координатора, **не полный raw log**; автор раздела не получал
его напрямую.

- `swift-source-check`: exit 0, 67.143 секунды.
- Все **7 source archives** проверены; pixman скачан с первой попытки.
- `native-base`: exit 0, 79.09 секунды. Это реальная Apple-сборка базовых native
  зависимостей, но не полный QEMU/Husk runtime или линковка приложения.
- `result.json` создан. IPA отсутствует; device Linux/JIT/Steam не проверены.

Предыдущий quota blocker **разрешён для этой попытки**: пользователь прямо
подтвердил 83 использованных / 417 оставшихся бесплатных macOS минут и дал
команду «Запускай сборку»; обычный automatic review одобрил отправку перед
этой CI. Нижний ночной раздел и
`experiments/linux-guest/evidence/overnight-quota-blocker.json` — исторический снимок до этого подтверждения, не текущий внешний blocker.
Старый JSON не изменён. Для любого следующего запуска нужна свежая проверка
квоты, disabled billing, private repo, отсутствия активной CI и exact pushed SHA.

В worker перед `native-angle` добавлен реальный compile probe минимального
Metal shader: `xcrun --sdk iphoneos metal -c` должен создать новый непустой AIR.
Только при точной диагностике missing Metal Toolchain вместе с официальной
recovery command вызывается **один**
`xcodebuild -downloadComponent metalToolchain` (каноническое имя component по
[документации Apple](https://developer.apple.com/documentation/xcode/downloading-and-installing-additional-xcode-components));
затем shader компилируется заново в другой новый AIR. В отчёт входят status,
факт download, version и size/SHA-256 probe. Probe/download/version исполняются
через `env -i` только с PATH/HOME, как pinned ANGLE; DEVELOPER_DIR/TOOLCHAINS
не могут незаметно выбрать другой compiler. В отчёте лишь boolean наличия
проигнорированных overrides. Unrelated compile/license/permission отказы, download/reprobe failure и timeout распространяются наружу; проверки
не заменяются заглушкой или одним `xcrun --find`. Это подготовка disposable
Xcode 27 runner в рамках разрешения. Лимиты **6900 секунд / 120 минут** сохранены;
автоматического принятия лицензий, аккаунтов, credentials или оплаты нет.
**Проверено координатором:** `python3 -B -m unittest discover -s
experiments/linux-guest/tests -v` — **68 host tests PASS**, exit 0, 0.744 секунды,
Python 3.12.14/Linux: 12 новых bootstrap tests плюс 56 прежних. Это network-free
host tests с подменой subprocess/Apple outputs, не настоящая загрузка component
или Metal compile. Native/Swift-Xcode auditor и независимый regression reviewer
одобрили итог. Log: `.work/metal-toolchain-bootstrap/host-tests.log`, SHA-256
`5e5dd83a4116efae67782d0e7eace0192ab77816992bc149d092883454a6cbc6`; не добавлен в Git. Script/test/lock hashes и evidence:
`experiments/linux-guest/evidence/metal-toolchain-bootstrap.json`.

Для полной raw-диагностики parent предоставил Library artifact ZIP
`libfile_f61b646f9c288191a124637f3544e895` и ожидаемые size/hashes. Root получил
разрешённый materialization URL, но обычный GET через cloud proxy остановился
на `Tunnel connection failed: 403 Forbidden` до получения bytes. ZIP не записан,
локальная независимая проверка raw digests не выполнена. Переданные hashes
помечены в новом evidence как **reported / unverified locally**; signed URL
не сохраняется. Переданный контекст: `CompileMetalFile`,
`mtl_internal_shaders_autogen.metal`, target `ANGLEMetalLib`,
`air64-apple-ios15.5`, SDK 27.0. Это всё ещё сведения parent, не прочитанный
локально full raw log; access denial не обходился.
Новая CI для bootstrap-исправления пока не запускалась; ей управляет только
browser-координатор. Полный новый SHA после commit/push брать через
`git rev-parse HEAD` и сверять с удалённой Linux-веткой; build SHA выше относится
к уже завершённой попытке.

## Ночной итог: исправление pushed, Apple-запуск заблокирован проверкой квоты

Code commit: [`d849a307727faf374b1bd8a60035a3afdd3e28fa`](https://github.com/Mi-Yomi/iDeck/commit/d849a307727faf374b1bd8a60035a3afdd3e28fa),
ветка `codex/linux-guest-feasibility-20261015`. Исправление bounded retry и
56 host tests PASS уже закоммичены и pushed; Apple-проверка этого кода **не
запускалась**. Этот раздел и два новых evidence-файла — последующее изменение
только документации. Его полный итоговый SHA после commit/push нужно получить
через `git rev-parse HEAD` и сверить с удалённой веткой; code SHA указан отдельно.

**Точный внешний блокер:** автоматическая проверка одобрения повторно не
разрешила отправку `ideck-linux-probe-ipa`: показание billing **83/500** не дало
независимого явного подтверждения **не менее 120 оставшихся бесплатных macOS
минут**. Счётчик рос 76 → 77 → 78 → 80 → 83, что похоже на израсходованные
минуты, но эта интерпретация и арифметический остаток не приняты как требуемое
явное доказательство. Browser-координатор проверял DOM, tooltips и официальную
billing/pricing документацию; однозначного подтверждения remaining quota не
получил. Это отказ approval review до запуска CI, **не ошибка кода, compiler
или linker**. Нового build URL для `d849a30` нет.

По browser-сводке координатора private repository, exact pushed code SHA,
отсутствие активной CI и отключённая платная подписка проверены. Полный raw
browser log автору этого раздела не передан. Оплата не включалась, ресурсы и
лимиты не менялись, обход review/access denial не предпринимался. Все четыре
роли команды выполнены: native/QEMU, Swift/Xcode/IPA audit, независимая
проверка, artifacts/provenance/HANDOFF. Дополнительных CI не запускали.

Последний **реальный** [Apple build `6ad130983ffd2c7f0ad3b5a1`](https://codemagic.io/app/6ad03ce9a8a969b53f3a4aa9/build/6ad130983ffd2c7f0ad3b5a1)
по-прежнему относится к [`ab86fe490027cf35a184f08745b3e4f12b80aa11`](https://github.com/Mi-Yomi/iDeck/commit/ab86fe490027cf35a184f08745b3e4f12b80aa11)
и остановился на pixman TLS reset; native compilation/linking не достигнуты.
Он не проверяет исправление retry в `d849a30`. Подробности этой попытки
и host-проверок сохранены ниже и в
`experiments/linux-guest/evidence/native-download-retry.json`.

Один реальный cloud preflight исправленного helper по точному locked pixman
URL остановился на первой попытке: proxy `403 Forbidden`, **0 bytes**, retry
не выполнен, partial files не осталось. Это подтверждает остановку при access
denial в этой облачной среде; доступность origin и Apple runner этим не
доказана. Локальный `preflight-result.json` проверен на отсутствие секретов и
скопирован **побайтно** в
`experiments/linux-guest/evidence/pixman-cloud-preflight.json` (SHA-256
`c59d5876f740528b6d2b19b035228f8ca121d69579037c099bf049f66bd0dafe`). Никакой новой сетевой проверки при
подготовке этого раздела не выполнялось. Итог блокера:
`experiments/linux-guest/evidence/overnight-quota-blocker.json`.

**Утренний следующий шаг:** получить явное независимое подтверждение ≥120
оставшихся бесплатных macOS минут при отключённой оплате и обычное одобрение
review для отправки. Затем заново проверить private repo, отсутствие активной
CI, clean checkout и полный текущий pushed HEAD, выбрать эту ветку и
`ideck-linux-probe-ipa`, запустить ровно одну сборку с этим SHA. Лимиты
6900 секунд / 120 минут сохраняются; billing и access ограничения не обходить.
После результата сохранить URL, exact SHA, первый реальный отказ и артефакты.
**IPA и его SHA-256 отсутствуют; Linux/JIT на iPhone и Steam не проверены.**

## Последняя Apple-попытка: pixman download reset

[Build `6ad130983ffd2c7f0ad3b5a1`](https://codemagic.io/app/6ad03ce9a8a969b53f3a4aa9/build/6ad130983ffd2c7f0ad3b5a1)
на SHA `ab86fe490027cf35a184f08745b3e4f12b80aa11` завершился **failed**.
Источник сведений в этом разделе — краткая browser-сводка координатора;
полный raw log автору раздела не передан, сводка не выдаётся за полный лог.

- `swift-source-check`: exit 0, 59.852 секунды. Source stage и guest hashes
  приняты; overlay SHA-256
  `b70bc4bfe6ad22b053d5392603ec93fe5176726a851ad5236080cc050e5afeb8`.
- QEMU archive SHA-256
  `7c9605290b34152debb842e965a55d2e4fbba4793e536ab677b4027e5dc0ba1a`
  принят, распаковка прошла с ровно одним ранее разрешённым пропуском symlink.
  Ошибки распаковки и JSON из предыдущей попытки здесь не повторились:
  `result.json` создан.
- Первый новый отказ: `Worker.fetch` при TLS `do_handshake` для
  `https://www.cairographics.org/releases/pixman-0.38.0.tar.gz` —
  `URLError`, внутри `ConnectionResetError`, errno 54. Общее время 126.498 секунды.
  Native library compilation, runtime linking и IPA packaging не достигнуты.

Lock сохраняет pixman 0.38.0: **891 291 байт**, SHA-256
`a7592bef0156d7c27545487a52245669b00cf7e70054505381cff2136d890ca8`.
Отдельная read-only проверка того же URL из облачной среды координатором
получила `Tunnel connection failed: 403 Forbidden`. Это отказ другого proxy,
не объяснение Apple TLS reset. Обход запрета не выполнялся; постоянная
недоступность URL на Apple runner этим не доказана.

В `ci/build_linux_probe_ipa.py` добавлен bounded retry для transient
transport failures и HTTP 408/429/500/502/503/504: не более **3 попыток**, backoff
**2/4 секунды**, общий deadline файла **300 секунд** вместе с попытками,
ожиданием, проверкой и публикацией; он также ограничен остатком worker budget.
Socket timeout — не более 60 секунд. Main-thread `SIGALRM` ограничивает полное
wall-clock время даже при медленном непрерывном ответе; неподдерживаемая среда
или уже активный timer дают отказ, прежний signal handler восстанавливается.
Certificate/SSL, access denial (включая 401/403/407), integrity/size и filesystem
errors, исчерпание бюджета не повторяются. TLS/security checks не отключены.

Каждая попытка пишет собственный exclusive partial. Только полностью проверенный
size/SHA-256 публикуется через no-clobber `os.link`; существующий destination,
включая dangling symlink, не перезаписывается. Собственный partial удаляется и
при ошибке. Диагностика URL/attempt/bytes/duration/error/errno/HTTP status идёт
в stdout и `downloads` в `result.json`; HTTPError response закрывается.
Source URLs, pins, locks, extraction/data_filter, guest checks, native recipe и
workflow не менялись. Старые evidence-снимки сохранены.

Работа ведётся в существующем облачном checkout `/workspace/iDeck`, только в
Linux-ветке, исходный HEAD `00745fb36b444df8d0e4b43842e0d8eb9a65999c`.
**Проверено координатором:** `python3 -B -m unittest discover -s
experiments/linux-guest/tests -v` — **56 host tests PASS**, exit 0, 0.607 секунды,
Python 3.12.14/Linux. Это 20 новых network-free download regressions и 36 прежних
request/source/guest/extraction tests. Проверены transient recovery, предел
попыток/deadlines, fatal SSL/access/integrity/filesystem отказы, partial cleanup,
no-clobber publication и signal timer/handler restoration. Независимый reviewer
не нашёл correctness/security blocker; Swift/Xcode/IPA auditor не установил
дополнительного доказанного blocker до следующего Apple run. Это host-проверки,
не компиляция native implementations или linking с Apple SDK.

Локальный лог: `.work/native-download-retry/host-tests.log`, SHA-256
`b92e977e5a6b7a4cc80de6428290b15bcba75f2143a01ced96a8207292e05a09`; лог не добавлен в Git. Отчёт с hash script/tests/lock:
`experiments/linux-guest/evidence/native-download-retry.json`.

Новая CI из этого checkout не запускалась; ей управляет browser-координатор.
Перед следующим запуском нужны свежие private/free-quota/billing проверки и
точный новый pushed SHA. Лимиты **6900 секунд / 120 минут** сохраняются.
**IPA нет; Linux/JIT на iPhone и Steam не проверены.**

## Распаковка native sources и JSON отчёт — 2026-10-16

По переданному пользователем логу build `6ad129af3ffd2c7f0ad3b35b`, SHA
`3a10400ebf40fc2d1d0578447d6f55b98f2dca66`, Swift gate **прошёл**: worker
продолжил установку build tools/Rust, checkout и подготовку полного Husk.
Следующий отказ — `tarfile.AbsoluteLinkError` на
`qemu-10.0.12-utm/roms/edk2/EmulatorPkg/Unix/Host/X11IncludeHack`. Затем
`finally` скрыл эту причину ошибкой `bytes is not JSON serializable`.
Native library compilation, linker и IPA packaging не запускались.

Исправления в той же Linux-ветке, все новые файлы на E:

- `unpack_source` повторно проверяет исходный size/SHA и пропускает только
  symlink по этому точному пути с target `/opt/X11/include`. Правило явно
  записано в native lock и попадает в отчёт. Другой тип/target, отсутствие
  ожидаемой ссылки или дубликат отклоняются. Остальные файлы проходят прежний
  Python `data_filter`; режим `fully_trusted` не используется.
- Это X11 include для **EDK2 Unix host emulator** (Host.inf, XCODE IA32/X64).
  iOS recipe собирает QEMU dylib, не этот firmware emulator. Пропускается сама
  ссылка, не весь каталог roms/edk2. Содержимое архивов, их URL, size/SHA,
  Git pins и Rust version не изменены.
- `restore_guest` раньше возвращал из `verify()` словарь с байтами трёх файлов;
  теперь возвращает их size/SHA-256. Проверка и сами гостевые bytes не меняются.
  Тот же `write_result` используется в finally и в regression: реальный гостевой
  архив + исключение распаковки теперь дают валидный JSON с исходной ошибкой,
  и исходное исключение продолжает выходить наружу.

**Проверено:** 36 host tests PASS; полный проход `data_filter` по записям всех
семи исходных архивов в Python 3.12.14 обнаружил только указанную абсолютную
ссылку. Negative tests сохраняют отказы для других absolute/outside links,
path traversal, неверных hash и изменённых omission rules. Доказательства и
результат полной распаковки — `experiments/linux-guest/evidence/native-input-fix.json`.
Все 7 реальных архивов полностью распакованы новым helper на Windows/Python
3.12.14 за 359.61 секунды вместе с guest/report check; пропущена ровно одна
указанная ссылка. `native-input-unpack.json` — фактический отчёт этого запуска.
Более медленный дублирующий WSL/Python 3.14 запуск остановлен SIGINT после
463.712 секунды; его частичный каталог сохранён в `.work`, за PASS он не принят.

Новая Apple-сборка из этой сессии не запускалась. Следующий запуск — тот же
`ideck-linux-probe-ipa`, эта же ветка и новый полный pushed SHA; прежний 3a10400
повторять не нужно. Требования текущей бесплатной квоты ≥120 macOS минут,
отключённой оплаты и private repository остаются. Старые evidence JSON ниже
сохраняются как снимки прошлых ревизий, их pending-состояния не переписываются.

## Исправление неполного Swift source archive — 2026-10-16

Пользователь передал полный вывод build `6ad126603ffd2c7f0ad3b258`:
`ideck-linux-probe-ipa`, правильная ветка и SHA
`e9dfb4b3dcfc68b58da5b6ea389b502e4a17a927`. Guard принял запрос. Xcode 27.0
(27A266a), iOS SDK 27.0: profile/evidence typecheck, native syntax и Mac validator
tests прошли; `husk-upstream-typecheck` упал при создании PCH из-за отсутствующего
`husk-console-abi.h`. Native libraries, linker и упаковка IPA не запускались.
Источник этих Apple-результатов — переданный пользователем лог, сохранённый в
`experiments/linux-guest/evidence/codemagic-ipa-e9dfb4b-user-log.txt`.

Причина — неполный подготовленный нами offline source slice: включили
`husk-console-host.h`, но пропустили его локальный include `husk-console-abi.h`.
В архив добавлен **оригинальный** файл из того же Husk commit
`0695248f491cda877f7969d1f0cc89aeede1482e` (blob
`18221e15875818efc166d37513fadea61dc37e57`); прежние 77 файлов byte-identical.
Теперь в архиве 78 файлов. Обновлены archive/overlay locks. Restore проверяет
цепочку всех literal quoted includes из HuskBridge.h до записи файлов на диск.
Это проверка комплектности; Apple compiler gate сохранён полностью.

Проверки исправления: **31 host tests PASS**; новый regression воспроизводит
неполный пакет с корректными хешами и проверяет отказ. Реальный Windows Clang
20.1.3 на старом source slice повторил `husk-console-abi.h file not found`
(exit 1), на исправленном slice с overlay прошёл `-fsyntax-only -x c -Wall
-Wextra -Werror` (exit 0). Системный компилятор использован без установки;
все новые файлы и временные каталоги на E. Распаковка source slice и применение
overlay проверены.
Протокол и хеши — `experiments/linux-guest/evidence/source-header-fix.json`.
Старый `ipa-build-preparation.json` остаётся историческим отчётом предыдущего SHA.

Повтор Apple-сборки здесь **не запускался**. Новый полный SHA после push нужно
указать в том же `ideck-linux-probe-ipa`, на той же Linux-ветке. Не повторять
старый e9dfb4b. Остальные inputs и требование свежей проверки 120 бесплатных
macOS минут/отключённой оплаты не изменены. IPA пока нет; Apple Swift success,
native link, device execution и Steam не заявлены.

Ниже сохранены предыдущие этапы; их «NOT RUN» и 77 файлов относятся к состоянию
до этого запуска и исправления.

## Исправление Codemagic и отдельный IPA workflow — 2026-10-16

Работа остаётся на `codex/linux-guest-feasibility-20261015` в `E:\Freddy Fazbear\iDeck`.
Точный новый commit: `git rev-parse HEAD` после фиксации этой части. Старый
`aea73cfe2ca4b5661a56863ab6dea2908071ed2e` больше не является вершиной после push.

По переданному пользователем результату, build `6ad11d5f3ffd2c7f0ad3af4f` выбрал
**main / a77ab500cdf8c8307af36a58b25816a3fa4d66db**, а не запрошенную Linux-ветку.
Пустой `EXPECTED_SOURCE_COMMIT` старого workflow был отклонён схемой до запуска
компилятора. Это не Swift/linker failure. Raw log этой сборки здесь не получен.

Исправлено в Linux-ветке:

- Все обязательные hash/commit inputs получили непустой sentinel `REQUIRED`.
  Его нельзя принять за разрешённый SHA: новый первый шаг проверяет формат и
  отказывает с понятным сообщением. Defaults подтверждений остаются `false`.
- Linux workflows дополнительно требуют правильные CM_BRANCH, CM_REPO_SLUG,
  CM_COMMIT, точный EXPECTED_COMMIT и clean checkout. Отчёт guard сохраняется.
- Первые 15 workflow сохраняют исходные execution bodies после нового guard.
  Linux source check поднят первым в списке. **main не изменён**; сначала выбрать
  Linux-ветку, затем workflow, иначе CI снова прочитает старый YAML.
- Добавлен шестнадцатый workflow **ideck-linux-probe-ipa**: реальные native builds,
  XcodeGen, xcodebuild, проверка bundle и ad-hoc IPA. Подробности в
  `experiments/linux-guest/ipa/README.md`.
- Отдельный project spec сохраняет реальные app/native sources, QEMU, ANGLE,
  pairing/StikJIT, но исключает embedded MoltenVK/PS4 и Android resource staging.
  Probe-only entry открывает Linux; отдельный bundle ID `dev.ideck.linuxprobe`.
- Проверенные Linux kernel/initramfs/profile теперь действительно включены в Git
  как архив 19 623 827 байт, SHA256
  `f973fe00e1cf54772589c3e54c8bc22a7396604ec927004267f9a4aea9d39efb`.
- Семь официальных native source archives реально скачаны и прочитаны локально;
  размеры/SHA закреплены. Git dependencies и Rust 1.99.1 закреплены. Новый WebKit
  ANGLE pin ещё не проверен Apple-компилятором. Homebrew tool versions фиксируются
  в отчёте каждого запуска; они не объявлены детерминированными.
- Отдельный format-patch исправляет игнорирование ошибок patch/отсутствующего
  dylib в upstream native recipe. Verifiers не ослаблены.

**Проверено здесь:** 30 host tests PASS; nonempty substitutions и сохранение старых
execution bodies в YAML; AST/JSON; полный source+guest stage в
`.work/husk-linux-ipa-staged`; применение native patch; `bash -n` canonical Git
версии shell recipe. Исходный Windows checkout имеет CRLF, поэтому его первый
прямой bash -n отказал на переводах строк; LF-версия из Git прошла. CI checkout
использует core.autocrlf=false. Индекс прежнего source export остаётся
`a305e267ebdb87ec4d202f4f8d5c499cc5ffbe44`; Husk base clean; main не менялся.

**Не выполнено:** server-side YAML validation новой версии, Apple Swift/native
компиляция, линковка, создание IPA, подпись владельцем, device run, Steam. Код
workflow — подготовленный путь сборки, не доказательство её успешности. Новая
сборка из этой сессии не запускалась: browser tool остаётся недоступен; текущая
квота не проверена. Dots, по сообщению пользователя, выполняет отдельную Swift
проверку предыдущего SHA; её итог пока не передан.

Для следующего запуска IPA: выбрать эту ветку и workflow `ideck-linux-probe-ipa`,
новый полный SHA в `expected_commit`, свежие private/free-quota attestations и
`native_build_approved=true`. Нужно **минимум 120 бесплатных macOS минут**, paid
disabled; worker aggregate 6900 секунд, provider cap 120 минут. Это лимит, не ETA.
Настройка Meson/Ninja/pkg-config/XcodeGen/rustup выполняется только на временном
runner. Локальная Windows-система, сертификаты/ключи и телефон не изменяются.
Сам workflow сначала выполняет Swift gate; отдельный повтор source check перед
ним не обязателен. При успехе артефакт `iDeck-Linux-Probe.ipa`, SHA в result.json;
IPA требует обычной подписи владельца для sideload. Нативные outputs сохраняются
в `native-products.tar.gz`, даже если следующая сборка приложения упадёт.

Локальные проверки:

```powershell
$env:TEMP = 'E:\Freddy Fazbear\work\temp'
$env:TMP = $env:TEMP
$env:PYTHONDONTWRITEBYTECODE = '1'
& 'C:\Users\Sevex\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest discover -s experiments/linux-guest/tests -v
git diff --check
git -C .work/source write-tree
```

Ниже сохранены предыдущие состояния; старые формулировки об отсутствии guest
в Git/IPA workflow и старые SHA относятся к прошлым этапам.

## Запрос компиляции: подготовка запуска

Пользователь попросил «скомпиль давай чекать». Ветка для существующего Codemagic:
`codex/linux-guest-feasibility-20261015`, workflow `ideck-linux-guest-profile-check`.
GitHub API подтвердил `Mi-Yomi/iDeck` как private. В workflow добавлено сохранение
`result.json` и отдельных compiler logs; остальные workflow не менялись.

Автоматический доступ к Codemagic сейчас заблокирован неисправностью локального
инструмента: и browser REPL, и Computer Use возвращают `failed to write kernel
assets: Системе не удается найти указанный путь. (os error 3)` до выполнения кода.
Повторная инициализация browser REPL не помогла. Это не ошибка компиляции.
Текущую бесплатную квоту и отключённую оплату проверить не удалось; старое число
66/500 не использовано как актуальное. Запуск Apple worker не подтверждён.

Ручной запуск в существующем приложении
`https://codemagic.io/app/6ad03ce9a8a969b53f3a4aa9`:

1. Проверить, что осталось не менее 10 бесплатных macOS минут и платная подписка
   отключена; выбрать private `Mi-Yomi/iDeck`.
2. Start new build → ветка выше → `ideck-linux-guest-profile-check`.
3. `expected_commit`: полный SHA HEAD этой опубликованной ветки (`git rev-parse
   HEAD`); `free_quota_verified=true`, `private_source_verified=true` только после
   соответствующей проверки. Gate отклонит другой или грязный checkout.
4. Сохранить URL сборки и результат. Успешный status должен быть
   `apple_husk_source_typecheck_and_host_checks_pass`; оба
   `upstream_husk_typechecked` и `integrated_husk_typechecked` должны быть true.

Эта задача проверяет весь настоящий Swift app source с pinned bridge и iOS SDK,
а также компилирует и запускает Mac validator tests. Она ещё не линкует native
QEMU/ANGLE/rppairing и не создаёт IPA. Ошибки baseline и overlay необходимо
разбирать отдельно, не заменяя runtime API заглушками и не ослабляя gates.

## Новое состояние после просьбы продолжить

Работа продолжена в `E:\Freddy Fazbear\iDeck`, ветка `codex/linux-guest-feasibility-20261015`.
Коммит реализации: `5baf235d52b2a5ec64587519e3ad2ec4c0fbd592`. Этот HANDOFF — следующий отдельный коммит; его точный ID: `git log -1 --format=%H -- HANDOFF.md`.
Локальный `main` остался на `a77ab500cdf8c8307af36a58b25816a3fa4d66db`.

Теперь подготовлена **интеграция настоящего Linux-пробника в исходники iOS-приложения Husk**, а не только генератор аргументов QEMU:

- Выбор Linux / прежняя библиотека Husk до создания Android-экрана. Выбор один на процесс; общая JIT-область не переиспользуется другой средой.
- Реальный вызов `qemu_init` / `qemu_main_loop` в отдельном потоке с сохранённым argv; существующие JIT/prewarm и `husk_display_init` / `HuskDisplay`.
- Отдельный каталог сессии, проверка размеров/SHA-256 файлов до старта, IO вне main thread. Android snapshots, GL probe, диски и watchers не вызываются этим маршрутом.
- Два framebuffer проверяются по каждому RGB-каналу каждого пикселя; реальные записи Linux evdev проверяются на нажатие/отпускание A и указателя, обе оси. UI предлагает тап по изображению, Send A и сохранение отчёта.
- Отчёт содержит OS, SHA-256 исполняемого файла приложения, параметры гостя, хеши кадров/serial и отдельные статусы. Physical screen / Steam / accelerated guest GPU не объявляются проверенными.
- Выделение JIT в Husk может быть 512 MiB при запросе TCG 256 MiB; это явно записывается. Безопасного in-process restart/teardown display в pinned bridge нет: после сессии закрыть и открыть приложение. Deadline прекращает сбор доказательств, не убивает общий процесс.

**На Windows Swift и iOS runtime не компилировались и на телефоне не запускались. IPA и Steam Big Picture на iPhone по-прежнему нет.** Интеграция пока является исходниками с подготовленной проверкой Apple SDK.

## Что действительно проверено в продолжении

1. Получен полный clean checkout `Leviidev/Husk` на `0695248f491cda877f7969d1f0cc89aeede1482e`. Исходный checkout `.work/husk-base` не изменён. Патч оформлен через `git format-patch` из отдельного authoring worktree.
2. Итоговая сборочная копия исходников и гостя: `.work/husk-linux-staged-final`. Все изменённые файлы совпали с `husk/overlay.lock.json`. Первая `.work/husk-linux-staged` была sparse-промежуточной и не является полной сборочной копией; сохранена. Теперь stage tool отказывает sparse checkout.
3. В offline source-check архиве **77 настоящих upstream Swift/header/license файлов**, каждый с SHA-256 и original Git blob ID. Архив не содержит native runtime binaries. License/headers сохранены, лицензии проекта не заменялись; старый Playport/Madeira target с QEMU не объединялся.
4. **20 host guard/staging tests PASS**. Host Clang проверил исходный C bridge. AST всех Python-скриптов и YAML проверены; среди CI workflow изменён только ранее добавленный Linux compiler check.
5. Сработал тот же resource stage, который добавлен в Xcode project. Из его выходного каталога `.work/ios-probe-bundle/iDeckLinuxProbe` **повторно реально загружен Linux в Windows QEMU**: оба кадра по 480 000 пикселей и guest keyboard/pointer PASS, 25.125 секунды. Raw run: `.work/linux-boot/run-ios-bundle`.
6. Индекс прежнего восстановленного source export остался **`a305e267ebdb87ec4d202f4f8d5c499cc5ffbe44`**. Ни staged diff прежней работы, ни main не сбрасывались. Push / CI dispatch / signing / device install не было.

Evidence: `experiments/linux-guest/evidence/ios-integration.json`, `host-smoke-ios-bundle.json`, `ios-staging-tests.txt`; общий индекс hashes обновлён. Git-staged bytes проверены против locks. Архив помечен binary; формат-patch сохраняет обязательные пробелы пустых context lines, а применённый source diff отдельно проходит whitespace check.

## Точные команды этой части

PowerShell из корня репозитория; повторный stage требует нового output-каталога.

```powershell
$taskPy = 'C:\Users\Sevex\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:TEMP = 'E:\Freddy Fazbear\work\temp'
$env:TMP = $env:TEMP

& $taskPy -m unittest discover -s experiments/linux-guest/tests -v
& $taskPy experiments/linux-guest/tools/stage_husk.py --upstream .work/husk-base --guest .work/linux-boot/probe-final --out .work/husk-linux-staged-final
& $taskPy .work/husk-linux-staged/scripts/ideck-stage-linux-guest.py .work/husk-linux-staged/guests/ideck-linux .work/ios-probe-bundle/iDeckLinuxProbe
& $taskPy experiments/linux-guest/tools/host_smoke.py --qemu .work/linux-boot/qemu/qemu-system-aarch64.exe --guest .work/ios-probe-bundle/iDeckLinuxProbe --out .work/linux-boot/run-ios-bundle
& 'C:\Program Files\Windhawk\Compiler\bin\clang-20.exe' -fsyntax-only -x c -Wall -Wextra -Werror .work/husk-base/src/app/Husk/HuskBridge.h

git -C .work/source write-tree
git -C .work/husk-base status --short
git diff --cached --check
git -C .work/husk-linux-staged-final diff --cached --check
```

Resource stage в host run использовал первый staged каталог до удаления неиспользуемого Python import; алгоритм и все три полученных файла идентичны итоговому stage. Final source stage уже включает полный checkout, финальный session source и окончательный overlay lock.

## Apple задача и оставшиеся ограничения

Существующий manual `ideck-linux-guest-profile-check` расширен: **480 секунд aggregate, provider cap 10 минут**. Точные clean commit / текущая бесплатная квота / private repository остаются входными gates. Ни текущая доступность Xcode 27 runner, ни квота в этой части не проверялись; задача не отправлялась.

Теперь worker проверяет profile/evidence для iOS, запускает Mac validator tests на реальном ранее записанном serial и negative fixtures, восстанавливает offline source slice и typecheck'ит **исходный и затем patched Husk Swift application против настоящего Apple SDK и HuskBridge.h**. JIT/QEMU API-заглушек нет. Это typecheck Swift/C declarations; не компиляция native implementation bodies, не линковка и не IPA.

Следующая независимая граница — выполнить эту Apple проверку на существующем разрешённом runner, затем собрать pinned Husk с его настоящими native dependency outputs и patched `project.yml`. Для device run: Linux → Enable JIT → Start Linux → увидеть первый кадр → тап и Send A в течение 20 секунд → второй кадр → сохранить отчёт и запись экрана. Снимки Android и сохранения не сбрасывать.

Параллельно будущему этапу остаётся собрать отдельный **glibc ARM64 rootfs + полный официальный Steam с common resources**, затем настоящий client/CEF и Big Picture. Здесь это не делалось. Требования GPU/игр и сведения о старом WIP остаются в предыдущем отчёте ниже.

## Новые hashes

- Offline Husk source-check archive: `044316e0de837a47c5dd1b765b5f15a939a07030ae8415fdd6add8f6bceb823f` (340 363 bytes).
- Overlay lock: `2dc41640bd14d8711259c6b8019349a7f013f5f494485487354cc799c1d6cbd4`.
- Kernel: `47970e0ee0478fe5c60824a89f162d5a353fa29466e5d3bddb0f9c506f1ed756`.
- Initramfs: `5f64312eeef340991c6b0d97bd9d1fb01649c1763e14d7fb8231ad16551e9343`.
- Final session source: `41012830eda0d37ab75e078f76a57300d554afcfdd9f37b6b490d8286e3231e9`.

## Изменённые файлы реализации

```text
.gitattributes
BUILD_PROGRESS.md
README.md
ci/check_linux_guest_profile.py
codemagic.yaml
experiments/linux-guest/README.md
experiments/linux-guest/evidence/artifact-hashes.json
experiments/linux-guest/evidence/host-smoke-ios-bundle.json
experiments/linux-guest/evidence/ios-integration.json
experiments/linux-guest/evidence/ios-staging-tests.txt
experiments/linux-guest/husk/README.md
experiments/linux-guest/husk/husk119-source-check.tar.gz
experiments/linux-guest/husk/overlay.lock.json
experiments/linux-guest/husk/patches/0001-isolated-linux-probe-route.patch
experiments/linux-guest/husk/patches/series
experiments/linux-guest/husk/source-check.lock.json
experiments/linux-guest/ios/LinuxGuestProfile.swift
experiments/linux-guest/ios/LinuxProbeEvidence.swift
experiments/linux-guest/ios/LinuxProbeSession.swift
experiments/linux-guest/ios/LinuxProbeView.swift
experiments/linux-guest/ios/tests/main.swift
experiments/linux-guest/tests/test_staging.py
experiments/linux-guest/tools/stage_bundle.py
experiments/linux-guest/tools/stage_husk.py
experiments/linux-guest/tools/typecheck_source.py
```

---

Ниже сохранён отчёт **предыдущего этапа**. Его формулировки «ещё не интегрировано», бюджет 240 секунд и отсутствие copied Husk source относятся к состоянию до продолжения; актуальные изменения перечислены выше.

# HANDOFF — iDeck, 2026-10-15

## Результат этой сессии

Приоритет пользователя сохранён: настоящий Linux со своим ядром и Linux Steam / Big Picture на iPhone 16 Pro Max, iOS 27. Сделан ограниченный проверяемый шаг: получены официальные ARM64 ELF Steam и реально запущен прямой Linux-гость с проверкой изображения и ввода на Windows-хосте. **Steam на iPhone, Big Picture, iOS JIT/Metal и игры здесь не запускались; IPA нет.**

Все новые рабочие данные находятся на E. Корень: `E:\Freddy Fazbear\iDeck`.

## Git и сохранённая работа

- Ветка: `codex/linux-guest-feasibility-20261015`.
- Исходный transport HEAD / неизменённый локальный main: `a77ab500cdf8c8307af36a58b25816a3fa4d66db`.
- Коммит реализации и evidence: `36d2463190b1fbac503960a30e0f6bf5dccb7e79`.
- Этот HANDOFF сохраняется отдельным следующим локальным коммитом. Его точный ID: `git log -1 --format=%H -- HANDOFF.md`.
- Push, PR, изменение GitHub/main, dispatch CI, подпись или установка на телефон не выполнялись.
- Начальный `git status --short --branch`: чистый `main...origin/main`. Ветка создана до редактирования.
- Репозиторий приватный и является transport-снимком для CI, а не полной историей разработки.
- Снимок восстановлен в `.work/source`: Playport HEAD `412de5f8c0bdd26d84e0127eb5776ba992e3b152` + исходный staged patch. Все **2 023** записи и точное index tree `a305e267ebdb87ec4d202f4f8d5c499cc5ffbe44` проверены штатными hash/tree gates. Original source checkpoint: `1b07a996efe8cec2e12e3d3c1e19805c198fcccf`. Этот staged diff — сохранённая прежняя работа; не сбрасывать.
- Прочитан восстановленный `AGENTS.md` и его локальные изменения к upstream. У transport-репозитория собственного AGENTS.md нет. Реализация добавлена отдельно, старый снимок и dependency pins не обновлялись.
- Первый полный clone был прерван из-за зависшего получения pack; его незавершённый каталог сохранён в `E:\Freddy Fazbear\work\ideck-incomplete-clone-20261015`. Успешный clone использовал `--depth 1 --single-branch` и HTTP/1.1.
- Штатный reconstruction fetch превысил 180 секунд, но FETCH_HEAD был получен. Локальная копия `.work/reconstruct_source_resumed.py` возобновила checkout/apply, сохранив проверку commit/tree/inventory/всех SHA. Исходный `ci/reconstruct_source.py` не менялся.

## Что доступно

1. Transport CI scripts, manifests, pairing source ZIP и архивы прежних native/Wine prerequisites — сохранены.
2. Полный восстановленный экспорт Playport-derived iDeck, включая документацию и исходники приложения — проверен, не пересобран.
3. Дополнения пользователя скопированы в `E:\Freddy Fazbear\inputs\ideck-20261015`: архитектурное решение и диагностический WIP. Архив содержит 16 base / 18 patched текстовых файлов, не полный DroidDeck runtime.
4. WIP: все заявленные hashes проверены; `git apply --check` + применение дают **побайтно тот же patched/**. На Windows необходим `-c core.autocrlf=false`. APK не собирался, runtime/асинхронное поведение не принято. В WIP название blocked-status отличается от `BLOCKED_PROCESS_ISOLATION_UNAVAILABLE` из последнего запроса — это ещё не интегрированный финальный фикс.
5. Официальные Steam ZIP и три выделенных ELF лежат только в `.work/steam-abi`, в Git не добавлены.
6. Linux/QEMU, generated guest assets, raw logs и все неудачные контролируемые прогоны сохранены в `.work/linux-boot`.

В полученном transport и точном source export не найдены полный ранее скомпилированный DroidDeck export, исходный Diagnostic APK/native payloads, архив 200 SHM mock-тестов, содержимое rootfs r9 и полный Android RescueParty log. Их прежние результаты не объявлялись повторно проверенными. Список с hashes: `experiments/linux-guest/evidence/source-inventory.json`.

## Основные новые доказательства

**Steam ABI.** Официальный URL из pinned DroidDeck installer:
`https://client-update.fastly.steamstatic.com/steam_client_steamdeck_publicbeta_linuxarm64`.
Manifest version `1791918634`; SHA-256 `65079d08bbcc0e7fdc3d9b153aadc4c9befc62913c3e4ee0b02425690366f15f`.
Шесть `_linuxarm64_linuxarm64` ZIP проверены по size/SHA-256. Все 87 ELF — AArch64.

| ELF | SHA-256 |
|---|---|
| `steamrtarm64/steam` | `090846de94be2fcd2ffe5475af412687a720f34dda6b96d1daffe2c587316456` |
| `steamrtarm64/steamwebhelper` | `48ceef78c6f9310369fb4baa95d7076b67e6a2fbb5a00dc71f23f076d0d3df01` |
| `steamrtarm64/libcef.so` | `891d85f97231fcafa5763b7140039c5d3cbbb99f2a42ede08de5991abcbc3cdb` |

GNU readelf независимо подтвердил architecture/interpreter/DT_NEEDED. Client и helper требуют `/lib/ld-linux-aarch64.so.1`; максимальные наблюдавшиеся GLIBC version requirements этих трёх файлов: 2.29 / 2.29 / 2.25 соответственно. Самого loader в проверенных ZIP нет. Это не dependency-closure proof и не минимальная glibc-версия всей будущей установки. Для этих клиентских ELF x86-translator не нужен; архитектуру игр/Proton проверять отдельно.

**Реальный Linux host test.** Alpine 3.24.1, kernel `6.18.35-0-virt`, ARM64 Linux, QEMU `virt`, `cortex-a72`, 4 vCPU, 1024 MiB RAM, TCG cache 256 MiB, software virtio-gpu 800×600, virtio keyboard/tablet. Скомпилированный из `guest/fb_probe.c` статический AArch64 ELF выполняет реальные Linux syscalls, framebuffer ioctls и mmap. Это не mock.

Финальный run: `.work/linux-boot/run-final`. Status `host_boot_framebuffer_input_pass`; QEMU exit 0. Два кадра: каждый из **480 000 пикселей** совпал. Guest evdev: KEY_A down/up, ABS_X=8192, ABS_Y=24575, BTN_LEFT down/up. Время хостового прогона 25.953 секунд; это не iPhone benchmark. Raw command line, logs, decoded events и exact hashes сохранены. Коммитный serial log имеет LF и обрезанные конечные пробелы; hash исходного неизменённого raw log указан отдельно.

Первый writer через `dd` не дал надёжного полного scanout: сначала cursor overlay, после отключения курсора — black frame. Проверка осталась строгой. Финальный probe использует mmap + msync + pan/unblank ioctls. В netboot initramfs также не хватало evdev; модуль взят из modloop того же SHA-verified архива и версии ядра.

**Предел host proof:** Windows QEMU 11.1.0 (`v11.1.0-12130-ge470268ff4`) отличается от Husk119 QEMU 10.0.12-utm. iOS split-WX/JIT, Metal, подпись, jetsam, touch-маршрут на телефоне и Steam UI им не проверяются. Alpine/musl — только boot probe; для Steam нужен отдельный glibc rootfs.

## Точные рабочие команды

PowerShell, из указанного каталога. Это запись уже выполненных команд; повторный host run требует нового output-каталога.

```powershell
Set-Location -LiteralPath 'E:\Freddy Fazbear\iDeck'
$taskPy = 'C:\Users\Sevex\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$taskClang = 'C:\Program Files\Windhawk\Compiler\bin\clang-20.exe'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:TEMP = 'E:\Freddy Fazbear\work\temp'
$env:TMP = $env:TEMP

git status --short --branch
git -C .work/source write-tree
& $taskPy experiments/linux-guest/tools/steam_abi.py --work .work/steam-abi

& $taskClang --target=aarch64-linux-gnu -fuse-ld=lld -nostdlib -static -ffreestanding -fno-builtin -fno-stack-protector -O2 -Wall -Wextra -Werror '-Wl,-e,_start' experiments/linux-guest/guest/fb_probe.c -o .work/linux-boot/fb-probe-final

& $taskPy experiments/linux-guest/tools/prepare_guest.py --archive .work/linux-boot/alpine-netboot-3.24.1-aarch64.tar.gz --out .work/linux-boot/probe-final --sevenzip 'C:\Windows\System32\7z.exe' --frame-probe .work/linux-boot/fb-probe-final

& $taskPy experiments/linux-guest/tools/host_smoke.py --qemu .work/linux-boot/qemu/qemu-system-aarch64.exe --guest .work/linux-boot/probe-final --out .work/linux-boot/run-final

& $taskPy experiments/linux-guest/tools/verify_wip.py --archive '../inputs/ideck-20261015/droiddeck-tl-source-fix-WIP-20261015.tar.gz' --out .work/wip-check-lf
& $taskPy -m unittest discover -s experiments/linux-guest/tests -v
git diff --cached --check
```

Compiler: LLVM clang 20.1.3, source revision `923a5c4f83d2b3675bb88e9fe441daeaa4d69488`, installed executable reused read-only. No compiler installation was performed. Guest output is static AArch64 ELF, no PT_INTERP or DT_NEEDED. QEMU was downloaded from the provider linked by qemu.org and unpacked with:

```powershell
7z x .work/linux-boot/qemu-w64-setup-20260811.exe '-o.work/linux-boot/qemu' 'qemu-system-aarch64.exe' '*.dll' 'share/*' 'COPYING*' 'LICENSE*' -r -y
```

The provider SHA-512 and the Alpine provider SHA-256 were checked before using them. Download/research helper sources remain at `E:\Freddy Fazbear\work\ideck-research\fetch_boot_inputs.py`, `collect.py`, `make_evidence.py`. Exact URLs/sizes/checksums are committed in `evidence/boot-inputs.json`. No system-wide installer ran.

Independent ABI command (each of `steam`, `steamwebhelper`, `libcef.so`):

```powershell
wsl -d archlinux --exec readelf -h -l -d '/mnt/e/Freddy Fazbear/iDeck/.work/steam-abi/key-elf/steamrtarm64/steam'
wsl -d archlinux --exec readelf --version-info '/mnt/e/Freddy Fazbear/iDeck/.work/steam-abi/key-elf/steamrtarm64/steam'
```

## Изменённые файлы

Implementation commit:

```text
.gitattributes
BUILD_PROGRESS.md
README.md
ci/check_linux_guest_profile.py
codemagic.yaml
experiments/linux-guest/README.md
experiments/linux-guest/RESEARCH.md
experiments/linux-guest/evidence/artifact-hashes.json
experiments/linux-guest/evidence/boot-inputs.json
experiments/linux-guest/evidence/diagnostic-wip-check.json
experiments/linux-guest/evidence/frame-0.png
experiments/linux-guest/evidence/frame-1.png
experiments/linux-guest/evidence/guest-profile.json
experiments/linux-guest/evidence/guest-serial.log
experiments/linux-guest/evidence/host-guard-tests.txt
experiments/linux-guest/evidence/host-smoke.json
experiments/linux-guest/evidence/readelf-key-objects.txt
experiments/linux-guest/evidence/repositories.lock.json
experiments/linux-guest/evidence/source-inventory.json
experiments/linux-guest/evidence/steam-abi.json
experiments/linux-guest/guest/fb_probe.c
experiments/linux-guest/guest/ideck-init
experiments/linux-guest/ios/LinuxGuestProfile.swift
experiments/linux-guest/ios/tests/main.swift
experiments/linux-guest/tests/test_guards.py
experiments/linux-guest/tools/host_smoke.py
experiments/linux-guest/tools/prepare_guest.py
experiments/linux-guest/tools/steam_abi.py
experiments/linux-guest/tools/verify_wip.py
```

Данный HANDOFF — отдельное добавление. Все ранее существовавшие Codemagic workflow objects проверены YAML-parser'ом: они не изменились; добавлен один manual-only workflow. `.gitattributes` закрепляет LF только для новых experiment/check файлов, чтобы Windows не ломал hash identity. Новые секреты/ключи не создавались; targeted secret scan совпадений не нашёл.

## Что прошло / что не запускалось

- PASS: exact reconstruction tree/inventory; WIP hashes и patch equivalence.
- PASS: официальные package hashes; 87 ELF ABI; независимый GNU readelf ключевых объектов.
- PASS: реальная cross-компиляция guest ELF, actual ARM64 kernel/guest execution, точные framebuffer кадры, decoded evdev input, штатный QMP quit.
- PASS: 9 host guard tests, Python syntax, YAML structure/неизменность старых workflows, git whitespace check, hashes committed evidence.
- NOT RUN: сборка/typecheck `LinuxGuestProfile.swift` с Apple SDK; prepared CI workflow.
- NOT RUN: iOS QEMU linking, IPA, signing/install/device run, Android/WIP APK build, Linux Steam/CEF runtime, Big Picture, пользовательский вход, игры, ускоренный guest GPU.

## Артефакты и SHA-256

| Артефакт | SHA-256 |
|---|---|
| Alpine netboot archive (431008592 bytes) | `54fe38fa41cce740ba379458ed63cfcd89ab06ae5e6a47a06dafe0a34e8427e8` |
| QEMU installer archive (206615928 bytes) | `f98a8aeb5f7faea9765b6dee28316c266cd179d80354a2fed8e50176f9a2e59f` |
| QEMU executable | `952f897511177803722efed6fefe79bc3e7e5a51a026112dfc40f9a37fb0dad2` |
| Guest kernel | `47970e0ee0478fe5c60824a89f162d5a353fa29466e5d3bddb0f9c506f1ed756` |
| Generated initramfs | `5f64312eeef340991c6b0d97bd9d1fb01649c1763e14d7fb8231ad16551e9343` |
| Compiled guest framebuffer probe | `62e9ab98f0730d00e052e2b9b0741070975ccc79229ce8ebe456303b9fee4d3d` |
| Supplied WIP archive | `c94c298326184137a4571ae883b02e7315a5aa4c94b7bab63e286729752fbe52` |

Все committed evidence files: `experiments/linux-guest/evidence/artifact-hashes.json`. Steam binaries остаются локально, не распространяются. Linux/QEMU notices и оригинальные архивы сохранены рядом с рабочими файлами.

## Блокеры и следующий конкретный шаг

1. **Apple compile gate.** Подготовлен `ideck-linux-guest-profile-check` в существующем `codemagic.yaml`, runner M2/Xcode 27.0, aggregate 240 секунд, provider cap 10 минут. Он typecheck'ит реальный Swift profile для arm64 iOS и запускает небольшие synthetic Mac tests. Он не собирает/линкует VM и не создаёт IPA. Входы: exact `expected_commit`, актуальные `free_quota_verified=true` и `private_source_verified=true`. До внешнего push/dispatch нужно актуальное подтверждение квоты/отключённой оплаты; старые 66/500 минут — историческая запись. Здесь задача была локальная, поэтому ничего не отправлено.
2. **iPhone probe integration.** В отдельной Linux session на pinned Husk119 подключить prepared profile/guest и существующие JIT self-test + software display/input. Не использовать Android snapshots/автосохранение/GL policy: `QemuRunner.run()` сейчас содержит общую Android-логику даже вокруг phase0. Не трогать сохранения Husk. Новый Linux session directory обязателен. Проверить те же два кадра и реальные touch/key события на iPhone 16 Pro Max; получить OS build, signed binary hash и логи.
3. **Steam guest.** Отдельный glibc ARM64 disk: фактический loader + DT_NEEDED closure, Xorg/modesetting/software Mesa, полный официальный клиент с `_all` ресурсами. Сначала настоящий `steam -gamepadui` и CEF, затем пользовательский вход и три минуты живой навигации. Нынешний Alpine probe для этого недостаточен.
4. **GPU/games.** Отдельный этап и отдельные измерения; никакие frameblit/JIT/AArch64 результаты не доказывают Metal/Vulkan ускорение гостевых игр. FEX/Box64 выбирать по ELF конкретных игр/Proton, не по названию каталога клиента.
5. **Лицензии.** Исследованные проекты и pins сведены в `RESEARCH.md`. Не склеивать автоматически GPLv3/exception app с QEMU/Husk: перед комбинированным target/distribution проверить конкретные файлы и зависимости. В этой сессии чужой runtime-код не перенесён, лицензия проекта не менялась, публикации не было.

Muguet — подготовленный WASM/AOT, Madeira/Playport — Windows/Wine, CyPort — конкретный macOS Mach-O port, d2r-mobile — конкретная Switch/HLE adaptation. Они дают технические приёмы, но не заменяют отсутствующий Linux guest/Steam proof. REA не понадобился: ABI вопрос удалось закрыть без декомпиляции.
