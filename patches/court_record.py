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
tools/dsimgtext.py) and set again in the same font, the DS's letters with the DS's gaps halved, so
they fit the GBA panel (tools/dsdesc.py).
"""
import os, re, struct, sys
from collections import Counter
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
import lz, dsdesc, dsimgtext, textgfx

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
    for i in range(COUNT):
        if i not in new:
            same = [k for k in new if orig[k] == orig[i]]
            if same: new[i] = new[same[0]]
    for i, addr in new.items():
        rom.w32(GBA_ITEMS + 8 * i, addr)
    print(f"  court record: {len(new)} of {COUNT} panels in English ({len(stored)} pictures)" +
          (f", narrower word gaps in {tight}" if tight else '') +
          (f"; could not read the DS text of {unread}" if unread else ''))
    font = textgfx.Font.from_ctx(ctx)
    for addr, text in LABELS.items():
        grid = textgfx.render(font, text, 64, 16, fill=12, outline=10, align='left', y0=2)
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
