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

## Talk topics and Move destinations

The boxes listed by Talk (霧緒のこと, ...) and Move (高菱屋・地下倉庫, ...) are pictures: a
**table of pointers at `0x08045d1c`**, entries 0–127 the talk topics and 128–149 the places
(entry 150, the 5120-byte block after them, is the first Court Record picture and not part of
the list). Each entry is LZ: 2048 bytes, a 128×32 4bpp picture stored as two 64×32 sprites (1D
tile order). The code at `0x08011158` unpacks the ones the scene lists into `0x0200afc0` and
copies them to OBJ tile `0x1a0 + 0x40 * row`; the highlighted box uses OBJ palette 9, the
others palette 10, both loaded from `0x082231cc`. The frame is the same in all 150 pictures:
fill index 12, frame 9 / 15 / 13; inside, 2..12 is a ramp from the lettering colour to the fill
(dark red in palette 9, grey in palette 10), lettering in columns 3–124, rows 8–23.

The DS keeps the same boxes as 128×32 16-colour texture files laid out one after another in
`data.bin` (2228 bytes each), in the same order. The arm9 holds their offsets at `0x020b24a4`:
places (Japanese, English, English), then topics (Japanese, English, English); the three words
before that (`0x020b2498`) are the 128×128 8bpp place thumbnails. In the DS pictures index 2 is
the fill and 4–15 a ramp from the fill to the lettering. The English lettering is an
anti-aliased face that is not in either game's fonts, so the build copies the pictures: it takes
each pixel's ink (how far its colour is from the fill towards the lettering colour) and sets it
again with the GBA ramp inside the GBA frame, narrowing lettering wider than 122 pixels.

## Episode-select screen

The background is the chunked image object at `0x08254afc` (8bpp, the courtroom, tinted green
at run time); its pointer is in a small table before the image table (`0x0803b364`). The boxes
and the 第n話 label are effects of the effects archive (below):

* effects 10–20, sub-archive `0x8f4c`, two palettes (white and grey): 10 is an empty box, 11–15
  the five titled boxes on palette 0 (the highlighted one, VRAM `0x06012300`) and 16–20 the same
  boxes on palette 1 (VRAM `0x06013300` + `0x1000` · n). A box is 128×64 and 23–24 sprites: the
  frame and the empty inside are shared cells (0–12), the title row (y −8..8) has cells of its
  own. Each box takes 128 OBJ tiles;
* effects 21–25, sub-archive `0x9ca0`: 第n話, three 16×16 sprites at y −60 (第, the digit, 話),
  VRAM `0x06011000` (tile 128); the arrows (effects 26, 27) follow at tiles 140 and 146, so the
  label has 12 tiles (48×16).

The prompt under the boxes (エピソードを選んでください) is common-bank section 2, drawn as sprite
text (see text-engine.md).

The English build reads the five titles from the DS common bank (the sections the save menu
uses: two centred lines, the episode title and the part) and builds the boxes on the empty box's layout:
nine 32×16 cells inside, the title in two lines of the DS font. The label is EPISODE n in
condensed capitals (Spleen 5x8 at double height).

## Save screen

START during an investigation opens it; common-bank section 0 or 1 asks the question, and the
game state is saved and restored around it (`0x0800bca8` copies the sprite records and the text
state back, then calls `0x08020024`, which redraws text sprites from the records).

* Header 記録: two 32×32 glyphs in the UI BG tile sheet (`0x08180820`, 256 tiles DMA'd to BG
  char block 0 by eight loaders), tiles `0x60`–`0x6f` and `0x70`–`0x7f` (`0x08181420`), placed by
  the BG2 map at `0x0803bf44` (32 wide, rows 2–11 are the box) at columns 10–13 and 18–21 of
  rows 3–6. BG palette 0: grey (3) lettering, white (8) outline, dark red (9) background. The
  English build draws SAVE as one 64×32 picture in the same 32 tiles and places it at columns
  12–19. The sheet stays in VRAM between screens: a savestate made with an older ROM shows the
  old tiles until a screen reloads the sheet (the episode select does).
