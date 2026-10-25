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
savestates hold the script's addresses: from 0.16.27 every script bank has a fixed slot in the
ROM (`data/bank_slots.json`), and from 0.16.38 a script fix leaves every section where it was (a
section a fix changes gets its new version after the other sections of its bank, or at a fixed
place at the end of the ROM when the bank's slot is full, and keeps the old one in its place), so
a savestate made with 0.16.27 or later keeps working in later builds.
One made with 0.16.26 or older finds its script moved in 0.16.27 and can freeze or show garbage;
load an in-game save instead.

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
* College Phoenix's sweater says P instead of RYU, and Larry's armband with Japanese
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

* 0.16.57 — the wide view of the courtroom when Iris screams in episode 5's last trial showed a
  black screen with broken tiles: the background change that comes with it on the GBA was lost
  (the DS draws that view its own way). It shows the courtroom again, as in the Japanese game and
  on the DS. Savestates from earlier builds keep working.
* 0.16.56 — the script checked command by command against the Japanese GBA one, and what the
  English game lost put back. A soft lock in episode 5: after anything Gumshoe's metal detector
  found, the game stopped for good, because the commands that hand the game back to the search
  were missing (the DS does that its own way); and the first lines after the search ran with the
  text box shut. Two choices whose wrong answer costs 16 of the life bar (episodes 3 and 4)
  showed no risk on the bar and took off whatever amount was set last, usually none. Pointing at
  the map in episode 5's trials has its "L Stop" again, to back out of the question. Smaller
  things as the Japanese game has them: the box hidden before the Judge reacts to a wrong piece
  of evidence, the evidence picture put away in two scenes, the music fading at the end of a
  part of episode 3, a newspaper in the restaurant's rack. Checked as well and found right: every
  conditional jump (308) lands where the Japanese one does, and every choice, label and
  next-part jump goes to the same scene. Savestates from earlier builds keep working: the
  changed scenes that no longer fit in their bank's space go to a fixed place at the end of the
  ROM, and nothing else moves.
* 0.16.55 — the page arrow no longer runs into the text: a third line long enough to reach it
  (about 300 pages; the DS's box is 16 pixels wider, so the same lines end well clear of its
  arrow) closes up by the few pixels it needs, spread over its letter gaps, and ends just before
  the arrow, which stays where the DS has it. Other lines are as they were. Savestates from
  earlier builds keep working.
* 0.16.54 — after a game over the courtroom doors close before the title screen again, as on the
  Japanese GBA and the DS: the English script went from the Judge's gavel to a black screen. The
  DS closes the doors from its own code, so its script has no commands for them and the
  conversion lost the GBA's; they are back in all 15 game-over scenes, frame for frame as in the
  Japanese game. Savestates from earlier builds keep working.
* 0.16.53 — a soft lock when the penalty bar ran out in the second part of a chapter (Godot's
  coffee mug in episode 2's second trial day, for one): instead of the Judge's guilty verdict the game stopped on an
  empty text box. A chapter too long for one script bank continues in a second one, and the
  Japanese game reaches the chapter's game-over scene, kept in the first, through what is left of
  that bank in memory; the English banks stay in the cartridge, where that look-up landed in the
  next bank's script. The second banks now point at the first's scenes: the game over plays to the
  end and back to the title screen in all ten such banks, as in the Japanese game. Saves and
  savestates from earlier builds keep working (one already stuck stays stuck).
* 0.16.52 — every Objection!, Hold it! and Take that! bubble shows in the middle of the screen,
  whoever shouts, as on the DS (checked against the US DS release running in DeSmuME), where the
  defence's sat towards the left and the prosecution's towards the right.
* 0.16.51 — lines shown in the text box without a name tag (Mia's "...Phoenix..." in episode 2's
  flashback, Adrian Andrews's "...*CRASH*...") start on the box's first line, as on the DS (checked
  against the US DS release running in DeSmuME), where they sat a line lower. Savestates from
  earlier builds keep working.
* 0.16.50 — lines shown in the text box without a name tag (Mia's voice in episode 2's
  flashback, and the like) wait with the DS's arrow at the right of the box, as every other page
  does; they had the original's, pointing down in the box's bottom edge. Savestates from earlier
  builds keep working.
* 0.16.49 — lines the English DS centres where the Japanese script does not (29 of them) are
  centred where they belong: Mia's "...Phoenix..." in episode 2's flashback, and the other
  voices and sounds shown without a name tag ("...*CRASH*...", "...click..."), were drawn in the
  middle of the screen above an empty text box; they are in the box now, centred, where the
  Japanese GBA has them. The rest (episode 5's date cards among them) get the same centring as
  the lines both DS scripts centre. Savestates from earlier builds keep working.
* 0.16.48 — a choice's question sits 4 pixels lower at the top of the screen, clear of the
  penalty gauge: a long first line ran on under the gauge and touched it. The answers stay where
  they were. Savestates from earlier builds keep working.
* 0.16.47 — a choice's question no longer disappears after continuing a save made while the
  question was waiting for the A Button: it came back in the box, and when the options came up
  the question was gone (and sometimes the box with it). It now comes back the way it is typed,
  so it moves to the top of the screen above the options as usual. Saves and savestates from
  earlier builds keep working; a savestate already showing the broken choice stays that way, but
  continuing the in-game save again brings it back right.
* 0.16.46 — the Court Record's Back prompt is whole: while presenting, its k was cut off at the
  screen's edge, and it was squeezed with the c against the k. Back is drawn at its full width
  now (only the B and a set a pixel closer), and the B icon and the prompt sit 10 pixels left of
  where the original has them, in a photo's detail view too (the L icon with them). Savestates
  from earlier builds keep working; one made with the Court Record open shows the old prompt
  until it is opened again.
* 0.16.45 — a line that trails off (Ron's mumbling) fades out in the DS's four greys: the
  second step was darker than the DS's and the same as the third, so the line went from light
  grey straight to the darker one and stayed there. The split points were already the DS's (the
  last few characters in the darkest grey, nearly the box's own, as on the DS and the Japanese
  GBA). Savestates from earlier builds keep working.
* 0.16.44 — Godot's coffee mug: after the mug slides along the desk into his hand, he settles
  holding it, as on the DS, where the GBA kept the last frame of the slide (the DS gives the pose
  its own resting picture, which the GBA has too). The script nearly always moves him on to
  another pose before he would settle, so it shows in one place, a short line of his in
  episode 3. One more of his gestures gets the DS's resting picture (mouth shut instead of
  open), though the script never lets it show. Savestates from earlier builds keep working.
* 0.16.43 — the page arrow stays white after a Psyche-Lock is broken: it used a sprite palette
  that the Psyche-Lock sequence loads its own colours into, and came out pale blue after one.
  It now uses the text's white, which stays the same in every scene. Savestates from earlier
  builds keep working.
* 0.16.42 — Pearl blinks after her shy hand-to-mouth gesture, as on the DS: the GBA held the
  gesture's last frame until the next page, the DS switches to her blinking idle once she has
  finished talking. The GBA has that animation already (it starts on the picture the gesture
  ends on), so 53 of her poses take it as their idle, 17 of them in episode 2. Savestates from
  earlier builds keep working.
* 0.16.41 — character poses checked against the DS and the Japanese GBA across the game. Four
  were off, all outside episode 2: in two of the Judge's lines in episode 1 he spoke with his
  mouth shut (the GBA sets his pose twice there and the DS once, and the conversion took the
  wrong one of the two), and two poses the DS writes a little later than the GBA were missing
  (one of Godot's in episode 3, one of Gumshoe's in episode 5). The rest match the GBA everywhere; where a
  mouth stays still in episode 2 (some of Godot's and Pearl's gestures, a pause in a line), the
  Japanese GBA game plays it the same way. Savestates from earlier builds keep working.
* 0.16.40 — Ron's "night of the crime" flashback now keeps the original timing too in a save
  with that flag on: the game sees the flash that could not end coming, switches the flag off
  there and waits for the fade, as the scene plays with the flag off. The fade back from white
  runs its full length, then the pause, then the one flash, frame for frame as in the Japanese
  game and the DS (0.16.39 had the flash half a second early). The flag stays off afterwards
  until a scene sets it on purpose. Nothing changes in a save with the flag off.
* 0.16.39 — asking Ron DeLite about the night of the crime, the screen flashed white every four
  frames through his second flashback, for several pages. The game holds the script while the
  screen fades, except while a flag lets it run on; that flag is set by the opening of episode 1
  and by a later scene, is kept in the save, and was on in this playthrough. A flash then started
  in the middle of the fade in from white, at a brightness its steps never bring back to normal,
  and it went round and round; the Japanese game does the same with the flag on. A fade that
  could never end now finishes the fade under way first (the flash goes off once, as when the
  fade has ended), and one already going round stops. Fades that end as before are unchanged.
  Savestates from earlier builds keep working; one taken during the flashing stops it at once.
* 0.16.38 — after asking Ron DeLite about the night of the crime, the security camera's picture
  stayed up behind the talk menu instead of his room. The DS changes the background back with a
  command of its own there, which the conversion left out, and the GBA's own was not put back.
  Six such background changes were missing, now restored as the Japanese game has them: the
  same thing in a second talk with the camera picture, a cut to the prosecutor's bench in
  episode 2's trial, and, at the very end of the game, the two pictures after the staff roll
  (with the first one's pan), where the screen stayed black. Savestates from earlier builds keep
  working, the changed conversations included.
* 0.16.37 — breaking Larry's last Psyche-Lock: instead of the locks shattering over the dark
  background, the room came back in grey and broke up into a mess of tiles before the
  "Unlock Successful" banner. The DS's English script lost a one-frame wait there that the
  Japanese GBA and DS scripts have at the end of every Psyche-Lock, so the room's background
  and the lock flag were changed while the unlock sequence was still running. The game now
  stops for that frame as the Japanese script does; the scene plays out as in the Japanese
  game (checked frame by frame), and savestates from earlier builds keep working.
* 0.16.36 — after the save screen (saving, or closing it with "No") or a continued save, a
  choice's question could come back with its lines going grey partway along: a line that trailed
  off earlier in the conversation ("..." fading out) was still counted as fading. The page is
  now put back with the fade on only the lines that have it, as the game types them.
* 0.16.35 — a choice whose options are too long for the box (eight in the game, such as "Mr. Atmey
  is no Ace Detective!") had their ends cut off at the right edge. When one of a menu's options
  does not fit, every option of that menu has its letters set a pixel closer together, the way a
  page line that does not fit already was, so they all fit and still look alike.
* 0.16.34 — the English text engine's work between frames is down to about a quarter (4 scanlines a
  frame on a dialogue page, from 16): on busy frames it pushed the game's own updates past the
  time the screen is not drawn, and a character or effect showed half updated at the top of the
  screen about ten times as often as in the Japanese game. Frames that run late because of it are
  now about one in four hundred in a trial, where the Japanese game's own heavy frames are about
  one in two hundred; the game also drops fewer frames on busy choice screens.
* 0.16.33 — on a choice, a block of a character could show torn at the top of the screen
  (Phoenix's hair over the question): the work 0.16.31 added between frames pushed the game's
  own updates past the time the screen is not being drawn. It now writes only what changed, and
  the text engine's checks on a choice screen are cheaper too, so the updates end earlier than
  before 0.16.31.
* 0.16.32 — the hand cursor on a choice's third option showed a square of the defence bench
  over the box (a sprite-order quirk of the hardware, met now that a three-line question puts the
  options a row lower): the cursor is drawn ahead of the bench. And a choice left framed by a
  save state from 0.16.30 or before no longer shows the box solid behind its question.
* 0.16.31 — a question asked before a choice (Phoenix's blue thoughts, an orange word) took the
  colour of the scene behind it, paler over a bright wall than over a dark suit: it was drawn on the
  text box's own layer, which the game blends with the scene. It now goes on a layer of its own over
  the box and keeps the same colours as every other page.
* 0.16.30 — the Witness Testimony / Cross Examination banners go 8 pixels higher again, so their
  lettering ends 4 pixels above the text box (which shows the testimony's title under them)
  instead of touching it.
* 0.16.29 — the Witness Testimony / Cross Examination banners sit 4 pixels higher and Unlock
  Successful 7: each now keeps the DS's spacing from its anchor (shrunk with the picture) instead
  of hanging from where the original's one-line banner started.
* 0.16.28 — a page whose box hides partway through (for a point or a desk slam, 14 pages in all,
  as in the Japanese and the DS) lost the lines typed before the hide: the box came back with
  only the rest of the page. The page's text now comes back with the box.
* 0.16.27 — a check of every jump and command in the script against the Japanese one: where the
  DS moved a command further along a section, the converter lost it on both sides. Four
  conversations in episode 3 never marked themselves as heard (and played their first-time
  version every time), four lines lost their speaker's name tag, and a few box hides went with
  them: 24 commands, now kept where the DS has them. The markers the GBA places on episode 4's
  maps (the DS draws its maps with them in) were missing too: 22 marker commands are back.
  The script banks now sit in fixed slots, so later script fixes no longer move them (savestates
  from 0.16.27 on keep working in newer builds; older ones do not carry over to this one).
* 0.16.26 — the L button's label while breaking Psyche-Locks reads Stop (it was still やめる), and
  the Court Record's A-button label きりかえ reads Swap.
* 0.16.25 — a soft lock halfway through episode 2: asking about a topic again could leave the
  text box up with nothing in it and the game waiting for good. The script's conditional jumps
  point at a byte position inside their section, and the converter kept the DS script's
  positions, which are a few words off in the converted English script; 17 of the 308 were wrong,
  that one landing past the command that closes the box. They now point at the same place as on
  the DS.
* 0.16.24 — the episode select's prompt box is whole again (since 0.16.22 its top edge sat a row
  too high over an empty row) and grows to hold the two-line prompt for a newly added episode.
  Pieces some rooms draw over their background as it loads (the statue in the basement warehouse,
  the stone at the bridge) no longer bring back strips of the Japanese signs behind them.
* 0.16.23 — the newly added episode's box no longer loses its bottom-right corner on the screen
  that announces it after an episode ends: the prompt under it cleared tiles the box needs.
* 0.16.22 — the third line stays on screen while the Court Record is open with a large
  character in the scene: it moves to sprite tiles nothing on screen is using (and gives them
  back when the Record closes) instead of being hidden. "THE END" after an episode is no longer
  cut off at the right edge.
* 0.16.21 — the page stays where it is when the Court Record opens (0.16.18 undone). A pale strip
  in the top corner left by an evidence box under an earlier build (and kept in saves made with
  it) is cleared as soon as the game is continued.
* 0.16.20 — opening the Court Record with certain large characters on screen (Armando, for
  one) turned the page's third line into coloured blocks, which stayed after the Record closed:
  the Record puts its picture in the original's spare tiles there, which are the third line's
  in this build. The third line now steps aside while the Record has them and the page is drawn
  again when it closes.
* 0.16.19 — episode 4 froze on a black screen at its first data screen (the escaped convict's
  file), whose two pages were also unreadable: the screen draws one sprite per character from
  the Japanese font, and the English pages ran it past the end of the sprite table into the
  game's state. The pages are now drawn in the English font, a few letters to a sprite, wrapped
  round the photo; the "Fugitive Data" header moves out of their tiles.
* 0.16.18 — with the Court Record open over a page, its button row (Profiles / OK / Back) sat on
  the page's first line, which could not be read (the original's text started lower). While the
  Record is open the page's lines now sit 8 px lower, clear of the buttons.
* 0.16.17 — a short pale strip (the top corners of an evidence box) stayed in the top-left or
  top-right corner after almost every item the script takes down: the last step of the box's
  closing animation cleared its smallest frame by hand at the box's old rows. It clears them a
  row higher now, with the box.
* 0.16.16 — the life bar lost its frame and its end while an Objection! / Hold it! / Take that!
  bubble was up (presenting the wrong evidence, among others). The English bubbles took 16–24
  sprites to the original's 7, and the game hands sprites to animations from the top of the
  list down with no limit, so they ran into the bar's. The bubbles are now half the DS picture,
  128×96, in four sprites; the bar is whole as in the original.
* 0.16.15 — the top edge of an item's box stayed on screen (a row of pale frame tiles along the
  top of the scene) after the item was taken down with a scene change: a second, inline clear
  of the box's rows still started at the old row. It starts at row 0 now, with the box.
* 0.16.14 — the name tag still lost its top row whenever an item shown in court was taken down
  or replaced: the box's erase cleared ten rows from the old row, the last of them the tag's.
  The erase and the right-hand item box move up with the box.
* 0.16.13 — 0.16.12 moved the item's box up but not the picture in it on the path that places
  it every frame, so the picture hung out of its box by a row. Both sites now place it.
* 0.16.12 — the item shown in court cut the name tag in half: its box on the background ended
  on the row the tag now starts on, above the taller text box. The item's box and picture sit
  one tile row higher.
* 0.16.11 — saving on a choice: the options drew over the save screen, and the game continued
  from that save with the question in the wrong colours and the options a few rows too low,
  off the cursor. The page's sprite text now goes while the save screen is up, and a continued
  choice puts its options under the question where the cursor is, with the question's colours.
* 0.16.10 — a game saved with a build before 0.16.8 (the shorter box) and continued on this one
  came back with an empty box: the save carries the box's map rows, so the box was put back a
  row lower than this build draws it and the page was never drawn again. The box is moved up
  when such a save is continued, and the page follows. Saves made on this build were fine.
* 0.16.9 — two animated effects drew their pictures into the third line's sprite tiles when
  they played over a page (the news report's "Fugitive Data" header, and a figure in the dark
  in a later episode): they are moved to the Court Record's tiles. A check of every effect in
  the game's animation table found no other that plays over a page from the text tiles.
* 0.16.8 — the text box is the DS box's height: 64 pixels (one tile row taller), with the
  DS's 60 pixels between its border lines, so the three lines sit 4 pixels below the top
  border as on the DS and the page arrow 10 pixels above the bottom one, where the box used to
  run out right under the third line. The name tag rides up with it; the arrows to the previous
  and next statement sit on the second line.
* 0.16.7 — the page arrow is the DS's: a white triangle pointing right at the end of the
  third line, sliding sideways as it does there (measured frame by frame on the DS), in place
  of the GBA's down-pointing triangle bobbing in the box's bottom edge.
* 0.16.6 — the text sits in the box as on the DS: lines start 8 pixels inside it (they
  started at 2, against the frame), measured against the DS running in an emulator; the
  glyphs, widths and line breaks were already the DS's. The GBA box is 16 pixels narrower, so
  the lines wider than 230 pixels (under 1%, up to 246) keep the letter spacing a pixel
  tighter rather than breaking elsewhere than the DS.
* 0.16.5 — the box came back empty after the START save screen was closed with "No" (the
  original restores the box's tiles, which held its text; the English page is sprite text):
  the page is drawn again, as it is when a saved game is continued. A sweep of the trial and
  investigation flows against the Japanese GBA and the DS (testimony statements, cross-
  examination with Press and Present, the part boundary with its save prompt, Continue from
  the chapter start and from a save point, examine and move in the investigation) found
  nothing else; the chapter name over Dahlia's statement (0.16.4) is the load screen's
  caption when a suspended game is continued from its save point, and 0.16.4 fixes it on
  that path.
* 0.16.4 — text drawn over a page in the box during a testimony (the chapter's name, "Turnabout
  Memories / Part 1-2", on top of Dahlia's statement): the game runs the common bank's system
  messages (the chapter names, the save prompts) through the text engine (the load screen's
  caption, when a suspended game is continued from its save point), and the English build
  drew them on the page; they are left out unless a save or continue screen is up. A page the engine starts over without clearing (its own
  cell counters back at 0, 0) now starts ours over too, so two pages can no longer overlap.
* 0.16.3 — the Testimony label in the top left corner sits three pixels in from the edge (the
  DS lettering fills its sprite edge to edge, where the Japanese 証言中 had a margin, so it
  looked cut off against the corner).
* 0.16.2 — the third line of the box broke up into coloured blocks in scenes with sprite effects
  over the dialogue (Dahlia's butterflies): the effects' tiles sat where that line's cells were.
  The page now uses the sprite tiles the original keeps for its own text plus the item shown in
  court's, and that item (the picture at the top left when evidence is shown) moves to the Court
  Record's tiles, which are free whenever it can be on screen.
* 0.16.1 — the engine's own continue arrow showed in the middle of the box next to ours (it
  bobs through four tiles, and only one of them was being taken out); ours now bobs with it at
  the right, as the original's does. The Back prompt in a photo's detail view ran off the
  screen: the B and L icons and the prompt sit three pixels further left and the prompt is
  drawn 27 pixels wide at most. The sprite cells are cleared at the start of every page,
  whether or not it begins with a line break.
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
  Larry loses his armband, as on the DS. Fixes: while the text box grows into a choice
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
