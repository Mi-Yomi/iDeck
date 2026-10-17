"""Run extracted Debian amd64 tools with their matching ELF loader/libc.

LD_LIBRARY_PATH alone mixes the host interpreter with the pinned libc on e.g.
Arch WSL. Keep the entire loader/library pair inside the authenticated extraction;
no system installation, binary rewriting or guest-runtime substitute is needed.
"""
from pathlib import Path


def command(host, argv):
    host=Path(host)
    library=host/'usr/lib/x86_64-linux-gnu'
    loader=library/'ld-linux-x86-64.so.2'
    binary=Path(argv[0])
    if (not loader.is_file() or loader.is_symlink() or not binary.is_file()
            or not binary.resolve().is_relative_to(host.resolve())):
        raise ValueError('missing/outside pinned GUI host tool or ELF loader')
    return [str(loader),'--library-path',str(library),*[str(a) for a in argv]]
