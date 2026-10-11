# Gyakuten Saiban 3 GBA English translation

<img width="400" height="266" alt="image" src="https://github.com/user-attachments/assets/5b35b4c8-c8e0-4f19-8cbe-5c49a6f609d9" />

A fan translation of Gyakuten Saiban 3 that uses the English DS script, features three lines, a vwf and of course, as always English!

Builds an English-language ROM of *Gyakuten Saiban 3* (Game Boy Advance) from your own copies of
the two games:

* `gs3_jp.gba` — Gyakuten Saiban 3 (Japan), 8 MB, CRC32 51B6CF22
* `tt_us.nds`  — Phoenix Wright: Ace Attorney – Trials and Tribulations (USA), game code YG3E

The English script, font, name tags, Court Record, talk topics, episode titles, pictures and
other English material are read out of the DS image while the ROM is built. This repository
holds the code changes (the new text engine, the script converter and the hooks) and a little
English typed in by hand: the choice-menu options, which the DS only has as pictures
(`tools/labels_en.py`), the short words on the buttons the build draws itself (Press, Present,
OK, Back and the investigation tabs), and the few DS lines the converter rewords for the GBA's
buttons. Nothing else from either game is stored in it.

## Use

Requires Python 3.8 or newer, nothing else.

    python3 build.py gs3_jp.gba tt_us.nds -o gs3_en.gba

Takes about 20–30 seconds. The output `gs3_en.gba` (16 MB) runs in any GBA emulator or on a
flash cart.

In-game saves carry over to newer builds: a save also notes where in the script you stopped,
and a newer build finds that place in its own script. Saves made with 0.11.6 or older are placed
by their position, which is right unless that part of the script changed in between. Emulator
savestates do not carry over: one made with an older build can show a garbled text box until
the next page of text.

## What the English build changes

* Variable-width English font (the DS font) in a three-line text box, with the DS English
  version's text speed and text blips (every other letter, never on a space, on all three
  lines).
* The complete DS English script, including the choice-menu options, with its sound effects
  and its centred date and place cards and testimony titles.
* English name tags from the DS version.
* Court Record in English: every evidence and profile name (the DS name pictures) and
  description (the DS text in the DS's own description font, set a little tighter so it fits
  the GBA panel; "Touch the Check Button" becomes "Press L"), and the R Profiles / R Evidence
  switch.
* The DS version's Witness Testimony / Cross Examination banners (shrunk to the GBA's banner
  width) and Testimony label; the cross-examination buttons (L Press / Present R) and the OK /
  Back prompts when presenting.
