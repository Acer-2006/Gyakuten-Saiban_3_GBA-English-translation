#!/usr/bin/env python3
"""GBA 'chunked image' objects: [u32 offsets[n]] then palette (512 bytes, raw) + LZ tile chunks."""
import struct, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lz

def load(g, base):
    first = struct.unpack_from('<I', g, base)[0]
    n = first // 4
    offs = struct.unpack_from('<%dI' % n, g, base)
    pal = g[base + offs[0]: base + offs[0] + 512]
    tiles = b''
    p = base + offs[0] + 512
    chunks = []
    for i in range(n):
        if i > 0: p = base + offs[i]
        dec, used = lz.decompress(g, p)
        chunks.append(len(dec)); tiles += dec
    return pal, tiles, chunks

def build(pal, tiles, chunk_bytes=3840):
    chunks = [tiles[i:i + chunk_bytes] for i in range(0, len(tiles), chunk_bytes)]
    n = len(chunks)
    body = bytearray(); offs = []
    for i, c in enumerate(chunks):
        if i == 0:
            offs.append(n * 4); body += pal
        else:
            while (n * 4 + len(body)) % 4: body.append(0)
            offs.append(n * 4 + len(body))
        comp = lz.compress(c)
        body += comp
    return b''.join(struct.pack('<I', o) for o in offs) + bytes(body)
