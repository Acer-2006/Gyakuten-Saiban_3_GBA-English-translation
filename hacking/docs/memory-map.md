# Memory map

Gyakuten Saiban 3 (Japan), A3JJ, 8 MB (`0x08000000`–`0x087fffff`), CRC32 `51B6CF22`.

## ROM

| Range | Contents |
| --- | --- |
| `0x08000000`–`0x080000c0` | header (title `GYAKUTEN_SA3`, code `A3JJ`) |
| `0x080000c0`–`0x0803c000` approx. | code (Thumb, a little ARM): game code to about `0x08030000`, the text engine around `0x0801e000`–`0x08023000`, the sound driver and BIOS wrappers `0x08036000`–`0x0803b000` (`m4aSongNumStart` `0x08038bd0`, LZ77-to-WRAM wrapper `0x0803a048`) |
| `0x08045f74` | Court Record item table (211 × {LZ picture, icon \| detail << 16}, see graphics.md) |
| `0x08049834`, `0x0804991c` | per-command property tables (u16 × 121) |
| `0x08049b38` | chapter table: 25 pointers to script banks |
| `0x080547f4`, `0x08054824` | MP2K player table, song table (406 entries) |
| `0x0803b3a4`–`0x0803b82c` | image table (145 × {object, flags}) |
| `0x0803b844` | text box template (32×32 bytes) |
| `0x08163afc` | script command dispatch table (121 pointers) |
| `0x08164640`–`0x08180000` | **unused** (`0x1b9c0` bytes of `0xff`) — the only padding of any size in the original ROM |
| `0x08181820` | name tag sheet (raw 4bpp) |
| `0x08189b20`–`0x0818b120` | raw UI sprites: R icon, cross-examination buttons, 決定 / もどる, the Court Record's 人物ファイル / 証拠品ファイル labels (see graphics.md) |
| `0x0818e300`, `0x0818e500` | title menu sprites (raw 4bpp) |
| `0x081f31cc`–`0x082231cc` | font, 0x600 glyphs × 128 bytes. The English build does not need it and reuses the whole area for its code and font tables |
| `0x0823e7a8`–`0x0848xxxx` | chunked image objects (backgrounds) and other compressed graphics |
| `0x08254d24`–`0x0825c000` approx. | episode-select sprite sheet (10 LZ blocks) |
| `0x0826deb0` | title screen image object |
| `0x086e3578`–`0x086e5bc4` | common script bank (raw) |
| `0x086e5bc4`–`0x087ff0d5` | 44 compressed script banks |

The ROM is full: anything of size has to go either into the padding at `0x08164640` or into an
expansion. The English build pads the ROM to 16 MB and uses `0x08800000`–`0x08ffffff` for the
bank directory (`0x08800000`, see script-format.md), the English script banks, graphics and
samples; a 16 MB ROM is fine for the GBA and every emulator. The hacking tools put new data
after the last used byte, growing the ROM when needed.
Keep in mind that Thumb `bl` only reaches ±4 MB, so new *code* that is called from the original
code must sit within that range of the caller (the font area is a good spot; the English build
puts all of its code there), while data can go anywhere.

## Script loader buffers (EWRAM)

| Address | Contents |
| --- | --- |
| `0x02011fc0` | decompressed chapter bank (appears to be `0x1b000` bytes) |
| `0x0202cfc0` | episode-select sprite sheet after decompression (`0x9600` bytes) |
| `0x02028000` | free in the original; the English build keeps its renderer state here (`0x02028000` vwf, `0x02028100` script) |

## IWRAM

| Address | Contents |
| --- | --- |
| `0x03002080` | BG1 map shadow (32×32 u16) → VRAM `0x0600e800` |
| `0x03002ba0` | OAM shadow (128 × 8) |
| `0x03002fa0` | BG0 map shadow |
| `0x030028c0` | inventory: `+0x10` number of evidence items, `+0x11` number of profiles, `+0x1c` evidence ids (u8, `0xff` = empty), `+0x3c` profile ids |
| `0x030037b0` | `SYS` game state (`+0x1a` BG dirty bits, `+0xc1` chapter, `+0x25c` caption flags, `+0x2d0` testimony flags) |
| `0x03003a90` | second struct referenced by the per-frame VRAM update |
| `0x03003e50` | 64 sprite records × 12 bytes |
| `0x03007200` | `TXT` text engine state (see text-engine.md) |
| `0x03007ffc` | IRQ vector (`0x080000f0` while the game is alive; the harness's `alive()` checks it) |

## VRAM

| Address | Contents |
| --- | --- |
| `0x06000000` | BG char block 0 (the English build's text canvas uses tiles `0xe0`..) |
| `0x0600e800` | BG1 map |
| `0x06010000` | OBJ tiles 0–127: dialogue text cells (original engine) |
| `0x06011000` | OBJ tiles 128–255: pool for "free slot" sprite text |
| `0x06013400` | OBJ tile 416: episode-select sheet |
| `0x05000200` | OBJ palettes (text label colours in palette 2 in the English build; episode boxes 10/12/13; bubble 11) |

## Button masks (harness `key`)

A 1, B 2, Select 4, Start 8, Right 0x10, Left 0x20, Up 0x40, Down 0x80, R 0x100, L 0x200.
