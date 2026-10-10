"""Court Record icons: the DS's English pictures for the items whose icon carries writing.

GBA: a table of 123 pointers at 0x0804660c, one LZ picture each: 32 bytes of palette (16 BGR555
colours, index 0 transparent) and a 64x64 4bpp picture as 8x8 tiles in rows (2048 bytes).  The
Court Record, the item shown in court and the presenting animation all draw from it.

DS: the same 123 pictures, in the same order, as 64x64 16-colour textures laid out one after
another in data.bin (the second of the per-language base offsets at 0x020a44c0 / 0x020a44e0;
the set is shared by both languages), followed by one more and then twenty pairs: the Japanese
picture again, then the English version of it (the Coldkiller X bottle, the Ami jar, the
newspapers and magazines, the letters, ...).  The game picks the English one by code; the build
finds each pair's Japanese picture among the GBA's and puts the English one in its place,
leaving pairs whose two pictures are the same alone.
"""
import struct, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import lz, dsimgtext

GBA_ICONS = 0x0804660c
GBA_COUNT = 123
DS_BASES = 0x020a44e0           # English: u32[8] offsets into data.bin; the icons are word 1
DS_ARM9 = 0x02000000
DS_COUNT = 164
FIRST_PAIR = 124

def ds_pictures(d, base):
    """-> [(rows, palette bytes)] of the DS set, in order."""
    out, o = [], base
    for _ in range(DS_COUNT):
        px, w, h, pal = dsimgtext.texture(d, o)
        if (w, h) != (64, 64): raise SystemExit('icons: a DS icon is not 64x64')
        out.append((px, pal))
        _, _, _, _, ioff, isz, poff, psz = struct.unpack_from('<4B4I', d, o)
        o += poff + psz
    return out

def rgb(pal, i):
    c = struct.unpack_from('<H', pal, 2 * i)[0]
    return (c & 31, c >> 5 & 31, c >> 10 & 31)

def gba_picture(rom, k):
    """GBA icon k -> (rows, palette bytes)."""
    p = rom.u32(GBA_ICONS + 4 * k)
    data, _ = lz.decompress(rom.d, p - 0x08000000)
    pal, px = data[:32], data[32:]
    rows = [[0] * 64 for _ in range(64)]
    for t in range(64):
        for y in range(8):
            for x in range(8):
                b = px[t * 32 + y * 4 + x // 2]
                rows[(t // 8) * 8 + y][(t % 8) * 8 + x] = (b >> 4) if x & 1 else (b & 15)
    return rows, pal

def colours(rows, pal):
    return [[rgb(pal, v) if v else None for v in row] for row in rows]

def encode(rows, pal):
    """(rows, palette) -> the GBA picture: palette, then 8x8 tiles in rows."""
    out = bytearray(pal[:32])
    for t in range(64):
        for y in range(8):
            for x in range(0, 8, 2):
                r = rows[(t // 8) * 8 + y]; x0 = (t % 8) * 8 + x
                out.append(r[x0] | r[x0 + 1] << 4)
    return bytes(out)

def apply(rom, ctx):
    d, arm9 = ctx.data, ctx.arm9
    base = struct.unpack_from('<8I', arm9, DS_BASES - DS_ARM9)[1]
    ds = ds_pictures(d, base)
    gba = {k: colours(*gba_picture(rom, k)) for k in range(GBA_COUNT)}
    replaced, same, unmatched = [], [], []
    for k in range(FIRST_PAIR, DS_COUNT, 2):
        jp, en = ds[k], ds[k + 1]
        if colours(*jp) == colours(*en): same.append(k); continue
        g = next((g for g in range(GBA_COUNT) if gba[g] == colours(*jp)), None)
        if g is None: unmatched.append(k); continue
        data = lz.compress(encode(*en))
        rom.w32(GBA_ICONS + 4 * g, rom.store(data, 'ext', 4, f'icon {g}'))
        replaced.append(g)
    if unmatched: raise SystemExit(f'icons: DS pairs {unmatched} match no GBA icon')
    print(f"  icons: {len(replaced)} from the DS English pictures ({', '.join(map(str, replaced))}); "
          f"{len(same)} pairs the same in both languages")
