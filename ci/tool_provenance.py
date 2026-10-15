"""Read-only exact official Rust component payload verification; never executes files."""
import os
from pathlib import Path, PurePosixPath
import tarfile
from pairing_validate import require, safe_relative, sha


def component_payload(archive, package, target):
    """Follow rust-installer v3 components/manifest.in, the same layout rustup installs."""
    root = f'{package}-1.99.0-{target}'
    rows = {}
    with tarfile.open(archive, 'r:xz') as tar:
        entries = {}
        total = 0
        for m in tar:
            name = m.name.rstrip('/')
            safe_relative(name)
            require(name == root or name.startswith(root + '/'), 'component tar root mismatch')
            require(name not in entries, 'duplicate component tar member')
            require(m.isdir() or m.isfile() or m.issym() or m.islnk(), 'component special member')
            total += m.size
            require(len(entries) < 60000 and total <= 2 * 1024**3 and m.size <= 512 * 1024**2,
                    'component tar cap')
            entries[name] = m
        def read(name):
            m = entries.get(name)
            require(m is not None and m.isfile(), 'missing regular component manifest')
            return tar.extractfile(m).read()
        require(read(root + '/rust-installer-version').strip() == b'3', 'unsupported component format')
        components = read(root + '/components').decode().splitlines()
        expected = package if package != 'rust-std' else package + '-' + target
        require(components == [expected], 'unexpected package component set')
        base = root + '/' + expected + '/'
        manifest = read(base + 'manifest.in').decode().splitlines()
        selected = set()
        for line in manifest:
            kind, sep, relative = line.partition(':')
            require(sep and kind in ('file', 'dir'), 'unsupported component manifest instruction')
            safe_relative(relative)
            name = base + relative
            require(name in entries, 'component manifest refers to absent payload')
            if kind == 'file':
                require(not entries[name].isdir(), 'component file is directory')
                selected.add(name)
            else:
                require(entries[name].isdir(), 'component directory is not directory')
                selected.update(n for n, m in entries.items() if n.startswith(name + '/') and not m.isdir())
        for name in sorted(selected):
            m = entries[name]
            relative = name[len(base):]
            safe_relative(relative)
            if m.issym():
                require(not PurePosixPath(m.linkname).is_absolute(), 'absolute component symlink')
                # Require symlink resolution to remain inside the toolchain (checked again on disk).
                rows[relative] = dict(kind='symlink', target=m.linkname)
            else:
                if m.islnk():
                    require(m.linkname.startswith(base), 'component hardlink escapes component')
                    target_member = entries.get(m.linkname)
                    require(target_member is not None and target_member.isfile(), 'unresolved component hardlink')
                    content = tar.extractfile(target_member).read()
                else:
                    content = tar.extractfile(m).read()
                rows[relative] = dict(kind='file', sha256=sha(content), size=len(content), executable=bool(m.mode & 0o111))
        require(rows, 'empty Rust component payload')
    return rows


def verify_installed(toolchain, payloads):
    expected = {}
    for component, rows in payloads.items():
        for name, row in rows.items():
            require(name not in expected or expected[name] == row, 'conflicting component payload')
            expected[name] = row
    for name, row in expected.items():
        p = toolchain / name
        require(p.resolve().is_relative_to(toolchain.resolve()), 'installed component path escapes toolchain')
        if row['kind'] == 'symlink':
            require(p.is_symlink() and os.readlink(p) == row['target'], 'installed component symlink mismatch')
        else:
            require(p.is_file() and not p.is_symlink(), 'installed component file type mismatch')
            require(p.stat().st_size == row['size'] and sha(p.read_bytes()) == row['sha256'],
                    'installed component bytes mismatch: ' + name)
            require(bool(p.stat().st_mode & 0o111) == row['executable'], 'installed component executable mode mismatch')
    # Only these rustup-generated administrative records may supplement the package payload.
    administrative = {'lib/rustlib/components', 'lib/rustlib/rust-installer-version',
                      'lib/rustlib/multirust-channel-manifest.toml', 'lib/rustlib/multirust-config.toml'}
    administrative.update('lib/rustlib/manifest-' + c for c in payloads)
    extras = []
    for p in toolchain.rglob('*'):
        if p.is_dir() and not p.is_symlink():
            continue
        name = str(p.relative_to(toolchain))
        if name in expected:
            continue
        require(name in administrative and p.is_file() and not p.is_symlink() and not p.stat().st_mode & 0o111,
                'unreviewed installed toolchain payload: ' + name)
        require(p.stat().st_size <= 2 * 1024**2, 'administrative metadata cap')
        extras.append(dict(path=name, sha256=sha(p.read_bytes()), size=p.stat().st_size))
    return dict(payload=expected, administrative=extras)
