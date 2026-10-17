#!/usr/bin/env python3
"""Small original FEAT_LSE probe: no Steam payload, VM, network or disk backend.

The instruction matches the observed initial client's SIGILL word (f8e10000).
Passing proves only this atomic operation, not the full client or iOS runtime.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess

WORDS = (
    0xd10043ff,  # sub sp, sp, #16
    0x910003e0,  # mov x0, sp
    0xd2800522,  # mov x2, #41
    0xf9000002,  # str x2, [x0]
    0xd2800021,  # mov x1, #1
    0xf8e10000,  # ldaddal x1, x0, [x0] -- exact observed faulting word
    0xf100a41f,  # cmp x0, #41
    0x1a9f07e0,  # cset w0, ne -- old value must be 41
    0xf94003e2,  # ldr x2, [sp]
    0xf100a85f,  # cmp x2, #42
    0x1a9f07e1,  # cset w1, ne -- stored value must be 42
    0x2a010000,  # orr w0, w0, w1
    0xd2800ba8,  # mov x8, #93 -- Linux exit, no other syscall
    0xd4000001,  # svc #0
)


def build_probe():
    code = struct.pack('<' + 'I' * len(WORDS), *WORDS)
    code_offset = 0x1000
    size = code_offset + len(code)
    header = b'\x7fELF\x02\x01\x01' + bytes(9)
    header += struct.pack('<HHIQQQIHHHHHH', 2, 183, 1, 0x400000 + code_offset,
                          64, 0, 0, 64, 56, 1, 0, 0, 0)
    program = struct.pack('<IIQQQQQQ', 1, 5, 0, 0x400000, 0x400000, size, size, 0x1000)
    return (header + program).ljust(code_offset, b'\0') + code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--qemu-user', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if os.name != 'posix':
        parser.error('run with the existing POSIX user-mode QEMU')
    import resource
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    args.output.mkdir(parents=True, exist_ok=False)
    probe = args.output / 'lse-probe'
    probe.write_bytes(build_probe())
    probe.chmod(0o755)
    records = []
    for cpu in ('cortex-a72', 'cortex-a76', 'max'):
        result = subprocess.run([str(args.qemu_user), '-cpu', cpu, str(probe)],
                                cwd=args.output, capture_output=True, timeout=10,
                                env={'PATH': os.defpath, 'HOME': str(args.output), 'TMPDIR': str(args.output)})
        (args.output / (cpu + '.stderr')).write_bytes(result.stderr)
        records.append({'cpu': cpu, 'returncode': result.returncode,
                        'atomic_old_and_new_values_correct': result.returncode == 0})
    report = {'schema': 1, 'kind': 'original-atomic-instruction-probe', 'instruction': 'ldaddal x1,x0,[x0]',
              'opcode': 'f8e10000', 'feature': 'FEAT_LSE', 'probe_sha256': hashlib.sha256(probe.read_bytes()).hexdigest(),
              'qemu_sha256': hashlib.file_digest(args.qemu_user.open('rb'), 'sha256').hexdigest(),
              'qemu_version': subprocess.check_output([str(args.qemu_user), '--version'], text=True).splitlines()[0],
              'results': records, 'valve_client_executed': False, 'full_vm': False, 'iphone_tested': False}
    (args.output / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
