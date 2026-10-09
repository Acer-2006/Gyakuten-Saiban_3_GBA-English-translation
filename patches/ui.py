"""Buttons drawn as raw sprites (the sheet around 0x0818a720), redrawn in English with the DS font.

Each graphic is 64x16 or 32x16 pixels stored as 32x16 one-dimensional sprite cells (4x2 tiles,
row-major, 256 bytes); see hacking/docs/graphics.md.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
import textgfx, smallfont

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

# investigation menu tabs (slide down from the top of the screen): 64x32 sprites, the lettering in
# rows 16-28; fill 1, lettering 3 (white), outline 14 (shows on the selected tab, OBJ palette 6;
# the others use palette 5)
TABS = [
    (0x08188b20, 'Examine'),                # 調べる
    (0x08188f20, 'Move'),                   # 移動する
    (0x08189320, 'Talk'),                   # 話す
    (0x08189720, 'Present'),                # つきつける
]

# save screen header 記録: two 32x32 glyphs in the UI BG tile sheet (0x08180820, DMA'd to char
# block 0), tiles 0x60-0x6f and 0x70-0x7f, placed by the screen's BG2 map (0x0803bf44, 32 wide)
# at columns 10-13 and 18-21 of rows 3-6.  BG palette 0: grey (3) lettering with a white (8)
# outline on dark red (9).  English: one 64x32 picture in the same 32 tiles, columns 12-19.
SAVE_TILES, SAVE_MAP = 0x08181420, 0x0803bf44
SAVE_ROWS, SAVE_COL0 = (3, 4, 5, 6), 10
SAVE_TEXT = 'SAVE'
SAVE_BG, SAVE_FILL, SAVE_OUTLINE, SAVE_PLAIN = 9, 3, 8, 0x40

# save screen はい / いいえ: 0x0819a070, two 64x32 sprites (1D) in the Talk-topic box style (OBJ
# palette 9 for the highlighted one, 10 for the other; 12 fill, dark lettering)
YESNO, YESNO_TEXT = 0x0819a070, ('Yes', 'No')
YESNO_FILL, YESNO_INK = 12, 4
# the continue screen (after Continue on the title) in the same style, two 128x32 boxes of two
# 64x32 sprites each, at (56, 98) and (56, 130): 中断したところから (from where the game was
# suspended) and この章のはじめから (from the start of this part)
CONTINUE, CONTINUE_TEXT = 0x08199070, ('Resume Play', 'Restart Part')
# the note under them (※ゲーム中にSTARTボタンを押せば、いつでも記録することができます。): 0x0818e720,
# 80 tiles shown as a 160x32 line at (40, 128): two 64x32 sprites, then a 32x32 column of four
# 32x8 strips whose tiles are stored in the order of rows 0, 2, 1, 3; OBJ palette 13, white (1)
# lettering, START in light blue (6), dark outline (5)
HELP = 0x0818e720
HELP_LINES = ('You can save at any time during', 'the game by pressing START.')
HELP_HIGHLIGHT = 'START'
HELP_FILL, HELP_HL, HELP_OUTLINE = 1, 6, 5

def box_button(rom, font, addr, width, text):
    """A box button of `width` // 64 sprites of 64x32 (1D): rows 6-25 and columns 2 to width - 4
    are the inside of the box; the text goes there, centred and bold."""
    n = width // 64
    grid = [sum((unpack_cells(rom.read(addr + 1024 * i, 1024), 64, 32, 64, 32)[y] for i in range(n)), [])
            for y in range(32)]
    if grid[6][2] != YESNO_FILL or grid[24][width - 4] != YESNO_FILL:
        raise SystemExit(f'ui: unexpected box button at {addr:#x}')
    for y in range(7, 25):
        for x in range(3, width - 4):
            grid[y][x] = YESNO_FILL
    w = font.measure(text) + 1
    if w > width - 7: raise SystemExit(f'ui: {text!r} does not fit its button')
    g = textgfx.render(font, text, w + 1, 16, fill=1, align='left')
    x0 = 2 + (width - 4 - w) // 2
    for y in range(16):
        for x in range(w):
            if g[y][x] or (x and g[y][x - 1]): grid[8 + y][x0 + x] = YESNO_INK   # bold
    rom.write(addr, b''.join(textgfx.sprite_cells([r[64 * i:64 * i + 64] for r in grid], 64, 32)
                             for i in range(n)), 'button ' + text)

def yes_no(rom, font):
    for k, text in enumerate(YESNO_TEXT):
        box_button(rom, font, YESNO + 1024 * k, 64, text)
    for k, text in enumerate(CONTINUE_TEXT):
        box_button(rom, font, CONTINUE + 2048 * k, 128, text)

def help_note(rom):
    cv = [[0] * 160 for _ in range(32)]
    for i, line in enumerate(HELP_LINES):
        x = (160 - smallfont.measure(line)) // 2
        y = 6 + 12 * i
        for j, part in enumerate(line.split(HELP_HIGHLIGHT)):
            if j:
                smallfont.render(HELP_HIGHLIGHT, cv, x, y, HELP_HL); x += smallfont.measure(HELP_HIGHLIGHT)
            smallfont.render(part, cv, x, y, HELP_FILL); x += smallfont.measure(part)
    src = [r[:] for r in cv]
    for y in range(32):
        for x in range(160):
            if not src[y][x] and any(0 <= y + dy < 32 and 0 <= x + dx < 160 and src[y + dy][x + dx] in (HELP_FILL, HELP_HL)
                                     for dy in (-1, 0, 1) for dx in (-1, 0, 1)):
                cv[y][x] = HELP_OUTLINE
    out = textgfx.sprite_cells([r[0:64] for r in cv], 64, 32) + textgfx.sprite_cells([r[64:128] for r in cv], 64, 32)
    for row in (0, 2, 1, 3):                     # the 32x8 strips
        out += b''.join(textgfx.tile4([r[128:160] for r in cv], tx * 8, row * 8) for tx in range(4))
    if len(out) != 2560: raise SystemExit('ui: help note size')
    rom.write(HELP, out, 'save note')

def save_header(rom):
    from .shouts import lettering
    old = [[rom.u16(SAVE_MAP + 2 * (r * 32 + c)) for c in range(SAVE_COL0, SAVE_COL0 + 12)] for r in SAVE_ROWS]
    want = [[0x60 + 4 * k + j for j in range(4)] + [SAVE_PLAIN] * 4 + [0x70 + 4 * k + j for j in range(4)]
            for k in range(4)]
    if old != want: raise SystemExit('ui: unexpected save screen map')
    m = lettering(SAVE_TEXT)
    h, w = len(m), len(m[0])
    if w + 2 > 64 or h + 2 > 32: raise SystemExit('ui: save header too big')
    cv = [[SAVE_BG] * 64 for _ in range(32)]
    x0, y0 = (64 - w) // 2, (32 - h) // 2
    for y in range(h):
        for x in range(w):
            if m[y][x]: cv[y0 + y][x0 + x] = SAVE_FILL
    src = [r[:] for r in cv]
    for y in range(32):
        for x in range(64):
            if src[y][x] != SAVE_FILL and any(0 <= y + dy < 32 and 0 <= x + dx < 64 and src[y + dy][x + dx] == SAVE_FILL
                                              for dy in (-1, 0, 1) for dx in (-1, 0, 1)):
                cv[y][x] = SAVE_OUTLINE
    tiles = b''.join(textgfx.tile4(cv, tx * 8, ty * 8) for ty in range(4) for tx in range(8))
    rom.write(SAVE_TILES, tiles, 'save header')
    for k, r in enumerate(SAVE_ROWS):           # the picture's 8x4 tiles in columns 12-19
        row = [SAVE_PLAIN, SAVE_PLAIN] + [0x60 + 8 * k + j for j in range(8)] + [SAVE_PLAIN, SAVE_PLAIN]
        for j, t in enumerate(row):
            rom.w16(SAVE_MAP + 2 * (r * 32 + SAVE_COL0 + j), t)

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
    for addr, text in TABS:
        grid = unpack_cells(rom.read(addr, 1024), 64, 32, 64, 32)
        for y in range(16, 29):
            for x in range(2, 58):
                if grid[y][x] in (2, 3, 14): grid[y][x] = 1
        txt = fit(font, text, 56, fill=3, outline=14, y0=1)
        for y in range(13):
            for x in range(56):
                if txt[y][x]: grid[16 + y][2 + x] = txt[y][x]
        rom.write(addr, textgfx.sprite_cells(grid, 64, 32), 'tab ' + text)
    save_header(rom)
    yes_no(rom, font)
    help_note(rom)
    print(f"  buttons: {len(BUTTONS) + len(PROMPTS) + len(TABS)} redrawn; save screen header, Yes / No and note; "
          f"continue screen {' / '.join(CONTINUE_TEXT)}")
