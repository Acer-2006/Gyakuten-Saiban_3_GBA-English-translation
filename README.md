# Gyakuten Saiban 3 GBA English translation

<img width="400" height="266" alt="image" src="https://github.com/user-attachments/assets/5b35b4c8-c8e0-4f19-8cbe-5c49a6f609d9" />

A fan translation of Gyakuten Saiban 3 that uses the English DS script, features three lines, a vwf and of course, as always English!

Builds an English-language ROM of *Gyakuten Saiban 3* (Game Boy Advance) from your own copies of
the two games:

* `gs3_jp.gba` — Gyakuten Saiban 3 (Japan), 8 MB, CRC32 51B6CF22
* `tt_us.nds`  — Phoenix Wright: Ace Attorney – Trials and Tribulations (USA), game code YG3E

The English script, font, name tags, menu labels and other English material are read out of the
DS image while the ROM is built. This tool only contains the code changes (the new text engine,
the script converter and the hooks); nothing from either game is stored in it.

## Use

Requires Python 3.8 or newer, nothing else.

    python3 build.py gs3_jp.gba tt_us.nds -o gs3_en.gba

Takes about 20–30 seconds. The output `gs3_en.gba` (16 MB) runs in any GBA emulator or on a
flash cart.

## What the English build changes

* Variable-width English font (the DS font) in a three-line text box.
* The complete DS English script, including the choice-menu options.
* English name tags from the DS version.
* Caption screens ("5 Years Earlier", date/location cards) in English.
* English title screen (DS logo) and title menu.
* The English voice clips ("Objection!", "Hold it!", "Take that!") from the DS version.

Still Japanese for now: the in-court speech bubbles, the testimony / cross-examination banners,
the investigation and court-record buttons, and the episode titles on the episode-select screen.

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

## Hacking the game yourself

`hacking/` holds format notes (script, text engine, graphics, sound, memory map) and
command-line tools for the Japanese ROM and for ROMs made by this build: dump and re-insert
script text, extract and replace backgrounds, view tiles and the font, export and replace
samples, find cross references, plus a headless mGBA harness for tracing. See
[hacking/README.md](hacking/README.md).

## Version history

* 0.6 — `hacking/` notes and tools. Build fixes: the three label jumps (command `0x36`) now land
  where they should, partial banks keep their structure, the common bank's true size is used,
  and a bank directory at `0x08800000` lets tools edit the English text.
* 0.5 — English voice clips from the DS version.
* 0.4 — voice-clip import (`voices/`) and sample export.
* 0.3 — English title screen and title menu.
* 0.2 — Python-only build tool; English choice menus; caption screens.
* 0.1 — first preview (script, font, three-line box, name tags).
