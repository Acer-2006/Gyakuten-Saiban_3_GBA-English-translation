"""The verdict from the DS version: Not Guilty / Guilty in its serif letters, as the English GS1 has them.

GBA: script command 0x44 (handler 0x080209dc, argument 0 = not guilty) DMAs two raw 64x64
pictures (無 罪, or 有 罪) to OBJ tiles 0x1a0 and 0x1e0 and their palette (0x08198b70, or
0x08198b50 for guilty) to OBJ palette 5, and switches to mode 9 (0x0800f23c, entry 9 of the mode
table at 0x08161088).  That shows the words as OAM entries 49 and 50, affine with double size,
centred at (47, 47) and (192, 47), and zooms each in from 2.5 times its size (matrices 0 and 1,
the scale in SYS+0xa0), the second 40 frames after the first; then moves them up while zooming
out, hides them, and for not guilty rains confetti (OAM entries 58-88).

DS: the English verdict is letters, raw 4bpp sprites in data.bin (64x64 or 32x64, from 0x23c80:
N o t G u i l t y) with the palettes 0x27540 (white letters, not guilty) and 0x27520 (black,
guilty).  The arm9 lists them for each verdict (0x020aca58 not guilty, 0x020ac9c8 guilty), 24
bytes each: {u32 frame, s16 x, s16 y, s16 x, s16 y, u16 512, u16 256, u32 data.bin offset, u32
size}, x and y the corner of the double-size box.  Each letter zooms in from twice its size about
its centre at its frame (frames 0 and 60: Not, then Guilty; Guilty alone letter by letter at
10-60), the size going from 512 to 256 in ten steps, and as the ninth begins the DS shakes the
screen for 4 frames (strength 1) and plays sound 0x56 (0x0202fd70), once for each letter.  The
letters stay 61 frames after the last has landed, then go at once (they do not rise as the
Japanese words do), and the confetti follows for not guilty.  The verdict starts with a flash
(0x0202f988: the DS's fade function 0x02017a30 with mode 3, a step a frame, 8 a step, every
layer, the script's 12 301 8 1f), white for two frames and half for one as the first letter
begins; there is none as the letters land.

The English build's letters are the English GS1's (v0.7.58, its verdict lettering kit; 0.16.87):
the DS letters at 90% (SCALE), made as GS1's tools/en/make_effects.py makes them, here from the
Trials and Tribulations DS ROM (the same letters and palettes as GS1's DS; every one comes out
pixel for pixel as the kit's).  resample.scale_indexed_box averages each colour channel and the
coverage over each new pixel (Pillow's BOX filter) and keeps the pixels at least half covered in
the nearest of the DS's own six colours, so the outline and fill stay crisp.  A letter whose ink
is at most 30 wide is centred on a 32x64 sprite, N and G (35) on a 64x64 one; the two t of Not
Guilty are one picture and share their tiles.  They are laid out as GS1 lays them: the DS's
centres scaled by SCALE about the screen's middle, the word's centre at y 57 (CENTRE_Y), Not Guilty
230 x 57 (x 5-234, y 28-84), Guilty 143 x 57 (x 50-192).  Until 0.16.86 the build had them at 80%
in 32x64 sprites (Not Guilty 195 px wide), centred at y 47.

src/verdict.c copies the tiles at the end of the command's handler (from tile 0x2c0 down: 0x180
for Not Guilty, 0x1e0 for Guilty; the characters' sprites start at 0x2c0, and the effects that use
the tiles below load their own when they start) and takes the verdict mode's place in the mode
table: until the letters go it runs the DS's timeline itself (each letter zooming in from its frame
as an affine sprite with double size, a shake and the slam 0x56 as each lands), then hands over
to the original's state 4 with its timer run out, which goes on to the confetti or back to the
court.  A landed letter is a plain sprite: nine affine ones with double size would take more of a
line's sprite time (1210 cycles; 10 + 2 x the box's width each) than there is.

The sprite time is close as Not Guilty's Guilty zooms in: its six letters (G 266 cycles, five
138) and Not landed (N 64, o 32, t 32) take 1084 on a line, and the judge's sprites below y 88
another 160 on line 88, the last row of the landed letters, 34 over (mGBA draws the sprite that
runs over and stops after it; the GBA cuts it short).  So a landed letter that is up while a group
of several letters zooms in and whose ink ends within its 56th row (Not's o and t) is drawn as
32x32, 32x16 and 32x8 from the same tiles (EXTRA: OAM entries 45-48 for the other two pieces),
which ends at y 80; the busiest line then takes 1196 (measured in the courtroom, all five).

The flash (0.16.86): start_flash, the build's last step but one, puts a routine in front of
verdict_start (the trampoline's call is pointed at it) that starts the same fade as the DS through
the game's own function, 0x08000b40, which command 0x12 uses: BLDY 24, 16, 8, 0.

Savestates: apply() keeps the room the 0.16.86 letters and code had (zeros now), so nothing
stored after it moves; the letters, their tables and the code are stored by letters(), the build's
last step, which points the mode table and the flash routine at the new code.
"""
import os, struct, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
import dspic, resample
from rom import compile_c
from .text import call_hook

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HANDLER_END = 0x08020a82                  # movs r0, #0x80; lsls r0, r0, #2 (entry 50 hidden)
MODE_TABLE, VERDICT_MODE = 0x08161088, 9
VERDICT_STEP = 0x0800f23c
GBA_PALS = (0x08198b70, 0x08198b50)       # not guilty, guilty
DS_LISTS = (0x020aca58, 0x020ac9c8)       # arm9
DS_COUNT = (9, 6)
DS_PALS = (0x27540, 0x27520)              # data.bin
SCALE = 0.9                               # as the English GS1: Not Guilty 230 of the 240 px
CENTRE_Y = 57                             # the word's centre, as GS1 has it
TILE_LOW, TILE_END = 0x180, 0x2c0         # the characters' sprites start at 0x2c0
OBJ_VRAM = 0x06010000
PALETTE = 5
EXTRA = (45, 46, 47, 48)                  # OAM entries for split letters' other pieces
BSS = 0x02029800                          # after src/menu.c's
L_MATRIX, L_SQUARE, L_SPLIT = 1, 2, 4     # src/verdict.c's letter flags
SPLIT_ROWS = 56                           # 32x32 + 32x16 + 32x8
# the room the 0.16.86 letters (80%, one 32x64 sprite each) and code had, kept (savestates)
OLD_CODE = 482

