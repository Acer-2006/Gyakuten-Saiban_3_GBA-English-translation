/* The verdict from the DS version: Not Guilty / Guilty in its letters, as the English GS1 has them
 * (patches/verdict.py).
 *
 * The original verdict mode (mode 9, 0x0800f23c, state in SYS+9) zooms its two words in (OAM
 * entries 49 and 50, affine with double size, matrices 0 and 1), each landing with a flash and
 * a slam (states 0-3), then moves them up while they grow (state 4), hides them, and rains
 * confetti for not guilty (states 5-7).  Here the first part follows the DS's English verdict
 * instead: every letter is a sprite (OAM entries 51-59; 32x64, or 64x64 for N and G) that zooms in
 * from twice its size about its own centre in ten steps, from its frame in the DS's list (Not,
 * then Guilty a second later; Guilty letter by letter), and each landing shakes the screen and
 * plays the slam, as on the DS.  The letters stay for a second after the last has landed and go
 * all at once; then the original goes on from state 4 with its timer run out (the words hidden,
 * then the confetti or the court).  The original's two entries stay hidden.
 *
 * A letter is affine only while it zooms in: nine affine sprites with double size would take more
 * of a line's sprite time than there is, and the judge behind them would go.  A letter marked
 * L_SPLIT is drawn, once landed, as 32x32, 32x16 and 32x8 from the same tiles (its entry and
 * entries extra, extra + 1), which stop at its 56th row: Not's o and t, so that the line below them
 * keeps the sprite time the judge needs while Guilty zooms in.
 */
#include "gba.h"

#define OAM_SH   ((volatile u16*)0x03002ba0)   /* OAM shadow, 4 halfwords per entry */
#define WORD0    49                            /* the original's two words */
#define FIRST    51                            /* the letters (the confetti, afterwards, uses 58-88) */
#define HIDE     0x0200
#define TALL     0x8000                        /* attr0 shape: 32x64 with size 3 */
#define WIDE     0x4000                        /* attr0 shape: 32x16 with size 2, 32x8 with size 1 */
#define AFFINE2  0x0300                        /* attr0: affine, double size */
#define SIZE1    0x4000
#define SIZE2    0x8000
#define SIZE3    0xc000
#define ZOOM     10                            /* steps from twice the size, as on the DS */
#define SLAM_AT  8                             /* the DS plays the slam as the ninth step begins */
#define HOLD     61                            /* frames the letters stay after the last landed */
#define SLAM     0x56                          /* sound */
#define DONE     0x21                          /* state 4's timer run out: the words go at once */

#define L_MATRIX 1                             /* affine matrix 1, else 0 */
#define L_SQUARE 2                             /* 64x64, else 32x64 */
#define L_SPLIT  4                             /* landed in three pieces (see above) */

/* the screen shake (0x0800024c, every frame while bit 0 of SYS+0xe8 is set): frames, strength */
#define SHAKE_TIME  ((volatile u16*)(SYS + 0x14))
#define SHAKE_SIZE  ((volatile u8*)(SYS + 0x16))
#define SHAKE_ON    ((volatile u32*)(SYS + 0xe8))

#define PLAY_SE(n)  ((void (*)(u32))0x08015bc9)(n)
#define ORIGINAL(s) ((void (*)(volatile u8*))0x0800f23d)(s)

/* x, y: the corner of the double-size box (y as attr0 has it) */
struct letter { u8 frame, flags; s16 x; u16 attr2; u8 y, extra; };
struct verdict { u16 n, words; const u32* tiles; const struct letter* l; volatile u32* vram; };
extern const struct verdict verdicts[2];      /* not guilty, guilty */

/* 0x10000 / size, the size going from 512 to 256 in tenths as the DS computes it */
static const u16 zoom[ZOOM] = { 128, 134, 142, 150, 159, 170, 182, 196, 212, 232 };

static u8 active;                             /* 0, or 1 + the verdict while the letters are up */
static u16 t;                                 /* frames since the verdict began */

/* the end of the handler of command 0x44 (0x080209dc), after it has loaded its pictures */
void verdict_start(void) {
    u32 kind = ((const u16*)TXT_PTR)[-1] ? 1 : 0;   /* the command's argument */
    const struct verdict* v = &verdicts[kind];
    for (u32 i = 0; i < v->words; i++) v->vram[i] = v->tiles[i];
    active = 1 + kind;
    t = 0;
}

static void hide(const struct verdict* v) {
    for (int i = 0; i < v->n; i++) {
        OAM_SH[(FIRST + i) * 4] = HIDE;
        if (v->l[i].flags & L_SPLIT) {
            OAM_SH[v->l[i].extra * 4] = HIDE;
            OAM_SH[(v->l[i].extra + 1) * 4] = HIDE;
        }
    }
}

/* the verdict mode, every frame (entry 9 of the mode table) */
void verdict_mode(volatile u8* sys) {
    if (!active || sys[9] >= 4) { ORIGINAL(sys); return; }
    const struct verdict* v = &verdicts[active - 1];
    int last = 0, slam = 0, end;
    hide(v);
    for (int i = 0; i < v->n; i++) {
        const struct letter* l = &v->l[i];
        volatile u16* o = &OAM_SH[(FIRST + i) * 4];
        int d = (int)t - l->frame;
        u32 sq = l->flags & L_SQUARE;
        if (l->frame > last) last = l->frame;
        if (d == SLAM_AT) slam = 1;
        if (d < 0) continue;
        if (d < ZOOM) {                                      /* zooming in */
            u32 m = l->flags & L_MATRIX;
            volatile u16* mt = &OAM_SH[m * 16 + 3];
            mt[0] = zoom[d]; mt[4] = 0; mt[8] = 0; mt[12] = zoom[d];
            o[0] = (sq ? 0 : TALL) | AFFINE2 | l->y;
            o[1] = SIZE3 | m << 9 | (l->x & 0x1ff);
            o[2] = l->attr2;
            continue;
        }
        /* landed: plain, the size of the sprite, about the box's centre */
        u32 x = (l->x + (sq ? 32 : 16)) & 0x1ff, y = (l->y + 32) & 0xff;
        if (l->flags & L_SPLIT) {
            volatile u16* e = &OAM_SH[l->extra * 4];
            o[0] = y;                    o[1] = SIZE2 | x; o[2] = l->attr2;        /* 32x32 */
            e[0] = WIDE | ((y + 32) & 0xff); e[1] = SIZE2 | x; e[2] = l->attr2 + 16;   /* 32x16 */
            e[4] = WIDE | ((y + 48) & 0xff); e[5] = SIZE1 | x; e[6] = l->attr2 + 24;   /* 32x8 */
        } else {
            o[0] = (sq ? 0 : TALL) | y;  o[1] = SIZE3 | x; o[2] = l->attr2;
        }
    }
    OAM_SH[WORD0 * 4] = HIDE;
    OAM_SH[(WORD0 + 1) * 4] = HIDE;
    if (slam) {
        *SHAKE_TIME = 4; *SHAKE_SIZE = 1; *SHAKE_ON |= 1;
        PLAY_SE(SLAM);
    }
    end = last + ZOOM + HOLD;
    if (t++ < end) return;
    hide(v);
    active = 0;
    sys[9] = 4; sys[10] = DONE;
    ORIGINAL(sys);
}

void _start(void) {}
