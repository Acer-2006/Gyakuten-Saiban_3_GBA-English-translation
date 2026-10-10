"""The verdict from the DS version: Not Guilty / Guilty in its serif letters.

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
Japanese words do), and the confetti follows for not guilty.

The English build shrinks the letters to 4/5 (area average), each into a 32x64 sprite from OBJ
tile 0x1a0 (nine take the tiles up to the characters' at 0x2c0), laid out as on the DS around the
middle of the screen at the height of the original's words.  src/verdict.c copies the tiles at
the end of the command's handler and takes the verdict mode's place in the mode table: until
the letters go it runs the DS's timeline itself (each letter zooming in from its frame, a shake
and the slam 0x56 as each lands, as the DS's English verdict does, which plays the slam once a
letter), then hands over to the original's state 4 with its timer run out, which goes on to the
confetti or back to the court.
"""
import os, struct, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
import dspic
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
SCALE = 0.8                               # N, G and y fit 32 wide
TILE0, TILE_END = 0x1a0, 0x2c0            # the characters' sprites start at 0x2c0
CX = 120                                  # the middle of the screen
BSS = 0x02029800                          # after src/menu.c's

def ds_letters(ctx, kind):
    """-> [(frame, centre x, picture rows, width)] in the DS layout"""
    out = []
    for i in range(DS_COUNT[kind]):
        fr, x, y, x2, y2, s0, s1, off, size = struct.unpack_from('<IhhhhHHII', ctx.arm9, DS_LISTS[kind] - 0x02000000 + 24 * i)
        if (x, y) != (x2, y2) or y != 32 or (s0, s1) != (512, 256) or size not in (0x400, 0x800):
            raise SystemExit(f'verdict: unexpected DS letter list at {DS_LISTS[kind]:#x}')
        w = 64 if size == 0x800 else 32
        out.append((fr, x + w, dspic.tiles_to_rows(ctx.data[off:off + size], w, 64), w))
    return out

def letter_picture(px, w, pal):
    """A DS letter (w x 64) -> a 32x64 picture at 4/5 size about the same centre."""
    ww, wh = round(32 / SCALE), round(64 / SCALE)
    x0, y0 = w // 2 - ww // 2, 32 - wh // 2
    inside = [[px[y][x] if 0 <= y < 64 and 0 <= x < w else 0 for x in range(x0, x0 + ww)] for y in range(y0, y0 + wh)]
    if sum(v != 0 for r in inside for v in r) != sum(v != 0 for r in px for v in r):
        raise SystemExit('verdict: a DS letter does not fit')
    return dspic.quantize(dspic.shrink(inside, pal, 32, 64), pal, dspic.used_indices(px))

def apply(rom, ctx):
    tables = []
    for kind in (0, 1):
        pal = list(struct.unpack_from('<16H', ctx.data, DS_PALS[kind]))
        letters = ds_letters(ctx, kind)
        if TILE0 + 32 * len(letters) > TILE_END: raise SystemExit('verdict: too many letters')
        ink = []
        for fr, cx, px, w in letters:
            cols = [x for x in range(w) if any(r[x] for r in px)]
            ink += [cx - w // 2 + cols[0], cx - w // 2 + cols[-1] + 1]
        mid = (min(ink) + max(ink)) / 2
        frames = sorted({fr for fr, *_ in letters})
        if frames[-1] > 200: raise SystemExit('verdict: unexpected DS letter frames')
        tiles = bytearray(); recs = bytearray()
        for k, (fr, cx, px, w) in enumerate(letters):
            matrix = frames.index(fr) & 1          # letters that zoom at the same time share one
            gx = CX + round((cx - mid) * SCALE)
            tiles += dspic.rows_to_tiles(letter_picture(px, w, pal), 0, 0, 32, 64)
            recs += struct.pack('<BBhHH', fr, matrix, gx - 32, (TILE0 + 32 * k) | 5 << 12, 0)
        t = rom.store(bytes(tiles), 'ext', 4, f'verdict letters {kind}')
        l = rom.store(bytes(recs), 'ext', 4, f'verdict layout {kind}')
        tables.append(struct.pack('<HHII', len(letters), len(tiles) // 4, t, l))
        old = rom.read(GBA_PALS[kind], 32)
        rom.write(GBA_PALS[kind], old[:2] + struct.pack('<15H', *pal[1:]), f'verdict palette {kind}')
    table = rom.store(b''.join(tables), 'ext', 4, 'verdict table')
    text_addr = 0x08000000 + ((rom.regions['font'].cur + 3) & ~3)
    binary, syms, bss = compile_c([os.path.join(ROOT, 'src/verdict.c')], text_addr, BSS,
                                  os.path.join(ROOT, 'build/verdict'), ld_defsyms={'verdicts': table})
    assert rom.store(binary, 'font', 4, 'verdict code') == text_addr
    assert bss <= 0x100, bss
    # the tiles, at the end of the command's handler
    displaced = 'movs r0, #0x80\n lsls r0, r0, #2'
    if rom.read(HANDLER_END, 4) != rom.asm_thumb(HANDLER_END, displaced):
        raise SystemExit('verdict: unexpected code in the verdict command')
    call_hook(rom, HANDLER_END, syms['verdict_start'], displaced, 'verdict start')
    # the verdict mode (called with SYS in r0), which calls the original for the rest
    entry = MODE_TABLE + 4 * VERDICT_MODE
    if rom.u32(entry) != VERDICT_STEP | 1: raise SystemExit('verdict: unexpected mode table')
    rom.w32(entry, syms['verdict_mode'] | 1)
    print(f"  verdict: Not Guilty / Guilty from the DS letters ({DS_COUNT[0]} and {DS_COUNT[1]}), "
          f"a slam for each as on the DS")
