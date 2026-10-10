"""Graphics: English assets from the DS copied into the GBA ROM."""
import os, struct, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

import lz, chunkimg, textgfx, resample

TITLE_MENU = {0x0818e300: 'New Game', 0x0818e500: 'Continue'}   # 64x16 sprites (two 32x16 cells), OBJ palette 2
# New Game only fits with its letters 2 pixels closer than the DS sets them, so that they touch;
# every pair of letters gets a pixel back, which fills the sprite to its last column
TITLE_KERN = {'Ne': 1, 'ew': 1, 'Ga': 1, 'am': 1, 'me': 1}

DS_TITLE = 0x3684          # LZ: 512-byte palette + 256x192 8bpp tiles (English title logo)
DS_TITLE_BG = 32           # its background colour
DS_LOGO = (4, 10, 252, 158)    # the logo in it (x0, y0, x1, y1; its ink is x 4..251, y 11..156)
LOGO_SCALE = (3, 4)        # 248x148 -> 186x111: as large as it fits above the menu (y 112)
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
        kern = sum(TITLE_KERN.get(text[i:i + 2], 0) for i in range(len(text) - 1))
        while font.measure(text) - sq * (len(text) - 1) + kern > 64: sq += 1   # the bearings hold the outline
        grid = textgfx.render(font, text, 64, 16, fill=3, outline=1, squeeze=sq, kern=TITLE_KERN)
        rom.write(addr, textgfx.sprite_cells(grid, 32, 16), 'title menu ' + text)
    print(f"  title menu: {len(TITLE_MENU)} items rendered")

def title(rom, ctx):
    """English title logo: the DS picture's logo scaled to 3/4 with a filter, each pixel then taking
    the nearest of the logo's own colours (tools/resample.py), centred at the top of the screen so
    it clears the menu at y=112; the GBA picture's copyright line at the bottom."""
    dec, _ = lz.decompress(ctx.data, DS_TITLE)
    pal, img = dec[:512], dec[512:]
    lin = bytearray(256 * 192)
    for t in range(32 * 24):
        tx, ty = (t % 32) * 8, (t // 32) * 8
        for i in range(64): lin[(ty + i // 8) * 256 + tx + i % 8] = img[t * 64 + i]
    if lin[0] != DS_TITLE_BG: raise SystemExit('title: unexpected DS title picture')
    x0, y0, x1, y1 = DS_LOGO
    w, h = x1 - x0, y1 - y0
    nw, nh = w * LOGO_SCALE[0] // LOGO_SCALE[1], h * LOGO_SCALE[0] // LOGO_SCALE[1]
    crop = bytes(lin[y * 256 + x] for y in range(y0, y1) for x in range(x0, x1))
    logo = resample.scale_indexed(crop, w, h, struct.unpack('<256H', pal), nw, nh)
    out = bytearray([DS_TITLE_BG]) * (240 * 160)
    lx = (240 - nw) // 2
    for y in range(nh):
        out[y * 240 + lx:y * 240 + lx + nw] = logo[y * nw:(y + 1) * nw]
    # keep the original copyright rows (148..159) from the GBA image
    gpal, gtiles, _ = chunkimg.load(rom.d, GBA_TITLE_OBJ - 0x08000000)
    gl = bytearray(240 * 160)
    for ty in range(20):
        for tx in range(30):
            for yy in range(8):
                gl[(ty * 8 + yy) * 240 + tx * 8: (ty * 8 + yy) * 240 + tx * 8 + 8] = gtiles[(ty * 30 + tx) * 64 + yy * 8: (ty * 30 + tx) * 64 + yy * 8 + 8]
    out[148 * 240:] = gl[148 * 240:]
    # palette: GBA entries 0..31 (shared UI bank), DS colours 32..255.  The copyright rows use GBA
    # indices: where the logo uses the same index for a colour within a step of the GBA's (black
    # 32, grey 195), the GBA colour goes in; otherwise the copyright pixels move to an index the
    # logo leaves free.
    newpal = bytearray(gpal[:64] + pal[64:])
    used = set(logo)
    free = [i for i in range(255, 31, -1) if i not in used]
    def close(a, b): return all(abs((a >> k & 31) - (b >> k & 31)) <= 1 for k in (0, 5, 10))
    remap = {}
    for idx in sorted(set(gl[148 * 240:])):
        if idx < 32: continue
        g = struct.unpack_from('<H', gpal, idx * 2)[0] & 0x7fff
        if idx in used and not close(g, struct.unpack_from('<H', pal, idx * 2)[0]):
            if not free: raise SystemExit('title: no palette entry left for the copyright line')
            remap[idx] = free.pop(0); idx = remap[idx]
        struct.pack_into('<H', newpal, idx * 2, g)
    for i in range(148 * 240, 160 * 240):
        out[i] = remap.get(out[i], out[i])
    tiles = bytearray()
    for ty in range(20):
        for tx in range(30):
            for yy in range(8):
                tiles += out[(ty * 8 + yy) * 240 + tx * 8: (ty * 8 + yy) * 240 + tx * 8 + 8]
    obj = chunkimg.build(newpal, bytes(tiles))
    addr = rom.store(obj, 'ext', 4, 'title image')
    assert rom.u32(GBA_TITLE_REF) == GBA_TITLE_OBJ
    rom.w32(GBA_TITLE_REF, addr)
    print(f"  title screen replaced ({len(obj)} bytes at {addr:#x}; the DS logo at {nw}x{nh})")
