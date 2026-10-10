# Gyakuten Saiban 3 (GBA) hacking notes and tools

Everything here is about the *structure* of the Japanese GBA ROM (A3JJ, 8 MB, CRC32 51B6CF22):
where things are, how they are encoded, and small programs that read and write them. There is no
game data in this folder; every tool works on a ROM image you supply.

The notes were written while building the English edition in the parent folder, so they lean
towards text, graphics and sound, but the memory map, the script format and the emulator harness
are useful for any kind of hack. Where something was observed rather than fully verified, the
notes say so.

| Document | Covers |
| --- | --- |
| [docs/script-format.md](docs/script-format.md) | script banks (including partial banks and label entries), tokens, the command table, character codes, choices and jumps |
| [docs/text-engine.md](docs/text-engine.md) | the text engine: dispatcher, state struct, how a character is drawn, the box, captions, and every hook the English build uses |
| [docs/graphics.md](docs/graphics.md) | chunked images (backgrounds, title), the DS pictures with writing and how they line up with the GBA ones, title menu sprites, name tags, the Court Record and the Talk / Move boxes (GBA pictures and where the DS keeps its English ones), the episode select, the save screen, the verdict, the effects archive (banners, speech bubbles), buttons, the font |
| [docs/sound.md](docs/sound.md) | the MP2K driver tables, song and sample formats, which songs are the shouts |
| [docs/memory-map.md](docs/memory-map.md) | ROM regions, free space, important RAM and VRAM addresses |
| [docs/tools.md](docs/tools.md) | how to use the command-line tools and the emulator harness |
| [docs/port-checklist.md](docs/port-checklist.md) | what the English build must not lose from the GBA game (commands between the words, name tags, the GBA's scenes), and what to check for each case |

## Tools (`tools/`)

Python 3, no game data inside. They import the library in `../tools/` and the tables in
`../data/` (relative to this folder), so keep the repository layout. Pillow and capstone are
optional extras (see tools.md).

* `gs3_script.py` — list banks; dump a bank to an editable text file; rebuild a bank from one
  (works on the Japanese ROM and on ROMs made by the English build).
* `gs3_lz.py` — LZ10 decompress / compress / scan a ROM for compressed blocks.
* `gs3_image.py` — the image table: extract a full-screen picture to PNG, put an edited one back.
* `gs3_sprites.py` — view any 4bpp / 8bpp tile region (raw or LZ) as a PNG sheet.
* `gs3_font.py` — render the font with the code of every glyph; print or replace a glyph.
* `gs3_sound.py` — list songs and samples, export a sample to WAV, replace one.
* `gs3_dis.py` — cross references (literals and `bl` calls), literal pool and hex dumps, and
  Thumb/ARM disassembly when capstone is installed.

## Emulator harness (`emu/`)

`gbarun.c` is a headless mGBA front end driven over stdin: run frames, press keys, take
screenshots, read and write memory, save states, tracepoints and watchpoints that log the
registers. `emu.py` wraps it for Python, `build.sh` builds it. Most of the reverse engineering
behind these notes was done with it.
