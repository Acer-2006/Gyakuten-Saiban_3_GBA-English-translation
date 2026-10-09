# Text engine

How the Japanese GBA game turns script tokens into pixels, and where the English build hooks
in. Addresses are for A3JJ.

## The dispatcher

`0x0801f858` is the main loop. Each pass:

1. calls `0x0801e1e8` (returns 1 when the engine must yield, e.g. during a wait);
2. reads the 16-bit token at `TXT+0` (the script pointer);
3. a token `<= 0x7f` is a command: `0x0801f478(cmd)` records it (`TXT+8` current command,
   `TXT+0xa` the index used for dispatch, `TXT+0x12`/`TXT+0x14` command property bits from the
   two `u16` tables at `0x08049834` and `0x0804991c`), then the handler is fetched from the
   **dispatch table at `0x08163afc`** (121 pointers, one per command id, called through
   `0x0803a1e8`). A handler that returns 0 keeps the loop going, otherwise the engine yields;
4. a token `>= 0x80` is a character: after the per-character bookkeeping it reaches the call at
   `0x0801f986` — `bl 0x0801f4c4` with `r0 = code - 0x80`, `r1 = column`, `r2 = row`.

Handler of command `n` = `u32 at 0x08163afc + 4*n` (entry 0 is `0x080216ed`, entry 1 — the
newline — `0x0802172d`).

## The state struct (`TXT`, `0x03007200`)

| Offset | Size | Meaning |
| --- | --- | --- |
| +0x00 | u32 | script pointer (current token) |
| +0x04 | u32 | start of the current section |
| +0x08 | u16 | current command id |
| +0x0a | u16 | command id used for dispatch (same value; compared to skip re-initialisation) |
| +0x0c | u16 | current section number (`>= 0x80` chapter bank, else common bank) |
| +0x10 | u16 | argument of command `0x0f` |
| +0x12 | u16 | property bits of the current command (`0x08049834[cmd] | 0x0804991c[cmd]`) |
| +0x14 | u16 | property bits of the previous command |
| +0x1c | u16 | flags. Bit 2 selects the "free sprite slot" text path (used for text drawn outside the dialogue box); bit 15 is cleared on every command except `0x0c`. The bit is *not* a reliable "choice menu" indicator — it stays set after caption screens |
| +0x22 | u8 | alignment (command `0x5d`): low nibble non-zero = centred; bit 5 enables colour-by-column (thresholds: the 5 words at `0x08049c1c`) |
| +0x24 | u8 | background music number (command `0x0e`) |
| +0x25 | u8 | colour: low nibble = palette index used for glyph pixels, high nibble = colour-by-column state |
| +0x28 | u8 | column of the next character |
| +0x29 | u8 | row of the next character |
| +0x44 | u16 | current script block number (command `0x6a`) |

Other engine data:

| Address | Meaning |
| --- | --- |
| `0x030037b0` (`SYS`) | game-state struct. `+0` (u16) must be 0 for the dispatcher to run; `+8`, `+9`, `+0xc` mode bytes checked when jumping sections; `+0x1a` BG dirty bits (bit 0 BG0 map, bit 1 BG1 map); `+0xc1` chapter number; `+0x25c` (`0x03003a0c`) bit 2 = caption mode (command `0x42`); `+0x2d0` (u32) bit 3 makes any section jump go to *current section + 1* while in a chapter bank (testimony flow) |
| `0x03002080` | BG1 map shadow, 32×32 `u16`, copied to VRAM `0x0600e800` when the dirty bit is set |
| `0x03002fa0` | BG0 map shadow |
| `0x03002ba0` | OAM shadow (128 × 8 bytes) |
| `0x03003e50` | 64 sprite records of 12 bytes (3 OAM attributes + bookkeeping); bit 15 of the first halfword = slot in use. Records 32–63 are the pool the text engine takes from in the bit-2 mode |
| `0x05000200` | OBJ palette (the English build puts its text colours into entries 13–15 of palette 2 for sprite text) |
| `0x0803b844` | 32×32 byte template of the text box: tile indices per map cell. Row 14 is the top edge (first byte `0x02`), rows 15–18 the interior (`0x06`), row 19 the bottom (`0x04`) |

## How a character is drawn (`0x0801f4c4`)

The original engine draws **one 16×16 sprite per character cell**: 16 cells per row, two rows.

