#!/usr/bin/env python3
"""Scaling a paletted picture down without breaking its letters, in plain Python.

Nearest-neighbour scaling by an uneven factor drops whole rows and columns here and there, which
breaks thin strokes and makes letters uneven.  Here the picture is scaled in full colour with a
Lanczos filter (3 lobes, stretched by the scale factor so that every source pixel counts), and
each new pixel then takes the nearest colour of the picture's own palette, so the result needs no
new colours.  (Python only: no Pillow at build time.)"""
import math

def _lanczos(t, a=3):
    if t == 0: return 1.0
    if abs(t) >= a: return 0.0
    pt = math.pi * t
    return a * math.sin(pt) * math.sin(pt / a) / (pt * pt)

def _weights(n_in, n_out, a=3):
    """For each output index: [(input index, weight)], weights summing to 1."""
    scale = n_in / n_out
    reach = a * max(scale, 1.0)
    out = []
    for o in range(n_out):
        centre = (o + 0.5) * scale
        ws = []
        for i in range(int(centre - reach) - 1, int(centre + reach) + 2):
            if 0 <= i < n_in:
                w = _lanczos((i + 0.5 - centre) / max(scale, 1.0), a)
                if w: ws.append((i, w))
        total = sum(w for _, w in ws)
        out.append([(i, w / total) for i, w in ws])
    return out

def scale_rgb(rows, nw, nh):
    """rows: lists of (r, g, b) -> nh rows of nw (r, g, b) floats."""
    h, w = len(rows), len(rows[0])
    wx, wy = _weights(w, nw), _weights(h, nh)
    tmp = []
    for row in rows:
        line = []
        for ws in wx:
            r = g = b = 0.0
            for i, wt in ws:
                p = row[i]; r += p[0] * wt; g += p[1] * wt; b += p[2] * wt
            line.append((r, g, b))
        tmp.append(line)
    out = []
    for ws in wy:
        line = []
        for x in range(nw):
            r = g = b = 0.0
            for i, wt in ws:
                p = tmp[i][x]; r += p[0] * wt; g += p[1] * wt; b += p[2] * wt
            line.append((r, g, b))
        out.append(line)
    return out

def bgr555_to_rgb(c):
    r, g, b = c & 31, c >> 5 & 31, c >> 10 & 31
    return (r << 3 | r >> 2, g << 3 | g >> 2, b << 3 | b >> 2)

def scale_indexed(pixels, w, h, palette, nw, nh):
    """pixels: w*h palette indices (row by row); palette: index -> BGR555 colour.  -> nw*nh
    indices, each the colour of the used ones nearest to the filtered pixel."""
    rgb = {i: bgr555_to_rgb(palette[i]) for i in set(pixels)}
    rows = [[rgb[pixels[y * w + x]] for x in range(w)] for y in range(h)]
    cands = sorted(rgb)
    cache, out = {}, bytearray()
    for line in scale_rgb(rows, nw, nh):
        for r, g, b in line:
            key = (round(r), round(g), round(b))
            if key not in cache:
                cache[key] = min(cands, key=lambda i: 3 * (rgb[i][0] - key[0]) ** 2 +
                                 4 * (rgb[i][1] - key[1]) ** 2 + 2 * (rgb[i][2] - key[2]) ** 2)
            out.append(cache[key])
    return bytes(out)

def scale_1d(samples, n_out):
    """A sound (or any list of numbers) resampled to n_out values with the same filter."""
    out = []
    for ws in _weights(len(samples), n_out):
        out.append(sum(samples[i] * w for i, w in ws))
    return out
