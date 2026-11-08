"""Court Record: English names and descriptions for the evidence and profile panels.

GBA: a table of 211 entries at 0x08045f74, {u32 image, u32 icon | detail << 16}, indexed by item
id.  Each image is LZ77: a 160x64 4bpp picture (ten 32x32 sprite cells, 5 across and 2 down,
tiles row-major in each cell) with the name on top and the description below; palette indices
9 background, 15 name, 8 text, 0 for the transparent columns 152-159.  The English build's are
160x72 (since 0.16.80, tall_panels: 8 rows more, drawn on the panel's background).

DS: the same item ids.  The arm9 has a table of 211 records of 24 bytes at 0x020a2368
({u16 icon, u16 name, u16 name, u16 info panel, u16 description, u16 detail, ...}; icon and
detail are the same numbers as the GBA's) and per-language base offsets into data.bin at
0x020a44c0 (8 words per language: Japanese, English, English).  English names are 128x16
textures (orange text, index 2), descriptions are 256x64 textures with three lines of dialogue-
font text.  The names are copied as pictures; the descriptions are read back to text (see
tools/dsimgtext.py) and set again in the same font, the DS's letters with the DS's gaps halved, so
they fit the GBA panel (tools/dsdesc.py).
"""
import json, os, re, struct, sys
from collections import Counter
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
import lz, dsdesc, dsimgtext, textgfx

# the "R" switch label under the panel: 64x16 (two 32x16 sprite cells), OBJ palette 4, white text
# (12) with a dark outline (10); copied to OBJ tile 0x1a8 when the Court Record opens.  Drawn as
# the English GS1 draws its own (textgfx.label, 0.16.92: pixel for pixel GS1's), Evidence 53
# pixels wide and Profiles 45 (they were 60 and 52, the letters at the DS's advances)
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
TEXT_X, TEXT_W = 1, 149        # the text's ink in columns 1..149, as the Japanese
# the panel row of each line's top (glyph row 0; the capitals start a row lower, the tails of g and
# y end 13 rows lower): up to three lines 16 rows apart, centred on the Japanese lines; four lines
# 12 apart, from just under the name to the bottom of the panel
LINES = {1: (17,), 2: (17, 33), 3: (17, 33, 49), 4: (14, 26, 38, 50)}

# The age after a profile's name, as the Japanese GBA has it ("成歩堂 龍一（21）", "（故人）",
# "（？？）"), with the US DS's values: its info panels ("Age: 21", a small font of their own that
# the build does not have) read once by item id.  All 68 agree with the Japanese GBA's.
AGES = {0: '61', 1: '49', 2: '21', 3: '22', 4: '20', 16: '???', 17: '26', 18: 'deceased', 19: '19',
        20: '9', 21: '32', 22: '???', 23: '34', 24: '34', 25: '23', 26: '23', 27: '23', 28: '23',
        29: '25', 30: '25', 31: '48', 68: '24', 74: '23', 75: '28', 76: '28', 77: '28', 78: '68',
        79: '68', 80: '39', 81: '39', 82: '???', 83: '???', 84: '25', 85: '78', 86: '42', 126: '27',
        127: '20', 128: '25', 129: '19', 130: '23', 131: '26', 132: 'deceased', 133: 'deceased',
        145: '???', 146: '19', 147: '19', 148: '9', 149: '9', 150: '48', 151: '48', 152: '48',
        153: '???', 154: '???', 155: '49', 156: '25', 157: '25', 158: '25', 159: '25', 160: '25',
        161: '26', 162: '19', 163: '19', 164: '26', 165: '???', 166: '???', 167: 'deceased',
        194: 'deceased', 207: '25', 209: '25'}
# The DS names are pictures in a font of their own (1-pixel strokes, capitals and digits on rows
# 3-12, the x-height from row 6, a space of 8 columns), and the DS sets a name too long for its
# 128 columns in a narrower version of it (letters 1 column apart, 2 beside an i, a space of 4;
# "Franziska von Karma").  The build takes the letters it needs from DS names whose text it knows
# (the most common picture of each letter in them), and draws what the font does not have: the
# digits but 1 and 2, the brackets, and a narrow w.  (first row, rows)
NAME_TEXTS = {7: 'Crime Photo 1', 8: 'Crime Photo 2', 166: '??????', 126: 'Diego Armando',
              78: 'Victor Kudo', 129: 'Melissa Foster', 4: 'Dahlia Hawthorne'}
NARROW_TEXTS = {6: "Doug's Autopsy Report", 34: 'Treasure Exhibit Poster', 35: "Ami Fey's Golden Statue",
                48: 'Security Camera Photo', 55: 'CEO Office Key Card', 60: "Kane's Autopsy Report",
                97: "Jean's Loan Contract", 100: "Glen's Autopsy Report", 104: 'Trés Bien Floor Plans',
                110: "Gumshoe's Lunchbox", 123: 'Aromatherapy Bottle', 162: 'Franziska von Karma',
                171: 'Hazakura Temple Map', 183: "Elise's Autopsy Report"}
