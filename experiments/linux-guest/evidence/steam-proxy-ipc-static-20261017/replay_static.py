#!/usr/bin/env python3
"""Read pinned private ELFs; reproduce bounded text-only static evidence.

No guest execution, networking, image access, binary patching or configuration.
Inputs and the existing private Capstone library are hash-checked before use.
The output directory must be new. No Valve binary is copied to the output.
"""
import argparse
import ctypes
import hashlib
import json
from pathlib import Path
import struct


INPUTS = {
    'steam': (10174384, '73da03ead208a74e14bee566869a4235063dc4a9e1063f29c4608de6d78bd4ea'),
    'steamclient.so': (47744848, '276f021548f9016de834274f4042b796604530d910d114b77ee170b46e409072'),
    'steamui.so': (39120760, '9a59e3bbbee2c6de7a2559986ae5407c01e7416ac5ac2d9e40f11c8aceffc1ee'),
    'chromehtml.so': (2923856, '753ca9cb1aff9740a99c84e0d8a8a1270c2cb081fd1a414696da2a5e8c833ae7'),
}
CAPSTONE = (9334752, '6db7eb6c4b7899a9f7b236e63f0aec33940fb6c7029384e33d69807e4d5fc201')
RANGES = {
    'steam': [
        (0x8ddb0, 0x8dde4), (0x8df30, 0x8df48), (0x8e0e8, 0x8e10c),
        (0xaa380, 0xaa3d4), (0xb26c8, 0xb26e8),
        (0x19a810, 0x19a890), (0x19aa04, 0x19ab50), (0x19acdc, 0x19ad1c),
        (0x19eaf0, 0x19ec18), (0x1a9f70, 0x1aa114), (0x1aa1f4, 0x1aa2d8),
        (0x13fc80, 0x13fcd4), (0x1a8b00, 0x1a8b48), (0x1a942c, 0x1a9444),
    ],
    'steamui.so': [(0xe6c6b8, 0xe6c6dc), (0x1000b88, 0x1000c58)],
    'chromehtml.so': [
        (0x3e268, 0x3e2a8), (0x41040, 0x4104c), (0x46570, 0x465bc),
        (0x46688, 0x46694), (0x4ea10, 0x4ea20), (0x54214, 0x54234),
        (0x5b078, 0x5b114), (0x5b114, 0x5b1b8), (0x5b2dc, 0x5b410),
        (0x5b510, 0x5b524), (0x5ac78, 0x5aca0), (0x53228, 0x532b0),
        (0x5c670, 0x5c6d4), (0x480b8, 0x48138),
    ],
}


def checked(path, expected):
    data = path.read_bytes()
    actual = (len(data), hashlib.sha256(data).hexdigest())
    if actual != expected:
        raise ValueError(f'input identity mismatch: {path.name}')
    return data


class ELF:
    def __init__(self, data):
        self.data = data
        assert data[:6] == b'\x7fELF\x02\x01'
        assert struct.unpack_from('<H', data, 18)[0] == 183
        shoff = struct.unpack_from('<Q', data, 40)[0]
        size, count, names_index = struct.unpack_from('<HHH', data, 58)
        headers = [struct.unpack_from('<IIQQQQIIQQ', data, shoff + i * size)
                   for i in range(count)]
        names_header = headers[names_index]
        names = data[names_header[4]:names_header[4] + names_header[5]]
        keys = ('name', 'type', 'flags', 'addr', 'off', 'size', 'link', 'info', 'align', 'entsize')
        self.sections = {names[h[0]:].split(b'\0')[0].decode(): dict(zip(keys, h)) for h in headers}
        self.maps = [s for s in self.sections.values() if s['flags'] & 2 and s['type'] != 8]
        s = self.sections['.dynsym']
        strings_header = headers[s['link']]
        strings = data[strings_header[4]:strings_header[4] + strings_header[5]]
        symbols = []
        for offset in range(s['off'], s['off'] + s['size'], s['entsize']):
            name = struct.unpack_from('<I', data, offset)[0]
            symbols.append(strings[name:].split(b'\0')[0].decode())
        self.relocs = {}
        self.plt = {}
        for name, s in self.sections.items():
            if s['type'] != 4:
                continue
            for i, offset in enumerate(range(s['off'], s['off'] + s['size'], s['entsize'])):
                address, info, addend = struct.unpack_from('<QQq', data, offset)
                symbol = symbols[info >> 32]
                self.relocs[address] = (info & 0xffffffff, addend, symbol)
                if name == '.rela.plt':
                    self.plt[self.sections['.plt']['addr'] + 32 + i * 16] = symbol

    def offset(self, address):
        for s in self.maps:
            if s['addr'] <= address < s['addr'] + s['size']:
                return s['off'] + address - s['addr']
        raise ValueError(f'unmapped virtual address: {address:#x}')

    def string(self, address):
        return self.data[self.offset(address):].split(b'\0')[0].decode()


