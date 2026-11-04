#!/usr/bin/env python3
"""Scaling a paletted picture down without breaking its letters, in plain Python.

Nearest-neighbour scaling by an uneven factor drops whole rows and columns here and there, which
breaks thin strokes and makes letters uneven.  Here the picture is scaled in full colour with a
Lanczos filter (3 lobes, stretched by the scale factor so that every source pixel counts), and
each new pixel then takes the nearest colour of the picture's own palette, so the result needs no
new colours.  (Python only: no Pillow at build time.)"""
import math, struct

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

def band_limited(samples, rate_in, rate_out, zeros=32, cutoff=0.97):
    """A sound at rate_in -> round(len * rate_out / rate_in) samples at rate_out, nothing above
    `cutoff` of the lower rate's half left in it: a Blackman-windowed sinc reaching `zeros` zero
    crossings each side, its weights summing to 1 at each output sample.  Sample o is the sound
    at input position o * rate_in / rate_out, so the timing is the input's.  Against an exact
    conversion (the spectrum cut at half the lower rate) the defaults are about 25 dB below the
    sound, where Lanczos-3 (scale_1d) is about 10: it dulls the top of the band and leaks above it."""
    n_out = round(len(samples) * rate_out / rate_in)
    step = rate_in / rate_out
    fc = cutoff * min(1.0, rate_out / rate_in) / 2          # cycles per input sample
    reach = zeros / (2 * fc)                                # input samples each side
    last = len(samples) - 1
    out = []
    for o in range(n_out):
        t = o * step
        acc = wsum = 0.0
        for i in range(max(0, int(t - reach)), min(last, int(t + reach) + 1) + 1):
            d = t - i
            if abs(d) >= reach: continue
            x = 2 * fc * d
            s = 1.0 if x == 0 else math.sin(math.pi * x) / (math.pi * x)
            u = math.pi * d / reach
            w = s * (0.42 + 0.5 * math.cos(u) + 0.08 * math.cos(2 * u))
            acc += samples[i] * w; wsum += w
        out.append(acc / wsum if wsum else 0.0)
    return out

# ---- the English GS1's verdict letters (tools/en/effects_common.py scale_indexed there) -------
# Pillow's BOX resize of mode F pictures, reproduced exactly: a pass along the rows, then one down
# the columns, each output sample the plain mean of the input samples whose centres fall inside it
# (Pillow's box filter on (x - centre + 0.5) / scale, in (-0.5, 0.5]), stored as 32-bit floats.

def _f32(x):
    return struct.unpack('<f', struct.pack('<f', x))[0]

def _box_coeffs(n_in, n_out):
    scale = n_in / n_out
    fscale = max(scale, 1.0)
    support = 0.5 * fscale
    out = []
    for o in range(n_out):
        centre = (o + 0.5) * scale
        lo = max(0, int(centre - support + 0.5))
        hi = min(n_in, int(centre + support + 0.5))
        ws = [1.0 if -0.5 < (i - centre + 0.5) / fscale <= 0.5 else 0.0 for i in range(lo, hi)]
        total = sum(ws)
        out.append((lo, [w / total for w in ws] if total else ws))
    return out

def _box_resize(rows, w, h, tw, th):
    hc, vc = _box_coeffs(w, tw), _box_coeffs(h, th)
    tmp = [[_f32(sum(row[lo + k] * wk for k, wk in enumerate(ws))) for lo, ws in hc] for row in rows]
    return [[_f32(sum(tmp[lo + k][x] * wk for k, wk in enumerate(ws))) for x in range(tw)] for lo, ws in vc]

def scale_indexed_box(px, colors, factor, usable):
    """The English GS1's scale_indexed: px (rows of palette indices, 0 transparent) scaled by
    factor (to round(w * factor) x round(h * factor)): each colour channel times the coverage,
    and the coverage itself, box-averaged; a pixel at least half covered takes the colour of
    `usable` (palette indices; colors: index -> (r, g, b)) nearest to the averaged colour, the
    rest stay transparent.  Every pixel is one of the picture's own colours."""
    h, w = len(px), len(px[0])
    tw, th = int(round(w * factor)), int(round(h * factor))
    cover = _box_resize([[1.0 if v else 0.0 for v in row] for row in px], w, h, tw, th)
    chans = [_box_resize([[float(colors[v][c]) if v else 0.0 for v in row] for row in px], w, h, tw, th)
             for c in range(3)]
    cand = [colors[u] for u in usable]
    out = [[0] * tw for _ in range(th)]
    for y in range(th):
        for x in range(tw):
            a = cover[y][x]
            if a < 0.5: continue
            col = [_f32(chans[c][y][x] / a) for c in range(3)]
            d = [sum((col[c] - k[c]) ** 2 for c in range(3)) for k in cand]
            out[y][x] = usable[d.index(min(d))]
    return out
