"""Witness Testimony / Cross Examination, Unlock Successful and the Testimony corner label from
the DS version.

The banners are sprite animations: entries of the animation table at 0x08046b30 (20 bytes each,
indexed by effect number: {u32 archive, u32 VRAM destination, u32 frame data, s16 x, s16 y, u32
flags}; the code at 0x080173e8 starts one; flags byte 0 is the first OBJ palette, byte 1 the
number of sprites).  The frame data names the sub-archive of the archive that holds the cells:

    frame data:   u16 0, u16 frames, u32 sub-archive offset
                  frames x {u16 sprite list offset, u16 time, u32 0}
                  sprite lists: u16 sprites, u16 0, then per sprite u16 position (y << 8 | x,
                  signed bytes from the anchor), u16 attribute (size and shape in the top 4
                  bits, then the palette bits, the cell number in the low 9 bits)
    sub-archive:  u16 palettes, u16 0x8000, 32 bytes per palette,
                  u32 cell offset[n] (from the start of this table), cells packed with a 16-bit
                  RLE (a token u16 t, then one u16 repeated t & 0x7fff times (t & 0x8000) or t
                  literal u16s)

The high byte of a frame's time says how the attribute picks the palette (0x08017eb0): 0 -> bit
11, one of two; 8 -> bits 10-11, one of four; 1 -> bits 9-11, one of eight.

The testimony banner (証言開始, blue) is three effects: its left and right halves (0x55 from x 0,
0x56 from x 240), which the code at 0x0800e788 slides to the middle (x 120, y 60), then the whole
banner (0x53) with a white sheen passing over it, then the halves again, sliding apart.  The
cross-examination banner (尋問開始, red) is 0x57, 0x58 and 0x54, and Unlock Successful (解除成功,
effects 105, 106 and 104; 107 is its right half alone) leaves up and down (0x0801a360).  The
original pictures are 128x32: the halves in OBJ tiles 0x260 and 0x240, the whole banner in 0x280
(two palettes, blue and red; four for Unlock, the last three for a flash at the end).

The DS keeps its English banners in data.bin in the same formats: two lines of bold italic
lettering (192x84 for Witness Testimony, 218x79 for Unlock Successful), and after the
sub-archive the frame data of the whole banner: the sheen as sprites over it in four frames,
then a flash through three lighter palettes.  The build shrinks every picture of that animation
to 128 wide (area average, tools/dspic.py) and cuts it into two 64x64 halves, so a banner takes
OBJ tiles 0x240-0x2bf like the original: the right half in 0x240, the left half in 0x280, and the
whole banner in 0x240 too, right half first, so that it has the same tiles as the halves when it
takes over from them.  The testimony banners keep two palettes (four from OBJ palette 11 would
reach the witness's), so their flash is drawn into the pictures; Unlock Successful flashes
through the DS's four palettes.
"""
import os, struct, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
import dspic

FX_ARCHIVE = 0x0869c8f0
ANIM_TABLE = 0x08046b30
ANIM_COUNT = 241                          # effects 0 (empty) .. 240
rle16, unrle16 = dspic.rle16, dspic.unrle16   # (patches/episodes.py and datascreen.py use them)

def effect_entries(rom, frames):
    """Animation table entries whose frame data is one of `frames`."""
    return [ANIM_TABLE + 20 * k for k in range(1, ANIM_COUNT) if rom.u32(ANIM_TABLE + 20 * k + 8) in frames]

# GBA frame data of each banner: the whole banner, its left half, its right half
GBA = {'testimony': (0x086de2b8, 0x086de4d8, 0x086de4f8),
       'cross': (0x086de3b0, 0x086de518, 0x086de538),
       'unlock': (0x086df030, 0x086df168, 0x086df188)}