class Instruction(ctypes.Structure):
    _fields_ = [('id', ctypes.c_uint), ('address', ctypes.c_uint64),
                ('size', ctypes.c_uint16), ('bytes', ctypes.c_ubyte * 24),
                ('mnemonic', ctypes.c_char * 32), ('op_str', ctypes.c_char * 160),
                ('detail', ctypes.c_void_p)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--elf-dir', required=True, type=Path)
    parser.add_argument('--capstone', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    assert not args.output.exists(), 'output must not already exist'
    binaries = {name: ELF(checked(args.elf_dir / name, identity)) for name, identity in INPUTS.items()}
    checked(args.capstone, CAPSTONE)
    library = ctypes.CDLL(str(args.capstone.resolve()))
    major, minor = ctypes.c_int(), ctypes.c_int()
    library.cs_version(ctypes.byref(major), ctypes.byref(minor))
    assert (major.value, minor.value) == (5, 0)
    library.cs_open.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_size_t)]
    library.cs_disasm.argtypes = [ctypes.c_size_t, ctypes.c_char_p, ctypes.c_size_t, ctypes.c_uint64,
                                 ctypes.c_size_t, ctypes.POINTER(ctypes.POINTER(Instruction))]
    library.cs_disasm.restype = ctypes.c_size_t
    library.cs_free.argtypes = [ctypes.POINTER(Instruction), ctypes.c_size_t]
    handle = ctypes.c_size_t()
    assert library.cs_open(1, 0, ctypes.byref(handle)) == 0

    def decode(data, address):
        instructions = ctypes.POINTER(Instruction)()
        count = library.cs_disasm(handle, data, len(data), address, 0, ctypes.byref(instructions))
        result = [(instructions[i].address, instructions[i].mnemonic.decode(), instructions[i].op_str.decode())
                  for i in range(count)]
        assert sum(instructions[i].size for i in range(count)) == len(data), 'incomplete decoding'
        library.cs_free(instructions, count)
        return result

    assert decode(bytes.fromhex('1f2003d5c0035fd6'), 0x1000) == [(0x1000, 'nop', ''), (0x1004, 'ret', '')]
    chrome = binaries['chromehtml.so']
    vtable = {}
    for slot in range(0, 104, 8):
        address = 0x2af930 + slot
        kind, addend, symbol = chrome.relocs[address]
        assert kind == 1027 and not symbol  # R_AARCH64_RELATIVE
        vtable[str(slot)] = {'relocation': hex(address), 'target': hex(addend)}
    assert vtable['64']['target'] == '0x480b8'
    assert vtable['72']['target'] == '0x4ea10'
    # Independent instruction-field checks for the readiness read and flag set.
    word = struct.unpack_from('<I', chrome.data, chrome.offset(0x4ea10))[0]
    assert word & 0xffc00000 == 0x39400000 and (word >> 10) & 0xfff == 0x20c
    assert (word >> 5) & 31 == 0 and word & 31 == 0
    word = struct.unpack_from('<I', chrome.data, chrome.offset(0x5b3e8))[0]
    assert word & 0xffc00000 == 0x39000000 and (word >> 10) & 0xfff == 0x9c
    assert (word >> 5) & 31 == 19 and word & 31 == 0
    assert 0x170 + 0x9c == 0x20c
    steam = binaries['steam']
    assert steam.string(0x744270) == '-bootstrapperproxy'
    assert steam.string(0x75cc38).startswith('Auto-detected proxy settings:')
    assert steam.string(0x75d2f8).startswith('CONNECT %s HTTP/1.1')
    assert chrome.string(0x1fefa8) == 'ChromeHTML_Controller_003'
    assert chrome.string(0x201b68) == '/tmp/steam_chrome_shmem_uid%d_spid%u'
    args.output.mkdir(mode=0o700)
    outputs = []
    for name, ranges in RANGES.items():
        elf = binaries[name]
        lines = []
        for start, end in ranges:
            lines.append(f'RANGE {start:#x}..{end:#x} (exclusive end)')
            offset = elf.offset(start)
            for address, mnemonic, operands in decode(elf.data[offset:offset + end - start], start):
                comment = ''
                if mnemonic in ('b', 'bl') and operands.startswith('#'):
                    comment = elf.plt.get(int(operands[1:], 0), '')
                lines.append((f'{address:#010x}: {mnemonic:8} {operands}' + (f' ; {comment}' if comment else '')).rstrip())
            lines.append('')
        path = args.output / (name + '.selected-disassembly.txt')
        path.write_text('\n'.join(lines))
        outputs.append({'path': path.name, 'size': path.stat().st_size,
                        'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    report = {'schema': 1, 'scope': 'static pinned ELF inspection only',
              'binaries': {name: {'size': size, 'sha256': sha} for name, (size, sha) in INPUTS.items()},
              'capstone': {'size': CAPSTONE[0], 'sha256': CAPSTONE[1], 'version': [5, 0]},
              'nop_ret_abi_check': 'PASS', 'independent_instruction_field_checks': 'PASS',
              'chrome_controller_vtable_address': '0x2af930', 'slots': vtable,
              'readiness_object_offset': '0x20c', 'ipc_subobject_offset': '0x170',
              'ipc_connection_flag_offset': '0x9c', 'outputs': outputs,
              'network_requests': 0, 'guest_or_disk_execution': False, 'configuration_changes': False}
    (args.output / 'static-replay.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'status': 'PASS', 'checked_binaries': len(INPUTS), 'text_outputs': len(outputs)}))


if __name__ == '__main__':
    main()
