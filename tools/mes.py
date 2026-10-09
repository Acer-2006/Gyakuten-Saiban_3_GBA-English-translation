#!/usr/bin/env python3
"""Script bank helpers: load sections, tokenize, rough English decode."""
import struct

def load_bank(d):
    n = struct.unpack_from('<I', d, 0)[0]
    offs = [struct.unpack_from('<I', d, 4 + i * 4)[0] for i in range(n)] + [len(d)]
    return [d[offs[i]:offs[i + 1]] for i in range(n)]

def save_bank(secs):
    hdr = struct.pack('<I', len(secs))
    off = 4 + 4 * len(secs)
    body = b''
    for s in secs:
        hdr += struct.pack('<I', off + len(body))
        body += s
    return hdr + body

def words(b):
    return [struct.unpack_from('<H', b, i)[0] for i in range(0, len(b) - 1, 2)]

def pack(ws):
    return b''.join(struct.pack('<H', w) for w in ws)

# provisional English char map (DS). Filled in properly once the font is extracted.
EN = {}
for i in range(10): EN[0x80 + i] = chr(48 + i)
for i in range(26): EN[0x8a + i] = chr(65 + i)
for i in range(26): EN[0xa4 + i] = chr(97 + i)
EN[0x17f] = ' '; EN[0x16f] = ','; EN[0x16d] = ':'; EN[0x161] = '.'

def decode_en(ws, cmd_args=None):
    out = []
    i = 0
    while i < len(ws):
        w = ws[i]
        if w >= 0x80:
            out.append(EN.get(w, f'[{w:03x}]')); i += 1
        else:
            if w == 1: out.append('\\n'); i += 1; continue
            if w == 2: out.append('<p>\n'); i += 1; continue
            n = cmd_args.get(w, 0) if cmd_args else 0
            args = ws[i + 1:i + 1 + n]
            out.append('<%02x%s>' % (w, (' ' + ' '.join(f'{a:x}' for a in args)) if n else ''))
            i += 1 + n
    return ''.join(out)
