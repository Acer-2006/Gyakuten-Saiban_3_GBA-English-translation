#!/usr/bin/env python3
"""Minimal MP2K (sappy) song/instrument reader for the GBA ROM."""
import struct

SONG_TABLE = 0x54824     # mp2k song table (406 entries of {header ptr, player, player})
NSONG = 406

def is_ptr(g, v): return 0x08000000 <= v < 0x08000000 + len(g)

def song(g, k):
    ptr, ms, me = struct.unpack_from('<IHH', g, SONG_TABLE + k * 8)
    a = ptr - 0x08000000
    tc = g[a]; tone = struct.unpack_from('<I', g, a + 4)[0]
    tracks = [struct.unpack_from('<I', g, a + 8 + t * 4)[0] - 0x08000000 for t in range(tc)]
    return {'hdr': a, 'tracks': tracks, 'tone': (tone - 0x08000000) if tone else None, 'ms': ms, 'me': me}

def track_events(g, p, limit=20000):
    """Yield (cmd, args) for a track: VOICE (0xbd, n), notes (note, key, vel), FINE."""
    out = []; last_cmd = None; last_key = 0; last_vel = 0; n = 0
    while n < limit:
        b = g[p]; n += 1
        if b >= 0x80:
            last_cmd = b
            if b == 0xb1: out.append(('FINE', ())); break
            if b == 0xb2: out.append(('GOTO', struct.unpack_from('<I', g, p + 1)[0])); break   # loop
            if b == 0xb3: p += 5; continue
            if b == 0xb4: p += 1; continue
            if b == 0xb5: p += 2; continue
            if b in (0xb9,): p += 4; continue
            if b in (0xba, 0xbb, 0xbc, 0xbd, 0xbe, 0xbf, 0xc0, 0xc1, 0xc2, 0xc3, 0xc4, 0xc5, 0xc8):
                arg = g[p + 1]; out.append((b, arg)); p += 2; continue
            if b == 0xcd: p += 3; continue
            if b in (0xce, 0xcf) or b >= 0xd0:
                p += 1
                # optional key, vel, gate
                if g[p] < 0x80: last_key = g[p]; p += 1
                if g[p] < 0x80: last_vel = g[p]; p += 1
                if g[p] < 0x80: p += 1
                out.append(('NOTE', (b, last_key, last_vel))); continue
            if b <= 0xb0: p += 1; continue   # wait
            p += 1; continue
        else:
            # running status
            if last_cmd in (0xce, 0xcf) or (last_cmd or 0) >= 0xd0:
                last_key = b; p += 1
                if g[p] < 0x80: last_vel = g[p]; p += 1
                if g[p] < 0x80: p += 1
                out.append(('NOTE', (last_cmd, last_key, last_vel))); continue
            if last_cmd in (0xbd, 0xbe, 0xbf, 0xc0, 0xc1, 0xc2, 0xc3, 0xc4, 0xc5, 0xc8):
                out.append((last_cmd, b)); p += 1; continue
            p += 1
    return out

def instrument_sample(g, tone, prog, key):
    """-> ROM offset of the sample header played by instrument `prog` at `key`, or None."""
    e = tone + prog * 12
    typ = g[e]
    if typ == 0x40:    # keysplit
        sub = struct.unpack_from('<I', g, e + 4)[0] - 0x08000000
        ks = struct.unpack_from('<I', g, e + 8)[0] - 0x08000000
        e = sub + g[ks + key] * 12; typ = g[e]
    elif typ == 0x80:  # drum
        sub = struct.unpack_from('<I', g, e + 4)[0] - 0x08000000
        e = sub + key * 12; typ = g[e]
    if typ & 0x07: return None
    p = struct.unpack_from('<I', g, e + 4)[0]
    return p - 0x08000000 if is_ptr(g, p) else None

def song_samples(g, k):
    s = song(g, k)
    if s['tone'] is None: return []
    res = []
    for t in s['tracks']:
        prog = 0
        for cmd, arg in track_events(g, t):
            if cmd == 0xbd: prog = arg
            elif cmd == 'NOTE':
                smp = instrument_sample(g, s['tone'], prog, arg[1])
                if smp is not None and smp not in [r[1] for r in res]: res.append((prog, smp))
    return res
