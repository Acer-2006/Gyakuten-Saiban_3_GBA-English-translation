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
Guilty are one picture and share their tiles.  They are laid out as GS1 lays them, the DS's
centres scaled by SCALE about the screen's middle, but at the DS's height (0.16.88): the DS centres
its letters on its screen's middle (their boxes at y 32-159 of 192, the ink at 64-126), and so does
this, at y 80 (CENTRE_Y; GS1 has them at 57): Not Guilty 230 x 57 (x 5-234, y 51-107), Guilty
143 x 57 (x 50-192), centred at 49.7% of the screen's height as on the DS.  Until 0.16.86 the build
had them at 80% in 32x64 sprites (Not Guilty 195 px wide), centred at y 47.

src/verdict.c copies the tiles at the end of the command's handler (from tile 0x2c0 down: 0x180
for Not Guilty, 0x1e0 for Guilty; the characters' sprites start at 0x2c0, and the effects that use
the tiles below load their own when they start) and takes the verdict mode's place in the mode
table: until the letters go it runs the DS's timeline itself (each letter zooming in from its frame
as an affine sprite with double size, a shake and the slam 0x56 as each lands), then hands over
to the original's state 4 with its timer run out, which goes on to the confetti or back to the
court.  A landed letter is plain: nine affine ones with double size would take more of a line's
sprite time (LINE_TIME, 1210 cycles; a plain sprite takes its width, an affine one 10 + 2 x its
box's width) than there is.

The sprite time is close as Not Guilty's Guilty zooms in: its six boxes (G 266 cycles, five 138)
cover lines 16-143, and with the judge behind (up to 160 on lines 85-98, BEHIND) that leaves 94 on
those lines for Not, landed at 48-111, whose sprites are 64 + 32 + 32 wide.  So each landed letter
is drawn as a list of pieces, which layout() works out by playing the verdict frame by frame as
src/verdict.c draws it (_over): every letter whole, then, wherever a line would run over, one of
the landed letters' tile rows on that line narrowed, the biggest saving first: to its inked tiles
from its own (32x8, 16x8, 8x8), or, failing that, to its ink cut out afresh (as narrow as whole
tiles allow; rows alike as one piece).  For Not Guilty that leaves o whole; N as 64x32 and its
inked tiles below (its empty last row left out); and t as 32x32, 16x8 and its stem in rows 40-55
as one 16x16 cut from x 11 (in its own tiles it straddles three).  The cut tiles go into tiles of
a letter in pieces that its pieces leave unused (N's 0x2b6-0x2b9), which its zoom shows, so they
are copied as Guilty begins (the late tiles; N has landed by then) and t is whole until then.  The
busiest line then takes 1204 and the judge is drawn whole (measured in the courtroom, all five);
Guilty's letters zoom in one at a time (at most 490).  The pieces take OAM entries 42-48 (from
EXTRA_TOP down), which nothing else uses during a verdict; the letters, Not's on top as before,
are pixel for pixel GS1's on every frame.

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
CENTRE_Y = 80                             # the screen's middle, where the DS centres its letters
TILE_LOW, TILE_END = 0x180, 0x2c0         # the characters' sprites start at 0x2c0
OBJ_VRAM = 0x06010000
PALETTE = 5
BSS = 0x02029800                          # after src/menu.c's
L_MATRIX, L_SQUARE = 1, 2                 # src/verdict.c's letter flags
EXTRA_TOP, EXTRA_LOW = 48, 34             # OAM entries for pieces, from 48 down (src/verdict.c's EXTRA)
ZOOM = 10                                 # src/verdict.c's ZOOM: a letter has landed ZOOM frames on
LINE_TIME = 1210                          # sprite cycles a line (DISPCNT bit 5 clear)
# the judge's sprites (OAM 114-127) behind the verdict: the most cycles they take on a line in the
# game's verdicts (measured in mGBA on every frame the letters are up; screen lines first-last)
BEHIND = ((13, 36, 32), (37, 38, 48), (39, 48, 80), (49, 60, 48), (61, 68, 80), (69, 84, 112),
          (85, 98, 160), (99, 122, 128))
# sprite shapes: (width, height) -> attr0's shape | attr1's size << 2
SHAPES = {(8, 8): 0, (16, 16): 4, (32, 32): 8, (64, 64): 12, (16, 8): 1, (32, 8): 5, (32, 16): 9,
          (64, 32): 13, (8, 16): 2, (8, 32): 6, (16, 32): 10, (32, 64): 14}
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

def _bands(rows, w):
    """A letter's eight tile rows: [(the tile columns with ink, (first, last) inked x or None)]"""
    out = []
    for b in range(8):
        xs = {x for row in rows[8 * b:8 * b + 8] for x, v in enumerate(row) if v}
        out.append((sorted({x // 8 for x in xs}), (min(xs), max(xs)) if xs else None))
    return out

def _band_cost(L, b, mode):
    """Cycles a line the letter's tile row b takes landed: whole ('full'), its inked tiles from its
    own ('tiles'), or its ink cut out afresh ('cut', as narrow as whole tiles allow)"""
    cols, span = L['bands'][b]
    if mode == 'full': return L['w']
    if mode == 'tiles': return 8 * len(cols)
    return 0 if not span else -(-(span[1] - span[0] + 1) // 8) * 8

def _row_pieces(L, b, cols):
    """Tile row b's inked tiles from the letter's own: runs of 32x8, 16x8, 8x8"""
    out, i = [], 0
    while i < len(cols):
        n = 1
        while i + n < len(cols) and cols[i + n] == cols[i] + n and n < 4: n += 1
        if n == 3: n = 2
        out.append((8 * n, 8, 8 * cols[i], 8 * b, ('own', b * L['w'] // 8 + cols[i]), 0))
        i += n
    return out

def _pieces(L, plan):
    """A letter's plan (a mode for each tile row) -> its landed pieces [(w, h, dx, dy, tiles,
    when)]: tiles ('own', the first of its tiles) or ('cut', x, y of the letter's picture); when 0
    always, 1 until the late tiles are in, 2 after.  A letter with cut rows is whole until then."""
    w, out, b = L['w'], [], 0
    while b < 8:
        mode = plan[b]
        n = 1
        while b + n < 8 and plan[b + n] == mode: n += 1
        if mode == 'full':                        # whole rows: as tall as the sprite shapes allow
            k = b
            while k < b + n:
                h = next(h for h in (8, 4, 2, 1) if k + h <= b + n and (w, 8 * h) in SHAPES or h == 1)
                if (w, 8 * h) not in SHAPES:    # a 64-wide row alone: its inked tiles
                    out += _row_pieces(L, k, L['bands'][k][0]); k += 1; continue
                if any(L['bands'][j][1] for j in range(k, k + h)):
                    out.append((w, 8 * h, 0, 8 * k, ('own', k * w // 8), 0))
                k += h
        elif mode == 'tiles':
            for k in range(b, b + n): out += _row_pieces(L, k, L['bands'][k][0])
        else:                                     # cut: the ink cut out afresh, as one piece for
            k = b                                 # rows alike
            while k < b + n:
                if not L['bands'][k][1]: k += 1; continue
                for h in (4, 2, 1):
                    js = range(k, k + h)
                    if k + h > b + n or not all(L['bands'][j][1] for j in js): continue
                    x0 = min(L['bands'][j][1][0] for j in js)
                    cw = -(-(max(L['bands'][j][1][1] for j in js) - x0 + 1) // 8) * 8
                    if h == 1 or all(cw == _band_cost(L, j, 'cut') for j in js): break
                c = 0
                while c < cw:
                    pw = 32 if cw - c >= 32 else 16 if cw - c >= 16 else 8
                    out.append((pw, 8 * h, x0 + c, 8 * k, ('cut', x0 + c, 8 * k), 0))
                    c += pw
                k += h
        b += n
    if 'cut' in plan: return [(w, 64, 0, 0, ('own', 0), 1)] + [p[:5] + (2,) for p in out]
    return out

def _entries(ps):
    """OAM entries the pieces take at once"""
    return max(sum(1 for p in ps if p[5] != 2), sum(1 for p in ps if p[5] != 1))

def _over(letters, plans, late):
    """The first (frame, line) where the sprites would take more than a line's time, or None:
    the letters as src/verdict.c draws them, frame by frame, with the judge behind (BEHIND)."""
    behind = [0] * 160
    for y0, y1, c in BEHIND:
        for y in range(y0, y1 + 1): behind[y] = c
    pieces = [_pieces(L, p) for L, p in zip(letters, plans)]
    for t in range(max(L['frame'] for L in letters) + ZOOM + 1):
        cost = behind[:]
        for L, ps in zip(letters, pieces):
            d = t - L['frame']
            if d < 0: continue
            if d < ZOOM:
                spans = [(L['by'], 128, 10 + 4 * L['w'])]
            else:
                spans = [(L['ly'] + dy, h, pw) for pw, h, dx, dy, src, when in ps
                         if not when or (when == 2) == (late is not None and t >= late)]
            for y0, h, c in spans:
                for y in range(max(0, y0), min(160, y0 + h)): cost[y] += c
        for y in range(160):
            if cost[y] > LINE_TIME: return t, y
    return None

def layout(ctx, kind):
    """-> (tile data from the lowest tile to TILE_END, its first tile, letter records, piece
    records, (frame, tile data, first tile) of the late tiles or None, OAM entries for pieces)"""
    pal = struct.unpack_from('<16H', ctx.data, DS_PALS[1])                  # GS1 maps through Guilty's
    colors = [((c & 31) << 3, (c >> 5 & 31) << 3, (c >> 10 & 31) << 3) for c in pal]
    letters, pics = [], {}
    tile = TILE_END
    for fr, dx, dy, px, dw in ds_letters(ctx, kind):
        rows, w = letter_sprite(px, colors)
        key = bytes(v for r in rows for v in r)
        if key not in pics:                                                 # the two t share
            tile -= w * 64 // 64
            pics[key] = [tile, dspic.rows_to_tiles(rows, 0, 0, w, 64), 0]
        pics[key][2] += 1
        # the DS's centre of the double-size box, scaled about the screen's middle; the box's corner
        cx = (dx + dw - 128) * SCALE + 120
        cy = (dy + 64 - 96) * SCALE + CENTRE_Y
        bx, by = int(round(cx - w)), int(round(cy - 64))
        letters.append(dict(frame=fr, w=w, rows=rows, bx=bx, by=by, lx=bx + w // 2, ly=by + 32,
                            t0=pics[key][0], key=key, bands=_bands(rows, w)))
    if tile < TILE_LOW: raise SystemExit('verdict: the letters need more sprite tiles')
    frames = sorted({L['frame'] for L in letters})
    # the landed letters' pieces: each letter whole, but for the tile rows of the line that would
    # run over, narrowed (its inked tiles; or the ink cut out afresh) until every line fits
    plans, late = [['full'] * 8 for _ in letters], None
    while True:
        over = _over(letters, plans, late)
        if not over: break
        t, y = over
        moves = []
        for i, L in enumerate(letters):
            b = (y - L['ly']) // 8
            if t - L['frame'] < ZOOM or not 0 <= b < 8: continue
            m = plans[i][b]
            for nm in ('tiles', 'cut'):
                save = _band_cost(L, b, m) - _band_cost(L, b, nm)
                if nm == m or m == 'cut' or save <= 0: continue
                more = _entries(_pieces(L, plans[i][:b] + [nm] + plans[i][b + 1:])) - _entries(_pieces(L, plans[i]))
                moves.append((nm == 'cut', -save, more, i, b, nm))
        if not moves: raise SystemExit(f'verdict: line {y} takes more sprite time than there is (frame {t})')
        *_, i, b, nm = min(moves)
        plans[i][b] = nm
        if nm == 'cut' and (late is None or t < late): late = t
    pieces = [_pieces(L, p) for L, p in zip(letters, plans)]
    # the cut tiles: into tiles of a letter drawn in pieces that its pieces leave unused, copied
    # once it has landed (its zoom shows all its tiles) and as the line needs them (late)
    cut = [(i, k) for i, ps in enumerate(pieces) for k, p in enumerate(ps) if p[4][0] == 'cut']
    late_tiles = None
    if cut:
        need = sum(pieces[i][k][0] * pieces[i][k][1] // 64 for i, k in cut)
        shared = {key for key, v in pics.items() if v[2] > 1}
        for h, H in enumerate(letters):
            if H['key'] in shared or H['frame'] + ZOOM >= late: continue
            used = set()
            for pw, ph, dx, dy, src, when in pieces[h]:
                if src[0] == 'own':
                    used |= {src[1] + r * H['w'] // 8 + c for r in range(ph // 8) for c in range(pw // 8)}
            free = [n for n in range(H['w'] * 8) if n not in used]
            run = next((n for n in free if all(n + j in free for j in range(need))), None)
            if run is not None: break
        else: raise SystemExit('verdict: no room for the cut tiles')
        data, at = bytearray(), H['t0'] + run
        for i, k in cut:
            pw, ph, dx, dy, (_, x0, y0), when = pieces[i][k]
            rows = letters[i]['rows']
            sub = [[rows[y][x] if 0 <= x < letters[i]['w'] else 0 for x in range(x0, x0 + pw)]
                   for y in range(y0, y0 + ph)]
            pieces[i][k] = (pw, ph, dx, dy, ('tile', at + len(data) // 32), when)
            data += dspic.rows_to_tiles(sub, 0, 0, pw, ph)
        late_tiles = (late, bytes(data), at)
    recs, precs, extra = [], [], 0
    for i, (L, ps) in enumerate(zip(letters, pieces)):
        flags = (frames.index(L['frame']) & 1) * L_MATRIX | (L['w'] == 64) * L_SQUARE
        recs.append(struct.pack('<BBhHBBH', L['frame'], flags, L['bx'], L['t0'] | PALETTE << 12,
                                L['by'] & 0xff, len(ps), len(precs)))
        for pw, ph, dx, dy, src, when in ps:
            t0 = src[1] if src[0] == 'tile' else L['t0'] + src[1]
            precs.append(struct.pack('<HBBBB', t0 | PALETTE << 12, SHAPES[pw, ph], dx, dy, when))
    for t in range(max(L['frame'] for L in letters) + ZOOM + 1):          # entries a frame
        n = 0
        for L, ps in zip(letters, pieces):
            if t - L['frame'] >= ZOOM:
                n += sum(1 for p in ps if not p[5] or (p[5] == 2) == (t >= late)) - 1
        extra = max(extra, n)
    if extra > EXTRA_TOP - EXTRA_LOW + 1: raise SystemExit('verdict: not enough OAM entries for the pieces')
    data = bytearray((TILE_END - tile) * 32)
    for t0, tl, _ in pics.values(): data[(t0 - tile) * 32:(t0 - tile) * 32 + len(tl)] = tl
    return bytes(data), tile, b''.join(recs), b''.join(precs), late_tiles, extra

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
        tiles, first, recs, pieces, late, extra = layout(ctx, kind)
        t = rom.store(tiles, 'ext', 4, f'verdict letters {kind}')
        l = rom.store(recs, 'ext', 4, f'verdict layout {kind}')
        p = rom.store(pieces, 'ext', 4, f'verdict pieces {kind}')
        frame, lt, lv = (late[0], rom.store(late[1], 'ext', 4, f'verdict late tiles {kind}'),
                         OBJ_VRAM + late[2] * 32) if late else (0xffff, 0, 0)
        tables.append(struct.pack('<HHIIIIHHH2xII', len(recs) // 10, len(tiles) // 4, t, l, OBJ_VRAM + first * 32,
                                  p, extra, frame, len(late[1]) // 4 if late else 0, lt, lv))
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
    print(f"  verdict: Not Guilty / Guilty in the English GS1's letters (the DS's at {SCALE:.0%}) at the DS's "
          f"height, a slam for each as on the DS")
