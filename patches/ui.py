"""Buttons drawn as raw sprites (the sheet around 0x0818a720), redrawn in English with the DS font.

Each graphic is 64x16 or 32x16 pixels stored as 32x16 one-dimensional sprite cells (4x2 tiles,
row-major, 256 bytes); see hacking/docs/graphics.md.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
import textgfx

# cross-examination buttons, OBJ palette 5: a white box (index 1) with dark lettering (3, grey 2
# for the anti-aliasing) and the L / R button icon at one end.  (address, cells, box interior
# x0, x1, text)
BUTTONS = [
    (0x0818a720, 2, 12, 62, 'Press'),       # L ゆさぶる, bottom left
    (0x0818a920, 2, 2, 53, 'Present'),      # つきつける R, bottom right
]
# Court Record prompts next to the A / B icons, OBJ palette 4: white lettering (12) with a dark
# outline (10) on a transparent background, like the R label (patches/court_record.py)
PROMPTS = [
    (0x0818ab20, 'OK'),                     # 決定
    (0x0818ac20, 'Back'),                   # もどる
]

def unpack_cells(data, w, h=16, cw=32, ch=16):
    """Inverse of textgfx.sprite_cells: cells left to right, top to bottom -> rows of indices."""
    grid = [[0] * w for _ in range(h)]
    k = 0
    for cy in range(0, h, ch):
        for cx in range(0, w, cw):
            for ty in range(0, ch, 8):
                for tx in range(0, cw, 8):
                    for y in range(8):
                        for x in range(0, 8, 2):
                            b = data[k]; k += 1
                            grid[cy + ty + y][cx + tx + x] = b & 15
                            grid[cy + ty + y][cx + tx + x + 1] = b >> 4
    return grid

def fit(font, text, width, **kw):
    """Render text centred in `width`, squeezing the letter spacing until it fits."""
    sq = 0
    while font.measure(text) - sq * (len(text) - 1) > width and sq < 3: sq += 1
    return textgfx.render(font, text, width, 16, squeeze=sq, **kw)

def apply(rom, ctx):
    font = textgfx.Font.from_ctx(ctx)
    for addr, cells, x0, x1, text in BUTTONS:
        grid = unpack_cells(rom.read(addr, cells * 256), cells * 32)
        for y in range(13):                      # clear the Japanese lettering inside the box
            for x in range(x0, x1):
                if grid[y][x] in (2, 3): grid[y][x] = 1
        txt = fit(font, text, x1 - x0, fill=3)
        for y in range(13):
            for x in range(x1 - x0):
                if txt[y][x]: grid[y][x0 + x] = txt[y][x]
        rom.write(addr, textgfx.sprite_cells(grid, 32, 16), 'button ' + text)
    for addr, text in PROMPTS:
        sq = 0
        while font.measure(text) - sq * (len(text) - 1) > 29: sq += 1
        grid = textgfx.render(font, text, 32, 16, fill=12, outline=10, align='left', y0=2, squeeze=sq)
        rom.write(addr, textgfx.sprite_cells(grid, 32, 16), 'prompt ' + text)
    print(f"  buttons: {len(BUTTONS) + len(PROMPTS)} redrawn")
