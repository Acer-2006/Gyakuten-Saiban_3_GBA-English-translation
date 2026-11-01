#!/usr/bin/env python3
"""Audit of the Court Record descriptions in a built ROM (the 160x72 pictures of 0.16.80).

  gs3_record_audit.py BUILT.gba US.nds [--layout build/court_record.json] [--png DIR]

For every item the picture the item table points at is unpacked from the built ROM and checked:

* the picture is 160x72 (180 tiles): rows 0-68 red (index 9) and rows 69-71 the panel's border
  in columns 0-151, columns 152-159 transparent, ink only the name (15) and the text (8);
* the text's pixels are exactly the lines the build recorded (build/court_record.json, written
  by every build), each drawn on its own with the DS font: nothing else, nothing missing;
* no pixel of one line is on or next to (8 ways, corners included) a pixel of another line, the
  name line counting as a line;
* the lines put together are the DS description word for word.

It prints one line per item with a problem and a summary; the exit status is 1 if any item has
one.  --png writes each picture (4x, the panel's colours) to DIR for looking at.
"""
import sys, os, json, struct, argparse
from _common import *
import lz, nitrofs, dsdesc, dsimgtext
sys.path.insert(0, ROOT)
from patches import court_record as cr

W, H, W_USE, RED_LAST = 160, 72, 152, 68
BG, NAME, TEXT, CLEAR = 9, 15, 8, 0

