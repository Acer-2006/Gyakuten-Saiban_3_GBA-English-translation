"""Court Record: English names and descriptions for the evidence and profile panels.

GBA: a table of 211 entries at 0x08045f74, {u32 image, u32 icon | detail << 16}, indexed by item
id.  Each image is LZ77: a 160x64 4bpp picture (ten 32x32 sprite cells, 5 across and 2 down,
tiles row-major in each cell) with the name on top and the description below; palette indices
9 background, 15 name, 8 text, 0 for the transparent columns 152-159.

DS: the same item ids.  The arm9 has a table of 211 records of 24 bytes at 0x020a2368
({u16 icon, u16 name, u16 name, u16 info panel, u16 description, u16 detail, ...}; icon and
detail are the same numbers as the GBA's) and per-language base offsets into data.bin at
0x020a44c0 (8 words per language: Japanese, English, English).  English names are 128x16
textures (orange text, index 2), descriptions are 256x64 textures with three lines of dialogue-
font text.  The names are copied as pictures; the descriptions are read back to text (see
tools/dsimgtext.py) and set again in a small font so they fit the GBA panel.
"""
import os, re, struct, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
import lz, smallfont, dsimgtext, textgfx

# the "R" switch label under the panel: 64x16 (two 32x16 sprite cells), OBJ palette 4, white text
# (12) with a dark outline (10); copied to OBJ tile 0x1a8 when the Court Record opens
LABELS = {0x0818ad20: 'Profiles',      # shown on the evidence page (人物ファイル)
          0x0818af20: 'Evidence'}      # shown on the profile page (証拠品ファイル)

GBA_ITEMS = 0x08045f74
COUNT = 211
DS_ARM9 = 0x02000000
DS_ITEMS = 0x020a2368          # 211 x 24 bytes
DS_BASES = 0x020a44e0          # English: u32[8] offsets into data.bin
NAME_BASE, DESC_BASE = 4, 7    # ... of the name textures and the description textures

BG, TITLE, BODY, CLEAR = 9, 15, 8, 0
W, H, W_USE = 160, 64, 152     # columns 152..159 stay transparent, as in the originals
TEXT_X, TEXT_W = 3, 142        # keep the text clear of the right arrow, like the Japanese

def ds_items(arm9):
    o = DS_ITEMS - DS_ARM9
    return [struct.unpack_from('<12H', arm9, o + 24 * i) for i in range(COUNT)]

def adapt(text, has_detail):
    """DS wording -> GBA (details are opened with the L Button on the GBA)."""
    if has_detail:
        text = text.replace('Touch the Check Button', 'Press L')
    return text

# closed compounds that a line break may have split with a hyphen ("Some-" / "thing")
CLOSED = {'something', 'anything', 'everything', 'nothing', 'someone', 'anyone', 'everyone',
          'somebody', 'anybody', 'everybody', 'nobody', 'somewhere', 'anywhere', 'everywhere',
          'nowhere', 'sometimes', 'somehow', 'whatever', 'whenever', 'wherever', 'however',
          'without', 'within', 'into', 'onto', 'cannot', 'myself', 'yourself', 'himself', 'herself',
          'itself', 'ourselves', 'themselves', 'together', 'otherwise', 'meanwhile'}

def join_lines(lines):
    """The DS description lines -> one paragraph (the GBA panel wraps it again)."""
    out = ''
    for ln in lines:
        if not ln: continue
        if out.endswith('-') and ln[:1].islower():
            head = re.split(r'[ /]', out[:-1])[-1]
            tail = re.match(r"[A-Za-z]*", ln).group(0)
            out = (out[:-1] if (head + tail).lower() in CLOSED else out) + ln
        else:
            out = (out + ' ' + ln) if out else ln
    return out

