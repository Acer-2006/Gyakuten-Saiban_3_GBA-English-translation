"""Buttons drawn as raw sprites (the sheet around 0x0818a720), redrawn in English with the DS font,
and the save and continue screens' header, buttons and note, taken from the DS's pictures.

Each button graphic is 64x16 or 32x16 pixels stored as 32x16 one-dimensional sprite cells (4x2
tiles, row-major, 256 bytes); see hacking/docs/graphics.md.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
import struct
import textgfx, dsimgtext, dspic
from rom import compile_c
from .text import call_hook
from . import topics

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

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

# save screen header: the GBA's 記録 is two 32x32 glyphs in the UI BG tile sheet (0x08180820),
# tiles 0x60-0x7f, placed by the box's BG2 map (0x0803bf44, 32 wide; the box is columns 4-27 of
# rows 2-11) at columns 10-13 and 18-21 of rows 3-6 with BG palette 0.  The DS has SAVE, and LOAD
# on the continue screen: 103x30 lettering in its save box textures (data.bin 0x7cbebc and
# 0x7cfef0), olive green with a white outline.  The build cuts the lettering out as 14x4 tiles,
# which src/menu.c puts in BG tiles 0x1c4.. when the screen opens, and maps them at columns 9-22
# with BG palette 1.  Palette 1 on these screens is entries 16-31 of the palette of the courtroom
# picture behind them (0x08254afc, also the episode select's), whose pixels use none of those
# entries: the DS colours palette 1 lacks are added to its empty ones.
HDR_DS = {'save': 0x7cbebc, 'load': 0x7cfef0}
SAVE_MAP = 0x0803bf44
HDR_ROWS, HDR_COL0, HDR_COLS = (3, 4, 5, 6), 9, 14
HDR_TILE, HDR_PAL = 0x1c4, 1
BOX_INSIDE, BOX_FILL = range(5, 27), 0x40
HDR_AREA = (36, 9, 220, 60)          # inside the DS box texture, clear of its frame: x0, y0, x1, y1
MENU_BG = 0x08254afc
MENU_BSS = 0x02029000                # after src/script.c's state
HDR_HOOKS = [(0x0800b636, 'hdr_game', 'str r1, [r0, #4]\n str r3, [r0, #8]'),      # saving (START, end of a part)
             (0x0800ae80, 'hdr_erase', 'str r1, [r0, #8]\n ldr r1, [r0, #8]'),     # erasing all data
             (0x0800d750, 'hdr_continue', 'str r0, [r1, #4]\n str r2, [r1, #8]')]  # Continue on the title
LABEL_POS = 0x0800e97c               # the Testimony label's OAM attribute 1 (x) is computed here
HDR_CLOSE = 0x0800bcc4               # the save screen closes, the game state is back (patches/text.py)

# save screen はい / いいえ (0x0819a070, two 64x32 sprites) and the continue screen's two buttons
# (0x08199070, two 128x32 boxes of two 64x32 sprites each, at (56, 98) and (56, 130):
# 中断したところから, from where the game was suspended, and この章のはじめから, from the start of
# this part), all 1D sprites in the Talk topics' box style (OBJ palette 9 for the highlighted
# one, 10 for the other).  The DS has its English buttons in the same style as textures in
# data.bin: Yes and No (128x32) and From save point. / From chapter start. (256x32); their
# lettering goes into the GBA boxes the way patches/topics.py copies the topics' (narrowed to the
# box where it is wider).
YESNO, CONTINUE = 0x0819a070, 0x08199070
DS_BUTTONS = [(YESNO, 64, 0x804e48, 'Yes'), (YESNO + 1024, 64, 0x8056dc, 'No'),
              (CONTINUE, 128, 0x802d20, 'From save point.'),
              (CONTINUE + 2048, 128, 0x803db4, 'From chapter start.')]
BUTTON_FILL = 12
DS_FRAME = 9                         # the DS box's outline
# the note under them (※ゲーム中にSTARTボタンを押せば、いつでも記録することができます。): 0x0818e720,
# 80 tiles shown as a 160x32 line at (40, 128): two 64x32 sprites, then a 32x32 column of four
# 32x8 strips whose tiles are stored in the order of rows 0, 2, 1, 3; OBJ palette 13 (0x08198cd0),
# white (1) lettering, START in light blue (6), dark outline (5).  The DS has its note, Press START
# at any time during / the game to save your data., as a 256x32 texture (data.bin 0x7e9b30): white
# (2) and light blue (3) letters with a dark (1) outline one pixel around them, the first line 184
# pixels wide.  The build takes the DS letters as they are and sets them closer: one outline column
# between letters (the DS has one or two) and three or four columns between words (the DS has four
# to six), which makes the first line's letters 160 pixels wide; the outline is drawn again around
# them, as on the DS (only the first line's two outermost columns of it fall outside the note).
HELP = 0x0818e720
HELP_PAL = 0x08198cd0
HELP_DS = 0x7e9b30
HELP_DS_PAL = (0x0842, 0x7fff, 0x7fb5)       # DS indices 1 (outline), 2 (white), 3 (light blue)
HELP_COLOURS = {2: 1, 3: 6}                  # DS letters -> GBA palette 13
HELP_OUTLINE = 5
HELP_W, HELP_H = 160, 32
WORD_GAP = (3, 4)                            # the narrowest and widest space between words

def ds_buttons(rom, data):
    levels = topics.ramp_gba(rom)
    for addr, width, off, name in DS_BUTTONS:
        n = width // 64
        grid = [sum((unpack_cells(rom.read(addr + 1024 * i, 1024), 64, 32, 64, 32)[y] for i in range(n)), [])
                for y in range(32)]
        if grid[6][2] != BUTTON_FILL or grid[24][width - 4] != BUTTON_FILL:
            raise SystemExit(f'ui: unexpected box button at {addr:#x}')
        px, w, h, pal = dsimgtext.texture(data, off)
        if h != 32 or w not in (128, 256):
            raise SystemExit(f'ui: unexpected DS button at data.bin {off:#x} ({name})')
        # only the inside of the DS box: its frame has colours of the lettering's ramp
        frame = [(x, y) for y in range(h) for x in range(w) if px[y][x] == DS_FRAME]
        x0, x1 = min(x for x, y in frame) + 2, max(x for x, y in frame) - 2
        y0, y1 = min(y for x, y in frame) + 2, max(y for x, y in frame) - 2
        px = [[v if x0 <= x <= x1 and y0 <= y <= y1 else topics.DS_FILL for x, v in enumerate(r)]
              for y, r in enumerate(px)]
        g = topics.picture(grid, px, topics.ink_ds(pal), levels, width)
        rom.write(addr, b''.join(textgfx.sprite_cells([r[64 * i:64 * i + 64] for r in g], 64, 32)
                                 for i in range(n)), 'button ' + name)

def note_letters(px, w, h):
    """The DS note's letters, line by line: 8-connected groups of lettering pixels, kept together
    where their columns overlap (an i and its dot, a kerned pair).  -> per line, left to right,
    [(x0, x1, [(x, y, index)])]."""
    seen, groups = set(), []
    for y in range(h):
        for x in range(w):
            if px[y][x] in HELP_COLOURS and (x, y) not in seen:
                stack, pts = [(x, y)], []
                seen.add((x, y))
                while stack:
                    cx, cy = stack.pop()
                    pts.append((cx, cy, px[cy][cx]))
                    for ny in (cy - 1, cy, cy + 1):
                        for nx in (cx - 1, cx, cx + 1):
                            if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in seen and px[ny][nx] in HELP_COLOURS:
                                seen.add((nx, ny)); stack.append((nx, ny))
                groups.append(pts)
    lines = [[], []]
    for pts in groups:
        lines[min(y for x, y, v in pts) >= h // 2].append(pts)
    out = []
    for line in lines:
        letters = []
        for pts in sorted(line, key=lambda p: min(x for x, y, v in p)):
            x0, x1 = min(x for x, y, v in pts), max(x for x, y, v in pts)
            if letters and x0 <= letters[-1][1]:
                a0, a1, apts = letters[-1]; letters[-1] = (a0, max(a1, x1), apts + pts)
            else:
                letters.append((x0, x1, pts))
        out.append(letters)
    return out

def help_note(rom, data):
    px, w, h, pal = dsimgtext.texture(data, HELP_DS)
    if (w, h) != (256, HELP_H) or struct.unpack_from('<3H', pal, 2) != HELP_DS_PAL:
        raise SystemExit(f'ui: unexpected DS save note at data.bin {HELP_DS:#x}')
    gba = [rom.u16(HELP_PAL + 2 * i) for i in range(16)]
    if [gba[HELP_COLOURS[i]] for i in (2, 3)] != list(HELP_DS_PAL[1:]):
        raise SystemExit('ui: the save note palette lacks the DS colours')
    cv = [[0] * HELP_W for _ in range(HELP_H)]
    for letters in note_letters(px, w, h):
        gaps = [b[0] - a[1] - 1 for a, b in zip(letters, letters[1:])]
        words = sum(g >= 4 for g in gaps)
        body = sum(x1 - x0 + 1 for x0, x1, _ in letters) + sum(min(g, 1) for g in gaps if g < 4)
        word = min(WORD_GAP[1], (HELP_W - body) // max(words, 1))
        if word < WORD_GAP[0]: raise SystemExit('ui: the DS save note does not fit')
        x = (HELP_W - body - word * words) // 2
        for (x0, x1, pts), g in zip(letters, gaps + [0]):
            for lx, y, v in pts:
                cv[y][x + lx - x0] = HELP_COLOURS[v]
            x += x1 - x0 + 1 + (word if g >= 4 else min(g, 1))
    src = [r[:] for r in cv]
    for y in range(HELP_H):
        for x in range(HELP_W):
            if not src[y][x] and any(src[yy][xx] for yy in range(max(y - 1, 0), min(y + 2, HELP_H))
                                     for xx in range(max(x - 1, 0), min(x + 2, HELP_W))):
                cv[y][x] = HELP_OUTLINE
    out = textgfx.sprite_cells([r[0:64] for r in cv], 64, 32) + textgfx.sprite_cells([r[64:128] for r in cv], 64, 32)
    for row in (0, 2, 1, 3):                     # the 32x8 strips
        out += b''.join(textgfx.tile4([r[128:160] for r in cv], tx * 8, row * 8) for tx in range(4))
    if len(out) != 2560: raise SystemExit('ui: help note size')
    rom.write(HELP, out, 'save note')

def menu_palette(rom):
    """Address and values of the courtroom picture's palette entries 16-31 (BG palette 1)."""
    p = MENU_BG + rom.u32(MENU_BG) + 32
    return p, [rom.u16(p + 2 * i) for i in range(16)]