ENTRIES = {'testimony': (1, 1, 1), 'cross': (1, 1, 1), 'unlock': (1, 1, 2)}
OLD_VRAM = (0x06015000, 0x06014c00, 0x06014800)
# data.bin: the English sub-archive, the frame data of the whole banner, its palette
DS = {'testimony': (0x71b000, 0x71f6f0, 0), 'cross': (0x71b000, 0x71f924, 4),
      'unlock': (0x73f01c, 0x742df8, 0)}
TILE0 = 0x240                             # the right half; the left half follows
VRAM = (0x06010000 + 32 * TILE0, 0x06010000 + 32 * (TILE0 + 64), 0x06010000 + 32 * TILE0)
W, H = 128, 64
TOP = -16                                 # the sprites from the anchor (y 60): centred where the
                                          # original's 128x32 was
HI = {'testimony': 0x000, 'cross': 0x000, 'unlock': 0x800}   # palette mode on the GBA
SQUARE = dspic.SHAPE[(64, 64)] << 12

# the "Testimony" label in the top left corner during a testimony (証言中): a raw 64x32 sprite
# (1D tiles, OBJ palette 5); data.bin has the Japanese one (the GBA's, byte for byte) and the
# English one 2 KB after it
LABEL = 0x08189f20
DS_LABEL_JP, DS_LABEL_EN = 0x1c900, 0x1d100

def ds_palette(attr, hi):
    if hi & 1: return attr >> 9 & 7
    if hi & 8: return attr >> 10 & 3
    return attr >> 11 & 1

