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
from dspic import SIZE as dsimg_size

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

# The item shown in court (OAM 65, a 64x64 sprite at the top left) is DMA'd to OBJ tiles
# 0x80-0xbf, which the English page's third line of sprite text needs (the original's two lines
# take 0x00-0x7f; the effects that play over dialogue, such as the butterflies, are at 0xe0 on).
# It moves to 0x1e0-0x21f, the Court Record's text sprites, whose only other user is the Record
# itself: the game DMAs the item again when the Record closes.
ITEM_DMA_LIT = 0x080158a4            # 0x06011000 in the routine at 0x08015870
ITEM_ATTR2 = (0x080155be, 0x08015710)   # movs r0, #0x84 (<< 5 = attr2 0x1080: palette 1, tile 0x80)
ITEM_TILE = 0x1e0

# Two animated effects also put their pictures at 0x80 and up while a page is in the box: 0x45
# (the "Fugitive Data" header of the escaped convict's data screen in episode 4, 112 tiles from
# 0x90, started by the screen at 0x0802b011 with the last page still counted as up) and 0xdd (a
# figure in the dark, 219 tiles from 0x80, started by the script over a page in bank 21).  Their
# entries in the animation table (0x08046b30 + 20 * n, u32 VRAM destination at +4) move them
# out.  0xdd goes to 0x100-0x1da, between the page arrow and choice cursor (0xf8-0xff) and the
# shout bubbles (0x1e8 on, effects 1-9): its one scene (bank 21 section 0xb0, a flashback in
# episode 3's second trial) shows Godot's Objection! over it.  Until 0.16.67 it went to 0x1a0,
# into the bubble's tiles, and both came out as garbage for the second the bubble was up.  0x45
# goes to 0x310: on the data screen 0x19c-0x2a7 hold its two pages of text (vwf_data_text) and
# 0x302-0x309 the PICTURE tab, and no character is on screen there.  The other effects placed in
# the text tiles play with no page up (the episode select, the episode title cards, the bursts
# the original put over its own two lines at 0x00-0x7f).
ANIM_TABLE = 0x08046b30
MOVED_EFFECTS = {0x45: 0x310, 0xdd: 0x100}
# where 0xdd's tiles must stay: after the cursor (0xff), before the item shown in court (0x1e0,
# never up in that scene) and the bubbles (0x1e8)
DARK_FIGURE_RANGE = (0x100, 0x1e0)

def effect_tiles(rom, n):
    """The OBJ tiles effect n takes: the most any of its frames' sprite lists covers."""
    fd = rom.u32(ANIM_TABLE + 20 * n + 8)
    lists = {rom.u16(fd + 8 + 8 * i) for i in range(rom.u16(fd + 2))}
    def size(attr):
        w, h = dsimg_size[attr >> 12]
        return w * h // 64
    return max(sum(size(rom.u16(fd + o + 6 + 4 * k)) for k in range(rom.u16(fd + o))) for o in lists)

# The life bar (28 OBJ tiles, DMA'd every frame it is up) sits at 0xc4-0xdf, and moves to
# 0x84-0x9f while any of the eight map-marker records at 0x03003af0 is taken (commands 0x39-0x3d;
# 20 bytes each, +0 the marker, 0xff = free; +5 bit 2 hidden; +0x10 its VRAM, from 0xc0): the
# markers' pictures are at 0xc0 on.  A marker that is hidden (0x39 with bit 0 clear) keeps its
# record until a section jump other than to the next section, so in a testimony, whose sections
# follow one another, a map's markers from before it stay taken, and the bar stayed at 0x84 for
# the whole cross-examination, over the third line's sprite text (episode 3's second trial, after
# the restaurant's floor plan).  The three places that pick the bar's tiles (the copy at
# 0x0801d324, 0x0801d3ec, the sprites at 0x0801d868) now count a marker only while it is shown:
# with every marker hidden the bar keeps its own tiles, as with none.  A hidden marker shown again
# (0x39 with bit 0 set, at 0x080228ae, without copying its picture) gets its picture copied from
# the marker table again, since the bar may have been over it meanwhile.
BAR_MARKER_TESTS = (0x0801d33e, 0x0801d458, 0x0801d8be)   # ldrb r0, [r0]; cmp r0, #0xff (then beq)
MARKER_RESHOW = 0x080228ae          # movs r0, #0xfb; ldrb r1, [r5, #5]: a marker shown again
MARKER_TABLE = 0x08049c50           # 12 bytes a marker: u32 picture, u16 bytes, ...

