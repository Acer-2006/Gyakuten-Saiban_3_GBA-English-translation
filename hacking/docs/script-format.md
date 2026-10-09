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
| `0x0b`, `0x0c`, `0x45` | 1, 1, 0 | text-flow commands whose exact meaning was not worked out; they are identical in the GBA and DS scripts and the English converter copies them verbatim |
| `0x42 n` | 1 | caption mode: `n = 0` sets bit 2 of `SYS+0x25c` (`0x03003a0c`), `n = 1` clears it. Caption text is re-dispatched every frame from column 0 / row 0 and drawn centred at `y = 62 + 18*row` |
| `0x5d a` | 1 | alignment, low nibble of `TXT+0x22`; non-zero (the script uses 2) = centred |
| `0x48 x y` | 2 | offset of free-slot sprite text: `TXT+0x4c` = x, `TXT+0x4d` = y (see text-engine.md) |
| `0x0e n` | 1 | background music, stored at `TXT+0x24` |
| `0x0f a b` | 2 | stores `a` at `TXT+0x10` |
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