def compose(data, cells, sprites, hi):
    """A DS sprite list -> 256x192 rows of indices into its palettes laid end to end."""
    px = [[0] * 256 for _ in range(192)]
    for x, y, w, h, c, attr in sprites:
        g = dspic.tiles_to_rows(dspic.unrle16(data, cells[c], w * h // 2), w, h)
        k = 16 * ds_palette(attr, hi)
        for yy in range(h):
            row, src = px[96 + y + yy], g[yy]
            for xx in range(w):
                if src[xx]: row[128 + x + xx] = k + src[xx]
    return px

def bbox(px):
    xs = [x for x in range(256) if any(r[x] for r in px)]
    ys = [y for y in range(192) if any(px[y])]
    return xs[0], ys[0], xs[-1] + 1, ys[-1] + 1

def ds_banner(data, name):
    sa, fp, base = DS[name]
    npal, flag, pals, cells = dspic.sub_archive(data, sa)
    sub, fl, defs = dspic.frame_data(data, fp)
    hi = fl[0][1] >> 8
    if sub or len(fl) != 13 or any(t >> 8 != hi for _, t in fl) or not hi & 9 or base >= npal:
        raise SystemExit(f'banners: unexpected DS {name} banner at data.bin {fp:#x}')
    pics = {off: compose(data, cells, sp, hi) for off, sp in defs.items()}
    return dict(pals=pals, fl=fl, defs=defs, hi=hi, base=base, pics=pics, plain=fl[0][0])

def window(banners):
    """The DS area every picture of these banners fits in, symmetric about the anchor."""
    x0, y0, x1, y1 = 256, 192, 0, 0
    for b in banners:
        for px in b['pics'].values():
            a, c, d, e = bbox(px)
            x0, y0, x1, y1 = min(x0, a), min(y0, c), max(x1, d), max(y1, e)
    half = max(128 - x0, x1 - 128)
    return 128 - half, y0, 128 + half, y1

def shrink(b, px, win, pal):
    """A DS picture -> the W x H canvas of indices into `pal`."""
    x0, y0, x1, y1 = win
    s = min(W / (x1 - x0), H / (y1 - y0))
    tw, th = round((x1 - x0) * s), round((y1 - y0) * s)
    allpal = [v for p in b['pals'] for v in p]
    img = dspic.shrink([r[x0:x1] for r in px[y0:y1]], allpal, tw, th)
    q = dspic.quantize(img, pal, range(1, 16))
    return dspic.grid(q, (W - tw) // 2, (H - th) // 2, W, H)

def halves(canvas):
    """-> (left cell, right cell), packed"""
    return tuple(dspic.rle16(dspic.rows_to_tiles(canvas, x, 0, 64, 64)) for x in (0, 64))

def build(rom, ctx, names, gba_pals):
    """One sub-archive for these banners (with the palettes `gba_pals`, DS palette numbers) and
    the frame data of their effects -> {name: (whole, left, right) frame data}, sub-archive"""
    data = ctx.data
    bs = {n: ds_banner(data, n) for n in names}
    win = window(bs.values())
    cells, frames = [], {}
    def cell(c):
        if c not in cells: cells.append(c)
        return cells.index(c)
    for n in names:
        b = bs[n]
        pal = b['pals'][b['base']]
        bits = gba_pals.index(b['base']) << 11 if not HI[n] else 0
        lists = {}
        plain = halves(shrink(b, b['pics'][b['plain']], win, pal))
        for off, sp in b['defs'].items():
            ks = {ds_palette(a, b['hi']) for *_, a in sp}
            k = ks.pop() if len(ks) == 1 else None
            same = [s[:5] for s in sp] == [s[:5] for s in b['defs'][b['plain']]]
            if HI[n] and same and k is not None and k in gba_pals:
                l, r, attr = plain[0], plain[1], gba_pals.index(k) << 10     # the DS's palette flash
            else:
                l, r = halves(shrink(b, b['pics'][off], win, pal)) if off != b['plain'] else plain
                attr = bits
            lists[off] = [(0, TOP, 64, 64, cell(r), SQUARE | attr), (-64, TOP, 64, 64, cell(l), SQUARE | attr)]
        fl = [(off, HI[n] | (t & 0xff)) for off, t in b['fl']]
        held = [(0, HI[n] | 1), (0, HI[n] | 0xff)]
        frames[n] = (dspic.write_frames(fl, lists),
                     dspic.write_frames(held, {0: [(-64, TOP, 64, 64, cell(plain[0]), SQUARE | bits)]}),
                     dspic.write_frames(held, {0: [(0, TOP, 64, 64, cell(plain[1]), SQUARE | bits)]}))
    b0 = bs[names[0]]
    sub = dspic.write_sub(len(gba_pals), 0x8000, [[0] + b0['pals'][k][1:] for k in gba_pals], cells)
    return frames, sub

def label(rom, data):
    if data[DS_LABEL_JP:DS_LABEL_JP + 1024] != rom.read(LABEL, 1024):
        raise SystemExit(f'banners: no DS testimony label at data.bin {DS_LABEL_JP:#x}')
    rom.write(LABEL, data[DS_LABEL_EN:DS_LABEL_EN + 1024], 'testimony label')

def apply(rom, ctx):
    total = 0
    for names, gba_pals in ((('testimony', 'cross'), [0, 4]), (('unlock',), [0, 1, 2, 3])):
        frames, sub = build(rom, ctx, names, gba_pals)
        arch = rom.store(sub, 'ext', 4, ' / '.join(names) + ' banner')
        total += len(sub)
        for n in names:
            for role, (old, new, vram, count) in enumerate(zip(GBA[n], frames[n], VRAM, ENTRIES[n])):
                es = effect_entries(rom, [old])
                if len(es) != count or any(rom.u32(e + 4) != OLD_VRAM[role] or rom.u16(e + 14) != 60 for e in es):
                    raise SystemExit(f'banners: unexpected animation entries for the {n} banner')
                fp = rom.store(new, 'ext', 4, f'{n} banner frames')
                for e in es:
                    rom.w32(e, arch); rom.w32(e + 4, vram); rom.w32(e + 8, fp)
                    rom.write(e + 17, bytes([2 if role == 0 else 1]), f'{n} banner sprites')
    label(rom, ctx.data)
    print(f"  banners: Witness Testimony / Cross Examination and Unlock Successful from the DS ({total} bytes), "
          f"the Testimony label")
