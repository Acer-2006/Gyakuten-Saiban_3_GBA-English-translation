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
is the title screen, 240×160 8bpp; its palette entries 0–31 are the shared UI colours, and the
copyright rows at the bottom (148–159) use entries 32 (black) and 195 (grey). The English build
rebuilds that object with `tools/chunkimg.py` (`load` / `build`) and only changes the pointer in
the table entry. Its logo comes from the DS title picture (`data.bin` `0x3684`, LZ: a 512-byte
palette and 256×192 8bpp tiles, the logo's ink in x 4–251, y 11–156), scaled to 3/4 (186×111, at
the top of the screen so it clears the menu at y 112) with a Lanczos filter, each pixel then taking
the nearest of the logo's own colours (`tools/resample.py`); the copyright rows stay the GBA's.

`gs3_image.py list ROM` prints the table with the flavour and size of each object;
`gs3_image.py extract` / `build` convert to and from PNG.

## Pictures with writing in them

The DS keeps its full-screen pictures in `data.bin` as small archives:

```
u32 7, then 7 x {u32 offset, u32 size}     ; offsets relative to the archive
pair 0:     palette (0x20 bytes, 16 colours, or 0x200, 256 colours)
pairs 1-6:  LZ chunks of 8x8 tiles in 1D order: 256x192, or 512x192 for the wide pictures
```

The arm9 lists them at `0x0209dce4`: 180 records `{u32 offset, u32 size, u32 flags, u32 index}`
in the DS's own order (flags bit 31 = 16 colours, as on the GBA). `index` is `0x8000` for a
picture that is the same in both languages; otherwise it selects one of the 57 pictures that
differ, listed as `{u32 offset, u32 size}` pairs twice in the same order: Japanese at
`0x0209d924`, English at `0x0209db04` (the Japanese table ends with a zero pair).

Most of them are the GBA picture with a border: the GBA's 240×160 is the Japanese DS picture cut
at (8, 16), the wide 480×160 ones at (16, 16), tile for tile and with the same palette. The
exceptions: a few are another quantisation or palette order of the same art (the store front,
the calling card, the river map), three are the GBA picture enlarged by 16/15 (the newspaper, the
urn twice), the pages of text were set again for the DS screen, and the burnt letter's paper is
8 pixels wider on the GBA. Of the 57, five are the DS episode title cards and two its save-error
screens, which the GBA does not have; ten look the same in both languages, and one changes only
outside the part the GBA shows.

`patches/pictures.py` pairs 39 GBA images with their DS pictures and changes the GBA picture
where the Japanese and English DS ones differ; it sets the English text of the pages into the GBA
pages (keeping the GBA's page numbers and arrows) and uses the whole English calling card and
newspaper. The rebuilt objects keep the original chunk sizes (chunks that did not change keep
their compressed bytes, `chunkimg.build(..., old=...)`), and every image-table entry that used an
old object is pointed at the new one.

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

## Map markers

The script marks places on maps and diagrams with small sprites: command `0x39 n` loads object
`n >> 8` (removes it when bit 0 is clear), `0x3a n xy` puts it at x = `xy >> 8`, y = `xy & 0xff`,
and `0x3c n` shows it. The objects are listed at `0x08049c50`, 12 bytes each: `{u32 tiles, u16
bytes, u16 attr0, u16 attr1}`, the tiles raw 4bpp (from `0x0823de08`), the palette `0x0823dde8`
(OBJ palette 6), OAM entries from 57 on. Three of the 16×16 circles have a kanji in them: 目
(object 0, green: the witness), 被 (1, blue: the victim) and 犯 (4, red: the killer); the others
are lines, dots, cars and snowmobiles. `data.bin` has the same markers at `0x60980`, each
Japanese one followed by the English one (W, V, K), and the English build copies those over
objects 0, 1 and 4 (`patches/graphics.py`).

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
for pixel), the description is the DS text set again in the font the DS pictures use, the
dialogue font, white (8) only like the DS's and the Japanese text (`tools/dsdesc.py`). The DS
lines run to 228 pixels with letters 2 pixels apart and words 10; the build halves every gap
(letters 1, words 5) and breaks the text into lines of up to 149 pixels: three lines 16 rows
apart when it fits (as the Japanese), otherwise four 12 rows apart, broken so that the letters
of two lines touch as little as possible (they are 13 rows tall). Where the DS says "Touch the Check Button",
the GBA text says "Press L".

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
  own. Each box takes 128 OBJ tiles. The frame data has two frames: the box for one frame, then
  one 32×16 piece of the inside, held. The box of episode 5, shown next to episode 4, runs 24
  tiles past the end of OBJ VRAM, which wraps to tiles 0–23;