* The DS version's Objection!, Hold it! and Take that! speech bubbles.
* Investigation menu tabs (Examine, Move, Talk, Present), and the Talk topics and Move
  destinations (the DS version's pictures, copied into the GBA boxes).
* Episode select: the DS version's episode titles in the GBA's boxes, and its Episode 1–5
  labels.
* Save screen: the DS version's SAVE header and Yes / No buttons, and its note under them
  (Press START at any time during the game to save your data.); the continue screen has the
  DS LOAD header, names the part you saved in and offers the DS buttons From save point. /
  From chapter start.
* The DS version's W, V and K markers (witness, victim, killer) on maps and diagrams.
* College Phoenix's sweater says P instead of RYU, and the policeman's armband with Japanese
  writing is gone, as in the DS version's sprites.
* The DS version's Unlock Successful banner when the last Psyche-Lock breaks, and its Not Guilty
  / Guilty verdict letters, each landing with a slam and a shake as on the DS.
* Pictures with writing in them, from the DS English ones: the pages behind the L Button (case
  summaries, letters, the price list, notes), maps, the newspapers, the calling card, the
  exhibition poster and the signs in the backgrounds.
* The escaped convict's data screen in episode 4 (Fugitive Data, Fugitive Movements).
* Caption screens ("5 Years Earlier", date/location cards) in English; lines shown without the
  text box (the episode-select prompt, "To be continued") sit where the original puts them.
* English title screen (DS logo) and title menu.
* The English voice clips ("Objection!", "Hold it!", "Take that!") from the DS version.

## Your own voice clips (optional)

The DS English shouts are installed automatically. If you would rather use recordings of your
own for some or all of them:

1. `python3 build.py gs3_jp.gba tt_us.nds --export-voices samples/` writes every candidate
   sample as a `.wav` named by its ROM offset, so you can hear which is which. The sample at
   `0xed1c0` is Mia's "Take that!"; the others are identified by ear.
2. Put your clips in `voices/` and write `voices/voices.json` mapping sample offsets to files
   (see `voices/voices.example.json`). WAV is read directly; other formats need ffmpeg.
3. Build as usual. Clips are resampled to at most 22 kHz, converted to 8-bit, placed in the
   expanded ROM, and the sound driver's instruments are repointed at them.

The `voices/` folder is ignored by git, so recordings stay on your machine.

## Credits

Thanks to Broco, whose *Comeback Courtroom 3* (2005–2007, http://comebackcourt.sourceforge.net)
was the fan translation of this game before there was an official one: it brought Case 1 to
English, and he closed it when the DS translation was announced. This project started from his
ROM hacking notes, his list of the script's control codes and his character table, which showed
where the scripts, the font, the graphics and the text routines are in the ROM and how the script
works. Thank you, Broco.

## Hacking the game yourself

`hacking/` holds format notes (script, text engine, graphics, sound, memory map) and
command-line tools for the Japanese ROM and for ROMs made by this build: dump and re-insert
script text, extract and replace backgrounds, view tiles and the font, export and replace
samples, find cross references, plus a headless mGBA harness for tracing. See
[hacking/README.md](hacking/README.md).

## Version history

* 0.16.0 — the page in the text box is sprite text, as the original's is: the box is a
  background layer blended with the scene, so text drawn on it took on the scene's colour (the
  orange, blue and green came out different in every room, and the white a little different
  from the Japanese game's); as sprites, in the engine's own text palette, the colours are the
  Japanese and DS values exactly, and the page stays in view under the Court Record by itself
  (the redraw-after-the-Record machinery and its glitches are gone with it). The question of a
  choice is the one page still drawn on the background, so that it can move to the top of the
  full-screen box.
* 0.15.15 — the direction the DS added is in: its three extra screen shakes, a flash, eleven
  sprite animations, seven moments an item is shown in court while it is talked about, and ten
  short waits (25 in all; the GBA's own direction was already the backbone, and the sounds are
  as they were).
* 0.15.14 — the Court Record icons that carry writing (the Coldkiller X bottle, the Ami jar, the
  newspapers, magazines and letters: 18 of them) are the DS English pictures; the name tag was
  half solid, half see-through while an item was shown in court (the window that keeps the
  item's box solid ended at the Japanese tag's top line; it now ends at ours).
* 0.15.13 — the metal detector lesson (Bridge to the Turnabout): the DS version moves the
  detector with the stylus and left out the Japanese line that explains the sound (it changes
  with the distance to the metal), which on the GBA is the only cue while searching; that line
  is translated from the Japanese again, with the DS line's sound and animation commands.
* 0.15.12 — the defence bench showed through the text box (brighter, over the box's bottom
  edge) once the Court Record had been scrolled or swapped, and stayed so after it closed: the
  page's third line of sprite text sat after the bench's sprites in OAM, and the hardware lifts
  an earlier sprite to the priority of a later one it overlaps; the sprite text is now in
  entries 3–26, before every scene sprite, as the original's own is.
* 0.15.11 — the Court Record's item names turned green while the panel slid from one item to
  the next (the ROM's copies of the UI palette had the text colours in entries 13–15, and the
  sliding panel names its items in entry 15; the copies are the original's again and the box's
  colours are set in the BG palette only while a page is mapped); a choice's options no longer
  show through the Court Record's panel (sprite text is at the engine's own priority).
* 0.15.10 — the Court Record's item names turned green while a choice's options or the page
  were shown as sprites (the sprite text used the panel's palette; it now uses the engine's own
  sprite-text palette); a choice's options are set on the rows the cursor is placed on, so the
  hand sits on the option it selects after a three-line question too.
* 0.15.9 — the text box keeps its page in view while the Court Record is open, as in the
  original (it went blank, since the Court Record draws its panel over the tiles the page is
  drawn in; the page is now shown as sprite text in its place until the Record closes).
* 0.15.8 — the three text colours (orange, light blue, green) are the Japanese game's own values,
  which the DS shares; ours were paler (the orange yellower, the green minty).
* 0.15.7 — episode cards: the DS titles in the GBA boxes no longer sit on a faint grey
  rectangle (the DS box's fill, copied with the letters), and their shades are matched to the
  box's dark red by lightness, so they are as dark as the Japanese titles.
* 0.15.6 — New Game on the title menu: a pixel between every pair of letters (the letters are
  unchanged; the word now fills its sprite edge to edge).
* 0.15.5 — four fixes: the Court Record opened during a choice drew its panel over the third
  option's sprites, which wrote over the panel's top row each frame (garbage where the item's
  name and description were); the shouts of Payne, Phoenix and one more voice played a third too
  deep and slow (their instruments play the sample at the mixer's own rate, so those clips are
  now resampled to it); the episode select's "Select an episode." box was the tall text box
  with its middle missing instead of the original's short box; and the episode cards are the
  GBA's own boxes again, with the DS titles set inside them in two lines at the DS size.
* 0.15.4 — the Testimony label in the corner during a testimony had black dots on the curves of
  its letters: the colour the DS gives them, a light green, was black in the GBA's palette.
* 0.15.3 — New Game on the title menu: a pixel between the N and the e and between the G and
  the a, which ran into each other (the letters themselves are unchanged).
* 0.15.2 — the title screen's DS logo is scaled properly: to 3/4 with a filter that keeps every
  stroke (the letters were uneven and broken in places, from dropping rows and columns), and a
  little larger than before.
* 0.15.1 — the Court Record descriptions are in the DS version's own description font (the
  dialogue font, sharp, read from your DS ROM) instead of Inter: the DS's letters with the gaps
  between them halved, so the text fits the GBA panel. A description that fits in three lines
  gets them where the Japanese has its three; a longer one takes four lines closer together,
  broken so that the letters of two lines touch as little as possible.
* 0.15 — the Court Record descriptions are set in Inter, a typeface made for screens, at 10
  pixels with smoothed edges (in the shades between the panel's red and white that its palette
  already had), instead of the 5×8 pixel font, in three lines (four where the text needs them)
  and with no lone word on the last line. The note on the save screen is the DS version's (Press
  START at any time during the game to save your data., START and save in light blue), its
  letters set a little closer so that it fits the GBA's note.
