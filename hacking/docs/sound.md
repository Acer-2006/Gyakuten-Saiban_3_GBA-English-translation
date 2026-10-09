# Sound

The GBA game uses Nintendo's MP2K ("Sappy") driver. Addresses are for A3JJ.

## Driver tables

| Address | What |
| --- | --- |
| `0x080547f4` | music player table (`MPlayTable`) |
| `0x08054824` | song table: 406 entries of `{u32 header, u16 player, u16 player}` |
| `0x08038bd0` | `m4aSongNumStart(song)` — play song number `song` |
| `0x08015bc8` | the game's sound-effect wrapper; its argument is the song number |

Song numbers are shared by music and effects: the script's sound commands and the game's own
calls all end up in `m4aSongNumStart`.

### Song header

```
u8  trackCount
u8  blockCount
u8  priority
u8  reverb
u32 voicegroup          ; "tone" table, 12-byte instruments
u32 track[trackCount]   ; pointers to the track event streams
```

### Instrument (voicegroup entry, 12 bytes)

```
u8  type      ; 0 / 8 = PCM sample, 1/2/9/10 square, 3/11 wave, 4/12 noise, 0x40 key split, 0x80 drum set
u8  key
u8  length
u8  pan_sweep
u32 sample    ; PCM: sample header; 0x40 / 0x80: sub voicegroup
u32 envelope  ; PCM: attack, decay, sustain, release; 0x40: key-split table
```

`gs3_sound.py` follows key splits and drum sets the same way the driver does.

### PCM sample header

```
u16 type       ; 0
u16 status     ; 0x4000 = looped
u32 rate       ; frequency << 10 (10512 Hz → 0x2a40000)
u32 loopStart
u32 size
s8  data[size] ; signed 8-bit PCM
```

### Track events used by the tools

`0xbd n` selects instrument `n`; `0xce`/`0xcf` and `0xd0`–`0xff` are notes (`key`, `velocity`
and gate time as optional sub-0x80 bytes, running status allowed); `0xb1` ends the track;
`0xb2 ptr` loops. `gs3_sound.py songs` walks the tracks far enough to list every sample a song
can play.

## The shouts

Twelve songs are the voiced shouts ("Objection!", "Hold it!", "Take that!" in the three voices):

```
0x37 0x38 0x39 0x47 0x51 0x96 0x16f 0x170 0x171 0x172 0x173 0x174
```

Each is one track with one PCM instrument and one sample (10512 Hz, about 1.3 s). Which voice is
used is decided by the chapter number at `SYS+0xc1` (`0x03003871`) in the code at `0x08013490`
and `0x0801460e`: chapters `<= 1`, `0xc`, `0xd` → Mia's set, `0xf`–`0x11` → Edgeworth's,
everything else → Phoenix's.

Replacing a shout is `gs3_sound.py replace`: it writes a new sample header + data (into free
space) and repoints every instrument that used the old sample, so the song itself is untouched.

## Nintendo DS side (for reference)

Trials and Tribulations keeps its audio in `sound_data.sdat` (SYMB / INFO / FAT / FILE blocks).
The play-SE function at `0x02025484` remaps a dozen sound numbers per language through the table
at `0x020a1d08` (12 entries, `u32[6]`, one id per language, 0x18 bytes apart). Ids up to `0x1fa`
are SSEQ records; higher ones are entries of sequence archive 0 (`0x20 + id * 12` →
`{u32 offset, u16 bank, u8 volume, ...}`) whose banks point at the voice SWAR waves
(16 000 Hz, about 1.3 s). `tools/sdat.py` in the build tool reads all of this.
