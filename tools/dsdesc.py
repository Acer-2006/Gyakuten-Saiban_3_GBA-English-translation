#!/usr/bin/env python3
"""The Court Record descriptions in the DS version's own description font.

The DS draws each description as a picture in its dialogue font (the font of the text box): sharp
one-colour letters 13 rows tall, 2 pixels apart, words 10 apart, three lines of up to 228 pixels
in a box under the panel.  The GBA panel has 149 pixels and 48 rows for the description, so the
build sets the same text in the same letters (read from the user's DS ROM, tools/dsfont.py) with
every gap of the DS layout halved: letters 1 pixel apart, words 5.  A description that fits in
three lines gets them 16 rows apart, at the height of the Japanese ones; a longer one gets four
lines 12 rows apart.  The letters reach 10 rows above the baseline and 3 below, so in four lines
the tail of a g can come down to the row where the line below begins.  The build weighs every way
to break the text into its lines (cost): letters of two lines (or of the first line and the
name) touching weigh most, then a lone word on the last line, a line ending on "a" or "the" or
between the two words of a name, and lines filled unevenly.  In about two thirds of the four-line
descriptions no letters touch.

A description that does not fit in four lines that way gets its word gaps narrowed (to 4, then 3
pixels), and then a word hyphenated where HYPHENS allows; with the US DS text, two need the first
and one (Franziska von Karma's profile) both."""
import dsfont, dsimgtext

# words that read badly at the end of a line, before the word they go with
CLINGY = {'a', 'an', 'the', 'to', 'of', 'in', 'on', 'at', 'by', 'for', 'and', 'or', 'with', 'from',
          'as', 'my', 'his', 'her', 'its', 'our', 'your', 'their', 'he', 'she', 'i'}
# what the line breaks cost, against the sum of the squared room left at the end of each line
# but the last: a pixel where letters of two lines overlap, a column where they touch, a
# last line of one word, a line ending badly (badness)
W_OVER, W_TOUCH, W_WIDOW, W_END = 10000, 1500, 2500, 700
# where a word may be broken when nothing else makes the text fit (dictionary hyphenation)
HYPHENS = {'prosecutor': 'pros-ecutor'}

class Font:
    """The DS dialogue font as ink columns: {char: (cols, lsb, rsb)}, cols a 16-bit mask per column
    (bit k = row k), lsb/rsb the blank columns before and after the ink within the advance."""
    def __init__(self, data, arm9):
        self.glyphs = {}
        for code, ch in dsimgtext.CHARS.items():
            self._add(ch, dsimgtext._cols_from_rows(dsfont.glyph_rows(data, code)),
                      dsfont.glyph_width(arm9, code))
        # the × and the narrow = of the DS pictures (the tool that drew them had them, the
        # game's font has no × and a wider =)
        for ch, cols, width, _ in dsimgtext._synthetic():
            self._add(ch, cols, width)
        self.space = dsfont.glyph_width(arm9, dsimgtext.SPACE)

    def _add(self, ch, cols, adv):
        ink = [x for x, m in enumerate(cols) if m]
        if ink: self.glyphs[ch] = (tuple(cols[ink[0]:ink[-1] + 1]), ink[0], adv - ink[-1] - 1)

    def glyph(self, ch):
        return self.glyphs.get(ch) or self.glyphs['?']

    def layout(self, text, word_cut=0):
        """-> ([(cols, x)], width): each glyph at x = its first ink column; the width of the ink.
        Each gap is half the DS one (rounded up), less word_cut between words."""
        out, x, prev, spaces = [], 0, None, 0
        for ch in text:
            if ch == ' ': spaces += 1; continue
            cols, lsb, rsb = self.glyph(ch)
            if prev is not None:
                x += (prev + spaces * self.space + lsb + 1) // 2 - (word_cut if spaces else 0)
            out.append((cols, x)); x += len(cols); prev = rsb; spaces = 0
        return out, x

    def width(self, text, word_cut=0):
        return self.layout(text, word_cut)[1]

    def masks(self, text, x0, w, word_cut=0):
        """The line as w column masks, starting at x0."""
        cols = [0] * w
        for gc, x in self.layout(text, word_cut)[0]:
            for i, m in enumerate(gc):
                if 0 <= x0 + x + i < w: cols[x0 + x + i] |= m
        return cols

