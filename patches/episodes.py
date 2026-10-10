"""Episode select from the DS version: the episode boxes and the "Episode n" label above them.

GBA: both are sprite animations of the effects archive (see patches/banners.py for the formats):

* effects 10-20 are the episode boxes, sub-archive 0x8f4c with two palettes (white for the
  selected box, grey for the others): 10 is an empty box; 11-15 are the five titles on palette 0
  and 16-20 the same on palette 1.  A box is 128x64 in 128 OBJ tiles (23 or 24 sprites).  Their
  frame data has two frames: the box for one frame, then one 32x16 piece of the inside, held.
* effects 21-25 are 第n話 ("episode n"), sub-archive 0x9ca0: three 16x16 sprites each (第, the
  digit, 話), at OBJ tile 128; the arrows follow at tile 140, the empty box at 152.

DS: each episode's box is a 256x64 texture in data.bin (from 0x7de7b8, 0x2094 bytes apart): a
176x58 box with the title in one line, four palettes (normal, touched, faded, greyed).  The
label is one 128x64 texture (0x7e8a9c): the digits 1-5, the arrows and the word Episode.

The English boxes are the GBA's own empty box (effect 10: white, a dark red frame with rounded
corners, grey on the other palette) with the DS title lettering set inside it in two lines, cut at
a word space (one DS line is wider than the box), at the DS size.  The DS lettering is a ramp
of a dozen shades from dark red to white; each pixel takes the nearest of the shades the GBA
box's palette has for its own lettering (indices 4-11 and the white fill, 12), so the grey
palette greys the English letters as it greys the Japanese ones.  Two 64x64 sprites, 128
tiles.  The label is the DS word Episode and the episode's digit, 96x24 in six sprites at OBJ tile
24: on this screen OBJ tiles 0-63 are free (the prompt under the boxes is sprite text in tiles
64-127), and the box of episode 5, shown next to episode 4, runs 24 tiles past the end of OBJ
VRAM, which wraps to tiles 0-23 (as in the original).
"""
import os, struct, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
import dsimgtext, dspic, resample
from mes import load_bank
from convert_script import tok, ADS
from .banners import rle16, unrle16, FX_ARCHIVE, effect_entries

BOX_SUB, LABEL_SUB = 0x8f4c, 0x9ca0
BLANK_FRAMES = 0x086de910                         # effect 10, the empty box
TITLE_FRAMES = [0x086de990, 0x086dea14, 0x086dea94, 0x086deb18, 0x086deb9c,   # palette 0
                0x086dec1c, 0x086deca0, 0x086ded20, 0x086deda4, 0x086dee28]   # palette 1
LABEL_FRAMES = [0x086deea8, 0x086deed0, 0x086deef8, 0x086def20, 0x086def48]
EPISODES = 5
SHAPE = dspic.SHAPE
SIZE = dspic.SIZE

DS_BOX, DS_BOX_STEP = 0x7de7b8, 0x2094            # data.bin: the five boxes, one after another
DS_LABEL = 0x7e8a9c                               # data.bin: digits, arrows, Episode
BOX_W, BOX_H = 128, 64
LINE_PITCH = 20                                   # the two lines of a title
WORD_GAP = 4                                      # a column run this wide with no ink is a space
GBA_FILL = 12                                     # the GBA box's inside (white, grey on palette 1)
GBA_INK = range(4, 13)                            # ... and its lettering shades, dark red to white

LABEL_W, LABEL_H = 96, 24
LABEL_TILE = 24                                   # OBJ tile of the label (see above)
LABEL_GAP = 5                                     # between Episode and the digit
LABEL_Y = -62                                     # top of the label from the anchor (x 120, y 80)

# --- the DS titles ---------------------------------------------------------------------------
def ds_titles(ctx):
    """Episode titles in order, from the DS English common bank: sections that are a caption
    (0x42 0) with two centred lines, title and part."""
    secs = load_bank(ctx.ds_banks[85])
    titles = []
    for s in secs:
        ws = [struct.unpack_from('<H', s, i)[0] for i in range(0, len(s) - 1, 2)]
        items = tok(ws, ADS)
        cmds = [(it[1], it[2]) for it in items if it[0] == 'c']
        if (0x42, (0,)) not in cmds or not any(c == 0x5d for c, _ in cmds): continue
        lines, cur = [], ''
        for kind, w, args in items:
            if kind == 't': cur += dsimgtext.CHARS.get(w, ' ' if w == dsimgtext.SPACE else '?')
            elif w == 0x01:
                if cur: lines.append(cur)
                cur = ''
        if cur: lines.append(cur)
        if len(lines) == 2 and lines[1].startswith('Part ') and lines[0] not in titles:
            titles.append(lines[0])
    if len(titles) != EPISODES:
        raise SystemExit(f'episodes: expected {EPISODES} titles in the DS common bank, found {titles}')
    return titles

