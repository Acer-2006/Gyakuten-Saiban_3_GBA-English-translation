"""Voice clips: the DS English recordings replace the GBA samples of the voiced shouts.

The DS play-SE function swaps a dozen sound numbers for language-specific ones (a table of
{japanese id, id for every other language} entries in arm9).  The sound numbers are the same on
both machines, so for each pair we take the GBA song, follow its instrument to the sample, and
point that instrument at a new sample built from the DS wave (decoded, scaled to the loudness
of the clip it replaces, stored as signed 8-bit PCM).

The sample's rate: an instrument of the pitched kind (type 0) plays a sample at the rate in its
header, so the DS clip keeps its own.  A fixed instrument (type 8, five of the shouts) plays its
sample straight at the mixer's output rate, which is the rate the GBA's own clips are recorded at
(10512 Hz), whatever the header says; a DS clip stored at 16 kHz came out a third deeper and
slower.  For those the clip is resampled to the GBA clip's rate.

A DS sound can be more than one note.  Eleven of the twelve are one wave each; Franziska's English
Objection! (0x1fa, for the GBA's 0x96) is two tracks playing together: a noisy layer with no voice
in it (velocity 101) and her voice (velocity 127), the voice the second.  Until 0.16.84 the build
took the first note of the first track only, so her Objection! was the noisy layer alone, without
the word.  The clip is now mixed from every note as the DS's sound driver plays them (velocity and
attack, tools/sdat.py `se_sound`); it is as long as the longest wave, the first, so its size is
what it was.  It is scaled by its voice's peak, as a one-wave clip is by its own, which keeps it
as loud beside the other shouts as it is on the DS (scaled by the mix's own peak, where the two
layers add up, it came out a quarter quieter); 81 of its 29320 samples, where the layers add up,
are cut at the 8-bit range.
"""
import os, sys, struct
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
import mp2k, resample
from sdat import SdatEx
FIXED = 0x08                  # instrument type bit: the sample plays at the mixer's rate

DS_VOICE_TABLE = 0x20a1d08    # u32[6] per entry (one id per language), 12 entries, 0x18 apart
DS_VOICE_COUNT = 12
DS_ARM9_BASE = 0x2000000
ENGLISH = 1

def apply(rom, ctx):
    sd = SdatEx(ctx.sdat)
    g = bytes(rom.d[:rom.orig_size])
    done = fixed = layered = 0
    for k in range(DS_VOICE_COUNT):
        ids = struct.unpack_from('<6I', ctx.arm9, DS_VOICE_TABLE - DS_ARM9_BASE + k * 0x18)
        jp, en = ids[0], ids[ENGLISH]
        # GBA side: the (only) sample the Japanese song plays
        samples = mp2k.song_samples(g, jp)
        if len(samples) != 1:
            print(f"  voice {jp:#x}: expected one sample, found {len(samples)}; skipped"); continue
        prog, smp = samples[0]
        tone = mp2k.song(g, jp)['tone']
        entry = tone + prog * 12
        assert struct.unpack_from('<I', g, entry + 4)[0] == 0x08000000 + smp
        # DS side: the sound as the DS plays it (all its notes; one wave for all but one)
        snd = sd.se_sound(en)
        if snd is None:
            print(f"  voice {jp:#x}: DS sound {en:#x} not found; skipped"); continue
        rate, pcm, ds_peak = snd
        mixed = len(sd.se_notes(en)) > 1
        layered += mixed
        t, st, freq, loop, size = struct.unpack_from('<HHIII', g, smp)
        if g[entry] & FIXED:
            pcm, rate = resample.scale_1d(pcm, round(len(pcm) * (freq >> 10) / rate)), freq >> 10
        # loudness: match the peak of the clip being replaced.  A mix is scaled by its loudest
        # layer's peak, so it is as loud beside the other shouts as on the DS; the few samples
        # where its layers add up beyond that are cut at the 8-bit range.
        old = g[smp + 16: smp + 16 + size]
        old_peak = max(1, max(abs(b - 256 if b > 127 else b) for b in old))
        new_peak = max(1, ds_peak if mixed else max(abs(v) for v in pcm))
        scale = old_peak / new_peak
        data = bytes((max(-128, min(127, int(round(v * scale)))) & 0xff) for v in pcm)
        hdr = struct.pack('<HHIII', 0, 0, rate << 10, 0, len(data))
        addr = rom.store(hdr + data + b'\0' * 16, 'ext', 4, f'voice {jp:#x}')
        rom.w32(0x08000000 + entry + 4, addr)
        done += 1; fixed += bool(g[entry] & FIXED)
    print(f"  voices: {done} clips replaced ({fixed} resampled to the mixer's rate, {layered} mixed from two recordings)")
