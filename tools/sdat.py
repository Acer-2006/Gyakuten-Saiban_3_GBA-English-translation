#!/usr/bin/env python3
"""Nitro SDAT reader: wave archives (SWAR) and ADPCM/PCM decoding (pure Python)."""
import struct

IMA_STEP = [7,8,9,10,11,12,13,14,16,17,19,21,23,25,28,31,34,37,41,45,50,55,60,66,73,80,88,97,107,118,130,143,
            157,173,190,209,230,253,279,307,337,371,408,449,494,544,598,658,724,796,876,963,1060,1166,1282,1411,
            1552,1707,1878,2066,2272,2499,2749,3024,3327,3660,4026,4428,4871,5358,5894,6484,7132,7845,8630,9493,
            10442,11487,12635,13899,15289,16818,18500,20350,22385,24623,27086,29794,32767]
IMA_IDX = [-1,-1,-1,-1,2,4,6,8]

class Sdat:
    def __init__(self, s):
        self.s = s
        self.symb_off, self.symb_sz, self.info_off, self.info_sz, self.fat_off, self.fat_sz, self.file_off, self.file_sz = struct.unpack_from('<8I', s, 0x10)
        self.recs = struct.unpack_from('<8I', s, self.symb_off + 8)
        self.irecs = struct.unpack_from('<8I', s, self.info_off + 8)
        self.wavearc_names = self._names(3)
        self.bank_names = self._names(2)
    def _names(self, kind):
        s = self.s; off = self.recs[kind]
        n = struct.unpack_from('<I', s, self.symb_off + off)[0]
        out = []
        for i in range(n):
            p = struct.unpack_from('<I', s, self.symb_off + off + 4 + i * 4)[0]
            if p == 0: out.append(None); continue
            q = self.symb_off + p; e = s.index(b'\0', q); out.append(s[q:e].decode())
        return out
    def file(self, fid):
        o, sz = struct.unpack_from('<II', self.s, self.fat_off + 12 + fid * 16); return self.s[o:o + sz]
    def wavearc(self, idx):
        """-> list of (fmt, rate, loop, loopstart, pcm16 samples list)"""
        p = struct.unpack_from('<I', self.s, self.info_off + self.irecs[3] + 4 + idx * 4)[0]
        fid = struct.unpack_from('<H', self.s, self.info_off + p)[0]
        w = self.file(fid)
        cnt = struct.unpack_from('<I', w, 0x38)[0]
        offs = struct.unpack_from('<%dI' % cnt, w, 0x3c)
        out = []
        for wo in offs:
            fmt, loop, rate, timer, loopst, nlen = struct.unpack_from('<BBHHHI', w, wo)
            data = w[wo + 12: wo + 12 + (loopst + nlen) * 4]
            out.append((fmt, rate, loop, loopst, decode(fmt, data)))
        return out

