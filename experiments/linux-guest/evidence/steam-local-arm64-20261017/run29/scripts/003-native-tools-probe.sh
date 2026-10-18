set -eu
export PYTHONDONTWRITEBYTECODE=1
python3 - <<'TOOLS_PROBE'
from pathlib import Path, PurePosixPath
import base64, hashlib, json, os, stat, subprocess, tarfile, time, urllib.request

os.umask(0o022)
out = Path('/home/ideck/steam-experiment-logs/runtime-tools-run29')
out.mkdir(mode=0o700, exist_ok=False)
baseline_namespaces = set()
for proc in Path('/proc').iterdir():
    if proc.name.isdecimal():
        try:
            baseline_namespaces.add(os.readlink(proc / 'ns/mnt'))
        except (FileNotFoundError, ProcessLookupError):
            pass
(out / 'baseline-namespaces.json').write_text(json.dumps(sorted(baseline_namespaces)) + '\n')
stage = Path('/opt/ideck-tools-probe29'); stage.mkdir(mode=0o755, exist_ok=False)
assert 'LD_PRELOAD' not in os.environ
assert os.statvfs(stage).f_bavail * os.statvfs(stage).f_frsize > 4 * 1024**3


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def steam_processes():
    found = []
    for p in Path('/proc').iterdir():
        if not p.name.isdecimal():
            continue
        try:
            exe = os.readlink(p / 'exe')
            if exe.endswith(('/steamrtarm64/steam', '/steamrtarm64/steamwebhelper')):
                found.append(int(p.name))
        except (FileNotFoundError, ProcessLookupError):
            pass
    return found


assert not steam_processes(), 'This test must run before any Steam client'
client_root = Path('/home/ideck/.local/share/Steam')
baseline = json.loads(Path('/home/ideck/steam-experiment-logs/resume-local-20261017-preflight/result.json').read_text())
assert all(digest(client_root / n) == v['sha256'] for n, v in baseline['client'].items())
packages = subprocess.check_output(['dpkg-query', '-W', '-f=${binary:Package}\t${Version}\n'])
source = Path('/opt/ideck-steam/namespace-check.py')
assert digest(source) == '96c929eafefb2f76aa7751fb1869baa6def54e5e31be2a0e6620a486bca64b0d'
assert digest('/usr/local/bin/ideck-steam') == '11cc1c70d2960a745b0f2c31a989eedc3ed23a1f6a95d5be7e6094cd25a7f790'
kernel_before = Path('/proc/vmstat').read_text()
port = int(os.environ['IDECK_CACHE_PORT']); assert 1 <= port <= 65535
archives = [
    ('SteamLinuxRuntime_4-arm64-4.0.20261007.263973.tar.xz', 'SteamLinuxRuntime_4-arm64', 90347988,
     '1ba0221e95e8b6a7722b0c5781aa83c4616dae8e9af492c6e0081169c600fcb8', 7212, 427380612, stage),
    ('GE-Proton11-9-aarch64.tar.gz', 'GE-Proton11-9-aarch64', 647938895,
     '948957ea8929b8a1b444c8b9278f87b7cba0006ccfee51cd551ab69555c34265', 9591, 2168240958,
     stage / 'tool-install/compatibilitytools.d'),
]
receipt = {'archives': [], 'cases': [], 'steam_started': False, 'registered_with_steam': False,
           'game_launch_verified': False, 'iphone_verified': False}


def filtered(member, destination, prefix):
    path = PurePosixPath(member.name)
    assert path.parts and path.parts[0] == prefix
    assert not path.is_absolute() and '..' not in path.parts and chr(0) not in member.name
    assert member.isfile() or member.isdir() or member.issym()
    return tarfile.data_filter(member, str(destination))


# Both cached archives contain relative symlinks, no hardlinks or special files.
for invalid in ('/absolute', '../escape', 'fixture/../../escape'):
    try:
        filtered(tarfile.TarInfo(invalid), stage, 'fixture')
    except (AssertionError, tarfile.FilterError):
        pass
    else:
        raise AssertionError('unsafe extraction accepted')
