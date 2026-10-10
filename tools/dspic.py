#!/usr/bin/env python3
"""Pictures from the DS version for the GBA build (pure Python).

The DS keeps many of its sprite pictures in the formats of the GBA's effects archive (see
patches/banners.py): frame data ({u16 0, u16 frames, u32 sub-archive offset}, then the frames and
their sprite lists) and sub-archives ({u16 palettes, u16 0x8000, the palettes, cell offsets, then
cells packed with a 16-bit RLE}); its other pictures are texture files (tools/dsimgtext.py).
This module reads both into rows of palette indices (0 = transparent), shrinks a picture (area
average), maps the colours back to a palette, and covers a picture with GBA sprites.
"""
import struct

# OAM size and shape of a sprite as the frame data stores it (top nibble of the attribute):
# size << 2 | shape
SHAPE = {(8, 8): 0x0, (16, 16): 0x4, (32, 32): 0x8, (64, 64): 0xc, (16, 8): 0x1, (32, 8): 0x5,
         (32, 16): 0x9, (64, 32): 0xd, (8, 16): 0x2, (8, 32): 0x6, (16, 32): 0xa, (32, 64): 0xe}
SIZE = {v: k for k, v in SHAPE.items()}

# --- the effects archive formats ---------------------------------------------------------------
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

def sub_archive(data, s):
    """-> (palettes, flag, [palette: 16 BGR555 values], [absolute cell offsets])"""
    npal, flag = struct.unpack_from('<HH', data, s)
    pals = [list(struct.unpack_from('<16H', data, s + 4 + 32 * k)) for k in range(npal)]
    tab = s + 4 + 32 * npal
    n = struct.unpack_from('<I', data, tab)[0] // 4
    return npal, flag, pals, [tab + struct.unpack_from('<I', data, tab + 4 * i)[0] for i in range(n)]

def frame_data(data, f):
    """-> (sub-archive offset, [(sprite list offset, duration)], {offset: [(x, y, w, h, cell, attr)]})"""
    z, n, sub = struct.unpack_from('<HHI', data, f)
    fl = [struct.unpack_from('<HH', data, f + 8 + 8 * i) for i in range(n)]
    defs = {}
    for off, _ in fl:
        if off in defs: continue
        sp = []
        for j in range(struct.unpack_from('<H', data, f + off)[0]):
            pos, attr = struct.unpack_from('<HH', data, f + off + 4 + 4 * j)
            x, y = pos & 0xff, pos >> 8
            w, h = SIZE[attr >> 12]
            sp.append((x - 256 if x >= 128 else x, y - 256 if y >= 128 else y, w, h, attr & 0x1ff, attr))
        defs[off] = sp
    return sub, fl, defs

