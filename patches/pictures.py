"""Pictures with writing in them: Court Record detail pages (L Button), letters, maps, signs.

The DS keeps its full-screen pictures in data.bin as small archives: u32 7, then {offset, size}
pairs (relative to the archive), the palette first (32 bytes for 16 colours, 512 for 256) and
then six LZ chunks of 8x8 tiles in 1D order, 256x192 or 512x192 for the wide ones.  The arm9
lists the 57 pictures that differ between the languages twice, as {data.bin offset, size} pairs
in the same order: Japanese at 0x0209d924, English at 0x0209db04.

Most of them are the GBA picture with a border: the GBA's 240x160 (480x160) is the Japanese DS
picture cut at (8, 16) ((16, 16) for the wide ones), tile for tile, with the same palette.  The
English build changes the GBA picture where the two DS pictures differ ('diff'); a few GBA
pictures are another quantisation of the same art (the English colours are matched to the GBA
palette), and two are drawn 15/16 the size of the DS ones ('scaled': the changed part is
shrunk).  The pages of text were laid out again for the DS, so their English text is set into
the GBA page ('page', keeping the GBA's page number and arrow).  The calling card and the
newspaper were redrawn: the whole English picture is used ('whole', 'fit').

The pictures are chunked image objects (tools/chunkimg.py) listed by the image table; the new
objects go to the expansion area and every table entry that used the old object is pointed at
the new one.
"""
import os, struct, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
import lz, chunkimg

IMAGE_TABLE, IMAGES = 0x0803b3a4, 145
DS_ARM9 = 0x02000000
LANG_JP, LANG_EN, LANG_N = 0x0209d924, 0x0209db04, 57

# (DS picture: index in the language tables, GBA image-table entry, method, options)
PICTURES = [
    (1, 7, 'diff', {}),            # department store, the exhibition banner
    (2, 8, 'diff', {}),            # store room (wide), the signs on the wall
    (4, 18, 'diff', {}),           # playground sign
    (5, 20, 'diff', {}),           # office, the motto on the wall and the window
    (7, 26, 'diff', {}),           # the bridge, its sign and stone
    (8, 27, 'diff', {}),
    (9, 29, 'diff', {}),
    (10, 30, 'diff', {}),          # the hall's sign
    (12, 39, 'diff', {}),
    (13, 45, 'diff', {}),          # the bottle's label
    (14, 48, 'page', {}),
    (15, 49, 'page', {'drop': (0, 148, 28, 192)}),
    (16, 50, 'page', {'drop': (0, 148, 28, 192)}),
    (17, 51, 'diff', {}),          # exhibition poster
    (18, 54, 'diff', {}),
    (20, 60, 'whole', {}),         # calling card
    (21, 66, 'fit', {}),           # newspaper
    (23, 69, 'diff', {}),
    (24, 72, 'scaled', {'at': (0, 7.5)}),   # the urn
    (25, 73, 'page', {}),
    (26, 74, 'page', {}),
    (27, 75, 'page', {}),
    (28, 79, 'diff', {'grow': 3}), # map
    (29, 83, 'diff', {}),          # newspaper with the bomber's scribbles
    (33, 97, 'page', {}),
    (34, 98, 'diff', {'grow': 3}), # map of the river
    (35, 106, 'scaled', {'at': (0, 9)}),    # the urn
    (36, 108, 'page', {}),
    (37, 109, 'page', {}),
    (38, 110, 'diff', {'grow': 3}),    # map of the temple grounds
    (39, 116, 'diff', {'bleed': (228, 236)}),   # letter pages
    (40, 117, 'diff', {'bleed': (228, 236)}),
    (41, 118, 'diff', {'bleed': (228, 236)}),
    (42, 119, 'diff', {}),         # magazine
    (45, 142, 'diff', {}),
    (53, 59, 'diff', {}),
    (54, 70, 'diff', {}),
    (55, 91, 'diff', {}),
    (56, 92, 'diff', {}),
]
# 'diff' options: grow = also copy the pixels this close to the changed ones (the GBA's own
# lettering of a map label is not always where the DS's was); bleed = (x0, x1), columns the GBA
# picture has beyond the DS one's edge (the letters' paper is 8 pixels wider, the burns run on
# into them): they repeat the column left of x0
SCALE = 16 / 15     # 'scaled': DS = GBA * SCALE + at
MATCH = 0.75        # share of the window that must look like the Japanese DS picture