* はい / いいえ: `0x0819a070`, two 64×32 sprites (1D) in the Talk-topic box style, DMA'd to OBJ
  tile `0x1e0`; OAM entries 40 and 41 at (48, 96) and (128, 96), palette 9 for the highlighted
  one and 10 for the other.
* The note ※ゲーム中にSTARTボタンを押せば、いつでも記録することができます。: `0x0818e720`, 80 tiles
  at OBJ tile `0x220`, a 160×32 line at (40, 128): two 64×32 sprites, then a 32×32 column of four
  32×8 sprites whose tiles are stored in the order of rows 0, 2, 1, 3. OBJ palette 13
  (`0x08198cd0`): white (1) lettering with grey (4) anti-aliasing and a dark (5) outline, the
  highlighted words light blue (6, 8, 9).

## The verdict

Script command `0x44` (handler `0x080209dc`, one argument: 0 not guilty, otherwise guilty) shows
two 64×64 affine sprites that slam in one after the other, left then right, from raw 4bpp
pictures (8×8 tiles, 1D order, 2 KB each) DMA'd to OBJ tiles `0x1a0` and `0x1e0`: not guilty
copies 無 (`0x0818bb00`) and 罪 (`0x0818cb00`) with palette `0x08198b70`; guilty copies 4 KB from
`0x0818c300` (literal at `0x08020a30`), 有 followed by the same 罪, with palette `0x08198b50`.
Index 1 is the lettering, 2 its outline, 5 an outer edge, 3 and 4 greys for the corners; the
not-guilty palette makes the lettering white on black, the guilty one black on white. 敗訴
follows at `0x0818d300`; no code reference to it was found.

## Effects archive: banners and speech bubbles

Animated effects (the testimony and cross-examination banners, the shout bubbles, and many
others) are driven by an **animation table at `0x08046b30`**, indexed by effect number (entry 0 is
empty), 20-byte entries

```
u32 archive, u32 VRAM destination, u32 frame data, s16 x, s16 y, u32 flags
```

The code at `0x080173e8` reads x and y and starts the effect; while `SYS+0x4a` bit 4 is set it
moves every effect except 1–8 and 0x1c–0x1d 240 pixels to the left.

Nearly all of them use the **effects archive at `0x0869c8f0`**. The frame data says which
sub-archive (offset inside the archive) holds its pictures:

```
frame data:   u16 0, u16 frames, u32 sub-archive offset
              frames x {u16 offset, u16 time, u32 0}
              at each offset: u16 sprites, u16 0, then per sprite
                  u16 position (y << 8 | x, signed bytes from the anchor)
                  u16 attribute: top nibble size << 2 | shape (as in OAM), 0x0800 = second
                      palette of the sub-archive, low bits = cell number
sub-archive:  u16 palettes, u16 0x8000, 32 bytes per palette,
              u32 cell offset[n] (from the start of this table), cells
cell:         a 4bpp sprite (1D tile order) packed with a 16-bit RLE: token u16 t, then one
              u16 repeated t & 0x7fff times (t & 0x8000 set) or t literal u16s
```

The pictures are decompressed into OBJ VRAM at the destination each time a frame is shown.

**Testimony / cross-examination banners** (証言開始 blue, 尋問開始 red): sub-archive offset 0,
two palettes, 19 cells: the halves 開始 (0), 証言 (1), 尋問 (13) as 64×32, and 32×32 quarters
plain and with a white sheen (2–12 for 証言開始, 14–18 for 尋問). Effects 0x53–0x58 use it
(entries `0x080471ac` + 20·n): the sheen over 証言開始 (frames `0x086de2b8`) and over 尋問開始
(`0x086de3b0`), and the halves sliding in: 証言, 開始, 尋問, 開始 (`0x086de4d8`, `0x086de4f8`,
`0x086de518`, `0x086de538`). The 0x0800 bit in the cross-examination frames selects the red
palette. The two banners share the right half 開始. The English build writes a new sub-archive
with 26 cells (the cross-examination banner gets its own right half in cells 19–25), points the
six entries at it and renumbers the cells in the two cross-examination frame blocks. The pieces
use OBJ tiles `0x240`–`0x2bf`, so a banner can be at most 128×32.

