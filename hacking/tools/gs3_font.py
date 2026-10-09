#!/usr/bin/env python3
"""The game's font: 16x16 4bpp glyphs at 0x081f31cc, 128 bytes each, glyph = character code - 0x80.

  gs3_font.py sheet ROM OUT.png [--from CODE] [--to CODE] [--cols N] [--addr ADDR]
        render the glyphs with their character code under each one (default codes 0x80..0x67f)
  gs3_font.py glyph ROM CODE [--addr ADDR]
        print one glyph as text
  gs3_font.py put ROM CODE IN.png OUT.gba [--addr ADDR]
        replace one glyph with a 16x16 indexed PNG (pixel values 0..3: 0 transparent, 3 full
        colour, 1 and 2 are the partial levels the engine masks with the colour index)

The sheet is the quickest way to build a character table for gs3_script.py --table.
Use --addr for a ROM whose font has been moved (the English build replaces this area).
"""
import sys, argparse
from _common import *
from _png import write_png, read_png

FONT = 0x081f31cc
NGLYPH = 0x600
GLYPH_BYTES = 128

DIGITS = {  # 3x5 hex digits for the labels
    '0': ['111', '101', '101', '101', '111'], '1': ['010', '110', '010', '010', '111'],
    '2': ['111', '001', '111', '100', '111'], '3': ['111', '001', '111', '001', '111'],
    '4': ['101', '101', '111', '001', '001'], '5': ['111', '100', '111', '001', '111'],
    '6': ['111', '100', '111', '101', '111'], '7': ['111', '001', '001', '001', '001'],
    '8': ['111', '101', '111', '101', '111'], '9': ['111', '101', '111', '001', '111'],
    'a': ['010', '101', '111', '101', '101'], 'b': ['110', '101', '110', '101', '110'],
    'c': ['111', '100', '100', '100', '111'], 'd': ['110', '101', '101', '101', '110'],
    'e': ['111', '100', '111', '100', '111'], 'f': ['111', '100', '111', '100', '100'],
}

def glyph_pixels(d, base, code):
    """-> 16 rows of 16 values (0..15) ; tiles TL, TR, BL, BR."""
    o = rom_off(base) + (code - 0x80) * GLYPH_BYTES
    g = d[o:o + GLYPH_BYTES]
    rows = [[0] * 16 for _ in range(16)]
    for t in range(4):
        tx, ty = (t % 2) * 8, (t // 2) * 8
        td = g[t * 32:(t + 1) * 32]
        for y in range(8):
            for x in range(8):
                b = td[y * 4 + x // 2]
                rows[ty + y][tx + x] = b & 15 if x % 2 == 0 else b >> 4
    return rows

def cmd_sheet(a):
    d = load_rom(a.rom)
    lo, hi = a.lo, a.hi
    n = hi - lo + 1
    cols = a.cols; cw, ch = 18, 24
    W = cols * cw; H = -(-n // cols) * ch
    img = [bytearray(W) for _ in range(H)]
    for k in range(n):
        code = lo + k
        x0, y0 = (k % cols) * cw, (k // cols) * ch
        rows = glyph_pixels(d, a.addr, code)
        for y in range(16):
            for x in range(16):
                v = rows[y][x]
                if v: img[y0 + 1 + y][x0 + 1 + x] = 4 + min(v, 3)   # 5..7 = ink levels
        label = f'{code:x}'
        lx = x0 + 1
        for chh in label[-4:]:
            pat = DIGITS[chh]
            for yy in range(5):
                for xx in range(3):
                    if pat[yy][xx] == '1': img[y0 + 18 + yy][lx + xx] = 2
            lx += 4
    pal = [(24, 24, 40), (0, 0, 0), (120, 200, 255), (0, 0, 0), (0, 0, 0), (110, 110, 110), (190, 190, 190), (255, 255, 255)]
    if a.scale > 1:
        s = a.scale
        img = [bytes(v for v in row for _ in range(s)) for row in img for _ in range(s)]
        W, H = W * s, H * s
    write_png(a.out, W, H, img, pal + [(0, 0, 0)] * (256 - len(pal)))
    print(f'{n} glyphs ({lo:#x}..{hi:#x}) -> {a.out}')

def cmd_glyph(a):
    d = load_rom(a.rom)
    for row in glyph_pixels(d, a.addr, a.code):
        print(''.join(' .:#'[min(v, 3)] for v in row))

def cmd_put(a):
    rom = bytearray(load_rom(a.rom))
    w, h, mode, rows, pal = read_png(a.infile)
    if (w, h) != (16, 16) or mode != 'P': sys.exit('need a 16x16 indexed PNG')
    out = bytearray()
    for t in range(4):
        tx, ty = (t % 2) * 8, (t // 2) * 8
        for y in range(8):
            for x in range(0, 8, 2):
                out.append((rows[ty + y][tx + x] & 15) | ((rows[ty + y][tx + x + 1] & 15) << 4))
    o = rom_off(a.addr) + (a.code - 0x80) * GLYPH_BYTES
    rom[o:o + GLYPH_BYTES] = out
    save_rom(rom, a.out)

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('sheet'); p.add_argument('rom'); p.add_argument('out')
    p.add_argument('--from', dest='lo', type=num, default=0x80); p.add_argument('--to', dest='hi', type=num, default=0x80 + NGLYPH - 1)
    p.add_argument('--cols', type=int, default=32); p.add_argument('--scale', type=int, default=1)
    p.add_argument('--addr', type=num, default=FONT); p.set_defaults(fn=cmd_sheet)
    p = sub.add_parser('glyph'); p.add_argument('rom'); p.add_argument('code', type=num); p.add_argument('--addr', type=num, default=FONT)
    p.set_defaults(fn=cmd_glyph)
    p = sub.add_parser('put'); p.add_argument('rom'); p.add_argument('code', type=num); p.add_argument('infile'); p.add_argument('out')
    p.add_argument('--addr', type=num, default=FONT); p.set_defaults(fn=cmd_put)
    a = ap.parse_args(); a.fn(a)

if __name__ == '__main__':
    main()
