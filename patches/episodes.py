"""Episode select in English: the episode titles and the "EPISODE n" label above them.

Both are sprite animations of the effects archive (see patches/banners.py for the formats):

* effects 10-20 are the episode boxes, sub-archive 0x8f4c with two palettes (white for the
  selected box, grey for the others): 10 is an empty box; 11-15 are the five titles on palette 0
  and 16-20 the same on palette 1.  A box is 128x64, made of 23 or 24 sprites; the frame and the
  empty inside are shared cells, the title row (y -8..8) has cells of its own.
* effects 21-25 are 第n話 ("episode n"), sub-archive 0x9ca0: three 16x16 sprites each (第, the
  digit, 話), copied to OBJ tile 128 (the arrows follow at tile 140, so the label keeps its 48x16).

The English boxes use the empty box's layout (nine 32x16 cells inside) with the title in two
lines of the DS dialogue font (emboldened, narrower word spaces); the titles are read from the DS version's common script bank,
where the save menu names each part (the episode title, then the part).  The label is
"EPISODE n" in condensed capitals (Spleen 5x8 at double height), white with a dark outline.
"""
import os, struct, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
import textgfx, smallfont, dsimgtext
from mes import load_bank
from convert_script import tok, ADS
from .banners import rle16, unrle16, FX_ARCHIVE, effect_entries

BOX_SUB, LABEL_SUB = 0x8f4c, 0x9ca0
BLANK_FRAMES = 0x086de910                         # effect 10, the empty box
TITLE_FRAMES = [0x086de990, 0x086dea14, 0x086dea94, 0x086deb18, 0x086deb9c,   # palette 0
                0x086dec1c, 0x086deca0, 0x086ded20, 0x086deda4, 0x086dee28]   # palette 1
LABEL_FRAMES = [0x086deea8, 0x086deed0, 0x086deef8, 0x086def20, 0x086def48]
EPISODES = 5
SHAPE = {(8, 8): 0x0, (16, 16): 0x4, (32, 32): 0x8, (64, 64): 0xc, (16, 8): 0x1, (32, 8): 0x5,
         (32, 16): 0x9, (64, 32): 0xd, (8, 16): 0x2, (8, 32): 0x6, (16, 32): 0xa, (32, 64): 0xe}
SIZE = {v: k for k, v in SHAPE.items()}           # size << 2 | shape -> (w, h)
INK = 4                                           # title lettering: dark red (palette 0) / near black (1)
TITLE_AREA = (-48, -24, 48, 24)                   # the nine inner cells
LABEL_TEXT, LABEL_FILL, LABEL_OUTLINE = 'EPISODE {}', 15, 1

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

GAP = 5                                           # word spacing in the titles (the font's space is 8)

def measure(font, text):
    """Width of a title line: bold lettering (1 px wider) and narrow word spacing."""
    words = text.split(' ')
    return sum(font.measure(w) for w in words) + GAP * (len(words) - 1) + 1

def line_mask(font, text, width):
    """16 rows x `width`: the line centred, words GAP apart, emboldened by one pixel."""
    out = [[0] * width for _ in range(16)]
    x = (width - measure(font, text)) // 2
    for w in text.split(' '):
        g = textgfx.render(font, w, font.measure(w) + 2, 16, fill=1, align='left')
        for y in range(16):
            for xx, v in enumerate(g[y]):
                if v:
                    for b in (0, 1):
                        if 0 <= x + xx + b < width: out[y][x + xx + b] = 1
        x += font.measure(w) + GAP
    return out

def wrap2(font, text, width):
    """Split into at most two lines that fit `width` (the break nearest the middle)."""
    if measure(font, text) <= width: return [text]
    words = text.split(' ')
    best = None
    for k in range(1, len(words)):
        a, b = ' '.join(words[:k]), ' '.join(words[k:])
        wa, wb = measure(font, a), measure(font, b)
        if wa <= width and wb <= width and (best is None or max(wa, wb) < best[0]):
            best = (max(wa, wb), [a, b])
    if best is None: raise SystemExit(f'episodes: title too long: {text}')
    return best[1]

# --- effects archive helpers -----------------------------------------------------------------
def sub_archive(rom, sub):
    s = FX_ARCHIVE + sub
    npal = rom.u16(s)
    tab = s + 4 + 32 * npal
    n = rom.u32(tab) // 4
    return dict(npal=npal, flag=rom.u16(s + 2), pals=rom.read(s + 4, 32 * npal), tab=tab,
                cells=[tab + rom.u32(tab + 4 * i) for i in range(n)])

