# Script format

All addresses are for Gyakuten Saiban 3 (Japan) GBA, A3JJ. `TXT` means the text-engine state
struct at `0x03007200` (see [text-engine.md](text-engine.md)).

## Where the script lives

The script is split into **44 chapter banks** plus one **common bank**.

* Chapter banks are LZ10-compressed (GBA BIOS format, see `gs3_lz.py`) and stored back to back
  at the end of the ROM, from `0x086e5bc4` to `0x087ff0d5`. The 44 compressed blocks are listed
  with their ROM offsets and sizes in `../../data/gba_mes_table.json` (`idx`, `rom_off`,
  `comp_size`, `dec_size`); `gs3_script.py list` prints the same.
* The common bank is **not** compressed: `0x086e3578`, `0x264c` bytes (it ends where bank 0 starts), 52 sections. It holds the
  sections that every chapter can jump to (section numbers below 0x80, see below).

The game's code jumps to most common sections by number (`movs r0, #n` before `bl 0x0801fcd8`):

| Sections | Used for |
| --- | --- |
| 0–6 | system messages: the two save questions (0, 1), the episode-select prompt (2), save failed (3), erase all data (4), a new episode (5), suspending (6) |
| 7–29 | the continue screen: the name of the part the save was made in, section 7 + the chapter number `SYS+0xc1` (`0x0800d860`) |
| 30, 31 | debug court / debug investigation |
| 32, 33 | Examine with nothing there (`0x08010c00`; chapters 14 and 15 jump to sections of their own) |
| 34 | a game-over line (the penalty bar running out goes to a section of the chapter bank instead, from the table at `0x08045bf2`) |
| 35–48 | the court's response to wrong evidence, one sequence per attorney and courtroom (`0x08012c02`–`0x08012ce4`, `0x0800ec44`) |
| 49, 50 | the text of the escaped convict's data screen (episode 4) |
| 51 | a dummy |

The DS common bank has 54 sections: it adds two system messages as sections 7 and 8, so GBA
section *n* is DS section *n* up to 6 and DS section *n* + 2 from 7 on. The English build keeps
the GBA numbering (`tools/convert_script.py`, `ds_common_section`).

The game refers to the banks from two places:

| Where | What |
| --- | --- |
| `0x08049b38` | chapter table: 25 pointers, the first bank of each chapter (banks 0, 1, 3, 5, 7, 10, 11, 13, 15, 17, 20, 21, 23, 25, 27, 28, 30, 31, 32, 34, 36, 38, 39, 42, 43) |
| literal pools of the loader (`0x0801ee9c`–`0x0801eff0`) | the other 19 banks, selected by a `switch` in the loader: 2 → `0x0801ee9c`, 4 → `0x0801eecc`, 6 → `0x0801eea4`, 8 → `0x0801eeb4`, 9 → `0x0801eebc`, 12 → `0x0801eed4`, 14 → `0x0801eee4`, 16 → `0x0801ef54`, 18 → `0x0801eef4`, 19 → `0x0801eefc`, 22 → `0x0801ef14`, 24 → `0x0801ef34`, 26 → `0x0801ef74`, 29 → `0x0801ef6c`, 33 → `0x0801ef84`, 35 → `0x0801ef9c`, 37 → `0x0801efa8`, 40 → `0x0801efc0`, 41 → `0x0801eff0`; and a second pointer to seven main banks, used when an episode is started from the episode select or a save is continued: 3 → `0x0801eec4`, 7 → `0x0801eeac`, 13 → `0x0801eedc`, 17 → `0x0801eeec`, 28 → `0x0801ef64`, 32 → `0x0801ef7c`, 34 → `0x0801ef8c` |
| `0x0801ed64`, `0x0801ed60` | the common bank: its base, and base + 4 (the offset table) |

The loader (seven call sites, `0x0801ef04 0x0801ef24 0x0801ef44 0x0801ef94 0x0801efb0 0x0801efd0
0x0801fb0c`, each `bl 0x0803a048`, the LZ77-to-WRAM wrapper) decompresses the selected bank to
EWRAM `0x02011fc0`. The buffer appears to be `0x1b000` bytes (the next buffer, used by the
episode-select sprite sheet, starts at `0x0202cfc0`); the largest original bank decompresses to
`0x18d24` bytes. Several engine functions hard-code `0x02011fc0` as the bank base, so a bank that
is edited and recompressed must either still fit its original compressed size, or be placed
elsewhere and have the pointer above updated (`gs3_script.py insert` does both).

