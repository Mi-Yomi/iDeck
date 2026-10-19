# Unified environment source verification

Baseline: `7fdb81605c117fdc03dba8c7dd9fc4dc80beda77`.
`python-tests.log` is the full Linux Python regression output from a real Git
checkout. The five SKIP entries name their requirements in that log.
`verification.json` records scope, independent local checks and explicit limits.
`validation.log` records the successful local validation script completion.

`validate.py` is the exact task-local validation recipe, run from the repository
root. It needs the already authorized retained original payload under
`.work/steam-readback-20261018/restored`, the real pinned cache under
`.work/steam-bundled-gamepad-20261019/owner-cache/`, and a fresh output source
directory (change its `source-unified-final-accessibility` suffix on rerun).
It does not fetch assets, start QEMU, access a user's disk or run Codemagic.
Its protected-file comparisons were executed against the baseline HEAD before
this source commit. The JSON adds a parsed comparison of all workflows and
unchanged cache/guest/bootstrap checks performed separately.

The action-lock regression uses the real generated guest action and real fcntl
locking, with a synthetic installer/cache context. It does not prove real Valve
installation or Swift execution. The new Swift fixtures are wired into the
mandatory Apple gate, but that gate and all new device/UI checks remain NOT RUN.
No account/credential data or Valve payload bytes are included in this folder.
