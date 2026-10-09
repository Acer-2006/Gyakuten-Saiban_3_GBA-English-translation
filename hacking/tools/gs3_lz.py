#!/usr/bin/env python3
"""LZ10 (GBA BIOS LZ77, type byte 0x10) decompress / compress / scan.

  gs3_lz.py d FILE ADDR OUT.bin         decompress the block at ADDR of FILE (a ROM address or an offset)
  gs3_lz.py c IN.bin OUT.lz [--wram]    compress (default output is safe for VRAM: no distance-1 copies)
  gs3_lz.py scan ROM [--min N] [--max N]
        list every 4-byte-aligned position that decompresses cleanly, with the compressed and
        decompressed sizes (default: decompressed size 32..0x40000 bytes)
"""
import sys, struct, argparse
from _common import *
import lz

def try_decompress(d, off, max_size):
    """Strict decoder: returns (size, used) or None if the block is not well-formed."""
    if d[off] != 0x10: return None
    size = d[off + 1] | (d[off + 2] << 8) | (d[off + 3] << 16)
    if size == 0 or size > max_size: return None
    p = off + 4; n = 0; L = len(d)
    while n < size:
        if p >= L: return None
        flags = d[p]; p += 1
        for bit in range(8):
            if n >= size: break
            if flags & (0x80 >> bit):
                if p + 2 > L: return None
                b1, b2 = d[p], d[p + 1]; p += 2
                cnt = (b1 >> 4) + 3; disp = ((b1 & 0xF) << 8 | b2) + 1
                if disp > n: return None
                n += cnt
            else:
                p += 1; n += 1
    if n != size: return None
    return size, p - off

def cmd_d(a):
    d = open(a.rom, 'rb').read()
    out, used = lz.decompress(d, rom_off(a.addr))
    open(a.out, 'wb').write(out)
    print(f'{rom_addr(a.addr):#x}: {used} compressed bytes -> {len(out)} bytes, written to {a.out}')

def cmd_c(a):
    data = open(a.infile, 'rb').read()
    out = lz.compress(data, vram_safe=not a.wram)
    open(a.out, 'wb').write(out)
    print(f'{len(data)} -> {len(out)} bytes ({len(out) * 100 // max(1, len(data))}%)')

def cmd_scan(a):
    d = load_rom(a.rom)
    n = 0
    print('  address    comp     dec')
    for off in range(0, len(d) - 4, 4):
        if d[off] != 0x10: continue
        r = try_decompress(d, off, a.max)
        if r is None or r[0] < a.min: continue
        size, used = r
        if used < 8 or used > size + 16: continue        # a real block is never bigger than its contents
        print(f'{rom_addr(off):#x}  {used:6}  {size:6}')
        n += 1
    print(f'{n} blocks')

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('d'); p.add_argument('rom'); p.add_argument('addr', type=num); p.add_argument('out'); p.set_defaults(fn=cmd_d)
    p = sub.add_parser('c'); p.add_argument('infile'); p.add_argument('out'); p.add_argument('--wram', action='store_true'); p.set_defaults(fn=cmd_c)
    p = sub.add_parser('scan'); p.add_argument('rom'); p.add_argument('--min', type=num, default=32); p.add_argument('--max', type=num, default=0x40000)
    p.set_defaults(fn=cmd_scan)
    a = ap.parse_args(); a.fn(a)

if __name__ == '__main__':
    main()
