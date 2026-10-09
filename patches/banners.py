"""Testimony / cross-examination banners and the "Testimony" corner label, in English.

The banners (証言開始 "testimony begins", blue; 尋問開始 "cross-examination begins", red) are
sprite animations.  Their pictures live in an effects archive at 0x0869c8f0: the animation table
at 0x08046b30 (20-byte entries {u32 archive, u32 VRAM destination, u32 frame data, s16 x, s16 y,
u32 flags}, indexed by effect number; the code at 0x080173e8 reads it) points at the archive,
and the frame data's header names the sub-archive inside it (offset 0 for the banners).  A
sub-archive is

    u16 palettes, u16 0x8000, 32 bytes per palette,
    u32 cell offset[n] (from the start of this table), cells

and each cell is a 64x32 or 32x32 4bpp sprite (1D tile order) packed with a 16-bit RLE: a token
u16 t, then either one u16 repeated t & 0x7fff times (t & 0x8000) or t literal u16s.

Frame data: {u16 0, u16 frames, u32 sub-archive offset}, then per frame {u16 offset, u16 time,
u32 0}, and at each offset {u16 sprites, u16 0, then per sprite u16 position (y << 8 | x, signed
bytes), u16 attribute (size and shape in the top 4 bits, 0x0800 = second palette, cell number in
the low bits)}.  The banner uses 19 cells: each half of the words (64x32), each quarter (32x32)
and the quarters with a white sheen passing over them.  Both banners share the right half
(開始), so the English build adds seven cells for the cross-examination banner and points its
frames at them.

The English pictures are two lines in bold italic DS-font lettering, blue (or red) with a white
outline, after the DS version's "Witness Testimony" / "Cross Examination".
"""
import os, struct, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
import textgfx, smallfont

FX_ARCHIVE = 0x0869c8f0
ANIM_TABLE = 0x08046b30
ANIM_COUNT = 142                          # effects 0 (empty) .. 141
BANNER_FRAMES = [0x086de2b8, 0x086de3b0, 0x086de4d8, 0x086de4f8, 0x086de518, 0x086de538]

def effect_entries(rom, frames):
    """Animation table entries whose frame data is one of `frames` (effects 0x53-0x58 for the
    banners, 1-9 for the shout bubbles)."""
    return [ANIM_TABLE + 20 * k for k in range(1, ANIM_COUNT) if rom.u32(ANIM_TABLE + 20 * k + 8) in frames]
TESTIMONY_FRAMES = 0x086de2b8          # sheen over 証言開始 (cells 0-12)
CROSS_FRAMES = [0x086de3b0, 0x086de538]  # sheen over 尋問開始, and its right half sliding in
CROSS_REMAP = {0: 19, 7: 20, 8: 21, 9: 22, 10: 23, 11: 24, 12: 25}

TEXT = {'testimony': ('Witness', 'Testimony'), 'cross': ('Cross', 'Examination')}
FILL, OUTLINE, SHEEN, SHEEN_EDGE = 3, 2, 1, 4

# the "Testimony" label in the top left corner during testimony (証言中): raw 64x32 sprite,
# OBJ palette 5, white (2) with a green outline (1)
LABEL = 0x08189f20
LABEL_TEXT = 'Testimony'

def rle16(data):
    """Pack bytes (even length) with the archive's 16-bit RLE."""
    w = [struct.unpack_from('<H', data, i)[0] for i in range(0, len(data), 2)]
    out = bytearray(); i = 0; lit = []
    def flush():
        while lit:
            chunk = lit[:0x7fff]; del lit[:len(chunk)]
            out.extend(struct.pack('<H', len(chunk)))
            for v in chunk: out.extend(struct.pack('<H', v))
    while i < len(w):
        j = i
        while j < len(w) and w[j] == w[i] and j - i < 0x7fff: j += 1
        if j - i >= 2:
            flush()
            out.extend(struct.pack('<HH', 0x8000 | (j - i), w[i])); i = j
        else:
            lit.append(w[i]); i += 1
    flush()
    return bytes(out)