**English build.** The build replaces the loader (`src/script.c`): a bank whose pointer is at or
above `0x08800000` is used *uncompressed, in place*, with no size limit. It also writes a bank
directory at `0x08800000` for tools: `'GS3E'`, `u32 1`, `u32 45`, then `{u32 address, u32 length}`
for banks 0–43 and the common bank (length 0 = still LZ-compressed at that address).
`gs3_script.py` reads it, so dumping and editing the English text works the same way.

## Bank layout

```
u32 count
u32 entry[count]       ; normally the byte offset of section n, from the start of the bank
...sections...
```

A section is a stream of little-endian 16-bit tokens. Section `n` of the current chapter bank is
addressed as `0x80 + n` by the engine; sections `0..0x7f` are the common bank's. There is no
section terminator: a section runs until the engine hits a jump or an end command.

Two kinds of entry are not section offsets:

* **Partial banks.** A chapter whose script does not fit one bank is split: the main bank (the one
  in the chapter table) and one or more partial banks loaded through the literal pool (command
  `0x6a n` switches to block `n`). A partial bank has the *same entry count* as its main bank; the
  entries of the sections it carries are real offsets, the others are copies of the main bank's
  offsets and are never used while the partial bank is loaded. The partial banks are 2 (of 1),
  6 (of 5), 12 (of 11), 16 (of 15), 22 (of 21), 24 (of 23), 26 (of 25), 37 (of 36), 40 and
  41 (of 39). The other literal-pool banks (4, 8, 9, 14, 18, 19, 29, 33, 35) are ordinary banks
  with their own section space.
* **Label entries**, the targets of command `0x36`: `{u16 byte offset, u16 section}`. The game
  has three, the last entry of banks 1, 11 and 30 (banks 5 and 43 also end with an unused one).

`tools/banks.py` (`parse_bank` / `build_bank`) tells the kinds apart and is what both the build
and `gs3_script.py` use.

## Tokens

* `0x0000`–`0x007f`: command, followed by a fixed number of 16-bit arguments.
* `0x0080` and up: a character; the glyph is `code - 0x80` in the font (see
  [text-engine.md](text-engine.md)).

### Argument counts

The number of arguments is fixed per command and is the only thing needed to walk a section.
The table (`data/cmd_args.json`, also built into `gs3_script.py`):

```
00:0 01:0 02:0 03:1 04:0 05:2 06:2 07:0 08:2 09:3 0a:1 0b:1 0c:1 0d:0 0e:1 0f:2
10:1 11:0 12:3 13:1 14:0 15:0 16:0 17:1 18:1 19:2 1a:4 1b:1 1c:1 1d:1 1e:3 1f:0
20:1 21:0 22:2 23:2 24:0 25:1 26:1 27:2 28:1 29:1 2a:3 2b:0 2c:1 2d:0 2e:0 2f:2
30:1 31:2 32:2 33:5 34:1 35:2 36:1 37:2 38:1 39:1 3a:2 3b:2 3c:1 3d:1 3e:1 3f:0
40:0 41:0 42:1 43:1 44:1 45:0 46:1 47:2 48:2 49:0 4a:1 4b:1 4c:0 4d:2 4e:1 4f:7
50:1 51:2 52:1 53:0 54:2 55:2 56:2 57:1 58:0 59:1 5a:1 5b:2 5c:3 5d:1 5e:1 5f:3
60:4 61:3 62:0 63:0 64:1 65:2 66:3 67:0 68:0 69:2 6a:1 6b:3 6c:1 6d:1 6e:1 6f:1
70:3 71:3 72:0 73:1 74:2 75:4 76:2 77:2 78:1 79:0 7a:1 7b:2 7c:0 7d:1 7e:1 7f:0
```

The GBA dispatch table has 121 entries (commands `0x00`–`0x78`); `0x79`–`0x7f` exist only in the
DS version of the script.

### Commands that matter for text