def panel(name_px, text):
    """name_px: 16 rows of the DS name texture (text = index 2).  -> 64 rows x 160 indices, or
    None when the text does not fit."""
    img = [[BG] * W_USE + [CLEAR] * (W - W_USE) for _ in range(H)]
    xs = [x for x in range(len(name_px[0])) if any(row[x] == 2 for row in name_px)]
    if xs:
        dx = (W_USE - (xs[-1] - xs[0] + 1)) // 2 - xs[0]
        for y, row in enumerate(name_px):
            for x, v in enumerate(row):
                if v == 2 and 0 <= x + dx < W_USE: img[y][x + dx] = TITLE
    lines = smallfont.wrap(text, TEXT_W)
    n = len(lines)
    if n <= 3: tops = [17 + 16 * i for i in range(n)]
    elif n == 4: tops = [16 + 12 * i for i in range(n)]
    elif n == 5: tops = [15 + 10 * i for i in range(n)]
    else: return None
    for t, line in zip(tops, lines):
        smallfont.render(line, img, TEXT_X, t + 2, BODY)
    return img

def cells(img):
    """64x160 -> 5120 bytes: 32x32 cells 5 across, 2 down, each 4x4 tiles row-major, 4bpp."""
    out = bytearray()
    for cy in range(2):
        for cx in range(5):
            for ty in range(4):
                for tx in range(4):
                    for r in range(8):
                        row = img[cy * 32 + ty * 8 + r]
                        x0 = cx * 32 + tx * 8
                        for x in range(x0, x0 + 8, 2):
                            out.append((row[x] & 15) | ((row[x + 1] & 15) << 4))
    return bytes(out)

def apply(rom, ctx):
    d, arm9 = ctx.data, ctx.arm9
    recs = ds_items(arm9)
    # the DS and GBA item tables have to agree (icon and detail picture of every item)
    for i, r in enumerate(recs):
        aux = rom.u32(GBA_ITEMS + 8 * i + 4)
        if (aux & 0xffff, aux >> 16) != (r[0], r[5]):
            raise SystemExit(f'court record: item {i} differs between the GBA and DS tables')
    bases = struct.unpack_from('<8I', arm9, DS_BASES - DS_ARM9)
    nb, db = bases[NAME_BASE], bases[DESC_BASE]
    nsz, dsz = dsimgtext.texture_size(d, nb), dsimgtext.texture_size(d, db)
    reader = dsimgtext.TextReader(d, arm9)
    orig = [rom.u32(GBA_ITEMS + 8 * i) for i in range(COUNT)]
    texts, stored, new = {}, {}, {}
    unread = []
    for i, r in enumerate(recs):
        if r[4] not in texts:
            px, w, h, _ = dsimgtext.texture(d, db + r[4] * dsz)
            texts[r[4]] = reader.read_image(px, w, h)
        lines = texts[r[4]]
        if not lines: continue                  # unused item: the DS has no description either
        if any(l is None for l in lines):
            unread.append(i); continue
        name_px, _, _, _ = dsimgtext.texture(d, nb + r[1] * nsz)
        img = panel(name_px, adapt(join_lines(lines), r[5] != 0))
        if img is None:
            unread.append(i); continue
        data = lz.compress(cells(img))
        if data not in stored: stored[data] = rom.store(data, 'ext', 4, f'court record {i}')
        new[i] = stored[data]
    # unused items share the picture of a used one in the GBA ROM (item 0 mostly); keep that
    for i in range(COUNT):
        if i not in new:
            same = [k for k in new if orig[k] == orig[i]]
            if same: new[i] = new[same[0]]
    for i, addr in new.items():
        rom.w32(GBA_ITEMS + 8 * i, addr)
    print(f"  court record: {len(new)} of {COUNT} panels in English ({len(stored)} pictures)" +
          (f"; could not read the DS text of {unread}" if unread else ''))
    font = textgfx.Font.from_ctx(ctx)
    for addr, text in LABELS.items():
        grid = textgfx.render(font, text, 64, 16, fill=12, outline=10, align='left', y0=2)
        rom.write(addr, textgfx.sprite_cells(grid, 32, 16), 'court record label ' + text)
