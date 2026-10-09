#!/usr/bin/env python3
"""Render any tile data in the ROM as a PNG sheet, to identify graphics.

  gs3_sprites.py ROM ADDR COUNT OUT.png [options]

  ADDR     ROM address or offset of the tile data (or of an LZ block with --lz)
  COUNT    number of 8x8 tiles, or `all` for a whole LZ block
  --bpp 4|8        tile depth (default 4)
  --lz             decompress the block at ADDR first
  --pal ADDR[,N]   palette: BGR555 entries at ADDR (16 or 256; N = sub-palette index for 4bpp);
                   without it a grey ramp is used
  --cols N         tiles per row (default 32)
  --cell WxH       the data is 1D-mapped sprite cells of W x H pixels (e.g. 32x16): each cell's
                   tiles are consecutive; cells are laid out left to right, --cols cells per row
  --scale N        enlarge the output (default 2)

Examples:
  the title menu sprite:   gs3_sprites.py rom.gba 0x0818e300 16 menu.png --cell 32x16 --cols 2 --pal 0x...
  a block of the episode-select sheet:  gs3_sprites.py rom.gba 0x08254d24 all ep.png --lz
"""
import sys, struct, argparse
from _common import *
from _png import write_png, palette_from_bytes
import lz

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('rom'); ap.add_argument('addr', type=num); ap.add_argument('count'); ap.add_argument('out')
    ap.add_argument('--bpp', type=int, choices=(4, 8), default=4)
    ap.add_argument('--lz', action='store_true')
    ap.add_argument('--pal')
    ap.add_argument('--cols', type=int, default=32)
    ap.add_argument('--cell')
    ap.add_argument('--scale', type=int, default=2)
    a = ap.parse_args()
    d = load_rom(a.rom)
    off = rom_off(a.addr)
    if a.lz:
        data, used = lz.decompress(d, off)
    else:
        data = d[off:]
    tsize = 32 if a.bpp == 4 else 64
    count = len(data) // tsize if a.count == 'all' else num(a.count)
    data = data[:count * tsize]
    # palette
    ncol = 16 if a.bpp == 4 else 256
    if a.pal:
        spec = a.pal.split(','); paddr = rom_off(num(spec[0])); sub = int(spec[1]) if len(spec) > 1 else 0
        palette = palette_from_bytes(d[paddr + sub * 32:], ncol)
    else:
        palette = [(i * 255 // (ncol - 1),) * 3 for i in range(ncol)]
    palette[0] = (255, 0, 255) if a.pal is None else palette[0]
    # decode tiles
    tiles = []
    for t in range(count):
        td = data[t * tsize:(t + 1) * tsize]
        if a.bpp == 8: tiles.append(list(td))
        else:
            px = []
            for b in td: px.append(b & 15); px.append(b >> 4)
            tiles.append(px)
    if a.cell:
        cw, ch = (int(x) for x in a.cell.lower().split('x'))
        tw, th = cw // 8, ch // 8
        ncell = count // (tw * th)
        rows_c = -(-ncell // a.cols)
        W, H = a.cols * cw, rows_c * ch
        img = [bytearray(W) for _ in range(H)]
        for c in range(ncell):
            cx, cy = (c % a.cols) * cw, (c // a.cols) * ch
            for k in range(tw * th):
                tile = tiles[c * tw * th + k]
                tx, ty = cx + (k % tw) * 8, cy + (k // tw) * 8
                for i, v in enumerate(tile): img[ty + i // 8][tx + i % 8] = v
    else:
        rows_t = -(-count // a.cols)
        W, H = a.cols * 8, rows_t * 8
        img = [bytearray(W) for _ in range(H)]
        for t, tile in enumerate(tiles):
            tx, ty = (t % a.cols) * 8, (t // a.cols) * 8
            for i, v in enumerate(tile): img[ty + i // 8][tx + i % 8] = v
    if a.scale > 1:
        s = a.scale
        img = [bytes(v for v in row for _ in range(s)) for row in img for _ in range(s)]
        W, H = W * s, H * s
    write_png(a.out, W, H, img, palette)
    print(f'{count} tiles ({a.bpp}bpp) -> {a.out} ({W}x{H})')

if __name__ == '__main__':
    main()
