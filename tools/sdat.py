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
    def instrument_wave(self, b, prog):
        """-> (wavearc index, wave index) of a PCM instrument"""
        f, was = self.bank(b)
        fr, off = struct.unpack_from('<BH', f, 0x3c + prog * 4)
        if fr not in (1, 2, 3, 4, 5): return None
        swav, swar = struct.unpack_from('<HH', f, off)
        return was[swar], swav
    def first_note(self, data):
        """first (program, key) of a sequence byte stream"""
        p = 0; prog = 0
        while p < len(data):
            b = data[p]
            if b == 0xff: break
            if b == 0x81:
                v = 0; p += 1
                while True:
                    c = data[p]; p += 1; v = (v << 7) | (c & 0x7f)
                    if not c & 0x80: break
                prog = v; continue
            if b < 0x80: return prog, b
            if b == 0x80:
                p += 1
                while data[p] & 0x80: p += 1
                p += 1; continue
            if 0xc0 <= b <= 0xd6: p += 2; continue
            if b in (0xe0, 0xe1, 0xe3): p += 3; continue
            if b == 0x93: p += 5; continue
            if b in (0x94, 0x95): p += 4; continue
            if b == 0xfe: p += 3; continue
            p += 1
        return None
    def se_wave(self, se):
        """SE id (as the game's play-SE function receives it, after language remap) ->
        (wavearc index, wave index).  Ids beyond the SEQ table (and a few special ones) live in
        the sequence archive; the sub-sequence index is the id itself."""
        n_seq = struct.unpack_from('<I', self.s, self.info_off + self.irecs[0])[0]
        if se < n_seq and self.seq_info(se) is not None:
            fid, bnk = self.seq_info(se)
            f = self.file(fid)
            doff = struct.unpack_from('<I', f, 0x18)[0]
            pn = self.first_note(f[doff:doff + 256])
        else:
            arc = self.seqarc_file(0)
            dataoff = struct.unpack_from('<I', arc, 0x18)[0]
            off, bnk = struct.unpack_from('<IH', arc, 0x20 + se * 12)
            pn = self.first_note(arc[dataoff + off: dataoff + off + 64])
        if pn is None: return None
        return self.instrument_wave(bnk, pn[0])
    def wave(self, wa, wi):
        """-> (rate, pcm16 list)"""
        w = self.wavearc(wa)[wi]
        return w[1], w[4]
