/* The item shown in court and the effects that share its tiles (patches/icons.py, item_waits).
 *
 * The item shown in court (OAM 65; 72 or 0 in some modes) is run by 0x0801545c every frame (from
 * the vertical blank's updates, 0x08000430, and once from 0x0801db9c), its state in SYS+0x99:
 * state 3, set by script command 0x13, unpacks its picture and copies it to OBJ tiles ITEM_TILE
 * (0x1e0-0x21f in the English build; the original's 0x80-0xbf are the English page's third line);
 * state 4 shows it; state 5, the item put away while the Court Record is open, copies it again
 * once the Record has gone (SYS+8, the mode, back to 6 or under).  Animated effects copy their
 * pictures to OBJ tiles too, each frame of their animation (the table at 0x08046b30), and two
 * dozen of them have tiles among the item's: the shout bubbles (effects 1-9, 192 tiles from
 * 0x1e8), Franziska's whip (28-30, from 0x200) and others.  In the original, with the item in
 * 0x80-0xbf, none did.  A bubble or a whip while an item is up wrote its picture over the
 * item's, which then showed the bubble's letters in its own colours until it was put away
 * (0.16.95: Objection! over the crystal sphere in episode 5).
 *
 * So, from 0.16.95: while an effect in that set (ITEM_EFFECTS, from the build) is running and the
 * item is up (state 4), the item's sprite is hidden; once none is running and no bubble sprite
 * is left on its tiles, its picture is copied again (the copy states 3 and 5 make, 0x080157e0)
 * and the sprite shown as it was.  The
 * item is out of sight while the effect plays, and comes back whole.  States 3 and 5 wait (doing
 * nothing that frame, the state staying) while such an effect is running, or (since 0.16.89)
 * while a sprite in the bubbles' palette uses the item's tiles, in the OAM shadow or in OAM
 * itself (a bubble stays a frame or two after its effect has gone): the item comes up after it.
 * The script goes on as before (command 0x13 takes its 16 frames all the same).  The waits end
 * after MAX_WAIT frames whatever is there (an effect, MAX_EFFECT_WAIT).
 */
#include "gba.h"

#define OAM_SH      ((volatile u16*)0x03002ba0)   /* OAM shadow, 4 halfwords per entry */
#define OAM         ((volatile u16*)0x07000000)
#define BUBBLE_PAL  11                             /* the bubbles' OBJ palette */
#define ITEM_PAL    1
#define ITEM_TILES  64
#define MAX_WAIT    60
#define MAX_EFFECT_WAIT 240
#define ITEM_STATE  0x99                           /* SYS+0x99 */
#define MODE        8                              /* SYS+8: 7 while the Court Record is up */
#define ITEM_FRAME(s) ((void (*)(volatile u8*))0x0801545d)(s)
#define ITEM_COPY(s)  ((void (*)(volatile u8*))0x080157e1)(s)   /* unpack and copy the picture */
#define EFFECT_SLOT(k) ((volatile u32*)(0x0300103c - (k) * 0x44))   /* 32 slots, +0 bit 28 running */
#define EFFECT_NUM(k)  (*(volatile u16*)(0x0300103c - (k) * 0x44 + 0xc))

static const u32 item_effects[8] = ITEM_EFFECTS;  /* bit n: effect n's tiles meet the item's */

static u8 waited;
static u8 spoiled;          /* the item is hidden for an effect; its picture is to be copied again */
static u16 shown_attr0;     /* its sprite's attr0 from before that */

/* tiles a sprite takes, by attr0 shape and attr1 size */
static const u8 tiles[3][4] = { { 1, 4, 16, 64 }, { 2, 4, 8, 32 }, { 2, 4, 8, 32 } };

static int item_entry(int i, volatile u16* oam) {
    return (oam[i * 4 + 2] & 0x3ff) == ITEM_TILE && oam[i * 4 + 2] >> 12 == ITEM_PAL;
}

static int over_item(volatile u16* oam) {
    for (int i = 0; i < 128; i++) {
        u32 a0 = oam[i * 4], a1 = oam[i * 4 + 1], a2 = oam[i * 4 + 2];
        if (item_entry(i, oam) || (a0 & 0x300) == 0x200 || a0 >> 14 == 3 || a2 >> 12 != BUBBLE_PAL) continue;
        u32 t0 = a2 & 0x3ff, t1 = t0 + tiles[a0 >> 14][a1 >> 14];
        if (t0 < ITEM_TILE + ITEM_TILES && t1 > ITEM_TILE) return 1;
    }
    return 0;
}

/* an effect whose pictures go into the item's tiles is running */
static int effect_over_item(void) {
    for (int k = 0; k < 32; k++) {
        if (!(*EFFECT_SLOT(k) & (1u << 28))) continue;
        u32 n = EFFECT_NUM(k);
        if (n < 256 && item_effects[n >> 5] >> (n & 31) & 1) return 1;
    }
    return 0;
}

/* the shadow entry the item's update uses (65; 72 or 0 in some modes), -1 if none has it */
static int item_sprite(void) {
    static const u8 entries[3] = { 65, 72, 0 };
    for (int j = 0; j < 3; j++)
        if (item_entry(entries[j], OAM_SH)) return entries[j];
    return -1;
}

/* in place of 0x0801545c at both its calls */
void item_frame(volatile u8* sys) {
    u32 s = sys[ITEM_STATE];
    int busy = effect_over_item();
    if ((s == 3 || (s == 5 && sys[MODE] <= 6)) &&
        ((busy && waited < MAX_EFFECT_WAIT) || (waited < MAX_WAIT && (over_item(OAM_SH) || over_item(OAM))))) {
        waited++;
        return;
    }
    waited = 0;
    ITEM_FRAME(sys);
    int i = item_sprite();
    if (sys[ITEM_STATE] != 4 || sys[MODE] > 6 || i < 0) {
        spoiled = 0;
        return;
    }
    if (busy || (spoiled && (over_item(OAM_SH) || over_item(OAM)))) {
        if (!spoiled) { shown_attr0 = OAM_SH[i * 4]; spoiled = 1; }
        OAM_SH[i * 4] = (OAM_SH[i * 4] & ~0x300) | 0x200;
        OAM[i * 4] = OAM_SH[i * 4];
    } else if (spoiled) {
        ITEM_COPY(sys);
        if ((OAM_SH[i * 4] & 0x300) == 0x200) OAM_SH[i * 4] = shown_attr0;
        spoiled = 0;
    }
}

void _start(void) {}