# The item's box on BG1 (its frame drawn from map row 1, column 1, around the 64x64 picture at
# y 16) is where the original has it, rows 1-10: from 0.16.12 to 0.16.67 it and the picture were a
# row higher (rows 0-9, y 8; with its erase, the scene's inline clear at 0x0803616e and the last
# step of the closing animation at 0x08015560 moved with them), because the 64-pixel text box of
# those builds put the name tag on row 10.  The tag is on rows 12-13 again (src/vwf.c, BOX_TOP).

def apply(rom, ctx):
    d, arm9 = ctx.data, ctx.arm9
    assert rom.u32(ITEM_DMA_LIT) == 0x06011000
    rom.w32(ITEM_DMA_LIT, 0x06010000 + ITEM_TILE * 32)
    for a in ITEM_ATTR2:
        assert rom.u16(a) == 0x2084
        rom.w16(a, 0x2000 | ((0x1000 | ITEM_TILE) >> 5))
    for n, tile in MOVED_EFFECTS.items():
        e = ANIM_TABLE + 20 * n
        assert rom.u32(e + 4) in (0x06011000, 0x06011200), hex(n)
        rom.w32(e + 4, 0x06010000 + tile * 32)
    lo, hi = DARK_FIGURE_RANGE
    start, need = MOVED_EFFECTS[0xdd], effect_tiles(rom, 0xdd)
    if not (lo <= start and start + need <= hi):
        raise SystemExit(f'icons: effect 0xdd takes tiles {start:#x}-{start + need - 1:#x}, outside {lo:#x}-{hi - 1:#x}')
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

def apply_bar(rom):
    """The life bar's tiles and the map markers (see BAR_MARKER_TESTS).  Applied after every other
    patch, so that its code follows theirs in the free space and moves none of it (a savestate
    holds return addresses into that code)."""
    # a map marker counts only while shown (Z set: free or hidden)
    shown = rom.thumb_code('''
        push {r1}
        ldrb r1, [r0]
        cmp r1, #0xff
        beq done
        ldrb r1, [r0, #5]
        lsrs r1, r1, #3
        sbcs r0, r0
    done:
        pop {r1}
        bx lr
    ''', note='marker shown test')
    for site in BAR_MARKER_TESTS:
        assert rom.read(site, 4) == rom.asm_thumb(site, 'ldrb r0, [r0]\n cmp r0, #0xff'), hex(site)
        assert rom.u16(site + 4) & 0xff00 == 0xd000, hex(site)        # beq
        rom.thumb(site, f'bl #{shown & ~1:#x}', 'life bar: shown markers only')
    # a marker shown again: its picture again (as a new one gets it), then the replaced code
    assert rom.read(MARKER_RESHOW, 4) == rom.asm_thumb(MARKER_RESHOW, 'movs r0, #0xfb\n ldrb r1, [r5, #5]')
    reshow = rom.thumb_code(f'''
        push {{r2, r3, lr}}
        ldrb r0, [r5]
        lsls r1, r0, #1
        adds r1, r1, r0
        lsls r1, r1, #2
        ldr r0, [pc, #32]
        adds r1, r1, r0
        ldr r2, [pc, #32]
        ldr r0, [r1]
        str r0, [r2]
        ldr r0, [r5, #0x10]
        str r0, [r2, #4]
        ldrh r0, [r1, #4]
        lsrs r0, r0, #1
        movs r3, #1
        lsls r3, r3, #31
        orrs r0, r3
        str r0, [r2, #8]
        ldr r0, [r2, #8]
        movs r0, #0xfb
        ldrb r1, [r5, #5]
        pop {{r2, r3, pc}}
        .word {MARKER_TABLE:#x}
        .word 0x040000d4
    ''', note='marker shown again')
    rom.thumb(MARKER_RESHOW, f'bl #{reshow & ~1:#x}', 'marker shown again')