def unrle16(data, p, size):
    out = bytearray()
    while len(out) < size:
        t = struct.unpack_from('<H', data, p)[0]; p += 2
        if t & 0x8000: out += data[p:p + 2] * (t & 0x7fff); p += 2
        else: out += data[p:p + 2 * t]; p += 2 * t
    return bytes(out[:size])

# --- lettering ---------------------------------------------------------------------------
def _mask(font, text, squeeze=0):
    g = textgfx.render(font, text, font.measure(text) + 4, 16, fill=1, align='left', squeeze=squeeze)
    return g

def _bold(g):
    out = [[0] * (len(g[0]) + 1) for _ in g]
    for y, row in enumerate(g):
        for x, v in enumerate(row):
            if v: out[y][x] = out[y][x + 1] = 1
    return out

def _italic(g, base=13, step=4):
    sh = base // step + 1
    out = [[0] * (len(g[0]) + sh) for _ in g]
    for y, row in enumerate(g):
        s = max(0, base - y) // step
        for x, v in enumerate(row):
            if v: out[y][x + s] = 1
    return out

def _crop(g):
    xs = [x for x in range(len(g[0])) if any(r[x] for r in g)]
    ys = [y for y in range(len(g)) if any(g[y])]
    return [r[xs[0]:xs[-1] + 1] for r in g[ys[0]:ys[-1] + 1]]

def _outline(cv, fill, out):
    src = [r[:] for r in cv]; h, w = len(cv), len(cv[0])
    for y in range(h):
        for x in range(w):
            if src[y][x] == fill: continue
            if any(0 <= y + dy < h and 0 <= x + dx < w and src[y + dy][x + dx] == fill
                   for dy in (-1, 0, 1) for dx in (-1, 0, 1)):
                cv[y][x] = out

def banner_picture(font, lines):
    """Two lines of bold italic lettering in a 128x32 picture (fill 3, outline 2)."""
    cv = [[0] * 128 for _ in range(32)]
    for i, text in enumerate(lines):
        g = _crop(_italic(_bold(_mask(font, text))))
        if len(g[0]) > 124: raise ValueError(f'banner line too wide: {text}')
        x0 = (128 - len(g[0])) // 2
        y0 = i * 16 + (16 - len(g)) // 2 + (1 if i == 0 else -1)
        for y, row in enumerate(g):
            for x, v in enumerate(row):
                if v: cv[y0 + y][x0 + x] = FILL
    _outline(cv, FILL, OUTLINE)
    return cv

def sheen(cv, pos):
    """The white sheen: a diagonal band over the lettering, `pos` = its left edge on the top row."""
    out = [r[:] for r in cv]
    for y, row in enumerate(out):
        for x, v in enumerate(row):
            if v != FILL: continue
            d = x - pos + y // 2
            if 0 <= d < 4: row[x] = SHEEN
            elif d in (-2, -1, 4, 5): row[x] = SHEEN_EDGE
    return out