def read_frames(rom, fp):
    """-> (sub offset, [(def offset, duration)], {def offset: [(x, y, w, h, cell, attr)]})"""
    n, sub = rom.u16(fp + 2), rom.u32(fp + 4)
    fl = [(rom.u16(fp + 8 + 8 * i), rom.u16(fp + 10 + 8 * i)) for i in range(n)]
    defs = {}
    for off, _ in fl:
        if off in defs: continue
        q = fp + off; sp = []
        for k in range(rom.u16(q)):
            pos, attr = rom.u16(q + 4 + 4 * k), rom.u16(q + 6 + 4 * k)
            x, y = pos & 0xff, pos >> 8
            w, h = SIZE[attr >> 12]
            sp.append((x - 256 if x >= 128 else x, y - 256 if y >= 128 else y, w, h, attr & 0x1ff, attr))
        defs[off] = sp
    return sub, fl, defs

def write_frames(fl, defs):
    """Frame data with the sub-archive at offset 0 of its archive."""
    order = []
    for off, _ in fl:
        if off not in order: order.append(off)
    pos = {}; body = bytearray(); base = 8 + 8 * len(fl)
    for off in order:
        pos[off] = base + len(body)
        sp = defs[off]
        body += struct.pack('<HH', len(sp), 0)
        for x, y, w, h, cell, attr in sp:
            body += struct.pack('<HH', (y & 0xff) << 8 | (x & 0xff), (attr & ~0x1ff) | cell)
    out = struct.pack('<HHI', 0, len(fl), 0)
    for off, dur in fl: out += struct.pack('<HHI', pos[off], dur, 0)
    return out + bytes(body)

def write_sub(npal, flag, pals, cells):
    table = bytearray(); body = bytearray()
    for c in cells:
        table += struct.pack('<I', 4 * len(cells) + len(body))
        body += c
        while len(body) % 2: body.append(0)
    return struct.pack('<HH', npal, flag) + pals + bytes(table) + bytes(body)

