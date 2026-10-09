"""Minimal PNG support: writing needs nothing but the standard library; reading uses Pillow if
it is installed (pip install pillow), otherwise a small decoder for non-interlaced 8-bit files."""
import struct, zlib

def _chunk(tag, data):
    c = struct.pack('>I', len(data)) + tag + data
    return c + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff)

def write_png(path, width, height, rows, palette=None):
    """rows: list of `height` byte strings. With `palette` (list of (r,g,b)), rows hold palette
    indices (one byte per pixel, 8-bit indexed PNG); otherwise rows hold RGB triples."""
    if palette is not None:
        ihdr = struct.pack('>IIBBBBB', width, height, 8, 3, 0, 0, 0)
        plte = b''.join(bytes(c) for c in palette)
    else:
        ihdr = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    raw = b''.join(b'\0' + bytes(r) for r in rows)
    out = b'\x89PNG\r\n\x1a\n' + _chunk(b'IHDR', ihdr)
    if palette is not None: out += _chunk(b'PLTE', plte)
    out += _chunk(b'IDAT', zlib.compress(raw, 9)) + _chunk(b'IEND', b'')
    open(path, 'wb').write(out)

def read_png(path):
    """-> (width, height, mode, rows, palette): mode 'P' (rows of indices, palette list) or
    'RGB' (rows of RGB bytes, palette None)."""
    try:
        from PIL import Image
    except ImportError:
        return _read_png_builtin(path)
    im = Image.open(path)
    if im.mode == 'P':
        pal = im.getpalette()
        palette = [tuple(pal[i:i + 3]) for i in range(0, len(pal), 3)]
        data = im.tobytes()
        rows = [data[y * im.width:(y + 1) * im.width] for y in range(im.height)]
        return im.width, im.height, 'P', rows, palette
    im = im.convert('RGB')
    data = im.tobytes()
    rows = [data[y * im.width * 3:(y + 1) * im.width * 3] for y in range(im.height)]
    return im.width, im.height, 'RGB', rows, None

def _paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc: return a
    return b if pb <= pc else c

def _read_png_builtin(path):
    d = open(path, 'rb').read()
    if d[:8] != b'\x89PNG\r\n\x1a\n': raise ValueError('not a PNG')
    p = 8; idat = b''; palette = None; w = h = depth = ctype = interlace = None
    while p < len(d):
        n, tag = struct.unpack('>I4s', d[p:p + 8]); body = d[p + 8:p + 8 + n]; p += 12 + n
        if tag == b'IHDR': w, h, depth, ctype, _, _, interlace = struct.unpack('>IIBBBBB', body)
        elif tag == b'PLTE': palette = [tuple(body[i:i + 3]) for i in range(0, len(body), 3)]
        elif tag == b'IDAT': idat += body
        elif tag == b'IEND': break
    if interlace or depth != 8 or ctype not in (2, 3, 6):
        raise ValueError('builtin PNG reader handles only non-interlaced 8-bit RGB/RGBA/indexed files; install Pillow')
    bpp = {2: 3, 3: 1, 6: 4}[ctype]
    raw = zlib.decompress(idat); stride = w * bpp
    rows = []; prev = bytearray(stride); q = 0
    for y in range(h):
        f = raw[q]; line = bytearray(raw[q + 1:q + 1 + stride]); q += 1 + stride
        for i in range(stride):
            a = line[i - bpp] if i >= bpp else 0; b = prev[i]; c = prev[i - bpp] if i >= bpp else 0
            if f == 1: line[i] = (line[i] + a) & 255
            elif f == 2: line[i] = (line[i] + b) & 255
            elif f == 3: line[i] = (line[i] + (a + b) // 2) & 255
            elif f == 4: line[i] = (line[i] + _paeth(a, b, c)) & 255
        rows.append(bytes(line)); prev = line
    if ctype == 3: return w, h, 'P', rows, palette
    if ctype == 6: rows = [bytes(b for i, b in enumerate(r) if i % 4 != 3) for r in rows]
    return w, h, 'RGB', rows, None

def _x5(v):
    return (v << 3) | (v >> 2)

def bgr555_to_rgb(v):
    """5-bit channels expanded to 8 bits so that rgb_to_bgr555 gives the same value back."""
    return (_x5(v & 31), _x5((v >> 5) & 31), _x5((v >> 10) & 31))

def rgb_to_bgr555(c):
    r, g, b = c
    return (r >> 3) | ((g >> 3) << 5) | ((b >> 3) << 10)

def palette_from_bytes(data, n):
    return [bgr555_to_rgb(struct.unpack_from('<H', data, 2 * i)[0]) for i in range(n)]
