#!/usr/bin/env python3
"""GBA 'chunked image' objects: [u32 offsets[n]] then palette (raw) + LZ tile chunks.

The palette is 512 bytes for 8bpp pictures and 32 bytes for 4bpp ones; chunk 0 follows it
directly, the other chunks start at their offsets (4-byte aligned).
"""
import struct, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lz

def parse(g, base, psz=512):
    """-> (palette, [(decompressed chunk, compressed bytes)])"""
    first = struct.unpack_from('<I', g, base)[0]
    n = first // 4
    offs = struct.unpack_from('<%dI' % n, g, base)
    pal = bytes(g[base + offs[0]: base + offs[0] + psz])
    chunks = []
    for i in range(n):
        p = base + offs[0] + psz if i == 0 else base + offs[i]
        dec, used = lz.decompress(g, p)
        chunks.append((dec, bytes(g[p:p + used])))
    return pal, chunks

def load(g, base, psz=512):
    pal, chunks = parse(g, base, psz)
    return pal, b''.join(c for c, _ in chunks), [len(c) for c, _ in chunks]

def build(pal, tiles, chunk_bytes=3840, old=None):
    """Chunk `tiles` (a list of chunk sizes may be given instead of one size) and LZ them; a chunk
    equal to the same chunk of `old` (as returned by parse) keeps its compressed bytes."""
    sizes = chunk_bytes if isinstance(chunk_bytes, (list, tuple)) else \
        [min(chunk_bytes, len(tiles) - i) for i in range(0, len(tiles), chunk_bytes)]
    assert sum(sizes) == len(tiles), (sum(sizes), len(tiles))
    chunks, p = [], 0
    for s in sizes:
        chunks.append(tiles[p:p + s]); p += s
    n = len(chunks)
    body = bytearray(); offs = []
    for i, c in enumerate(chunks):
        if i == 0:
            offs.append(n * 4); body += pal
        else:
            while (n * 4 + len(body)) % 4: body.append(0)
            offs.append(n * 4 + len(body))
        if old is not None and i < len(old) and old[i][0] == c:
            body += old[i][1]
        else:
            body += lz.compress(c)
    return b''.join(struct.pack('<I', o) for o in offs) + bytes(body)