def ds_letters(ctx, kind):
    """-> [(frame, DS box x, DS box y, picture rows, width)] from the DS's list"""
    out = []
    for i in range(DS_COUNT[kind]):
        fr, x, y, x2, y2, s0, s1, off, size = struct.unpack_from('<IhhhhHHII', ctx.arm9, DS_LISTS[kind] - 0x02000000 + 24 * i)
        if (x, y) != (x2, y2) or y != 32 or (s0, s1) != (512, 256) or size not in (0x400, 0x800):
            raise SystemExit(f'verdict: unexpected DS letter list at {DS_LISTS[kind]:#x}')
        w = 64 if size == 0x800 else 32
        out.append((fr, x, y, dspic.tiles_to_rows(ctx.data[off:off + size], w, 64), w))
    return out

def letter_sprite(px, colors):
    """A DS letter -> (rows, width): at SCALE, centred on a 32x64 sprite (ink at most 30 wide) or
    a 64x64 one (the zoom pivots on the sprite's centre), as GS1's make_effects.py does."""
    s = resample.scale_indexed_box(px, colors, SCALE, list(range(1, 7)))
    xs = [x for row in s for x, v in enumerate(row) if v]
    w = 32 if max(xs) - min(xs) + 1 <= 32 - 2 else 64
    oy, ox = int(round(32 - len(s) / 2)), int(round(w / 2 - len(s[0]) / 2))
    out = [[0] * w for _ in range(64)]
    n = 0
    for y, row in enumerate(s):
        for x, v in enumerate(row):
            if v and 0 <= y + oy < 64 and 0 <= x + ox < w: out[y + oy][x + ox] = v; n += 1
    if n != len(xs): raise SystemExit('verdict: a letter does not fit its sprite')
    return out, w

def layout(ctx, kind):
    """-> (tile data from the lowest tile to TILE_END, its first tile, letter records)"""
    pal = struct.unpack_from('<16H', ctx.data, DS_PALS[1])                  # GS1 maps through Guilty's
    colors = [((c & 31) << 3, (c >> 5 & 31) << 3, (c >> 10 & 31) << 3) for c in pal]
    letters = ds_letters(ctx, kind)
    frames = sorted({fr for fr, *_ in letters})
    group = {fr: sum(1 for l in letters if l[0] == fr) for fr in frames}
    pics, recs, extra = {}, [], list(EXTRA)
    tile = TILE_END
    for fr, dx, dy, px, dw in letters:
        rows, w = letter_sprite(px, colors)
        key = bytes(v for r in rows for v in r)
        if key not in pics:                                                 # the two t share
            tile -= w * 64 // 64
            pics[key] = (tile, dspic.rows_to_tiles(rows, 0, 0, w, 64))
        t0 = pics[key][0]
        # the DS's centre of the double-size box, scaled about the screen's middle; the box's corner
        cx = (dx + dw - 128) * SCALE + 120
        cy = (dy + 64 - 96) * SCALE + CENTRE_Y
        bx, by = int(round(cx - w)), int(round(cy - 64))
        flags = (frames.index(fr) & 1) * L_MATRIX | (w == 64) * L_SQUARE
        ink = [y for y, r in enumerate(rows) if any(r)]
        crowded = any(n > 1 for f, n in group.items() if f > fr)          # up while a group zooms
        e = 0
        if w == 32 and crowded and ink[-1] < SPLIT_ROWS:
            if len(extra) < 2: raise SystemExit('verdict: no OAM entries left for a split letter')
            flags |= L_SPLIT; e = extra.pop(0); extra.pop(0)
        recs.append(struct.pack('<BBhHBB', fr, flags, bx, t0 | PALETTE << 12, by & 0xff, e))
    if tile < TILE_LOW: raise SystemExit('verdict: the letters need more sprite tiles')
    data = bytearray((TILE_END - tile) * 32)
    for t0, tl in pics.values(): data[(t0 - tile) * 32:(t0 - tile) * 32 + len(tl)] = tl
    return bytes(data), tile, b''.join(recs)