DRAWN = {
    '0': (3, ['..###..', '.#...#.', '#.....#', '#.....#', '#.....#', '#.....#', '#.....#', '#.....#', '.#...#.', '..###..']),
    '3': (3, ['..###..', '.#...#.', '#.....#', '......#', '....##.', '......#', '......#', '#.....#', '.#...#.', '..###..']),
    '4': (3, ['....#..', '...##..', '..#.#..', '..#.#..', '.#..#..', '#...#..', '#######', '....#..', '....#..', '....#..']),
    '5': (3, ['#######', '#......', '#......', '#.###..', '##...#.', '......#', '......#', '#.....#', '.#...#.', '..###..']),
    '6': (3, ['..###..', '.#...#.', '#......', '#......', '#.###..', '##...#.', '#.....#', '#.....#', '.#...#.', '..###..']),
    '7': (3, ['#######', '#.....#', '.....#.', '.....#.', '....#..', '....#..', '...#...', '...#...', '...#...', '...#...']),
    '8': (3, ['..###..', '.#...#.', '#.....#', '.#...#.', '..###..', '.#...#.', '#.....#', '#.....#', '.#...#.', '..###..']),
    '9': (3, ['..###..', '.#...#.', '#.....#', '#.....#', '.#...##', '..###.#', '......#', '......#', '.#...#.', '..###..']),
    '(': (2, ['..#', '.#.', '.#.', '#..', '#..', '#..', '#..', '#..', '#..', '.#.', '.#.', '..#']),
    ')': (2, ['#..', '.#.', '.#.', '..#', '..#', '..#', '..#', '..#', '..#', '.#.', '.#.', '#..']),
}
NARROW_DRAWN = {
    'w': (6, ['#..##..#', '#..##..#', '#..##..#', '#.#..#.#', '#.#..#.#', '.#....#.', '.#....#.']),
}
# names whose age does not fit after them at the normal width: the name and the age are set again
# in the narrow letters, as the DS sets its long names ("Dahlia Hawthorne (deceased)")
LONG_NAMES = {132: 'Dahlia Hawthorne', 133: 'Dahlia Hawthorne', 167: 'Dahlia Hawthorne'}

def drawn(table):
    return {ch: tuple(sum(1 << (top + y) for y in range(len(rows)) if rows[y][x] == '#') for x in range(len(rows[0])))
            for ch, (top, rows) in table.items()}

def ink_runs(px):
    """The ink (index 2) of a DS name picture as runs of column masks, one per letter."""
    cols = [sum(1 << y for y, row in enumerate(px) if row[x] == 2) for x in range(len(px[0]))]
    out, cur = [], []
    for m in cols + [0]:
        if m: cur.append(m)
        elif cur: out.append(tuple(cur)); cur = []
    return out

def letters_of(name_px_of, texts):
    """{char: column masks}: each letter's most common picture in the DS names `texts` (item: text)."""
    seen = {}
    for i, text in texts.items():
        runs, chars = ink_runs(name_px_of(i)), [c for c in text if c != ' ']
        if len(runs) != len(chars):
            raise SystemExit(f'court record: the DS name of item {i} is not "{text}"')
        for ch, run in zip(chars, runs): seen.setdefault(ch, Counter())[run] += 1
    return {ch: c.most_common(1)[0][0] for ch, c in seen.items()}

class NameFont:
    """The DS name font's letters (normal and narrow), with the drawn ones."""
    def __init__(self, name_px_of):
        self.normal = {**drawn(DRAWN), **letters_of(name_px_of, NAME_TEXTS)}
        self.narrow = {**drawn(DRAWN), **letters_of(name_px_of, NARROW_TEXTS), **drawn(NARROW_DRAWN)}

    def age(self, age, space, gap):
        """' (age)' as column masks: `space` blank columns, then the bracketed age, its letters `gap`
        apart (1 inside the brackets)."""
        text = '(' + age + ')'
        out = [0] * space
        for k, ch in enumerate(text):
            if k: out += [0] * (1 if ch == ')' or text[k - 1] == '(' else gap)
            out += self.normal[ch]
        return out

    def narrow_line(self, text):
        """text in the narrow letters, spaced as the DS spaces them."""
        out, prev = [], None
        for ch in text:
            if ch == ' ': prev = ' '; continue
            if prev is not None:
                out += [0] * (4 if prev == ' ' else 2 if 'i' in (prev, ch) else 1)
            out += self.narrow[ch]; prev = ch
        return out

# (space, gap) for the age, widest first: the space before the bracket narrows to 4, then the
# letters go 1 apart, and only then the space goes down to 3
AGE_SPACING = ((6, 2), (5, 2), (4, 2), (5, 1), (4, 1), (3, 2), (3, 1))

def name_columns(name_px, age=None, font=None, long_name=None):
    """The DS name's ink (index 2) as column masks, and the age after it at the widest spacing that
    fits the panel (AGE_SPACING), or the name and the age in the narrow letters (long_name: the
    name's text); None if neither fits."""
    xs = [x for x in range(len(name_px[0])) if any(row[x] == 2 for row in name_px)]
    if not xs: return []
    cols = [sum(1 << y for y, row in enumerate(name_px) if row[x] == 2) for x in range(xs[0], xs[-1] + 1)]
    if age is None: return cols
    for space, gap in AGE_SPACING:
        out = cols + font.age(age, space, gap)
        if len(out) <= W_USE: return out
    if long_name:
        out = font.narrow_line(f'{long_name} ({age})')
        if len(out) <= W_USE: return out
    return None

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

