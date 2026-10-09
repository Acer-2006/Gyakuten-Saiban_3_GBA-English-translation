# Tools

All tools live in `hacking/tools/` and need Python 3.8 or newer. They import the build tool's
library from `tools/` and the tables from `data/`, so run them from a checkout of the repository
(any working directory is fine). Every tool prints its usage with `--help`. Addresses can be
given as ROM addresses (`0x0826deb0`) or offsets (`0x26deb0`); numbers accept `0x`.

Optional extras: `pillow` (reading PNG files in formats the small built-in reader does not
handle; PNG writing never needs it), `capstone` (only for `gs3_dis.py dis`).

None of the tools contain game data. They read your ROM and write what you ask for.

## gs3_script.py — script text

```
gs3_script.py list   rom.gba
gs3_script.py dump   rom.gba 3 bank3.txt --table jp
gs3_script.py insert rom.gba 3 bank3.txt out.gba --table jp
gs3_script.py table  mytable.tsv --table jp
```

* `list` shows every bank with its address, stored size, decompressed size and section count,
  and marks partial banks (see [script-format.md](script-format.md)) and label entries.
* `dump` writes a bank as text: `@section N` headers, commands as `{xx a b}`, characters through
  the table or as `[xxx]`. A dump re-inserts byte for byte, including the stale entries of partial
  banks (`@section N stale 0x...`) and the label entries of command `0x36` (`{@N}` anchors in the
  text, so moving text around keeps the label pointing at the same spot).
* `insert` rebuilds the bank. If the compressed bank still fits where it was, it goes back in
  place; otherwise it is written to free space (the ROM grows to 16 MB if needed) and every
  pointer to the old bank is updated. On a ROM made by the English build the banks are stored
  uncompressed and the tool keeps it that way (it reads and updates the bank directory at
  `0x08800000`), so the same commands edit the English text.
* Tables: `en` is the English build's font layout, `jp` the Japanese font (Latin, kana and
  punctuation; kanji stay as `[hex]` until you add them). Write your own with `table` as a
  starting point; the font sheet from `gs3_font.py` gives you the code of every glyph.

Characters that are not in the table can always be written as `[hex]`. Keep the number of
arguments of every command as in the table in script-format.md — the tool refuses anything else.

## gs3_lz.py — LZ77 blocks

```
gs3_lz.py d    rom.gba 0x08254d24 block.bin
gs3_lz.py c    block.bin block.lz
gs3_lz.py scan rom.gba
```

