"""Shout bubbles from the DS version: Objection!, Hold it!, Take that!

The GBA's bubbles (異議あり！, 待った！, くらえ！) are effects 1-9 of the effects archive (see
patches/banners.py for the formats): three sub-archives (0x28e4, 0x3c44, 0x4e24) with one list of
seven sprites each, a 96x144 bubble with the words written downwards, in 216 OBJ tiles at tile
0x1e8 (at tile 0x100 when Take that! is shouted at a Psyche-Lock).

The DS keeps its English bubbles in data.bin in the same formats: frame data, then its
sub-archive, a 256x192 picture as twelve 64x64 cells with one palette.  The build shrinks each
one to half size, 128x96 (area average), maps the colours back to the DS palette, and writes a
new sub-archive and frame data for each bubble with the original timing: four sprites (two
64x64 over two 64x32), 192 of the 216 tiles.  Every bubble is shown in the middle of the screen
(x 120, y 80), as the DS shows them all whoever shouts (seen in DeSmuME, the US release: Phoenix's
and Godot's alike); the GBA puts the defence's at x 45 and the prosecution's at x 190 (until 0.16.52
the English build moved those in to 64 and 176).

The sprite count matters more than the tiles.  The animation renderer (0x08017cc8) hands out OAM
entries from 127 downwards to every animation on screen, with no lower limit, and the life bar
has fixed entries 61-70: the original's bubbles (seven sprites) leave room for it, and a bubble
with more sprites than that runs into the bar, which loses its frame and its end while the
bubble is up.  An earlier 144x108 bubble covered with as few sprites as fit the 216 tiles took
16-24 sprites and did exactly that; the build now refuses a bubble with more sprites than the
original's.

After the shake (30 frames of random steps) the bubble goes back to where it started (settle,
applied last), as the DS's does: the original leaves it where the last step put it.
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
SIZE = (128, 96)                     # half the DS picture
TILES = 216                          # the OBJ tiles the bubbles have
# the sprites covering SIZE: whole 64x64 squares, then a row of 64x32 under them
RECTS = [(x, y, 64, 64) for y in range(0, SIZE[1] - 63, 64) for x in range(0, SIZE[0], 64)] + \
        [(x, SIZE[1] // 64 * 64, 64, 32) for x in range(0, SIZE[0], 64)]
CENTRE = (120, 80)                   # where every bubble goes, as on the DS
GBA_X = (45, 120, 190)               # the original's anchors (defence, middle, prosecution)

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
        dx = dy = 0; rects = RECTS
        assert sum(w * h for x, y, w, h in rects) // 64 <= TILES
        covered = sorted((tx, ty) for rx, ry, rw, rh in rects
                         for tx in range(rx, rx + rw, 8) for ty in range(ry, ry + rh, 8))
        assert covered == sorted((tx, ty) for tx in range(0, SIZE[0], 8) for ty in range(0, SIZE[1], 8))
        orig = rom.u16(old_fp + rom.u16(old_fp + 8))       # sprites in the original's list
        if len(rects) > orig:
            raise SystemExit(f'shouts: {name} has {len(rects)} sprites, the original {orig} (see the notes above)')
        g = dspic.grid(q, dx, dy, *SIZE)
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
        x, y = rom.u16(e + 12), rom.u16(e + 14)
        if x not in GBA_X or y != CENTRE[1]: raise SystemExit(f'shouts: unexpected anchor ({x}, {y}) at {e:#x}')
        if x != CENTRE[0]:
            rom.w16(e + 12, CENTRE[0]); moved += 1
    print(f"  shouts: the DS bubbles for {len(entries)} effects ({len(archive)} bytes), {moved} moved to the middle")

# The shake (0x0801914c, the update of effects 1-9 in the table at 0x08161a48): for 30 frames x
# goes back and forth by 1-4 pixels about the x it started at (kept at slot + 0x2e) and y takes a
# random step of -4..3 a frame, held to 70-90; then it stops (counter at slot + 0x2b set to 40,
# 0x080191b2) and the bubble stays where the last step left it, up to 4 pixels left of its place
# and 10 above or below it.  The DS shakes its bubbles by a fixed pattern that ends where it began.
# The original's bubbles at the screen's edge hid it; the English ones in the middle showed a
# different place after every shake, so the build puts the bubble back where it started when the
# shake stops (applied last, so that nothing before it moves).
SHAKE_STOP = 0x080191b2

def settle(rom):
    if rom.read(SHAKE_STOP, 4) != rom.asm_thumb(SHAKE_STOP, 'movs r0, #0x28\n strb r0, [r3]'):
        raise SystemExit('shouts: unexpected code where the shake stops')
    back = rom.thumb_code(f'''
        movs r0, #0x28
        strb r0, [r3]
        ldrh r0, [r4, #0x2e]
        strh r0, [r4, #0x10]
        movs r0, #{CENTRE[1]}
        strh r0, [r4, #0x12]
        bx lr
    ''', note='shout bubble back in place after the shake')
    rom.hook_bl(SHAKE_STOP, back, 'shake stop: back in place')
