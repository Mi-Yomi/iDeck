#!/usr/bin/env python3
"""Approved ephemeral Homebrew prerequisites; run only under bounded CI wrapper."""
import hashlib,json,os,platform,re,subprocess,sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
LOCK=HERE/'homebrew-wine-tools-lock.json'


def installed_version(formula):
    stable=formula['versions']['stable']
    return stable+(f"_{formula['revision']}" if formula['revision'] else '')


def validate_formulae(data,lock,installed=False):
    rows={x['name']:x for x in data['formulae']}
    if len(rows)!=len(data['formulae']):raise ValueError('Duplicate formula metadata')
    if set(rows)!=set(lock['formulae']):raise ValueError('Unexpected formula set')
    for name,want in lock['formulae'].items():
        got=rows[name]
        for key in ('name','full_name','tap','revision','version_scheme','keg_only','dependencies','uses_from_macos','ruby_source_path','ruby_source_checksum'):
            if got.get(key)!=want[key]:raise ValueError(f'{name}: changed {key}')
        if got['versions']['stable']!=want['stable']:raise ValueError(f'{name}: version drift')
        if got.get('disabled') or got.get('deprecated'):raise ValueError(f'{name}: unsupported formula')
        bottle=got['bottle']['stable']['files'].get(lock['bottle_tag'])
        if bottle!=want['bottle']:raise ValueError(f'{name}: bottle drift')
        if not bottle['url'].startswith('https://ghcr.io/v2/homebrew/core/') or not re.fullmatch('[a-f0-9]{64}',bottle['sha256']):
            raise ValueError(f'{name}: unexpected bottle provenance')
        if installed:
            matches=[x for x in got['installed'] if x['version']==installed_version(got)]
            if len(matches)!=1 or not matches[0].get('poured_from_bottle'):
                raise ValueError(f'{name}: exact bottled version was not installed')
            for dep in matches[0].get('runtime_dependencies',[]):
                dep_name=dep['full_name']
                if dep_name not in lock['formulae']:raise ValueError(f'{name}: unlocked installed dependency')
                expected=lock['formulae'][dep_name]
                wanted=expected['stable']+(f"_{expected['revision']}" if expected['revision'] else '')
                actual=dep.get('pkg_version') or dep['version']+(f"_{dep['revision']}" if dep.get('revision') else '')
                if actual!=wanted:raise ValueError(f'{name}: installed dependency version drift')
    # Verify closure so a previously unlisted runtime dependency cannot slip in.
    for want in lock['formulae'].values():
        if not set(want['dependencies'])<=set(rows):raise ValueError('Unlocked runtime dependency')
    if not rows['bison']['keg_only'] or not rows['llvm']['keg_only']:
        raise ValueError('Main tools must remain keg-only')
    return rows


def main():
    if len(sys.argv)!=2:raise SystemExit('Usage: prepare_wine_tools.py EVIDENCE_DIRECTORY')
    if os.environ.get('WINE_TOOLS_INSTALL_APPROVED')!='true':
        raise SystemExit('Explicit prerequisite installation approval required')
    if sys.platform!='darwin' or platform.machine()!='arm64' or platform.mac_ver()[0].split('.')[0]!='26':
        raise SystemExit('Reviewed arm64 macOS26 image required')
    out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=True)
    if any((out/n).exists() for n in ('homebrew-before.json','homebrew-after.json','homebrew-install.log','homebrew-tools.json')):
        raise SystemExit('Fresh prerequisite evidence required')
    lock=json.loads(LOCK.read_text());names=list(lock['formulae'])
    env=dict(os.environ,HOMEBREW_NO_AUTO_UPDATE='1',HOMEBREW_NO_ANALYTICS='1',
             HOMEBREW_NO_INSTALL_CLEANUP='1',HOMEBREW_NO_ENV_HINTS='1',GIT_TERMINAL_PROMPT='0')
    # Prevent an inherited custom mirror/tap/domain from replacing official downloads.
    for key in ('HOMEBREW_BOTTLE_DOMAIN','HOMEBREW_ARTIFACT_DOMAIN','HOMEBREW_API_DOMAIN',
                'HOMEBREW_BREW_GIT_REMOTE','HOMEBREW_CORE_GIT_REMOTE'):
        env.pop(key,None)
    report={'result':'failed','lock_sha256':hashlib.sha256(LOCK.read_bytes()).hexdigest(),
            'bottle_tag':lock['bottle_tag'],'install_command':['brew','install','--force-bottle','--formula','bison','llvm'],
            'scope':'ephemeral build tools only','automatic_linking_of_main_kegs':False}
    def run(*args):
        p=subprocess.run(args,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,check=False)
        if p.returncode:raise RuntimeError(f'{args[0]} failed ({p.returncode}): {p.stderr[-12000:]}')
        return p.stdout
    try:
        if run('brew','--prefix').strip()!='/opt/homebrew':raise ValueError('Unexpected Homebrew prefix')
        before=json.loads(run('brew','info','--json=v2','--formula',*names))
        (out/'homebrew-before.json').write_text(json.dumps(before,indent=2)+'\n')
        validate_formulae(before,lock)
        with (out/'homebrew-install.log').open('w') as log:
            subprocess.run(report['install_command'],env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
        after=json.loads(run('brew','info','--json=v2','--formula',*names))
        (out/'homebrew-after.json').write_text(json.dumps(after,indent=2)+'\n')
        rows=validate_formulae(after,lock,installed=True)
        report['installed']={n:[{k:r.get(k) for k in ('version','built_as_bottle','poured_from_bottle','runtime_dependencies')} for r in f['installed'] if r['version']==installed_version(f)] for n,f in rows.items()}
        paths={name:Path(run('brew','--prefix',name).strip()) for name in ('bison','llvm')}
        tools={'bison':paths['bison']/'bin/bison','llvm-objcopy':paths['llvm']/'bin/llvm-objcopy'}
        report['tools']={}
        for name,path in tools.items():
            if not path.resolve().is_relative_to(Path('/opt/homebrew/Cellar')) or not path.is_file():
                raise ValueError('Unexpected installed executable path')
            report['tools'][name]={'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                                   'version':run(str(path),'--version')}
        report['result']='passed'
    except Exception as error:
        report['failure']=str(error);print(str(error),file=sys.stderr)
    finally:
        (out/'homebrew-tools.json').write_text(json.dumps(report,indent=2)+'\n')
    return 0 if report['result']=='passed' else 1

if __name__=='__main__':raise SystemExit(main())