* effects 21–25, sub-archive `0x9ca0`: 第n話, three 16×16 sprites at y −60 (第, the digit, 話),
  VRAM `0x06011000` (tile 128); the arrows (effects 26, 27) follow at tiles 140 and 146, so the
  label has 12 tiles (48×16).

The prompt under the boxes (エピソードを選んでください) is common-bank section 2, drawn as sprite
text in OBJ tiles 64–127 (see text-engine.md); tiles 24–63 are free on this screen.

The DS has each episode's box as a 256×64 texture in `data.bin` (from `0x7de7b8`, `0x2094` bytes
apart; texture format under Court Record): a 176×58 box with the title on one line and four
palettes (normal, touched, faded, greyed). The label is one 128×64 texture (`0x7e8a9c`): the
digits 1–5, the arrows and the word Episode. The English build (`patches/episodes.py`) draws
128×64 boxes in the DS style (its outline, highlight, shadow and fill colours, the corners cut)
with the DS title lettering cut into two lines at a word space, on DS palettes 0 and 3 for the
highlighted box and the others: two 64×64 sprites in the same 128 tiles. The label is the DS word
Episode and the digit, 96×24 in six sprites (three 32×16 over three 32×8) at OBJ tile 24. The five
titles read from the DS common bank (the sections the save screen uses: two centred lines, the
episode title and the part) check that each box is the episode it should be.

## Save screen

START during an investigation opens it; common-bank section 0 or 1 asks the question, and the
game state is saved and restored around it (`0x0800bca8` copies the sprite records and the text
state back, then calls `0x08020024`, which redraws text sprites from the records).

* Header 記録: two 32×32 glyphs in the UI BG tile sheet (`0x08180820`, 256 tiles DMA'd to BG
  char block 0 by eight loaders), tiles `0x60`–`0x6f` and `0x70`–`0x7f` (`0x08181420`), placed by
  the BG2 map at `0x0803bf44` (32 wide, rows 2–11 are the box) at columns 10–13 and 18–21 of
  rows 3–6. BG palette 0: grey (3) lettering, white (8) outline, dark red (9) background. The
  sheet stays in VRAM between screens: the save screen opened during the game loads no BG tiles
  of its own.