**Speech bubbles** (異議あり！, 待った！, くらえ！): sub-archives `0x28e4`, `0x3c44`, `0x4e24`,
one palette each (1 white, 2 red, 3–4 darker reds, 5 bubble outline, 6 grey, 7 light red),
one frame of 7 cells (32×64, two 64×64, 32×64, three 32×16; 216 tiles at OBJ tile `0x1e8`,
palette 11), frames `0x086de558`, `0x086de590` and `0x086de5c8`. Effects 1–9 show them: 異議あり
at x 45, 190 and 120 (effects 2, 3, 6, 8, 9), 待った at 45 and 120 (1, 5, 7), くらえ at 45 (4),
y 80. The words are written vertically in a 96×144 bubble. The English build draws OBJECTION!
and HOLD IT! in a 144×96 bubble (two 64×64, two 64×32 and three 16×32 sprites, the same 216
tiles), moves their anchors at x 45 / 190 to 72 / 168 so they stay on screen, and keeps the
tall shape for TAKE THAT!, which shares the screen with the evidence being presented.

A copy of the banner kanji as 16×16 blocks also sits raw at `0x08186b20`; the game does not
use it for the banners.

**Testimony label** (証言中, top left during a testimony): raw 64×32 sprite at `0x08189f20`
(1D tile order), OBJ palette 5, white (2) with a green outline (1).

**Psyche-Lock banner** (解除成功, "unlock successful"): sub-archive `0xa4b4`, four palettes (the
last three for the flash at the end), 13 cells with the banner's roles: 解除 (0) and 成功 (1) as
64×32, quarter 2 (2), quarter 1 with the sheen coming in (3, 4), quarter 1 (5), quarter 2 with
the sheen (6), quarter 3 with it (7, 9), quarter 3 (10), quarter 4 (8) and with the sheen (11,
12). Effects 104 (the whole sequence, frames `0x086df030`) and 105–107 (the halves, `0x086df168`,
`0x086df188`). The English build writes a new sub-archive and sets the three frame blocks'
sub-archive offset to 0.

Other effects with writing: 69 and 70 (脱獄囚に関するデータ, 脱獄から再逮捕までの推移, a data
screen) and 71–73 (PICTURE, DATA1, DATA2), sub-archive `0x2d240`. The DS keeps a copy of that
sub-archive in `data.bin` at `0x76c254`, still in Japanese.

## Buttons

Raw 4bpp sprites, 32×16 one-dimensional cells (256 bytes):

| Address | Size | Japanese | Shown |
| --- | --- | --- | --- |
| `0x0818a720` | 64×16 | L ゆさぶる | cross-examination, top left; white box (1), lettering 3 / 2, OBJ palette 5 |
| `0x0818a920` | 64×16 | つきつける R | cross-examination, top right |
| `0x0818ab20` | 32×16 | 決定 | Court Record when presenting, next to the A icon; white (12), outline (10), OBJ palette 4 |
| `0x0818ac20` | 32×16 | もどる | next to the B icon |

The cross-examination pair is DMA'd (1 KB) to OBJ tile `0x180` with palette `0x081988d0` by the
code at `0x0800ddd0`, `0x0800eb6c`, `0x0801e5a8` and `0x080224f4`.

The investigation menu tabs that slide down from the top of the screen are 64×32 sprites (1D
tile order, 1 KB each) loaded to OBJ tiles `0x100`, `0x120`, `0x140`, `0x160` when an
investigation begins: 調べる `0x08188b20`, 移動する `0x08188f20`, 話す `0x08189320`,
つきつける `0x08189720`. The lettering is in rows 16–28: fill 1, lettering 3 (white), outline 14;
the selected tab uses OBJ palette 6 (orange, dark outline), the others palette 5 (outline the
same colour as the fill).

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