def units(text):
    """Words, with a word of symbols only (the × and = of "× = victim's seat", a --) kept with the
    words next to it, and the L of "Press L" with Press."""
    out, glue = [], False
    for word in text.split(' '):
        if not word: continue
        symbol = not any(c.isalnum() for c in word)
        if out and (glue or symbol or word in ('L', 'R')): out[-1] += ' ' + word
        else: out.append(word)
        glue = symbol
    return out

def hyphenated(us):
    """The units with HYPHENS applied, one word at a time: [(units, hyphen at)]."""
    for i, u in enumerate(us):
        h = HYPHENS.get(u.lower().strip('.,'))
        if h:
            a, b = h.split('-')
            if u[:1].isupper(): a = a.capitalize()
            yield us[:i] + [a + '-', u[len(a):]] + us[i + 1:], i

def splits(us, n, fits, hy=None):
    """Every way to cut the units into n lines that fit -> lists of line strings.  hy: the index of
    the first half of a hyphenated word, which has to end its line."""
    if n == 1:
        line = ' '.join(us)
        if us and hy is None and fits(line): yield [line]
        return
    for k in range(1, len(us) - n + 2):
        line = ' '.join(us[:k])
        if not fits(line) or (hy is not None and hy < k - 1): break
        for tail in splits(us[k:], n - 1, fits, None if hy is None or hy == k - 1 else hy - k):
            yield [line] + tail

def clash(upper, lower, pitch):
    """(overlapping pixels, columns where letters touch) of two lines' masks, the lower `pitch`
    rows below the upper."""
    over = touch = 0
    for x in range(len(upper)):
        low = lower[x] << pitch
        if not low: continue
        a = upper[x]
        near = (upper[x - 1] if x else 0) | a | (upper[x + 1] if x + 1 < len(upper) else 0)
        near |= near << 1 | near >> 1
        over += bin(a & low).count('1')
        touch += bool(near & low)
    return over, touch

def badness(end, nxt):
    """How badly a line reads ending on `end` with `nxt` starting the next."""
    if end.endswith('-') or end[-1] in '.,:;?!': return 0
    if end[0].isupper() and nxt[0].isupper(): return 2         # a name: Furio / Tigre
    return int(end.lower() in CLINGY or end.isdigit() or (len(end) == 1 and end.isalpha()))

def choose(font, text, maxw, name_masks, x0, layouts):
    """-> (lines, tops, word_cut): the description's lines and the panel row of each line's top.
    layouts: {line count: tops}."""
    us = units(text)
    for word_cut in (0, 1, 2):
        def fits(line): return font.width(line, word_cut) <= maxw
        for cand_units, hy in [(us, None)] + (list(hyphenated(us)) if word_cut == 2 else []):
            for n in sorted(layouts):
                cands = list(splits(cand_units, n, fits, hy))
                if not cands: continue
                tops = layouts[n]
                return min(cands, key=lambda c: cost(font, c, tops, maxw, name_masks, x0, word_cut)), tops, word_cut
    return None, None, None

def cost(font, lines, tops, maxw, name_masks, x0, word_cut):
    w = len(name_masks)
    ms = [font.masks(l, x0, w, word_cut) for l in lines]
    over = touch = 0
    o, t = clash(name_masks, [m << tops[0] for m in ms[0]], 0)
    over += o; touch += t
    for k in range(len(lines) - 1):
        o, t = clash(ms[k], ms[k + 1], tops[k + 1] - tops[k])
        over += o; touch += t
    words = [l.split(' ') for l in lines]
    widow = int(len(lines) > 1 and len(units(lines[-1])) == 1)
    ends = sum(badness(words[k][-1], words[k + 1][0]) for k in range(len(lines) - 1))
    rag = sum((maxw - font.width(l, word_cut)) ** 2 for l in lines[:-1])
    if len(lines) > 1 and font.width(lines[-1], word_cut) > font.width(lines[-2], word_cut) + 16:
        rag += 400                                             # a last line longer than the one above
    return over * W_OVER + touch * W_TOUCH + widow * W_WIDOW + ends * W_END + rag
