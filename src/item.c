/* The item shown in court waits for a shout bubble to go (patches/icons.py, item_waits).
 *
 * The item shown in court (OAM 65) is run by 0x0801545c every frame (from the vertical blank's
 * updates, 0x08000430, and once from 0x0801db9c), its state in SYS+0x99: state 3, set by script
 * command 0x13, unpacks its picture and copies it to OBJ tiles ITEM_TILE (0x1e0-0x21f in the
 * English build; the original's 0x80-0xbf are the English page's third line); state 5, the item
 * put away while the Court Record is open, copies it again once the Record has gone (SYS+8, the
 * mode, back to 6 or under).  The shout bubbles (effects 1-9) keep their pictures from tile
 * 0x1e8, so a copy made while a bubble is still on screen writes over the bubble's top left: for
 * its last frames the bubble shows the item's picture in the bubble's palette.  Presenting
 * evidence in court does just that: the Record goes, Take that! (or Objection!) stays up two
 * frames longer, and an item up before the Record opened comes back, or the section the evidence
 * leads to puts one up at once (Larry's profile in episode 5, bank 30 section 0xde).  The
 * original, its item in other tiles, shows both.
 *
 * So in those two states the item's update waits while a sprite in the bubbles' palette uses the
 * item's tiles, in the OAM shadow or in OAM itself: it does nothing that frame and the state
 * stays.  The bubble goes as it does in the original and the item comes up after it, two frames
 * later than the original's; the script goes on as before (command 0x13 takes its 16 frames all
 * the same).  The wait ends with the bubble, which shows one frame for a fixed time; MAX_WAIT
 * frames at most, whatever is there.
 */
#include "gba.h"

#define OAM_SH      ((volatile u16*)0x03002ba0)   /* OAM shadow, 4 halfwords per entry */
#define OAM         ((volatile u16*)0x07000000)
#define ITEM_ENTRY  65
#define BUBBLE_PAL  11                             /* the bubbles' OBJ palette */
#define ITEM_TILES  64
#define MAX_WAIT    60
#define ITEM_STATE  0x99                           /* SYS+0x99 */
#define MODE        8                              /* SYS+8: 7 while the Court Record is up */
#define ITEM_FRAME(s) ((void (*)(volatile u8*))0x0801545d)(s)

static u8 waited;

/* tiles a sprite takes, by attr0 shape and attr1 size */
static const u8 tiles[3][4] = { { 1, 4, 16, 64 }, { 2, 4, 8, 32 }, { 2, 4, 8, 32 } };

static int over_item(volatile u16* oam) {
    for (int i = 0; i < 128; i++) {
        u32 a0 = oam[i * 4], a1 = oam[i * 4 + 1], a2 = oam[i * 4 + 2];
        if (i == ITEM_ENTRY || (a0 & 0x300) == 0x200 || a0 >> 14 == 3 || a2 >> 12 != BUBBLE_PAL) continue;
        u32 t0 = a2 & 0x3ff, t1 = t0 + tiles[a0 >> 14][a1 >> 14];
        if (t0 < ITEM_TILE + ITEM_TILES && t1 > ITEM_TILE) return 1;
    }
    return 0;
}

/* in place of 0x0801545c at both its calls */
void item_frame(volatile u8* sys) {
    u32 s = sys[ITEM_STATE];
    if ((s == 3 || (s == 5 && sys[MODE] <= 6)) && waited < MAX_WAIT && (over_item(OAM_SH) || over_item(OAM))) {
        waited++;
        return;
    }
    waited = 0;
    ITEM_FRAME(sys);
}

void _start(void) {}
