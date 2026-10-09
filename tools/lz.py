#!/usr/bin/env python3
"""GBA/NDS BIOS-style LZ77 (type 0x10) codec."""
import struct

def decompress(d, off=0):
    if d[off] != 0x10:
        raise ValueError(f'not LZ10 at {off:#x}: {d[off]:#x}')
    size = d[off + 1] | (d[off + 2] << 8) | (d[off + 3] << 16)
    out = bytearray()
    p = off + 4
    while len(out) < size:
        flags = d[p]; p += 1
        for bit in range(8):
            if len(out) >= size: break
            if flags & (0x80 >> bit):
                b1, b2 = d[p], d[p + 1]; p += 2
                n = (b1 >> 4) + 3
                disp = ((b1 & 0xF) << 8 | b2) + 1
                for _ in range(n):
                    out.append(out[-disp])
            else:
                out.append(d[p]); p += 1
    return bytes(out), p - off  # data, compressed length consumed

def compress(data, vram_safe=True):
    """Greedy LZ10 encoder (min disp 2 when vram_safe, as the GBA BIOS needs for VRAM)."""
    out = bytearray(struct.pack('<I', 0x10 | (len(data) << 8)))
    n = len(data); i = 0
    min_disp = 2 if vram_safe else 1
    # simple hash chain for speed
    from collections import defaultdict
    table = defaultdict(list)
    def find(i):
        best_len, best_disp = 0, 0
        if i + 3 > n: return 0, 0
        key = data[i:i + 3]
        cands = table.get(key, ())
        for j in reversed(cands):
            disp = i - j
            if disp > 0x1000: break
            if disp < min_disp: continue
            l = 0
            maxl = min(18, n - i)
            while l < maxl and data[j + l] == data[i + l]: l += 1
            if l > best_len:
                best_len, best_disp = l, disp
                if l == 18: break
        return best_len, best_disp
    while i < n:
        flags = 0; chunk = bytearray()
        for bit in range(8):
            if i >= n: break
            l, disp = find(i)
            if l >= 3:
                flags |= 0x80 >> bit
                chunk += bytes([((l - 3) << 4) | ((disp - 1) >> 8), (disp - 1) & 0xFF])
                for k in range(l):
                    if i + k + 3 <= n: table[data[i + k:i + k + 3]].append(i + k)
                i += l
            else:
                chunk.append(data[i])
                if i + 3 <= n: table[data[i:i + 3]].append(i)
                i += 1
        out.append(flags); out += chunk
    while len(out) % 4: out.append(0)
    return bytes(out)

if __name__ == '__main__':
    import sys
    d = open(sys.argv[1], 'rb').read()
    off = int(sys.argv[3], 0) if len(sys.argv) > 3 else 0
    out, used = decompress(d, off)
    open(sys.argv[2], 'wb').write(out)
    print(f'decompressed {used:#x} -> {len(out):#x}')
