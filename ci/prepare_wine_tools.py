#!/usr/bin/env python3
"""Approved ephemeral Homebrew prerequisites; run only under bounded CI wrapper."""
import hashlib,json,os,platform,re,subprocess,sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
LOCK=HERE/'homebrew-wine-tools-lock.json'
REVIEWED_HOMEBREW_VERSIONS=frozenset(('5.0.0','5.0.16','5.1.15','6.0.2','6.0.22','7.0.9'))


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
        if got.get('pinned') and not any(r.get('version')==installed_version(got) for r in got.get('installed',[])):
            raise ValueError(f'{name}: pinned older keg cannot satisfy exact install')
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
                # This is the dependency version in the historical install receipt,
                # not the version the current opt symlink resolves to. Actual kegs
                # are validated separately below; preserve differences as evidence.
    # Verify closure so a previously unlisted runtime dependency cannot slip in.
    for want in lock['formulae'].values():
        if not set(want['dependencies'])<=set(rows):raise ValueError('Unlocked runtime dependency')
    if not rows['bison']['keg_only'] or not rows['llvm']['keg_only']:
        raise ValueError('Main tools must remain keg-only')
    return rows


def isolated_environment(out, inherited=None):
    env=dict(os.environ if inherited is None else inherited)
    for key in ('HOMEBREW_BOTTLE_DOMAIN','HOMEBREW_ARTIFACT_DOMAIN','HOMEBREW_API_DOMAIN',
                'HOMEBREW_BREW_GIT_REMOTE','HOMEBREW_CORE_GIT_REMOTE',
                'HOMEBREW_NO_INSTALL_FROM_API','HOMEBREW_FORCE_API_AUTO_UPDATE',
                'HOMEBREW_NO_INSTALL_UPGRADE'):
        env.pop(key,None)
    cache=Path(out)/'homebrew-cache'
    cache.mkdir(exist_ok=False)
    env.update(HOMEBREW_CACHE=str(cache.resolve()),HOMEBREW_NO_AUTO_UPDATE='1',
               HOMEBREW_NO_ANALYTICS='1',HOMEBREW_NO_INSTALL_CLEANUP='1',
               HOMEBREW_NO_INSTALLED_DEPENDENTS_CHECK='1',HOMEBREW_NO_ENV_HINTS='1',
               GIT_TERMINAL_PROMPT='0')
    return env


def validate_keg(name,want,prefix,receipt,cellar=Path('/opt/homebrew/Cellar')):
    version=want['stable']+(f"_{want['revision']}" if want['revision'] else '')
    cellar=cellar.resolve(strict=True)
    expected=cellar/name/version
    actual=Path(prefix).resolve(strict=True)
    if actual!=expected or not actual.is_dir():raise ValueError(f'{name}: actual resolved keg version drift')
    if not actual.is_relative_to(cellar):raise ValueError('Keg outside reviewed Homebrew Cellar')
    if not receipt.get('poured_from_bottle'):raise ValueError(f'{name}: actual keg was not bottled')
    source=receipt.get('source',{})
    if source.get('tap')!='homebrew/core':raise ValueError(f'{name}: actual keg has unreviewed source tap')
    if source.get('versions',{}).get('stable')!=want['stable']:
        raise ValueError(f'{name}: actual receipt source version drift')
    return actual


def historical_dependency_differences(rows,lock):
    differences=[]
    for name,formula in rows.items():
        installed=next(r for r in formula['installed'] if r['version']==installed_version(formula))
        for dep in installed.get('runtime_dependencies',[]):
            target=lock['formulae'][dep['full_name']]
            wanted=target['stable']+(f"_{target['revision']}" if target['revision'] else '')
            historical=dep.get('pkg_version') or dep['version']+(f"_{dep['revision']}" if dep.get('revision') else '')
            if historical!=wanted:
                differences.append({'formula':name,'dependency':dep['full_name'],
                    'historical_receipt_version':historical,'validated_current_keg_version':wanted})
    return differences


def install_command(lock):
    # Explicitly request the already-reviewed runtime closure. Homebrew can
    # otherwise keep an ABI-compatible older dependency, violating our exact
    # current-keg contract. This is install/upgrade, never forced reinstall.
    return ['brew','install','--force-bottle','--formula']+[
        'homebrew/core/'+name for name in lock['formulae']]


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
    env=isolated_environment(out)
    report={'result':'failed','lock_sha256':hashlib.sha256(LOCK.read_bytes()).hexdigest(),
            'bottle_tag':lock['bottle_tag'],'install_command':install_command(lock),
            'scope':'ephemeral build tools only','automatic_linking_of_main_kegs':False,'isolated_api_cache':True,
            'installed_dependents_check_disabled':True,'formula_lock_unchanged':True}
    def run(*args):
        p=subprocess.run(args,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,check=False)
        if p.returncode:raise RuntimeError(f'{args[0]} failed ({p.returncode}): {p.stderr[-12000:]}')
        return p.stdout
    try:
        report['homebrew_version']=run('brew','--version').strip()
        version=re.match(r'^Homebrew ([0-9]+\.[0-9]+\.[0-9]+)(?:\n|$)',report['homebrew_version'])
        if not version or version[1] not in REVIEWED_HOMEBREW_VERSIONS:
            raise ValueError('Unreviewed Homebrew API-cache contract version')
        if run('brew','--prefix').strip()!='/opt/homebrew':raise ValueError('Unexpected Homebrew prefix')
        before=json.loads(run('brew','info','--json=v2','--formula',*['homebrew/core/'+n for n in names]))
        (out/'homebrew-before.json').write_text(json.dumps(before,indent=2)+'\n')
        validate_formulae(before,lock)
        with (out/'homebrew-install.log').open('w') as log:
            subprocess.run(report['install_command'],env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
        after=json.loads(run('brew','info','--json=v2','--formula',*['homebrew/core/'+n for n in names]))
        (out/'homebrew-after.json').write_text(json.dumps(after,indent=2)+'\n')
        rows=validate_formulae(after,lock,installed=True)
        report['installed']={n:[{k:r.get(k) for k in ('version','built_as_bottle','poured_from_bottle','runtime_dependencies')} for r in f['installed'] if r['version']==installed_version(f)] for n,f in rows.items()}
        paths={name:Path(run('brew','--prefix','homebrew/core/'+name).strip()) for name in names}
        report['actual_kegs']={}
        for name,path in paths.items():
            receipt_path=path.resolve(strict=True)/'INSTALL_RECEIPT.json'
            if receipt_path.is_symlink() or not receipt_path.is_file() or receipt_path.stat().st_size>1024*1024:
                raise ValueError(f'{name}: invalid keg receipt')
            receipt_bytes=receipt_path.read_bytes();receipt=json.loads(receipt_bytes)
            actual=validate_keg(name,lock['formulae'][name],path,receipt)
            report['actual_kegs'][name]={'prefix':str(path),'resolved_keg':str(actual),
                'receipt_sha256':hashlib.sha256(receipt_bytes).hexdigest(),
                'source_tap':receipt['source']['tap'],'source_versions':receipt['source']['versions'],
                'poured_from_bottle':True}
        report['historical_receipt_dependency_differences']=historical_dependency_differences(rows,lock)
        tools={'bison':paths['bison']/'bin/bison','llvm-objcopy':paths['llvm']/'bin/llvm-objcopy'}
        report['tools']={}
        for name,path in tools.items():
            owner='llvm' if name=='llvm-objcopy' else name
            if not path.resolve().is_relative_to(Path(report['actual_kegs'][owner]['resolved_keg'])) or not path.is_file():
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