link = tarfile.TarInfo('fixture/link'); link.type = tarfile.SYMTYPE; link.linkname = '../../outside'
try:
    filtered(link, stage, 'fixture')
except tarfile.FilterError:
    pass
else:
    raise AssertionError('escaping link accepted')

for name, prefix, size, expected, count, expanded, destination in archives:
    destination.mkdir(parents=True, exist_ok=destination == stage)
    archive = stage / name
    url = f'http://10.0.2.2:{port}/client/{name}'
    got = 0; sha = hashlib.sha256()
    with urllib.request.urlopen(url, timeout=30) as response, archive.open('xb') as stream:
        assert response.url == url and int(response.headers['Content-Length']) == size
        while chunk := response.read(1024 * 1024):
            got += len(chunk); assert got <= size
            stream.write(chunk); sha.update(chunk)
        stream.flush(); os.fsync(stream.fileno())
    assert got == size and sha.hexdigest() == expected
    with tarfile.open(archive, 'r:*') as tf:
        members = tf.getmembers()
        assert len(members) == count and len({m.name for m in members}) == count
        assert sum(m.size for m in members if m.isfile()) == expanded
        tf.extractall(destination, members=members, filter=lambda m, d: filtered(m, destination, prefix))
    # Match an ordinary user's tool install; no root code runs from this tree.
    for directory, directories, files in os.walk(destination / prefix, followlinks=False):
        for item in directories + files:
            path = Path(directory) / item
            if path.is_symlink():
                assert path.resolve().is_relative_to((destination / prefix).resolve())
        os.chown(directory, 1000, 1000, follow_symlinks=False)
        for item in directories + files:
            os.chown(Path(directory) / item, 1000, 1000, follow_symlinks=False)
    receipt['archives'].append({'name': name, 'size': size, 'sha256': expected,
                                'members': count, 'regular_expanded_bytes': expanded})
    (out / 'tools-probe.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print('EXTRACTED=' + json.dumps(receipt['archives'][-1]), flush=True)

runtime = stage / 'SteamLinuxRuntime_4-arm64'
proton = stage / 'tool-install/compatibilitytools.d/GE-Proton11-9-aarch64'
manifest = (proton / 'toolmanifest.vdf').read_text()
assert '"require_tool_appid" "4185400"' in manifest
assert '"compatmanager_layer_name" "proton"' in manifest
# The source remains unchanged; new diagnostic calls its existing namespace guards.
helper = Path('/run/ideck/tools-namespace29.py')
helper.write_text('''from pathlib import Path
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
record=Path('/home/ideck/steam-experiment-logs/runtime-tools-run29')/('namespace-'+Path(case['variable']).name+'.json')
with record.open('x') as f:json.dump({'rooted':rooted,'preflight':pre,'pid_preflight':pidpre},f)
env={'PATH':'/usr/bin:/bin','HOME':'/home/ideck','USER':'ideck','LOGNAME':'ideck','LANG':'C.UTF-8',
     'DISPLAY':':0','XAUTHORITY':'/run/user/1000/Xauthority','XDG_RUNTIME_DIR':'/run/user/1000',
     'PRESSURE_VESSEL_VARIABLE_DIR':case['variable'],'WINEPREFIX':case['variable']+'/wineprefix'}
os.closerange(3,65536)
os.execve('/usr/bin/setpriv',['setpriv','--reuid=1000','--regid=1000','--init-groups',
          'timeout','--kill-after=5s',str(case['seconds'])+'s',*case['argv']],env)
''')
helper.chmod(0o600)
vars = stage / 'variables'; vars.mkdir(mode=0o755)
wine = str(proton / 'files/bin-arm64/wine')
entry = str(runtime / '_v2-entry-point')
cases = [
    ('wrap-version', [str(runtime / 'pressure-vessel/bin/pressure-vessel-wrap'), '--version'], 30),
    ('launcher-version', [str(runtime / 'pressure-vessel/bin/steam-runtime-launcher-service'), '--version'], 30),
    ('verify-help', [str(runtime / 'pressure-vessel/bin/pv-verify'), '--help'], 30),
    ('container', [entry, '--verb=waitforexitandrun', '--', '/bin/sh', '-c',
                   'printf "IDECK_RUNTIME4_CONTAINER_OK\\n"; id -u; getconf LONG_BIT; uname -m; cat /usr/lib/os-release'], 180),
    ('wine-version', [wine, '--version'], 30),
    ('container-wine-version', [entry, '--verb=waitforexitandrun', '--', wine, '--version'], 180),
]
namespaces = set()
for name, argv, seconds in cases:
    variable = vars / name; variable.mkdir(mode=0o700); os.chown(variable, 1000, 1000)
    started = time.monotonic()
    result = subprocess.run(['python3', str(helper), json.dumps({'argv': argv, 'seconds': seconds,
                            'variable': str(variable)})], stdin=subprocess.DEVNULL,
                            capture_output=True, timeout=seconds + 90, start_new_session=True)
    (out / (name + '.stdout.log')).write_bytes(result.stdout)
    (out / (name + '.stderr.log')).write_bytes(result.stderr)
    rows = [json.loads(s.split('=', 1)[1]) for s in result.stdout.decode(errors='replace').splitlines()
            if s.startswith('IDECK_TOOL_NAMESPACE=')]
    assert len(rows) == 1
    namespaces.add(rows[0]['rooted']['mount_namespace'])
    receipt['cases'].append({'case': name, 'exit': result.returncode,
              'seconds': round(time.monotonic() - started, 3), 'uid1000_preflights_passed': True,
              'stdout_bytes': len(result.stdout), 'stderr_bytes': len(result.stderr),
              'container_marker': b'IDECK_RUNTIME4_CONTAINER_OK\n1000\n64\naarch64\n' in result.stdout,
              'wine_version_reported': b'GE-Proton11-9' in result.stdout or b'wine-' in result.stdout.lower()})
    (out / 'tools-probe.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print('TOOL_CASE=' + json.dumps(receipt['cases'][-1]), flush=True)

holders = []
for proc in Path('/proc').iterdir():
    if not proc.name.isdecimal():
        continue
    try:
        if os.readlink(proc / 'ns/mnt') not in baseline_namespaces:
            holders.append(int(proc.name))
    except (FileNotFoundError, ProcessLookupError):
        pass
audit = subprocess.run(['dpkg', '--audit'], capture_output=True)
client = {n: {'sha256': digest(client_root / n), 'unchanged': digest(client_root / n) == v['sha256']}
          for n, v in baseline['client'].items()}
receipt['post'] = {'private_namespace_holders': holders, 'steam_processes': steam_processes(),
          'audit_exit': audit.returncode, 'audit_stdout_bytes': len(audit.stdout), 'audit_stderr_bytes': len(audit.stderr),
          'client': client, 'package_versions_unchanged': packages == subprocess.check_output(['dpkg-query','-W','-f=${binary:Package}\t${Version}\n']),
          'namespace_helper_unchanged': digest(source) == '96c929eafefb2f76aa7751fb1869baa6def54e5e31be2a0e6620a486bca64b0d',
          'launcher_unchanged': digest('/usr/local/bin/ideck-steam') == '11cc1c70d2960a745b0f2c31a989eedc3ed23a1f6a95d5be7e6094cd25a7f790'}
def oom(data):
    return int(next(s.split()[1] for s in data.splitlines() if s.startswith('oom_kill ')))
receipt['kernel_oom_kill_before'] = oom(kernel_before)
receipt['kernel_oom_kill_after'] = oom(Path('/proc/vmstat').read_text())
post = receipt['post']
post['ready_for_original_vm_stop'] = not holders and not post['steam_processes'] and all(v['unchanged'] for v in client.values())
(out / 'tools-probe.json').write_text(json.dumps(receipt, indent=2) + '\n')
print('TOOL_POST_CHECK=' + json.dumps(post), flush=True)
assert post['ready_for_original_vm_stop'] and post['package_versions_unchanged']
assert post['namespace_helper_unchanged'] and post['launcher_unchanged']
assert audit.returncode == 0 and not audit.stdout and not audit.stderr

TOOLS_PROBE
