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

## Compared with the DS version

What differs between the two games' sound, and what the English build does about it (0.14):

* **Sound numbers** are the same on both machines: the GBA's song numbers are the DS's SSEQ /
  sequence-archive ids, for music and effects, in the script (`0x05`, `0x06`) and in the code
  (the engine's own calls to `0x08015bc8` use the ids the DS's calls to `0x02025484` use, apart
  from the DS's touch-screen sounds). The one exception is a looping effect the DS numbers
  `0x197` and the GBA `0x17c`; the script converter learns that from the two Japanese scripts
  and turns it back.
* **Language.** The DS swaps only the twelve shouts per language (the table above); the English
  build puts the DS's English clips in their place (`patches/voices.py`).
* **The script's sounds.** The DS's English script plays the same sounds as its Japanese one.
  Up to 0.13 the converter dropped every DS command that has no counterpart in the GBA's script,
  and three of those were sounds: `0x175` and the looping `0x187` at the end of episode 2's trial
  (bank 12, section 17), and the command that stops `0x187` again in episode 5 (bank 38, section
  29; without it the loop went on). They are kept now. The GBA's script has two sound commands
  the DS's has not, in bank 39, section 59 (`0xa4` stopped, then `0xa5`, its fade-out): `0xa4`
  loops on the GBA, so they stay.
* **The verdict.** The DS's English verdict slams once a letter (Guilty six times) with a short
  shake of the screen where the Japanese one flashes once a word; the English build does the
  same (see graphics.md, "The verdict").
* **Text blips.** The DS's English text runs faster and blips on every other letter (every third
  at the fastest speeds), the typewriter included, never on a space; the GBA's blips on every
  other letter of its first two rows only, the typewriter on every letter. The English build
  takes the DS's pace and blips, on all three rows (see text-engine.md, "Pace and text blips").
* **The recordings.** Nearly every effect is the same recording on both machines; the DS keeps
  most at 15 768 or 22 050 Hz where the GBA has 10 512 Hz. A few ambient effects that the GBA
  makes from one short looping noise sample (`0x80f156c`), shaped by its sequence's volume
  (`0x176`, `0x177`, `0x17a`–`0x17d`, `0x187`, `0x188`, `0x195`), are longer recordings of their
  own on the DS, and a few short ones are cut differently (`0x76`, `0x9d`, `0x135`, `0x18e`).
  The English build keeps the GBA's samples.
