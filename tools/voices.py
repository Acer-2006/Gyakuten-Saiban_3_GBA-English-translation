#!/usr/bin/env python3
"""Voice clips: export the GBA's shout samples for identification, and install replacements.

The GBA plays its shouts through the mp2k sound driver from 8-bit PCM samples in ROM.  Put your
recordings in the `voices/` folder next to build.py together with a `voices.json` that says which
sample each file replaces:

    {"0xed1c0": "mia_take_that.wav", ...}

Keys are the sample offsets printed by `build.py --export-voices DIR` (which writes every
candidate sample as a .wav so you can hear which one is which).  WAV files are read directly;
other formats are converted with ffmpeg when it is installed.  A replacement is resampled to at
most 22 kHz, converted to signed 8-bit, stored in the expanded ROM, and every instrument that
pointed at the old sample is repointed at it.
"""
import os, struct, json, wave, subprocess, shutil

MAX_RATE = 22050

def samples(g):
    """All mp2k sample headers in the ROM: list of (offset, rate, size, looped)."""
    out = []
    for i in range(0, len(g) - 16, 4):
        t, st, freq, loop, size = struct.unpack_from('<HHIII', g, i)
        if t == 0 and st in (0, 0x4000) and freq % 1024 == 0 and 4000 <= freq // 1024 <= 48000 \
                and 100 < size < 2000000 and i + 16 + size <= len(g) and loop <= size:
            out.append((i, freq // 1024, size, bool(st & 0x4000)))
    return out

def candidates(g):
    """The shouts are unlooped 10.5 kHz clips of about a second: list of (offset, rate, size)."""
    return [(off, rate, size) for off, rate, size, looped in samples(g)
            if not looped and rate <= 11000 and 0.6 <= size / rate <= 2.0]

def write_wav(path, rate, pcm16):
    w = wave.open(path, 'wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
    w.writeframes(struct.pack('<%dh' % len(pcm16), *pcm16)); w.close()

def export(ctx, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    g = ctx.gba; n = 0
    for off, rate, size in candidates(g):
        pcm = [((b - 256) if b > 127 else b) << 8 for b in g[off + 16: off + 16 + size]]
        write_wav(os.path.join(out_dir, f'{off:#x}_{size / rate:.2f}s.wav'), rate, pcm); n += 1
    print(f'  {n} samples written to {out_dir}')

def read_clip(path):
    """-> (rate, mono pcm16 list).  WAV directly, anything else through ffmpeg."""
    if not path.lower().endswith('.wav'):
        if not shutil.which('ffmpeg'):
            raise SystemExit(f'{path}: only .wav files can be read without ffmpeg installed')
        tmp = path + '.tmp.wav'
        subprocess.check_call(['ffmpeg', '-v', 'error', '-y', '-i', path, '-ac', '1', '-ar', str(MAX_RATE), tmp])
        try: return read_clip(tmp)
        finally: os.remove(tmp)
    w = wave.open(path, 'rb')
    ch, sw, rate, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
    raw = w.readframes(n); w.close()
    if sw == 2: s = list(struct.unpack('<%dh' % (len(raw) // 2), raw))
    elif sw == 1: s = [(b - 128) << 8 for b in raw]
    elif sw == 3: s = [struct.unpack('<i', raw[i:i + 3] + (b'\xff' if raw[i + 2] & 0x80 else b'\0'))[0] >> 8 for i in range(0, len(raw), 3)]
    else: raise SystemExit(f'{path}: unsupported sample width {sw}')
    if ch > 1: s = [sum(s[i:i + ch]) // ch for i in range(0, len(s) - ch + 1, ch)]
    return rate, s

def to_pcm8(pcm16, rate, max_rate=MAX_RATE):
    """Resample (linear) down to max_rate if needed; normalise; signed 8-bit bytes."""
    if rate > max_rate:
        n = int(len(pcm16) * max_rate / rate); out = []
        for i in range(n):
            x = i * rate / max_rate; j = int(x); f = x - j
            a = pcm16[j]; b = pcm16[min(j + 1, len(pcm16) - 1)]
            out.append(int(a + (b - a) * f))
        pcm16, rate = out, max_rate
    peak = max(1, max(abs(v) for v in pcm16))
    scale = 30000 / peak
    data = bytes((max(-128, min(127, int(v * scale) >> 8))) & 0xff for v in pcm16)
    return rate, data

def apply(rom, ctx, folder):
    """Install the clips listed in folder/voices.json.  Returns the number installed."""
    mapping_path = os.path.join(folder, 'voices.json')
    if not os.path.exists(mapping_path): return 0
    mapping = json.load(open(mapping_path))
    g = bytes(rom.d[:rom.orig_size])
    known = {off for off, _, _, _ in samples(g)}
    n = 0
    for key, fname in mapping.items():
        off = int(key, 0)
        if off not in known: raise SystemExit(f'voices.json: {key} is not a sample in the GBA ROM')
        rate, pcm = read_clip(os.path.join(folder, fname))
        rate, data = to_pcm8(pcm, rate)
        hdr = struct.pack('<HHIII', 0, 0, rate * 1024, 0, len(data))
        blob = hdr + data + b'\0' * ((-len(data)) & 3) + b'\0' * 16
        new = rom.store(blob, 'ext', 4, f'voice {fname}')
        old = 0x08000000 + off
        refs = [i for i in range(0, len(g) - 4, 4) if struct.unpack_from('<I', g, i)[0] == old]
        if not refs: raise SystemExit(f'voices.json: nothing in the ROM refers to sample {key}')
        for r in refs: rom.w32(0x08000000 + r, new)
        n += 1
    print(f'  voices: {n} clips installed')
    return n
