# Gyakuten Saiban 3 GBA English translation

<img width="400" height="266" alt="image" src="https://github.com/user-attachments/assets/5b35b4c8-c8e0-4f19-8cbe-5c49a6f609d9" />

A fan translation of Gyakuten Saiban 3 that uses the English DS script, features three lines, a vwf and of course, as always English!

Builds an English-language ROM of *Gyakuten Saiban 3* (Game Boy Advance) from your own copies of
the two games:

* `gs3_jp.gba` — Gyakuten Saiban 3 (Japan), 8 MB, CRC32 51B6CF22
* `tt_us.nds`  — Phoenix Wright: Ace Attorney – Trials and Tribulations (USA), game code YG3E

The English script, font, name tags, Court Record, menu labels, talk topics, episode titles,
pictures and other English material are read out of the DS image while the ROM is built. This tool only contains the code changes (the new text engine,
the script converter and the hooks); nothing from either game is stored in it.

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

* Variable-width English font (the DS font) in a three-line text box.
* The complete DS English script, including the choice-menu options.
* English name tags from the DS version.
* Court Record in English: every evidence and profile name (the DS name pictures) and
  description (the DS text, set in a small font so it fits the GBA panel; "Touch the Check
  Button" becomes "Press L"), and the R Profiles / R Evidence switch.
* Witness Testimony / Cross Examination banners (bold italic lettering after the DS ones), the
  Testimony label, the cross-examination buttons (L Press / Present R) and the OK / Back
  prompts when presenting.
* OBJECTION!, HOLD IT! and TAKE THAT! speech bubbles.
* Investigation menu tabs (Examine, Move, Talk, Present), and the Talk topics and Move
  destinations (the DS version's pictures, copied into the GBA boxes).
* Episode select: the episode titles (from the DS script) and EPISODE 1–5 labels.
* Save screen: SAVE header, Yes / No and the note under them; the continue screen names the
  part you saved in and offers Resume Play / Restart Part.
* Unlock Successful when the last Psyche-Lock breaks, and the NOT GUILTY / GUILTY verdict.
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

The Court Record descriptions use Spleen 5x8 by Frederic Cambus (BSD 2-Clause licence, see
`tools/fonts/LICENSE.spleen`).

## Hacking the game yourself

`hacking/` holds format notes (script, text engine, graphics, sound, memory map) and
command-line tools for the Japanese ROM and for ROMs made by this build: dump and re-insert
script text, extract and replace backgrounds, view tiles and the font, export and replace
samples, find cross references, plus a headless mGBA harness for tracing. See
[hacking/README.md](hacking/README.md).

## Version history

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
  borrows the text box's tiles to slide between items; the box now shows empty during the slide
  and the text comes back afterwards.
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
