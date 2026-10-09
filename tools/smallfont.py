#!/usr/bin/env python3
"""Small proportional font for the Court Record panels: Spleen 5x8 (BSD-2-Clause, Frederic Cambus;
see fonts/LICENSE.spleen), read from its BDF file.  Glyphs advance by their ink width + 1, so the
5x8 cells set as a proportional font; the space is 3 pixels.  Spleen has no accented letters, so
the few the English text uses are composed from the base letter and an accent mark."""
import os

BDF = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts', 'spleen-5x8.bdf')
H = 8              # cell height; the baseline is row 6 (descenders use row 7)
SPACE = 3

def _load(path):
    glyphs = {}
    enc = bbx = bitmap = None
    for line in open(path, encoding='ascii', errors='replace'):
        p = line.split()
        if not p: continue
        if p[0] == 'ENCODING': enc = int(p[1])
        elif p[0] == 'BBX': bbx = tuple(int(x) for x in p[1:5])
        elif p[0] == 'BITMAP': bitmap = []
        elif p[0] == 'ENDCHAR':
            w, h, xo, yo = bbx
            rows = [[False] * 5 for _ in range(H)]
            top = 7 - (yo + h)
            for r, hexrow in enumerate(bitmap):
                v = int(hexrow, 16); bits = len(hexrow) * 4
                for x in range(w):
                    if v >> (bits - 1 - x) & 1:
                        yy, xx = top + r, xo + x
                        if 0 <= yy < H and 0 <= xx < 5: rows[yy][xx] = True
            glyphs[enc] = rows
            bitmap = None
        elif bitmap is not None:
            bitmap.append(p[0])
    return glyphs

GLYPHS = _load(BDF)

def _cols(g):
    return [x for x in range(5) if any(g[y][x] for y in range(H))]

# accented letters: base letter + mark
_ACC = {'é': ('e', 'acute'), 'è': ('e', 'grave'), 'ê': ('e', 'circ'), 'à': ('a', 'grave'), 'á': ('a', 'acute'),
        'â': ('a', 'circ'), 'ç': ('c', 'cedil'), 'Ç': ('C', 'cedil'), 'ñ': ('n', 'tilde'), 'ï': ('i', 'uml'),
        'î': ('i', 'circ'), 'û': ('u', 'circ'), 'ü': ('u', 'uml'), 'ö': ('o', 'uml'), 'ä': ('a', 'uml')}

def _compose(base, acc):
    g = [row[:] for row in GLYPHS[ord(base)]]
    cols = _cols(g); c0, c1 = cols[0], cols[-1]; mid = (c0 + c1) // 2
    if acc == 'cedil':
        g[7][mid] = True
        return g
    g[0] = [False] * 5; g[1] = [False] * 5
    if acc == 'acute': g[0][min(c1, mid + 1)] = True; g[1][mid] = True
    elif acc == 'grave': g[0][max(c0, mid - 1)] = True; g[1][mid] = True
    elif acc == 'circ': g[1][max(c0, mid - 1)] = True; g[0][mid] = True; g[1][min(c1, mid + 1)] = True
    elif acc == 'tilde':
        for i, x in enumerate(range(c0, c1 + 1)): g[1 if i % 2 == 0 else 0][x] = True
    elif acc == 'uml': g[1][c0] = True; g[1][c1] = True
    return g

for _k, (_b, _a) in _ACC.items():
    GLYPHS[ord(_k)] = _compose(_b, _a)

# m, w, M and W five pixels wide: in four they are hard to tell apart at this size
def _shape(rows):
    return [[c == '#' for c in r] for r in rows]
GLYPHS[ord('m')] = _shape(['.....', '.....', '##.#.', '#.#.#', '#.#.#', '#.#.#', '#.#.#', '.....'])
GLYPHS[ord('w')] = _shape(['.....', '.....', '#...#', '#...#', '#.#.#', '#.#.#', '.#.#.', '.....'])
GLYPHS[ord('M')] = _shape(['.....', '#...#', '##.##', '#.#.#', '#.#.#', '#...#', '#...#', '.....'])
GLYPHS[ord('W')] = _shape(['.....', '#...#', '#...#', '#.#.#', '#.#.#', '##.##', '#...#', '.....'])
GLYPHS[ord('☆')] = GLYPHS[ord('*')]
GLYPHS[ord('×')] = GLYPHS[ord('X')]
for _k, _v in {'“': '"', '”': '"', '‘': "'", '’': "'", '…': '.'}.items():
    GLYPHS[ord(_k)] = GLYPHS[ord(_v)]

def glyph(ch):
    return GLYPHS.get(ord(ch)) or GLYPHS[ord('?')]

def advance(ch):
    if ch == ' ': return SPACE
    cols = _cols(glyph(ch))
    return cols[-1] - cols[0] + 2 if cols else SPACE

def measure(text):
    return sum(advance(c) for c in text)

def render(text, canvas, x, y, value):
    """Draw text into canvas (list of rows of palette indices) with its cell top at y."""
    for ch in text:
        if ch != ' ':
            g = glyph(ch); cols = _cols(g); lb = cols[0] if cols else 0
            for r in range(H):
                for c in range(5):
                    if g[r][c]:
                        yy, xx = y + r, x + c - lb
                        if 0 <= yy < len(canvas) and 0 <= xx < len(canvas[0]): canvas[yy][xx] = value
        x += advance(ch)
    return x

def wrap(text, maxw):
    """Greedy word wrap -> list of lines."""
    lines = ['']
    for word in text.split(' '):
        if not word: continue
        cand = (lines[-1] + ' ' + word) if lines[-1] else word
        if measure(cand) <= maxw or not lines[-1]: lines[-1] = cand
        else: lines.append(word)
    return lines