# The choice cursor (the white pointing hand, 16x16, 128 bytes) is a picture at 0x081fa2cc, inside
# the Japanese font, which the English build fills with its code (the 'font' region from
# 0x081f31cc): once that code passed 0x7100 bytes the cursor showed a scrap of it.
# The two routines that copy it to OBJ tile 0xfc (a menu's end, 0x08021a6c's pool, and the one at
# 0x0800dfd4's) get a copy of the original, kept after the code.
CURSOR_PICTURE = 0x081fa2cc
CURSOR_LITS = (0x0800dfd4, 0x08021a6c)

def keep_cursor(rom, ctx):
    """Applied last, after apply_bar, so that nothing before it moves."""
    pic = ctx.gba[CURSOR_PICTURE - 0x08000000: CURSOR_PICTURE - 0x08000000 + 0x80]
    addr = rom.store(pic, 'font', 4, 'choice cursor picture')
    for lit in CURSOR_LITS:
        assert rom.u32(lit) == CURSOR_PICTURE, hex(lit)
        rom.w32(lit, addr)


# Evidence presented shows its icon at the top middle of the screen (OAM 52), DMA'd to OBJ tiles
# 0x80-0xbf, the third line's, while the frame is drawn with the page still up: in that one frame
# the third line showed the icon's tiles as garbage (src/vwf.c, vwf_icon).  Both routines that
# load it (the Court Record's item, 0x08014690; a fixed picture, 0x08036b9c) call vwf_icon before
# they decompress it.  Applied last, so that nothing before it moves.
ICON_LOADS = (0x08014690, 0x08036b9c)   # bl 0x0803a048 (LZ to 0x0200afc0), then the DMA to 0x06011000
ICON_UNPACK = 0x0803a048

def present_icon(rom):
    from .text import call_hook
    for site in ICON_LOADS:
        if rom.read(site, 4) != rom.asm_thumb(site, f'bl #{ICON_UNPACK:#x}'):
            raise SystemExit(f'icons: unexpected code where the presented icon is unpacked ({site:#x})')
        call_hook(rom, site, rom.syms['vwf_icon'], f'bl #{ICON_UNPACK:#x}', 'present icon', keep=('r0', 'r1'))


# The Court Record's picture goes to OBJ tile 0x280, or with a large character on screen to 0x80,
# the third line's (graphics.md, text-engine.md "Where sprite text goes"): the DMA at 0x08014dda
# runs during the frame's update, and the third line moved out only the next frame, so for two
# frames it showed the picture's tiles (src/vwf.c, vwf_record_pic).  The DMA calls vwf_record_pic
# first.  Applied last (0.16.78), so that nothing before it moves.
RECORD_PIC_DMA = 0x08014dda                # str r5, [r2]; ldr r0, =0x06011000 (DMA source, dest)
RECORD_PIC_CODE = bytes.fromhex('15600b48')

def record_picture(rom):
    from .text import call_hook
    if rom.read(RECORD_PIC_DMA, 4) != RECORD_PIC_CODE or rom.u32(((RECORD_PIC_DMA + 2 + 4) & ~3) + 0x2c) != 0x06011000:
        raise SystemExit('icons: unexpected code where the Court Record picture is copied to 0x80')
    # the literal load is redone without its pool: 0x6011 << 12
    call_hook(rom, RECORD_PIC_DMA, rom.syms['vwf_record_pic'],
              'str r5, [r2]\n movs r0, #0x60\n lsls r0, r0, #8\n adds r0, #0x11\n lsls r0, r0, #12',
              'record picture', keep=('r1', 'r2', 'r3'))
