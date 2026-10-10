/* The verdict from the DS version: Not Guilty / Guilty in its letters (patches/verdict.py).
 *
 * The original verdict mode (mode 9, 0x0800f23c, state in SYS+9) zooms its two words in (OAM
 * entries 49 and 50, affine with double size, matrices 0 and 1), each landing with a flash and
 * a slam (states 0-3), then moves them up while they grow (state 4), hides them, and rains
 * confetti for not guilty (states 5-7).  Here the first part follows the DS's English verdict
 * instead: every letter is a 32x64 sprite (OAM entries 51-59) that zooms in from twice its size
 * about its own centre in ten steps, from its frame in the DS's list (Not, then Guilty a second
 * later; Guilty letter by letter), and each landing shakes the screen and plays the slam, as on
 * the DS.  The letters stay for a second after the last has landed and go all at once; then the
 * original goes on from state 4 with its timer run out (the words hidden, then the confetti or
 * the court).  The original's two entries stay hidden.  (A letter is affine only while it zooms
 * in: nine affine sprites with double size would take more of a line's sprite time than there
 * is, and the judge behind them would go.)
 */
#include "gba.h"

#define OAM_SH   ((volatile u16*)0x03002ba0)   /* OAM shadow, 4 halfwords per entry */
#define WORD0    49                            /* the original's two words */
#define FIRST    51                            /* the letters (the confetti, afterwards, uses 58-88) */
#define TILES    ((volatile u32*)0x06013400)   /* OBJ tile 0x1a0 */
#define HIDE     0x0200
#define TALL     0x8000                        /* attr0 shape: 32x64 with size 3 in attr1 */
#define AFFINE2  0x0300                        /* attr0: affine, double size */
#define SIZE3    0xc000
#define BOX_Y    0xef                          /* top of the double-size boxes: centre y 47 */
#define ZOOM     10                            /* steps from twice the size, as on the DS */
#define SLAM_AT  8                             /* the DS plays the slam as the ninth step begins */
#define HOLD     61                            /* frames the letters stay after the last landed */
#define SLAM     0x56                          /* sound */
#define DONE     0x21                          /* state 4's timer run out: the words go at once */

/* the screen shake (0x0800024c, every frame while bit 0 of SYS+0xe8 is set): frames, strength */
#define SHAKE_TIME  ((volatile u16*)(SYS + 0x14))
#define SHAKE_SIZE  ((volatile u8*)(SYS + 0x16))
#define SHAKE_ON    ((volatile u32*)(SYS + 0xe8))

#define PLAY_SE(n)  ((void (*)(u32))0x08015bc9)(n)
#define ORIGINAL(s) ((void (*)(volatile u8*))0x0800f23d)(s)

struct letter { u8 frame, matrix; s16 x; u16 attr2, pad; };   /* x: of the double-size box */
struct verdict { u16 n, words; const u32* tiles; const struct letter* l; };
extern const struct verdict verdicts[2];      /* not guilty, guilty */

/* 0x10000 / size, the size going from 512 to 256 in tenths as the DS computes it */
static const u16 zoom[ZOOM] = { 128, 134, 142, 150, 159, 170, 182, 196, 212, 232 };

static u8 active;                             /* 0, or 1 + the verdict while the letters are up */
static u16 t;                                 /* frames since the verdict began */

/* the end of the handler of command 0x44 (0x080209dc), after it has loaded its pictures */
void verdict_start(void) {
    u32 kind = ((const u16*)TXT_PTR)[-1] ? 1 : 0;   /* the command's argument */
    const struct verdict* v = &verdicts[kind];
    for (u32 i = 0; i < v->words; i++) TILES[i] = v->tiles[i];
    active = 1 + kind;
    t = 0;
}

/* the verdict mode, every frame (entry 9 of the mode table) */
void verdict_mode(volatile u8* sys) {
    if (!active || sys[9] >= 4) { ORIGINAL(sys); return; }
    const struct verdict* v = &verdicts[active - 1];
    int last = 0, slam = 0, end;
    for (int i = 0; i < v->n; i++) {
        const struct letter* l = &v->l[i];
        volatile u16* o = &OAM_SH[(FIRST + i) * 4];
        int d = (int)t - l->frame;
        if (l->frame > last) last = l->frame;
        if (d == SLAM_AT) slam = 1;
        if (d < 0) { o[0] = HIDE; continue; }
        if (d < ZOOM) {                                      /* zooming in */
            volatile u16* m = &OAM_SH[l->matrix * 16 + 3];
            m[0] = zoom[d]; m[4] = 0; m[8] = 0; m[12] = zoom[d];
            o[0] = TALL | AFFINE2 | BOX_Y;
            o[1] = SIZE3 | l->matrix << 9 | (l->x & 0x1ff);
        } else {                                             /* landed */
            o[0] = TALL | ((BOX_Y + 32) & 0xff);
            o[1] = SIZE3 | ((l->x + 16) & 0x1ff);
        }
        o[2] = l->attr2;
    }
    OAM_SH[WORD0 * 4] = HIDE;
    OAM_SH[(WORD0 + 1) * 4] = HIDE;
    if (slam) {
        *SHAKE_TIME = 4; *SHAKE_SIZE = 1; *SHAKE_ON |= 1;
        PLAY_SE(SLAM);
    }
    end = last + ZOOM + HOLD;
    if (t++ < end) return;
    for (int i = 0; i < v->n; i++) OAM_SH[(FIRST + i) * 4] = HIDE;
    active = 0;
    sys[9] = 4; sys[10] = DONE;
    ORIGINAL(sys);
}

void _start(void) {}