* 0.14.1 — the witness, victim and killer markers on maps and diagrams are the DS version's W, V
  and K instead of 目, 被 and 犯.
* 0.14 — sound and layout as in the DS version: the date and place cards and the testimony titles
  are centred; the text runs at the DS English version's speed (the usual speed is 2 frames a
  letter instead of 3) and blips as it does, on every other letter and never on a space, and the
  third line of the box blips too (it was silent); the verdict slams once a letter, with a short
  shake, and its letters go without rising, as on the DS; three sound commands of the DS script
  are back (two at the end of episode 2's trial, and in episode 5 the stop of a looping sound,
  which was left playing). The other differences found between the two versions' sounds are
  listed in `hacking/docs/sound.md`.
* 0.13 — the Witness Testimony / Cross Examination and Unlock Successful banners, the Testimony
  label and the Not Guilty / Guilty verdict come from the DS version too: the banners shrunk to
  the width of the GBA's, with the DS's shine and flash; the verdict in the DS's serif letters,
  each zooming in as on the DS.
* 0.12 — graphics from the DS version in place of the ones the build drew itself: the
  Objection! / Hold it! / Take that! bubbles (shrunk to the GBA screen), the SAVE and LOAD
  headers, the Yes / No and continue-screen buttons (now From save point. / From chapter start.,
  as on the DS), and the episode-select boxes and labels. College Phoenix's sweater says P, and
  the policeman loses his armband, as on the DS. Fixes: while the text box grows into a choice
  (and shrinks back after it), the page's text no longer smears over the rows the box passes; a
  strip of the name tag no longer stays above the box when the next line has no name, after a
  choice or when the box closes; hiding the text box no longer writes its state to a stray
  address.
* 0.11.8 — cross-examination statements keep clear of the arrows to the previous and next
  statement (the left arrow covered the first letter of the second line); a save made during
  a cross-examination shows its statement again when continued.
