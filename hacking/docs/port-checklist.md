# What the English build must get right

The English build puts the DS version's English script into the GBA game. Getting the words in
is the easy part. These are the ways a port like this goes wrong, and what to check so that this
one doesn't. Keep them in mind for every change to the script converter and every case that is
played through.

## 1. The GBA script's commands stay with the lines

A script line is more than its text. Between the words, the script changes a character's
animation (Phoenix coughs and sneezes in the middle of his lines in Turnabout Memories), switches
poses, plays sounds, flashes and shakes the screen, and pauses. Taking the DS lines as they are
and losing what the GBA script does between them leaves the words right and the scene wrong: a
character stuck in one pose for all of his lines.

* In this build, `tools/convert_script.py` builds each section from the DS English command
  stream. A command that lines up with one of the GBA's gets the GBA's arguments. A command the
  GBA script has and the DS doesn't is carried over only if it is a sound (the `gba_sounds`
  count the build prints). Any other GBA-only command is not in the output, for example an
  animation the DS does with different commands. Find out what that leaves out before trusting
  a case.
* Check by comparison: for each message, list the commands of the Japanese GBA script and of
  the English build (`hacking/tools/gs3_script.py` dumps both). Anything the Japanese has and the
  English lacks has to be a deliberate drop, with the reason written down.
* Check in play: Turnabout Memories from the start, side by side with the Japanese ROM. Every
  animation that plays in the middle of a line in the Japanese has to play in the English.

## 2. Name tags follow the speaker

Every line has to carry the name of the character saying it. The name tag is set by a script
command. When the DS sets it at a different point than the GBA, or a message boundary moves in
the merge, a run of lines can carry the previous speaker's name.

* Check by comparison: the name tag in force on every English text page is the one in force on
  the Japanese page it replaces.
* Check in play: the name tag on every line of case 1, especially where the speaker changes
  without a new message, and where several lines in a row belong to someone else.

## 3. The text fits the GBA scene, not just the DS box

The words are the DS English script, but they are played in the GBA's scenes. Where a scene
waits for a button, pauses, plays a sound or moves a character comes from the GBA script. A port
is more than the DS text shown in the GBA's box. Line and page breaks have to suit the box, and
no line may end up before or after the animation, sound or pause it belongs with.

## 4. Why the GBA edition exists

If the English build plays worse than the DS version, there is no reason to play it: its point
is the GBA game itself, in English. A patch that covers less but plays right is better than a
complete one with these faults. A case isn't done until it plays as cleanly as the Japanese.

## Checklist for a case

* Animations in the middle of lines play as in the Japanese (start with Phoenix in Turnabout
  Memories).
* Every line's name tag is the speaker's.
* Sounds, flashes, shakes and pauses come at the same points as in the Japanese.
* Text breaks suit the box, and nothing runs out of it or is cut.
* Choices, Court Record prompts and cross-examinations behave as in the Japanese.