# --- effects archive helpers (also used by patches/datascreen.py) ----------------------------
def sub_archive(rom, sub):
    s = FX_ARCHIVE + sub
    npal = rom.u16(s)
    tab = s + 4 + 32 * npal
    n = rom.u32(tab) // 4
    return dict(npal=npal, flag=rom.u16(s + 2), pals=rom.read(s + 4, 32 * npal), tab=tab,
                cells=[tab + rom.u32(tab + 4 * i) for i in range(n)])

def read_frames(rom, fp):
    """-> (sub offset, [(def offset, duration)], {def offset: [(x, y, w, h, cell, attr)]})"""
    return dspic.frame_data(rom.d, fp - 0x08000000)

write_frames = dspic.write_frames

def write_sub(npal, flag, pals, cells):
    table = bytearray(); body = bytearray()
    for c in cells:
        table += struct.pack('<I', 4 * len(cells) + len(body))
        body += c
        while len(body) % 2: body.append(0)
    return struct.pack('<HH', npal, flag) + pals + bytes(table) + bytes(body)

def tiles_to_grid(data, w, h):
    return dspic.tiles_to_rows(data, w, h)

def grid_to_tiles(g, x0, y0, w, h):
    return dspic.rows_to_tiles(g, x0, y0, w, h)

# --- the boxes -------------------------------------------------------------------------------
def ds_box(data, k):
    """Episode k's DS box -> (texture rows, palettes, frame colours, lettering bbox, word spaces)."""
    off = DS_BOX + DS_BOX_STEP * k
    px, w, h, palb = dsimgtext.texture(data, off)
    if (w, h) != (256, 64) or len(palb) != 128:
        raise SystemExit(f'episodes: no DS episode box at data.bin {off:#x}')
    pals = [list(struct.unpack_from('<16H', palb, 32 * i)) for i in range(4)]
    # the box: outline, a highlight inside it at the top and left, a shadow at the bottom, fill
    rows = [y for y in range(h) if any(px[y])]
    cols = [x for x in range(w) if any(px[y][x] for y in range(h))]
    x0, x1, y0, y1 = cols[0], cols[-1], rows[0], rows[-1]
    edge, light, fill, shade = px[y0 + 2][x0], px[y0 + 1][x0 + 2], px[y0 + 4][x0 + 4], px[y1 - 1][x0 + 4]
    if px[y0][x0] or px[y0][x0 + 1] != edge or px[y0 + 4][x1] != edge or len({edge, light, fill, shade}) != 4:
        raise SystemExit(f'episodes: unexpected DS episode box at data.bin {off:#x}')
    ink = [(x, y) for y in range(y0 + 3, y1 - 2) for x in range(x0 + 3, x1 - 2) if px[y][x] != fill]
    bx0, bx1 = min(x for x, y in ink), max(x for x, y in ink) + 1
    by0, by1 = min(y for x, y in ink), max(y for x, y in ink) + 1
    inked = {x for x, y in ink}
    spaces, run = [], None
    for x in range(bx0, bx1):
        if x not in inked:
            if run is None: run = x
        else:
            if run is not None and x - run >= WORD_GAP: spaces.append((run, x))
            run = None
    return px, pals, (edge, light, fill, shade), (bx0, by0, bx1, by1), spaces

