"""The escaped convict's data screen (episode 4): its two title bars in English.

Effects 69 and 70 are the bars (sub-archive 0x2d240 of the effects archive, see
patches/banners.py; one palette, 17 cells): 224x32 at the top of the screen, a rounded end cap
(cell 0, flipped at the right end) and pieces of the bar with the lettering, 16x32 to 64x32.
Effects 71-73, the PICTURE, DATA1 and DATA2 tabs (cells 8-16), are in English already.

The DS keeps the sub-archive twice in data.bin, Japanese at 0x76c254 and English at 0x76d2c0;
the English one has the same cap and tabs and new lettering pieces.  The build copies the cap and
the pieces into a sub-archive of their own (plus a plain 32x32 piece made of two 16x32 ones) and
lays the bars out again: the caps stay where they are, the lettering is centred between them.
The new frame data replaces the old in place: a game saved while the bars are up keeps the
address of their frames.
"""
import struct
from .banners import rle16, unrle16, FX_ARCHIVE, effect_entries
from .episodes import read_frames, write_frames, write_sub, SHAPE, tiles_to_grid, grid_to_tiles

DS_SUB = 0x76d2c0                 # data.bin: the English sub-archive
GBA_SUB = 0x2d240
TAB_FRAMES = [0x086e282c, 0x086e27d4, 0x086e2800]     # effects 71-73, to check the DS copy
# the DS cells copied: cell -> (w, h): the cap, a plain 16x32 piece, the lettering pieces
DS_CELLS = {0: (16, 32), 1: (16, 32), 2: (64, 32), 3: (64, 32), 4: (32, 32), 5: (64, 32),
            6: (64, 32), 7: (32, 32)}
PLAIN = 8                         # the new cell: two plain pieces side by side
# the inside of each bar, between the caps at x -112 and 96: (x, w, cell); y and h as the caps
BARS = {
    0x086e2768: [(-96, 32, PLAIN), (-64, 64, 2), (0, 64, 3), (64, 32, PLAIN)],   # effect 69
    0x086e27a0: [(-96, 32, 7), (-64, 64, 6), (0, 64, 5), (64, 32, 4)],           # effect 70
}

def ds_sub(data):
    npal, flag = struct.unpack_from('<HH', data, DS_SUB)
    tab = DS_SUB + 4 + 32 * npal
    n = struct.unpack_from('<I', data, tab)[0] // 4
    return npal, flag, [tab + struct.unpack_from('<I', data, tab + 4 * i)[0] for i in range(n)]

def apply(rom, ctx):
    data = ctx.data
    npal, flag, cells = ds_sub(data)
    s = FX_ARCHIVE + GBA_SUB
    gnpal, gflag = rom.u16(s), rom.u16(s + 2)
    gtab = s + 4 + 32 * gnpal
    gcells = [gtab + rom.u32(gtab + 4 * i) for i in range(rom.u32(gtab) // 4)]
    if (npal, flag, len(cells)) != (gnpal, gflag, len(gcells)):
        raise SystemExit('datascreen: unexpected DS sub-archive')
    def same(cell, w, h):
        return unrle16(data, cells[cell], w * h // 2) == unrle16(rom.d, gcells[cell] - 0x08000000, w * h // 2)
    tabs = [(c, w, h) for fp in TAB_FRAMES for sp in read_frames(rom, fp)[2].values() for x, y, w, h, c, a in sp]
    if not tabs or not all(same(c, w, h) for c, w, h in tabs) or not same(0, 16, 32):
        raise SystemExit('datascreen: the DS sub-archive does not match the GBA one')
    pics = {c: unrle16(data, cells[c], w * h // 2) for c, (w, h) in DS_CELLS.items()}
    g = tiles_to_grid(pics[1], 16, 32)
    plain = [r + r for r in g]
    out = [rle16(pics[c]) for c in sorted(DS_CELLS)] + [rle16(grid_to_tiles(plain, 0, 0, 32, 32))]
    arch = rom.store(write_sub(npal, flag, rom.read(s + 4, 32 * npal), out), 'ext', 4, 'data screen bars')
    for fp, inside in BARS.items():
        sub, fl, defs = read_frames(rom, fp)
        new = {}
        for off, sp in defs.items():
            caps = [t for t in sp if t[4] == 0]
            if sub != GBA_SUB or sorted((x, w, h) for x, y, w, h, c, a in caps) != [(-112, 16, 32), (96, 16, 32)]:
                raise SystemExit(f'datascreen: unexpected frame data at {fp:#x}')
            y = caps[0][1]
            new[off] = caps + [(x, y, w, 32, c, SHAPE[(w, 32)] << 12) for x, w, c in inside]
        entries = effect_entries(rom, [fp])
        if len(entries) != 1: raise SystemExit('datascreen: unexpected effects')
        # in place of the old frames (a saved game keeps the address of a running effect's frames,
        # so it stays the same from build to build)
        data = write_frames(fl, new)
        size = max([8 + 8 * len(fl)] + [off + 4 + 4 * len(sp) for off, sp in defs.items()])
        if len(data) > size: raise SystemExit('datascreen: new frames do not fit')
        rom.write(fp, data, 'data screen bar frames')
        for e in entries:
            rom.w32(e, arch)
    print("  data screen: title bars from the DS")