* Glyph source: `0x081f31cc + (code - 0x80) * 128`. A glyph is 16×16 4bpp stored as four 8×8
  tiles (top-left, top-right, bottom-left, bottom-right), 128 bytes; the font covers codes
  `0x80`–`0x67f` (`0x30000` bytes, `0x081f31cc`–`0x082231cc`).
* The glyph is DMA'd to a stack buffer and recoloured word by word: each 4-bit pixel `p`
  becomes `(p * 5) & colour`, with `colour` = the low nibble of `TXT+0x25` replicated into every
  nibble. So pixel value 3 becomes the colour index, 1 and 2 become `colour & 5` / `colour & 0xa`
  (used for anti-aliasing with suitably laid-out palettes), 0 stays transparent.
* Destination in OBJ VRAM: normal mode `0x06010000 + column * 128 + row * 2048` (tiles 0–127,
  i.e. the first 4 KB of OBJ VRAM belong to the dialogue text); bit-2 mode
  `0x06011000 + (slot - 32) * 128`, where `slot` is the first free record 32–63 of `0x03003e50`.
* The sprite attributes for the cell are written to the `0x03003e50` record and reach OAM through
  the shadow at `0x03002ba0`.

The dialogue box itself is a BG1 window: the template rows above are copied into the map shadow,
the name tag (tiles from the sheet at `0x08181820`, see [graphics.md](graphics.md)) goes to rows
12–13 (`0x03002380`, literals at `0x08006678` and `0x0800667c` in the tag drawer), and the
function at `0x08006684` DMAs the shadow to VRAM once per frame (its literal pool holds
`0x030037b0` and `0x03003a90`). A partial redraw of the box frame starts at template row 14 —
`movs r1, #0xe0` at `0x0800577a` and `movs r5, #0xe0` at `0x08005784` (byte offset `0x1c0` after
the shift). The interior is cleared by the loop at `0x08022166`–`0x08022186`.

Page ends reset the text state in four places: `0x08021ab0` (wait for button), `0x08022622`
(command `0x2e`), `0x0801fc00` (section initialisation) and `0x0801fa6c` (text reset).

## Captions and choices

* **Captions** (command `0x42 0`): the same text is dispatched again every frame from column 0,
  row 0, and the original draws it centred at `y = 62 + 18 * row` in light blue. Turning caption
  mode off is `0x42 1`.
* **Choice menus** (command `0x07`): the box grows to the full screen (the map shadow then starts
  with tile `0x06` at `[0]` and `0x01` at `[1]`, which is how the English build recognises the
  mode), the question stays in the top rows and the labels are drawn as text in the lower part.

## Where the English build hooks in

Everything below is done by `patches/text.py` with code compiled from `src/vwf.c` and placed in
the old font area.

| Site | Patch |
| --- | --- |
| `0x0801f986` | `bl vwf_draw_char` instead of the sprite cell draw; the VWF keeps a 30×6-tile canvas in BG char block 0 (tiles `0xe0`..) mapped on BG1 rows 14–19 and blits 1-bit glyph rows at a pixel pen |
| dispatch entry 1 (`0x08163b00`) | trampoline: `vwf_newline`, then the original handler `0x0802172d` |
| `0x08021ab0`, `0x08022622`, `0x0801fc00`, `0x0801fa6c` | call `vwf_clear` before the original instructions |
| `0x08006686` | per-frame hook (`vwf_frame`) before the BG map DMA: remaps the canvas, handles caption / choice sprites |
| `0x0803b844` | template rewritten to a three-line box: rows 13–19 = top edge, 5 interior rows, bottom |
| `0x0800577a`, `0x08005784` | `0xe0 → 0xd0`: partial redraw starts one row higher |
| `0x08006678`, `0x0800667c` | name tag one row up (`0x030023c0`, `0x03002340`) |
| `0x08022166` | box clear loop replaced by `bl vwf_boxclear; b 0x08022186` |
| every copy of the 16-colour UI palette (`0000 0400 1ce7 4210 739c 3800 3cc5 5a0c 7fff 0c6c 3191 4656 631b 3def 028c 03ff`) | entries 13–15 become the text colours (`167f`, `7eed`, `2be7`) |

Free RAM used by the new code: EWRAM `0x02028000` (BSS of `vwf.c`) and `0x02028100` (BSS of
`script.c`). The script loader is replaced at its seven call sites so that banks placed above
`0x08800000` are used uncompressed in place (`src/script.c`: `script_load`, `jump_section`,
`jump_label`), which also removes the EWRAM size limit for edited banks.
