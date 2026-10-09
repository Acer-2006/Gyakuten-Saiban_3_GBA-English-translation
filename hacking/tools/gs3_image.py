#!/usr/bin/env python3
"""Chunked images (full-screen pictures: backgrounds, the title screen) <-> PNG.

  gs3_image.py list    ROM                         the image table at 0x0803b3a4 (145 entries)
  gs3_image.py extract ROM ENTRY|ADDR OUT.png [--width TILES]
  gs3_image.py build   IN.png OUT.bin [--bpp 4|8] [--width TILES]
        make a chunked image object from an indexed PNG (16 or 256 colours)
  gs3_image.py insert  ROM ENTRY IN.png OUT.gba [--at ADDR]
        build the object from the PNG, store it in free space (or at ADDR) and point every
        table entry that used the old object at it

ENTRY is an index into the image table; ADDR (0x08......) names an object directly.
The PNG written by `extract` is indexed, so an edit that keeps the palette round-trips; a
PNG with a new palette is fine too (first colour = transparent/backdrop as in the original).
Pictures are 30 tiles (240 px) wide unless --width says otherwise.
"""
import sys, struct, argparse
from _common import *
from _png import write_png, read_png, palette_from_bytes, rgb_to_bgr555
import lz

TABLE = 0x0803b3a4
TABLE_N = 145

def load_object(d, base):
    """-> (bpp, palette bytes, tile bytes, [chunk sizes])"""
    first = struct.unpack_from('<I', d, base)[0]
    n = first // 4
    if n == 0 or n > 64 or first % 4: raise ValueError('not a chunked image')
    offs = struct.unpack_from('<%dI' % n, d, base)
    for palsz, bpp in ((512, 8), (32, 4)):
        q = base + offs[0] + palsz
        if q < len(d) and d[q] == 0x10:
            try:
                first_chunk, _ = lz.decompress(d, q)
            except Exception:
                continue
            pal = d[base + offs[0]: base + offs[0] + palsz]
            chunks = [first_chunk] + [lz.decompress(d, base + offs[k])[0] for k in range(1, n)]
            return bpp, pal, b''.join(chunks), [len(c) for c in chunks]
    raise ValueError('not a chunked image')

