# Gyakuten Saiban 3 — English build tool

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

Still Japanese for now: the in-court speech bubbles ("Objection!" etc.), the testimony /
cross-examination banners, the investigation and court-record buttons, the episode titles on the
episode-select screen, and the voice clips.

## Your own voice clips

The shouts ("Objection!" and so on) are 8-bit samples in the GBA ROM. To replace them with
recordings of your own:

1. `python3 build.py gs3_jp.gba tt_us.nds --export-voices samples/` writes every candidate
   sample as a `.wav` named by its ROM offset, so you can hear which is which. The sample at
   `0xed1c0` is Mia's "Take that!"; the others are identified by ear.
2. Put your clips in `voices/` and write `voices/voices.json` mapping sample offsets to files
   (see `voices/voices.example.json`). WAV is read directly; other formats need ffmpeg.
3. Build as usual. Clips are resampled to at most 22 kHz, converted to 8-bit, placed in the
   expanded ROM, and the sound driver's instruments are repointed at them.

The `voices/` folder is ignored by git, so recordings stay on your machine.

## Version history

* 0.4 — voice-clip import (`voices/`) and sample export.

* 0.3 — English title screen and title menu.
* 0.2 — Python-only build tool; English choice menus; caption screens.
* 0.1 — first preview (script, font, three-line box, name tags).