def picture(rom, addr):
    """The 160x72 picture at addr (LZ77) -> rows of indices."""
    tiles, _ = lz.decompress(rom, rom_off(addr))
    if len(tiles) != 180 * 32: raise ValueError(f'{len(tiles)} bytes, not 180 tiles')
    img = [[0] * W for _ in range(H)]
    def put(t, x0, y0):
        for r in range(8):
            for c in range(8):
                b = tiles[t * 32 + r * 4 + c // 2]
                img[y0 + r][x0 + c] = b >> 4 * (c & 1) & 15
    t = 0
    for cy in range(2):                     # ten 32x32 cells, 5 across and 2 down
        for cx in range(5):
            for ty in range(4):
                for tx in range(4):
                    put(t, cx * 32 + tx * 8, cy * 32 + ty * 8); t += 1
    for tx in range(20):                    # rows 64-71, left to right
        put(t, tx * 8, 64); t += 1
    return img

def pixels(img, index):
    return {(x, y) for y in range(H) for x in range(W) if img[y][x] == index}

def line_pixels(font, line, top, cut):
    out = set()
    for x, m in enumerate(font.masks(line, cr.TEXT_X, W, cut)):
        for k in range(16):
            if m >> k & 1: out.add((x, top + k))
    return out

def touching(a, b):
    """Pixels of a on or next to (8 ways) a pixel of b."""
    return sum(1 for (x, y) in a if any((x + dx, y + dy) in b for dx in (-1, 0, 1) for dy in (-1, 0, 1)))

def joined(lines):
    """The lines as one text, both ways where a line ends in a hyphen (a word split by the build,
    or a hyphen of the text)."""
    outs = ['']
    for ln in lines:
        nxt = []
        for o in outs:
            if not o: nxt.append(ln); continue
            nxt.append(o + ' ' + ln)
            if o.endswith('-'): nxt.append(o[:-1] + ln)
        outs = nxt
    return outs

# the panel's colours, near enough (index: 8 text, 9 red, 10-11 and 1 the border, 15 the name)
PNG_PAL = [(0, 0, 0), (40, 16, 16)] + [(0, 0, 0)] * 6 + [(248, 248, 248), (96, 24, 24), (200, 150, 150),
           (140, 90, 90)] + [(0, 0, 0)] * 3 + [(248, 248, 0)]

def write_png(path, img):
    from _png import write_png as wp
    s = 4
    rows = [bytes(img[y // s][x // s] for x in range(W * s)) for y in range(H * s)]
    wp(path, W * s, H * s, rows, PNG_PAL)

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('gba'); ap.add_argument('nds')
    ap.add_argument('--layout', default=os.path.join(ROOT, 'build', 'court_record.json'))
    ap.add_argument('--png', metavar='DIR')
    a = ap.parse_args()
    rom = load_rom(a.gba)
    nds = open(a.nds, 'rb').read()
    files = nitrofs.files(nds)
    a9o, _, _, a9s = struct.unpack_from('<IIII', nds, 0x20)
    arm9, data = nds[a9o:a9o + a9s], files['data.bin']
    lay = json.load(open(a.layout))
    fonts = {False: dsdesc.Font(data, arm9), True: dsdesc.Font(data, arm9, stem_gap=True)}
    recs = cr.ds_items(arm9)
    db = struct.unpack_from('<8I', arm9, cr.DS_BASES - cr.DS_ARM9)[cr.DESC_BASE]
    dsz = dsimgtext.texture_size(data, db)
    reader = dsimgtext.TextReader(data, arm9)
    class Reader:
        def read(self, ad, n): return rom[rom_off(ad):rom_off(ad) + n]
    border = cr.border_rows(Reader())
    if a.png: os.makedirs(a.png, exist_ok=True)
    bad, spacing, contacts_n, checked = {}, {}, 0, 0
    for i in range(cr.COUNT):
        addr = struct.unpack_from('<I', rom, rom_off(cr.GBA_ITEMS + 8 * i))[0]
        problems = []
        if lay['pictures'].get(str(i)) != addr: problems.append('not the picture the build recorded')
        try:
            img = picture(rom, addr)
        except Exception as ex:
            bad[i] = [f'picture: {ex}']; continue
        # the panel: red, border, transparent columns, nothing but name and text ink
        for y in range(H):
            for x in range(W):
                v = img[y][x]
                if x >= W_USE: want = {CLEAR}
                elif y > RED_LAST: want = {border[y - 64]}
                else: want = {BG, NAME, TEXT}
                if v not in want:
                    problems.append(f'pixel ({x}, {y}) is {v}'); break
            else: continue
            break
        L = lay['layouts'].get(str(i))
        if L is None:
            if str(i) not in lay['pictures']: problems.append('no layout')
            if problems: bad[i] = problems
            continue
        checked += 1
        font = fonts[L['stem_gap']]
        name = pixels(img, NAME)
        text = pixels(img, TEXT)
        lines = [line_pixels(font, l, t, L['word_cut']) for l, t in zip(L['lines'], L['tops'])]
        union = set().union(*lines)
        if union != text:
            problems.append(f'text pixels differ from the recorded lines ({len(union ^ text)})')
        parts = [name] + lines
        n = 0
        for p in range(len(parts)):
            for q in range(p + 1, len(parts)):
                k = touching(parts[p], parts[q])
                if k: problems.append(f'{"name" if p == 0 else "line %d" % p} touches line {q} ({k} pixels)'); n += 1
        contacts_n += bool(n)
        # the DS text, word for word
        r = recs[i]
        px, w, h, _ = dsimgtext.texture(data, db + r[4] * dsz)
        ds_text = cr.adapt(cr.join_lines(reader.read_image(px, w, h)), r[5] != 0)
        if ds_text not in joined(L['lines']): problems.append('the lines are not the DS text')
        if len(L['lines']) == 4:
            t = L['tops']; key = (t[0],) + tuple(t[k + 1] - t[k] for k in range(3))
            spacing[key] = spacing.get(key, 0) + 1
        if problems: bad[i] = problems
        if a.png:
            write_png(os.path.join(a.png, f'{i:03d}.png'), img)
    for i, p in sorted(bad.items()):
        print(f'item {i}: ' + '; '.join(p))
    print(f'{checked} descriptions checked, {len(bad)} with a problem, {contacts_n} with lines touching')
    print('four lines (first row, gaps): ' + ', '.join(f'{k}: {v}' for k, v in sorted(spacing.items(), key=lambda kv: -kv[1])))
    sys.exit(1 if bad else 0)

if __name__ == '__main__':
    main()