| Command | Args | Effect |
| --- | --- | --- |
| `0x01` | – | new line |
| `0x02` | – | end of page: wait for the button, then clear the box |
| `0x2d`, `0x2e` | – | end of page variants (`0x2e` clears the text state without waiting) |
| `0x03 c` | 1 | text colour `c`, stored in the low nibble of `TXT+0x25` (0 white; the English build maps 1 → orange, 2 → light blue, 3 → green) |
| `0x0b n` | 1 | text speed: `n` frames from one character to the next (`0xff` = 3), at `TXT+0x26`; the DS's English text maps it through a table first (see text-engine.md, "Pace and text blips") |
| `0x0c n` | 1 | pause for `n` frames |
| `0x45` | 0 | a text-flow command whose exact meaning was not worked out; the English converter copies it, `0x0b` and `0x0c` verbatim from the DS script |
| `0x30 n` | 1 | blips: `n = 2` the typewriter (`TXT+0x16` = 0); the GBA ignores 0 and 1 (the low and the high blip), which it takes from the speaker |
| `0x42 n` | 1 | caption mode: `n = 0` sets bit 2 of `SYS+0x25c` (`0x03003a0c`), `n = 1` clears it. Caption text is re-dispatched every frame from column 0 / row 0 and drawn centred at `y = 62 + 18*row` |
| `0x5d a` | 1 | text layout flags in `TXT+0x22`: 0 clears the low nibble (alignment), 1 and 2 set it (centred; 2 = caption height), 3 sets bit 4, 4 clears the high nibble, 5 sets bit 5: the rest of the line fades out (see text-engine.md) |
| `0x48 x y` | 2 | offset of free-slot sprite text: `TXT+0x4c` = x, `TXT+0x4d` = y (see text-engine.md) |
| `0x0e n` | 1 | speaker: `(n >> 8) & 0x7f` at `TXT+0x24` (the name tag, and the blip) |
| `0x0f a b` | 2 | stores `a` at `TXT+0x10` |
| `0x39 n`, `0x3a n xy`, `0x3c n` | 1, 2, 1 | map markers: load object `n >> 8` (bit 0 clear: remove it), place it at (`xy >> 8`, `xy & 0xff`), show it (see graphics.md, "Map markers") |
| `0x27 n s` | 2 | shake the screen for `n` frames with strength `s` (`SYS+0x14`, `SYS+0x16`, bit 0 of `SYS+0xe8`; strength 0 moves the screen by up to 1 pixel, 1 by up to 3, 2 by up to 6) |
| `0x10 f` | 1 | set flag |
| `0x1b v` | 1 | stores `v` at `TXT+0x12` |

### Jumps and choices

| Command | Args | Effect |
| --- | --- | --- |
| `0x0d` | – | jump with no inline target (the engine takes it from its state) |
| `0x07` | – | start of a choice menu. The option labels follow as plain text, separated by `0x01`, up to the terminator |
| `0x0a s` | 1 | one-option menu end: section `s` |
| `0x08 s1 s2` | 2 | two-option menu end |
| `0x09 s1 s2 s3` | 3 | three-option menu end |
| `0x35 f o` | 2 | conditional jump (handler `0x08022724`): flag `f >> 8`; with `f & 1` it jumps if the flag is set, without if it is clear; the target is the current section's start (`TXT+4`) plus `o` bytes, or label `o` (as `0x36`) when `f & 0x80`. The offset is a byte position inside the section, so it differs between the GBA and the DS scripts and between languages: the English converter (`section_jumps` in `tools/convert_script.py`) finds the DS item the offset points at and points it at that item's place in the converted section. Before 0.16.25 it kept the DS offset, and 17 of the 308 jumps landed a few words off: in episode 2 one skipped the box's close (`1c 3`) and stopped on the `0x15` after it, which waits for the box to be closed, and the game locked up |
| `0x36 i` | 1 | jump to label `i`: entry `i` of the bank's offset table is read as `{u16 byte offset, u16 section}`; the engine jumps to section `section + 0x80` at that offset (function `0x0801fc9c`) |
| `0x6a n` | 1 | load script block `n` (1–27): the block number is stored at `TXT+0x44` and the loader at `0x0801ee08` jumps through its 27-case table to the bank for that block; the script uses it at the end of a bank, followed by `0x0d` |

Section jumps go through `0x0801fcd8`: sections `>= 0x80` are looked up in the chapter bank,
smaller ones in the common bank. Both functions compute `bank base + offset[section]` and store
the result in `TXT+0` (current pointer) and `TXT+4` (section start).

In the DS version the choice blocks contain only the `0x01` separators; the labels are button
textures instead of text. On the GBA they are ordinary text and are drawn with the same
character routine as dialogue, in a full-screen box (see text-engine.md).

## Character codes

The Japanese ROM's font has 0x600 glyphs for codes `0x80`–`0x67f`. The Latin part of the layout,
shared with the English DS font, is:

