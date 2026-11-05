#!/usr/bin/env python3
"""English font tables from the DS ROM.

Glyphs are 16x16 4bpp (four 8x8 tiles: TL, TR, BL, BR) in data.bin; the Latin block
(codes 0x80..0x17f) starts at 0x58920, everything else is addressed as sheet index code-0x80 from
0x27920.  Advance widths are a byte table in arm9 (0xac2c0: codes 0x80.., then +0x100 for the
accented letters 0x681..).  We keep the shapes as 1-bit rows (any non-zero pixel is ink) and the
widths; the renderer colours the glyph itself.

Glyph slots used by the renderer: 0x000..0x0ff -> codes 0x80..0x17f, 0x100..0x117 -> codes
0x680..0x697, 0x118 -> the 'missing glyph' box.
"""
import struct

LATIN_BASE = 0x58920
SHEET_BASE = 0x27920
WIDTH_TAB = 0xac2c0
NGLYPH = 0x119
MISSING = 0x118

def slot_codes():
    return [0x80 + i for i in range(0x100)] + [0x680 + i for i in range(0x18)]

def glyph_rows(data, code):
    off = LATIN_BASE + (code - 0x80) * 128 if code < 0x180 else SHEET_BASE + (code - 0x80) * 128
    rows = [0] * 16
    for t, (ox, oy) in enumerate(((0, 0), (8, 0), (0, 8), (8, 8))):
        base = off + t * 32
        for i in range(32):
            b = data[base + i]
            y = oy + i // 4; x = ox + (i % 4) * 2
            if b & 15: rows[y] |= 1 << (15 - x)
            if b >> 4: rows[y] |= 1 << (14 - x)
    return rows

def glyph_width(arm9, code):
    if 0x80 <= code < 0x180: return arm9[WIDTH_TAB + code - 0x80]
    if 0x681 <= code < 0x698: return arm9[WIDTH_TAB + 0x100 + code - 0x681]
    return 14

def tables(data, arm9, clear_top=False):
    """-> (rows: u16[NGLYPH*16] bytes, widths: u8[NGLYPH] bytes).  clear_top: every glyph with ink
    in its top row is moved a row down (see below)."""
    rows = []; widths = []
    for code in slot_codes():
        r = glyph_rows(data, code)
        if clear_top and r[0] and not r[15]: r = [0] + r[:15]
        rows += r; widths.append(glyph_width(arm9, code))
    # missing glyph: a hollow box
    rows += [0x7ffe if r in (2, 12) else (0x4002 if 2 < r < 12 else 0) for r in range(16)]
    widths.append(10)
    assert len(widths) == NGLYPH
    return b''.join(struct.pack('<H', r) for r in rows), bytes(widths)

# The DS sets its lines 16 pixels apart, the GBA's box 14.  The letters take rows 1-13 of the
# glyph (capitals 1-10, descenders to 13), but a few marks reach a row higher: the apostrophe, the
# quotation mark, the brackets, $ and # (and the star).  14 pixels apart, a mark on a line's top
# row came right under the descenders of the line above ("grandfather" over '"Violetta"': the
# quotation mark under the g), with no row between them.  The renderer's font (patches/text.py)
# has those marks a row lower, their tops level with the capitals', which keeps a row clear
# between any two lines.  (The pictures drawn with the font, tools/textgfx.py, keep the DS's.)

def width_map(arm9):
    """code -> advance width, for the script line-measuring in the converter."""
    return {c: glyph_width(arm9, c) for c in slot_codes()}
