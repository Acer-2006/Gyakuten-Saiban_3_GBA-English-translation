#!/usr/bin/env python3
"""Render text with the DS font into GBA 4bpp sprite/tile graphics (pure Python)."""
import struct
import dsfont

class Font:
    def __init__(self, rows, widths):
        self.rows = rows; self.widths = widths
    @classmethod
    def from_ctx(cls, ctx):
        rows, widths = dsfont.tables(ctx.data, ctx.arm9)
        return cls(rows, widths)
    def slot(self, ch):
        from labels_en import encode
        code = encode(ch)[0]
        if 0x80 <= code < 0x180: return code - 0x80
        if 0x680 <= code < 0x698: return 0x100 + code - 0x680
        return dsfont.MISSING
    def glyph(self, ch):
        s = self.slot(ch)
        return [struct.unpack_from('<H', self.rows, (s * 16 + r) * 2)[0] for r in range(16)], self.widths[s]
    def measure(self, text):
        return sum(self.glyph(c)[1] for c in text)

def render(font, text, w, h=16, fill=1, outline=None, align='center', y0=0, squeeze=0, kern=None):
    """-> list of h rows, each a list of w palette indices (0 = transparent).  squeeze takes that
    many pixels out of every gap; kern {two characters: pixels} adds to the gap between a pair."""
    grid = [[0] * w for _ in range(h)]
    extra = [(kern or {}).get(text[i:i + 2], 0) for i in range(len(text))]
    tw = font.measure(text) - squeeze * max(0, len(text) - 1) + sum(extra[:-1])
    x = {'center': (w - tw) // 2, 'left': 0, 'right': w - tw}[align]
    if x < 0: x = 0
    for ch, more in zip(text, extra):
        rows, adv = font.glyph(ch)
        for r in range(16):
            yy = y0 + r
            if yy < 0 or yy >= h: continue
            bits = rows[r]
            for k in range(16):
                if bits & (1 << (15 - k)):
                    xx = x + k
                    if 0 <= xx < w: grid[yy][xx] = fill
        x += adv - squeeze + more
    if outline is not None:
        src = [row[:] for row in grid]
        for y in range(h):
            for x in range(w):
                if src[y][x] == fill: continue
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        yy, xx = y + dy, x + dx
                        if 0 <= yy < h and 0 <= xx < w and src[yy][xx] == fill:
                            grid[y][x] = outline; break
                    if grid[y][x] == outline: break
    return grid

def tile4(grid, x0, y0):
    out = bytearray()
    for y in range(8):
        for x in range(0, 8, 2):
            a = grid[y0 + y][x0 + x]; b = grid[y0 + y][x0 + x + 1]
            out.append((a & 15) | ((b & 15) << 4))
    return bytes(out)

def sprite_cells(grid, cell_w, cell_h):
    """Pack a (cell_h*k) x (cell_w*n) grid into 1D-mapped sprite cells of cell_w x cell_h,
    left to right then top to bottom; each cell's tiles row-major."""
    h = len(grid); w = len(grid[0])
    out = bytearray()
    for cy in range(0, h, cell_h):
        for cx in range(0, w, cell_w):
            for ty in range(0, cell_h, 8):
                for tx in range(0, cell_w, 8):
                    out += tile4(grid, cx + tx, cy + ty)
    return bytes(out)
