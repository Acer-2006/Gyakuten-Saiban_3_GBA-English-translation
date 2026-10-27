# Plans

Work agreed on but not started. Nothing here is in the build. These are kept here because plans
made in conversation alone have been lost before.

## 1. A shorter text box (about 56 pixels) — last, after the game is stable

The English box is 64 pixels, the DS box's height (0.16.8), so that three lines and the page arrow
fit. The DS shows the GBA's scene moved down 16 pixels (and right 8: its pictures are the GBA's
with a border), so the top of its box is where the top of the Japanese GBA's 48-pixel box is
(y 112 in GBA terms): the DS covers characters exactly as much as the original does, and the
English build 16 pixels more (Pearl, the shortest, loses her chin). A 56-pixel box gives back 8
of the 16 and covers 35% of the screen (the DS's box 33%). The line pitch stays 16; the page arrow
goes beside the last line, as there is no room under it. Everything that knows the box's rows
moves with it: `TEXT_Y0` and the line rows, the name tag, the choice question on BG0, the
cross-examination arrows on the second line, the episode select's short box, the life bar and
map-marker tile juggling, and `box_rows_fix` for saves made with another box. (Mock-ups of the 64
and 56 boxes, with and without a scene shift, were made from savestates; they are not kept here.)

A whole-scene shift (the DS's framing for everyone) was looked at and set aside: it cuts the top
of every scene (tall characters' heads) and needs the DS's extra bottom rows of every background
and every character.

## 2. Pearl framed as on the DS (scoped 2026-10-27; after the box)

Raise only Pearl and fill the bottom of her sprites with the rows the DS has under them.

**Position.** A character's slot (from `0x0801681c`; Pearl's at `0x03000844` in the episode 2
state used) has the character at slot + `0x0d` (`0x1e`) and x, y at slot + `0x10`, `0x12`
(120, 80). The setup routine `0x080172a8 (character, pose, x, y)` has 12 callers: most pass y 80,
two pass 128 (entries from below), several slide x. Raise her where sprites are drawn (the
animation renderer, `0x08017cc8`): y − N for the slot whose character is `0x1e`, which covers every
entrance and slide. (Setting `0x03000856` in a savestate moves her as wanted: tried at 8 and 16.)

**Art.** Pearl is person 27 of the person table (`0x08046920`: sub-archives from `0x0860cdbc`,
frame data `0x086193d4`, 37). The script uses 18 of her poses (1777 times, 440 frames), every frame
ending at the bottom of the screen (y + 80). Her frame data holds 19 poses (`0x0` is the one not
used). Each has exactly one match in `data.bin` with the same frame timing and every GBA piece at
the same place, size and shape (only the cell numbers differ, as the DS's cells are numbered with
its extra ones): the DS's frames are the GBA's with more pieces under them, at y +80 (the DS's
picture goes on 16 rows below the GBA's), 32×16 and smaller, from cells the GBA does not have:
2 more pieces in most poses, 3 in `0x804` and `0x928`, 6 in `0x3148` and in the wide pose `0x2f0c`
(whose new pieces start at +72). The DS's poses (`data.bin`), for the build to find again:

| GBA | DS | | GBA | DS | | GBA | DS | | GBA | DS |
|---|---|---|---|---|---|---|---|---|---|---|
| `0x0` | `0x666a24` | | `0x928` | `0x667408` | | `0x1808` | `0x66c5f8` | | `0x2ae4` | `0x67129c` |
| `0x130` | `0x666b6c` | | `0xc68` | `0x6677a8` | | `0x20f0` | `0x66cf80` | | `0x2bfc` | `0x6713cc` |
| `0x468` | `0x666edc` | | `0xe04` | `0x66795c` | | `0x2288` | `0x66d138` | | `0x2f0c` | `0x671714` |
| `0x55c` | `0x666fe8` | | `0x1290` | `0x667e20` | | `0x241c` | `0x66d2e4` | | `0x3148` | `0x671998` |
| `0x804` | `0x6672c0` | | `0x13d8` | `0x667f80` | | `0x2894` | `0x66d79c` | | | |

The build would copy her frame lists with the DS's lower pieces (cut to N rows) and her
sub-archives with the extra cells to the expansion area and point her table entry at them, in a
last build step (savestates).

**Budgets.** Sprites: at most 34 in a frame now (the wide pose), 38 with the DS pieces, the others
at most 30; animations take OAM from 127 down and the life bar has 61–70 (see "Speech bubbles" in
graphics.md), so the build should refuse more than the DS's count. Tiles: characters load at OBJ
tile `0x2c0` (320 tiles to `0x3ff`); her largest frame takes 164, about 190 with the pieces.

**Scenes.** 130 sections, episodes 2, 4 and 5. Mostly investigation rooms; at the defence bench
(background 1) twice and the witness stand (3) once, where the bench's front is drawn over
characters: to be looked at. 413 of her poses come after a background set in an earlier section:
to be listed when it is done.

**How much.** 8 pixels with the 56-pixel box gives the DS's framing for her and changes her
height in the room little; 16 pixels does it with the 64-pixel box, and she looks taller.

## 3. Gyakuten Saiban translation tools for the GBA trilogy

Package this project's tools so that others can use them for GS1, GS2 and GS3 (the maintainer has
finished English translations of GS1 and GS2; these are not to be redone). Users bring their own
ROMs (Japanese GBA, US DS); nothing from the games ships. Separate the general parts (text
engine, DS→GBA script converter, matching of pictures, icons, banners and sprites) from GS3's own
fixes. Wanted:

* a background viewer: every background of the three games with its ROM address, size and
  palette, full view and PNG export;
* a script editor: the Japanese script on the left and the DS English with its control codes on
  the right (editable), scroll bars locked together (by page), Save (a project file the build uses
  in place of the DS text) and Load (game, episode, section), control codes inserted from a menu
  as readable tokens; a preview of the page in the GBA's three-line box would help.

Proposed: Python (standard library only, as the build) serving a page to the browser, using the
existing readers. GS1's DS version has a fifth episode that the GBA does not.
