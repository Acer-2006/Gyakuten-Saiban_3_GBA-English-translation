# Graphics

Addresses are for A3JJ. "LZ" means the GBA BIOS LZ77 format (type byte `0x10`), handled by
`gs3_lz.py`.

## Chunked images (backgrounds, title screen)

Full-screen pictures are stored as *chunked image objects*:

```
u32 offset[n]          ; n = offset[0] / 4, offsets relative to the object start (always 10 here)
at offset[0]:  palette (raw), immediately followed by LZ chunk 0
at offset[k]:  LZ chunk k            (k = 1..n-1, 4-byte aligned)
```

Two flavours, told apart by the table flags (below) or by where the first LZ header sits:

| | palette | chunk (decompressed) | tiles |
| --- | --- | --- | --- |
| 8bpp (flags bit 31 clear) | 512 bytes (256 × BGR555) | 3840 bytes = 60 tiles (7680 for the wide pictures) | 8×8, 64 bytes |
| 4bpp (flags bit 31 set) | 32 bytes (16 colours) | 1920 bytes = 60 tiles | 8×8, 32 bytes |

The chunks concatenate into a tile stream in row-major order, 30 tiles per row for a 240×160
picture (600 tiles). Nine objects are 1200 tiles (two screens wide; the table entries that use
them carry `0x11` or `0x21` in the low flag byte) and one is 900.

**Image table: `0x0803b3a4`**, 145 entries of `{u32 object, u32 flags}` (`0x0803b3a4`–
`0x0803b82c`). Several entries share one object. Known entries: 6 (`0x0803b3d4` → `0x0826deb0`)
is the title screen, 240×160 8bpp; its palette entries 0–31 are the shared UI colours and the
copyright rows at the bottom use them. The English build rebuilds that object with
`tools/chunkimg.py` (`load` / `build`) and only changes the pointer in the table entry.

`gs3_image.py list ROM` prints the table with the flavour and size of each object;
`gs3_image.py extract` / `build` convert to and from PNG.

## Sprite text on the title screen

The title menu items are raw 4bpp sprites, each 64×16 pixels stored as two 32×16 one-dimensional
cells (a cell = 4×2 tiles, row-major, 256 bytes):

| Address | Item |
| --- | --- |
| `0x0818e300` | first menu item (new game) |
| `0x0818e500` | second menu item (continue) |

They use OBJ palette 2; the lettering is index 3 with an outline of index 1. The English build
renders new text into these slots with the DS font (`tools/textgfx.py`).

## Name tags

The sheet at `0x08181820` is raw 4bpp: 10 groups of `0x800` bytes, 5 tags per group, each tag
6×2 tiles. For tag id `t` (1–49): group `t // 5`, slot `k = t % 5`; the top tile row is at
`group * 0x800 + k * 0xc0` (6 tiles, 192 bytes) and the bottom row at `+ 0x400`. The tag is
drawn into BG1 rows 12–13 above the dialogue box.

## Episode-select screen

The sprite sheet is ten LZ blocks of 3840 bytes each:

```
0x08254d24 0x082558b0 0x08256614 0x08257300 0x08257ef0
0x08258ae0 0x08259570 0x0825a0d8 0x0825ae68 0x0825b974
```

They are decompressed through the wrapper `0x0803a048` to EWRAM `0x0202cfc0` and `0x5000` bytes
are DMA'd to OBJ VRAM `0x06013400` (4bpp tile 416) by the routine at `0x0800c354`.

As observed in OAM while the screen is up (not cross-checked against the loader in every detail):

* selected episode box: objects 101–124, tiles 280–404, palette 10; its interior is 96×48 at
  x 72–168, y 48–96, background index 12, title lettering in indices 4–11 and 14;
* unselected box: palette 12, tiles 540–663;
* the "episode n" label: objects 125–127, tiles 128–136, palette 13, at y = 12.

## Speech bubbles (court shouts)

The bubble shown with a shout is seven sprites, objects 105–111, palette 11, tiles 488–712,
placed at (x, y, w×h): (57, 132, 32×16), (25, 132, 32×16), (−7, 132, 32×16), (57, 68, 32×64),
(−7, 68, 64×64), (−7, 4, 64×64), (57, 4, 32×64). The tile data was not found as a plain LZ block
in the ROM; it most likely lives inside one of the 4bpp chunked objects of the image table.

## Font

See [text-engine.md](text-engine.md): `0x081f31cc`, 128 bytes per glyph (16×16 4bpp, four
tiles TL, TR, BL, BR), glyph index = character code − 0x80, 0x600 glyphs. `gs3_font.py sheet`
renders it; `gs3_font.py glyph` prints one glyph as text.

## Finding more

* `gs3_lz.py scan ROM` lists every position that decompresses cleanly as LZ10, with the
  decompressed size — tile sets, maps and palettes show up as blocks of round sizes.
* `gs3_sprites.py` renders any ROM region as 4bpp or 8bpp tiles with a palette taken from
  another ROM address (or greys), which is the quickest way to identify a block.
* `gs3_dis.py xref ROM ADDR` finds the literal pools and `bl` instructions that refer to an
  address, which leads from a data block to the code that loads it.