| Codes | Glyphs |
| --- | --- |
| `0x80`–`0x89` | digits 0–9 |
| `0x8a`–`0xa3` | A–Z |
| `0xa4`–`0xbd` | a–z |
| `0xbe`, `0xbf` | `!`, `?` |
| `0x161` | `.` |
| `0x165`, `0x166` | `(` and `)` (Phoenix's thoughts are in parentheses) |
| `0x16d` | `:` |
| `0x16f` | `,` |
| `0x173` | apostrophe |
| `0x17d` | ☆ |
| `0x17f` | space |
| `0x681`, `0x682` | `-` and `"` (DS English font) |
| `0x683`–`0x68a` | `[ ] $ # > < = ■` (DS English font) |
| `0x68b`–`0x697` | `é á ; ç à Ç û î è â ñ ï ê` (DS English font) |

Everything else in `0x80`–`0x67f` is Japanese (kana, kanji, symbols). Use `gs3_font.py sheet`
to render the whole font of your ROM with the code of every glyph, and build a table file from
it for `gs3_script.py --table`.

## DS script (for reference)

Phoenix Wright: Ace Attorney – Trials and Tribulations keeps its script in `mes_all.bin`:
`[u32 count][u32 offset, u32 size] × 86`, each entry an LZ10 block. Banks `2b` / `2b+1` are the
Japanese / English text of chapter bank `b` (0–41); 84 / 85 are the common bank. The DS
commands `0x74`–`0x78` take 2, 4, 2, 2, 1 arguments and do not exist on the GBA.

Two commands differ between the versions:

* `0x3a` takes **three** arguments on the DS, `(slot, x, y)`, and two on the GBA, which packs them
  as `(slot << 8, x << 8 | y)`: DS `3a 1 a1 12` is GBA `3a 100 a112`. Reading the DS script with
  two arguments desynchronises it (the third argument is taken for a character or a command); the
  DS game's own argument table at `0x020a1b44` (arm9) says 3.
* `0x53` (no arguments) exists on both: 27 uses in the GBA chapter banks, 117 in the DS ones. The
  handler (`0x080235b9`) clears `SYS+0x256` and calls `0x0801a8b4(2)`. The converter keeps the
  GBA's uses and drops the ones the DS added.
* What the converter does with a command the DS has where the GBA has none: a sound (`0x05`,
  `0x06`) is kept, as is a screen shake (`0x27`), a flash (`0x47`), a sprite animation
  (`0x12`), an item shown in court (`0x13`) or a wait (`0x4e`) — 25 in all, with their arguments
  as they are, since the two scripts agree on them wherever both have the command (`DS_EFFECTS`
  in `tools/convert_script.py`). The rest (the DS's graphic loads, `0x69`/`0x6b`, the box
  hide/shows around its top-screen updates, `0x53`, the DS-only `0x74`...) is dropped.
  Except a command the DS only moved: when the GBA has the same command with the same
  arguments elsewhere in the section, lining up with nothing, it is the same one, and it is
  kept where the DS has it (24 of them: four flags that mark a conversation as heard, four
  speakers' name tags, box hides and others). Before 0.16.27 these were dropped on both sides,
  and the conversations behind those four flags played their first-time version every time.
* Map markers (`0x39`, `0x3a`, `0x3c`) the GBA places where the DS script has none (the DS draws
  its maps with their markers in): the GBA's own are put back where the GBA has them, as the
  GBA's sounds are (22, on the maps of episode 4's investigation).
* Background changes (`0x1b`) the GBA has where the DS has none (0.16.38): the DS makes a few
  with commands of its own, which are dropped (`0x4d bg 1` where the GBA has `0x1b bg`, twice in
  bank 7 after the security camera's picture; its own top-screen pictures after episode 5's
  staff roll, bank 41 section `0x8b`). The GBA's are put back where the GBA has them, or, when
  the DS shows a picture of its own in their place (the end of episode 5), where the DS has it;
  one that sets the background already set just before or just after is left out (the judge's,
  twice in a row, in five places of episode 1's trial). Six in all, with the pan over the first
  picture at the end (`0x1d 0x201`), which the DS has no use for. `0x1b bg` waits until the
  background is up; `0x4d bg n` only asks for it (and sets bit 0 of `SYS+0x3d` when `n` is 0).
* Sections keep their place from build to build (0.16.38): a savestate holds the script
  pointer and its section's start as addresses. Fixes to the conversion are numbered
  (`FIX_LEVEL` in `tools/convert_script.py`; level 0 is the conversion of 0.16.37); a bank is
  laid out with every section's level-0 version where 0.16.37 had it, and a section a later fix
  changes gets its new version after the bank's sections, level by level
  (`banks.build_bank_layered`), with its entry pointing there. A savestate inside the old version
  carries on in it; nothing else moves. The tools read such a bank with `parse_bank(...,
  english=True)` (`hacking/tools/gs3_script.py` does), and show an old version as the end of the
  section before it. Other GBA-only commands are
  left out as before, notably 13 of `0x41` (sets up four sprites) and the GBA's own
  `0x69`/`0x6b` (screen movement) where the DS has its own instead. The 13 `0x41` all end a
  Psyche-Lock conversation, after the unlock sequence: the game goes back to the investigation
  without them (the sequence's last step sets `SYS+8` to `0x104` itself and `0x5b` brings up the
  talk menu, as with them).
* `0x64` (a Psyche-Lock conversation ends; its argument is not read on the GBA) sets `SYS+8` to
  `0x40a04`: the game's main loop then runs the unlock sequence (`0x08011e4c`: with no lock left,
  `0x03003968` reaching 0, step 7: the locks break, the background is broken up, the white flash,
  "Unlock Successful"; otherwise step 3), and the script is not run until it is over. In the
  Japanese GBA script and the DS's, every `0x64` is followed by a wait (`0x0c`, after a `0x26`
  or a sound when there is one), which ends the script's run for that frame, so the commands
  after it run once the sequence is over: `0x37` (the location's lock flag, byte 3 of its
  20-byte entry at `0x03002920`) and `0x1b` (the room's background). The DS's English script
  lost that wait once, at the end of Larry's locks (bank 8 section `0xbb`): `0x37` and `0x1b`
  ran under the sequence, the background was loaded again from the room's, and the sequence
  broke up a grey copy of the room instead. The English build does not put the wait back in
  the script (the rest of the bank would move, and a savestate in it with it): `psyche_end`
  (`src/script.c`, dispatch entry `0x64`) ends the script's run after `0x64` (and a `0x26` right
  after it, which the Japanese script runs first) when no wait follows. It changes nothing
  where the wait is there.