def cell(cv, x0, w):
    """Cut a w x 32 sprite out of the picture -> 4bpp tiles in 1D order."""
    out = bytearray()
    for ty in range(4):
        for tx in range(w // 8):
            for y in range(8):
                row = cv[ty * 8 + y]
                for x in range(x0 + tx * 8, x0 + tx * 8 + 8, 2):
                    out.append((row[x] & 15) | ((row[x + 1] & 15) << 4))
    return bytes(out)

def banner_cells(pic):
    """The roles of the original cells, for one banner: {role: bytes}.  Roles follow the
    testimony banner's numbering (1/0 left/right half, 2/3 quarters 1-2, 4/5 quarter 1 with the
    sheen, 6 quarter 2 with it, 7/9 quarter 3 with it, 10 quarter 3, 8 quarter 4, 11/12 quarter 4
    with the sheen)."""
    s = {p: sheen(pic, p) for p in (14, 40, 78, 90, 104, 118)}
    return {1: cell(pic, 0, 64), 0: cell(pic, 64, 64), 2: cell(pic, 0, 32), 3: cell(pic, 32, 32),
            4: cell(s[14], 0, 32), 5: cell(s[40], 0, 32), 6: cell(s[40], 32, 32),
            7: cell(s[78], 64, 32), 9: cell(s[90], 64, 32), 10: cell(pic, 64, 32),
            8: cell(pic, 96, 32), 11: cell(s[104], 96, 32), 12: cell(s[118], 96, 32)}

def label_picture(text):
    """Condensed tall lettering (Spleen 5x8 at double height), white with a green outline."""
    w = smallfont.measure(text) + 2
    g = [[0] * w for _ in range(8)]
    smallfont.render(text, g, 0, 0, 1)
    g = _crop([r for r in g for _ in range(2)])
    cv = [[0] * 64 for _ in range(32)]
    x0, y0 = (64 - len(g[0])) // 2, (32 - len(g)) // 2
    for y, row in enumerate(g):
        for x, v in enumerate(row):
            if v: cv[y0 + y][x0 + x] = 2
    _outline(cv, 2, 1)
    return cv

def apply(rom, ctx):
    font = textgfx.Font.from_ctx(ctx)
    a = FX_ARCHIVE
    entries = effect_entries(rom, BANNER_FRAMES)
    if len(entries) != 6:
        raise SystemExit(f'banners: expected 6 animation entries, found {len(entries)}')
    for e in entries:
        fp = rom.u32(e + 8)
        if rom.u32(e) != a or rom.u32(fp + 4) != 0:
            raise SystemExit(f'banners: unexpected animation entry at {e:#x}')
    npal = rom.u16(a)
    pals = rom.read(a + 4, 32 * npal)
    t = a + 4 + 32 * npal
    if rom.u32(t) != 19 * 4:
        raise SystemExit('banners: the banner sub-archive does not have 19 cells')
    test = banner_cells(banner_picture(font, TEXT['testimony']))
    cross = banner_cells(banner_picture(font, TEXT['cross']))
    cells = [None] * 26
    for role, data in test.items(): cells[role] = data
    # cross-examination: left half and quarters in the original's cells 13-18 ...
    for k, role in {13: 1, 14: 4, 15: 3, 16: 5, 17: 6, 18: 2}.items(): cells[k] = cross[role]
    # ... and its own right half in the new cells 19-25
    for old, new in CROSS_REMAP.items(): cells[new] = cross[old]
    table = bytearray(); body = bytearray()
    for c in cells:
        table += struct.pack('<I', 4 * len(cells) + len(body))
        body += rle16(c)
        while len(body) % 2: body.append(0)
    blob = struct.pack('<HH', npal, rom.u16(a + 2)) + pals + bytes(table) + bytes(body)
    addr = rom.store(blob, 'ext', 4, 'banner sub-archive')
    for e in entries:
        rom.w32(e, addr)
    # point the cross-examination frames at its own right half
    for fp in CROSS_FRAMES:
        n = rom.u16(fp + 2)
        offs = sorted({rom.u16(fp + 8 + 8 * i) for i in range(n)})
        for off in offs:
            q = fp + off; cnt = rom.u16(q)
            for k in range(cnt):
                at = q + 4 + 4 * k + 2
                attr = rom.u16(at); c = attr & 0x1ff
                if c in CROSS_REMAP: rom.w16(at, (attr & ~0x1ff) | CROSS_REMAP[c])
    # corner label
    cv = label_picture(LABEL_TEXT)
    tiles = bytearray()
    for ty in range(4):
        for tx in range(8):
            for y in range(8):
                row = cv[ty * 8 + y]
                for x in range(tx * 8, tx * 8 + 8, 2):
                    tiles.append((row[x] & 15) | ((row[x + 1] & 15) << 4))
    rom.write(LABEL, bytes(tiles), 'testimony label')
    print(f"  banners: testimony / cross-examination ({len(blob)} bytes) and the Testimony label")
