from pathlib import Path
import importlib.util,json,os,sys
source=Path('/opt/ideck-steam/namespace-check.py')
spec=importlib.util.spec_from_file_location('original_namespace',source)
ns=importlib.util.module_from_spec(spec);spec.loader.exec_module(ns)
ns.guard();operations=[];before=ns.snapshot();ns.private_root(operations);rooted=ns.snapshot()
pre=ns.exec_preflight('inherited-private-real-root')
pidpre=ns.exec_preflight('inherited-private-real-root',True)
assert pre.get('status')==pidpre.get('status')=='pass'
print('IDECK_TOOL_NAMESPACE='+json.dumps({'rooted':rooted,'preflight':pre,'pid_preflight':pidpre}),flush=True)
case=json.loads(sys.argv[1]);assert set(case)=={'argv','seconds','variable'}
record=Path('/home/ideck/steam-experiment-logs/game-run30')/('namespace-'+Path(case['variable']).name+'.json')
with record.open('x') as f:json.dump({'rooted':rooted,'preflight':pre,'pid_preflight':pidpre},f)
env={'PATH':'/usr/bin:/bin','HOME':'/home/ideck','USER':'ideck','LOGNAME':'ideck','LANG':'C.UTF-8',
     'DISPLAY':':0','XAUTHORITY':'/run/user/1000/Xauthority','XDG_RUNTIME_DIR':'/run/user/1000',
     'PRESSURE_VESSEL_VARIABLE_DIR':case['variable'],'WINEPREFIX':case['variable']+'/wineprefix'}
env.pop('WINEPREFIX',None)
env.update({'PYTHONDONTWRITEBYTECODE': '1', 'SteamAppId': '0', 'SteamGameId': '0', 'UMU_ID': 'umu-default', 'UMU_USE_STEAM': '0', 'STEAM_COMPAT_CLIENT_INSTALL_PATH': '/home/ideck/.local/share/Steam', 'STEAM_COMPAT_DATA_PATH': '/opt/ideck-tools-probe29/variables/game30-shared/compatdata', 'PROTON_LOG': '1', 'PROTONFIXES_DISABLE': '1', 'PROTON_LOCAL_SHADER_CACHE': '0', 'PROTON_FSR3_UPGRADE': '0', 'PROTON_FSR4_UPGRADE': '0', 'PROTON_MLFG_UPGRADE': '0', 'PROTON_DLSS_UPGRADE': '0', 'PROTON_XESS_UPGRADE': '0', 'PROTON_USE_OPTISCALER': '0', 'WINEDLLOVERRIDES': 'mscoree,mshtml='})
env.update({'PROTON_LOG_DIR':case['variable']+'/proton-logs','XDG_CACHE_HOME':case['variable']+'/cache','XDG_CONFIG_HOME':case['variable']+'/config'})
if Path(case['variable']).name.endswith('-nosync'):
 env.update({'PROTON_NO_FSYNC':'1','PROTON_NO_ESYNC':'1'})
os.closerange(3,65536)
os.execve('/usr/bin/setpriv',['setpriv','--reuid=1000','--regid=1000','--init-groups',
          'timeout','--kill-after=5s',str(case['seconds'])+'s','dbus-run-session','--',*case['argv']],env)