def apply(rom, ctx):
    for kind in (0, 1):
        pal = list(struct.unpack_from('<16H', ctx.data, DS_PALS[kind]))
        old = rom.read(GBA_PALS[kind], 32)
        rom.write(GBA_PALS[kind], old[:2] + struct.pack('<15H', *pal[1:]), f'verdict palette {kind}')
    # the room of the 0.16.86 letters, layouts and table, then of its code (see the docstring)
    for kind in (0, 1):
        rom.store(bytes(DS_COUNT[kind] * 0x400), 'ext', 4, f'verdict room (letters {kind} until 0.16.86)')
        rom.store(bytes(DS_COUNT[kind] * 8), 'ext', 4, f'verdict room (layout {kind} until 0.16.86)')
    rom.store(bytes(2 * 12), 'ext', 4, 'verdict room (table until 0.16.86)')
    room = rom.store(bytes(OLD_CODE), 'font', 4, 'verdict room (code until 0.16.86)')
    # the tiles, at the end of the command's handler (pointed at the code by letters())
    displaced = 'movs r0, #0x80\n lsls r0, r0, #2'
    if rom.read(HANDLER_END, 4) != rom.asm_thumb(HANDLER_END, displaced):
        raise SystemExit('verdict: unexpected code in the verdict command')
    call_hook(rom, HANDLER_END, room | 1, displaced, 'verdict start')
    entry = MODE_TABLE + 4 * VERDICT_MODE
    if rom.u32(entry) != VERDICT_STEP | 1: raise SystemExit('verdict: unexpected mode table')
    ctx.verdict_room = room

FADE_START = 0x08000b40                   # starts a brightness fade: (mode, frames a step, step, layers)
FLASH = (3, 1, 8, 0x1f)                   # brighter, back down to 0: the script's 12 301 8 1f

def thumb_bl_target(rom, at):
    h1, h2 = struct.unpack('<HH', rom.read(at, 4))
    if h1 & 0xf800 != 0xf000 or h2 & 0xf800 != 0xf800: return None
    off = (h1 & 0x7ff) << 12 | (h2 & 0x7ff) << 1
    if off & 0x400000: off -= 0x800000
    return at + 4 + off

def start_flash(rom, ctx):
    """The build's last step but one: the DS's flash as the verdict starts (see the docstring).
    The routine calls verdict_start, which letters() puts in."""
    tramp = thumb_bl_target(rom, HANDLER_END)
    call = tramp + 6 if tramp else None               # push {r0-r3, lr}; mov r0, r12; push {r0}; bl
    if not call or thumb_bl_target(rom, call) != ctx.verdict_room:
        raise SystemExit('verdict: the start hook is not where it was')
    m, per, step, layers = FLASH
    stub = rom.thumb_code(f'''
        push {{lr}}
        movs r0, #{m}
        movs r1, #{per}
        movs r2, #{step}
        movs r3, #{layers:#x}
        bl #{FADE_START:#x}
        bl #{ctx.verdict_room:#x}
        pop {{pc}}
    ''', note='verdict flash')
    rom.thumb(call, f'bl #{stub & ~1:#x}', 'verdict start: the flash first')
    ctx.verdict_flash = stub & ~1
    print("  verdict: a flash as it starts, as on the DS")

def letters(rom, ctx):
    """The build's last step: the letters, their layout and the code (see the docstring)."""
    tables = []
    for kind in (0, 1):
        tiles, first, recs = layout(ctx, kind)
        t = rom.store(tiles, 'ext', 4, f'verdict letters {kind}')
        l = rom.store(recs, 'ext', 4, f'verdict layout {kind}')
        tables.append(struct.pack('<HHIII', len(recs) // 8, len(tiles) // 4, t, l, OBJ_VRAM + first * 32))
    table = rom.store(b''.join(tables), 'ext', 4, 'verdict table')
    text_addr = 0x08000000 + ((rom.regions['font'].cur + 3) & ~3)
    binary, syms, bss = compile_c([os.path.join(ROOT, 'src/verdict.c')], text_addr, BSS,
                                  os.path.join(ROOT, 'build/verdict'), ld_defsyms={'verdicts': table})
    assert rom.store(binary, 'font', 4, 'verdict code') == text_addr
    assert bss <= 0x100, bss
    call = ctx.verdict_flash + 14                      # the flash routine's call of verdict_start
    if thumb_bl_target(rom, call) != ctx.verdict_room: raise SystemExit('verdict: the flash routine is not as made')
    rom.thumb(call, f'bl #{syms["verdict_start"] & ~1:#x}', 'verdict flash: then the letters')
    rom.w32(MODE_TABLE + 4 * VERDICT_MODE, syms['verdict_mode'] | 1)
    print(f"  verdict: Not Guilty / Guilty in the English GS1's letters (the DS's at {SCALE:.0%}), "
          f"a slam for each as on the DS")
