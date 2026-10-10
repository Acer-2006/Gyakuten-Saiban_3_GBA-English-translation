#!/usr/bin/env python3
"""The Court Record descriptions' font: Inter Medium at 10 pixels, anti-aliased (fonts/
inter-medium-10.txt, made by fonts/make_crfont.py from Inter 4.0, SIL Open Font License 1.1, see
fonts/LICENSE.inter).

Glyphs are coverage maps of five levels, 0 (background) to 4 (full); the advances and the
kerning are kept in 1/64 pixel, and a line is laid out as FreeType lays out the whole line: the pen
moves by the exact advances and kerning, and each glyph is put at the nearest pixel.  Word spaces
are half a pixel wider than Inter's own (2.7 pixels at this size), which keeps the words apart
where a letter's edge would otherwise round into the gap.  The caller gives the palette index of
each level: the Court Record panel has a ramp from its background to white."""
import os

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts', 'inter-medium-10.txt')

class Glyph:
    __slots__ = ('adv', 'x', 'y', 'w', 'h', 'rows')

def _load(path):
    glyphs, kern, metrics = {}, {}, {}
    g = None
    for line in open(path, encoding='utf-8'):
        if line.startswith('#') or not line.strip(): continue
        if line.startswith(' '):
            g.rows.append([0 if c == '.' else int(c) for c in line.strip()]); continue
        p = line.split()
        if p[0] == 'size':
            metrics = {k: int(v) for k, v in zip(p[::2], p[1::2])}
        elif p[0] == 'glyph':
            g = Glyph(); g.adv, g.x, g.y, g.w, g.h = (int(v) for v in p[2:7]); g.rows = []
            glyphs[chr(int(p[1], 16))] = g
        elif p[0] == 'kern':
            kern[(chr(int(p[1], 16)), chr(int(p[2], 16)))] = int(p[3])
    return glyphs, kern, metrics

GLYPHS, KERN, METRICS = _load(PATH)
ASCENT, DESCENT = METRICS['ascent'], METRICS['descent']
LINE = ASCENT + DESCENT          # height of a line box; the baseline is ASCENT rows from its top
FALLBACK = {'—': '-', '–': '-', '´': "'", '`': "'"}
SPACE_EXTRA = 32                 # 1/64 pixel added to each space

def glyph(ch):
    return GLYPHS.get(ch) or GLYPHS.get(FALLBACK.get(ch, '?')) or GLYPHS['?']

def layout(text):
    """-> [(glyph, x)] with x in pixels from the line's start, and the width of the line."""
    out, pen, prev = [], 0, None
    for ch in text:
        if prev is not None: pen += KERN.get((prev, ch), 0)
        g = glyph(ch)
        out.append((g, (pen + 32) >> 6))
        pen += g.adv + (SPACE_EXTRA if ch == ' ' else 0); prev = ch
    return out, (pen + 63) >> 6

def measure(text):
    return layout(text)[1]

BALANCE = 16                     # pixels the last line may be longer than the one above it
# words that read badly at the end of a line, before the word they go with
CLINGY = {'a', 'an', 'the', 'to', 'of', 'in', 'on', 'at', 'by', 'for', 'and', 'or', 'with', 'from',
          'as', 'my', 'his', 'her', 'its', 'our', 'your', 'their', 'he', 'she', 'i'}

def wrap(text, maxw):
    """Greedy word wrap -> list of lines.  A word of symbols only (the × and = of "× = victim's
    seat", a --) stays on the line of the words next to it.  A last line of one word gets one to
    three more from the line above, as many as make that line end best: after a full stop or a
    comma rather than in the middle of a sentence, and not on an article, a preposition, a
    number or a single letter ("Written by Bullard. Press L to / read." becomes "Written by
    Bullard. / Press L to read."); the line above keeps two words at least and, unless it ends a
    sentence, does not get much shorter than the last.  The L of "Press L" stays with Press."""
    units = []
    glue = False
    for word in text.split(' '):
        if not word: continue
        symbol = not any(c.isalnum() for c in word)
        if units and (glue or symbol or word in ('L', 'R')): units[-1] += ' ' + word
        else: units.append(word)
        glue = symbol
    lines = [[]]
    for unit in units:
        if lines[-1] and measure(' '.join(lines[-1] + [unit])) > maxw: lines.append([])
        lines[-1].append(unit)
    if len(lines) > 1 and len(lines[-1]) == 1:
        def badness(end, nxt):
            if end[-1] in '.,:;?!': return -1
            if end[0].isupper() and nxt[0].isupper(): return 2       # a name: Furio / Tigre
            return int(end.lower() in CLINGY or end.isdigit() or (len(end) == 1 and end.isalpha()))
        prev, last = lines[-2], lines[-1]
        best = None
        for k in range(1, min(3, len(prev) - 2) + 1):
            cost = (badness(prev[-k - 1], prev[-k]), k)
            if cost[0] >= 0 and measure(' '.join(prev[-k:] + last)) > measure(' '.join(prev[:-k])) + BALANCE:
                continue
            if best is None or cost < best: best = cost
        if best and best[0] < 2:
            k = best[1]
            lines[-2:] = [prev[:-k], prev[-k:] + last]
    return [' '.join(l) for l in lines]

def render(text, levels, x, top):
    """Draw text into `levels` (rows of coverage levels 0-4, which keep the highest level where
    glyphs overlap) with its line box's top at `top`."""
    base = top + ASCENT
    for g, gx in layout(text)[0]:
        for r, row in enumerate(g.rows):
            yy = base + g.y + r
            if not 0 <= yy < len(levels): continue
            line = levels[yy]
            for c, v in enumerate(row):
                xx = x + gx + g.x + c
                if v and 0 <= xx < len(line) and v > line[xx]: line[xx] = v