* The DS has SAVE, and LOAD on the continue screen: 103×30 olive-green lettering with a white
  outline in its save box textures (`data.bin` `0x7cbebc` and `0x7cfef0`). The English build
  (`patches/ui.py`) cuts the lettering out as 14×4 tiles and maps them at columns 9–22 of rows
  3–6 with BG palette 1 (the rest of the box inside is tile `0x40`). Palette 1 on these screens
  is entries 16–31 of the palette of the courtroom picture behind them (`0x08254afc`, the episode
  select's too), whose pixels use none of those entries; the DS colours that palette 1 lacks go
  into its empty entries. The 56 tiles do not fit in the UI sheet, so `src/menu.c` copies them to
  BG tiles `0x1c4`–`0x1fb` when a screen with the header opens: hooks at `0x0800b636` (the save
  screen, opened with START or at the end of a part), `0x0800ae80` (erase all data, from the
  title) and `0x0800d750` (the continue screen). During the game a scene's graphics may be in
  those tiles, so the save screen keeps them (in `0x02029000`..) and puts them back when it
  closes, at `0x0800bcc4` after the game state is restored. The question under the header starts
  at y 56 with a 16-pixel pitch, clear of the lettering.
* はい / いいえ: `0x0819a070`, two 64×32 sprites (1D) in the Talk-topic box style, DMA'd to OBJ
  tile `0x1e0`; OAM entries 40 and 41 at (48, 96) and (128, 96), palette 9 for the highlighted
  one and 10 for the other.
* The continue screen (Continue on the title) uses the same screen: the box shows the name of
  the part the save was made in (common section 7 + chapter, see script-format.md) and two
  128×32 buttons in the same style sit at (56, 98) and (56, 130), each two 64×32 sprites:
  中断したところから (where the game was suspended) at `0x08199070` and この章のはじめから (the
  start of this part) at `0x08199870`, OBJ tiles `0x1a0`–`0x21f`, OAM entries 38–41. The box
  inside is index 12 from row 6 to 25 and column 2 to 125.
* The DS has the English buttons in the same box style as textures: Yes (`0x804e48`) and No
  (`0x8056dc`), 128×32, and From save point. (`0x802d20`) and From chapter start. (`0x803db4`),
  256×32, its box outlined in index 9. The English build copies their lettering (inside the DS
  outline) into the GBA boxes the way the Talk topics are copied, narrowed where it is wider than
  the box.
* The note ※ゲーム中にSTARTボタンを押せば、いつでも記録することができます。: `0x0818e720`, 80 tiles
  at OBJ tile `0x220`, a 160×32 line at (40, 128): two 64×32 sprites, then a 32×32 column of four
  32×8 sprites whose tiles are stored in the order of rows 0, 2, 1, 3. OBJ palette 13
  (`0x08198cd0`): white (1) lettering with grey (4) anti-aliasing and a dark (5) outline, the
  highlighted words light blue (6, 8, 9).
* The DS's note, Press START at any time during / the game to save your data., is a 256×32
  texture at `0x7e9b30`: white (2) and light blue (3, the same colour as the GBA's 6) letters
  with a dark (1) outline exactly one pixel around them (the 8 neighbours), the first line 184
  pixels wide. The English build takes its letters, sets them one outline column apart (the DS
  has one or two) with three or four columns between words (the DS four to six), which makes the
  first line's letters fill the 160 columns, and draws the outline again around them.

## The verdict

Script command `0x44` (handler `0x080209dc`, one argument: 0 not guilty, otherwise guilty) shows
two 64×64 affine sprites that slam in one after the other, left then right, from raw 4bpp
pictures (8×8 tiles, 1D order, 2 KB each) DMA'd to OBJ tiles `0x1a0` and `0x1e0`: not guilty
copies 無 (`0x0818bb00`) and 罪 (`0x0818cb00`) with palette `0x08198b70`; guilty copies 4 KB from
`0x0818c300` (literal at `0x08020a30`), 有 followed by the same 罪, with palette `0x08198b50`.
Index 1 is the lettering, 2 its outline, 5 an outer edge, 3 and 4 greys for the corners; the
not-guilty palette makes the lettering white on black, the guilty one black on white. 敗訴
follows at `0x0818d300`; no code reference to it was found.

The handler sets the scale (`SYS+0xa0`) to 2.5 (`0x280`), puts the first word in OAM entry 49
(affine, double size, matrix 0, centred at (47, 47)) and switches to mode 9, whose handler
(`0x0800f23c`, entry 9 of the mode table at `0x08161088`, state in `SYS+9`) does the rest: state 0
zooms the word in (the scale −0x10 a frame) and lands it with a flash and sound `0x56`; state 1
waits 40 frames and shows the second word in entry 50 (matrix 1, centred at (192, 47)); state 2
zooms it in; state 3 waits 64 frames; state 4 moves both up a pixel a frame while they grow for
32 frames, then hides them; for not guilty, states 5–7 rain confetti (OAM entries 58–88, OBJ
tile `0xfc`, palettes 5–8).

The DS's English verdict is letters, raw 4bpp sprites in `data.bin` (64×64 or 32×64, from
`0x23c80`: N o t G u i l t y; 無, 有 and 罪 are at `0x1ece0`..) with the palettes `0x27540`
(white letters with a black outline, not guilty) and `0x27520` (black on white, guilty), a ramp
in indices 1–6. The arm9 lists the letters of each verdict (`0x020aca58` not guilty,
`0x020ac9c8` guilty), 24 bytes each: `{u32 frame, s16 x, s16 y, s16 x, s16 y, u16 512, u16 256,
u32 data.bin offset, u32 size}`, x and y the corner of the double-size box. Each letter zooms in
from twice its size about its own centre at its frame: Not at 0, then Guilty at 60; Guilty alone
letter by letter at 10, 20, ... 60. The size goes from 512 to 256 in ten steps (`0x0202fb58`), and
as the ninth begins the letter lands: a 4-frame shake of the screen (strength 1, in the fields
the DS's shake command `0x27` sets) and sound `0x56` (`0x0202fd70`), so
Guilty slams six times where the Japanese 有罪 slams twice, and there is no flash. 61 frames after
the last letter has landed they all go at once (no rise, unlike the Japanese words), and the
confetti follows for not guilty.

The English build (`patches/verdict.py`, `src/verdict.c`) shrinks the letters to 4/5, each into a
32×64 sprite (OBJ tiles `0x1a0`–`0x2bf` for the nine of not guilty), laid out as on the DS around
the middle of the screen at the original's height. `verdict_mode` takes the place of the mode's
handler in the mode table and runs the DS's timeline itself until the letters go: the letters
are entries 51–59, affine (matrix 0 or 1) with the DS's ten sizes while they zoom in and plain
sprites once they have landed; each landing sets off the GBA's shake as command `0x27 4 1` would
(`SYS+0x14` frames, `SYS+0x16` strength, bit 0 of `SYS+0xe8`; run by `0x0800024c`) and plays
sound `0x56`. Then it hides the
letters, sets state 4 with its timer run out (`SYS+0xa` = `0x21`) and calls the original, which
hides its two words (entries 49 and 50, hidden from the start) and goes on to the confetti, or
back to the court. (Nine affine sprites with double size take 9 × 138 cycles of the 1210 a line
has for sprites, and the judge behind them would not be drawn.)

## Effects archive: banners and speech bubbles

Animated effects (the testimony and cross-examination banners, the shout bubbles, and many
others) are driven by an **animation table at `0x08046b30`**, indexed by effect number (entry 0 is
empty), 20-byte entries

```
u32 archive, u32 VRAM destination, u32 frame data, s16 x, s16 y, u32 flags
```

The code at `0x080173e8` reads x and y and starts the effect; while `SYS+0x4a` bit 4 is set it
moves every effect except 1–8 and 0x1c–0x1d 240 pixels to the left. The second byte of `flags`
is the number of sprites (OAM entries) the effect takes: the most any of its frames uses. Script
command `0x2f n on` starts effect `n` (`on` = 1) or stops it (0).

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
palette. The two banners share the right half 開始. The halves (OBJ tiles `0x260` left, `0x240`
right) slide in from x 0 and 240 to 120 (the testimony's code at `0x0800e788`, y 60), then
the whole banner (OBJ tile `0x280`) takes over with the sheen, and at the end the halves slide
apart again (testimony: across each other; cross-examination and Unlock Successful: up and
down).

The high byte of a frame's time says how a sprite's attribute picks its palette (`0x08017eb0`):
0, bit 11 (two palettes); 8, bits 10–11 (four); 1, bits 9–11 (eight). The palettes go to the
OBJ palettes from the one in the flags on.

The DS keeps its English banners in `data.bin` in the same formats: Witness Testimony and Cross
Examination in the sub-archive at `0x71b000` (eight palettes: blue, three lighter blues, red,
three lighter reds; 44 cells, the lettering in pieces of up to 64×32), Unlock Successful at
`0x73f01c` (four blues, 45 cells); after each, the frame data of the whole banners (`0x71f6f0`,
`0x71f924`, `0x742df8`: the sheen as sprites over the lettering in four frames of 7, then a flash
through the lighter palettes, held 60 frames) and of the halves, which on the DS are the two
lines. The lettering is two lines of bold italic, 192×84 and 218×79 pixels. `0x716b58` and
`0x73bfb0` are the Japanese ones.

The English build (`patches/banners.py`) composes every picture of the DS animation, shrinks it
to 128 wide (area average) and cuts it into two 64×64 halves: Witness Testimony and Cross
Examination are 128×56, Unlock Successful 128×46. The banner takes OBJ tiles `0x240`–`0x2bf` as
before: the right half at `0x240`, the left half at `0x280`, and the whole banner at `0x240` too,
right half first, so that its first frame writes the same tiles the halves have when it takes
over from them (and the halves the same as its last frame when they take over again). The
testimony banners keep two palettes, so their flash is drawn into the pictures (four palettes
from OBJ palette 11 would reach the witness's 14); Unlock Successful flashes through the DS's
four palettes, as the original's did. The frames keep the DS's timing.

**Speech bubbles** (異議あり！, 待った！, くらえ！): sub-archives `0x28e4`, `0x3c44`, `0x4e24`,
one palette each (1 white, 2 red, 3–4 darker reds, 5 bubble outline, 6 grey, 7 light red),
one frame of 7 cells (32×64, two 64×64, 32×64, three 32×16; 216 tiles at OBJ tile `0x1e8`,
palette 11), frames `0x086de558`, `0x086de590` and `0x086de5c8`. Effects 1–9 show them: 異議あり
at x 45, 190 and 120 (effects 2, 3, 6, 8, 9), 待った at 45 and 120 (1, 5, 7), くらえ at 45 (4),
y 80. The words are written vertically in a 96×144 bubble. (When Take that! is shouted at a
Psyche-Lock, the bubble goes to OBJ tile `0x100`.)

The DS keeps its English bubbles in `data.bin` in the same formats: frame data at `0x7228f8`
(Objection!), `0x72b1f8` (Hold it!) and `0x733738` (Take that!), one list of twelve 64×64 sprites
covering 256×192, followed by the sub-archive (one palette). The English build
(`patches/shouts.py`) shrinks each picture to 144×108 (area average, `tools/dspic.py`), maps the
colours back to the DS palette, covers the 8×8 tiles that have something in them with as few
sprites as it finds within the 216 tiles (16–24 sprites, so it raises the sprite count in the
entries' flags), and writes a new sub-archive and frame data for each bubble with the original
timing. The anchors at x 45 / 190 move to 72 / 168 so the bubble stays on screen. Presenting
evidence from the Court Record starts effect 4 (Take that!, `0x08013488`) or 2 (Objection!,
`0x080134ca`), and the item's icon shows at the top middle of the screen and spins away: the
tall Japanese bubbles at x 45 left room for it, the wide English ones are under it for about
half a second.

A copy of the banner kanji as 16×16 blocks also sits raw at `0x08186b20`; the game does not
use it for the banners.

**Testimony label** (証言中, top left during a testimony): raw 64×32 sprite at `0x08189f20`
(1D tile order), OBJ palette 5, white (2) with a green outline (1). `data.bin` has it at
`0x1c900` and the English Testimony 2 KB after it (`0x1d100`, with a few pixels of index 3), which
the English build copies.

**Psyche-Lock banner** (解除成功, "unlock successful"): sub-archive `0xa4b4`, four palettes (the
last three for the flash at the end), 13 cells with the banner's roles: 解除 (0) and 成功 (1) as
64×32, quarter 2 (2), quarter 1 with the sheen coming in (3, 4), quarter 1 (5), quarter 2 with
the sheen (6), quarter 3 with it (7, 9), quarter 3 (10), quarter 4 (8) and with the sheen (11,
12). Effects 104 (the whole sequence, frames `0x086df030`, OBJ tile `0x280`) and 105–107 (the
halves, `0x086df168`, `0x086df188`; the code at `0x0801a360` slides them; 107, the right half
alone, belongs to script command `0x72`, which neither script uses). See above for the English
build's.

**Data screen** (episode 4, the escaped convict): effects 69 and 70 are its title bars
(脱獄囚に関するデータ, 脱獄から再逮捕までの推移) and 71–73 the PICTURE, DATA1 and DATA2 tabs,
sub-archive `0x2d240` (one palette, 17 cells; frames `0x086e2768`, `0x086e27a0`, `0x086e282c`,
`0x086e27d4`, `0x086e2800`). A bar is 224×32 at the top of the screen: the end cap (cell 0, a
16×32 sprite, with attribute bit `0x0200` set for the right end, which flips it) and pieces with
the lettering from 16×32 to 64×32. The DS keeps the sub-archive in `data.bin` twice, Japanese at
`0x76c254` and English at `0x76d2c0`: the same cap and tabs (cells 8–16), and for the bars a
plain 16×32 piece (1) and the lettering pieces 2–7 (64×32, and 32×32 for 4 and 7). The English
build copies cells 0–7 into a sub-archive of their own, adds a plain 32×32 piece and gives the
two effects new frames: the caps, then the lettering centred between them. The new frame data
takes the place of the old (it is not larger), because a saved game keeps the address of a
running effect's frames (see memory-map.md, "Saved games").

The animation table has 241 entries (0–240); the ones after 141 are characters and objects for
cut-scenes and the ending, with no writing.

## Characters

**Person table: `0x08046920`**, 44 entries of `{u32 sub-archive, u32 frame data, u32 count}`.
Each person's pictures are sub-archives in the effects-archive format (above): the first one,
then more for its other poses, each a palette and its cells. The frame data (in the effects'
format) gives the sub-archive as an offset from the person's first one. Person 7 is Phoenix at
college (sub-archives `0x08501c50`, `0x08507708`, `0x0850b2a0`), person 12 a policeman
(`0x08548548`, `0x0854a904`, `0x0854f42c`, `0x08551a74`); effects 35–37 (sub-archive
`0x086bb1cc`) are the close-up of Phoenix at college.

The DS keeps the same sub-archives in `data.bin`, the ones its English version changed twice:
Japanese (the GBA's cells, byte for byte) and English, with the same cells in the same order and
a few cells the GBA does not have. Its English sprites put P on Phoenix's sweater instead of RYU
(`0x53ccf0` / `0x6f3f9c`, `0x544150` / `0x6fb274`, `0x548ad0` / `0x6ffaf8`, and the close-up
`0x758718` / `0x75ac78`) and take away the policeman's armband with Japanese writing on it
(`0x58b270` / `0x704db8`, `0x590f5c` / `0x70a9dc`, `0x593cc4` / `0x70d710`). Two more pairs
(`0x70f8dc` / `0x70fab8`, `0x712ac8` / `0x713258`, effects 204 and 211) change a few pixels of
pictures with no writing in them. `patches/sprites.py` finds the GBA cell that is the same as each
Japanese cell the English version changed, stores the English one in the expansion area and
points the sub-archive's cell table at it (offsets are 32-bit and count from the table; the game
unpacks a cell until the sprite is full, so the cells need not follow one another): 37 cells.

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
