set -eu
python3 - <<'PY'
from pathlib import Path
import re,json,time
out=Path('/home/ideck/steam-experiment-logs/resume-local-20261017-desktop-zero-v20')
cef=(out/'delta-cef_log.txt').read_text(errors='replace')
html=(out/'delta-steamui_html.txt').read_text(errors='replace')
login=out/'delta-steamui_login.txt'
launcher=(out/'launcher.log').read_text(errors='replace')
sources=re.findall(r'\[(?:ERROR|WARNING|FATAL):([a-zA-Z0-9_.]+)\(\d+\)\]',cef)
terms=('Failed to connect to the bus','GPU process exited','Failed to create','InitializeSandbox','SharedJSContext','OnMainFrameReady','SetLoginState: Success - OK','WaitingForLibraryReady','Failed to connect','Unable to connect','assertion failed')
alltext=cef+'\n'+html+'\n'+(login.read_text(errors='replace') if login.exists() else '')
r={'cef_error_sources':{s:sources.count(s) for s in sorted(set(sources))},'checkpoint_counts':{s:alltext.count(s) for s in terms},'updater_restarts':launcher.count('IDECK_STEAM_STATUS=update_restart_requested'),'launcher_failed': 'IDECK_STEAM_ERROR=' in launcher,'summary_exists':(out/'summary.json').exists()}
(out/'ui-stage.json').write_text(json.dumps(r,indent=2)+'\n');print('UI_STAGE='+json.dumps(r))
PY