# how far the name line may move from the centre (columns), nearest first, when its letters would
# touch the description's (the tail of a y on the top of a capital below it): 22 panels move, 20
# of them by 1 or 2 columns, "Kane's Autopsy Report" by 7 and "Magazine Clipping" by 10 (its g's)
NUDGES = (0,) + tuple(d for k in range(1, 13) for d in (-k, k))

def touching(img):
    """True if a pixel of the name is on or next to (8 ways) a pixel of the description."""
    for y in range(H):
        for x in range(W):
            if img[y][x] != TITLE: continue
            for yy in range(max(0, y - 1), min(H, y + 2)):
                for xx in range(max(0, x - 1), min(W, x + 2)):
                    if img[yy][xx] == BODY: return True
    return False

def name_offset(img):
    """How many columns the name line is right of the centre."""
    xs = [x for x in range(W_USE) if any(img[y][x] == TITLE for y in range(16))]
    return xs[0] - (W_USE - (xs[-1] - xs[0] + 1)) // 2 if xs else 0

def panel(name_px, text, font, age=None, names=None, long_name=None, nudge=False, clear=False, first=(),
          steps=(0, 1)):
    """name_px: 16 rows of the DS name texture (text = index 2); age: the profile's age, put after
    the name in the NameFont `names` (long_name: see name_columns).  The description's lines are
    chosen against the name line, centred.  nudge: the lines are the ones chosen against the name
    alone (as before the ages), and the name line (with the age) moves off the centre (NUDGES)
    until no letter of it touches them; only if that cannot be done are the lines chosen again
    for each place of the name line.  clear: lines that touch each other are chosen again
    (dsdesc.choose_clear).  first: the lines the description begins with (BREAKS); steps: the
    rows a gap between lines may change by there (LINE_STEPS).  -> (64 rows x 160 indices, the
    word gap narrowing), or (None, None) when the text (or the name with the age) does not fit."""
    cols = name_columns(name_px, age, names, long_name)
    if cols is None: return None, None
    def ink(line, dx):
        x0 = (W_USE - len(line)) // 2 + dx
        if x0 < 0 or x0 + len(line) > W_USE: return None
        img = [[BG] * W_USE + [CLEAR] * (W - W_USE) for _ in range(H)]
        for x, m in enumerate(line):
            for y in range(16):
                if m >> y & 1: img[y][x0 + x] = TITLE
        return img
    def lay(img):
        nm = [sum(1 << y for y in range(H) if img[y][x] == TITLE) for x in range(W)]
        if clear:
            return dsdesc.choose_clear(font, text, TEXT_W, nm, TEXT_X, LINES, H - 1, first, steps)
        return dsdesc.choose(font, text, TEXT_W, nm, TEXT_X, LINES, first) + (None,)
    def draw(dx, layout=None):
        img = ink(cols, dx)
        if img is None: return None
        lines, tops, cut, shifts = layout or lay(img)
        if lines is None: return None
        for k, (line, top) in enumerate(zip(lines, tops)):
            for x, m in enumerate(font.masks(line, TEXT_X + (shifts[k] if shifts else 0), W_USE, cut)):
                for k in range(16):
                    if m >> k & 1 and 0 <= top + k < H: img[top + k][x] = BODY
        return img, cut
    if not nudge:
        return draw(0) or (None, None)
    base = lay(ink(name_columns(name_px), 0))
    for layout in (base, None):
        if layout is not None and layout[0] is None: continue
        for dx in NUDGES:
            drawn = draw(dx, layout)
            if drawn and not touching(drawn[0]): return drawn
    return draw(0, base if base[0] is not None else None) or (None, None)

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
    font = dsdesc.Font(d, arm9)
    orig = [rom.u32(GBA_ITEMS + 8 * i) for i in range(COUNT)]
    texts, stored, new = {}, {}, {}
    unread, tight = [], []
    inputs = ctx.court_inputs = {}             # for add_ages: every item's name picture and text
    for i, r in enumerate(recs):
        if r[4] not in texts:
            px, w, h, _ = dsimgtext.texture(d, db + r[4] * dsz)
            texts[r[4]] = reader.read_image(px, w, h)
        lines = texts[r[4]]
        if not lines: continue                  # unused item: the DS has no description either
        if any(l is None for l in lines):
            unread.append(i); continue
        name_px, _, _, _ = dsimgtext.texture(d, nb + r[1] * nsz)
        text = adapt(join_lines(lines), r[5] != 0)
        img, cut = panel(name_px, text, font)
        if img is None:
            unread.append(i); continue
        inputs[i] = (name_px, text)
        if cut: tight.append(i)
        data = lz.compress(cells(img))
        if data not in stored: stored[data] = rom.store(data, 'ext', 4, f'court record {i}')
        new[i] = stored[data]
    # unused items share the picture of a used one in the GBA ROM (item 0 mostly); keep that
    shared = ctx.court_shared = {}             # for tall_panels: unused item -> the item it shares
    for i in range(COUNT):
        if i not in new:
            same = [k for k in new if orig[k] == orig[i]]
            if same: new[i] = new[same[0]]; shared[i] = shared.get(same[0], same[0])
    for i, addr in new.items():
        rom.w32(GBA_ITEMS + 8 * i, addr)
    print(f"  court record: {len(new)} of {COUNT} panels in English ({len(stored)} pictures)" +
          (f", narrower word gaps in {tight}" if tight else '') +
          (f"; could not read the DS text of {unread}" if unread else ''))
    font = textgfx.Font.from_ctx(ctx)
    for addr, text in LABELS.items():
        grid = textgfx.label(font, text, 64)    # as the English GS1 draws them (0.16.92)
        rom.write(addr, textgfx.sprite_cells(grid, 32, 16), 'court record label ' + text)