def decode(fmt, data):
    if fmt == 0: return [(b - 256 if b > 127 else b) << 8 for b in data]
    if fmt == 1: return list(struct.unpack('<%dh' % (len(data) // 2), data[:len(data) // 2 * 2]))
    # IMA ADPCM: 4-byte header (initial predictor s16, step index u16)
    pred, idx = struct.unpack_from('<hH', data, 0)
    out = []
    for b in data[4:]:
        for nib in (b & 15, b >> 4):
            step = IMA_STEP[idx]
            diff = step >> 3
            if nib & 1: diff += step >> 2
            if nib & 2: diff += step >> 1
            if nib & 4: diff += step
            pred = pred - diff if nib & 8 else pred + diff
            pred = max(-32768, min(32767, pred))
            idx = max(0, min(88, idx + IMA_IDX[nib & 7]))
            out.append(pred)
    return out

# ---- lookups used by the voice port --------------------------------------------------------
class SdatEx(Sdat):
    def seq_info(self, i):
        """SEQ i -> (file id, bank) or None"""
        p = struct.unpack_from('<I', self.s, self.info_off + self.irecs[0] + 4 + i * 4)[0]
        if p == 0: return None
        fid, _, bnk = struct.unpack_from('<HHH', self.s, self.info_off + p)
        return fid, bnk
    def seqarc_file(self, i=0):
        p = struct.unpack_from('<I', self.s, self.info_off + self.irecs[1] + 4 + i * 4)[0]
        return self.file(struct.unpack_from('<H', self.s, self.info_off + p)[0])
    def bank(self, b):
        """bank b -> (SBNK bytes, [wavearc indices])"""
        p = struct.unpack_from('<I', self.s, self.info_off + self.irecs[2] + 4 + b * 4)[0]
        fid, _ = struct.unpack_from('<HH', self.s, self.info_off + p)
        was = struct.unpack_from('<4H', self.s, self.info_off + p + 4)
        return self.file(fid), [w for w in was if w != 0xffff]
    def instrument(self, b, prog):
        """-> (wavearc index, wave index, attack) of a single-wave PCM instrument, or None"""
        f, was = self.bank(b)
        fr, off = struct.unpack_from('<BH', f, 0x3c + prog * 4)
        if fr not in (1, 2, 3, 4, 5): return None
        swav, swar, _key, attack = struct.unpack_from('<HHBB', f, off)
        return was[swar], swav, attack
    @staticmethod
    def notes(data, base, start):
        """Every note of a sequence: data is the file, base where its track offsets count from
        (its data block), start where track 0 begins.  -> list of (tick, program, key,
        velocity), tracks opened with 0x93 included.  Only what sound effects use is read: a
        jump, call or variable command raises ValueError."""
        def varlen(p):
            v = 0
            while True:
                c = data[p]; p += 1; v = (v << 7) | (c & 0x7f)
                if not c & 0x80: return v, p
        out, todo = [], [start]
        while todo:
            p = todo.pop(0); tick = prog = 0; mono = False
            while True:
                b = data[p]
                if b in (0xff, 0xfd): break
                if b < 0x80:                                   # note: key, velocity, length
                    length, q = varlen(p + 2)
                    out.append((tick, prog, b, data[p + 1]))
                    if mono: tick += length                    # mono: the note waits its length
                    p = q
                elif b == 0x80: v, p = varlen(p + 1); tick += v            # rest
                elif b == 0x81: prog, p = varlen(p + 1)                    # program
                elif b == 0x93:                                            # open track
                    todo.append(base + (data[p + 2] | data[p + 3] << 8 | data[p + 4] << 16)); p += 5
                elif b == 0xfe: p += 3                                     # tracks used
                elif b == 0xc7: mono = bool(data[p + 1]); p += 2           # mono / poly
                elif 0xc0 <= b <= 0xd6: p += 2
                elif b in (0xe0, 0xe1, 0xe3): p += 3
                else: raise ValueError(f'sequence command {b:#x} at {p:#x}')
        return out
    def se_notes(self, se):
        """SE id (as the game's play-SE function receives it, after language remap) -> every note
        it plays: list of (tick, wavearc index, wave index, velocity, attack).  Ids beyond the
        SEQ table (and a few special ones) live in the sequence archive; the sub-sequence index
        is the id itself."""
        n_seq = struct.unpack_from('<I', self.s, self.info_off + self.irecs[0])[0]
        if se < n_seq and self.seq_info(se) is not None:
            fid, bnk = self.seq_info(se)
            data = self.file(fid)
            base = start = struct.unpack_from('<I', data, 0x18)[0]
        else:
            data = self.seqarc_file(0)
            base = struct.unpack_from('<I', data, 0x18)[0]
            off, bnk = struct.unpack_from('<IH', data, 0x20 + se * 12)
            start = base + off
        out = []
        for tick, prog, key, vel in self.notes(data, base, start):
            ins = self.instrument(bnk, prog)
            if ins is None: raise ValueError(f'SE {se:#x}: program {prog} is not a PCM instrument')
            out.append((tick,) + ins[:2] + (vel, ins[2]))
        return out
    def wave(self, wa, wi):
        """-> (rate, pcm16 list)"""
        w = self.wavearc(wa)[wi]
        return w[1], w[4]
    def se_sound(self, se):
        """SE id -> (rate, samples, peak): the sound as the DS plays it.  One note is its wave as
        it is; several notes starting together (Franziska's English Objection!: her voice and a
        quieter second layer) are mixed as the sound driver mixes them, each at its velocity's
        volume with its instrument's attack, as long as the longest.  peak is the loudest
        layer's peak as heard (one wave: its own), the level to scale the sound by: where the
        layers add up a mix goes beyond it."""
        notes = self.se_notes(se)
        if not notes: return None
        if any(t for t, *_ in notes): raise ValueError(f'SE {se:#x}: a note does not start at once')
        layers = [(self.wave(wa, wi), vel, atk) for _, wa, wi, vel, atk in notes]
        rate = layers[0][0][0]
        if any(r != rate for (r, _), _, _ in layers): raise ValueError(f'SE {se:#x}: waves at different rates')
        if len(layers) == 1 and layers[0][1] == 127 and layers[0][2] == 127:
            pcm = layers[0][0][1]
            return rate, pcm, max(abs(v) for v in pcm)
        out, peak = [0.0] * max(len(pcm) for (_, pcm), _, _ in layers), 0
        for (_, pcm), vel, atk in layers:
            g = velocity_gain(vel)
            peak = max(peak, g * max(abs(v) for v in pcm))
            for i, (v, e) in enumerate(zip(pcm, attack_envelope(atk, len(pcm), rate))):
                out[i] += v * g * e
        return rate, out, peak

# The DS sound driver's volume curves (NitroSDK): a note's velocity sets its volume in tenths of
# a decibel from the square of velocity / 127; the attack starts the envelope at -92544 (-72.3 dB in
# 1/128ths of a tenth) and multiplies it by the attack rate / 256 once a sound frame (64 * 2728
# cycles of the 33.51 MHz clock), before the frame is heard, until it reaches 0 dB.  Attack 127 is
# instant.
ATTACK_RATES = (0x00, 0x01, 0x05, 0x0e, 0x1a, 0x26, 0x33, 0x3f, 0x49, 0x54, 0x5c, 0x64, 0x6d, 0x74,
                0x7b, 0x7f, 0x84, 0x89, 0x8f)      # attack 127 down to 109; below that 255 - attack
SOUND_FRAME = 64 * 2728 / 33513982

def velocity_gain(vel):
    return (vel / 127) ** 2

def attack_envelope(attack, n, rate):
    """Amplitude (0..1) of each of n samples at rate under the attack."""
    k = ATTACK_RATES[127 - attack] if attack >= 109 else 255 - attack
    env, out, f = -92544, [], 0
    while len(out) < n:
        env = -((-env * k) >> 8)
        f += 1
        out.extend([10 ** ((env >> 7) / 200)] * (round(f * rate * SOUND_FRAME) - len(out)))
    return out[:n]
