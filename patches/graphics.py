"""Graphics: English assets from the DS copied into the GBA ROM."""
import os, struct, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

import lz, chunkimg, textgfx

TITLE_MENU = {0x0818e300: 'New Game', 0x0818e500: 'Continue'}   # 64x16 sprites (two 32x16 cells), OBJ palette 2

DS_TITLE = 0x3684          # LZ: 512-byte palette + 256x192 8bpp tiles (English title logo)
GBA_TITLE_OBJ = 0x0826deb0 # chunked image object: 240x160 8bpp title screen
GBA_TITLE_REF = 0x0803b3d4 # table entry pointing at it

GBA_TAGS = 0x08181820      # 10 groups x 0x800: 5 tags per group, 6x2 tiles each (top row k*0xc0, bottom +0x400)
DS_TAGS_EN = 0x9360 + 0x5000   # same packing inside data.bin, DS index = GBA id - 1

# Markers the script puts on maps and diagrams (command 0x39 n: object n of the table at
# 0x08049c50, 12 bytes each: {u32 tiles, u16 bytes, u16 attr0, u16 attr1}; one 16x16 sprite in
# OBJ palette 6, 0x0823dde8).  data.bin has them too, each Japanese marker followed by the
# English one: object -> (data.bin offset of the Japanese marker, what it marks)
MARKER_TABLE = 0x08049c50
DS_MARKERS = {0: (0x60980, 'W (witness)'), 1: (0x60a80, 'V (victim)'), 4: (0x60c80, 'K (killer)')}

def apply(rom, ctx):
    d = ctx.data
    # --- name tags ---
    def ds_tag(i):
        grp, k = divmod(i, 5); off = DS_TAGS_EN + grp * 0x800 + k * 0xc0
        return d[off:off + 0xc0], d[off + 0x400:off + 0x400 + 0xc0]
    for gid in range(1, 50):
        top, bot = ds_tag(gid - 1)
        grp, k = divmod(gid, 5); off = GBA_TAGS + grp * 0x800 + k * 0xc0
        rom.write(off, top, 'name tag top'); rom.write(off + 0x400, bot, 'name tag bottom')
    print("  name tags: 49 replaced")
    markers(rom, ctx)
    title(rom, ctx)
    title_menu(rom, ctx)

def markers(rom, ctx):
    """The map markers 目, 被 and 犯 (witness, victim, killer): the DS's W, V and K."""
    for obj, (jp, what) in DS_MARKERS.items():
        tiles, size = struct.unpack_from('<IH', rom.read(MARKER_TABLE + 12 * obj, 6))
        if size != 0x80 or ctx.data[jp:jp + size] != rom.read(tiles, size):
            raise SystemExit(f'markers: the DS marker at {jp:#x} is not the GBA object {obj}')
        en = ctx.data[jp + size:jp + 2 * size]
        if en == rom.read(tiles, size): raise SystemExit(f'markers: no English marker after {jp:#x}')
        rom.write(tiles, en, f'map marker {obj}')
    print(f"  map markers: {', '.join(w for _, w in DS_MARKERS.values())} from the DS")

def title_menu(rom, ctx):
    """Title menu items: rendered with the DS font into the original sprite slots."""
    font = textgfx.Font.from_ctx(ctx)
    for addr, text in TITLE_MENU.items():
        sq = 0
        while font.measure(text) - sq * (len(text) - 1) > 62: sq += 1
        grid = textgfx.render(font, text, 64, 16, fill=3, outline=1, squeeze=sq)
        rom.write(addr, textgfx.sprite_cells(grid, 32, 16), 'title menu ' + text)
    print(f"  title menu: {len(TITLE_MENU)} items rendered")

def title(rom, ctx):
    """English title logo: the DS 256x192 image scaled to 240x160 (nearest neighbour keeps the
    palette), logo rows on top, the DS copyright line at the bottom."""
    dec, _ = lz.decompress(ctx.data, DS_TITLE)
    pal, img = dec[:512], dec[512:]
    lin = bytearray(256 * 192)
    for t in range(32 * 24):
        tx, ty = (t % 32) * 8, (t // 32) * 8
        for i in range(64): lin[(ty + i // 8) * 256 + tx + i % 8] = img[t * 64 + i]
    # logo (DS rows 8..160) scaled by 0.7 and centred, so it clears the menu sprite at y=112
    SCALE = 0.7
    lw, lh = int(256 * SCALE), int(152 * SCALE)
    x0 = (240 - lw) // 2
    out = bytearray(240 * 160)
    for y in range(lh):
        sy = 8 + int(y / SCALE)
        for x in range(lw):
            out[y * 240 + x0 + x] = lin[sy * 256 + int(x / SCALE)]
    # keep the original copyright rows (148..159) from the GBA image
    gpal, gtiles, _ = chunkimg.load(rom.d, GBA_TITLE_OBJ - 0x08000000)
    gl = bytearray(240 * 160)
    for ty in range(20):
        for tx in range(30):
            for yy in range(8):
                gl[(ty * 8 + yy) * 240 + tx * 8: (ty * 8 + yy) * 240 + tx * 8 + 8] = gtiles[(ty * 30 + tx) * 64 + yy * 8: (ty * 30 + tx) * 64 + yy * 8 + 8]
    out[148 * 240:] = gl[148 * 240:]
    tiles = bytearray()
    for ty in range(20):
        for tx in range(30):
            for yy in range(8):
                tiles += out[(ty * 8 + yy) * 240 + tx * 8: (ty * 8 + yy) * 240 + tx * 8 + 8]
    # palette: GBA entries 0..31 (shared UI bank), DS colours 32..255; the copyright rows use
    # GBA indices, so copy those colours over any DS indices they need
    newpal = bytearray(gpal[:64] + pal[64:])
    used_copy = set(gl[148 * 240:])
    for idx in used_copy:
        if idx >= 32: newpal[idx * 2: idx * 2 + 2] = gpal[idx * 2: idx * 2 + 2]
    obj = chunkimg.build(newpal, bytes(tiles))
    addr = rom.store(obj, 'ext', 4, 'title image')
    assert rom.u32(GBA_TITLE_REF) == GBA_TITLE_OBJ
    rom.w32(GBA_TITLE_REF, addr)
    print(f"  title screen replaced ({len(obj)} bytes at {addr:#x})")