def add_ages(rom, ctx):
    """The panels made again in the last step of the build: the profiles with the age after the
    name (AGES, 0.16.63), and every panel whose name touches its description.  In both the name
    line moves off the centre until no letter of it touches the description (NUDGES, 0.16.65),
    which keeps the lines chosen against the name alone, as before the ages.  Applied last so that
    the pictures stored before them, and everything after them in the ROM, keep their addresses:
    the panels made by apply() stay where they are, unused."""
    d, arm9 = ctx.data, ctx.arm9
    font = dsdesc.Font(d, arm9)
    recs = ds_items(arm9)
    nb = struct.unpack_from('<8I', arm9, DS_BASES - DS_ARM9)[NAME_BASE]
    nsz = dsimgtext.texture_size(d, nb)
    names = NameFont(lambda i: dsimgtext.texture(d, nb + recs[i][1] * nsz)[0])
    stored, ages, moved, still, wide, narrow = {}, 0, [], [], [], []
    for i, (name_px, text) in sorted(ctx.court_inputs.items()):
        if i in AGES:
            centred, _ = panel(name_px, text, font, AGES[i], names, LONG_NAMES.get(i))
            img, cut = panel(name_px, text, font, AGES[i], names, LONG_NAMES.get(i), nudge=True)
            if img is None:
                wide.append(i); continue
            if i in LONG_NAMES: narrow.append(i)
            ages += 1
        else:
            centred, _ = panel(name_px, text, font)
            if centred is None or not touching(centred): continue
            img, cut = panel(name_px, text, font, nudge=True)
        off = name_offset(img)
        if off: moved.append((i, off))
        if touching(img): still.append(i)
        data = lz.compress(cells(img))
        if data not in stored: stored[data] = rom.store(data, 'ext', 4, f'court record {i} (age, name line)')
        rom.w32(GBA_ITEMS + 8 * i, stored[data])
    print(f"  court record: ages after {ages} of {sum(1 for i in ctx.court_inputs if i in AGES)} profile names" +
          (f", in the narrow letters for {narrow}" if narrow else '') +
          (f"; no room for the age of {wide}" if wide else '') +
          f"; name line moved (item, columns) {moved} ({len(stored)} pictures)" +
          (f"; still touching: {still}" if still else ''))

# Descriptions set with the DS's 2-pixel gap between letters whose straight sides face each other
# (dsdesc.Font(stem_gap)), where 1 pixel made them read as one stroke: Pearl Fey's first profile,
# the g and l of "amazingly" (0.16.74).  Only there: the others are left as they are.
STEM_GAPS = {20}

# Descriptions whose lines are given, where the lines the build chose split what reads as one
# phrase: the profile named "??????" (item 166) had "Morgan Fey's / daughter and Iris's twin /
# sister." (0.16.75).  The lines are set the same way as the others (clear_lines), only their
# breaks are these, and a gap between two of them may also be a row narrower (where nothing of the
# line above goes below the baseline) or two rows wider (LINE_STEPS): with the tail of the g of
# "Morgan" over the I of "Iris's", item 166 has its lines 14, 11 and 11 rows apart.
BREAKS = {166: ("Morgan Fey's daughter", "and Iris's twin sister.", "Her father deals")}
# Descriptions whose lines are spaced with LINE_STEPS too, their breaks chosen as for the others:
# the second Key Card (item 54), whose p of "Opens" touched the E of "CEO's" in every layout with
# gaps of 12 or 13 rows, has its lines 12, 14 and 12 rows apart (0.16.76).
SPACED = {54}
LINE_STEPS = (0, 1, -1, 2)
# the panels set again after the others in clear_lines, in the order they came (0.16.74: 20,
# 0.16.75: 166, 0.16.76: 54); new ones go at the end
LATE = (20, 166, 54)

def final_panel(i, name_px, text, font, names, clear=False, first=(), steps=(0, 1)):
    """The panel apply() and add_ages() leave for item i (clear, first, steps: see panel)."""
    kw = dict(clear=clear, first=first, steps=steps)
    if i in AGES:
        img, _ = panel(name_px, text, font, AGES[i], names, LONG_NAMES.get(i), nudge=True, **kw)
        if img is not None: return img
    img, _ = panel(name_px, text, font, **kw)
    if img is not None and i not in AGES and touching(img):
        img, _ = panel(name_px, text, font, nudge=True, **kw)
    return img