* `0x12 m s l` fades the screen's brightness: `m >> 8` is the mode (1 darker down to 0, 2 darker
  up to 16, 3 brighter down to 0, 4 brighter up to 16), `m & 0xff` the frames per step, `s` the
  step, `l` the layers. `0x08000b40` sets it up (`SYS+0x88` layers, `+0x8a` mode, `+0x8c` frame
  counter, `+0x8e` frames per step, `+0x8f` step); the main loop moves `BLDY` (shadow
  `0x03003ade`) by the step, keeps its low 5 bits, and ends the fade when it lands on the target.
  The scripts use steps of 0 (at once), 1 and 8; a flash is a fade that starts on its target and
  goes once round, `12 301 8 1f` from 0: 24, 16, 8, 0. The dispatcher does not run the script
  while a fade is under way unless bit 1 of `TXT+0x1c` is set. Effect 1 of `0x69` sets it at the
  start of episode 1 and leaves it set, effect `0x62 3d` sets it and `0x62 3e` clears it, effects
  1, 3 and `0xc` clear it in some of their steps, and the save keeps it (the DS has the same rule,
  with bit 16 of its text flags). With the bit set, a fade can start while another is under way,
  and one whose step never lands on its target from there goes round for good. In Ron's "night
  of the crime" (bank 7 section `0xa8`) a fade in from white of 32 frames (`12 302 1 1f`) runs
  under a wait of 15 (`0c f`), the flash after it starts at 9, and the screen flashed every four
  frames for several pages, until the next fade. The Japanese game does the same from the same
  state. The English build plays such a place as the game does with the bit clear (0.16.40):
  the dispatcher's test (`0x0801f86e`) calls `fade_hold` (`src/script.c`), which keeps the
  game's rule and, with the bit set, looks past the commands just ahead that take no time
  (`0x05`, `0x06`, `0x0e`, `0x1c`) and at most one wait (`0x0c`; one under way has `0x0c` in
  `TXT+0xa` and the frames left in `TXT+0x12`). When they lead to a fade that could not land
  from the level the fade under way will be at by then, it clears the bit and the script
  waits: in Ron's scene the fade in from white runs its 32 frames, then the wait of 15, then
  the flash, frame for frame as with the bit clear. It never stops a fade that lands, so the
  places that set the bit on purpose play as before. Two fallbacks (0.16.39): `fade_start`
  (in place of the body of `0x08000b40`) first finishes the fade under way when a new one could
  not land all the same (with none, it starts from the level below that it can land from), and
  the step in the main loop (`0x08000c26`, `0x08000dfc` down, `0x08000d98`, `0x08000e70` up)
  stops on the target where it would go past it from the near side, so a fade already going
  round (in a savestate) ends too. With the bit clear, nothing changes.