def build_object(pal, tiles, nchunks=10):
    tile_bytes = len(tiles)
    per = -(-tile_bytes // nchunks)
    per = -(-per // 64) * 64                      # whole tiles per chunk
    chunks = [tiles[i:i + per] for i in range(0, tile_bytes, per)]
    n = len(chunks)
    body = bytearray(); offs = []
    for i, c in enumerate(chunks):
        if i == 0:
            offs.append(n * 4); body += pal
        else:
            while (n * 4 + len(body)) % 4: body.append(0)
            offs.append(n * 4 + len(body))
        body += lz.compress(c)
    while len(body) % 4: body.append(0)
    return b''.join(struct.pack('<I', o) for o in offs) + bytes(body)

def tiles_to_rows(tiles, bpp, width_tiles):
    tsize = 64 if bpp == 8 else 32
    ntiles = len(tiles) // tsize
    rows_t = -(-ntiles // width_tiles)
    w = width_tiles * 8; h = rows_t * 8
    rows = [bytearray(w) for _ in range(h)]
    for t in range(ntiles):
        tx, ty = (t % width_tiles) * 8, (t // width_tiles) * 8
        td = tiles[t * tsize:(t + 1) * tsize]
        for y in range(8):
            for x in range(8):
                if bpp == 8: v = td[y * 8 + x]
                else:
                    b = td[y * 4 + x // 2]; v = b & 15 if x % 2 == 0 else b >> 4
                rows[ty + y][tx + x] = v
    return w, h, rows

def rows_to_tiles(rows, w, h, bpp):
    out = bytearray()
    for ty in range(0, h, 8):
        for tx in range(0, w, 8):
            for y in range(8):
                if bpp == 8: out += bytes(rows[ty + y][tx:tx + 8])
                else:
                    for x in range(0, 8, 2):
                        out.append((rows[ty + y][tx + x] & 15) | ((rows[ty + y][tx + x + 1] & 15) << 4))
    return bytes(out)

def table_entries(d):
    return [struct.unpack_from('<II', d, rom_off(TABLE) + 8 * i) for i in range(TABLE_N)]

def cmd_list(a):
    d = load_rom(a.rom); warn_not_gs3(d)
    print('entry  object     flags       kind')
    for i, (obj, flags) in enumerate(table_entries(d)):
        try:
            bpp, pal, tiles, chunks = load_object(d, rom_off(obj))
            ntiles = len(tiles) // (64 if bpp == 8 else 32)
            kind = f'{bpp}bpp, {ntiles} tiles ({ntiles // 30}x30 tiles if 240 wide), {len(chunks)} chunks'
        except Exception as e:
            kind = f'? ({e})'
        print(f'{i:5}  {obj:#x}  {flags:#010x}  {kind}')

def resolve(d, spec):
    v = num(spec)
    if v < TABLE_N: return table_entries(d)[v][0]
    return rom_addr(v)

def cmd_extract(a):
    d = load_rom(a.rom)
    obj = resolve(d, a.entry)
    bpp, pal, tiles, chunks = load_object(d, rom_off(obj))
    w, h, rows = tiles_to_rows(tiles, bpp, a.width)
    palette = palette_from_bytes(pal, 256 if bpp == 8 else 16)
    write_png(a.out, w, h, rows, palette)
    print(f'{obj:#x}: {bpp}bpp {w}x{h}, {len(chunks)} chunks of {chunks[0]} bytes -> {a.out}')

def png_to_object(path, bpp=None):
    w, h, mode, rows, palette = read_png(path)
    if mode != 'P': sys.exit(f'{path}: must be an indexed (palette) PNG')
    if w % 8 or h % 8: sys.exit(f'{path}: size must be a multiple of 8')
    maxidx = max(max(r) for r in rows)
    if bpp is None: bpp = 4 if maxidx < 16 and len(palette) <= 16 else 8
    if bpp == 4 and maxidx >= 16: sys.exit(f'{path}: uses palette index {maxidx}, too many colours for 4bpp')
    ncol = 256 if bpp == 8 else 16
    palette = (palette + [(0, 0, 0)] * ncol)[:ncol]
    pal = b''.join(struct.pack('<H', rgb_to_bgr555(c)) for c in palette)
    tiles = rows_to_tiles(rows, w, h, bpp)
    return bpp, build_object(pal, tiles)

def cmd_build(a):
    bpp, obj = png_to_object(a.infile, a.bpp)
    open(a.out, 'wb').write(obj)
    print(f'{a.infile}: {bpp}bpp -> {len(obj)} byte object {a.out}')

def cmd_insert(a):
    rom = bytearray(load_rom(a.rom)); warn_not_gs3(rom)
    i = num(a.entry)
    if i >= TABLE_N: sys.exit('ENTRY must be a table index')
    old, flags = table_entries(rom)[i]
    try:
        obpp = load_object(rom, rom_off(old))[0]
    except Exception:
        obpp = None
    bpp, obj = png_to_object(a.infile, obpp)
    if obpp is not None and bpp != obpp:
        sys.exit(f'the original object is {obpp}bpp; give a PNG with {"16" if obpp == 4 else "256"} colours')
    new = place(rom, obj, a.at, 4, f'image {i}')
    n = 0
    for k, (o, f) in enumerate(table_entries(rom)):
        if o == old:
            struct.pack_into('<I', rom, rom_off(TABLE) + 8 * k, new); n += 1
    print(f'{n} table entries now point at {new:#x}')
    save_rom(rom, a.out)

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('list'); p.add_argument('rom'); p.set_defaults(fn=cmd_list)
    p = sub.add_parser('extract'); p.add_argument('rom'); p.add_argument('entry'); p.add_argument('out')
    p.add_argument('--width', type=num, default=30); p.set_defaults(fn=cmd_extract)
    p = sub.add_parser('build'); p.add_argument('infile'); p.add_argument('out'); p.add_argument('--bpp', type=int, choices=(4, 8))
    p.add_argument('--width', type=num, default=30); p.set_defaults(fn=cmd_build)
    p = sub.add_parser('insert'); p.add_argument('rom'); p.add_argument('entry'); p.add_argument('infile'); p.add_argument('out')
    p.add_argument('--at', type=num); p.set_defaults(fn=cmd_insert)
    a = ap.parse_args(); a.fn(a)

if __name__ == '__main__':
    main()
