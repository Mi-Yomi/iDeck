# iDeck launcher and session navigation

Baseline: `cd19729dee56f7e4294def4763fde451dca88cc6`, Steam branch only.
The follow-up from `d1e9d20988599e3b06477421c14ed1b2a59f8811` corrects the two
read-only review findings: active probe diagnostics now uses its own report,
without terminal fallback/refresh; waiting/error text scrolls inside the display
while the report action remains fixed outside that scroll area. Lifecycle and
runtime code are unchanged by this follow-up. Narrow portrait is structurally
addressed; visual/device validation remains NOT RUN.

The previous route allowed one selection from its chooser and had no Home path.
Desktop/terminal disappearance also cancelled preparation, so adding a simple
back button would have cancelled a pending start. Actual runtime ownership was
already independent of views: static session objects retain their workers,
native thread, sockets and disk owner. Pinned HuskMetalView teardown removes its
observer/releases input; it does not stop QEMU or release the disk.

Home and resume now change only screen selection. They do not enable/reset JIT,
start/stop QEMU, cancel preparation or release a disk. The existing one-use native
entry guard is unchanged. After any native attempt, including failure, recovery
or clean Stop, its environment remains reserved; another VM requires a new app
process. Before an attempt, profile selection can change. Leaving a desktop view
releases input. Explicit Cancel start and app-background preparation cancellation
remain; the root handles background even while Home is shown. Live VM shutdown
still requires the existing Stop path. Full Husk library content remains mounted
behind Home and its initialization runs only once.

The main route uses the existing Husk Theme, adaptive cards and system safe
areas: Steam / Big Picture, desktop and settings, plus actual session status and
resume. Actions open the real environment; there is no simulated game library or
claimed Steam success. Steam keeps its separate disk and explicit network consent
and official installer. Tests/console modes are under Advanced; keyboard/game
input is in a collapsible panel. Diagnostics remains reachable from every route,
with direct Share report on blocked starts. GUI recovery is available under
Diagnostics before an attempt; its existing transaction/generator is unchanged.

The phone's black-window cause remains **unknown**. The existing bridge's atomic
frame sequence is now observed without frame copies/BQL polling. While preparing
or waiting, the UI shows actual startup/recovery messages over the real display.
A 60-second missing-frame observation is exported; a late real frame can still
appear. A frame sequence is not proof of non-black pixels or a Steam window.
GUI readiness and the guest Steam status remain separate. Steam actions without
completion acknowledgement after 180 seconds offer a report message; the timer
does not kill/retry the installer, clear its busy guard or claim failure/success.
These bounded observations are included in Markdown reports. A current device
report (source/build, mode, status, storage failure and Steam/GUI stage) is still
needed to diagnose the specific phone behavior.

Validation after follow-up: **545 Python tests OK (540 PASS, 5 SKIP)**, generator/strict recovery
gates, actual git attributes, full 81-file/five-patch source overlay and real sealed
Steam stage/repeat/resource verification without file_digest PASS. Production
Foundation Home/resume/repeated-tap/sticky-owner checks are added to the mandatory
Apple gate via `LINUX_LAUNCHER_NAVIGATION_PASS`. No new dependency, payload rebuild,
Release, secret, main, phone disk or recovery/owner/fsync weakening.

New Swift/Apple/native IPA, visual portrait/landscape and actual phone Home/resume
are **NOT RUN** here; CI was not dispatched. Parent checks fresh free quota before
one build for the exact new pushed SHA. The previously delivered recovery IPA was
built at `9018b9bfbaab7b50d6011ae1e29e5eba0995fd28` and does not include this UX.
BusyBox provenance remains **OPEN**.