def clear_lines(rom, ctx):
    """Applied last (0.16.73): no two lines of a description touching, where that can be had.  A
    description of four lines has them 12 rows apart (LINES), less than the 13 rows the letters
    take, and in 33 of the 188 the tail of a g, p, y or comma on one line touched a letter of the
    next (the lines are chosen to avoid that, dsdesc.cost, but not every text can).  Those are
    set again (dsdesc.choose_clear): other line breaks, a line spacing of 13 instead of 12 (the
    first line a row higher, or a gap a row wider), word gaps a pixel narrower or a line moved a
    pixel or two sideways, whichever costs least; one (54) has no such layout.  Then, after them
    (LATE), the descriptions in STEM_GAPS are set with the wider gap between straight sides (since
    0.16.74), those in BREAKS with the lines given there (since 0.16.75) and those in BREAKS and
    SPACED with more ways to space the lines (LINE_STEPS; 54, since 0.16.76).  Applied last, like
    add_ages(), so that the pictures stored before stay where they are; the other panels are left
    alone."""
    d, arm9 = ctx.data, ctx.arm9
    font = dsdesc.Font(d, arm9)
    stems = dsdesc.Font(d, arm9, stem_gap=True)
    recs = ds_items(arm9)
    nb = struct.unpack_from('<8I', arm9, DS_BASES - DS_ARM9)[NAME_BASE]
    nsz = dsimgtext.texture_size(d, nb)
    names = NameFont(lambda i: dsimgtext.texture(d, nb + recs[i][1] * nsz)[0])
    stored, changed, still = {}, [], []
    for i, (name_px, text) in sorted(ctx.court_inputs.items()):
        before = final_panel(i, name_px, text, font, names)
        after = final_panel(i, name_px, text, font, names, clear=True)
        if after is None or after == before: continue
        data = lz.compress(cells(after))
        if data not in stored: stored[data] = rom.store(data, 'ext', 4, f'court record {i} (clear lines)')
        rom.w32(GBA_ITEMS + 8 * i, stored[data])
        changed.append(i)
        if touching(after): still.append(i)
    # after the others, in the order they came (LATE), so that the pictures above keep the
    # addresses they had before (the picture of these there stays in its place, unused)
    if set(LATE) != STEM_GAPS | set(BREAKS) | SPACED or len(set(LATE)) != len(LATE):
        raise SystemExit('court record: LATE has to list STEM_GAPS, BREAKS and SPACED once each')
    for i in LATE:
        name_px, text = ctx.court_inputs[i]
        after = final_panel(i, name_px, text, stems if i in STEM_GAPS else font, names, clear=True,
                            first=BREAKS.get(i, ()),
                            steps=LINE_STEPS if i in BREAKS or i in SPACED else (0, 1))
        if after is None: raise SystemExit(f'court record: item {i} does not fit')
        why = 'straight sides' if i in STEM_GAPS else 'line breaks' if i in BREAKS else 'line spacing'
        rom.w32(GBA_ITEMS + 8 * i, rom.store(lz.compress(cells(after)), 'ext', 4, f'court record {i} ({why})'))
    print(f"  court record: the lines of {changed} set again so that fewer letters touch ({len(stored)} pictures)" +
          (f"; name touching: {still}" if still else ''))

# The panels on 160x72 pictures (0.16.80, as in the maintainer's English GS1): no pixel of a line
# touching one of the line above or below it, the name line included, with the DS's line breaks.
# The Japanese picture is 160x64, drawn as sprites at y 24-87, and the DS's letters reach from
# row 0 of their cell (quotes, brackets) to row 13 (the tails of g, j, p, q, y and the comma), so
# with the name four lines fitted only 12 rows apart, and at that spacing letters met (0.16.73-
# 0.16.76 chose other line breaks, spacings and word gaps around that).  The panel's red runs
# down to y 92, under the picture's last row: the picture grows to 72 rows, its rows 0-68 red and
# 69-71 the panel's bottom border (BORDER_TILE's last three rows), and four lines go 14 rows apart
# (dsdesc.choose_tall).  Since 0.16.91 the name line is NAME_RAISE rows higher than the DS's name
# picture has it (its capitals on rows 1-10, the brackets on 0-11; as high as the maintainer's
# English GS1 has its names) and every description starts on the same row under it, whatever its
# number of lines (dsdesc.TALL_TOPS): the same space between the name and the text in every
# panel.  The first 160 tiles are the picture's rows 0-63 as before (the ten
# sprites); the 20 after them are its rows 64-71, of which the first 19 (the transparent columns
# 152-159 are the panel's corner tile) are drawn on the panel itself, BG2 row 11, where the panel's
# map has BORDER_TILE: no sprite memory is free for them whenever the Record shows, and the
# background has its slide copy there already.  The loader (LOADER_DMA) copies them to one of two
# sets of BG tiles in char block 0 (STRIP_SETS, which nothing else uses), the other one each time,
# and the scroll that brings the panel's columns in (FEEDS) takes them from a copy of the panel's
# map (SLIDE_MAP) whose row 11 has the set of the item last loaded: the item sliding out keeps
# its strip, in the set it had, until it is gone.
TALL_H, RED_LAST = 72, 68
NAME_RAISE = 2                 # rows the name line goes up from where the DS's name picture has it
UI_SHEET = 0x08180820          # BG tile sheet in char block 0 (256 tiles)
BORDER_TILE = 0x4c             # under the description: 5 red rows, then the border (a, b, 1)
SLIDE_MAP = 0x0803bc44         # the panel's BG2 map (32x12), read only by the scroll at 0x080061bc
STRIP_ROW, STRIP_COL, STRIP_TILES = 11, 11, 19
STRIP_SETS = (0x194, 0x1a7)    # BG tiles of the two strip sets (char block 0)
STRIP_STATE = 0x02029c00       # u8: the set of the item last loaded
UNPACK = 0x0200afc0            # where the loader unpacks the picture
LOADER_DMA = 0x08014e40        # ldr r0, [r1, #8]; pop {r4, r5}: after the 0x1400-byte DMA to 0x06013c00
FEEDS = {0x08006298: ('r4', 'mov r1, ip'),     # ldr r4, =SLIDE_MAP; mov r1, ip (right edge)
         0x080062cc: ('r2', 'mov sl, r2')}     # ldr r2, =SLIDE_MAP; mov sl, r2 (left edge)
