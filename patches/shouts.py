"""Shout bubbles from the DS version: Objection!, Hold it!, Take that!

The GBA's bubbles (異議あり！, 待った！, くらえ！) are effects 1-9 of the effects archive (see
patches/banners.py for the formats): three sub-archives (0x28e4, 0x3c44, 0x4e24) with one list of
seven sprites each, a 96x144 bubble with the words written downwards, in 216 OBJ tiles at tile
0x1e8 (at tile 0x100 when Take that! is shouted at a Psyche-Lock).

The DS keeps its English bubbles in data.bin in the same formats: frame data, then its
sub-archive, a 256x192 picture as twelve 64x64 cells with one palette.  The build shrinks each
one to 144x108 (area average), maps the colours back to the DS palette, covers the 8x8 tiles that
have something in them with as few sprites as it finds within the 216 tiles, and writes a new
sub-archive and frame data for each bubble with the original timing.  The effects anchored at
the screen edges (x 45 and 190) move in so the bubble stays on screen.
"""
import os, struct, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
import dspic
from .banners import FX_ARCHIVE, effect_entries

# (GBA frame data, its sub-archive, frame data of the DS English bubble in data.bin, name)
SHOUTS = [(0x086de558, 0x28e4, 0x7228f8, 'Objection!'),
          (0x086de590, 0x3c44, 0x72b1f8, 'Hold it!'),
          (0x086de5c8, 0x4e24, 0x733738, 'Take that!')]
DS_W, DS_H = 256, 192
SIZE = (144, 108)                    # 9/16 of the DS picture
TILES = 216                          # the OBJ tiles the bubbles have
EDGE_X = {45: 72, 190: 168}          # anchors at the screen edges, moved in

def ds_bubble(data, f, name):
    """-> (the 256x192 picture as rows of indices, its palette)"""
    sub, fl, defs = dspic.frame_data(data, f)
    if sub != 0 or not fl or len(defs) != 1:
        raise SystemExit(f'shouts: no DS bubble at data.bin {f:#x} ({name})')
    (off, sp), = defs.items()
    want = sorted((x, y) for x in range(-DS_W // 2, DS_W // 2, 64) for y in range(-DS_H // 2, DS_H // 2, 64))
    if sorted((x, y) for x, y, w, h, c, a in sp if (w, h) == (64, 64)) != want or len(sp) != len(want):
        raise SystemExit(f'shouts: unexpected DS bubble at data.bin {f:#x} ({name})')
    npal, flag, pals, cells = dspic.sub_archive(data, f + off + 4 + 4 * len(sp))   # follows the list
    if npal != 1 or flag != 0x8000 or len(cells) < len(sp) or max(c for *_, c, a in sp) >= len(cells):
        raise SystemExit(f'shouts: unexpected DS bubble sub-archive ({name})')
    return dspic.compose(data, sp, cells, DS_W, DS_H, DS_W // 2, DS_H // 2), pals[0]

def apply(rom, ctx):
    archive = bytearray(); frames = {}; count = {}
    for old_fp, sub, ds_f, name in SHOUTS:
        if rom.u32(old_fp + 4) != sub or rom.u16(FX_ARCHIVE + sub) != 1:
            raise SystemExit(f'shouts: unexpected frame data at {old_fp:#x}')
        px, pal = ds_bubble(ctx.data, ds_f, name)
        q = dspic.quantize(dspic.shrink(px, pal, *SIZE), pal, dspic.used_indices(px))
        fit = dspic.cover(q, TILES)
        if fit is None: raise SystemExit(f'shouts: {name} does not fit in {TILES} tiles')
        dx, dy, rects = fit
        g = dspic.grid(q, dx, dy, max(x + w for x, y, w, h in rects), max(y + h for x, y, w, h in rects))
        cells = [dspic.rle16(dspic.rows_to_tiles(g, x, y, w, h)) for x, y, w, h in rects]
        off = len(archive)
        archive += dspic.write_sub(1, rom.u16(FX_ARCHIVE + sub + 2), [pal], cells)
        while len(archive) % 4: archive.append(0)
        # frame data: the original's timing, one list of the sprites around the anchor
        n = rom.u16(old_fp + 2)
        fl = [(rom.u16(old_fp + 8 + 8 * i), rom.u16(old_fp + 10 + 8 * i)) for i in range(n)]
        if len({o for o, _ in fl}) != 1: raise SystemExit('shouts: bubble with more than one frame')
        fd = struct.pack('<HHI', 0, n, off)
        for _, t in fl: fd += struct.pack('<HHI', 8 + 8 * n, t, 0)
        fd += struct.pack('<HH', len(rects), 0)
        cx, cy = dx + SIZE[0] // 2, dy + SIZE[1] // 2
        for k, (x, y, w, h) in enumerate(rects):
            fd += struct.pack('<HH', ((y - cy) & 0xff) << 8 | ((x - cx) & 0xff), dspic.SHAPE[(w, h)] << 12 | k)
        frames[old_fp] = fd; count[old_fp] = len(rects)
        print(f"  shout {name}: {len(rects)} sprites, {sum(w * h for x, y, w, h in rects) // 64} tiles")
    arch = rom.store(bytes(archive), 'ext', 4, 'shout bubbles')
    fd_addr = {fp: rom.store(fd, 'ext', 4, 'shout frames') for fp, fd in frames.items()}
    moved = 0
    entries = effect_entries(rom, set(fd_addr))           # effects 1-9
    for e in entries:
        fp = rom.u32(e + 8)
        if rom.u32(e) != FX_ARCHIVE: raise SystemExit(f'shouts: unexpected entry at {e:#x}')
        rom.w32(e, arch); rom.w32(e + 8, fd_addr[fp])
        rom.write(e + 17, bytes([count[fp]]), 'shout sprite count')
        x = rom.u16(e + 12)
        if x in EDGE_X:
            rom.w16(e + 12, EDGE_X[x]); moved += 1
    print(f"  shouts: the DS bubbles for {len(entries)} effects ({len(archive)} bytes), {moved} moved in from the edge")
