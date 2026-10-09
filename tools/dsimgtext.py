#!/usr/bin/env python3
"""Read the text of the DS version's pre-rendered English text images.

Some English text in Trials and Tribulations is not in the script but in images: the Court
Record descriptions (256x64 textures in data.bin, three lines of text in the dialogue font).
The images were drawn with the same font the game uses for dialogue, so the text can be read
back exactly: every glyph is matched pixel for pixel against the font in the user's own DS ROM,
and the whole line has to be accounted for, ink and gaps.

How the images are set: each glyph is drawn at the pen position rounded down to an even x (two
4bpp pixels per byte), and the pen advances by the glyph's width from the font's width table.
The tool that drew them used one or two widths that differ by a pixel from the game's table
(the double quote, for example), so a width may be off by one.  It also had two symbols that
the game's font lacks, a multiplication sign and a narrow equals sign; they are described below
by their shape.
"""
import struct
import dsfont

# characters for the codes the English text uses (same encoding as the script)
def _charmap():
    m = {}
    for i in range(10): m[0x80 + i] = chr(48 + i)
    for i in range(26): m[0x8a + i] = chr(65 + i); m[0xa4 + i] = chr(97 + i)
    m.update({0xbe: '!', 0xbf: '?', 0x161: '.', 0x165: '(', 0x166: ')', 0x16d: ':', 0x16f: ',',
              0x170: '+', 0x171: '/', 0x172: '*', 0x173: "'", 0x177: '%', 0x179: '~', 0x17c: '&', 0x17d: '☆'})
    for i, ch in enumerate('-"[]$#><=■éá;çàÇûîèâñïê'): m[0x681 + i] = ch
    return m

CHARS = _charmap()
SPACE = 0x17f
# search order: lowercase first (so an ambiguous shape reads as the common letter), then the rest
ORDER = (list(range(0xa4, 0xbe)) + list(range(0x8a, 0xa4)) + list(range(0x80, 0x8a)) +
         [0x161, 0x16f, 0x173, 0xbe, 0xbf, 0x16d, 0x171, 0x681, 0x682, 0x165, 0x166, 0x17d, 0x17c,
          0x177, 0x170, 0x172, 0x179] + list(range(0x683, 0x698)))

def _cols_from_rows(rows):
    """16 row bitmasks (bit 15 = x 0) -> 16 column bitmasks (bit k = row k)."""
    cols = []
    for x in range(16):
        m = 0
        for k in range(16):
            if rows[k] & (1 << (15 - x)): m |= 1 << k
        cols.append(m)
    return cols

def _synthetic():
    """Symbols the image tool had but the game's font does not."""
    times = [0] * 16                                   # 10x10 diagonal cross, rows 1..10
    for c in range(10): times[1 + c] = (1 << (1 + c)) | (1 << (10 - c))
    equals = [0] * 16                                  # two 5-pixel bars on rows 4 and 8
    for c in range(5): equals[1 + c] = (1 << 4) | (1 << 8)
    return [('×', times, 12, (0, -1, 1, -2, 2)), ('=', equals, 7, (0, 1, -1, 2, -2))]

class TextReader:
    def __init__(self, data, arm9):
        self.glyphs = []          # (char, column masks, width, width tolerances)
        for code in ORDER:
            rows = dsfont.glyph_rows(data, code)
            if not any(rows): continue
            self.glyphs.append((CHARS[code], _cols_from_rows(rows), dsfont.glyph_width(arm9, code), (0, 1, -1)))
        self.glyphs += _synthetic()
        self.space = dsfont.glyph_width(arm9, SPACE)

    def read_line(self, masks):
        """masks: one 16-bit ink mask per column (bit k = row k of the line).  -> str or None."""
        W = len(masks)
        first = next((x for x, m in enumerate(masks) if m), None)
        if first is None: return ''
        def colm(x): return masks[x] if 0 <= x < W else 0
        memo = {}
        def go(pen):
            if pen in memo: return memo[pen]
            x = pen & ~1
            if not any(masks[max(0, x):]): memo[pen] = ''; return ''
            res = None
            for ch, cols, wd, tol in self.glyphs:
                if colm(x) != cols[0]: continue
                for dt in tol:
                    nx = (pen + wd + dt) & ~1
                    if any(colm(x + i) != (cols[i] if i < 16 else 0) for i in range(max(nx - x, 0))): continue
                    if any(cols[i] & ~colm(x + i) for i in range(max(nx - x, 0), 16)): continue
                    r = go(pen + wd + dt)
                    if r is not None: res = ch + r; break
                if res is not None: break
            if res is None:
                for dt in (0, 1, -1):
                    nx = (pen + self.space + dt) & ~1
                    if not any(colm(x + i) for i in range(nx - x)):
                        r = go(pen + self.space + dt)
                        if r is not None: res = ' ' + r; break
            memo[pen] = res
            return res
        for pen in range(max(0, first - 4), first + 1):
            r = go(pen)
            if r is not None: return r.strip()
        return None

    def read_image(self, px, w, h, pitch=16, top=0):
        """px: rows of palette indices (0 = background).  Lines are `pitch` rows apart from `top`.
        -> list of lines (None for a line that could not be read), trailing blank lines dropped."""
        lines = []
        for y0 in range(top, h - 15, pitch):
            masks = []
            for x in range(w):
                m = 0
                for k in range(16):
                    if px[y0 + k][x]: m |= 1 << k
                masks.append(m)
            lines.append(self.read_line(masks))
        while lines and lines[-1] == '': lines.pop()
        return lines

def texture(data, off):
    """DS texture file as stored in data.bin: {u8 format, u8 log2(w/8), u8 log2(h/8), u8 0,
    u32 image offset (0x14), u32 image size, u32 palette offset, u32 palette size}.
    -> (rows of pixel values, width, height, palette bytes); only 16-colour textures (format 3)."""
    fmt, s, t, z, ioff, isz, poff, psz = struct.unpack_from('<4B4I', data, off)
    w, h = 8 << s, 8 << t
    if fmt != 3 or z != 0 or ioff != 0x14 or isz != w * h // 2 or poff != ioff + isz:
        raise ValueError(f'not a 16-colour texture at {off:#x}')
    px = []
    for y in range(h):
        row = []
        for b in data[off + ioff + y * w // 2: off + ioff + (y + 1) * w // 2]:
            row.append(b & 15); row.append(b >> 4)
        px.append(row)
    return px, w, h, data[off + poff: off + poff + psz]

def texture_size(data, off):
    fmt, s, t, z, ioff, isz, poff, psz = struct.unpack_from('<4B4I', data, off)
    return poff + psz
