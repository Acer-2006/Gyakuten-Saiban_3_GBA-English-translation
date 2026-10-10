"""Character sprites the DS version changed for its English release: college Phoenix's sweater
says P instead of RYU (person 7 and the close-up of effects 35-37), and the policeman of person
12 no longer wears his armband with Japanese writing on it.

Characters (the person table at 0x08046920: {u32 sub-archive, u32 animations, u32 count} per
person, and further sub-archives after each one for its other poses) and cut-scene effects keep
their pictures in sub-archives (see patches/banners.py), and so does the DS.  For each picture
the English version changed, data.bin has the sub-archive twice, Japanese (the GBA's cells, byte
for byte) and English, with the same cells in the same order.  The DS adds a few frames the GBA
does not have, so the GBA's cells are found by their contents: every GBA cell that is the same as
a Japanese cell the English version changed gets the English one.  The new cell goes into the
expansion area and the sub-archive's cell table points to it (cell offsets are 32-bit and count
from the table, and the game unpacks a cell until the sprite is full rather than up to the next
cell), so the frame data and the rest of the sub-archive stay where they are.

Two more pairs in data.bin (0x70f8dc / 0x70fab8 and 0x712ac8 / 0x713258, effects 204 and 211 on
the GBA) change a few pixels of pictures with no writing in them, so they are left as they are.
"""
import os, struct, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
import dspic

DS_PAIRS = [                                   # (Japanese, English) sub-archives in data.bin
    (0x53ccf0, 0x6f3f9c, 'college Phoenix'),
    (0x544150, 0x6fb274, 'college Phoenix'),
    (0x548ad0, 0x6ffaf8, 'college Phoenix'),
    (0x758718, 0x75ac78, 'college Phoenix (cut-in)'),
    (0x58b270, 0x704db8, 'policeman'),
    (0x590f5c, 0x70a9dc, 'policeman'),
    (0x593cc4, 0x70d710, 'policeman'),
]
GBA_AREA = (0x480000, 0x6e3578)               # the GBA's person and effect pictures (offsets)

def rle_size(data, p, end):
    """Bytes a packed cell unpacks to (the cell runs from p to end)."""
    n = 0
    while p < end:
        t = struct.unpack_from('<H', data, p)[0]; p += 2
        if t & 0x8000: n += 2 * (t & 0x7fff); p += 2
        else: n += 2 * t; p += 2 * t
    return n

def gba_cells(g):
    """Every cell of every sub-archive in GBA_AREA: {cell address: (table address, index)}."""
    out = {}
    i = GBA_AREA[0]
    while True:
        i = g.find(b'\x00\x80', i, GBA_AREA[1])
        if i < 0: break
        s = i - 2; i += 1
        if s % 2: continue
        npal = struct.unpack_from('<H', g, s)[0]
        if not 1 <= npal <= 16: continue
        tab = s + 4 + 32 * npal
        first = struct.unpack_from('<I', g, tab)[0]
        if first % 4 or not 4 <= first <= 4096: continue
        offs = struct.unpack_from(f'<{first // 4}I', g, tab)
        if any(b <= a for a, b in zip(offs, offs[1:])) or offs[-1] > 0x80000: continue
        for k, o in enumerate(offs): out.setdefault(tab + o, (tab, k))
    return out

def apply(rom, ctx):
    data, g = ctx.data, bytes(rom.d[:rom.orig_size])
    cells = gba_cells(g)
    stored, changed = {}, 0
    for jp, en, name in DS_PAIRS:
        nj, fj, pj, cj = dspic.sub_archive(data, jp)
        ne, fe, pe, ce = dspic.sub_archive(data, en)
        if (nj, len(cj)) != (ne, len(ce)) or pj != pe:
            raise SystemExit(f'sprites: unexpected DS sub-archives at data.bin {jp:#x} / {en:#x} ({name})')
        found = 0
        for i in range(len(cj) - 1):
            a, b = data[cj[i]:cj[i + 1]], data[ce[i]:ce[i + 1]]
            if a == b: continue
            if rle_size(a, 0, len(a)) != rle_size(b, 0, len(b)):
                raise SystemExit(f'sprites: DS cell {i} of {jp:#x} changed size ({name})')
            h = g.find(a, GBA_AREA[0], GBA_AREA[1])
            while h >= 0:
                if h in cells:
                    tab, k = cells[h]
                    if b not in stored: stored[b] = rom.store(b, 'ext', 4, f'{name} cell')
                    rom.w32(0x08000000 + tab + 4 * k, stored[b] - (0x08000000 + tab))
                    found += 1
                h = g.find(a, h + 1, GBA_AREA[1])
        if not found: raise SystemExit(f'sprites: none of the {name} cells changed by the DS are in the GBA ROM')
        changed += found
    print(f"  sprites: {changed} cells from the DS English sprites (college Phoenix's sweater, the policeman's armband)")
