# Plans

Work agreed on but not started (nothing of it is in the build), and plans since carried out.
They are kept here because plans made in conversation alone have been lost before.

## Done

* The text box (0.16.68): the original's 48 pixels again, the three lines 14 pixels apart, in
  place of the 64-pixel box of 0.16.8-0.16.67 (and the 56-pixel one before it). The DS shows the
  GBA's scene moved down 16 pixels with the top of its box where the top of the original's is
  (y 112 in GBA terms), so the box now covers exactly what the original and the DS cover, for
  every character and close-up. That also settles the plan to raise Pearl alone and fill her
  sprites from the DS's extra rows (scoped the same day): with the original box she is framed as
  on the DS without it.

## Gyakuten Saiban translation tools for the GBA trilogy

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
