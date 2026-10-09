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

Still Japanese for now: the in-court speech bubbles ("Objection!" etc.), the testimony /
cross-examination banners, the investigation and court-record buttons, the episode titles on the
episode-select screen, and the voice clips.

## Version history

* 0.3 — English title screen and title menu.
* 0.2 — Python-only build tool; English choice menus; caption screens.
* 0.1 — first preview (script, font, three-line box, name tags).