SLIDE_MAP_POOL = 0x08006348

def border_rows(rom):
    """BORDER_TILE's rows (each one colour), checked against what the pictures assume."""
    b = rom.read(UI_SHEET + 32 * BORDER_TILE, 32)
    t = [[b[y * 4 + x // 2] >> 4 * (x & 1) & 15 for x in range(8)] for y in range(8)]
    if any(len(set(row)) != 1 for row in t) or any(row[0] != BG for row in t[:5]):
        raise SystemExit('court record: unexpected panel border tile')
    return [row[0] for row in t]

def tall_picture(name_cols, dx, lines, tops, font, cut, border):
    """160x72 indices: the name line `dx` columns off the centre, the lines at `tops`."""
    img = [[border[y - 64] if y >= 64 else BG] * W_USE + [CLEAR] * (W - W_USE) for y in range(TALL_H)]
    x0 = (W_USE - len(name_cols)) // 2 + dx
    for x, m in enumerate(name_cols):
        for y in range(16):
            if m >> y & 1: img[y][x0 + x] = TITLE
    for line, top in zip(lines, tops):
        for x, m in enumerate(font.masks(line, TEXT_X, W_USE, cut)):
            for k in range(16):
                if m >> k & 1: img[top + k][x] = BODY
    return img

def tall_tiles(img):
    """The picture's tiles: rows 0-63 as cells() (160 tiles), then rows 64-71 left to right (20)."""
    out = bytearray(cells(img))
    for tx in range(W // 8):
        for r in range(8):
            row = img[64 + r]
            for x in range(tx * 8, tx * 8 + 8, 2):
                out.append((row[x] & 15) | ((row[x + 1] & 15) << 4))
    return bytes(out)

def tall_layouts(ctx, font, stems, names):
    """{item: (name columns, dx, lines, tops, word cut, font)} for every description."""
    out, bad = {}, []
    for i, (name_px, text) in sorted(ctx.court_inputs.items()):
        cols = name_columns(name_px, AGES[i], names, LONG_NAMES.get(i)) if i in AGES else None
        if cols is None: cols = name_columns(name_px)
        if any(m & ((1 << NAME_RAISE) - 1) for m in cols):
            raise SystemExit(f'court record: the name of item {i} has ink in its top {NAME_RAISE} rows')
        cols = [m >> NAME_RAISE for m in cols]
        places = []
        for dx in NUDGES:
            x0 = (W_USE - len(cols)) // 2 + dx
            if 0 <= x0 and x0 + len(cols) <= W_USE:
                m = [0] * W
                m[x0:x0 + len(cols)] = cols
                places.append((dx, m))
        f = stems if i in STEM_GAPS else font
        found = dsdesc.choose_tall(f, text, TEXT_W, TEXT_X, W, places, RED_LAST, BREAKS.get(i, ()))
        if found is None: bad.append(i); continue
        lines, tops, cut, dx = found
        out[i] = (cols, dx, lines, tops, cut, f)
    if bad: raise SystemExit(f'court record: no layout without touching letters for {bad}')
    return out

def tall_panels(rom, ctx):
    """Applied last (0.16.80): every panel again on a 160x72 picture (see above), the loader and
    the scroll taught about the strip.  The pictures stored before stay where they are, unused."""
    d, arm9 = ctx.data, ctx.arm9
    font = dsdesc.Font(d, arm9)
    stems = dsdesc.Font(d, arm9, stem_gap=True)
    recs = ds_items(arm9)
    nb = struct.unpack_from('<8I', arm9, DS_BASES - DS_ARM9)[NAME_BASE]
    nsz = dsimgtext.texture_size(d, nb)
    names = NameFont(lambda i: dsimgtext.texture(d, nb + recs[i][1] * nsz)[0])
    border = border_rows(rom)
    layouts = ctx.court_layouts = tall_layouts(ctx, font, stems, names)
    stored, addr = {}, {}
    for i, (cols, dx, lines, tops, cut, f) in layouts.items():
        data = lz.compress(tall_tiles(tall_picture(cols, dx, lines, tops, f, cut, border)))
        if data not in stored: stored[data] = rom.store(data, 'ext', 4, f'court record {i} (160x72)')
        addr[i] = stored[data]
    for i, k in ctx.court_shared.items(): addr[i] = addr[k]
    if sorted(addr) != list(range(COUNT)): raise SystemExit('court record: items without a 160x72 picture')
    for i, a in addr.items(): rom.w32(GBA_ITEMS + 8 * i, a)
    # the panel's map with row 11 on each strip set
    if rom.u32(SLIDE_MAP_POOL) != SLIDE_MAP: raise SystemExit('court record: unexpected panel scroll')
    base = rom.read(SLIDE_MAP, 32 * 12 * 2)
    maps = []
    for first in STRIP_SETS:
        m = bytearray(base)
        for k in range(STRIP_TILES):
            o = 2 * (STRIP_ROW * 32 + STRIP_COL + k)
            if struct.unpack_from('<H', m, o)[0] != BORDER_TILE: raise SystemExit('court record: unexpected panel map')
            struct.pack_into('<H', m, o, first + k)
        maps.append(rom.store(bytes(m), 'ext', 4, f'court record panel map, strip at {first:#x}'))
    # the loader: the strip to the other set (the sprites' DMA has run), then what was replaced
    if rom.read(LOADER_DMA, 4) != rom.asm_thumb(LOADER_DMA, 'ldr r0, [r1, #8]\n pop {r4, r5}'):
        raise SystemExit('court record: unexpected code after the description DMA')
    strip = rom.thumb_code(f'''
        ldr r0, [r1, #8]
        ldr r3, state
        ldrb r2, [r3]
        movs r0, #1
        eors r2, r0
        strb r2, [r3]
        ldr r0, set_a
        cmp r2, #0
        beq have
        ldr r0, set_b
    have:
        ldr r2, src
        str r2, [r1]
        str r0, [r1, #4]
        ldr r2, ctrl
        str r2, [r1, #8]
        ldr r2, [r1, #8]
        pop {{r4, r5}}
        bx lr
        .align 2
    state: .word {STRIP_STATE:#x}
    set_a: .word {0x06000000 + 32 * STRIP_SETS[0]:#x}
    set_b: .word {0x06000000 + 32 * STRIP_SETS[1]:#x}
    src: .word {UNPACK + 160 * 32:#x}
    ctrl: .word {0x84000000 | STRIP_TILES * 8:#x}
    ''', note='court record strip')
    rom.hook_bl(LOADER_DMA, strip, 'court record strip')
    # the scroll: the map of the set last loaded
    for site, (reg, rest) in FEEDS.items():
        if rom.read(site, 4) != rom.asm_thumb(site, f'ldr {reg}, [pc, #{SLIDE_MAP_POOL - ((site + 4) & ~3):#x}]\n {rest}'):
            raise SystemExit(f'court record: unexpected code in the panel scroll at {site:#x}')
        feed = rom.thumb_code(f'''
            ldr {reg}, state
            ldrb {reg}, [{reg}]
            cmp {reg}, #0
            ldr {reg}, map_a
            beq have
            ldr {reg}, map_b
        have:
            {rest}
            bx lr
            .align 2
        state: .word {STRIP_STATE:#x}
        map_a: .word {maps[0]:#x}
        map_b: .word {maps[1]:#x}
        ''', note='court record panel map')
        rom.hook_bl(site, feed, 'court record panel map')
    # what each picture has where, for hacking/tools/gs3_record_audit.py
    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'build', 'court_record.json')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w') as fh:
        json.dump({'pictures': {i: addr[i] for i in sorted(addr)},
                   'layouts': {i: {'name_dx': l[1], 'lines': l[2], 'tops': l[3], 'word_cut': l[4],
                                   'stem_gap': l[5] is stems, 'age': AGES.get(i)}
                               for i, l in layouts.items()}}, fh, indent=1)
    four = [i for i, l in layouts.items() if len(l[2]) == 4]
    moved = [i for i, l in layouts.items() if len(l[2]) == 4 and l[3] != dsdesc.TALL_TOPS[4]]
    print(f"  court record: {len(layouts)} descriptions on 160x72 pictures ({len(stored)}), "
          f"{len(four)} in four lines ({len(moved)} spaced otherwise), "
          f"narrower word gaps in {[i for i, l in layouts.items() if l[4]]}")


# When the Record's panel slides in from the left (LEFT; in the free-slot text mode a choice puts
# the engine in, TXT+0x1c bit 2), the game swaps the OAM shadow entries of the panel's top-row
# cells 1-4 (36-39) with four of the dialogue's sprite-text entries (0x08014ee6-0x08014f82: r7+2,
# r7+3, r7+18 and r7+19, r7 worked out from the panel's position over the Japanese question's
# characters, 14 pixels apart), so that the panel comes before the characters it slides over in
# OAM and the hardware draws it over them.  The English question is not sprite text (it is on
# the canvas, BG0: src/vwf.c), and those entries are the options' cells, which src/vwf.c writes
# again every frame before OAM is copied: two of the incoming panel's cells were lost each frame
# for about eight frames of every LEFT slide in a choice, and the panel's copy behind them (the
# outgoing item's text, on BG2) showed through ("Irise's Autopsymony").  Since 0.17.00 the swap
# is skipped: the branch past it taken always.  The options sit under the panel's top row at
# most for two rows of a one-line question's first option (y 54-55).
SWAP_TEST = 0x08014ef0          # beq 0x08014f84 (TXT+0x1c bit 2 clear: no swap)

def no_panel_swap(rom):
    if rom.u16(SWAP_TEST) != 0xd048:
        raise SystemExit("court_record: the panel's OAM swap is not where it was")
    rom.w16(SWAP_TEST, 0xe048)     # b 0x08014f84


# An item's detail view (L in the Court Record) is a step routine of its own (0x08013a14, steps
# 0-10).  Two kinds of item copy pictures to the first OBJ tiles: the Hanging Scroll covered in
# gravy (item 173, detail 0x1c, R Swap above B L Back; ui.py, SWAP) its Swap prompt to tiles
# 0x00-0x07 and the button icon sheet to 0x08-0x17 (step 1, 0x08013e9a: two 16-bit DMAs, done
# again each time R swaps the scrolls, step 6 to step 1), and items 202 and 203 (detail 0x21 and
# 0x22) a mark to tile 0x00 (the end of step 0, 0x08013dfc).  In the original those tiles hold the
# page's first characters (16x16 sprites, four tiles each), which the game draws again from its
# sprite records as the view closes (step 10, 0x08014464: 0x08020024).  In the English build they
# are the first three 32x16 cells of the page's first line (src/vwf.c), which the records do not
# hold: up to 0.17.01 the Swap prompt and the icons took the place of the line's first words
# ("The painting is obscured by..." in Bikini's Psyche-Lock), and the map's mark left a dot before
# them, under the Court Record and after it had closed, until the page was over.  Since 0.17.02
# the tiles are kept as the view opens, at the end of step 0 (its call to the B / L / Back row's
# placement, 0x08015170, which comes once a view and before both copies), and put back as it
# closes, after the game's own redraw (DETAIL_FLAG holds DETAIL_MAGIC while DETAIL_KEEP holds
# them; anything else there, as from a save state made with an earlier build during the view,
# puts nothing back).  Step 0 also hides OAM entries 0-31, the original's sprite text, for the
# view; the English renderer writes a choice's options into its entries every frame, so up to
# 0.17.01 they were drawn over the picture at a choice.  Since 0.17.02 the view opening also calls
# vwf_overlay, as the save screen does, which keeps the page's sprite text hidden until
# vwf_restore, which the view's closing already calls (RESTORE_CALLS).
# The kept tiles are in the chapter bank's buffer, which the English build's banks do not use
# (memory-map.md), after BOX_EDGES (0x0202a800-0x0202a877).  In 0.17.02 they were at
# 0x0202b000-0x0202b303, over the original's own scratch buffer at 0x0202b1c0, where the
# background loader (0x08003ccc, case 0x08003ea8: SYS+0x258 2, 3 or 7) unpacks a picture before
# copying it to VRAM; the view's closing reloads the scene's background through that loader (step
# 3, 0x08014172), so with such a background the kept tiles and the flag could have been written
# over before step 10 put them back.  No scene was seen to take that case with a detail view open.
DETAIL_OPEN  = 0x08013d7e       # bl 0x08015170 (r0 = 1), the end of the detail view's step 0
DETAIL_ROW   = 0x08015170
DETAIL_CLOSE = 0x08014464       # bl to the restore trampoline (patches/text.py, RESTORE_CALLS)
DETAIL_TILES = 0x18             # OBJ tiles 0x00-0x17
DETAIL_KEEP  = 0x0202a900       # 768 bytes (0x0202a900-0x0202abff), clear of 0x0202b1c0
DETAIL_FLAG  = 0x0202ac00
DETAIL_MAGIC = 0x4c494554

def detail_keeps_text(rom):
    """The build's last step: the page's first tiles kept over an item's detail view."""
    from .icons import thumb_bl_target
    if thumb_bl_target(rom, DETAIL_OPEN) != DETAIL_ROW:
        raise SystemExit("court_record: the detail view's B / L row is not placed where it was")
    if thumb_bl_target(rom, DETAIL_CLOSE) != rom.restore_tramp & ~1:
        raise SystemExit("court_record: the detail view does not close where it did")
    words = DETAIL_TILES * 32 // 4
    keep = rom.thumb_code(f'''
        push {{r0, lr}}
        ldr r1, k_dma
        ldr r2, k_vram
        str r2, [r1]
        ldr r2, k_keep
        str r2, [r1, #4]
        ldr r2, k_ctl
        str r2, [r1, #8]
        ldr r2, [r1, #8]
        ldr r1, k_flag
        ldr r2, k_magic
        str r2, [r1]
        bl #{rom.syms["vwf_overlay"] & ~1:#x}
        pop {{r0}}
        bl #{DETAIL_ROW:#x}
        pop {{pc}}
        .align 2
    k_dma:   .word 0x040000d4
    k_vram:  .word 0x06010000
    k_keep:  .word {DETAIL_KEEP:#x}
    k_ctl:   .word {0x84000000 | words:#x}
    k_flag:  .word {DETAIL_FLAG:#x}
    k_magic: .word {DETAIL_MAGIC:#x}
    ''', note='detail view: the page\'s first tiles kept')
    back = rom.thumb_code(f'''
        push {{lr}}
        bl #{rom.restore_tramp & ~1:#x}
        ldr r3, b_flag
        ldr r2, [r3]
        ldr r1, b_magic
        cmp r2, r1
        bne b_done
        movs r1, #0
        str r1, [r3]
        ldr r1, b_dma
        ldr r2, b_keep
        str r2, [r1]
        ldr r2, b_vram
        str r2, [r1, #4]
        ldr r2, b_ctl
        str r2, [r1, #8]
        ldr r2, [r1, #8]
    b_done:
        pop {{pc}}
        .align 2
    b_dma:   .word 0x040000d4
    b_vram:  .word 0x06010000
    b_keep:  .word {DETAIL_KEEP:#x}
    b_ctl:   .word {0x84000000 | words:#x}
    b_flag:  .word {DETAIL_FLAG:#x}
    b_magic: .word {DETAIL_MAGIC:#x}
    ''', note='detail view: the page\'s first tiles put back')
    rom.hook_bl(DETAIL_OPEN, keep, 'detail view opens: the page\'s first tiles kept')
    rom.hook_bl(DETAIL_CLOSE, back, 'detail view closes: the page\'s first tiles put back')