class Pic:
    """Palette-indexed picture: w x h indices in `px`, `pal` a list of 15-bit colours."""
    def __init__(self, w, h, pal, px, bpp8):
        self.w, self.h, self.pal, self.px, self.bpp8 = w, h, pal, px, bpp8
    def rgb(self, i):
        c = self.pal[self.px[i]]
        return c & 31, (c >> 5) & 31, (c >> 10) & 31

def colour(c): return c & 31, (c >> 5) & 31, (c >> 10) & 31

def untile(tiles, bpp8, tw):
    ts = 64 if bpp8 else 32
    nt = len(tiles) // ts
    th = nt // tw
    w = tw * 8
    px = bytearray(w * th * 8)
    for t in range(nt):
        x0, y0 = (t % tw) * 8, (t // tw) * 8
        b = t * ts
        for y in range(8):
            row = (y0 + y) * w + x0
            if bpp8:
                px[row:row + 8] = tiles[b + y * 8:b + y * 8 + 8]
            else:
                for x in range(4):
                    v = tiles[b + y * 4 + x]
                    px[row + 2 * x] = v & 15; px[row + 2 * x + 1] = v >> 4
    return px, w, th * 8

def retile(p):
    out = bytearray()
    w = p.w
    for ty in range(p.h // 8):
        for tx in range(w // 8):
            for y in range(8):
                row = (ty * 8 + y) * w + tx * 8
                if p.bpp8:
                    out += p.px[row:row + 8]
                else:
                    out += bytes(p.px[row + x] | (p.px[row + x + 1] << 4) for x in range(0, 8, 2))
    return bytes(out)

def ds_picture(data, off):
    n = struct.unpack_from('<I', data, off)[0]
    ents = [struct.unpack_from('<II', data, off + 4 + 8 * k) for k in range(n)]
    po, psz = ents[0]
    if n != 7 or po != 0x3c or psz not in (0x20, 0x200):
        raise SystemExit(f'pictures: unexpected DS picture at {off:#x}')
    pal = list(struct.unpack_from('<%dH' % (psz // 2), data, off + po))
    tiles = b''.join(lz.decompress(data, off + o)[0] for o, s in ents[1:])
    bpp8 = psz == 0x200
    nt = len(tiles) // (64 if bpp8 else 32)
    px, w, h = untile(tiles, bpp8, 64 if nt == 1536 else 32)
    return Pic(w, h, pal, px, bpp8)

def gba_picture(rom, obj, bpp8):
    psz = 512 if bpp8 else 32
    pal, chunks = chunkimg.parse(rom.d, obj - 0x08000000, psz)
    tiles = b''.join(c for c, _ in chunks)
    nt = len(tiles) // (64 if bpp8 else 32)
    px, w, h = untile(tiles, bpp8, 60 if nt == 1200 else 30)
    return Pic(w, h, list(struct.unpack('<%dH' % (psz // 2), pal)), px, bpp8), chunks

class Matcher:
    """Nearest colour among the picture's own entries (8bpp: 32-255, the rest are the shared UI
    colours; 4bpp: 1-15, 0 is transparent)."""
    def __init__(self, pal, bpp8):
        lo = 32 if bpp8 else 1
        self.ents = [(i, colour(pal[i])) for i in range(lo, len(pal))]
        self.cache = {}
    def __call__(self, rgb):
        v = self.cache.get(rgb)
        if v is None:
            r, g, b = rgb
            v = min(self.ents, key=lambda e: 3 * (e[1][0] - r) ** 2 + 4 * (e[1][1] - g) ** 2 + 2 * (e[1][2] - b) ** 2)[0]
            self.cache[rgb] = v
        return v

def close(a, b): return abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2]) <= 6

def similarity(g, d, ox, oy):
    """Share of g's pixels that look like d's at offset (ox, oy) (sampled)."""
    n = same = 0
    for y in range(0, g.h, 3):
        for x in range(0, g.w, 3):
            n += 1
            same += close(g.rgb(y * g.w + x), d.rgb((y + oy) * d.w + x + ox))
    return same / n

def changed(jp, en):
    """Indices of the pixels whose colour differs between the two DS pictures."""
    jc = [colour(c) for c in jp.pal]; ec = [colour(c) for c in en.pal]
    return [i for i in range(len(jp.px)) if jc[jp.px[i]] != ec[en.px[i]]]

def dilate(w, h, idx, r):
    m = bytearray(w * h)
    for i in idx:
        y, x = divmod(i, w)
        for yy in range(max(0, y - r), min(h, y + r + 1)):
            row = yy * w
            m[row + max(0, x - r):row + min(w, x + r + 1)] = b'\x01' * (min(w, x + r + 1) - max(0, x - r))
    return m

def method_diff(g, jp, en, grow=0, bleed=None):
    ox, oy = (en.w - g.w) // 2, (en.h - g.h) // 2
    if similarity(g, jp, ox, oy) < MATCH: return None
    mask = dilate(en.w, en.h, changed(jp, en), grow)
    same_pal = [c & 0x7fff for c in g.pal] == [c & 0x7fff for c in en.pal]
    near = Matcher(g.pal, g.bpp8)
    px = bytearray(g.px)
    for y in range(g.h):
        row = (y + oy) * en.w + ox
        for x in range(g.w):
            if mask[row + x]:
                i = row + x
                px[y * g.w + x] = en.px[i] if same_pal else near(en.rgb(i))
        if bleed:
            v = px[y * g.w + bleed[0] - 1]
            px[y * g.w + bleed[0]:y * g.w + bleed[1]] = bytes([v]) * (bleed[1] - bleed[0])
    return Pic(g.w, g.h, g.pal, px, g.bpp8)

def method_whole(g, jp, en):
    ox, oy = (en.w - g.w) // 2, (en.h - g.h) // 2
    if not g.bpp8 or similarity(g, jp, ox, oy) < MATCH: return None
    px = bytearray(g.w * g.h)
    for y in range(g.h):
        px[y * g.w:(y + 1) * g.w] = en.px[(y + oy) * en.w + ox:(y + oy) * en.w + ox + g.w]
    return Pic(g.w, g.h, g.pal[:32] + en.pal[32:], px, True)

def area(p, x0, y0, x1, y1):
    """Average colour of p over the rectangle [x0, x1) x [y0, y1) (fractional edges)."""
    r = gg = b = wt = 0.0
    for y in range(int(y0), min(p.h, int(y1 - 1e-9) + 1)):
        wy = min(y + 1, y1) - max(y, y0)
        if wy <= 0: continue
        for x in range(int(x0), min(p.w, int(x1 - 1e-9) + 1)):
            wx = min(x + 1, x1) - max(x, x0)
            if wx <= 0: continue
            c = p.rgb(y * p.w + x); k = wx * wy
            r += c[0] * k; gg += c[1] * k; b += c[2] * k; wt += k
    return int(r / wt + .5), int(gg / wt + .5), int(b / wt + .5)

def method_fit(g, jp, en):
    """The whole English picture, shrunk to the GBA screen."""
    if not g.bpp8 or similarity_scaled(g, jp, 0, 0) < MATCH * 0.8: return None
    near = Matcher(en.pal, True)
    sx, sy = en.w / g.w, en.h / g.h
    px = bytearray(g.w * g.h)
    for y in range(g.h):
        for x in range(g.w):
            px[y * g.w + x] = near(area(en, x * sx, y * sy, (x + 1) * sx, (y + 1) * sy))
    return Pic(g.w, g.h, g.pal[:32] + en.pal[32:], px, True)

def similarity_scaled(g, d, ox, oy):
    n = same = 0
    for y in range(0, g.h, 3):
        for x in range(0, g.w, 3):
            dx, dy = int(x * SCALE + ox + .5), int(y * SCALE + oy + .5)
            if dx >= d.w or dy >= d.h: continue
            n += 1
            same += close(g.rgb(y * g.w + x), d.rgb(dy * d.w + dx))
    return same / n

def method_scaled(g, jp, en, at):
    ox, oy = at
    if similarity_scaled(g, jp, ox, oy) < MATCH: return None
    mask = dilate(en.w, en.h, changed(jp, en), 1)
    near = Matcher(g.pal, g.bpp8)
    px = bytearray(g.px)
    for y in range(g.h):
        y0, y1 = y * SCALE + oy, (y + 1) * SCALE + oy
        if y1 > en.h: break
        for x in range(g.w):
            x0, x1 = x * SCALE + ox, (x + 1) * SCALE + ox
            if x1 > en.w: break
            if any(mask[yy * en.w + xx] for yy in range(int(y0), min(en.h, int(y1) + 1))
                   for xx in range(int(x0), min(en.w, int(x1) + 1))):
                px[y * g.w + x] = near(area(en, x0, y0, x1, y1))
    return Pic(g.w, g.h, g.pal, px, g.bpp8)

# --- pages of text ---
def bands(rows):
    """[(first, last)] runs of True in rows."""
    out, y = [], 0
    while y < len(rows):
        if rows[y]:
            y0 = y
            while y < len(rows) and rows[y]: y += 1
            out.append((y0, y - 1))
        else: y += 1
    return out

def squeeze(line, width):
    """Narrow a line (rows of 0/1, cropped to its ink) to `width` by taking columns out of the
    widest gaps between letters."""
    w = len(line[0])
    ink = [any(r[x] for r in line) for x in range(w)]
    gaps = [[x0, x1 - x0 + 1] for x0, x1 in bands([not v for v in ink])]
    cut = set()
    need = w - width
    while need > 0:
        g = max(gaps, key=lambda g: g[1], default=None)
        if not g or g[1] < 2: raise SystemExit('pictures: a line of text does not fit')
        g[1] -= 1; need -= 1
        cut.add(g[0] + g[1])          # take the gap's last remaining column
    keep = [x for x in range(w) if x not in cut]
    return [[r[x] for x in keep] for r in line]

def method_page(g, jp, en, drop=None, box=(0, 0, 240, 142), keep=144):
    """Set the English page's text into box (x0, y0, x1, y1) of the GBA page, after clearing the
    GBA's own text above row `keep` (the rows below hold the GBA's page number and arrow, and
    the Court Record's B / L Back prompt covers the bottom right); drop: a rectangle of the DS
    page left out (its page number)."""
    def counts(p):
        c = [0] * len(p.pal)
        for v in p.px: c[v] += 1
        return c
    ce, cg = counts(en), counts(g)
    bg_e = max(range(len(ce)), key=ce.__getitem__)
    bg_g = max(range(len(cg)), key=cg.__getitem__)
    inks = [i for i in range(len(ce)) if ce[i] and i != bg_e]
    if len(inks) != 1 or colour(en.pal[bg_e]) != colour(g.pal[bg_g]): return None
    ink_g = [i for i in range(len(g.pal)) if cg[i] and colour(g.pal[i]) == colour(en.pal[inks[0]])]
    if len(ink_g) != 1: return None
    ink_g = ink_g[0]
    m = [[1 if en.px[y * en.w + x] != bg_e else 0 for x in range(en.w)] for y in range(en.h)]
    if drop:
        for y in range(drop[1], drop[3]):
            for x in range(drop[0], drop[2]): m[y][x] = 0
    lines = []
    for y0, y1 in bands([any(r) for r in m]):
        cols = [x for x in range(en.w) if any(m[y][x] for y in range(y0, y1 + 1))]
        lines.append([y0, cols[0], [m[y][cols[0]:cols[-1] + 1] for y in range(y0, y1 + 1)]])
    bx0, by0, bx1, by1 = box
    room = bx1 - bx0 - 2
    for ln in lines:
        if len(ln[2][0]) > room: ln[2] = squeeze(ln[2], room)
    left = min(ln[1] for ln in lines)
    right = max(ln[1] + len(ln[2][0]) for ln in lines)
    if right - left > room:                       # squeezed lines: keep them inside the box
        for ln in lines: ln[1] = min(ln[1], left + room - len(ln[2][0]))
        right = left + room
    # vertical: close up the gaps between lines, keeping their proportions, until the page fits
    top = lines[0][0]
    height = lines[-1][0] + len(lines[-1][2]) - top
    gaps = [lines[k + 1][0] - (lines[k][0] + len(lines[k][2])) for k in range(len(lines) - 1)]
    orig = gaps[:]
    while height > by1 - by0 - 4:          # 2 rows clear at the top and bottom
        k = max((k for k in range(len(gaps)) if gaps[k] > 1), key=lambda k: (gaps[k] / orig[k], gaps[k]), default=None)
        if k is None: raise SystemExit('pictures: a page of text does not fit')
        gaps[k] -= 1; height -= 1
    dx = bx0 + (bx1 - bx0 - (right - left)) // 2 - left
    oy = (en.h - g.h) // 2
    y = max(by0 + 2, min(max(top - oy, by0 + 6), by1 - 2 - height))
    px = bytearray(g.px)
    px[:keep * g.w] = bytes([bg_g]) * (keep * g.w)
    for k, (y0, x0, rows) in enumerate(lines):
        for r, row in enumerate(rows):
            for c, v in enumerate(row):
                if v: px[(y + r) * g.w + x0 + dx + c] = ink_g
        if k < len(gaps): y += len(rows) + gaps[k]
    return Pic(g.w, g.h, g.pal, px, g.bpp8)

METHODS = {'diff': method_diff, 'whole': method_whole, 'fit': method_fit, 'scaled': method_scaled,
           'page': method_page}

def make(rom, ctx, lang, entry, how, opts):
    """-> (old object, new Pic, old chunks)"""
    def lang_pic(table):
        o, size = struct.unpack_from('<II', ctx.arm9, table - DS_ARM9 + 8 * lang)
        return ds_picture(ctx.data, o)
    obj, flags = struct.unpack_from('<II', rom.d, IMAGE_TABLE - 0x08000000 + 8 * entry)
    jp, en = lang_pic(LANG_JP), lang_pic(LANG_EN)
    g, chunks = gba_picture(rom, obj, not flags >> 31)
    if g.bpp8 != jp.bpp8 or (jp.w, jp.h) != (en.w, en.h):
        raise SystemExit(f'pictures: image {entry} does not match DS picture {lang}')
    new = METHODS[how](g, jp, en, **opts)
    if new is None:
        raise SystemExit(f'pictures: image {entry} does not match DS picture {lang} ({how})')
    return obj, new, chunks

def apply(rom, ctx):
    if struct.unpack_from('<II', ctx.arm9, LANG_JP - DS_ARM9 + 8 * LANG_N) != (0, 0):
        raise SystemExit('pictures: unexpected DS picture tables')
    entries = [struct.unpack_from('<II', rom.d, IMAGE_TABLE - 0x08000000 + 8 * k) for k in range(IMAGES)]
    total = 0
    for lang, entry, how, opts in PICTURES:
        obj, new, chunks = make(rom, ctx, lang, entry, how, opts)
        pal = struct.pack('<%dH' % len(new.pal), *new.pal)
        data = chunkimg.build(pal, retile(new), [len(c) for c, _ in chunks], chunks)
        addr = rom.store(data, 'ext', 4, f'picture {entry}')
        for k, (o, f) in enumerate(entries):
            if o == obj: rom.w32(IMAGE_TABLE + 8 * k, addr)
        total += 1
    print(f"  pictures with writing: {total} from the DS English ones")
