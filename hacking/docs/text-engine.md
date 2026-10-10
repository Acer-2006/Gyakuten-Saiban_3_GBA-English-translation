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
| +0x16 | u16 | text blips: 0 = the typewriter (command `0x30 2`, and every text reset), 2 after a name tag (command `0x0e`); the original counts 2, 1 in it to blip on every other letter |
| +0x1c | u16 | flags. Bit 2 selects the "free sprite slot" text path (used for text drawn outside the dialogue box); bit 15 is cleared on every command except `0x0c`. The bit is *not* a reliable "choice menu" indicator — it stays set after caption screens |
| +0x22 | u8 | alignment (command `0x5d`): low nibble non-zero = centred; bit 5 enables colour-by-column (thresholds: the 5 words at `0x08049c1c`) |
| +0x24 | u8 | speaker (command `0x0e`, high byte): the name tag, and the blip from the table at `0x08049af2` (0 the low blip, sound `0x2d`; 1 the high one, `0x2e`) |
| +0x25 | u8 | colour: low nibble = palette index used for glyph pixels, high nibble = colour-by-column state |
| +0x26 | u8 | text speed (command `0x0b`; `0xff` = 3): frames from one character to the next |
| +0x27 | u8 | low nibble: frames left before the next character |
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
| `0x05000200` | OBJ palette (the English build's sprite text uses palette 0, the engine's own sprite-text palette, the same in every scene: white 3, orange 6, blue 9, green 12) |
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
the shift). A line with no name tag puts the template back over the tag's rows (the loop at
`0x0800659c`, from template entry `0x180`, row 12: `movs r4, #0xc0` at `0x0800658c` and
`movs r5, #0xc0` at `0x08006596`, both shifted). Rows 12–19 are cleared by two loops:
`0x08022166`–`0x08022186` (command `0x1c`, which hides the box; the code after it sets
`TXT+0x23`, the box state, to 1 through `r4`, which the loop's first instructions set up) and
`0x08021c8e`–`0x08021caa` (after a choice).

Before a choice the box grows to the full screen a few rows a frame, and shrinks back after it:
the engine copies the map rows up (or down) one row at a time.

Page ends reset the text state in four places: `0x08021ab0` (wait for button), `0x08022622`
(command `0x2e`), `0x0801fc00` (section initialisation) and `0x0801fa6c` (text reset).

## Where sprite text goes

Each drawn character gets a 12-byte record at `0x03003e50` (in use: bit 15 of the first
halfword; then tile, x = 14 · column, y = 18 · row, colour). The writer at `0x0801fd6c` turns
the records into OAM entries 2, 3, ... every frame, unless `SYS+0x19` is 0: then it hides
entries 2–33 and the records stay as they are (the episode select clears the byte as soon as an
episode is picked, with its prompt still on the page). Where it puts them:

* normally y + 116 and x + 9 (the box rows);
* if the current section (`TXT+0xc`) is 0, 1, 3, 4 or 6–31 of the common bank (the system
  messages: save prompts, the chapter names): y − 64, and no centring;
* otherwise, with alignment set (`TXT+0x22` low nibble, command `0x5d`): the line is centred,
  and alignment 2 (captions) puts it at y 62 + 18 · row, or at y 71 when `TXT+0x1a` is 0
  (it is until the engine reaches the page's first new line: a one-line caption stays at 71, a
  longer one moves up to 62 when its second line starts);
* in the free-slot mode (`TXT+0x1c` bit 2) the record already holds the position
  (14 + 14 · column + `TXT+0x4c`, 36 + 18 · row + `TXT+0x4d`; the writer adds 9 to x) and the
  records are taken from 32 on. The staff roll at the end of the game is shown this way, with
  the offsets set by command `0x48 x y` (`x = 0xffff` puts 0 in both and sets bit 9 of
  `0x03003ada`).

Command `0x42 0` (bit 2 of `SYS+0x25c`) is used for every line shown without the text box:
captions, the episode-select prompt (common section 2), phone calls and voices over a black
screen, "To be continued".

Screens that are opened over the game (the save screen, ...) save the records and the text
state and put them back when they close; `0x08020024` then redraws the text sprites from the
records (called at `0x0800bcc4`, `0x0800dcd4` and `0x08014464`). Continuing a saved game does
the same from the save (`0x0800dcd4`, see memory-map.md, "Saved games").

## Continuing a saved game

The save holds the text state (`TXT`) and the sprite records, so the original shows the page it
stopped on again from the records. Two things change in the English build:

* **The script pointer.** `TXT+0` and `TXT+4` are saved as addresses, and the English banks
  are used in place in ROM, so their addresses move whenever a newer build changes the script.
  When a save is written, `script_save` (`src/script.c`) also records the section number and
  the 16 script words before the pointer and the one at it (SRAM `0x0e007f00`). On continuing,
  `script_resume` takes the section's start from this build's bank and looks for those words in
  the section, nearest the old offset; without a record (saves from 0.11.6 and older), or if
  the words are not there any more, it takes the nearest place with the command the game
  stopped on when that is a page end or a choice (`TXT+8`), then the old offset if it is still
  on a token boundary, and as a last resort the start of the section.
* **The page.** The English text is on the canvas (and the choice options in OBJ tiles), which
  the save does not keep, and the records are empty. When the game stopped on a page end
  (`0x02`, `0x2d`), a choice (`0x08`–`0x0a`), a statement (`0x15`) or the Court Record opened to
  present (`0x21`), `vwf_resume` finds the page (from the last page end before the pointer,
  with the colour and layout commands before it), and the first frame that shows the box (or
  the full-screen choice box) lays it out again: the text into the glyph log, drawn as a lost
  page is once no other background uses the canvas tiles, and for a choice the question on the
  canvas and the options after `0x07` as labels. A caption (`0x42 0`) is left to the engine,
  which draws it again every frame.

## Cross-examination statements

A statement is a section of its own whose text ends in command `0x15` instead of a page end: the
text stays up while the game waits for Press (L), Present (R) or the next statement (A). While
it waits, two 16×16 sprites show the arrows to the previous and next statement: OAM entries 0
and 1 at (0, 128) and (224, 128), OBJ tiles `0x1a0` and `0x1a4`, over the box's edge columns at
the height of the second line. The original's two lines start at x 9 and stay clear of them;
the English build lays a page that ends in `0x15` out from x 10 and up to 220 pixels wide
(narrowing the letter spacing for longer lines, as for every line that does not fit), instead
of from x 2 and up to 236 pixels.

## Fading lines

Command `0x5d 5` sets bit 5 of `TXT+0x22`: the cell draw then greys the text out by column, using
the thresholds at `0x08049c1c` (4, 8, 11, 14, 16): columns 0–3 as usual, then OBJ palette 13
indices 4, 3, 2, 1 (`0x6b5a`, `0x5294`, `0x4210`, `0x318c`), and nothing from column 16 on. The
script uses it for the last line of a page when a character trails off. The DS keeps the same
table at `0x020a1ca0` and one for English after it, (8, 16, 22, 28, 32), counted in characters;
the English build uses that one, with the greys 4, 3, 3 and 2 of the UI palette.

## Pace and text blips

After a character is drawn the dispatcher (`0x0801f7f8`) reloads the wait before the next one
from the speed (`0x0801f958`: `TXT+0x27` = `TXT+0x26`) and, unless it was a space, the text is
instant or the row (`TXT+0x29`) is past 1, plays the speaker's blip on every other letter
(`0x0801f9b8`; on every letter at speeds above 5, and the typewriter, sound `0x44`, on every
letter): none in the common bank's first 29 sections (the system messages), in caption mode, or
twice in one frame.

The DS's English text runs faster than its Japanese. The DS waits the speed through a table
first (`0x020ac050`: 0, 1, 1, 2, 2, 3, 3, ..., 8 for speeds 0-15, so the usual speed 3 is 2
frames a character), and blips on every other letter after a blip, every third when the mapped
speed is 1, the typewriter included, and never on a space (`0x0202370c`; the Japanese counts
1 instead of 2). The English build does the same: `text_pace` (`src/vwf.c`) gives the wait at
`0x0801f960`, and `text_blip` replaces the original's blip from `0x0801f9b0` on, which also
gives the third line of the three-line box its blips (the original had none past the second
row).

## Centred lines

The DS centres the date and place cards ("April 11, 9:40 AM / District Court / ...") and the
testimony titles ("-- The Victim and I --") with command `0x5d 1` before them and `0x5d 0`
after: it measures the line at its first character and starts it at (256 − width) / 2
(`0x02023840`). The GBA's script has none of these (332 pairs); the English converter keeps the
DS's, and the canvas starts a line under alignment 1 at (236 − width) / 2 into the box. The
engine itself only uses the alignment for its sprite cells (`0x0801f014`: the offsets at
`TXT+0x18`), which the English build does not draw.

## Captions and choices

* **Captions** (command `0x42 0`): the same text is dispatched again every frame from column 0,
  row 0, and the original draws it centred at `y = 62 + 18 * row` in light blue. Turning caption
  mode off is `0x42 1`.
  The English build draws text in this mode as sprites (16×16 cells in OBJ tiles 0–191, OAM
  entries 3–18, 19–34 and 58–73 for its three lines: the third keeps clear of the Court
  Record's panel, entries 34–47, which can open over a choice, and of the choice cursor, 57) and places the lines by the rules above, taking the section, alignment and
  number of lines at the first character; the system messages are centred (the English lines
  have no padding) and start at y 56 with a 16-pixel pitch, under the save screen's header, and
  a page with a third English line uses the three-line box's rows (y 112 + 16 · row). Only the OAM entries it has used are switched off again: the save screen
  shows its Yes / No in entries 40 and 41.
* **Choice menus** (command `0x07`): the box grows to the full screen (the map shadow then starts
  with tile `0x06` at `[0]` and `0x01` at `[1]`, which is how the English build recognises the
  mode), the question stays in the top rows and the labels are drawn as text in the lower part.
  The engine puts its cursor at y 18 · (row + selection), the row being the question's lines plus
  a blank one (`TXT+0x29` + 1 when the first option is drawn); the English build's option
  sprites go on those rows, 18 px apart.

## Where the English build hooks in

Everything below is done by `patches/text.py` with code compiled from `src/vwf.c` and placed in
the old font area.

| Site | Patch |
| --- | --- |
| `0x0801f986` | `bl vwf_draw_char` instead of the sprite cell draw; the VWF keeps a 30×6-tile canvas in BG char block 0 (tiles `0xe0`..) mapped on BG1 rows 14–19 and blits 1-bit glyph rows at a pixel pen |
| dispatch entry 1 (`0x08163b00`) | trampoline: `vwf_newline`, then the original handler `0x0802172d` |
| `0x08021ab0`, `0x08022622`, `0x0801fc00`, `0x0801fa6c` | call `vwf_clear` before the original instructions |
| `0x08006686` | per-frame hook (`vwf_frame`) before the BG map DMA: remaps the canvas, handles caption / choice sprites, and clears the arrow cells (row 19, columns 14–15) that the engine writes after the box has closed. While the box grows or shrinks around a choice, the rows the engine copies would show the canvas (the page) in every row it passes: when a canvas row is above the box's first text row, `box_moving` puts the template's tiles in place of every canvas row until the box has stopped (the original hides the text then too) |
| `0x0801f960` | `bl` to a trampoline: the wait before the next character from `text_pace` (the DS English pace) |
| `0x0801f9b0` | `bl` to a trampoline that calls `text_blip` (the DS English blips, on every row), then back to the loop |
| `0x0803b844` | template rewritten to a three-line box: rows 13–19 = top edge, 5 interior rows, bottom |
| `0x0800577a`, `0x08005784` | `0xe0 → 0xd0`: partial redraw starts one row higher |
| `0x08006678`, `0x0800667c` | name tag one row up (`0x030023c0`, `0x03002340`) |
| `0x0800658c`, `0x08006596` | `0xc0 → 0xb0`: a line with no name tag puts the template back from row 11 |
| `0x08022166`, `0x08021c8e` | the two box clear loops replaced by `bl vwf_boxclear` (rows 11–19) and a branch past the loop, keeping the register the code after the loop uses (`r4` = `TXT+0x23` for command `0x1c`, `r5` = `0x03002080` after a choice) |
| BG tiles `0xe0`–`0x193` | the canvas. The Court Record copies its panel into BG tiles `0xa0`–`0x17f` to slide from one item to the next, and char block 0 has no room for both; `vwf_frame` keeps a checksum of the canvas tiles and, when they change behind its back, draws the page again from a log of the glyphs blitted since the last clear: while the Court Record is open (`SYS+8` = 7) as sprite text cell for cell over the box's rows, as the original keeps its page in view under the panel, and on the canvas again once no background uses those tiles any more |
| `0x0800bcc4`, `0x08014464` | `bl` to a trampoline that calls `vwf_restore` (drops the sprite text of the screen that is closing) and then `0x08020024`; at `0x0800bcc4` (the save screen closing) `patches/ui.py` first puts back the BG tiles its header borrowed (`hdr_close`, see graphics.md, "Save screen") |
| `0x0800dcd4` (continuing a save; `patches/script.py`) | `script_resume`, `vwf_restore`, `0x08020024`, `vwf_resume` (see "Continuing a saved game") |
| `0x0800ac22` (writing a save; `patches/script.py`) | `script_save` instead of `WriteSramEx`: the game's save, then the record at SRAM `0x0e007f00` |
| every copy of the 16-colour UI palette (`0000 0400 1ce7 4210 739c 3800 3cc5 5a0c 7fff 0c6c 3191 4656 631b 3def 028c 03ff`) | entries 13–15 become the text colours (`1dde`, `7b0d`, `03c0`: the orange, light blue and green of the Japanese sprite text's OBJ palette 0, entries 6, 9 and 12, which the DS uses too) |

Free RAM used by the new code: EWRAM `0x02028000` (BSS of `vwf.c`) and `0x02028800` (BSS of
`script.c`). The script loader is replaced at its seven call sites so that banks placed above
`0x08800000` are used uncompressed in place (`src/script.c`: `script_load`, `jump_section`,
`jump_label`), which also removes the EWRAM size limit for edited banks.
