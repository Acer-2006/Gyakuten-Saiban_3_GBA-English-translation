#!/usr/bin/env python3
"""Minimal NitroFS (NDS ROM filesystem) extractor."""
import os, struct, sys

def read_fnt(d, fnt_off):
    # main table entries: (subtable offset, first file id, parent/count)
    sub_off, first_id, total = struct.unpack_from('<IHH', d, fnt_off)
    dirs = {}
    for i in range(total):
        sub_off, first_id, parent = struct.unpack_from('<IHH', d, fnt_off + i * 8)
        dirs[0xF000 + i] = (sub_off, first_id, parent)
    names = {}  # file_id -> path ; also dir paths
    dirpath = {0xF000: ''}
    def walk(did):
        sub_off, fid, _ = dirs[did]
        p = fnt_off + sub_off
        while True:
            l = d[p]; p += 1
            if l == 0: break
            n = l & 0x7F
            name = d[p:p + n].decode('ascii', 'replace'); p += n
            if l & 0x80:
                sub = struct.unpack_from('<H', d, p)[0]; p += 2
                dirpath[sub] = dirpath[did] + name + '/'
                walk(sub)
            else:
                names[fid] = dirpath[did] + name
                fid += 1
    walk(0xF000)
    return names

def extract(rom, outdir):
    d = open(rom, 'rb').read()
    fnt_off, fnt_size, fat_off, fat_size = struct.unpack_from('<IIII', d, 0x40)
    names = read_fnt(d, fnt_off)
    n = fat_size // 8
    res = []
    for i in range(n):
        s, e = struct.unpack_from('<II', d, fat_off + i * 8)
        name = names.get(i, f'overlay_{i}')
        res.append((i, name, s, e))
        if outdir:
            path = os.path.join(outdir, name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            open(path, 'wb').write(d[s:e])
    # also dump arm9/arm7 + overlays tables
    if outdir:
        a9o, _, _, a9s = struct.unpack_from('<IIII', d, 0x20)
        a7o, _, _, a7s = struct.unpack_from('<IIII', d, 0x30)
        open(os.path.join(outdir, 'arm9.bin'), 'wb').write(d[a9o:a9o + a9s])
        open(os.path.join(outdir, 'arm7.bin'), 'wb').write(d[a7o:a7o + a7s])
        y9o, y9s = struct.unpack_from('<II', d, 0x50)
        if y9s:
            open(os.path.join(outdir, 'y9.bin'), 'wb').write(d[y9o:y9o + y9s])
    return res

def files(d):
    """ROM bytes -> {path: bytes} for every file in the filesystem."""
    fnt_off, fnt_size, fat_off, fat_size = struct.unpack_from('<IIII', d, 0x40)
    names = read_fnt(d, fnt_off)
    out = {}
    for i in range(fat_size // 8):
        s, e = struct.unpack_from('<II', d, fat_off + i * 8)
        out[names.get(i, f'overlay_{i}')] = d[s:e]
    return out

if __name__ == '__main__':
    rom = sys.argv[1]; out = sys.argv[2] if len(sys.argv) > 2 else None
    for i, name, s, e in extract(rom, out):
        print(f'{i:4d} {s:#010x} {e - s:#10x} {name}')