`scan` lists every position in the ROM that decodes cleanly as an LZ10 block with its sizes;
graphics show up as blocks of round sizes (3840 = 60 8bpp tiles, 1920 = 60 4bpp tiles, 512 = a
palette...). `c` produces VRAM-safe output by default (`--wram` allows distance-1 copies, which
the game's script banks use since they are decompressed to EWRAM).

## gs3_image.py — full-screen pictures

```
gs3_image.py list    rom.gba
gs3_image.py extract rom.gba 6 title.png
gs3_image.py insert  rom.gba 6 title_edited.png out.gba
gs3_image.py build   picture.png object.bin
```

Works on the chunked image objects of the image table (`0x0803b3a4`, see
[graphics.md](graphics.md)). `extract` writes an indexed PNG with the picture's palette; edit
it keeping it indexed (16 colours for a 4bpp picture, 256 for 8bpp; index 0 is the backdrop) and
`insert` builds a new object in free space and repoints every table entry that used the old one.
`build` only makes the object file, for use with your own pointer changes.

## gs3_sprites.py — tile viewer

```
gs3_sprites.py rom.gba 0x0818e300 16 menu.png --cell 32x16 --cols 2
gs3_sprites.py rom.gba 0x08254d24 all block.png --lz --cols 16
gs3_sprites.py rom.gba 0x08181820 60 tags.png --cols 6 --pal 0x... 
```

Renders raw or LZ-compressed tile data as a sheet, 4bpp or 8bpp, with a palette read from
the ROM (`--pal ADDR[,sub]`) or a grey ramp. `--cell WxH` lays out one-dimensional sprite cells
(the way OBJ tiles are arranged for a W×H sprite) instead of plain rows of tiles.

## gs3_font.py — the font

```
gs3_font.py sheet rom.gba font.png              # every glyph with its character code
gs3_font.py glyph rom.gba 0x8b                  # one glyph as text
gs3_font.py put   rom.gba 0x8b glyph.png out.gba
```

The sheet is the fastest way to make a character table. `put` writes a 16×16 indexed PNG
(values 0–3) over one glyph. `--addr` selects another font location (the English build's font
is a different format: 1-bit rows plus a width table, see `src/vwf.c`).

## gs3_sound.py — songs and samples

```
gs3_sound.py songs   rom.gba 0x37 0x39
gs3_sound.py samples rom.gba
gs3_sound.py export  rom.gba 0x080a86f8 objection.wav
gs3_sound.py replace rom.gba 0x080a86f8 mine.wav out.gba
```

`songs` lists song headers, track counts, voicegroups and the PCM samples each song reaches
(through key splits and drum sets). `replace` stores a WAV (converted to signed 8-bit mono at its
own sample rate) as a new sample in free space and repoints every instrument that used the old
one; `--loop` sets the loop flag. The shouts are listed in [sound.md](sound.md).

## gs3_dis.py — disassembly and cross references

```
gs3_dis.py dis  rom.gba 0x0801f4c4 60
gs3_dis.py xref rom.gba 0x0803a048
gs3_dis.py pool rom.gba 0x08049b38 25
gs3_dis.py hex  rom.gba 0x080000a0 32
```

`xref` finds every aligned 32-bit literal equal to a value (pointer tables, literal pools) and
every Thumb `bl` that calls an address — the usual first step from a data block to the code
that uses it, or from a function to its callers. `dis` needs capstone and annotates `ldr rX, [pc, #n]`
with the literal's value.

## Emulator harness (`hacking/emu/`)

`gbarun.c` is a tiny front end for the mGBA core, driven by commands on standard input, one
answer line per command:

| Command | Effect |
| --- | --- |
| `run N` | run N frames |
| `key MASK` | set the held buttons (A 1, B 2, Select 4, Start 8, Right 0x10, Left 0x20, Up 0x40, Down 0x80, R 0x100, L 0x200) |
| `shot FILE.ppm` | screenshot |
| `rd ADDR LEN` / `wr ADDR HEX` | read / write memory through the bus |
| `save FILE` / `load FILE` | save states |
| `pc` | the program counter |
| `tp ADDR [MEM]` | tracepoint: on every execution of ADDR log the registers (and the 32-bit word at MEM) and continue |
| `wp ADDR [r\|w\|rw\|c]` | watchpoint, logged the same way |
| `tplog FILE` / `tpflush` | start a trace log / flush it and report the hit count |
| `crashtrace N` | single-step up to N instructions until PC leaves ROM/RAM, print the last 64 PCs |
| `reset`, `quit` | |

Build it with `sh build.sh` (clones mGBA 0.10.5, builds the static core library with the
debugger enabled, then compiles `gbarun.c` against it; needs cmake, a C compiler and git).
`emu.py` wraps the harness for Python:

```python
import sys; sys.path.insert(0, 'hacking/emu')
from emu import Emu
e = Emu('out/gs3_en.gba')
e.run(300); e.press('START'); e.press('A')
print(hex(e.rd32(0x03007200)))        # the script pointer
e.tplog('trace.txt'); e.tp(0x0801f4c4, 0x03007225); e.run(120); print(e.tpflush(), 'hits')
e.shot('screen.png')                   # .png with Pillow, .ppm otherwise
e.close()
```

Tracepoint lines are `pc r0..r7 sp lr [m=word]`; watchpoint lines start with `WP`. The usual
workflow is: find a candidate address with `gs3_dis.py xref`, put a tracepoint on it, play to
the moment of interest (save states make that repeatable), and read the log.
