"""Shout bubbles in English: OBJECTION!, HOLD IT!, TAKE THAT!

The Japanese bubbles (異議あり！, 待った！, くらえ！) are tall spiky bubbles with the words written
vertically, three sub-archives of the effects archive (see patches/banners.py for the formats),
each with one frame of seven sprites: 32x64, 64x64, 64x64, 32x64 and three 32x16, 216 tiles in
all at OBJ tile 0x1e8.  English needs a wide bubble, so the build draws a new 144x96 picture,
cuts it into seven sprites with the same tile budget (two 64x64, two 64x32, three 16x32), writes
new frame data for them, and moves the bubbles that sat at the left and right screen edge so the
wider bubble stays on screen.

The lettering is a chunky italic block face drawn here (6x10 cells at double size); the bubble
is a spiky ellipse.  Colours are the original palette's: 1 white, 2 red, 4 dark red, 5 bubble
outline, 6 grey, 7 light red.
"""
import math, os, struct, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
from .banners import rle16, FX_ARCHIVE, effect_entries

# (old frame data, sub-archive offset in the effects archive, lines, layout)
SHOUTS = [(0x086de558, 0x28e4, ['OBJECTION!'], 'wide'),
          (0x086de590, 0x3c44, ['HOLD IT!'], 'wide'),
          # shown together with the evidence being presented, which flies in right next to it:
          # keep the original tall bubble so the two do not overlap
          (0x086de5c8, 0x4e24, ['TAKE', 'THAT!'], 'tall')]
EDGE_X = {0x2d: 72, 0xbe: 168}         # wide bubbles: anchors at the screen edges moved in so the
                                       # 144-pixel bubble stays on screen

LETTERS = {
    'O': ['.####.', '######', '##..##', '##..##', '##..##', '##..##', '##..##', '##..##', '######', '.####.'],
    'B': ['#####.', '######', '##..##', '##..##', '#####.', '#####.', '##..##', '##..##', '######', '#####.'],
    'J': ['...###', '...###', '....##', '....##', '....##', '....##', '##..##', '##..##', '######', '.####.'],
    'E': ['######', '######', '##....', '##....', '#####.', '#####.', '##....', '##....', '######', '######'],
    'C': ['.#####', '######', '##....', '##....', '##....', '##....', '##....', '##....', '######', '.#####'],
    'T': ['######', '######', '..##..', '..##..', '..##..', '..##..', '..##..', '..##..', '..##..', '..##..'],
    'I': ['##'] * 10,
    'N': ['##..##', '###.##', '###.##', '######', '######', '##.###', '##.###', '##..##', '##..##', '##..##'],
    'H': ['##..##', '##..##', '##..##', '##..##', '######', '######', '##..##', '##..##', '##..##', '##..##'],
    'L': ['##....'] * 8 + ['######', '######'],
    'D': ['#####.', '######', '##..##', '##..##', '##..##', '##..##', '##..##', '##..##', '######', '#####.'],
    'A': ['.####.', '######', '##..##', '##..##', '######', '######', '##..##', '##..##', '##..##', '##..##'],
    'K': ['##..##', '##.###', '#####.', '####..', '###...', '####..', '#####.', '##.###', '##..##', '##..##'],
    '!': ['##', '##', '##', '##', '##', '##', '##', '..', '##', '##'],
    'S': ['.#####', '######', '##....', '##....', '#####.', '.#####', '....##', '....##', '######', '#####.'],
    'V': ['##..##', '##..##', '##..##', '##..##', '##..##', '##..##', '##..##', '.####.', '.####.', '..##..'],
}
WHITE, RED, DARK, EDGE, GREY, LIGHT = 1, 2, 4, 5, 6, 7
# picture size and the seven sprites (x, y, w, h) cut from it, in VRAM order; 216 tiles each
LAYOUTS = {
    'wide': ((144, 96), [(0, 0, 64, 64), (64, 0, 64, 64), (128, 0, 16, 32), (128, 32, 16, 32),
                         (0, 64, 64, 32), (64, 64, 64, 32), (128, 64, 16, 32)]),
    'tall': ((96, 144), [(64, 0, 32, 64), (0, 0, 64, 64), (0, 64, 64, 64), (64, 64, 32, 64),
                         (0, 128, 32, 16), (32, 128, 32, 16), (64, 128, 32, 16)]),   # the original's
}
SHAPE = {(64, 64): 0xc, (16, 32): 0xa, (64, 32): 0xd, (32, 64): 0xe, (32, 16): 0x9}  # size << 2 | shape

