"""The dxmt revision the fork's winemetal / dxmt / airconv patch checks start from.

madeira-bcd: since the 2026-10-15 upstream merge the dxmt pin (128b297) carries
the fork's patches that went upstream (willfaust/dxmt #9 and #21-#33), so a
check that applies a patch to the pin as committed would find it already there.
Those checks start from OVERLAY_BASE, the pin the patches were written against,
instead: rev() names it (fetched into the dxmt checkout when a shallow clone
lacks it) when the pin carries the wave, else HEAD as before. CI builds from the
new pin plus the same patches, which leaves the same files (the pin's own
additions are those patches' output; checked when the merge was made).
"""
from pathlib import Path
import subprocess

OVERLAY_BASE = 'db546ee466ad50ec6463edb5fa183de11db43761'
PIN_MARKER = 'madeira_rp_lean_on'   # willfaust/dxmt#26, in the wave's pin and later
# Modified for iDeck-BCD, 2026-10-20: the submodule's origin (thebcd69/bcd-dxmt) does not serve
# OVERLAY_BASE by its hash ("not our ref"); the public DXMT forks the pin came from do. origin
# is still tried first.
FALLBACK_REMOTES = ('https://github.com/willfaust/dxmt.git', 'https://github.com/3Shain/dxmt.git')


def fetch_commit(repo, sha, fallbacks):
    """Fetch one commit by its hash into a (shallow) checkout: origin, then each fallback URL."""
    for src in ('origin',) + tuple(fallbacks):
        if subprocess.run(['git', '-C', str(repo), 'fetch', '-q', '--depth=1', src, sha],
                          capture_output=True).returncode == 0:
            return
    raise SystemExit(f'{sha} could not be fetched into {repo} from origin or {", ".join(fallbacks)}')


def rev(dxmt):
    dxmt = Path(dxmt)
    wm = dxmt / 'src/winemetal/unix/winemetal_unix.c'
    if not wm.is_file() or PIN_MARKER not in wm.read_text(errors='ignore'):
        return 'HEAD'
    have = subprocess.run(['git', '-C', str(dxmt), 'cat-file', '-e', OVERLAY_BASE + '^{commit}'], capture_output=True)
    if have.returncode:
        fetch_commit(dxmt, OVERLAY_BASE, FALLBACK_REMOTES)
    return OVERLAY_BASE