def gba_box(rom, sa):
    """The GBA's empty episode box (effect 10, first frame) -> 128x64 rows of its palette indices,
    and the inside: (x0, y0, x1, y1) of the fill."""
    sub, fl, defs = read_frames(rom, BLANK_FRAMES)
    if sub != BOX_SUB: raise SystemExit('episodes: unexpected empty box frames')
    g = [[0] * BOX_W for _ in range(BOX_H)]
    for x, y, w, h, c, attr in defs[fl[0][0]]:
        t = dspic.tiles_to_rows(dspic.unrle16(rom.d, sa['cells'][c] - 0x08000000, w * h // 2), w, h)
        for yy in range(h):
            for xx in range(w):
                if t[yy][xx]: g[BOX_H // 2 + y + yy][BOX_W // 2 + x + xx] = t[yy][xx]
    rows = [y for y in range(BOX_H) if g[y].count(GBA_FILL) > BOX_W // 2]
    cols = [x for x in range(BOX_W) if sum(g[y][x] == GBA_FILL for y in range(BOX_H)) > BOX_H // 2]
    if not rows or not cols: raise SystemExit('episodes: the GBA box has no inside')
    return g, (cols[0], rows[0], cols[-1] + 1, rows[-1] + 1)

def box_picture(base, inside, lines, px, ds_pal, gba_pal):
    """The GBA box with the DS lettering lines ([(x0, x1)] of the DS texture's lettering band, top
    to bottom) inside it -> rows of GBA palette indices."""
    g = [row[:] for row in base]
    if not lines: return g
    by0, by1, bands = lines
    ix0, iy0, ix1, iy1 = inside
    h = by1 - by0
    shades = {i: resample.bgr555_to_rgb(gba_pal[i]) for i in GBA_INK}
    top = iy0 + (iy1 - iy0 - (h + LINE_PITCH * (len(bands) - 1))) // 2
    cache = {}
    for i, (a, b) in enumerate(bands):
        rgb = [[resample.bgr555_to_rgb(ds_pal[px[by0 + y][a + x]]) for x in range(b - a)] for y in range(h)]
        w = b - a
        if w > ix1 - ix0 - 4:                                 # wider than the inside: scaled down
            nw = ix1 - ix0 - 4; nh = round(h * nw / w)
            rgb = [[tuple(round(c) for c in p) for p in row] for row in resample.scale_rgb(rgb, nw, nh)]
            w = nw
        x0 = ix0 + (ix1 - ix0 - w) // 2
        for y, row in enumerate(rgb):
            for x, p in enumerate(row):
                if p not in cache:
                    cache[p] = min(shades, key=lambda k: sum((shades[k][c] - p[c]) ** 2 for c in range(3)))
                if cache[p] != GBA_FILL: g[top + LINE_PITCH * i + y][x0 + x] = cache[p]
    return g

def split2(bx0, bx1, spaces):
    """The two lines (x ranges) with the narrower longer line."""
    best = None
    for s0, s1 in spaces:
        lines = [(bx0, s0), (s1, bx1)]
        wmax = max(b - a for a, b in lines)
        if best is None or wmax < best[0]: best = (wmax, lines)
    if best is None: raise SystemExit('episodes: a title does not fit in two lines')
    return best[1]

def boxes(rom, ctx, titles):
    """-> (sub-archive, {'blank': cells, k: cells}, fill cell): cells = two 64x64 cell numbers"""
    sa = sub_archive(rom, BOX_SUB)
    if sa['npal'] != 2: raise SystemExit('episodes: unexpected box sub-archive')
    gba_pal = list(struct.unpack_from('<16H', sa['pals'], 0))
    base, inside = gba_box(rom, sa)
    cells, pics = [], {}
    for k in range(EPISODES):
        px, ps, col, (bx0, by0, bx1, by1), spaces = ds_box(ctx.data, k)
        if len(spaces) != titles[k].count(' '):
            raise SystemExit(f'episodes: the DS box of episode {k + 1} does not read {titles[k]!r}')
        pics[k] = box_picture(base, inside, (by0, by1, split2(bx0, bx1, spaces)), px, ps[0], gba_pal)
    pics['blank'] = base
    index = {}
    for key, g in pics.items():
        index[key] = []
        for x in (0, 64):
            cells.append(dspic.rle16(dspic.rows_to_tiles(g, x, 0, 64, 64)))
            index[key].append(len(cells) - 1)
    g = [[GBA_FILL] * 32 for _ in range(16)]
    cells.append(dspic.rle16(dspic.rows_to_tiles(g, 0, 0, 32, 16)))
    fill_cell = len(cells) - 1
    blob = dspic.write_sub(2, sa['flag'], [list(struct.unpack_from('<16H', sa['pals'], 32 * i)) for i in range(2)], cells)
    return blob, index, fill_cell

# --- the label -------------------------------------------------------------------------------
def label_pictures(data):
    """'Episode n' for n = 1..5 as 96x24 rows of DS palette indices -> (pictures, palette)."""
    px, w, h, palb = dsimgtext.texture(data, DS_LABEL)
    if (w, h) != (128, 64): raise SystemExit('episodes: no DS label texture')
    pal = list(struct.unpack_from('<16H', palb, 0))
    def box(x0, y0, x1, y1):
        pts = [(x, y) for y in range(y0, y1) for x in range(x0, x1) if px[y][x]]
        if not pts: return None
        return min(x for x, y in pts), min(y for x, y in pts), max(x for x, y in pts) + 1, max(y for x, y in pts) + 1
    word = box(0, 40, 128, 64)                        # Episode, under the arrows
    # the digits: the column runs of the top band right of the arrows
    band = [x for x in range(w) if any(px[y][x] for y in range(0, 22))]
    runs, s = [], None
    for x in range(w + 1):
        if x < w and x in band:
            if s is None: s = x
        elif s is not None: runs.append((s, x)); s = None
    if word is None or len(runs) != EPISODES:
        raise SystemExit('episodes: unexpected DS label texture')
    pics = []
    for a, b in runs:
        d = box(a, 0, b, 22)
        ww = (word[2] - word[0]) + LABEL_GAP + (d[2] - d[0])
        hh = max(word[3] - word[1], d[3] - d[1])
        if ww > LABEL_W or hh > LABEL_H: raise SystemExit('episodes: the label is too big')
        g = [[0] * LABEL_W for _ in range(LABEL_H)]
        x = (LABEL_W - ww) // 2
        for y in range(word[1], word[3]):
            for xx in range(word[0], word[2]):
                if px[y][xx]: g[y - word[1]][x + xx - word[0]] = px[y][xx]
        x += word[2] - word[0] + LABEL_GAP
        for y in range(d[1], d[3]):                   # the digit's top level with the E's
            for xx in range(d[0], d[2]):
                if px[y][xx]: g[y - d[1]][x + xx - d[0]] = px[y][xx]
        pics.append(g)
    return pics, pal

LABEL_SPRITES = [(x, 0, 32, 16) for x in (0, 32, 64)] + [(x, 16, 32, 8) for x in (0, 32, 64)]

def apply(rom, ctx):
    titles = ds_titles(ctx)
    # 1. the boxes
    blob, index, fill_cell = boxes(rom, ctx, titles)
    arch = rom.store(blob, 'ext', 4, 'episode boxes')
    new_fp = {}
    for fp in [BLANK_FRAMES] + TITLE_FRAMES:
        sub, fl, defs = read_frames(rom, fp)
        if sub != BOX_SUB or len(fl) != 2 or len(defs[fl[1][0]]) != 1:
            raise SystemExit(f'episodes: unexpected frame data at {fp:#x}')
        key = 'blank' if fp == BLANK_FRAMES else TITLE_FRAMES.index(fp) % EPISODES
        pal = defs[fl[0][0]][0][5] & 0x0800                    # palette 0 or 1, as the original
        box = [(x, -BOX_H // 2, 64, 64, index[key][i], SHAPE[(64, 64)] << 12 | pal)
               for i, x in enumerate((-BOX_W // 2, 0))]
        x, y, w, h, c, attr = defs[fl[1][0]][0]                # the held piece of the inside
        new_fp[fp] = rom.store(write_frames(fl, {fl[0][0]: box, fl[1][0]: [(x, y, w, h, fill_cell, attr)]}),
                               'ext', 4, 'episode box frames')
    entries = effect_entries(rom, list(new_fp))
    if len(entries) != 2 * EPISODES + 1: raise SystemExit('episodes: unexpected box effects')
    for e in entries:
        rom.w32(e, arch); rom.w32(e + 8, new_fp[rom.u32(e + 8)])
        rom.write(e + 17, bytes([2]), 'episode box sprites')
    # 2. the labels
    pics, pal = label_pictures(ctx.data)
    sa = sub_archive(rom, LABEL_SUB)
    cells, label_fp = [], {}
    for k, fp in enumerate(LABEL_FRAMES):
        sub, fl, defs = read_frames(rom, fp)
        if sub != LABEL_SUB or len(defs) != 1:
            raise SystemExit(f'episodes: unexpected label frame data at {fp:#x}')
        attr = list(defs.values())[0][0][5] & 0x0e00            # palette and flip bits as the original
        sp = []
        for x, y, w, h in LABEL_SPRITES:
            data = dspic.rle16(dspic.rows_to_tiles(pics[k], x, y, w, h))
            if data not in cells: cells.append(data)
            sp.append((x - LABEL_W // 2, LABEL_Y + y, w, h, cells.index(data), SHAPE[(w, h)] << 12 | attr))
        label_fp[fp] = write_frames(fl, {off: sp for off in defs})
    arch2 = rom.store(dspic.write_sub(1, sa['flag'], [[0] + pal[1:]], cells), 'ext', 4, 'episode labels')
    entries = effect_entries(rom, LABEL_FRAMES)
    if len(entries) != EPISODES: raise SystemExit('episodes: unexpected label effects')
    stored = {fp: rom.store(b, 'ext', 4, 'episode label frames') for fp, b in label_fp.items()}
    for e in entries:
        if rom.u32(e + 4) != 0x06011000: raise SystemExit('episodes: unexpected label VRAM')
        rom.w32(e, arch2); rom.w32(e + 8, stored[rom.u32(e + 8)])
        rom.w32(e + 4, 0x06010000 + 32 * LABEL_TILE)
        rom.write(e + 17, bytes([len(LABEL_SPRITES)]), 'episode label sprites')
    print(f"  episode select: the GBA boxes with the DS titles ({', '.join(titles)}), the DS labels")