def lettering(text, scale=2, slant=3):
    cells = [None if ch == ' ' else LETTERS[ch] for ch in text]
    units = sum(3 if c is None else len(c[0]) for c in cells) + len(cells) - 1
    h = 10 * scale
    m = [[0] * (units * scale + h // (h // slant) + 2) for _ in range(h)]
    x = 0
    for c in cells:
        if c is None: x += 4; continue
        for r, row in enumerate(c):
            for k, v in enumerate(row):
                if v != '#': continue
                for dy in range(scale):
                    for dx in range(scale):
                        yy = r * scale + dy
                        m[yy][(x + k) * scale + dx + (h - 1 - yy) // (h // slant)] = 1
        x += len(c[0]) + 1
    xs = [i for i in range(len(m[0])) if any(row[i] for row in m)]
    return [row[xs[0]:xs[-1] + 1] for row in m]

def bubble(W, H, spikes=18):
    cx, cy, rx, ry = W / 2 - 0.5, H / 2 - 0.5, W / 2 - 1, H / 2 - 1
    img = [[0] * W for _ in range(H)]
    for y in range(H):
        for x in range(W):
            dx, dy = (x - cx) / rx, (y - cy) / ry
            th = (math.atan2(dy, dx) / (2 * math.pi)) % 1.0
            t = (th * spikes) % 1.0
            peak = 1.0 if int(th * spikes) % 2 == 0 else 0.94
            lim = 0.84 + (peak - 0.84) * (1 - abs(2 * t - 1)) ** 2.2
            if math.hypot(dx, dy) < lim: img[y][x] = WHITE
    src = [r[:] for r in img]
    for y in range(H):
        for x in range(W):
            if src[y][x] == WHITE and any(not (0 <= y + dy < H and 0 <= x + dx < W) or src[y + dy][x + dx] == 0
                                          for dy in (-1, 0, 1) for dx in (-1, 0, 1)):
                img[y][x] = EDGE
    return img

def picture(lines, W, H, gap=6):
    img = bubble(W, H)
    ms = [lettering(t) for t in lines]
    th = sum(len(m) for m in ms) + gap * (len(ms) - 1)
    y0 = (H - th) // 2
    marks = []
    for m in ms:
        h, w = len(m), len(m[0])
        if w > W - 6: raise ValueError(f'shout too wide: {lines}')
        marks.append((m, (W - w) // 2, y0)); y0 += h + gap
    for m, x0, y0 in marks:                              # drop shadow
        for y in range(len(m)):
            for x in range(len(m[0])):
                if m[y][x] and 0 <= y0 + y + 2 < H and 0 <= x0 + x + 2 < W and img[y0 + y + 2][x0 + x + 2] == WHITE:
                    img[y0 + y + 2][x0 + x + 2] = GREY
    for m, x0, y0 in marks:
        for y in range(len(m)):
            for x in range(len(m[0])):
                if m[y][x]: img[y0 + y][x0 + x] = RED
    src = [r[:] for r in img]
    for y in range(H):
        for x in range(W):
            if src[y][x] != RED and any(0 <= y + dy < H and 0 <= x + dx < W and src[y + dy][x + dx] == RED
                                        for dy in (-1, 0, 1) for dx in (-1, 0, 1)):
                img[y][x] = DARK
            elif src[y][x] == RED and y > 0 and src[y - 1][x] != RED:
                img[y][x] = LIGHT                        # light top edge on every stroke
    return img

def piece(img, x0, y0, w, h):
    out = bytearray()
    for ty in range(h // 8):
        for tx in range(w // 8):
            for y in range(8):
                row = img[y0 + ty * 8 + y]
                for x in range(x0 + tx * 8, x0 + tx * 8 + 8, 2):
                    out.append((row[x] & 15) | ((row[x + 1] & 15) << 4))
    return bytes(out)

def apply(rom, ctx):
    a = FX_ARCHIVE
    archive = bytearray(); frames_new = {}; wide = set()
    for old_fp, sub, lines, layout in SHOUTS:
        if rom.u32(old_fp + 4) != sub or rom.u16(a + sub) != 1:
            raise SystemExit(f'shouts: unexpected frame data at {old_fp:#x}')
        pal = rom.read(a + sub + 4, 32)
        (W, H), PIECES = LAYOUTS[layout]
        if layout == 'wide': wide.add(old_fp)
        img = picture(lines, W, H)
        cells = [rle16(piece(img, *p)) for p in PIECES]
        off = len(archive)
        table = bytearray(); body = bytearray()
        for c in cells:
            table += struct.pack('<I', 4 * len(cells) + len(body)); body += c
        archive += struct.pack('<HH', 1, rom.u16(a + sub + 2)) + pal + table + body
        while len(archive) % 4: archive.append(0)
        # frame data: the original timing, one frame of the seven pieces centred on the anchor
        n = rom.u16(old_fp + 2)
        fl = [(rom.u16(old_fp + 8 + 8 * i), rom.u16(old_fp + 10 + 8 * i)) for i in range(n)]
        if len({o for o, _ in fl}) != 1: raise SystemExit('shouts: bubble with more than one frame')
        defs = 8 + 8 * n
        fd = struct.pack('<HHI', 0, n, off)
        for _, t in fl: fd += struct.pack('<HHI', defs, t, 0)
        fd += struct.pack('<HH', len(PIECES), 0)
        for k, (x, y, w, h) in enumerate(PIECES):
            px, py = (x - W // 2) & 0xff, (y - H // 2) & 0xff
            fd += struct.pack('<HH', py << 8 | px, SHAPE[(w, h)] << 12 | k)
        frames_new[old_fp] = fd
    arch_addr = rom.store(bytes(archive), 'ext', 4, 'shout bubbles')
    fd_addr = {fp: rom.store(fd, 'ext', 4, 'shout frames') for fp, fd in frames_new.items()}
    moved = 0
    entries = effect_entries(rom, set(fd_addr))           # effects 1-9 (left x=45, right x=190, centre)
    for e in entries:
        fp = rom.u32(e + 8)
        if rom.u32(e) != a: raise SystemExit(f'shouts: unexpected entry at {e:#x}')
        rom.w32(e, arch_addr); rom.w32(e + 8, fd_addr[fp])
        x = rom.u16(e + 12)
        if fp in wide and x in EDGE_X:
            rom.w16(e + 12, EDGE_X[x]); moved += 1
    print(f"  shouts: {len(SHOUTS)} bubbles redrawn ({len(archive)} bytes) for {len(entries)} effects, "
          f"{moved} moved in from the edge")
