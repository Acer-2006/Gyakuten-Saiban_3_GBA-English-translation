#!/usr/bin/env python3
"""MP2K (Sappy) sound data: songs, instruments and PCM samples.

  gs3_sound.py songs   ROM [FIRST [LAST]]       list songs: header, tracks, voicegroup, samples used
  gs3_sound.py samples ROM                      every PCM sample reachable from a song
  gs3_sound.py export  ROM SAMPLE_ADDR OUT.wav  write a sample as a 8-bit mono WAV
  gs3_sound.py replace ROM SAMPLE_ADDR IN.wav OUT.gba [--at ADDR] [--loop]
        store IN.wav (any PCM WAV; converted to 8-bit mono at its own rate) as a new sample in
        free space and point every instrument that used SAMPLE_ADDR at it

Song numbers are what the game's sound calls use (song table 0x08054824, 406 entries). The
twelve shouts are songs 0x37 0x38 0x39 0x47 0x51 0x96 0x16f..0x174, one sample each.
"""
import sys, struct, wave, argparse
from _common import *
import mp2k

def sample_info(g, off):
    t, st, rate, loop, size = struct.unpack_from('<HHIII', g, off)
    return {'off': off, 'rate': rate >> 10, 'loop': loop, 'size': size, 'looped': bool(st & 0x4000)}

def cmd_songs(a):
    g = load_rom(a.rom); warn_not_gs3(g)
    lo = a.first if a.first is not None else 0
    hi = a.last if a.last is not None else (lo if a.first is not None else mp2k.NSONG - 1)
    for k in range(lo, hi + 1):
        try:
            s = mp2k.song(g, k)
        except Exception:
            print(f'{k:#5x}: (unreadable)'); continue
        try:
            samples = mp2k.song_samples(g, k)
        except Exception:
            samples = []
        smp = ' '.join(f'prog{p}:{rom_addr(o):#x}' for p, o in samples)
        print(f'{k:#5x}: header {rom_addr(s["hdr"]):#x}, {len(s["tracks"])} track(s), voicegroup '
              f'{rom_addr(s["tone"]):#x}' if s['tone'] is not None else f'{k:#5x}: header {rom_addr(s["hdr"]):#x}, no voicegroup', end='')
        if smp: print(f', samples {smp}')
        else: print()

def all_samples(g):
    seen = {}
    for k in range(mp2k.NSONG):
        try:
            for p, o in mp2k.song_samples(g, k):
                seen.setdefault(o, []).append(k)
        except Exception:
            pass
    return seen

def cmd_samples(a):
    g = load_rom(a.rom); warn_not_gs3(g)
    seen = all_samples(g)
    print('  address    rate   bytes  loop   used by songs')
    for o in sorted(seen):
        i = sample_info(g, o)
        songs = ' '.join(f'{k:#x}' for k in seen[o][:8]) + (' ...' if len(seen[o]) > 8 else '')
        print(f'{rom_addr(o):#x}  {i["rate"]:5}  {i["size"]:6}  {"yes" if i["looped"] else "no ":4}  {songs}')
    print(f'{len(seen)} samples')

def cmd_export(a):
    g = load_rom(a.rom)
    off = rom_off(a.sample)
    i = sample_info(g, off)
    data = g[off + 16: off + 16 + i['size']]
    w = wave.open(a.out, 'wb'); w.setnchannels(1); w.setsampwidth(1); w.setframerate(i['rate'])
    w.writeframes(bytes((b + 128) & 0xff for b in data)); w.close()      # signed -> unsigned 8-bit
    print(f'{rom_addr(off):#x}: {i["size"]} samples at {i["rate"]} Hz -> {a.out}')

def read_wav(path):
    w = wave.open(path, 'rb')
    ch, sw, rate, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
    raw = w.readframes(n); w.close()
    out = []
    for i in range(n):
        acc = 0
        for c in range(ch):
            p = (i * ch + c) * sw
            if sw == 1: v = raw[p] - 128
            elif sw == 2: v = struct.unpack_from('<h', raw, p)[0] >> 8
            elif sw == 3: v = struct.unpack_from('<i', b'\0' + raw[p:p + 3])[0] >> 24
            else: v = struct.unpack_from('<i', raw, p)[0] >> 24
            acc += v
        out.append(max(-128, min(127, acc // ch)))
    return rate, out

def cmd_replace(a):
    rom = bytearray(load_rom(a.rom)); warn_not_gs3(rom)
    old = rom_off(a.sample)
    rate, pcm = read_wav(a.infile)
    hdr = struct.pack('<HHIII', 0, 0x4000 if a.loop else 0, rate << 10, 0, len(pcm))
    data = hdr + bytes(v & 0xff for v in pcm) + b'\0' * 16
    new = place(rom, data, a.at, 4, 'sample')
    n = repoint(rom, rom_addr(old), new)
    print(f'{n} instrument(s) repointed from {rom_addr(old):#x} to {new:#x} ({len(pcm)} samples at {rate} Hz)')
    if n == 0: sys.exit('nothing referred to that sample address')
    save_rom(rom, a.out)

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('songs'); p.add_argument('rom'); p.add_argument('first', nargs='?', type=num); p.add_argument('last', nargs='?', type=num)
    p.set_defaults(fn=cmd_songs)
    p = sub.add_parser('samples'); p.add_argument('rom'); p.set_defaults(fn=cmd_samples)
    p = sub.add_parser('export'); p.add_argument('rom'); p.add_argument('sample', type=num); p.add_argument('out'); p.set_defaults(fn=cmd_export)
    p = sub.add_parser('replace'); p.add_argument('rom'); p.add_argument('sample', type=num); p.add_argument('infile'); p.add_argument('out')
    p.add_argument('--at', type=num); p.add_argument('--loop', action='store_true'); p.set_defaults(fn=cmd_replace)
    a = ap.parse_args(); a.fn(a)

if __name__ == '__main__':
    main()