* 0.11.7 — continuing a save shows the page you stopped on again (the text box came back
  empty, and a choice came back with no question and no options), and saves carry over to
  newer builds of the patch (they kept a ROM address that moves when the script changes).
* 0.11.6 — fix: the shared script lines the game calls up by number were two places off from
  the DS ones from the continue screen on (the DS added two messages there). Examining a spot
  with nothing in it showed a debug line and the game stopped; presenting the wrong evidence
  in court played the wrong response; the continue screen showed a DS error message instead
  of the part you saved in. The continue screen's two buttons are in English (Resume Play,
  Restart Part).
* 0.11.5 — the metal detector tutorial in case 5 gives the GBA controls (the display turns red,
  press the A Button) instead of the DS touch screen's.
* 0.11.4 — lines that trail off (Ron's mumbling) fade out as in the original.
* 0.11.3 — the staff roll at the end of the game is placed as in the original (it was drawn at
  the bottom of the screen); captions of more than one line ("5 Years Earlier") start at the
  height the original moves them to.
* 0.11.2 — the episode-select prompt no longer stays on screen after an episode is picked (it
  went with the box in the original); `gs3_script.py` shows the music note.
* 0.11.1 — the escaped convict's data screen in episode 4 in English (its title bars, from the
  DS version).
* 0.11 — pictures with writing in them in English: the L Button pages, letters, maps, the
  newspapers, the calling card, the poster and the signs in the backgrounds (39 pictures, taken
  from your DS ROM while building).
* 0.10.1 — browsing the Court Record no longer leaves garbage in the text box: the Court Record
  borrows the text box's tiles to slide between items; the box showed empty during the slide
  and the text came back afterwards (0.15.9 keeps it in view).
* 0.10 — Talk topics and Move destinations, the episode-select titles and labels, the save
  screen, the Psyche-Lock "Unlock Successful" banner and the verdict in English. Lines shown
  without the text box are placed as in the original (the episode-select prompt was drawn over
  the boxes), and the save prompt no longer stays on screen after the save screen closes.
* 0.9.1 — fix: starting an episode from the episode select (or continuing a save at the start
  of a chapter) loaded the Japanese script for chapters 3, 7, 13, 17, 28, 32 and 34's first
  part; the loader had a second set of pointers to those banks. Investigation menu tabs in
  English.
* 0.9 — OBJECTION!, HOLD IT! and TAKE THAT! bubbles in English.
* 0.8.1 — the case 1 tutorial lines that said to touch the Court Record Button now say to press
  the R Button (and "Touch to see before and after" for the Hanging Scroll says Press L);
  choice labels with quotation marks ("You were blinded?") showed parentheses instead;
  `gs3_script.py --table en` now shows Phoenix's thoughts as ( ), and the DS font's hyphen,
  quote and accented letters.
* 0.8 — Witness Testimony / Cross Examination banners, the Testimony label, the
  cross-examination buttons and the OK / Back prompts in English.
* 0.7 — Court Record in English: names and descriptions of all 211 evidence and profile
  entries, taken from your DS ROM while building (the DS stores the descriptions as pictures;
  the build reads their text back with the DS font and sets it again for the GBA panel), and the
  R Profiles / R Evidence label.
* 0.6.1 — script and box fixes: the DS command `0x3a` is now read with its three arguments,
  which fixes about 20 boxes in cases 3–5 where a word was cut ("ini" for "Bikini"), a stray
  character box appeared, or two boxes ran together; the GBA's own `0x53` commands are kept; no
  more 16×8 scrap of box frame left at the bottom of the screen after the text box closes.
* 0.6 — `hacking/` notes and tools. Build fixes: the three label jumps (command `0x36`) now land
  where they should, partial banks keep their structure, the common bank's true size is used,
  and a bank directory at `0x08800000` lets tools edit the English text.
* 0.5 — English voice clips from the DS version.
* 0.4 — voice-clip import (`voices/`) and sample export.
* 0.3 — English title screen and title menu.
* 0.2 — Python-only build tool; English choice menus; caption screens.
* 0.1 — first preview (script, font, three-line box, name tags).