def tiles_to_rows(raw, w, h):
    """4bpp tiles in 1D order (a sprite cell) -> h rows of w indices."""
    px = [[0] * w for _ in range(h)]
    tw = w // 8
    for t in range(tw * (h // 8)):
        oy, ox = (t // tw) * 8, (t % tw) * 8
        for y in range(8):
            row = px[oy + y]
            for x in range(0, 8, 2):
                b = raw[t * 32 + y * 4 + x // 2]
                row[ox + x] = b & 15; row[ox + x + 1] = b >> 4
    return px

def rows_to_tiles(px, x0, y0, w, h):
    """The w x h area at (x0, y0) of rows of indices -> 4bpp tiles in 1D order."""
    out = bytearray()
    for ty in range(y0, y0 + h, 8):
        for tx in range(x0, x0 + w, 8):
            for y in range(ty, ty + 8):
                row = px[y]
                for x in range(tx, tx + 8, 2):
                    out.append((row[x] & 15) | (row[x + 1] & 15) << 4)
    return bytes(out)

def compose(data, sprites, cells, w, h, ax, ay):
    """Paste a frame's sprites (as frame_data lists them) into a w x h picture whose anchor is
    at (ax, ay); later sprites go over earlier ones, as on the screen (the game gives them the
    lower OAM numbers)."""
    px = [[0] * w for _ in range(h)]
    for x, y, sw, sh, c, attr in sprites:
        g = tiles_to_rows(unrle16(data, cells[c], sw * sh // 2), sw, sh)
        for yy in range(sh):
            for xx in range(sw):
                v = g[yy][sw - 1 - xx if attr & 0x200 else xx]
                if v: px[ay + y + yy][ax + x + xx] = v
    return px

def write_sub(npal, flag, pals, cells):
    """A sub-archive from palettes (lists of 16 values) and packed cells."""
    table = bytearray(); body = bytearray()
    for c in cells:
        table += struct.pack('<I', 4 * len(cells) + len(body))
        body += c
        while len(body) % 2: body.append(0)
    return (struct.pack('<HH', npal, flag) + b''.join(struct.pack('<16H', *p) for p in pals) +
            bytes(table) + bytes(body))

# --- shrinking and colours -----------------------------------------------------------------------
def rgb(v):
    return (v & 31, v >> 5 & 31, v >> 10 & 31)

def _weights(n_src, n_dst):
    f = n_src / n_dst
    out = []
    for d in range(n_dst):
        a, b = d * f, (d + 1) * f
        ws = []
        i = int(a)
        while i < b and i < n_src:
            lo, hi = max(a, i), min(b, i + 1)
            if hi > lo: ws.append((i, (hi - lo) / f))
            i += 1
        out.append(ws)
    return out

def shrink(px, pal, w, h):
    """Area average of a picture (rows of indices into pal, 0 transparent) to w x h.
    -> rows of (r, g, b, a): colour in 0..31 per channel, coverage a in 0..1."""
    sw, sh = len(px[0]), len(px)
    cols = [rgb(v) for v in pal]
    # premultiplied colour and coverage per source pixel
    src = [[(0.0, 0.0, 0.0, 0.0) if v == 0 else cols[v] + (1.0,) for v in row] for row in px]
    wx, wy = _weights(sw, w), _weights(sh, h)
    mid = []
    for row in src:
        out = []
        for ws in wx:
            r = g = b = a = 0.0
            for i, k in ws:
                p = row[i]
                if p[3]: r += p[0] * k; g += p[1] * k; b += p[2] * k; a += k
            out.append((r, g, b, a))
        mid.append(out)
    img = []
    for ws in wy:
        out = []
        for x in range(w):
            r = g = b = a = 0.0
            for j, k in ws:
                p = mid[j][x]
                r += p[0] * k; g += p[1] * k; b += p[2] * k; a += p[3] * k
            out.append((r / a, g / a, b / a, a) if a > 1e-9 else (0.0, 0.0, 0.0, 0.0))
        img.append(out)
    return img

def nearest(c, pal, usable):
    """The index among `usable` whose colour is nearest to c = (r, g, b) in 0..31."""
    best, bd = None, None
    for i in usable:
        r, g, b = rgb(pal[i])
        d = 3 * (r - c[0]) ** 2 + 4 * (g - c[1]) ** 2 + 2 * (b - c[2]) ** 2
        if bd is None or d < bd: best, bd = i, d
    return best

def quantize(img, pal, usable, cut=0.5):
    """Rows of (r, g, b, a) -> rows of indices: transparent where a < cut."""
    memo = {}
    out = []
    for row in img:
        o = []
        for r, g, b, a in row:
            if a < cut: o.append(0); continue
            key = (round(r * 2), round(g * 2), round(b * 2))
            if key not in memo: memo[key] = nearest((r, g, b), pal, usable)
            o.append(memo[key])
        out.append(o)
    return out

def used_indices(px):
    return sorted({v for row in px for v in row if v})

# --- sprites -------------------------------------------------------------------------------------
_TILE_SHAPES = [(8, 8), (8, 4), (4, 8), (4, 4), (4, 2), (2, 4), (2, 2), (4, 1), (1, 4), (2, 1), (1, 2), (1, 1)]

def _cover(mask, tol):
    h, w = len(mask), len(mask[0])
    left = [r[:] for r in mask]
    used = [[0] * w for _ in range(h)]
    out = []
    for sw, sh in _TILE_SHAPES:
        for y in range(h - sh + 1):
            for x in range(w - sw + 1):
                if any(used[yy][xx] for yy in range(y, y + sh) for xx in range(x, x + sw)): continue
                n = sum(left[yy][xx] for yy in range(y, y + sh) for xx in range(x, x + sw))
                if n and (n >= (1 - tol) * sw * sh or sw * sh == 1):
                    out.append((x, y, sw, sh))
                    for yy in range(y, y + sh):
                        for xx in range(x, x + sw): left[yy][xx] = 0; used[yy][xx] = 1
    return out

def cover(px, budget, steps=(0, 2, 4, 6)):
    """Sprites covering every 8x8 tile of the picture with something in it, using at most
    `budget` tiles and as few sprites as the search finds.  The picture may be moved right and
    down by a few pixels on the tile grid (`steps`).
    -> (dx, dy, [(x, y, w, h)] in pixels on the grid) or None"""
    h, w = len(px), len(px[0])
    best = None
    for dx in steps:
        for dy in steps:
            tw, th = (w + dx + 7) // 8, (h + dy + 7) // 8
            mask = [[0] * tw for _ in range(th)]
            for y in range(h):
                for x in range(w):
                    if px[y][x]: mask[(y + dy) // 8][(x + dx) // 8] = 1
            for tol in (0.3, 0.25, 0.2, 0.15, 0.1, 0.05, 0.0):
                sp = _cover(mask, tol)
                tiles = sum(a * b for x, y, a, b in sp)
                if tiles <= budget and (best is None or (len(sp), tiles) < (len(best[2]), best[3])):
                    best = (dx, dy, sp, tiles)
    if best is None: return None
    dx, dy, sp, _ = best
    return dx, dy, [(x * 8, y * 8, a * 8, b * 8) for x, y, a, b in sp]

def grid(px, dx, dy, w, h):
    """The picture placed at (dx, dy) on a w x h canvas (rows of indices)."""
    out = [[0] * w for _ in range(h)]
    for y, row in enumerate(px):
        for x, v in enumerate(row):
            if v: out[dy + y][dx + x] = v
    return out
