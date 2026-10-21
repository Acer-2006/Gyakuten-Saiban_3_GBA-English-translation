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
| +0x1c | u16 | flags. Bit 1 lets the script run while the screen fades (`0x12`, see script-format.md); bit 2 selects the "free sprite slot" text path (used for text drawn outside the dialogue box); bit 15 is cleared on every command except `0x0c`. The bit is *not* a reliable "choice menu" indicator — it stays set after caption screens |
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
episode is picked, with its prompt still on the page). The entries are at priority 1, under
BG2: the Court Record's panel (priority 0) covers a choice's options while it is open, and the
English build's sprite text uses the same priority. (The Record's button row, R Profiles, A OK,
B Back, is sprites at y 96 on the original's name tag; the English page's first line, at y 102,
is under it while the Record is open: 0.16.18 moved the page 8 px lower meanwhile, and 0.16.21
put it back.) The Record's picture (OAM 34, 64×64) goes to OBJ tile `0x280`, or with a large character
on screen whose sprites start below `0x2c0` (the loader's test at `0x08014dca`; Armando's start at
`0x284`) to `0x80` (`0x08014ddc`, attribute at `0x08014e9a`): the original's spare tiles of the item
shown in court, the third line's here. While it is there `vwf_frame` moves the third line to
64 tiles from `0x100`–`0x17f` that no shown sprite uses (in court the defence bench's and witness
stand's fronts take `0x100`–`0x12f`, so it is usually `0x130`), keeping what was there in EWRAM
`0x0202a000` and putting it back when the Record closes; the page is drawn again from its start
(`vwf_resume`) each time it moves. If no such block is free the third line is hidden until
the Record closes. Where the engine puts them:

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
* **The page.** The English text is in OBJ tiles (the page as sprite text, or a question on the
  canvas with the options as sprite text), which the save does not keep, and the records are
  empty. When the game stopped on a command (a page end `0x02`/`0x2d`, a choice `0x08`–`0x0a`,
  a statement `0x15`, the Court Record opened to present `0x21`, the wait before a choice's
  question `{0c 1}`, ...), `vwf_resume` finds the page (from the last page end before the
  pointer, with the colour and layout commands before it), and the first frame that shows the
  box (or the full-screen choice box) lays it out again: the page as sprite text (its tiles
  cleared first), or for a page that leads to a choice (`page_has_choice`, as when it is typed)
  the question on the canvas and the options after `0x07` as labels, under the question and a
  blank row (`lbl_base`: the engine's row counter has moved on to the last option by then) and
  with the question's colours set. A save made while the question waited at its `0x07` for the
  A Button (the box not grown yet) is such a page too: before 0.16.47 it was judged by the box
  alone and came back as sprite text, which the options then replaced when they came up, the
  question gone (and with it, sometimes, the box). A caption (`0x42 0`) is left to the engine,
  which draws it again every frame.
  A save carries the box's map rows; one made with the 56-pixel box of builds before 0.16.8
  puts the box back a row lower than this build's, which `box_open` never saw: `box_rows_fix`
  moves it up (the tag rows too) before the page is looked for.
  The same is done when the START save screen closes without saving ("No"): the game puts
  the text state back after its redraw from the records, so the hook is its last call
  (`0x0800bd54`); the original restored the box's tiles, which held its text, and the English
  page came back empty without this.

## Cross-examination statements

A statement is a section of its own whose text ends in command `0x15` instead of a page end: the
text stays up while the game waits for Press (L), Present (R) or the next statement (A). While
it waits, two 16×16 sprites show the arrows to the previous and next statement: OAM entries 0
and 1 at (0, 128) and (224, 128), OBJ tiles `0x1a0` and `0x1a4`, over the box's edge columns at
the height of the second line. The original's two lines start at x 9 and stay clear of them;
the English build lays a page that ends in `0x15` out from x 10 and up to 220 pixels wide (the arrows on the second line, y 118, with the taller box)
(narrowing the letter spacing for longer lines, as for every line that does not fit), instead
of from x 8 and up to 230 pixels (the DS's margin: its lines start 8 pixels inside its 256-wide
box; measured on the DS, "No one's asking how you feel!" is 221 pixels on both).

## Fading lines

Command `0x5d 5` sets bit 5 of `TXT+0x22`: the cell draw then greys the text out by column, using
the thresholds at `0x08049c1c` (4, 8, 11, 14, 16): columns 0–3 as usual, then OBJ palette 13
indices 4, 3, 2, 1 (`0x6b5a`, `0x5294`, `0x4210`, `0x318c`, which the engine loads there from the
list after the thresholds), and nothing from column 16 on. The script uses it for the last line
of a page when a character trails off (31 lines across the English banks). The DS keeps the same
table at `0x020a1ca0` and one for English after it, (8, 16, 22, 28, 32), counted in characters,
and greys of its own: its glyph draw (`0x020239bc`) recolours a character with the entries 13, 2,
14 and 1 of its text palette (the table at `0x020a1cc8`; the palette is the GBA's OBJ palette 0
entry for entry: `0x5ad6`, `0x56b5`, `0x4a52`, `0x318c`). The English build uses the English
table and those four entries of OBJ palette 0 (`box_glyph`; before 0.16.45 it took 2, 14, 14 and
1, the second step darker than the DS's and the same as the third). The last step is nearly the
box's own grey on both, so the last few characters all but vanish, as the line trails off. The
question canvas (a page ending in a choice, BG text) would use the greys 4, 3, 3 and 2 of the UI
palette, but no question trails off.
The bit lasts one line: the engine clears it at the next line (`0x01`, `0x0802172c`), at a page
end (`0x02`, `0x07`, `0x0a`, `0x2d`: `0x080217d8`; `0x2e`: `0x0802258c`) and at a jump (`0x2c`).
A page laid out again after the save screen or a continued save (`vwf_resume`, `resume_replay`)
follows the same rule (`ends_trail`); before 0.16.36 a line that trailed off earlier in the
section left the bit set for the page being put back, and a choice's question came back grey
from its ninth character on.

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
DS's, and a line under alignment 1 starts at (240 − width) / 2 on the screen. The English DS
centres 29 more lines its Japanese script does not (Mia's voice in episode 2's flashback, the
"...*CRASH*..." of Adrian Andrews's, "...click...", the date cards of episode 5's investigation, ...);
until 0.16.49 they took the argument map's 2 (the GBA's caption height, learnt from the captions
the GBA raises where the DS centres them): a line in the box lost its centring and a caption
(`0x42 0`) was drawn in the middle of the screen, above the box the original puts it in. They
keep the DS's 1 now (fix level 5). The
engine itself only uses the alignment for its sprite cells (`0x0801f014`: the offsets at
`TXT+0x18`), which the English build does not draw.

## Captions and choices

* **Captions** (command `0x42 0`): the same text is dispatched again every frame from column 0,
  row 0, and the original draws it centred at `y = 62 + 18 * row` in light blue. Turning caption
  mode off is `0x42 1`.
  The English build draws text in this mode as sprites (32×16 cells, eight a line, in OBJ
  tiles 0–191; OAM entries 3–10, 11–18 and 19–26 for its three lines, at priority 1 like the
  original's. They have to come before the scene's own sprites: the hardware draws an earlier
  sprite of lower priority that overlaps a later one of higher priority with the latter's
  priority, so a line in entries after the defence bench's 48–51 lifted the bench above the
  box. The Court Record's panel is in 34–47, which can open over a choice, the save screen's
  Yes / No in 40–41 and the choice cursor is 57) and places the lines by the rules above, taking the section, alignment and
  number of lines at the first character; the system messages are centred (the English lines
  have no padding) and start at y 56 with a 16-pixel pitch, under the save screen's header, and
  a page with a third English line uses the three-line box's rows (y 102 + 16 · row). Only the OAM entries it has used are switched off again: the save screen
  shows its Yes / No in entries 40 and 41. Likewise only the tiles of the lines a page writes on
  are cleared, each when its first character comes (`line_clean`): on the screen that announces
  a newly added episode the new box, at OBJ tile `0x398`, runs past the end of OBJ VRAM into
  tiles 0–23, the first line's, and the prompt under it is on the second and third lines.
  The episode select's box is the original's short one (top edge on map row 16, for the
  one-line prompts at y 134); while that two-line prompt is up, `select_box` grows it two rows
  (top edge on row 14, around y 118 and 134) and puts it back for the next one-line page.
  A line wider than 222 pixels with leading spaces drops as many of their pixels as it takes
  to fit (`LBL_FIT`, `lbl_trim`): the episode endings' "THE END" is pushed right by spaces in
  the DS's script, which the DS's 256-pixel screen had room for, and on the GBA's it ran off
  the right edge.
* **Choice menus** (command `0x07`): the box grows to the full screen (the map shadow then starts
  with tile `0x06` at `[0]` and `0x01` at `[1]`, which is how the English build recognises the
  mode), the question stays in the top rows and the labels are drawn as text in the lower part.
  The engine puts its cursor at y 18 · (row + selection), the row being the question's lines plus
  a blank one (`TXT+0x29` + 1 when the first option is drawn); the English build's option
  sprites go on those rows, 18 px apart, from x 24 (`LBL_X0`, after the cursor). The box's right
  border is at x 238, so an option may take 212 pixels (`OPT_FIT`); eight of the script's 27
  choices have one wider (up to 234 pixels; the DS's screen is 16 pixels wider). As a page line
  that does not fit closes its letters up a pixel (`box_glyph`), `page_scan` works out the
  smallest gap cut (`vx.lbl_sq`, at most 2; 1 does for all of them) that fits the menu's widest
  option, and every option of that menu is drawn with it, so that they keep the same spacing.
  The engine's cursor is OAM 57 (a 16×16 hand, OBJ tiles `0xfc`–`0xff`, priority 1), after the defence
  bench's sprites (48–51, priority 3, from y 128). The hardware draws an earlier, lower-priority sprite that
  overlaps a later, higher-priority one with the latter's priority, so where the cursor met the bench a
  square of the bench came up over the box; a three-line question puts the options a row lower than the
  Japanese ones, and the third option's cursor (y 126) meets it. The engine writes the cursor every frame;
  while the full-screen box is up the English build shows it from OAM 33 (free then) and hides 57
  (`cursor_ahead`).

## Where the English build hooks in

Everything below is done by `patches/text.py` with code compiled from `src/vwf.c` and placed in
the old font area.

| Site | Patch |
| --- | --- |
| `0x0801f986` | `bl vwf_draw_char` instead of the sprite cell draw: 1-bit glyph rows blitted at a pixel pen. The page is sprite text like the original's — three lines of eight 32×16 cells, OAM 3–26, OBJ tiles `0x00`–`0xbf` (the original's two lines take `0x00`–`0x7f`; the item shown in court, which had `0x80`–`0xbf`, is moved to `0x1e0` by `patches/icons.py`; the effects that play over dialogue, such as the butterflies, start at `0xe0`, the continue arrow is at `0xf8` and the choice cursor at `0xfc`), the engine's sprite-text palette (OBJ palette 0: white 3, orange 6, blue 9, green 12, greys 13 / 2 / 14 / 1 for a line trailing off), shown while the box is open, under the Court Record's panel too. The box behind it is the engine's own (BG1, blended with the scene: text on it would take the scene's colour, and the original's never does, being sprites). A page that ends in a choice (`0x07`) is the exception: its question goes on a 30×6-tile canvas in BG char block 0 (tiles `0xe0`..) mapped on BG1 rows 13–18 (the box's interior; its bottom edge, row 19, is the template's), so that it can move to the top rows when the box grows while the options take the sprite cells. BG1 blends with the scene (the box lets 7/16 of it through), so letters drawn on it took the colour of what was behind them; while the game has BG0 off (every choice page seen), the canvas tiles hold the letters alone and BG0 shows them over the box (see `0x0800673a` and `0x08000422` below), BG1's map shadow keeping the canvas entries and VRAM getting the box's own tiles in their place |
| dispatch entry 1 (`0x08163b00`) | trampoline: `vwf_newline`, then the original handler `0x0802172d` |
| `0x08021ab0`, `0x08022622`, `0x0801fc00`, `0x0801fa6c` | call `vwf_clear` before the original instructions |
| `0x0800673a` | `ldr r0, [r2]; str r0, [r1]` (BG0CNT \| BG1CNT << 16 from the shadow at `0x03003a90`, right after the map DMAs) → `vwf_bgcnt`: while the choice question is on BG0, BG0's control (char block 0, map `0x0600e000`, BG1's priority: BG0 is drawn over BG1 at the same priority) and scroll (BG1's; at the top of the full-screen choice box 4 pixels lower, `Q_DROP`, since 0.16.48: the question's first line at y 21, clear of the penalty gauge, y 4–16 at the top right, which a long English first line ran under and touched at the original's y 17), BG0's map (the canvas entries where BG1's shadow has them) and BG1's canvas cells in VRAM put back to the box's tiles; `q_frame`, run at the end of `vwf_frame`, takes BG0 off the game's DMA meanwhile (SYS+0x1a bit 0) and sets both bits when the question goes, so that the game's own BG0 map and scroll go back. All of this runs in the vertical blank ahead of the game's own updates (the OAM DMA, the characters' tiles at `0x08005660` and after): it writes only what changed, a row at a time by DMA (a first version that rewrote twenty rows every frame took 23 scanlines and pushed the game's updates past the blank, and a character showed half updated at the top of the screen; with the cheaper canvas checks in `choice_frame` the whole update now ends around scanline 188 in a full-screen choice, against 206 before the question moved to BG0). A DMA from the cartridge always steps its source, so the zero for a fill is on the stack |
| `0x08000422` | `bl 0x080009bc` (the IO register update from the same shadow: DISPCNT at `+0x4a`, BLDCNT `+0x48`, WININ / WINOUT `+0x40`) → a trampoline that adds BG0 to DISPCNT, to a fade's targets (brightness modes with BG1 a target) and to every window that shows BG1, in the shadow, around the call (`vwf_io_pre` / `vwf_io_post`), and puts the shadow back |
| (timing) | Everything `vwf_frame` does runs in the vertical blank, ahead of the game's own updates (the OAM DMA, the effects' and characters' tiles decompressed by `0x08018134` and `0x080005ec`); the blank ends at scanline 227, and an update that runs later is drawn half done at the top of the screen. The Japanese game runs past it on about 0.5% of frames (large effects such as 0x23-0x25 always do). On a dialogue page `vwf_frame` costs about 4 scanlines (it cost 16.5 before 0.16.34: the item-box leftover scan now looks at two rows a frame, two cells a read, and the page arrow is copied from a table only when its tiles are not there); bulk copies and fills (the third line's tiles lent to the Court Record, the question canvas, a line's tiles) go by DMA. Page redraws (a continued save, the Court Record closing over a question) still take up to about 40 scanlines on their one frame |
| `0x08006686` | per-frame hook (`vwf_frame`) before the BG map DMA: places the page's sprite cells (or remaps the question canvas), handles caption / choice sprites, puts the box's bottom edge back where the engine writes its own arrow cells (row 19, columns 14–15, bobbing through the tile pairs `0x20`/`0x21` to `0x26`/`0x27`, each a row lower: the English arrow is the DS's, a solid white 9×9 triangle pointing right at the third line's rows, a 16×16 sprite at OBJ tiles `0xf8`–`0xfb` in the text's white (OBJ palette 0, entry 3: before 0.16.43 it took entry 8 of OBJ palette 2, which a Psyche-Lock sequence leaves pale blue-violet), x 229 at rest with its tip 2 pixels inside the box's right edge, sliding a pixel at a time three frames a step from one pixel right of its rest to two pixels left and back, an 18-frame cycle as measured on the DS) and clears them after the box has closed. While the box grows or shrinks around a choice, the rows the engine copies would show the canvas (the page) in every row it passes: when a canvas row is above the box's first text row, `box_moving` puts the template's tiles in place of every canvas row until the box has stopped (the original hides the text then too) |
| `0x0801f960` | `bl` to a trampoline: the wait before the next character from `text_pace` (the DS English pace) |
| `0x0801f9b0` | `bl` to a trampoline that calls `text_blip` (the DS English blips, on every row), then back to the loop |
| `0x0803b844` | template rewritten to a three-line box: rows 12–19 = top edge, 6 interior rows, bottom: 64 pixels, the DS box's height, with the DS's 60 pixels between the border lines; the page's sprite lines start at y 102, 4 pixels below the top border as on the DS, and the page arrow sits 10 pixels above the bottom one |
| `0x0800577a`, `0x08005784` | `0xe0 → 0xc0`: partial redraw starts two rows higher |
| `0x08006678`, `0x0800667c` | name tag two rows up (`0x03002380`, `0x03002300`: rows 10–11) |
| `0x08000eda` | WIN0V bottom 100 → 80: the item shown in court stays solid down to the tag's top |
| `0x0802afd0`, `0x0802b50e` | `bl vwf_data_text` instead of `0x0801ecd4`: the episode 4 data screen's two pages (common sections `0x31`, `0x32`) in the English font, a few letters to a 16×16 sprite (OAM records from 37, tiles from `0x19c`), with the original's timing list; see graphics.md, "The escaped convict's data screen" |
| `0x0800ebc8`, `0x0800ebfe` | the statement arrows' y 128 → 118, the second line |
| `0x0800658c`, `0x08006596` | `0xc0 → 0xa0`: a line with no name tag puts the template back from row 10 |
| `0x08022166`, `0x08021c8e` | the two box clear loops replaced by `bl vwf_boxclear` (rows 10–19) and a branch past the loop, keeping the register the code after the loop uses (`r4` = `TXT+0x23` for command `0x1c`, `r5` = `0x03002080` after a choice). A page of sprite text is not started over by it: `0x1c 1` can hide the box in the middle of a page (14 pages in both the Japanese and the DS script, for an animation; the Japanese sometimes goes on in the same line after `0x1c 0`), and the original keeps its sprite text through the hide, so the page's lines come back with the box |
| BG tiles `0xe0`–`0x193` | the question canvas. The Court Record copies its panel into BG tiles `0xa0`–`0x17f` to slide from one item to the next, and char block 0 has no room for both; `vwf_frame` keeps a checksum of the canvas tiles and, when they change behind its back, draws the question again from a log of the glyphs blitted since the last clear, once no background uses those tiles any more |
| `0x0800bcc4`, `0x08014464` | `bl` to a trampoline that calls `vwf_restore` (drops the sprite text of the screen that is closing) and then `0x08020024`; at `0x0800bcc4` (the save screen closing) `patches/ui.py` first puts back the BG tiles its header borrowed (`hdr_close`, see graphics.md, "Save screen") |
| `0x0800b636` (the save screen opening; `patches/ui.py`, with `hdr_game`) | `vwf_overlay`: the page's sprite text is hidden until `vwf_restore`, a page start or a box clear (a choice's options were drawn over the save screen) |
| `0x0800bd54` (the save screen closing, the text state back; `patches/text.py`) | `0x080201e4`, then `vwf_resume` (see "Continuing a saved game") |
| `0x0800dcd4` (continuing a save; `patches/script.py`) | `script_resume`, `vwf_restore`, `0x08020024`, `vwf_resume` (see "Continuing a saved game") |
| `0x0800ac22` (writing a save; `patches/script.py`) | `script_save` instead of `WriteSramEx`: the game's save, then the record at SRAM `0x0e007f00` |
| BG palette 0, entries 13–15 (`0x0500001a`) | the text colours (`1dde`, `7b0d`, `03c0`: the orange, light blue and green of the Japanese sprite text's OBJ palette 0, entries 6, 9 and 12, which the DS uses too), written by `vwf.c` each frame while a page is mapped and put back to the UI palette's own values (`3def 028c 03ff`) when it is not: the ROM's copies of the 16-colour UI palette (`0000 0400 1ce7 4210 739c 3800 3cc5 5a0c 7fff 0c6c 3191 4656 631b 3def 028c 03ff`) stay as they are, since they also load into OBJ palette 2, whose entry 15 is the Court Record's item-name yellow, and the Record's panel uses BG entry 15 for the same while it slides |

Free RAM used by the new code: EWRAM `0x02028000` (BSS of `vwf.c`; its fields added since
0.16.22 are at `0x02028780`, past the BSS, so that a save state from an earlier build does not
read other data in them), `0x02028800` (BSS of
`script.c`) and `0x0202a000`–`0x0202a7ff` (the OBJ tiles the third line borrows under the Court
Record). The script loader is replaced at its seven call sites so that banks placed above
`0x08800000` are used uncompressed in place (`src/script.c`: `script_load`, `jump_section`,
`jump_label`), which also removes the EWRAM size limit for edited banks.
