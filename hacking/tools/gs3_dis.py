#!/usr/bin/env python3
"""Disassembly and cross-reference helper for the ROM.

  gs3_dis.py dis  ROM ADDR [COUNT] [--arm]   disassemble COUNT instructions (needs `pip install capstone`);
                                             pc-relative loads are annotated with the literal's value
  gs3_dis.py xref ROM VALUE                  where VALUE appears: as an aligned 32-bit literal (pointer
                                             tables, literal pools; VALUE and VALUE|1 are both tried)
                                             and as the target of Thumb `bl` instructions
  gs3_dis.py pool ROM ADDR COUNT             dump COUNT 32-bit words at ADDR, marking ROM/RAM pointers
  gs3_dis.py hex  ROM ADDR [LEN]             hex dump

No capstone is needed for xref, pool and hex.
"""
import sys, struct, argparse
from _common import *

def annotate_literal(g, ins_addr, op_str):
    try:
        imm = int(op_str.split('#')[1].rstrip(']'), 0)
        p = ((ins_addr + 4) & ~3) + imm
        return struct.unpack_from('<I', g, rom_off(p))[0]
    except Exception:
        return None

def cmd_dis(a):
    try:
        from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_ARM
    except ImportError:
        sys.exit('capstone is not installed: pip install capstone')
    g = load_rom(a.rom)
    addr = a.addr & ~1
    md = Cs(CS_ARCH_ARM, CS_MODE_ARM if a.arm else CS_MODE_THUMB)
    off = rom_off(addr)
    n = 0
    for ins in md.disasm(g[off:off + a.count * 4 + 8], rom_addr(addr)):
        s = f'{ins.address:08x}  {ins.bytes.hex():<10} {ins.mnemonic:<7} {ins.op_str}'
        if ins.mnemonic.startswith('ldr') and '[pc' in ins.op_str:
            v = annotate_literal(g, ins.address, ins.op_str)
            if v is not None: s += f'   ; ={v:#x}'
        print(s); n += 1
        if n >= a.count: break

def thumb_bl_targets(g):
    """Yield (site, target) for every Thumb bl pair in the ROM (sites are even offsets)."""
    L = len(g) - 4
    for i in range(0, L, 2):
        h1 = g[i] | (g[i + 1] << 8)
        if (h1 & 0xf800) != 0xf000: continue
        h2 = g[i + 2] | (g[i + 3] << 8)
        if (h2 & 0xf800) != 0xf800: continue
        off = ((h1 & 0x7ff) << 12) | ((h2 & 0x7ff) << 1)
        if off & 0x400000: off -= 0x800000
        yield i, i + 4 + off

def cmd_xref(a):
    g = load_rom(a.rom)
    v = a.value
    cands = {v, v | 1} if v >= 0x08000000 or 0x02000000 <= v < 0x04000000 else {v}
    print(f'literals equal to {" / ".join(f"{c:#x}" for c in sorted(cands))}:')
    n = 0
    for c in sorted(cands):
        pat = struct.pack('<I', c); i = 0
        while True:
            i = g.find(pat, i)
            if i < 0: break
            if i % 4 == 0: print(f'  {rom_addr(i):#x}'); n += 1
            i += 1
    print(f'  ({n} found)')
    if 0x08000000 <= v < 0x08000000 + len(g):
        t = rom_off(v) & ~1
        sites = [rom_addr(s) for s, tgt in thumb_bl_targets(g) if tgt == t]
        print(f'thumb bl to {rom_addr(t):#x}: {len(sites)} site(s)')
        for s in sites[:200]: print(f'  {s:#x}')

def cmd_pool(a):
    g = load_rom(a.rom)
    off = rom_off(a.addr) & ~3
    for k in range(a.count):
        v = struct.unpack_from('<I', g, off + 4 * k)[0]
        tag = ''
        if 0x08000000 <= v < 0x08000000 + len(g): tag = 'ROM' + (' (thumb)' if v & 1 else '')
        elif 0x02000000 <= v < 0x02040000: tag = 'EWRAM'
        elif 0x03000000 <= v < 0x03008000: tag = 'IWRAM'
        elif 0x04000000 <= v < 0x04000400: tag = 'I/O'
        elif 0x05000000 <= v < 0x05000400: tag = 'palette'
        elif 0x06000000 <= v < 0x06018000: tag = 'VRAM'
        elif 0x07000000 <= v < 0x07000400: tag = 'OAM'
        print(f'{rom_addr(off + 4 * k):#x}: {v:08x}  {tag}')

def cmd_hex(a):
    g = load_rom(a.rom)
    off = rom_off(a.addr)
    for i in range(off, off + a.length, 16):
        chunk = g[i:i + 16]
        print(f'{rom_addr(i):#x}: {chunk.hex(" ")}  {"".join(chr(b) if 32 <= b < 127 else "." for b in chunk)}')

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('dis'); p.add_argument('rom'); p.add_argument('addr', type=num); p.add_argument('count', nargs='?', type=num, default=40)
    p.add_argument('--arm', action='store_true'); p.set_defaults(fn=cmd_dis)
    p = sub.add_parser('xref'); p.add_argument('rom'); p.add_argument('value', type=num); p.set_defaults(fn=cmd_xref)
    p = sub.add_parser('pool'); p.add_argument('rom'); p.add_argument('addr', type=num); p.add_argument('count', type=num); p.set_defaults(fn=cmd_pool)
    p = sub.add_parser('hex'); p.add_argument('rom'); p.add_argument('addr', type=num); p.add_argument('length', nargs='?', type=num, default=64); p.set_defaults(fn=cmd_hex)
    a = ap.parse_args(); a.fn(a)

if __name__ == '__main__':
    main()