def tiles_to_grid(data, w, h):
    g = [[0] * w for _ in range(h)]
    for t in range((w // 8) * (h // 8)):
        for y in range(8):
            for x in range(8):
                b = data[t * 32 + y * 4 + x // 2]
                g[(t // (w // 8)) * 8 + y][(t % (w // 8)) * 8 + x] = b >> 4 if x & 1 else b & 15
    return g

def grid_to_tiles(g, x0, y0, w, h):
    out = bytearray()
    for ty in range(h // 8):
        for tx in range(w // 8):
            for y in range(8):
                row = g[y0 + ty * 8 + y]
                for x in range(x0 + tx * 8, x0 + tx * 8 + 8, 2):
                    out.append((row[x] & 15) | ((row[x + 1] & 15) << 4))
    return bytes(out)

# --- the boxes -------------------------------------------------------------------------------
def title_boxes(rom, font, titles):
    sa = sub_archive(rom, BOX_SUB)
    sub, bfl, bdefs = read_frames(rom, BLANK_FRAMES)
    if sub != BOX_SUB: raise SystemExit('episodes: unexpected empty-box frame data')
    layout = bdefs[bfl[0][0]]                      # the empty box: 23 sprites
    # its picture, 128x64 with the anchor at (64, 32)
    cv = [[0] * 128 for _ in range(64)]
    for x, y, w, h, c, attr in layout:
        g = tiles_to_grid(unrle16(rom.d, sa['cells'][c] - 0x08000000, w * h // 2), w, h)
        for yy in range(h):
            for xx in range(w):
                if g[yy][xx]: cv[32 + y + yy][64 + x + xx] = g[yy][xx]
    inner = [s for s in layout if s[2:4] == (32, 16) and TITLE_AREA[0] <= s[0] < TITLE_AREA[2]
             and TITLE_AREA[1] <= s[1] < TITLE_AREA[3]]
    if len(inner) != 9: raise SystemExit('episodes: unexpected empty-box layout')
    shared = sorted({s[4] for s in layout})        # frame and empty-inside cells, kept as they are
    cells = [rle16(unrle16(rom.d, sa['cells'][c] - 0x08000000,
                           next(s[2] * s[3] // 2 for s in layout if s[4] == c))) for c in shared]
    remap = {c: i for i, c in enumerate(shared)}
    per_title = []
    x0, y0, x1, y1 = (64 + TITLE_AREA[0], 32 + TITLE_AREA[1], 64 + TITLE_AREA[2], 32 + TITLE_AREA[3])
    for t in titles:
        pic = [r[:] for r in cv]
        lines = wrap2(font, t, x1 - x0)
        top = 32 - 8 * len(lines)
        for i, ln in enumerate(lines):
            g = line_mask(font, ln, x1 - x0)
            for yy in range(16):
                for xx in range(x1 - x0):
                    if g[yy][xx]: pic[top + 16 * i + yy][x0 + xx] = INK
        own = {}
        for x, y, w, h, c, attr in inner:
            data = rle16(grid_to_tiles(pic, 64 + x, 32 + y, w, h))
            if data not in cells: cells.append(data)
            own[(x, y)] = cells.index(data)
        per_title.append(own)
    blob = write_sub(sa['npal'], sa['flag'], sa['pals'], cells)
    return blob, layout, remap, per_title

def label_cells(k):
    """'EPISODE k': 48x16, three 16x16 cells."""
    text = LABEL_TEXT.format(k)
    w = smallfont.measure(text) + 2
    g = [[0] * w for _ in range(8)]
    smallfont.render(text, g, 0, 0, 1)
    rows = [y for y in range(8) if any(g[y])]
    g = [r for y in range(rows[0], rows[-1] + 1) for r in (g[y], g[y])]   # double height
    cols = [x for x in range(w) if any(r[x] for r in g)]
    g = [r[cols[0]:cols[-1] + 1] for r in g]
    if len(g[0]) + 2 > 48 or len(g) + 2 > 16: raise SystemExit(f'episodes: label too big: {text}')
    cv = [[0] * 48 for _ in range(16)]
    ox, oy = (48 - len(g[0])) // 2, (16 - len(g)) // 2
    for y, r in enumerate(g):
        for x, v in enumerate(r):
            if v: cv[oy + y][ox + x] = LABEL_FILL
    src = [r[:] for r in cv]
    for y in range(16):
        for x in range(48):
            if src[y][x] != LABEL_FILL and any(0 <= y + dy < 16 and 0 <= x + dx < 48 and src[y + dy][x + dx] == LABEL_FILL
                                               for dy in (-1, 0, 1) for dx in (-1, 0, 1)):
                cv[y][x] = LABEL_OUTLINE
    return [rle16(grid_to_tiles(cv, 16 * i, 0, 16, 16)) for i in range(3)]

def apply(rom, ctx):
    font = textgfx.Font.from_ctx(ctx)
    titles = ds_titles(ctx)
    # 1. the boxes
    blob, layout, remap, per_title = title_boxes(rom, font, titles)
    arch = rom.store(blob, 'ext', 4, 'episode boxes')
    entries = effect_entries(rom, TITLE_FRAMES)
    if len(entries) != 2 * EPISODES: raise SystemExit('episodes: unexpected box effects')
    new_fp = {}
    for k, fp in enumerate(TITLE_FRAMES):
        sub, fl, defs = read_frames(rom, fp)
        if sub != BOX_SUB or len(fl) != 2: raise SystemExit(f'episodes: unexpected frame data at {fp:#x}')
        pal = defs[fl[0][0]][0][5] & 0x0800        # palette 0 or 1, as the original
        own = per_title[k % EPISODES]
        sp = []
        for x, y, w, h, c, attr in layout:
            cell = own[(x, y)] if (x, y) in own and (w, h) == (32, 16) else remap[c]
            sp.append((x, y, w, h, cell, (attr & ~0x0800) | pal))
        # the second frame (the engine holds it): one empty inside cell, as the original
        x, y, w, h, c, attr = defs[fl[1][0]][0]
        if c not in remap: raise SystemExit('episodes: unexpected second frame')
        out_defs = {fl[0][0]: sp, fl[1][0]: [(x, y, w, h, remap[c], attr)]}
        new_fp[fp] = rom.store(write_frames(fl, out_defs), 'ext', 4, 'episode box frames')
    for e in entries:
        rom.w32(e, arch); rom.w32(e + 8, new_fp[rom.u32(e + 8)])
    # 2. the labels
    sa = sub_archive(rom, LABEL_SUB)
    cells, label_fp = [], {}
    for k, fp in enumerate(LABEL_FRAMES):
        sub, fl, defs = read_frames(rom, fp)
        sp = defs[fl[0][0]]
        if sub != LABEL_SUB or sorted((x, y, w, h) for x, y, w, h, c, a in sp) != \
                [(-24, -60, 16, 16), (-8, -60, 16, 16), (8, -60, 16, 16)]:
            raise SystemExit(f'episodes: unexpected label frame data at {fp:#x}')
        idx = []
        for data in label_cells(k + 1):
            if data not in cells: cells.append(data)
            idx.append(cells.index(data))
        attr = sp[0][5]
        new = [(-24 + 16 * i, -60, 16, 16, idx[i], attr) for i in range(3)]
        label_fp[fp] = write_frames(fl, {off: new for off in defs})
    arch2 = rom.store(write_sub(sa['npal'], sa['flag'], sa['pals'], cells), 'ext', 4, 'episode labels')
    entries = effect_entries(rom, LABEL_FRAMES)
    if len(entries) != EPISODES: raise SystemExit('episodes: unexpected label effects')
    stored = {fp: rom.store(b, 'ext', 4, 'episode label frames') for fp, b in label_fp.items()}
    for e in entries:
        rom.w32(e, arch2); rom.w32(e + 8, stored[rom.u32(e + 8)])
    print(f"  episode select: {', '.join(titles)}")