def header_pictures(data, pal1):
    """The DS lettering as 112x32 pictures of palette 1 indices -> ({name: rows}, {index: colour})."""
    add, pics = {}, {}
    for name, off in HDR_DS.items():
        px, w, h, palb = dsimgtext.texture(data, off)
        dspal = struct.unpack_from('<16H', palb)
        x0, y0, x1, y1 = HDR_AREA
        fill = px[y1][(x0 + x1) // 2]
        pts = [(x, y) for y in range(y0, y1) for x in range(x0, x1) if px[y][x] != fill]
        if not pts: raise SystemExit(f'ui: no lettering in the DS {name} box')
        bx0, bx1 = min(x for x, y in pts), max(x for x, y in pts) + 1
        by0, by1 = min(y for x, y in pts), max(y for x, y in pts) + 1
        W, H = 8 * HDR_COLS, 8 * len(HDR_ROWS)
        if bx1 - bx0 > W or by1 - by0 > H: raise SystemExit(f'ui: the DS {name} lettering is too big')
        cx, cy = bx0 - (W - (bx1 - bx0)) // 2, by0      # centred, at the top (the text goes below)
        if cx < x0 or cy < y0 or cx + W > x1 or cy + H > y1 + 8:
            raise SystemExit(f'ui: the DS {name} lettering is not where expected')
        pic = []
        for y in range(cy, cy + H):
            row = []
            for x in range(cx, cx + W):
                c = dspal[px[y][x]]
                if c and c in pal1[1:]: i = pal1.index(c, 1)
                elif c in add.values(): i = next(k for k, v in add.items() if v == c)
                else:
                    free = [k for k in range(1, 16) if pal1[k] == 0 and k not in add]
                    if not free: raise SystemExit('ui: no room in palette 1 for the header')
                    i = free[0]; add[i] = c
                row.append(i)
            pic.append(row)
        pics[name] = pic
    return pics, add

def save_header(rom, ctx):
    old = [[rom.u16(SAVE_MAP + 2 * (r * 32 + c)) for c in BOX_INSIDE] for r in HDR_ROWS]
    want = [[0x60 + 4 * k + c - 10 if 10 <= c < 14 else 0x70 + 4 * k + c - 18 if 18 <= c < 22 else BOX_FILL
             for c in BOX_INSIDE] for k in range(4)]
    if old != want: raise SystemExit('ui: unexpected save screen map')
    paddr, pal1 = menu_palette(rom)
    pics, add = header_pictures(ctx.data, pal1)
    # the courtroom picture must not use the entries the header takes
    import chunkimg
    _, pixels, _ = chunkimg.load(rom.d, MENU_BG - 0x08000000, 512)
    if set(pixels) & {16 + i for i in add}: raise SystemExit('ui: the menu background uses palette 1')
    for i, c in add.items(): rom.w16(paddr + 2 * i, c)
    tiles = {name: b''.join(dspic.rows_to_tiles(pic, 8 * c, 8 * r, 8, 8)
                            for r in range(len(HDR_ROWS)) for c in range(HDR_COLS))
             for name, pic in pics.items()}
    addr = {name: rom.store(t, 'ext', 4, f'{name} header') for name, t in tiles.items()}
    for k, r in enumerate(HDR_ROWS):
        for c in BOX_INSIDE:
            j = c - HDR_COL0
            rom.w16(SAVE_MAP + 2 * (r * 32 + c), (HDR_TILE + k * HDR_COLS + j) | HDR_PAL << 12
                    if 0 <= j < HDR_COLS else BOX_FILL)
    # the code that puts the tiles in VRAM (src/menu.c)
    text_addr = 0x08000000 + ((rom.regions['font'].cur + 3) & ~3)
    binary, syms, bss = compile_c([os.path.join(ROOT, 'src/menu.c')], text_addr, MENU_BSS,
                                  os.path.join(ROOT, 'build/menu'),
                                  ld_defsyms={'hdr_save': addr['save'], 'hdr_load': addr['load']})
    assert rom.store(binary, 'font', 4, 'menu code') == text_addr
    for site, fn, displaced in HDR_HOOKS:
        if rom.read(site, 4) != rom.asm_thumb(site, displaced): raise SystemExit(f'ui: unexpected code at {site:#x}')
        call_hook(rom, site, syms[fn], displaced, fn)
    # the Testimony label 3 pixels in from the corner (src/menu.c label_pos): the hook replaces
    # the x computation and adds the offset to it
    if rom.read(LABEL_POS, 4) != rom.asm_thumb(LABEL_POS, 'movs r0, #0xc0\n lsls r0, r0, #8'):
        raise SystemExit('ui: unexpected code placing the Testimony label')
    call_hook(rom, LABEL_POS, syms['label_pos'], 'movs r0, #0xc0\n lsls r0, r0, #8\n adds r0, #3', 'label_pos')
    old_tramp = rom.restore_tramp
    if rom.read(HDR_CLOSE, 4) != rom.asm_thumb(HDR_CLOSE, f'bl #{old_tramp & ~1:#x}'):
        raise SystemExit('ui: unexpected save screen exit')
    tramp = rom.thumb_code(f'''
        push {{lr}}
        bl #{syms["hdr_close"] & ~1:#x}
        bl #{old_tramp & ~1:#x}
        pop {{pc}}
    ''', note='save screen close trampoline')
    rom.thumb(HDR_CLOSE, f'bl #{tramp & ~1:#x}', 'save screen close hook')

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
    # The detail view (L on a photo) shows the B and L icons and the Back prompt at x 184, 200
    # and 216: 24 pixels of the prompt's 32 are on screen.  The three move left to 181, 197 and
    # 213 (the icon's attr1 literal, the L icon's `subs r1, #0xfc` from that literal, the
    # prompt's attr1 literal, all in the routine at 0x08015170), and the prompts are at most 27
    # pixels wide.
    assert rom.u16(0x080151a8) == 0x40b8 and rom.u16(0x08015182) == 0x39fc and rom.u16(0x080151b8) == 0x80d8
    rom.w16(0x080151a8, 0x40b5); rom.w16(0x08015182, 0x39ff); rom.w16(0x080151b8, 0x80d5)
    for addr, text in PROMPTS:
        sq = 0
        while font.measure(text) - sq * (len(text) - 1) > 27: sq += 1
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
    save_header(rom, ctx)
    ds_buttons(rom, ctx.data)
    help_note(rom, ctx.data)
    print(f"  buttons: {len(BUTTONS) + len(PROMPTS) + len(TABS)} redrawn; from the DS: "
          f"{' / '.join(n.upper() for n in HDR_DS)} headers, {' / '.join(n for a, w, o, n in DS_BUTTONS)}, "
          f"the save note")
