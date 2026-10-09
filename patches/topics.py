"""Talk topics and Move destinations in English.

GBA: the boxes listed by Talk (霧緒のこと, ...) and Move (高菱屋・地下倉庫, ...) are pictures, a
table of pointers at 0x08045d1c: entries 0-127 are the talk topics, 128-149 the places, each LZ
of 2048 bytes, a 128x32 4bpp picture stored as two 64x32 sprites (1D tile order).  The code at
0x08011158 unpacks the ones a scene lists into 0x0200afc0 and copies them to OBJ tile
0x1a0 + 0x40 * row; the highlighted box is shown with OBJ palette 9 (0x082231cc), the others
with palette 10 (0x082231ec).  The frame is the same in every picture; inside it, index 12 is
the fill and 2..12 a ramp from the lettering colour to the fill (dark red in palette 9, grey in
palette 10).

DS: the same boxes are 128x32 16-colour textures in data.bin, one after another.  The arm9
keeps their data.bin offsets at 0x020b24a4: places (Japanese, English, English), then topics
(Japanese, English, English), in the GBA's order.  Index 2 is the fill and 4..15 a ramp from
the fill to the lettering colour.  The lettering is an anti-aliased face that is not in the
game's fonts, so the English pictures are copied: every DS pixel's ink (how far its colour lies
from the fill towards the lettering colour) is set again with the GBA ramp inside the GBA
frame, and lettering wider than the frame is narrowed to fit.
"""
import os, struct, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
import lz, dsimgtext

TABLE = 0x08045d1c
TOPICS, PLACES = 128, 22             # table entries 0..127 and 128..149
PALETTE = 0x082231cc                 # OBJ palette 9, the highlighted box
DS_ARM9 = 0x02000000
DS_BASES = 0x020b24a4                # u32 places[3], topics[3] (Japanese, English, English)
W, H = 128, 32
FILL, INK = 12, 2                    # GBA ramp: index 12 (fill) .. 2 (lettering)
DS_FILL, DS_INK = 2, 15              # DS ramp
X0, X1 = 3, 124                      # lettering columns inside the frame (as the Japanese)
Y0, Y1 = 6, 25                       # rows inside the frame

def luma(c):
    return 0.299 * (c & 31) + 0.587 * (c >> 5 & 31) + 0.114 * (c >> 10 & 31)

def ramp_gba(rom):
    """[(ink, index)] for indices 2..12 of the box palette (ink 0 = fill, 1 = lettering)."""
    pal = [rom.u16(PALETTE + 2 * i) & 0x7fff for i in range(16)]
    lf, li = luma(pal[FILL]), luma(pal[INK])
    return [((lf - luma(pal[i])) / (lf - li), i) for i in range(INK, FILL + 1)]

def ink_ds(pal_bytes):
    pal = [struct.unpack_from('<H', pal_bytes, 2 * i)[0] & 0x7fff for i in range(16)]
    lf, li = luma(pal[DS_FILL]), luma(pal[DS_INK])
    return [min(1.0, max(0.0, (lf - luma(pal[i])) / (lf - li))) if 4 <= i <= 15 else 0.0
            for i in range(16)]

def unpack(data):
    """Two 64x32 sprites (1D) -> rows of indices."""
    g = [[0] * W for _ in range(H)]
    for s in range(2):
        for t in range(32):
            for y in range(8):
                for x in range(8):
                    b = data[s * 1024 + t * 32 + y * 4 + x // 2]
                    g[(t // 8) * 8 + y][s * 64 + (t % 8) * 8 + x] = b >> 4 if x & 1 else b & 15
    return g

def pack(g):
    out = bytearray()
    for s in range(2):
        for t in range(32):
            for y in range(8):
                row = g[(t // 8) * 8 + y]
                for x in range(0, 8, 2):
                    x0 = s * 64 + (t % 8) * 8 + x
                    out.append((row[x0] & 15) | ((row[x0 + 1] & 15) << 4))
    return bytes(out)

def lettering(px, ink):
    """DS texture rows -> (ink rows inside the DS frame, first row): the coverage of each pixel."""
    rows = [[ink[v] for v in r] for r in px[5:27]]
    return rows, 5

def fit(rows, width):
    """Crop to the inked columns; narrow (area average) to `width` if wider."""
    cols = [x for x in range(len(rows[0])) if any(r[x] > 0 for r in rows)]
    if not cols: return [[] for _ in rows]
    a, b = cols[0], cols[-1] + 1
    rows = [r[a:b] for r in rows]
    w = b - a
    if w <= width: return rows
    s = w / width                            # source pixels per output pixel
    out = []
    for r in rows:
        o = []
        for j in range(width):
            lo, hi = j * s, (j + 1) * s
            acc, k = 0.0, int(lo)
            while k < hi and k < w:
                acc += r[k] * (min(hi, k + 1) - max(lo, k)); k += 1
            o.append(acc / s)
        out.append(o)
    return out

def picture(orig, px, ink, levels):
    g = [r[:] for r in orig]
    for y in range(Y0, Y1 + 1):                          # clear the Japanese lettering
        for x in range(X0 - 1, X1 + 2):
            if (y, x) != (Y1, X1 + 1): g[y][x] = FILL
    rows, top = lettering(px, ink)
    rows = fit(rows, X1 - X0 + 1)
    used = [i for i, r in enumerate(rows) if any(v > 0 for v in r)]
    if not used: raise ValueError('empty picture')
    w = len(rows[used[0]])
    y_first, y_last = top + used[0], top + used[-1]
    dy = min(0, Y1 - y_last) + max(0, Y0 - y_first)   # keep descenders inside the frame
    x0 = X0 + (X1 - X0 + 1 - w) // 2
    for i in used:
        for x, v in enumerate(rows[i]):
            if v <= 0.02: continue
            g[top + i + dy][x0 + x] = min(levels, key=lambda l: abs(l[0] - v))[1]
    return g

def apply(rom, ctx):
    d, arm9 = ctx.data, ctx.arm9
    places_jp, places_en, _, topics_jp, topics_en, _ = struct.unpack_from('<6I', arm9, DS_BASES - DS_ARM9)
    size = dsimgtext.texture_size(d, topics_en)
    # the DS lists must match the GBA's: same number of places and topics
    if (places_en - places_jp) // size != PLACES or (topics_en - topics_jp) // size != TOPICS:
        raise SystemExit('topics: the DS place / topic lists are not the expected size')
    levels = ramp_gba(rom)
    stored = {}
    for k in range(TOPICS + PLACES):
        p = rom.u32(TABLE + 4 * k)
        data, _ = lz.decompress(rom.d, p - 0x08000000)
        if len(data) != 2048:
            raise SystemExit(f'topics: unexpected picture {k} at {p:#x}')
        src = topics_en + k * size if k < TOPICS else places_en + (k - TOPICS) * size
        px, w, h, pal = dsimgtext.texture(d, src)
        if (w, h) != (W, H):
            raise SystemExit(f'topics: DS picture {k} is {w}x{h}')
        g = picture(unpack(data), px, ink_ds(pal), levels)
        blob = lz.compress(pack(g))
        if blob not in stored: stored[blob] = rom.store(blob, 'ext', 4, f'topic {k}')
        rom.w32(TABLE + 4 * k, stored[blob])
    print(f"  topics: {TOPICS} talk topics and {PLACES} places in English")
