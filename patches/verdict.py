"""The verdict in English: NOT GUILTY / GUILTY.

Script command 0x44 (handler 0x080209dc) shows the verdict as two 64x64 sprites that slam in one
after the other, left then right: raw 4bpp pictures (8x8 tiles, 1D order, 2 KB each) DMA'd to
OBJ tile 0x1a0 and 0x1e0.  Not guilty copies 無 (0x0818bb00) and 罪 (0x0818cb00), 2 KB each;
guilty copies 4 KB from 0x0818c300, 有 followed by that same 罪.  Index 1 is the lettering, 2 its
outline, 5 an outer edge (3 and 4 are greys for the corners); the not-guilty palette makes the
lettering white on black, the guilty one black on white.

English: NOT | GUILTY in place of 無 | 罪, and for guilty a new 4 KB picture GUILTY | ! (the
literal at 0x08020a30 is pointed at it), in tall condensed lettering: the DS dialogue font,
emboldened by a pixel and stretched to four times its height.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
import textgfx

NOT_PIC, GUILTY_PIC = 0x0818bb00, 0x0818cb00     # 無, 罪 (2 KB each)
GUILTY_SRC_LIT, GUILTY_SRC = 0x08020a30, 0x0818c300
FILL, OUTLINE, EDGE = 1, 2, 5
STRETCH = 4

def word(font, text, bold=1):
    w = font.measure(text) + 2
    g = textgfx.render(font, text, w, 16, fill=1, align='left')
    rows = [y for y in range(16) if any(g[y])]
    cols = [x for x in range(w) if any(g[y][x] for y in rows)]
    g = [r[cols[0]:cols[-1] + 1] for r in g[rows[0]:rows[-1] + 1]]
    for _ in range(bold):                                  # embolden: each pixel one to the right too
        g = [[1 if r[x] or (x and r[x - 1]) else 0 for x in range(len(r))] + [r[-1]] for r in g]
    return [r for r in g for _ in range(STRETCH)]

def picture(font, text, bold=1):
    """64x64, 8x8 tiles in 1D order."""
    g = word(font, text, bold)
    h, w = len(g), len(g[0])
    if w + 4 > 64 or h + 4 > 64: raise SystemExit(f'verdict: {text} too big')
    cv = [[0] * 64 for _ in range(64)]
    x0, y0 = (64 - w) // 2, (64 - h) // 2
    for y in range(h):
        for x in range(w):
            if g[y][x]: cv[y0 + y][x0 + x] = FILL
    for val, inner in ((OUTLINE, FILL), (EDGE, OUTLINE)):
        src = [r[:] for r in cv]
        for y in range(64):
            for x in range(64):
                if not src[y][x] and any(0 <= y + dy < 64 and 0 <= x + dx < 64 and src[y + dy][x + dx] == inner
                                         for dy in (-1, 0, 1) for dx in (-1, 0, 1)):
                    cv[y][x] = val
    return b''.join(textgfx.tile4(cv, tx * 8, ty * 8) for ty in range(8) for tx in range(8))

def apply(rom, ctx):
    font = textgfx.Font.from_ctx(ctx)
    if rom.u32(GUILTY_SRC_LIT) != GUILTY_SRC or GUILTY_SRC + 0x800 != GUILTY_PIC:
        raise SystemExit('verdict: unexpected verdict code')
    rom.write(NOT_PIC, picture(font, 'NOT'), 'verdict NOT')
    rom.write(GUILTY_PIC, picture(font, 'GUILTY'), 'verdict GUILTY')
    addr = rom.store(picture(font, 'GUILTY') + picture(font, '!', bold=3), 'ext', 4, 'verdict GUILTY !')
    rom.w32(GUILTY_SRC_LIT, addr)
    print("  verdict: NOT GUILTY / GUILTY")
