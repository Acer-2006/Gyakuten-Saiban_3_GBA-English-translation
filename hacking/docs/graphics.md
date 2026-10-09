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

## Court Record

**Item table: `0x08045f74`**, 211 entries of `{u32 image, u32 icon | detail << 16}`, indexed by
item id (evidence and profiles share one id space; the inventory in RAM lists ids, see
memory-map.md). `icon` selects the picture in the left box; `detail` is non-zero for items that
have a second page opened with the L Button (photos, maps, letters).

Each `image` is LZ: 5120 bytes, a 160×64 4bpp picture stored as ten 32×32 sprite cells, 5 across
and 2 down, each cell 4×4 tiles row-major. It holds the item name on top and the description
below it (Japanese: the name in 12-pixel kanji, three lines of text at a 16-pixel pitch). The
picture is drawn at (80, 24) with OBJ palette 2: index 9 is the background, 15 the name
(yellow), 8 the text (white), and columns 152–159 are index 0 (transparent; the right arrow sits
there). Unused ids (69–73, 121–125, 192, 193, 195, 196, 204, 205) point at item 0's picture.

The label next to the R icon under the picture, 人物ファイル on the evidence page and 証拠品ファイル
on the profile page, is two raw 32×16 sprite cells each (512 bytes) at `0x0818ad20` and
`0x0818af20`, OBJ palette 4 (white 12, outline 10, grey 11), DMA'd to OBJ tile `0x1a8`
(`0x06013500`) by the code with literal pools at `0x08013988` and `0x080139cc`. The same raw
sheet holds 決定 (`0x0818ab20`) and もどる (`0x0818ac20`), 32×16 each, and the cross-examination
buttons from `0x0818a720`.

The English build makes new pictures: the name is the DS version's name picture (copied pixel
for pixel), the description is the DS text set again in Spleen 5x8 (`tools/smallfont.py`) so it
fits 152 pixels. Where the DS says "Touch the Check Button", the GBA text says "Press L".

### Where the DS version keeps them

Item ids are the same in both versions. The arm9 has a table of 211 records of 24 bytes at
`0x020a2368`: `{u16 icon, u16 name, u16 name, u16 info panel, u16 description, u16 detail, ...}`
(icon and detail are the GBA's numbers). Per-language offsets into `data.bin` are at
`0x020a44c0`, eight words for each of Japanese, English and English again; for English the
fifth word is the first name picture and the eighth the first description picture. Both are
plain texture files laid out one after another:

```
u8 format (3 = 16 colours), u8 log2(width/8), u8 log2(height/8), u8 0,
u32 image offset (0x14), u32 image size, u32 palette offset, u32 palette size
```

Names are 128×16 (`0x434` bytes per file; text index 2), descriptions 256×64 (`0x2034`). The
description pictures were drawn with the dialogue font, so `tools/dsimgtext.py` reads their text
back exactly (see its docstring for the two quirks of the tool that drew them). The info panels
("Type: ...", "Age: ...") use a small font that is not in the ROM and are not used.

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
