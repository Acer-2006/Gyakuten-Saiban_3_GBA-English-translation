"""Voice clips: the DS English recordings replace the GBA samples of the voiced shouts.

The DS play-SE function swaps a dozen sound numbers for language-specific ones (a table of
{japanese id, id for every other language} entries in arm9).  The sound numbers are the same on
both machines, so for each pair we take the GBA song, follow its instrument to the sample, and
point that instrument at a new sample built from the DS wave (decoded, scaled to the loudness
of the clip it replaces, stored as signed 8-bit PCM).

The sample's rate: every clip is converted to the mixer's output rate, 10512 Hz, the rate the
GBA's own clips are recorded at, with a band-limiting filter (tools/resample.py `band_limited`:
nothing above about 5.1 kHz, the most the mixer can carry, is left in it).  A fixed instrument
(type 8, five of the shouts) plays its sample straight at the mixer's rate whatever the header
says (a DS clip stored at 16 kHz came out a third deeper and slower, until 0.15.5); an instrument
of the pitched kind (type 0, the other seven) plays it at the rate in its header.  Until 0.16.85
those seven kept the DS's rate (16 kHz, Franziska's 22 kHz), and the mixer brought them down to
its own as it played them, without a filter: what lay above its half folded back into the
voice, a harshness on the "-jec-tion" and the like; the five were converted with Lanczos-3
(resample.scale_1d), which dulls the top of the band.  Now all twelve are converted the same way,
as the maintainer's English GS2 stores its clips.  Each keeps the room it had in 0.16.84 (the
rest zeros), so nothing stored after the voices moves and savestates keep working.

A DS sound can be more than one note.  Eleven of the twelve are one wave each; Franziska's English
Objection! (0x1fa, for the GBA's 0x96) is two tracks playing together: a noisy layer with no voice
in it (velocity 101) and her voice (velocity 127), the voice the second.  Until 0.16.84 the build
took the first note of the first track only, so her Objection! was the noisy layer alone, without
the word.  The clip is now mixed from every note as the DS's sound driver plays them (velocity and
attack, tools/sdat.py `se_sound`); it is as long as the longest wave, the first, so its size is
what it was.  It is scaled by its voice's peak, as a one-wave clip is by its own, which keeps it
as loud beside the other shouts as it is on the DS (scaled by the mix's own peak, where the two
layers add up, it came out a quarter quieter); a few dozen samples, where the layers add up, are
cut at the 8-bit range (81 of 29320 at the DS's rate; at the mixer's, 38 of 13978 are at its ends).
"""
import os, sys, struct
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
import mp2k, resample
from sdat import SdatEx
FIXED = 0x08                  # instrument type bit: the sample plays at the mixer's rate
MIXER_RATE = 10512            # the sound driver's output rate (SoundInfo pcmFreq), the Japanese clips' rate

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
        if freq >> 10 != MIXER_RATE:
            raise SystemExit(f'voice {jp:#x}: the Japanese clip is at {freq >> 10} Hz, not the mixer\'s {MIXER_RATE}')
        # the room the clip had until 0.16.84 (the DS rate's length; a fixed instrument's at the
        # mixer's rate), kept so that nothing stored after the voices moves
        room = round(len(pcm) * MIXER_RATE / rate) if g[entry] & FIXED else len(pcm)
        pcm, rate = resample.band_limited(pcm, rate, MIXER_RATE), MIXER_RATE
        # loudness: match the peak of the clip being replaced.  A mix is scaled by its loudest
        # layer's peak, so it is as loud beside the other shouts as on the DS; the few samples
        # where its layers add up beyond that are cut at the 8-bit range.
        old = g[smp + 16: smp + 16 + size]
        old_peak = max(1, max(abs(b - 256 if b > 127 else b) for b in old))
        new_peak = max(1, ds_peak if mixed else max(abs(v) for v in pcm))
        scale = old_peak / new_peak
        data = bytes((max(-128, min(127, int(round(v * scale)))) & 0xff) for v in pcm)
        if len(data) > room: raise SystemExit(f'voice {jp:#x}: {len(data)} samples, room for {room}')
        hdr = struct.pack('<HHIII', 0, 0, rate << 10, 0, len(data))
        addr = rom.store(hdr + data + b'\0' * (room - len(data) + 16), 'ext', 4, f'voice {jp:#x}')
        rom.w32(0x08000000 + entry + 4, addr)
        done += 1; fixed += bool(g[entry] & FIXED)
    print(f"  voices: {done} clips replaced, all converted to the mixer's {MIXER_RATE} Hz "
          f"({fixed} on fixed instruments, {layered} mixed from two recordings)")
